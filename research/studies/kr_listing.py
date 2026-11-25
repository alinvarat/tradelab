"""D2 (protocol_kr_listing_20261126.md): long the global perp after an Upbit / Bithumb KRW-market listing notice. Modes:

    python research/studies/kr_listing.py <out> events          # Wayback notices -> events + timestamp audit, NO prices
    python research/studies/kr_listing.py <out> run <frozen>    # price the frozen events, stage-0 gate, Holm, placebo, control
GitHub Actions only (workflow kr_listing.yml)."""
import gzip
import html
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import forced_flow as ff   # noqa: E402
from core import kr_listing as kl    # noqa: E402
from core import sweep_stats as ss   # noqa: E402
from research.studies import forced_flow as sf   # noqa: E402


def upbit_notices(stats):
    """All Upbit notices from API snapshots: {id: (capture stamp, posted ts, title)}; title/time from the EARLIEST capture."""
    first = {}
    one = sf.cdx("api-manager.upbit.com/api/v1/announcements/") or []
    lists = sf.cdx("api-manager.upbit.com/api/v1/announcements?", "&filter=" + quote("original:.*per_page.*"), limit=6000, collapse="timestamp:8") or []
    stats["upbit_snapshots"] = {"single": len(one), "list": len(lists)}
    jobs = sorted([tuple(x) for x in one if re.search(r"/announcements/\d+", x[1])] + [tuple(x) for x in lists[:4500]])

    def work(j):
        t = sf.snap(j[0], j[1], "upbit")
        try:
            d = json.loads(t)["data"]
        except Exception:  # noqa: BLE001
            return j[0], []
        return j[0], d.get("notices") or ([d] if d.get("title") else [])
    with ThreadPoolExecutor(6) as ex:
        for stamp, notes in ex.map(work, jobs):
            for n in notes:
                if n.get("id") not in first:
                    first[n.get("id")] = (stamp, n)
    out = {}
    for i, (stamp, n) in first.items():
        raw = n.get("first_listed_at") or n.get("listed_at")
        try:
            out[i] = (stamp, sf.kst(raw), n.get("title", ""), raw)
        except Exception:  # noqa: BLE001
            continue
    stats["upbit_notices"] = len(out)
    return out


def bithumb_notices(stats):
    rows = sf.cdx("feed.bithumb.com/notice/") or []
    ids = {}
    for t, u in rows:
        m = re.search(r"/notice/(\d+)", u)
        if m and m.group(1) not in ids:
            ids[m.group(1)] = (t, u)
    stats["bithumb_notice_pages"] = len(ids)

    def work(j):
        t, u = j
        h = sf.snap(t, u, "bithumb")
        if not h:
            return None
        txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", h))))
        m = re.search(r"^.*공지사항\s+(.+?)\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+공유하기", txt)
        return (t, sf.kst(m.group(2)), m.group(1), m.group(2)) if m else None
    out = {}
    with ThreadPoolExecutor(6) as ex:
        for i, got in zip(ids, ex.map(work, list(ids.values()))):
            if got:
                out[i] = got
    stats["bithumb_notices"] = len(out)
    return out


