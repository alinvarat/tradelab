"""D1 forced-flow proxy fade on small perps (protocol_d1_liq_20261126.md). GitHub Actions only (workflow d1_liq.yml, mode run).

    python research/studies/d1_liq.py shard <out_dir> <i> <n>      # price one hash shard of the symbols, write rows
    python research/studies/d1_liq.py aggregate <out_dir> <rows_dir>   # apply the locked gate and criteria to all shard rows
"""
import glob
import gzip
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import d1_liq as d1       # noqa: E402
from core import sweep_stats as ss  # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402


def month_list():
    return bv.months(d1.T0, d1.T_LAST)


def shard_of(sym, n):
    return int(hashlib.sha1(sym.encode()).hexdigest(), 16) % n


def do_symbol(sym):
    s = d1.Series()
    failed = missing = 0
    for ym in month_list():
        rows = bv.fetch("futures/um", "monthly", "klines", sym, ym, "1m", bv.parse_kline)
        if rows is None:
            failed += 1
        elif not rows:
            missing += 1
        else:
            s.add_rows(rows)
    events = d1.find_events(s)
    return sym, [d1.event_row(s, sym, e) for e in events], {"failed_months": failed, "missing_months": missing, "events": len(events)}


def shard(out_dir, i, n):
    t0 = time.time()
    syms = [x for x in bv.list_symbols("futures/um", "USDT", "klines", "monthly") if d1.is_small(x) and shard_of(x, n) == i]
    rows, meta = [], {}
    with ThreadPoolExecutor(3) as ex:
        for sym, r, m in ex.map(do_symbol, syms):
            rows += r
            meta[sym] = m
    with gzip.open(os.path.join(out_dir, f"rows_{i:02d}.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    with open(os.path.join(out_dir, f"meta_{i:02d}.json"), "w") as f:
        json.dump({"shard": i, "of": n, "symbols": len(syms), "events": len(rows), "seconds": round(time.time() - t0), "per_symbol": meta}, f)
    print("shard", i, "symbols", len(syms), "events", len(rows), "failed_months", sum(m["failed_months"] for m in meta.values()),
          "seconds", round(time.time() - t0), flush=True)


def ctrl_mean(trades):
    return ss.mean([t["ctrl_net"] for t in trades if t.get("ctrl_net") is not None])


def split_stats(tr):
    return {k: d1.stats([t["net"] for t in ss.in_split(tr, *d1.BOUNDS[k])], (d1.BOUNDS[k][1] - d1.BOUNDS[k][0]) / 86400 / 30.4375)
            for k in d1.BOUNDS}


def aggregate(out_dir, rows_dir):
    rows, metas = [], []
    for p in sorted(glob.glob(os.path.join(rows_dir, "**", "rows_*.jsonl.gz"), recursive=True)):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            rows += [json.loads(l) for l in f]
    for p in sorted(glob.glob(os.path.join(rows_dir, "**", "meta_*.json"), recursive=True)):
        metas.append(json.load(open(p)))
    t0, t1 = d1.BOUNDS["train"]
    train_days = (t1 - t0) / 86400
    summ = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": round(d1.MONTHS, 2),
            "shards": len(metas), "symbols": sum(m["symbols"] for m in metas), "raw_events": len(rows),
            "symbols_with_events": len({r["sym"] for r in rows}),
            "failed_months": sum(v["failed_months"] for m in metas for v in m["per_symbol"].values()),
            "events_by_split": {k: sum(1 for r in rows if d1.BOUNDS[k][0] <= r["ts"] < d1.BOUNDS[k][1]) for k in d1.BOUNDS},
            "s2_events": sum(1 for r in rows if r["s2"]), "long_fades": sum(1 for r in rows if r["side"] > 0), "rules": {}, "reported_delay300": {}}
    gate_rows = []
    for rid, size, hold, delay in d1.judged_rules():
        tr_all, busy, nobar = d1.select(rows, size, hold, delay)
        tr = ss.in_split(tr_all, t0, t1)
        ok, info = ss.gate(tr, {"size": d1.SIZE}, d1.CFG, train_days)
        cm = ctrl_mean(tr)
        info = dict(info, id=rid, control_mean_train=cm)
        if ok and cm is not None and (info["train_mean"] or 0) <= cm:
            ok, info["reason"] = False, "train net mean not above the random-control mean"
        by_dir = {("long" if sd > 0 else "short"): d1.stats([t["net"] for t in tr_all if t["side"] == sd], d1.MONTHS) for sd in (1, -1)}
        summ["rules"][rid] = {"gate": info, "ok": ok, "all": d1.stats([t["net"] for t in tr_all], d1.MONTHS), "by_split": split_stats(tr_all),
                              "gross_by_split": {k: ss.mean([t["gross"] for t in ss.in_split(tr_all, *d1.BOUNDS[k])]) for k in d1.BOUNDS},
                              "control_by_split": {k: ctrl_mean(ss.in_split(tr_all, *d1.BOUNDS[k])) for k in d1.BOUNDS},
                              "placebo_by_split": {k: ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in ss.in_split(tr_all, *d1.BOUNDS[k])])
                                                   for k in d1.BOUNDS},
                              "by_direction_all": by_dir, "skipped_busy": busy, "skipped_no_bar": nobar,
                              "stop_share": round(sum(1 for t in tr_all if t["reason"] == "stop") / max(1, len(tr_all)), 4)}
        if ok:
            r = {"id": rid, "gate": info, "status": "ok", **ss.evaluate(tr_all, {"size": d1.SIZE}, d1.BOUNDS)}
            va, te = ss.in_split(tr_all, *d1.BOUNDS["validation"]), ss.in_split(tr_all, *d1.BOUNDS["test"])
            cv, ct = ctrl_mean(va), ctrl_mean(te)
            r["extra_criteria"] = {"val_beats_control": (ss.mean([t["net"] for t in va]) or 0) > (cv if cv is not None else 9),
                                   "test_beats_control": (ss.mean([t["net"] for t in te]) or 0) > (ct if ct is not None else 9)}
            gate_rows.append(r)
    for rid, size, hold, delay in d1.reported_rules():
        tr_all, busy, _ = d1.select(rows, size, hold, delay)
        summ["reported_delay300"][rid] = {"all": d1.stats([t["net"] for t in tr_all], d1.MONTHS), "by_split": split_stats(tr_all)}
    fam = ss.judge_family(gate_rows, d1.CFG) if gate_rows else {"holm_m": 0}
    summ["gate"] = {"rules_tested": len(d1.judged_rules()), "stage0_survivors": len(gate_rows), "holm": fam,
                    "passed": [r["id"] for r in gate_rows if r.get("passed")],
                    "evaluated": [dict(ss.compact(r), criteria=r["criteria"]) for r in gate_rows]}
    closest = min(summ["rules"].items(), key=lambda kv: -(kv[1]["gate"].get("x") or -9))
    summ["closest_by_train_x"] = {"id": closest[0], "gate": closest[1]["gate"]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    print(json.dumps(summ, default=str)[:6000], flush=True)


def main():
    mode, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "shard":
        shard(out_dir, int(sys.argv[3]), int(sys.argv[4]))
    elif mode == "aggregate":
        aggregate(out_dir, sys.argv[3])
    else:
        raise SystemExit("mode must be shard or aggregate")


if __name__ == "__main__":
    main()
