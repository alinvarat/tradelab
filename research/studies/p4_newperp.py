"""P4 new-perp first-week short (protocol_p1p4_20261126.md). GitHub Actions only (workflow p1p4.yml).

    python research/studies/p4_newperp.py step0 <out_dir> <parts_dir> <ff_rows>
        Step 0: a read of the R2 V1 rows of calendar_flow_1 run 2 (the part files of Actions 45556054691). Kill 0 is locked in the protocol.
    python research/studies/p4_newperp.py step1 <out_dir>
        Step 1 (counts only, no returns): listing time of every USDT perp on the non-Binance venues, eligible clusters. Kill 1 (< 60) is locked.
"""
import glob
import gzip
import json
import math
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from concurrent.futures import ThreadPoolExecutor   # noqa: E402

from core import calendar_flow as cf   # noqa: E402
from core import d1_liq as d1          # noqa: E402
from core import forced_flow as ff     # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402
from research.studies import d3d4_core as dc   # noqa: E402
from research.studies import l1f_venues as lv   # noqa: E402

MONTH = 30.4375 * 86400
HOLD_S = 168 * 3600
KILL_X = 0.15
CAP_N = 8.6
STEP2_BOUNDS = {"train": (cf.utc(2023), cf.utc(2024, 9)), "validation": (cf.utc(2024, 9), cf.utc(2025, 9)), "test": (cf.utc(2025, 9), cf.utc(2026, 10, 29))}
WINDOW = (cf.utc(2023), cf.utc(2026, 10, 29))
SAME_WEEK = 7 * 86400
KILL1_MIN = 60
STABLE_BASES = {"USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "USDE", "USDT", "EUR", "AEUR", "XAUT", "PAXG"}


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


# ---------------------------------------------------------------- step 1: listing times on the non-Binance venues (counts only, no prices)
def base_name(x):
    x = x.upper() if not (x[:1] == "k" and x[1:].isupper()) else x[1:]
    return re.sub(r"^(1000000|10000|1000)(?=[A-Z])", "", x)


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def venue_okx():
    st, d = lv.jget("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
    out = {}
    for r in ((d or {}).get("data") or []):
        if r.get("settleCcy") == "USDT" and r.get("instId", "").endswith("-USDT-SWAP"):
            t = _num(r.get("listTime"))
            if t:
                out[base_name(r["instId"].split("-")[0])] = t / 1000
    return st, out


def venue_gate():
    st, d = lv.jget("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    out = {}
    for r in (d if isinstance(d, list) else []):
        t = _num(r.get("create_time"))
        if t and str(r.get("name", "")).endswith("_USDT"):
            out[base_name(r["name"][:-5])] = t
    return st, out


def venue_mexc():
    st, d = lv.jget("https://contract.mexc.com/api/v1/contract/detail")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("createTime"))
        if t and r.get("quoteCoin") == "USDT":
            out[base_name(r.get("baseCoin") or r["symbol"].split("_")[0])] = t / 1000
    return st, out


def venue_bitget():
    st, d = lv.jget("https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("launchTime"))
        if t:
            out[base_name(r.get("baseCoin") or r["symbol"][:-4])] = t / 1000
    return st, out


def venue_kucoin():
    st, d = lv.jget("https://api-futures.kucoin.com/api/v1/contracts/active")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("firstOpenDate"))
        if t and r.get("quoteCurrency") == "USDT" and not r.get("isInverse"):
            b = r.get("baseCurrency", "")
            out[base_name("BTC" if b == "XBT" else b)] = t / 1000
    return st, out


def venue_hyperliquid():
    import json as _j
    st, d = lv.jget("https://api.hyperliquid.xyz/info", data=_j.dumps({"type": "meta"}).encode(), method="POST")
    names = [u["name"] for u in ((d or {}).get("universe") or []) if not u.get("isDelisted")]
    out = {}

    def one(nm):
        body = _j.dumps({"type": "candleSnapshot", "req": {"coin": nm, "interval": "1d", "startTime": 0, "endTime": int(time.time() * 1000)}})
        _, c = lv.jget("https://api.hyperliquid.xyz/info", data=body.encode(), method="POST")
        return nm, (min(int(k["t"]) for k in c) / 1000 if isinstance(c, list) and c else None)
    with ThreadPoolExecutor(4) as ex:
        for nm, t in ex.map(one, names):
            if t:
                out[base_name(nm)] = t
    return st, out


VENUE_FNS = (("okx", venue_okx), ("gate", venue_gate), ("mexc", venue_mexc), ("bitget", venue_bitget), ("kucoin_fut", venue_kucoin),
             ("hyperliquid", venue_hyperliquid))


def binance_first(sym_list):
    """First 1h bar of the earliest monthly file for the first symbol of `sym_list` that exists on Binance USDT-M. None = never listed; False = listing check failed."""
    for sym in sym_list:
        try:
            files = bv.list_files("futures/um", "monthly", "klines", sym, "1h")
        except RuntimeError:
            return False
        if files:
            rows = bv.fetch("futures/um", "monthly", "klines", sym, files[0], "1h", bv.parse_kline)
            if rows is None:
                return False
            if rows:
                return float(rows[0][0])
    return None


def step1(out_dir):
    venues, status = {}, {}
    for name, fn in VENUE_FNS:
        try:
            st, got = fn()
        except Exception as e:  # noqa: BLE001
            st, got = repr(e)[:100], {}
        venues[name], status[name] = got, {"http": st, "contracts_with_listing_time": len(got)}
    first = {}
    for name, got in venues.items():
        for b, t in got.items():
            if b in STABLE_BASES:
                continue
            if b not in first or t < first[b][0]:
                first[b] = (t, name)
    cand = {b: v for b, v in first.items() if WINDOW[0] <= v[0] < WINDOW[1]}
    bsyms = set(bv.list_symbols("futures/um", "USDT"))

    def binance(b):
        names = [s for s in (b + "USDT", "1000" + b + "USDT", "10000" + b + "USDT", "1000000" + b + "USDT") if s in bsyms]
        return b, (binance_first(names) if names else None)
    with ThreadPoolExecutor(4) as ex:
        bin_t = dict(ex.map(binance, sorted(cand)))
    clusters, dropped = [], {"binance_first_or_same_week": 0, "binance_check_failed": 0}
    for b, (t, v) in sorted(cand.items()):
        bt = bin_t[b]
        if bt is False:
            dropped["binance_check_failed"] += 1
        elif bt is not None and bt <= t + SAME_WEEK:
            dropped["binance_first_or_same_week"] += 1
        else:
            clusters.append({"base": b, "first_venue": v, "first_ts": t, "binance_ts": bt})
    by_venue, by_split, by_month = {}, {}, {}
    for c in clusters:
        by_venue[c["first_venue"]] = by_venue.get(c["first_venue"], 0) + 1
        g = time.gmtime(c["first_ts"])
        k = f"{g.tm_year}-{g.tm_mon:02d}"
        by_month[k] = by_month.get(k, 0) + 1
    for sp, (a, b2) in STEP2_BOUNDS.items():
        by_split[sp] = sum(1 for c in clusters if a <= c["first_ts"] < b2)
    res = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "venues": status, "bases_listed_in_window": len(cand),
           "binance_symbols": len(bsyms), "dropped": dropped, "eligible_clusters": len(clusters), "kill1_fired": len(clusters) < KILL1_MIN,
           "by_first_venue": by_venue, "by_split": by_split, "by_month": dict(sorted(by_month.items())), "clusters": clusters}
    with open(os.path.join(out_dir, "step1.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "clusters"}, indent=1), flush=True)


def main():
    mode, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "step0":
        step0(out_dir, sys.argv[3], sys.argv[4])
    elif mode == "step1":
        step1(out_dir)
    else:
        raise SystemExit("mode must be step0 or step1")


if __name__ == "__main__":
    main()