def audit(src, notes, ev_counts):
    """Timestamp audit (no prices): capture lag (capture - posted; posted after capture is impossible for a correct clock/zone),
    KST hour-of-day histogram of all notices and of listing notices, per-month listing coverage."""
    lag, late, hours_all, hours_lst, months = [], 0, [0] * 24, [0] * 24, {}
    for stamp, ts, title, raw in notes.values():
        cap = sf.cap_ts(stamp)
        if ts > cap + 60:
            late += 1
        elif ts >= ff.START:
            lag.append(cap - ts)
        h = int(((ts + 9 * 3600) % 86400) // 3600)
        hours_all[h] += 1
        if kl.listing_title(title):
            hours_lst[h] += 1
            if ff.in_window(ts):
                m = time.strftime("%Y-%m", time.gmtime(ts))
                months[m] = months.get(m, 0) + 1
    lag.sort()
    q = (lambda p: round(lag[int(p * (len(lag) - 1))] / 60, 1)) if lag else (lambda p: None)
    return {"src": src, "notices": len(notes), "posted_after_capture": late, "capture_lag_min": {"p0": q(0), "p10": q(0.1), "p50": q(0.5), "p90": q(0.9)},
            "share_lag_le_10min": round(sum(1 for v in lag if v <= 600) / len(lag), 3) if lag else None,
            "kst_hour_all": hours_all, "kst_hour_listing": hours_lst, "listing_by_month": dict(sorted(months.items()))}


def build_events(out_dir):
    stats, ev, aud = {}, [], []
    titles = []
    for src, fn in (("upbit", upbit_notices), ("bithumb", bithumb_notices)):
        try:
            notes = fn(stats)
        except Exception as e:  # noqa: BLE001
            stats[src + "_error"] = repr(e)[:200]
            notes = {}
        late = 0
        for i, (stamp, ts, title, raw) in notes.items():
            if ff.in_window(ts):
                titles.append({"src": src, "id": i, "ts": ts, "raw": raw, "cap": stamp, "title": title[:160]})
            if not kl.listing_title(title):
                continue
            if ts > sf.cap_ts(stamp) + 60:
                late += 1
                continue
            ev += [{"fam": kl.FAM, "sym": s, "ts": ts, "src": src, "title": title[:140], "raw": raw} for s in kl.listing_symbols(title)]
        stats[src + "_time_after_capture_dropped"] = late
        aud.append(audit(src, notes, None))
    stats["fetch_failures"], stats["fetch_error_kinds"] = dict(sf.FAILS), dict(sf.ERRS)
    allev = [e for e in ev if ff.in_window(e["ts"])]
    events = kl.dedupe(allev)
    for e in events:
        e["venues"] = sorted({x["src"] for x in allev if x["sym"] == e["sym"] and abs(x["ts"] - e["ts"]) < kl.DEDUPE_S})
    counts = {"raw_listing_events": len(allev), "events": len(events), "by_src_first": {}, "by_split": {}}
    for e in events:
        counts["by_src_first"][e["src"]] = counts["by_src_first"].get(e["src"], 0) + 1
        sp = next((k for k, (a, b) in ff.BOUNDS.items() if a <= e["ts"] < b), "test")
        counts["by_split"][sp] = counts["by_split"].get(sp, 0) + 1
    doc = {"events": events, "stats": stats, "counts": counts, "audit": aud, "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(out_dir, "events.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False)
    with gzip.open(os.path.join(out_dir, "titles.jsonl.gz"), "wt", encoding="utf-8") as f:
        for t in sorted(titles, key=lambda t: t["ts"]):
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in doc.items() if k != "events"}, ensure_ascii=False, default=str)[:6000], flush=True)
    for e in events[:12]:
        print("SAMPLE", e["sym"], time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(e["ts"] + 9 * 3600)), "KST", e["src"], e["raw"], e["title"][:70], flush=True)
    return doc


# ---------------------------------------------------------------- pricing
def process_event(e):
    sym, ts = e["sym"], e["ts"]
    span = max(kl.HOLDS) + max(kl.DELAYS) + 3 * 60 + 600
    bars, src = sf.perp_bars(sym, ts, span)
    row = {**e, "price_src": src, "rules": {}, "dropped": []}
    if bars is None:
        return row
    rng = random.Random(f"{kl.SEED}:{sym}:{int(ts)}")
    picks = ff.pick_control(rng, sym)
    cb = {}
    for c in picks:
        b = sf.um_bars(c + "USDT", ts - 3600, ts + span, "5m")
        if b:
            cb[c] = b
    for rid, h, d in kl.family_rules():
        s = kl.long_trade(bars, 60, ts, d, h)
        if not s:
            row["dropped"].append(rid)
            continue
        cg = kl.control_gross(cb, picks, 300, ts, d, h)
        row["rules"][rid] = [round(s["gross"], 6), None if cg is None else round(cg, 6), round(s["mfe"], 5), round(s["mae"], 5), s["reason"], s["te"], s["x"]]
    return row


def trades_of(rows, rid, hold, src=None):
    out = []
    for r in rows:
        v = r["rules"].get(rid)
        if not v or (src and r["src"] != src):
            continue
        t = kl.make_trade(r["sym"], r["ts"], {"te": v[5], "x": v[6], "gross": v[0], "mfe": v[2], "mae": v[3], "reason": v[4]}, hold, v[1])
        t["nid"] = f"{r['src']}|{int(r['ts'])}|{r['sym']}"
        out.append(t)
    return sorted(out, key=lambda t: t["t"])


def split_stats(trades):
    return {k: ff.stats([t["net"] for t in ss.in_split(trades, *ff.BOUNDS[k])], (ff.BOUNDS[k][1] - ff.BOUNDS[k][0]) / 86400 / 30.4375) for k in ff.BOUNDS}


