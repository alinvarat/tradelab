"""P1 deep resting orders on small perps (protocol_p1p4_20261126.md). GitHub Actions only (workflow p1p4.yml).

    python research/studies/p1_rest.py shard <out_dir> <i> <n>                    # price one hash shard of the symbols; rows per cell + audit of a fill sample
    python research/studies/p1_rest.py aggregate <out_dir> <shards_dir> <ff_rows>  # locked gate, criteria, controls, L1f correlation
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
from core import d1_liq as d1            # noqa: E402
from core import forced_flow as ff       # noqa: E402
from core import p1_rest as p1           # noqa: E402
from core import sweep_stats as ss       # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402
from research.studies import d3d4_core as dc        # noqa: E402

AUDIT_BUDGET_S = 1500


def shard_of(sym, n):
    return int(hashlib.sha1(sym.encode()).hexdigest(), 16) % n


def do_symbol(sym):
    s = d1.Series()
    failed = missing = 0
    for ym in bv.months(d1.T0, d1.T_LAST):
        rows = bv.fetch("futures/um", "monthly", "klines", sym, ym, "1m", bv.parse_kline)
        if rows is None:
            failed += 1
        elif not rows:
            missing += 1
        else:
            s.add_rows(rows)
    rows, counts = p1.symbol_rows(s, sym)
    cand = []
    for r in rows:
        g = dict(zip(p1.FIELDS, r))
        if g["hold"] == 5:
            ok, h = p1.audit_pick(sym, g["i"], g["d"], g["side"])
            if ok:
                ref = s.c[g["i"] - 2]
                cand.append([h, sym, g["i"], g["side"], g["d"], ref * (1 - g["d"]) if g["side"] > 0 else ref * (1 + g["d"])])
    return sym, rows, {"failed_months": failed, "missing_months": missing, "fills": counts}, cand


def audit(cands):
    """aggTrades audit: for the lowest-hash candidates, the notional printed through the limit in the fill minute."""
    t0 = time.time()
    uniq = {}
    for c in sorted(cands):
        uniq.setdefault((c[1], c[2], c[4], c[3]), c)
    out = []
    for c in list(uniq.values())[:p1.AUDIT_CAP]:
        _, sym, i, side, d, limit = c
        ts0 = d1.T0 + i * 60
        g = time.gmtime(ts0)
        base = {"sym": sym, "i": i, "d": d, "side": side}
        if time.time() - t0 > AUDIT_BUDGET_S:
            out.append(dict(base, status="budget"))
            continue
        it = bv.iter_file("futures/um", "daily", "aggTrades", sym, (g.tm_year, g.tm_mon, g.tm_mday), None, bv.parse_aggtrade)
        if it is None:
            out.append(dict(base, status="failed"))
            continue
        if it == []:
            out.append(dict(base, status="missing"))
            continue
        got = []
        for r in it:
            if r[0] >= ts0 + 60:
                break
            if r[0] >= ts0:
                got.append(r)
        notional = p1.through_notional(got, ts0, limit, side)
        out.append(dict(base, status="ok", notional=round(notional, 2), supported=p1.audit_supported(notional)))
    return out


def shard(out_dir, i, n):
    t0 = time.time()
    syms = [x for x in bv.list_symbols("futures/um", "USDT", "klines", "monthly") if d1.is_small(x) and shard_of(x, n) == i]
    meta, cands, files = {}, [], {}
    cl = p1.cells()
    for k in range(len(cl)):
        files[k] = gzip.open(os.path.join(out_dir, f"rows_{i:02d}_{k:02d}.jsonl.gz"), "wt", encoding="utf-8")
    index = {(c[1], c[2], c[3]): k for k, c in enumerate(cl)}
    nrows = 0
    with ThreadPoolExecutor(3) as ex:
        for sym, rows, m, cand in ex.map(do_symbol, syms):
            for r in rows:
                files[index[(r[3], r[4], r[2])]].write(json.dumps(r, separators=(",", ":")) + "\n")
            nrows += len(rows)
            meta[sym] = m
            cands += cand
    for f in files.values():
        f.close()
    aud = audit_safe(cands)
    with open(os.path.join(out_dir, f"meta_{i:02d}.json"), "w") as f:
        json.dump({"shard": i, "of": n, "symbols": len(syms), "rows": nrows, "seconds": round(time.time() - t0), "per_symbol": meta,
                   "audit_candidates": len(cands), "audit": aud}, f)
    print("shard", i, "symbols", len(syms), "rows", nrows, "failed_months", sum(m["failed_months"] for m in meta.values()),
          "audited", len(aud), "seconds", round(time.time() - t0), flush=True)


def audit_safe(cands):
    try:
        return audit(cands)
    except Exception as e:  # noqa: BLE001  (an audit crash is reported, never read as "supported")
        return [{"status": "crashed", "error": repr(e)[:200]}]


# ---------------------------------------------------------------- aggregate
def cstats(tr, a, b):
    months = (b - a) / 86400 / 30.4375
    return d1.stats([t["net"] for t in ss.in_split(tr, a, b)], months)


def read_cell(shards_dir, k):
    out = []
    for p in sorted(glob.glob(os.path.join(shards_dir, "**", f"rows_*_{k:02d}.jsonl.gz"), recursive=True)):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            out += [p1.fill_trade(json.loads(line)) for line in f]
    return out


def mean_key(trades, key):
    return ss.mean([t[key] for t in trades if key in t])


def audit_summary(metas):
    items = [a for m in metas for a in m.get("audit", [])]
    ok = [a for a in items if a.get("status") == "ok"]
    unsup = [a for a in ok if not a["supported"]]
    by_d = {}
    for a in ok:
        v = by_d.setdefault(round(a["d"] * 100), [0, 0])
        v[0] += 1
        v[1] += 0 if a["supported"] else 1
    share = len(unsup) / len(ok) if ok else None
    return {"sampled": len(items), "ok": len(ok), "unsupported": len(unsup), "unsupported_share": share,
            "failed_or_budget": sum(1 for a in items if a.get("status") in ("failed", "budget", "crashed", "missing")),
            "by_d_ok_unsupported": by_d, "kill": share is not None and share > p1.AUDIT_UNSUPPORTED_MAX,
            "unusable": not ok}


def aggregate(out_dir, shards_dir, ff_rows):
    metas = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(shards_dir, "**", "meta_*.json"), recursive=True))]
    aud = audit_summary(metas)
    l1f = dc.l1f_exit_trades([json.loads(line) for line in gzip.open(ff_rows, "rt", encoding="utf-8")])
    a0, b0 = d1.START, d1.END
    l1f_day = dc.exit_series(l1f, a0, b0)
    t0, t1 = p1.BOUNDS["train"]
    train_days = (t1 - t0) / 86400
    summ = {"run_utc": p1.now_utc(), "months": round(d1.MONTHS, 2), "shards": len(metas), "symbols": sum(m["symbols"] for m in metas),
            "rows": sum(m["rows"] for m in metas), "failed_months": sum(v["failed_months"] for m in metas for v in m["per_symbol"].values()),
            "audit": aud, "cells": {}, "l1f_trades": len(l1f)}
    fill_counts = {}
    for m in metas:
        for v in m["per_symbol"].values():
            for k, n in v["fills"].items():
                fill_counts[k] = fill_counts.get(k, 0) + n
    summ["raw_fills_by_d_side"] = fill_counts
    gate_rows = []
    for k, (cid, d, hold, side) in enumerate(p1.cells()):
        fills = read_cell(shards_dir, k)
        cl = p1.clusters(fills)
        tr_fills = ss.in_split(fills, t0, t1)
        tr_cl = ss.in_split(cl, t0, t1)
        ok, info = ss.gate(tr_cl, {"size": p1.SIZE}, p1.CFG, train_days)
        cm = mean_key(tr_cl, "ctrl_net")
        gap = p1.late_taker_gap(tr_fills)
        top = p1.top_share([f["net"] for f in tr_fills])
        info = dict(info, id=cid, control_mean_train=cm, late_taker_gap_train=gap, top1pct_share_train=top)
        if ok and cm is not None and info["train_mean"] <= cm:
            ok, info["reason"] = False, "train net mean not above the random-control mean"
        if ok and (gap is None or gap < p1.GAP_MIN):
            ok, info["reason"] = False, f"late-taker gap {gap} < {p1.GAP_MIN}"
        if ok and (top is None or top > p1.TOP_SHARE_MAX):
            ok, info["reason"] = False, f"best 1% of fills made {top} of train profit"
        if ok and aud["kill"]:
            ok, info["reason"] = False, "aggTrades audit kill: unsupported share above 20%"
        if ok and aud["unusable"]:
            ok, info["reason"] = False, "aggTrades audit produced no usable fill (failed or crashed)"
        cx = {}
        for sp, (a, b) in p1.BOUNDS.items():
            sf, sc = ss.in_split(fills, a, b), ss.in_split(cl, a, b)
            cx[sp] = {"clusters": cstats(cl, a, b), "fills_n": len(sf), "fills_mean": ss.mean([f["net"] for f in sf]),
                      "gross": ss.mean([f["gross"] for f in sf]), "placebo": ss.mean([-f["gross"] - f["cost"] + f["fund"] for f in sf]),
                      "ctrl_cluster": mean_key(sc, "ctrl_net"), "taker_cluster": mean_key(sc, "taker_net"),
                      "mean_at_taker_cost": ss.mean([f["gross"] - p1.COST_TAKER - f["fund"] for f in sf]),
                      "stop_share": round(sum(1 for f in sf if f["reason"] == "stop") / max(1, len(sf)), 4)}
        corr = ff.corr(dc.exit_series(cl, a0, b0), l1f_day)
        summ["cells"][cid] = {"gate": info, "ok": ok, "by_split": cx, "corr_l1f_exit_day": corr, "all_clusters": cstats(cl, a0, b0)}
        if ok:
            r = {"id": cid, "gate": info, "status": "ok", **ss.evaluate(cl, {"size": p1.SIZE}, p1.BOUNDS)}
            ex = {}
            for sp, short in (("validation", "val"), ("test", "test")):
                c = cx[sp]
                m = (c["clusters"] or {}).get("mean")
                ex[f"{short}_beats_control"] = m is not None and m > (c["ctrl_cluster"] if c["ctrl_cluster"] is not None else 9)
                ex[f"{short}_beats_late_taker"] = m is not None and m > (c["taker_cluster"] if c["taker_cluster"] is not None else 9)
            r["extra_criteria"] = ex
            gate_rows.append(r)
        del fills, cl
    fam = ss.judge_family(gate_rows, p1.CFG) if gate_rows else {"holm_m": 0}
    summ["gate"] = {"rules_tested": len(p1.cells()), "stage0_survivors": len(gate_rows), "holm": fam, "passed": [r["id"] for r in gate_rows if r.get("passed")],
                    "evaluated": [dict(ss.compact(r), criteria=r["criteria"]) for r in gate_rows]}
    closest = min(summ["cells"].items(), key=lambda kv: -(kv[1]["gate"].get("x") or -9))
    summ["closest_by_train_x"] = {"id": closest[0], "gate": closest[1]["gate"]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    print(json.dumps({k: summ[k] for k in ("months", "shards", "symbols", "rows", "failed_months", "audit", "gate", "closest_by_train_x")}, default=str)[:6000], flush=True)
    for cid, v in summ["cells"].items():
        print(cid, "ok", v["ok"], (v["gate"].get("reason")), "train", v["by_split"]["train"]["clusters"], "val", v["by_split"]["validation"]["clusters"],
              "test", v["by_split"]["test"]["clusters"], "corr", v["corr_l1f_exit_day"], flush=True)


def main():
    mode, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "shard":
        shard(out_dir, int(sys.argv[3]), int(sys.argv[4]))
    elif mode == "aggregate":
        aggregate(out_dir, sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("mode must be shard or aggregate")


if __name__ == "__main__":
    main()
