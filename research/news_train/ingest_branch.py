"""Reader for the pod's news-ingest log as published on branch data/news-ingest by core/news_publish.py
(addendum research/news_train/protocol_ingest_addendum_20261126.md). Pure functions, stdlib only, no network, no outcomes.

Layout read: <root>/news_ingest/<YYYYMMDD>/<start>-<end>.jsonl (a flat <root>/news_ingest/<YYYYMMDD>.jsonl, the pod's own file
format, is read too). Parts may overlap or repeat; rows are de-duplicated on (event, source, key)."""
import json
import os
from statistics import median

WIRES = ("prnewswire", "globenewswire", "businesswire")
PROXY_LAG_S = 93          # round 2's fixed entry lag (params entry.lag_s); the log measures the real seen-minus-published time


def files(root):
    base = os.path.join(root, "news_ingest")
    out = []
    if os.path.isdir(base):
        for d, _, fs in os.walk(base):
            out += [os.path.join(d, f) for f in fs if f.endswith(".jsonl")]
    return sorted(out)


def load_rows(root):
    """-> list of unique rows. A missing directory or branch gives []; unreadable lines are skipped."""
    seen, rows = set(), []
    for f in files(root):
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("event") not in ("item", "llm") or not r.get("source") or not r.get("key"):
                continue
            k = (r["event"], r["source"], r["key"])
            if k in seen:
                continue
            seen.add(k)
            rows.append(r)
    return rows


def join(rows):
    """-> {(source, key): {source, key, title, t_pub, res, t_seen, t_llm, llm_s}} from the item row and its optional llm row.
    The pod's own Haiku reading (`parsed`) is deliberately not carried: it comes from another prompt and is never a decision."""
    out = {}
    for r in rows:
        k = (r["source"], r["key"])
        d = out.setdefault(k, {"source": r["source"], "key": r["key"], "title": None, "t_pub": None, "res": None,
                               "t_seen": None, "t_llm": None, "llm_s": None})
        if r["event"] == "item":
            d.update(title=r.get("title"), t_pub=r.get("t_pub"), res=r.get("res"), t_seen=r.get("t_seen"))
        else:
            d.update(t_llm=r.get("t_llm"), llm_s=r.get("llm_s"))
            if d["t_seen"] is None:
                d["t_seen"] = r.get("t_seen")
            if d["t_pub"] is None:
                d["t_pub"] = r.get("t_pub")
    return out


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def timing_for(item_key, joined, source="sec_8k"):
    """Pod timing for one forward item key (round 2 keys are 'sec:<accession>'), or None when the pod has no row for it."""
    d = joined.get((source, item_key))
    if not d or not _num(d.get("t_seen")):
        return None
    gap = d["t_seen"] - d["t_pub"] if _num(d.get("t_pub")) else None
    return {"t_pub_pod": d.get("t_pub"), "t_seen": d["t_seen"], "t_llm": d.get("t_llm"), "res": d.get("res"),
            "seen_minus_pub_s": None if gap is None else round(gap, 3),
            "seen_minus_proxy_s": None if gap is None else round(gap - PROXY_LAG_S, 3)}


def r2_timing(items, joined):
    """Attach pod timing to round-2 forward items (descriptive only: entry, decisions, trigger and scoring never read it).
    -> {'coverage': {...}, 'rows': {key: timing}}. Items without a pod row are listed as missing, never dropped or imputed."""
    rows, miss = {}, 0
    for it in items:
        t = timing_for(it["key"], joined)
        if t is None:
            miss += 1
        else:
            rows[it["key"]] = t
    gaps = [t["seen_minus_pub_s"] for t in rows.values() if t["seen_minus_pub_s"] is not None]
    return {"coverage": {"items": len(items), "with_pod_row": len(rows), "missing": miss,
                         "median_seen_minus_pub_s": round(median(gaps), 3) if gaps else None,
                         "n_seen_slower_than_proxy": sum(1 for g in gaps if g > PROXY_LAG_S)},
            "rows": rows}


def r3_progress(joined):
    """Counts only for the round-3 forward arm: wire press releases the pod saw (no tickers resolved, no bars, no outcomes)."""
    by = {}
    for (src, _), d in joined.items():
        if src in WIRES:
            b = by.setdefault(src, {"n": 0, "n_llm": 0, "gaps": []})
            b["n"] += 1
            b["n_llm"] += 1 if _num(d.get("t_llm")) else 0
            if _num(d.get("t_seen")) and _num(d.get("t_pub")):
                b["gaps"].append(d["t_seen"] - d["t_pub"])
    return {s: {"n": b["n"], "n_llm": b["n_llm"], "median_seen_minus_pub_s": round(median(b["gaps"]), 3) if b["gaps"] else None}
            for s, b in sorted(by.items())}