def evaluate(rows, cfg):
    cfg = cfg or kl.CFG
    table, gate_rows = {}, []
    t0, t1 = ff.BOUNDS["train"]
    train_days = (t1 - t0) / 86400
    for rid, h, d in kl.family_rules():
        tr_all = trades_of(rows, rid, h)
        tr = ss.in_split(tr_all, t0, t1)
        ok, info = ss.gate(tr, {"size": kl.SIZE}, cfg, train_days)
        cm = sf.ctrl_mean(tr)
        info = dict(info, id=rid, control_mean_train=cm)
        if ok and cm is not None and (info["train_mean"] or 0) <= cm:
            ok, info["reason"] = False, "train net mean not above the random-control mean"
        table[rid] = {"gate": info, "all": ff.stats([t["net"] for t in tr_all], ff.MONTHS), "by_split": split_stats(tr_all),
                      "gross_mean_by_split": {k: ss.mean([t["gross"] for t in ss.in_split(tr_all, *ff.BOUNDS[k])]) for k in ff.BOUNDS},
                      "control_mean_by_split": {k: sf.ctrl_mean(ss.in_split(tr_all, *ff.BOUNDS[k])) for k in ff.BOUNDS},
                      "placebo_mean_by_split": {k: ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in ss.in_split(tr_all, *ff.BOUNDS[k])]) for k in ff.BOUNDS},
                      "mean_2x_cost_all": ss.mean([t["net"] - t["cost"] for t in tr_all]),
                      "by_src_all": {s: ff.stats([t["net"] for t in trades_of(rows, rid, h, s)], ff.MONTHS) for s in ("upbit", "bithumb")},
                      "ok": ok}
        if ok:
            r = {"id": rid, "gate": info, "status": "ok", **ss.evaluate(tr_all, {"size": kl.SIZE}, ff.BOUNDS)}
            va, te = ss.in_split(tr_all, *ff.BOUNDS["validation"]), ss.in_split(tr_all, *ff.BOUNDS["test"])
            cv, ct = sf.ctrl_mean(va), sf.ctrl_mean(te)
            r["extra_criteria"] = {"val_beats_control": (ss.mean([t["net"] for t in va]) or 0) > (cv if cv is not None else 9),
                                   "test_beats_control": (ss.mean([t["net"] for t in te]) or 0) > (ct if ct is not None else 9)}
            gate_rows.append(r)
    return table, gate_rows


def main():
    out_dir = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "events"
    os.makedirs(out_dir, exist_ok=True)
    if mode == "events":
        build_events(out_dir)
        return
    doc = json.load(open(sys.argv[3]))
    events = doc["events"]
    with open(os.path.join(out_dir, "events.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False)
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(process_event, events))
    print("rows", len(rows), "seconds", round(time.time() - t0), flush=True)
    with gzip.open(os.path.join(out_dir, "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    cov = {"events": len(events), "priced_rows": sum(1 for r in rows if r["rules"]), "by_src": {}, "dropped_rule_instances": sum(len(r["dropped"]) for r in rows)}
    for r in rows:
        cov["by_src"][r["price_src"]] = cov["by_src"].get(r["price_src"], 0) + 1
    table, gate_rows = evaluate(rows, kl.CFG)
    _, strict_rows = evaluate(rows, kl.CFG_STRICT)
    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": round(ff.MONTHS, 2), "coverage": cov, "rules": table,
               "rules_tested": len(kl.family_rules())}
    for name, rows_, cfg in (("event_gate", gate_rows, kl.CFG), ("sweep_strict_gate", strict_rows, kl.CFG_STRICT)):
        for r in rows_:
            r["family"] = kl.FAM
        info = ss.judge_family(rows_, cfg) if rows_ else {"holm_m": 0}
        summary[name] = {"stage0_survivors": len(rows_), "holm": info, "passed": [r["id"] for r in rows_ if r.get("passed")],
                         "evaluated": [dict(ss.compact(r, kl.FAM), criteria=r["criteria"], extra=r.get("extra_criteria")) for r in rows_]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    print(json.dumps(cov))
    for rid, v in table.items():
        print(rid, "gate_ok", v["ok"], v["gate"].get("reason"), "train", v["by_split"]["train"], "val", v["by_split"]["validation"], "test", v["by_split"]["test"], flush=True)
    print(json.dumps({k: summary[k] for k in ("event_gate", "sweep_strict_gate")}, default=str)[:3000])


if __name__ == "__main__":
    main()
