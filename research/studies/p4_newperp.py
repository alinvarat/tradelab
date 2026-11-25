"""P4 new-perp first-week short (protocol_p1p4_20261126.md). GitHub Actions only (workflow p1p4.yml).

    python research/studies/p4_newperp.py step0 <out_dir> <parts_dir> <ff_rows>
        Step 0: a read of the R2 V1 rows of calendar_flow_1 run 2 (the part files of Actions 45556054691). Kill 0 is locked in the protocol.
    python research/studies/p4_newperp.py step2 <out_dir> <step1.json> <ff_rows>
        Step 2: rule V1 on the step 1 clusters, first venue (protocol addendum 2026-11-26). Kill 2, criteria, controls, L1f correlation.
    python research/studies/p4_newperp.py step1 <out_dir>
        Step 1 (counts only, no returns): listing time of every USDT perp on the non-Binance venues, eligible clusters. Kill 1 (< 60) is locked.
"""
import glob
import gzip
import json
import math
import os
import random
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
                out[base_name(r["instId"].split("-")[0])] = (t / 1000, r["instId"])
    return st, out


def venue_gate():
    st, d = lv.jget("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    out = {}
    for r in (d if isinstance(d, list) else []):
        t = _num(r.get("create_time"))
        if t and str(r.get("name", "")).endswith("_USDT"):
            out[base_name(r["name"][:-5])] = (t, r["name"])
    return st, out


def venue_mexc():
    st, d = lv.jget("https://contract.mexc.com/api/v1/contract/detail")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("createTime"))
        if t and r.get("quoteCoin") == "USDT":
            out[base_name(r.get("baseCoin") or r["symbol"].split("_")[0])] = (t / 1000, r["symbol"])
    return st, out


