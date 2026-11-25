"""P4 new-perp first-week short (protocol_p1p4_20261126.md). GitHub Actions only (workflow p1p4.yml).

    python research/studies/p4_newperp.py step0 <out_dir> <parts_dir> <ff_rows>
        Step 0: a read of the R2 V1 rows of calendar_flow_1 run 2 (the part files of Actions 45556054691). Kill 0 is locked in the protocol.
"""
import calendar
import glob
import gzip
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import calendar_flow as cf   # noqa: E402
from core import forced_flow as ff     # noqa: E402
from research.studies import d3d4_core as dc   # noqa: E402

MONTH = 30.4375 * 86400
HOLD_S = 168 * 3600
KILL_X = 0.15
CAP_N = 8.6
FIRST_ENTRY_S = 24 * 3600


def find_rows(obj, out):
    """Every dict with kind == newperp_short inside a parsed part file (the nesting is not assumed)."""
    if isinstance(obj, dict):
        if obj.get("kind") == "newperp_short":
            out.append(obj)
            return
        for v in obj.values():
            find_rows(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_rows(v, out)


def load_rows(parts_dir):
    rows = []
    for p in sorted(glob.glob(os.path.join(parts_dir, "**", "*.json"), recursive=True)):
        try:
            find_rows(json.load(open(p)), rows)
        except ValueError:
            continue
    seen, out = set(), []
    for r in rows:
        k = (r.get("symbol"), r.get("ts"))
        if k not in seen and "V1" in (r.get("ret") or {}):
            seen.add(k)
            out.append(r)
    return out


def sd_of(v):
    n = len(v)
    if n < 2:
        return None
    m = sum(v) / n
    return math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))


def stats(nets, months, cap=None):
    n = len(nets)
    if n < 2:
        return {"n": n, "months": round(months, 2)}
    m = sum(nets) / n
    sd = sd_of(nets)
    s = m / sd if sd else 0.0
    N = n / months
    return {"n": n, "months": round(months, 2), "mean": round(m, 5), "sd": round(sd, 5), "s": round(s, 4), "N_per_month": round(N, 3),
            "x": round(N * s * s, 4), "x_capped": round(min(N, cap if cap else N) * s * s, 4), "hit": round(sum(1 for v in nets if v > 0) / n, 3)}


def months_between(a, b):
    return (b - a) / MONTH


def step0(out_dir, parts_dir, ff_rows):
    rows = load_rows(parts_dir)
    bounds = cf.BOUNDS_R2
    res = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": len(rows), "source": "Actions 45556054691 part-calendar_flow_1-*"}
    nets_by = {}
    for sp, (a, b) in bounds.items():
        nets_by[sp] = [r["ret"]["V1"]["net"] for r in rows if a <= r["ts"] < b]
    res["by_split"] = {sp: stats(nets_by[sp], months_between(*bounds[sp]), CAP_N) for sp in bounds}
    a_v, b_t = bounds["validation"][0], bounds["test"][1]
    pooled = [r["ret"]["V1"]["net"] for r in rows if a_v <= r["ts"] < b_t]
    res["pooled_validation_test"] = stats(pooled, months_between(a_v, b_t), CAP_N)
    by_year = {}
    for r in rows:
        by_year.setdefault(time.gmtime(r["ts"]).tm_year, []).append(r["ret"]["V1"]["net"])
    res["by_year"] = {str(y): stats(v, 12.0, CAP_N) for y, v in sorted(by_year.items())}
    monthly = {}
    for r in rows:
        g = time.gmtime(r["ts"])
        monthly[f"{g.tm_year}-{g.tm_mon:02d}"] = monthly.get(f"{g.tm_year}-{g.tm_mon:02d}", 0) + 1
    res["monthly_counts"] = dict(sorted(monthly.items()))
    y26 = by_year.get(2026, [])
    res["mean_2026"] = (sum(y26) / len(y26)) if y26 else None
    res["n_2026"] = len(y26)
    res["mean_2025"] = (sum(by_year[2025]) / len(by_year[2025])) if by_year.get(2025) else None
    x_pool = (res["pooled_validation_test"] or {}).get("x")
    kill_x = x_pool is None or x_pool < KILL_X
    kill_26 = res["mean_2026"] is None or res["mean_2026"] <= 0
    res["kill0"] = {"fired": bool(kill_x or kill_26), "pooled_x_below_0.15": bool(kill_x), "mean_2026_not_positive": bool(kill_26),
                    "pooled_x": x_pool, "mean_2026": res["mean_2026"]}
    a0, b0 = cf.utc(2024), cf.utc(2026, 10, 29)
    trades = [{"x": r["ts"] + HOLD_S, "net": r["ret"]["V1"]["net"]} for r in rows]
    l1f = dc.l1f_exit_trades([json.loads(line) for line in gzip.open(ff_rows, "rt", encoding="utf-8")])
    res["corr_l1f_exit_day_2024_2026"] = ff.corr(dc.exit_series(trades, a0, b0), dc.exit_series(l1f, a0, b0))
    res["corr_l1f_exit_week_2024_2026"] = ff.corr(dc.exit_series(trades, a0, b0, True), dc.exit_series(l1f, a0, b0, True))
    res["l1f_trades"] = len(l1f)
    with open(os.path.join(out_dir, "step0.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1)[:6000], flush=True)


def main():
    mode, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "step0":
        step0(out_dir, sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("mode must be step0")


if __name__ == "__main__":
    main()
