"""Price the L1f short on every venue that offered a shortable instrument (protocol_l1f_venues_20261125.md). Called by
l1f_venues.py mode price. One rule: 4 h hold, 60 s delay, 25% stop."""
import gzip
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor

from core import forced_flow as ff
from core import sweep_stats as ss
from research.studies import forced_flow as FF
from research.studies import l1f_venues as V

FAM = "l1f_reach"
RID = ff.rule_id(FAM, V.HOLD, V.DELAY)
RT_FEES = 0.0022          # 2 x 0.11%


def range_cost(bars, te, x):
    def sl(t):
        b = bars.get(t)
        return max(0.002, 0.5 * (b[1] - b[2]) / b[3]) if b and b[3] > 0 else 0.002
    return RT_FEES + sl(te) + sl(x)


def price_event(e, venues):
    """-> {venue: row} for the venues listed (each row in the forced-flow rows format + extras)."""
    ts, sym = e["ts"], e["sym"]
    t0, t1 = V.span(ts)
    rng = random.Random(f"{ff.SEED}:l1f_reach:{sym}:{int(ts)}")
    picks = ff.pick_control(rng, sym)
    cb = {}
    for c in picks:
        b = FF.um_bars(c + "USDT", ts - 3600, ts + V.HOLD + 900, "5m")
        if b:
            cb[c] = b
    out = {}
    for v in venues:
        bars = V.bars_spot(sym, t0, t1) if v == "binance_spot" else V.FETCH[v](sym, t0, t1)
        if not bars:
            out[v] = None
            continue
        s = ff.short_trade(bars, 60, ts, V.DELAY, V.HOLD)
        if not s:
            out[v] = None
            continue
        cg = ff.control_gross(cb, picks, 300, ts, V.DELAY, V.HOLD)
        out[v] = {"fam": FAM, "sym": sym, "ts": ts, "src": v, "title": e.get("title"), "price_src": v, "overlap_l1f": False,
                  "rules": {RID: [round(s["gross"], 6), None if cg is None else round(cg, 6), round(s["mfe"], 5), round(s["mae"], 5),
                                  s["reason"], s["te"], s["x"]]},
                  "range_cost": round(range_cost(bars, s["te"], s["x"]), 5)}
    return out


def summarize(rows, label):
    """Stats of one set of priced rows (forced-flow evaluate_family on the single rule + extras)."""
    tr = FF.trades_of(rows, RID, FAM, V.HOLD)
    months = ff.MONTHS
    res = {"label": label, "events_priced": len(tr)}
    if not tr:
        return res
    res["all"] = ff.stats([t["net"] for t in tr], months)
    res["notice_level_all"] = FF.notice_level(tr, months)
    res["by_split"] = {k: ff.stats([t["net"] for t in ss.in_split(tr, *ff.BOUNDS[k])], (b - a) / 86400 / 30.4375)
                       for k, (a, b) in ff.BOUNDS.items()}
    res["control_mean"] = FF.ctrl_mean(tr)
    res["placebo_mean"] = ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in tr])
    res["mean_2x_cost"] = ss.mean([t["net"] - t["cost"] - t["fund"] for t in tr])
    rc = [r["rules"][RID][0] - r["range_cost"] - ff.FUND[V.HOLD] for r in rows if r["rules"].get(RID)]
    res["range_slip_variant"] = ff.stats(rc, months)
    res["stopped"] = sum(1 for t in tr if t["reason"] == "stop")
    res["syms"] = sorted({t["sym"] for t in tr})
    table, gate_rows = FF.evaluate_family(FAM, rows)
    res["stage0"] = {"ok": table[RID]["ok"], "gate": table[RID]["gate"]}
    if gate_rows:
        info = ss.judge_family(gate_rows, ff.CFG)
        res["after_stage0"] = {"holm": info, "passed": [r["id"] for r in gate_rows if r.get("passed")],
                               "evaluated": [dict(ss.compact(r, FAM), criteria=r["criteria"], extra=r.get("extra_criteria")) for r in gate_rows]}
    return res


def run(out, events_path, probe_path):
    t_start = time.time()
    doc = json.load(open(probe_path))
    prow = {(r["sym"], int(r["ts"])): r for r in doc["rows"]}
    evs = [e for e in json.load(open(events_path))["l1f"] if (e["sym"], int(e["ts"])) in prow]
    jobs = []
    for e in evs:
        vs = prow[(e["sym"], int(e["ts"]))]["venues"]
        want = [v for v in V.VENUES if vs[v]["shortable"]] + ["binance_spot"]
        jobs.append((e, want))
    with ThreadPoolExecutor(4) as ex:
        priced = list(ex.map(lambda j: price_event(*j), jobs))
    by_event = [(e, p) for (e, _), p in zip(jobs, priced)]
    with gzip.open(os.path.join(out, "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for e, p in by_event:
            f.write(json.dumps({"event": e, "priced": p}, separators=(",", ":")) + "\n")

    def judged(e):
        return e["sym"] not in V.STABLES

    first = {}                                   # event -> (venue, row) on the first shortable perp venue in the fixed priority
    for e, p in by_event:
        for v in V.VENUES:
            if p.get(v):
                first[(e["sym"], int(e["ts"]))] = (v, p[v])
                break
    setA = [r for (v, r) in first.values() if v == "binance_um" and r["sym"] not in V.STABLES]
    setB = [r for (v, r) in first.values() if v != "binance_um" and r["sym"] not in V.STABLES]
    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": round(ff.MONTHS, 2), "events": len(evs),
               "stables_excluded": sorted(V.STABLES & {e["sym"] for e in evs}), "probe_summary": doc["summary"],
               "coverage_first_venue": {}, "sets": {}, "errors": dict(V.ERR)}
    for v, _r in first.values():
        summary["coverage_first_venue"][v] = summary["coverage_first_venue"].get(v, 0) + 1
    summary["no_perp_anywhere"] = sorted(e["sym"] for e in evs if (e["sym"], int(e["ts"])) not in first)
    summary["sets"]["A_binance_um"] = summarize(setA, "A: Binance USDT-M perp")
    summary["sets"]["B_other_venues"] = summarize(setB, "B: no Binance perp, perp on another venue (fixed priority)")
    summary["sets"]["AB_reachable"] = summarize(setA + setB, "A+B reachable by perp")
    for v in V.VENUES:
        rows = [p[v] for e, p in by_event if p.get(v) and judged(e)]
        if rows:
            summary["sets"][f"venue_{v}"] = summarize(rows, f"{v} alone")
    spot = [p["binance_spot"] for e, p in by_event if p.get("binance_spot") and judged(e)]
    summary["sets"]["margin_upper_bound_all"] = summarize(spot, "UPPER BOUND, not point-in-time verified: Binance spot priced, borrow assumed")
    nop = {(r["sym"], int(r["ts"])) for r in spot} - {(r["sym"], int(r["ts"])) for r in setA}
    summary["sets"]["margin_upper_bound_no_binance_perp"] = summarize(
        [r for r in spot if (r["sym"], int(r["ts"])) in nop], "UPPER BOUND: spot-priced, notices with no Binance perp")
    summary["seconds"] = round(time.time() - t_start)
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    for k, v in summary["sets"].items():
        print(k, json.dumps({a: v.get(a) for a in ("events_priced", "all", "by_split", "control_mean", "placebo_mean", "mean_2x_cost")}, default=str))
        print("   stage0", json.dumps(v.get("stage0", {}).get("ok")), v.get("stage0", {}).get("gate", {}).get("reason"))
