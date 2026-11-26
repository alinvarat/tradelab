"""Weekly review of the live bot's own outcomes (pure: no network, no files, no model). Input rows are the pod's append-only
`desk_outcomes` rows (one per scored candidate and horizon, see LlmTrader._outcome_row) and the ingest log rows; the runner
research/llm_trader/weekly.py reads them from the data branches and writes a report plus a proposal for the next protocol tag.

Rules of the review (the same as core/desk_rules.py): cells are shrunk toward zero (mean x n / (n + K)); overlapping candidates
are collapsed to one row per symbol, day, action and horizon before anything is counted; a change is only proposed from a cell
with at least CLUSTER_MIN clusters on at least DAYS_MIN distinct days; proposals can only veto, shrink or relax a veto, never
enlarge a trade or flip a side. Nothing here changes the bot: the proposal is a PR for a human or an AI to review and apply as
a new tag with its own addendum."""
import json
import re
import time

from . import desk_rules as dr

CLUSTER_MIN = 30
DAYS_MIN = 5
VETO_SHRUNK = -1.0        # percent: a long-side 1 d cell this negative (shrunk) supports a new veto
RELAX_SHRUNK = 0.5        # percent: vetoed entries that would have earned this much (shrunk) support relaxing the rule
HORIZONS = {3600: "1h", 86400: "1d"}


def next_tag(tag):
    m = re.fullmatch(r"v(\d+)\.(\d+)", tag)
    return f"v{m.group(1)}.{int(m.group(2)) + 1}" if m else tag + "+1"


def load_rows(lines):
    out, seen = [], set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("abn") is None or r.get("ts") is None:
            continue
        k = (r.get("symbol"), r.get("ts"), r.get("h"), r.get("action"))
        if k in seen:                       # a part uploaded twice with other boundaries must not double count
            continue
        seen.add(k)
        out.append(r)
    return out


def _day(ts):
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def collapse(rows):
    """One row per (symbol, UTC day, action, horizon): the first one scored. Repeated cycles on the same symbol overlap."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["ts"]):
        k = (r["symbol"], _day(r["ts"]), r["action"], r["h"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _sign(r):
    return -1.0 if r["action"] == "short" else 1.0


def _stat(vals, days):
    n = len(vals)
    if not n:
        return {"clusters": 0, "days": 0, "mean_pct": None, "shrunk_pct": None, "hit": None}
    m = sum(vals) / n * 100
    return {"clusters": n, "days": len(days), "mean_pct": round(m, 3), "shrunk_pct": round(dr.shrink(m, n), 3),
            "hit": round(sum(v > 0 for v in vals) / n, 2)}


def cell_table(rows):
    """Cells as the bot's desk_stats builds them (source/action/horizon and type:<news type>/action/horizon), from collapsed rows."""
    groups, days = {}, {}
    for r in rows:
        lab = HORIZONS.get(r["h"])
        if not lab:
            continue
        keys = [f"{r.get('src') or 'mover'}/{r['action']}/{lab}"]
        if r.get("news_type"):
            keys.append(f"type:{r['news_type']}/{r['action']}/{lab}")
        for k in keys:
            groups.setdefault(k, []).append(_sign(r) * r["abn"])
            days.setdefault(k, set()).add(_day(r["ts"]))
    return {k: _stat(v, days[k]) for k, v in sorted(groups.items())}


def rule_scores(rows):
    """What each rule did: for vetoed rows, the return the entry would have earned (buy +1, short -1 on the abnormal return)."""
    by, days = {}, {}
    for r in rows:
        if r.get("veto") and r["action"] in ("buy", "short") and r["h"] in HORIZONS:
            k = f"{r['veto']}/{HORIZONS[r['h']]}"
            by.setdefault(k, []).append(_sign(r) * r["abn"])
            days.setdefault(k, set()).add(_day(r["ts"]))
    return {k: {**_stat(v, days[k]), "reading": "vetoed entries would have earned this (positive = the rule cost money)"} for k, v in sorted(by.items())}


def input_scores(rows):
    """Did an input move P&L? Mean signed outcome of acted (buy/short) candidates split by whether an input was present."""
    acted = [r for r in rows if r["action"] in ("buy", "short") and not r.get("veto") and r["h"] in HORIZONS]
    splits = {"forced_flow": lambda r: bool(r.get("forced")), "stated_expected_move": lambda r: r.get("em") is not None,
              "a_feed_was_stale": lambda r: bool(r.get("stale"))}
    out = {}
    for name, f in splits.items():
        for label, want in (("present", True), ("absent", False)):
            for h, hl in HORIZONS.items():
                sel = [r for r in acted if r["h"] == h and f(r) is want]
                out[f"{name}={label}/{hl}"] = _stat([_sign(r) * r["abn"] for r in sel], {_day(r["ts"]) for r in sel})
    return out


