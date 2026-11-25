"""Data loaders for sweeps (network; runs on GitHub Actions only). One call per data group = (source, market, tf, symbols):
bars are fetched once, cached under .sweepcache/ (restored by the workflow's Actions cache) and returned as the bar dicts
core.sweep_engine expects. A symbol with a failed download or too many missing bars is dropped and reported, never filled."""
import gzip
import hashlib
import json
import os
import sys
import time

from core import sweep_config as sc

CACHE_DIR = os.environ.get("SWEEP_CACHE", os.path.join(sc.ROOT, ".sweepcache"))
HOUR = 3600
MAX_MISSING = 0.03


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _cached(key, producer, cache_dir=None):
    """producer() -> (value, ok). The value is cached only when ok."""
    cache_dir = cache_dir or CACHE_DIR
    path = os.path.join(cache_dir, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json.gz")
    try:
        with gzip.open(path, "rt") as f:
            return json.load(f)
    except (OSError, ValueError):
        pass
    val, ok = producer()
    if ok:
        try:
            os.makedirs(cache_dir, exist_ok=True)
            with gzip.open(path, "wt") as f:
                json.dump(val, f)
        except OSError:
            pass
    return val


def to_grid(rows, fund, prem, start_s, end_s):
    """rows [(ts, o, h, l, c, v, tb)] hourly -> (bars dict on a regular hourly grid, missing hours). A missing hour is flat
    at the previous close with zero volume. fund [(ts, rate)] is summed into the hour bucket; prem [(ts, close)]."""
    by = {int(r[0]): r for r in rows if start_s <= r[0] < end_s}
    if not by:
        return None, 0
    t0, t1 = min(by), max(by)
    d = {k: [] for k in ("ts", "o", "h", "l", "c", "v", "tb")}
    miss = 0
    for t in range(t0, t1 + 1, HOUR):
        r = by.get(t)
        if r is None:
            p = d["c"][-1]
            vals = (p, p, p, p, 0.0, 0.0)
            miss += 1
        else:
            vals = r[1:7]
        d["ts"].append(t)
        for k, v in zip(("o", "h", "l", "c", "v", "tb"), vals):
            d[k].append(v)
    fm = {}
    for t, r in fund or []:
        k = int(t) // HOUR * HOUR
        fm[k] = fm.get(k, 0.0) + r
    d["fund"] = [fm.get(t, 0.0) for t in d["ts"]]
    if prem is None:
        d["prem"] = None
    else:
        pm = {int(t): v for t, v in prem}
        d["prem"] = [pm.get(t, float("nan")) for t in d["ts"]]
    return d, miss


def resample(d, k):
    """k-hour bars aligned to UTC multiples of k hours; only complete blocks."""
    if k == 1:
        return d
    out = {key: [] for key in d if d[key] is not None}
    ts = d["ts"]
    n, i = len(ts), 0
    while i + k <= n:
        if (ts[i] // HOUR) % k == 0 and ts[i + k - 1] == ts[i] + (k - 1) * HOUR:
            j = i + k
            out["ts"].append(ts[i])
            out["o"].append(d["o"][i])
            out["h"].append(max(d["h"][i:j]))
            out["l"].append(min(d["l"][i:j]))
            out["c"].append(d["c"][j - 1])
            out["v"].append(sum(d["v"][i:j]))
            out["tb"].append(sum(d["tb"][i:j]))
            out["fund"].append(sum(d["fund"][i:j]))
            if d.get("prem") is not None:
                out["prem"].append(d["prem"][j - 1])
            i = j
        else:
            i += 1
    if d.get("prem") is None:
        out["prem"] = None
    return out


def load_binance(spec, workers=8):
    """({sym: bars}, {sym: reason dropped}) for a binance_vision group."""
    from concurrent.futures import ThreadPoolExecutor
    from research.studies import binance_vision as bv
    market = spec.get("market", "futures/um")
    start_s, end_s = sc.day(spec["start"]), sc.day(spec["end"])
    extras = spec.get("extras", [])

    def one(sym):
        kkey = f"bv|{market}|{sym}|1h|{start_s}|{end_s}"

        def prod_k():
            rows, failed = bv.klines(sym, start_s, end_s, "1h", market=market)
            return {"rows": [[r[0], r[1], r[2], r[3], r[4], r[5], r[9]] for r in rows], "failed": failed}, not failed
        k = _cached(kkey, prod_k)
        fund = prem = None
        failed = list(k["failed"])
        if "funding" in extras:
            def prod_f():
                rows, fl = bv.funding(sym, start_s, end_s)
                return {"rows": [list(r) for r in rows], "failed": fl}, not fl
            f = _cached(f"bvf|{sym}|{start_s}|{end_s}", prod_f)
            fund, failed = f["rows"], failed + f["failed"]
        if "premium" in extras:
            def prod_p():
                rows, fl = bv.premium_index(sym, start_s, end_s, "1h")
                return {"rows": [[r[0], r[4]] for r in rows], "failed": fl}, not fl
            p = _cached(f"bvp|{sym}|{start_s}|{end_s}", prod_p)
            prem, failed = p["rows"], failed + p["failed"]
        return sym, k["rows"], fund, prem, failed

    with ThreadPoolExecutor(workers) as ex:
        loaded = list(ex.map(one, spec["symbols"]))
    bars, dropped = {}, {}
    for sym, rows, fund, prem, failed in loaded:
        if failed:
            dropped[sym] = f"download failed {failed[:3]}"
            continue
        d, miss = to_grid(rows, fund, prem, start_s, end_s)
        if d is None:
            dropped[sym] = "no bars"
        elif miss / len(d["ts"]) > MAX_MISSING:
            dropped[sym] = f"missing hours {miss}/{len(d['ts'])}"
        elif fund is not None and len(fund) < 0.9 * len(d["ts"]) / 8:
            dropped[sym] = f"funding settlements {len(fund)} < 90% of {len(d['ts']) / 8:.0f}"
        else:
            bars[sym] = resample(d, sc.TFS[spec["tf"]])
    return bars, dropped


def _yahoo_daily(sym, start_s, end_s):
    """Raw daily bars [{t,o,h,l,c,v}] for [start_s, end_s) via explicit period1/period2 (range=max returns only about a year)."""
    import urllib.parse
    import urllib.request
    from core import data
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1={int(start_s) - 7 * 86400}"
           f"&period2={int(end_s) + 7 * 86400}&interval=1d&includePrePost=false")
    with urllib.request.urlopen(urllib.request.Request(url, headers=data.UA), timeout=40) as r:
        d = json.loads(r.read())["chart"]
    if d.get("error") or not d.get("result"):
        raise ValueError(f"no data for {sym}: {d.get('error')}")
    res = d["result"][0]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None not in (o, h, l, c):
            bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    return bars


def load_yahoo(spec, tries=4):
    """Daily bars from Yahoo Finance; a bar's day is its timestamp + 6 h floored to a UTC day (US sessions and FX/futures
    sessions that open the evening before both land on their trading date)."""
    start_s, end_s = sc.day(spec["start"]), sc.day(spec["end"])
    bars, dropped = {}, {}
    for sym in spec["symbols"]:
        def prod(sym=sym):
            err = ""
            for k in range(tries):
                try:
                    return _yahoo_daily(sym, start_s, end_s), True
                except Exception as e:      # noqa: BLE001  a missing symbol is a gap, not a crash
                    err = f"{type(e).__name__}: {e}"
                    time.sleep(2 * (k + 1))
            return {"error": err}, False
        raw = _cached(f"yahoo2|{sym}|1d|{spec['start']}|{spec['end']}", prod)
        if isinstance(raw, dict):
            dropped[sym] = raw["error"]
            continue
        by = {}
        for b in raw:
            t = (int(b["t"]) + 6 * HOUR) // 86400 * 86400
            if start_s <= t < end_s and min(b["o"], b["h"], b["l"], b["c"]) > 0:
                by[t] = b
        ts = sorted(by)
        if len(ts) < 500:
            dropped[sym] = f"only {len(ts)} bars"
            continue
        bars[sym] = {"ts": ts, "o": [by[t]["o"] for t in ts], "h": [by[t]["h"] for t in ts], "l": [by[t]["l"] for t in ts],
                     "c": [by[t]["c"] for t in ts], "v": [float(by[t].get("v") or 0) for t in ts], "tb": [0.0] * len(ts),
                     "fund": [0.0] * len(ts), "prem": None}
    return bars, dropped


def load_group(spec):
    t0 = time.time()
    bars, dropped = load_binance(spec) if spec["source"] == "binance_vision" else load_yahoo(spec)
    log(f"loaded {spec['source']} {spec['tf']} {len(bars)}/{len(spec['symbols'])} symbols in {time.time() - t0:.0f}s; dropped {dropped}")
    return bars, dropped