def venue_bitget():
    st, d = lv.jget("https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("launchTime"))
        if t:
            out[base_name(r.get("baseCoin") or r["symbol"][:-4])] = (t / 1000, r["symbol"])
    return st, out


def venue_kucoin():
    st, d = lv.jget("https://api-futures.kucoin.com/api/v1/contracts/active")
    out = {}
    for r in ((d or {}).get("data") or []) if isinstance(d, dict) else []:
        t = _num(r.get("firstOpenDate"))
        if t and r.get("quoteCurrency") == "USDT" and not r.get("isInverse"):
            b = r.get("baseCurrency", "")
            out[base_name("BTC" if b == "XBT" else b)] = (t / 1000, r["symbol"])
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
                out[base_name(nm)] = (t, nm)
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
        for b, (t, _nat) in got.items():
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


# ---------------------------------------------------------------- step 2: rule V1 on the first venue (addendum 2026-11-26)
from core import sweep_stats as ss    # noqa: E402

H = 3600
ENTRY_OFF, HOLD_BARS = 24 * H, 144
COST2 = 2 * cf.LEG_COST
SIZE2 = {"lev": 1, "k": 2}
CFG2 = {"alpha": 0.05, "account_usd": 147.0,
        "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
        "pass": {"min_val_trades": 30, "min_test_trades": 20}}
AGE_MIN_S = 180 * 86400
NATIVE_SEC = {}


def _row_bar(t, o, h, l, c):     # noqa: E741
    return (int(t), float(o), float(h), float(l), float(c))


def b1h_okx(nat, t0, t1):
    out, after = {}, int(t1 * 1000)
    for _ in range(6):
        time.sleep(0.12)
        st, d = lv.jget(f"https://www.okx.com/api/v5/market/history-candles?instId={nat}&bar=1H&after={after}&limit=100")
        if d is None:
            return None
        if d.get("code") != "0":
            return {}
        rows = d.get("data") or []
        if not rows:
            break
        for k in rows:
            out[int(k[0]) // 1000] = _row_bar(int(k[0]) // 1000, k[1], k[2], k[3], k[4])
        oldest = min(int(k[0]) for k in rows)
        if oldest / 1000 <= t0:
            break
        after = oldest
    return out


def b1h_gate(nat, t0, t1):
    time.sleep(0.1)
    st, d = lv.jget(f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={nat}&interval=1h&from={int(t0)}&to={int(t1)}")
    if d is None:
        return {} if st in (400, 404) else None
    return {int(k["t"]): _row_bar(k["t"], k["o"], k["h"], k["l"], k["c"]) for k in d} if isinstance(d, list) else {}


def b1h_mexc(nat, t0, t1):
    time.sleep(0.1)
    st, d = lv.jget(f"https://contract.mexc.com/api/v1/contract/kline/{nat}?interval=Min60&start={int(t0)}&end={int(t1)}")
    if d is None:
        return {} if st in (400, 404) else None
    x = d.get("data") if isinstance(d, dict) else None
    if not x or not x.get("time"):
        return {}
    return {int(t): _row_bar(t, o, h, l, c) for t, o, h, l, c in zip(x["time"], x["open"], x["high"], x["low"], x["close"])}


def b1h_kucoin(nat, t0, t1):
    time.sleep(0.1)
    st, d = lv.jget(f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={nat}&granularity=60&from={int(t0 * 1000)}&to={int(t1 * 1000)}")
    if d is None:
        return {} if st in (400, 404) else None
    if d.get("code") != "200000":
        return {}
    return {int(k[0]) // 1000: _row_bar(int(k[0]) // 1000, k[1], k[2], k[3], k[4]) for k in d.get("data") or []}


def b1h_hl(nat, t0, t1):
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": nat, "interval": "1h", "startTime": int(t0 * 1000), "endTime": int(t1 * 1000)}})
    st, d = lv.jget("https://api.hyperliquid.xyz/info", data=body.encode(), method="POST")
    if d is None:
        return {} if st in (400, 404, 422, 500) else None
    return {int(k["t"]) // 1000: _row_bar(int(k["t"]) // 1000, k["o"], k["h"], k["l"], k["c"]) for k in d} if isinstance(d, list) else {}


B1H = {"okx": b1h_okx, "gate": b1h_gate, "mexc": b1h_mexc, "kucoin_fut": b1h_kucoin, "hyperliquid": b1h_hl}


def bars_1h(venue, nat, t0, t1):
    """{bar open s: (t, o, h, l, c)} (hour-aligned bars inside [t0, t1)) | {} none | None failed."""
    got = B1H[venue](nat, t0, t1)
    if got is None:
        return None
    return {t: b for t, b in got.items() if t % H == 0 and t0 <= t < t1}


def btc_hourly():
    out = {}
    for ym in bv.months(cf.utc(2022, 12), cf.utc(2026, 11)):
        rows = bv.fetch("futures/um", "monthly", "klines", "BTCUSDT", ym, "1h", bv.parse_kline)
        if rows is None:
            raise RuntimeError(f"BTCUSDT 1h {ym} failed")
        for r in rows:
            out[r[0]] = (r[0], r[1], r[2], r[3], r[4])
    return out


def v1_trade(bars, btc, entry_t, side=-1, stop=cf.NEWPERP_STOP):
    """Rule V1 (or its mirror, side +1) on one venue's 1h bars: (trade dict | None, why-not). Hedge leg from Binance BTCUSDT, funding 0."""
    seq = cf.contiguous(bars, entry_t, H, HOLD_BARS)
    if not seq:
        return None, "no_bar_at_entry"
    entry = seq[0][1]
    px, k, why = cf.walk(seq, side, entry * (1 + stop) if side < 0 else entry * (1 - stop))
    if why == "time" and len(seq) < HOLD_BARS:
        why = "gap"
    b0, b1 = btc.get(seq[0][0]), btc.get(seq[k][0])
    if b0 is None or b1 is None:
        return None, "no_btc_bar"
    t = cf.make_trade(side, entry, px, COST2, 0.0, (b0[1], b1[4]), why)
    lo = min(b[3] for b in seq[:k + 1])
    hi = max(b[2] for b in seq[:k + 1])
    t["mfe"] = max((entry - lo) / entry if side < 0 else (hi - entry) / entry, 0.0)
    t["mae"] = max((hi - entry) / entry if side < 0 else (entry - lo) / entry, 0.0)
    t["xt"] = seq[k][0] + H
    return t, None


def one_cluster(c, btc, pools):
    venue, base = c["first_venue"], c["base"]
    nat = NATIVE_SEC.get(venue, {}).get(base)
    out = {"base": base, "venue": venue, "t": c["first_ts"], "status": None}
    if not nat:
        out["status"] = "no_native_symbol"
        return out
    bars = bars_1h(venue, nat, c["first_ts"] - H, c["first_ts"] + 8 * 86400 + H)
    if bars is None:
        out["status"] = "download_failed"
        return out
    if not bars:
        out["status"] = "no_bars"
        return out
    t0 = min(bars)
    entry_t = t0 + ENTRY_OFF
    real, why = v1_trade(bars, btc, entry_t, -1)
    if real is None:
        out["status"] = why
        return out
    mirror, _ = v1_trade(bars, btc, entry_t, 1)
    out.update(status="ok", t0=t0, entry_t=entry_t, real=real, mirror=mirror)
    rng = random.Random(f"20261126:{base}")
    cands = [b for b, (tl, _n) in pools.get(venue, {}).items() if tl <= t0 - AGE_MIN_S and b != base]
    rng.shuffle(cands)
    for b in cands[:3]:
        n2 = NATIVE_SEC[venue][b]
        bb = bars_1h(venue, n2, entry_t - H, entry_t + 7 * 86400 + 2 * H)
        if not bb:
            continue
        ct, _ = v1_trade(bb, btc, entry_t, -1)
        if ct:
            out["ctrl"] = {"base": b, "net": ct["net"]}
            break
    return out


def to_trade(o):
    r = o["real"]
    t = {"sym": o["base"], "side": -1, "t": o["t"], "te": o["entry_t"], "x": r["xt"], "gross": r["gross"], "cost": r["cost"], "fund": 0.0, "net": r["net"],
         "mfe": r["mfe"], "mae": r["mae"], "reason": r["reason"], "venue": o["venue"]}
    if o.get("mirror"):
        t["plac_net"] = o["mirror"]["net"]
    if o.get("ctrl"):
        t["ctrl_net"] = o["ctrl"]["net"]
    return t


def step2(out_dir, step1_path, ff_rows):
    c1 = json.load(open(step1_path))["clusters"]
    pools = {}
    for name, fn in VENUE_FNS:
        if name == "bitget":
            continue
        _, got = fn()
        pools[name] = got
        NATIVE_SEC[name] = {b: nat for b, (_t, nat) in got.items()}
    btc = btc_hourly()
    t_start = time.time()
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda c: one_cluster(c, btc, pools), c1))
    status = {}
    for o in res:
        status[o["status"]] = status.get(o["status"], 0) + 1
    trades = [to_trade(o) for o in res if o["status"] == "ok"]
    summ = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "clusters_in": len(c1), "status": status, "trades": len(trades),
            "seconds": round(time.time() - t_start), "bounds": {k: [a, b] for k, (a, b) in STEP2_BOUNDS.items()}}
    by_split = {}
    for sp, (a, b) in STEP2_BOUNDS.items():
        tr = ss.in_split(trades, a, b)
        nets = [t["net"] for t in tr]
        m = months_between(a, b)
        d = stats(nets, m, CAP_N)
        d.update(placebo_mirror=ss.mean([t["plac_net"] for t in tr if "plac_net" in t]), random_age=ss.mean([t["ctrl_net"] for t in tr if "ctrl_net" in t]),
                 n_ctrl=sum(1 for t in tr if "ctrl_net" in t), mean_2x=ss.mean([t["net"] - t["cost"] for t in tr]),
                 mean_gate_placebo=ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in tr]))
        by_split[sp] = d
    summ["by_split"] = by_split
    summ["by_venue"] = {v: {"n": sum(1 for t in trades if t["venue"] == v), "mean": ss.mean([t["net"] for t in trades if t["venue"] == v])}
                        for v in sorted({t["venue"] for t in trades})}
    a, b = STEP2_BOUNDS["train"]
    tr = ss.in_split(trades, a, b)
    ok, info = ss.gate(tr, {"size": SIZE2}, CFG2, (b - a) / 86400)
    tm = by_split["train"]
    k2 = {"train_mean_not_positive": not (tm.get("mean") or 0) > 0,
          "train_not_above_placebo": (tm.get("mean") or 0) <= (tm.get("placebo_mirror") if tm.get("placebo_mirror") is not None else -9),
          "train_not_above_random_age": (tm.get("mean") or 0) <= (tm.get("random_age") if tm.get("random_age") is not None else -9),
          "train_x_capped_below_0.2": (tm.get("x_capped") or 0) < 0.2}
    summ["kill2"] = {"fired": any(k2.values()), **k2}
    summ["gate"] = {"ok": ok, **info}
    ev = {"id": "v1", "status": "ok", "gate": info, **ss.evaluate(trades, {"size": SIZE2}, STEP2_BOUNDS)}
    ex2 = {}
    for sp, short in (("validation", "val"), ("test", "test")):
        d = by_split[sp]
        ex2[f"{short}_beats_placebo"] = (d.get("mean") or 0) > (d["placebo_mirror"] if d.get("placebo_mirror") is not None else 9)
        ex2[f"{short}_beats_random_age"] = (d.get("mean") or 0) > (d["random_age"] if d.get("random_age") is not None else 9)
    ev["extra_criteria"] = ex2
    fam = ss.judge_family([ev], CFG2)
    summ["criteria"] = {"holm": fam, "p_validation": ev["validation"]["p"], "p_adj": ev["p_adj"], "criteria": ev["criteria"], "passed": ev["passed"],
                        "folds": ev["folds"], "descriptive_if_gate_failed": not ok}
    a0, b0 = cf.utc(2024), cf.utc(2026, 10, 29)
    l1f = dc.l1f_exit_trades([json.loads(line) for line in gzip.open(ff_rows, "rt", encoding="utf-8")])
    summ["corr_l1f_exit_day"] = ff.corr(dc.exit_series(trades, a0, b0), dc.exit_series(l1f, a0, b0))
    summ["corr_l1f_exit_week"] = ff.corr(dc.exit_series(trades, a0, b0, True), dc.exit_series(l1f, a0, b0, True))
    summ["passed"] = bool(ok and not summ["kill2"]["fired"] and ev["passed"])
    with open(os.path.join(out_dir, "step2.json"), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    with open(os.path.join(out_dir, "step2_rows.json"), "w") as f:
        json.dump([{k: v for k, v in o.items() if k not in ("real", "mirror")} | ({"net": o["real"]["net"], "reason": o["real"]["reason"]} if o["status"] == "ok" else {})
                   for o in res], f)
    print(json.dumps(summ, indent=1, default=str)[:7000], flush=True)


def main():
    mode, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "step0":
        step0(out_dir, sys.argv[3], sys.argv[4])
    elif mode == "step1":
        step1(out_dir)
    elif mode == "step2":
        step2(out_dir, sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("mode must be step0, step1 or step2")


if __name__ == "__main__":
    main()