def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def feed_quality(ingest_rows, days):
    """Per source from the ingest log: items, median and p90 of seen-minus-published (second-resolution rows), and the number of
    days of the window with no item at all (a broken or silent feed)."""
    by = {}
    for r in ingest_rows:
        if r.get("event") != "item" or not r.get("t_seen"):
            continue
        s = by.setdefault(r["source"], {"n": 0, "lat": [], "days": set()})
        s["n"] += 1
        s["days"].add(_day(r["t_seen"]))
        if r.get("lat_s") is not None and r.get("res") != "m":
            s["lat"].append(r["lat_s"])
    out = {}
    for src, s in sorted(by.items()):
        out[src] = {"items": s["n"], "median_s": None if not s["lat"] else round(_pct(s["lat"], 0.5), 1),
                    "p90_s": None if not s["lat"] else round(_pct(s["lat"], 0.9), 1), "days_with_items": len(s["days"]),
                    "silent_days": max(0, days - len(s["days"]))}
    return out


def stale_share(rows):
    cyc = [r for r in rows if r["h"] == 3600]
    if not cyc:
        return {}
    cnt = {}
    for r in cyc:
        for f in r.get("stale") or []:
            cnt[f] = cnt.get(f, 0) + 1
    return {f: round(c / len(cyc), 2) for f, c in sorted(cnt.items())}


def propose(rows, ingest_rows=(), window_days=7, tag=None):
    tag = tag or dr.TAG
    allrows = collapse(rows)
    cells = cell_table(allrows)
    rules = rule_scores(allrows)
    changes = []
    for k, c in cells.items():
        if not k.endswith("/1d") or c["clusters"] < CLUSTER_MIN or c["days"] < DAYS_MIN:
            continue
        side = k.split("/")[1]
        if side in ("hold", "buy") and c["shrunk_pct"] <= VETO_SHRUNK:
            changes.append({"id": f"veto:{k}", "kind": "veto",
                            "text": f"veto or halve new long entries for cell {k}: its long-side 1 d history is negative",
                            "evidence": c})
    for k, c in rules.items():
        if c["clusters"] >= CLUSTER_MIN and c["days"] >= DAYS_MIN and c["shrunk_pct"] >= RELAX_SHRUNK:
            changes.append({"id": f"relax:{k}", "kind": "relax",
                            "text": f"relax rule {k.split('/')[0]}: entries it vetoed would have earned {c['shrunk_pct']:+.2f}% (shrunk) at {k.split('/')[1]}",
                            "evidence": c})
    ts = [r["ts"] for r in allrows]
    return {"current_tag": tag, "next_tag": next_tag(tag),
            "window": {"rows": len(rows), "clusters": len(allrows), "days": len({_day(t) for t in ts}),
                       "from": _day(min(ts)) if ts else None, "to": _day(max(ts)) if ts else None},
            "thresholds": {"cluster_min": CLUSTER_MIN, "days_min": DAYS_MIN, "shrink_k": dr.SHRINK_K,
                           "veto_shrunk_pct": VETO_SHRUNK, "relax_shrunk_pct": RELAX_SHRUNK},
            "changes": changes, "cells": cells, "rule_scores": rules, "input_scores": input_scores(allrows),
            "stale_share": stale_share(allrows), "feed_quality": feed_quality(list(ingest_rows), window_days),
            "note": "no change proposed: no cell or rule reached the cluster and day floors with a large enough shrunk effect"
                    if not changes else "proposals can only veto, shrink or relax a veto; none enlarges a trade or flips a side"}


def render_md(p, today):
    w = p["window"]
    L = [f"# Bot weekly review {today} (current {p['current_tag']}, proposal for {p['next_tag']})", "",
         f"Window {w['from']} to {w['to']}: {w['rows']} outcome rows, {w['clusters']} after collapsing overlapping candidates, {w['days']} days.",
         f"Floors for any change: {p['thresholds']['cluster_min']} clusters on {p['thresholds']['days_min']} days; cells shrunk by n/(n+{p['thresholds']['shrink_k']}).",
         "", "## Proposed changes (each with its evidence)"]
    L += [f"- **{c['id']}**: {c['text']}. Evidence: {json.dumps(c['evidence'])}" for c in p["changes"]] or [f"- None. {p['note']}"]
    L += ["", "## Cells (SPY-relative, signed; hold = long return of a passed candidate)"]
    L += [f"- {k}: clusters {c['clusters']}, days {c['days']}, mean {c['mean_pct']}%, shrunk {c['shrunk_pct']}%, hit {c['hit']}" for k, c in p["cells"].items()]
    L += ["", "## What each rule did (vetoed entries scored afterwards)"]
    L += [f"- {k}: clusters {c['clusters']}, days {c['days']}, mean {c['mean_pct']}%, shrunk {c['shrunk_pct']}%" for k, c in p["rule_scores"].items()] or ["- no vetoed candidate has an outcome yet"]
    L += ["", "## Did an input move P&L (acted entries, signed, SPY-relative)"]
    L += [f"- {k}: clusters {c['clusters']}, mean {c['mean_pct']}%, shrunk {c['shrunk_pct']}%" for k, c in p["input_scores"].items() if c["clusters"]] or ["- no acted entry has an outcome yet"]
    L += ["", "## Data quality", f"- Share of 1 h outcome rows with a stale feed: {json.dumps(p['stale_share']) or '{}'}"]
    L += [f"- {s}: {q['items']} items, median {q['median_s']} s, p90 {q['p90_s']} s, silent days {q['silent_days']}" for s, q in p["feed_quality"].items()]
    L += ["", "Rules apply only through a new tag: a branch with the code change, a tag bump and a dated addendum, reviewed as a PR. This report changes nothing."]
    return "\n".join(L) + "\n"
