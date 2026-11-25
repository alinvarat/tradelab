"""D1 stage A probe (PLAN_20261126_fable direction D1): which point-in-time liquidation or forced-flow data is reachable from Actions.

Counts and structure only. Nothing here computes a forward return, a trade or a P&L; trigger counts use only information known at the
trigger time (volume and the bar's own move), so reading them cannot tune an outcome. Output: <out_dir>/probe.json.

    python research/studies/d1_probe.py <out_dir>
"""
import json
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.studies import binance_vision as bv   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
MAJORS = {"BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC", "BCH", "NEAR", "UNI", "ATOM", "ETC",
          "XLM", "FIL", "APT", "ARB", "OP", "SUI", "TON", "SHIB", "PEPE", "AAVE", "HBAR", "INJ", "TAO"}


def get(url, timeout=30):
    try:
        with urlopen(Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", None) or type(e).__name__, str(e)[:200]


def jget(url):
    st, body = get(url)
    try:
        return st, json.loads(body)
    except ValueError:
        return st, body[:300]


# ---------------------------------------------------------------- A. Binance Vision liquidationSnapshot
def probe_vision(out):
    res = {}
    for market in ("futures/um", "futures/cm"):
        for period in ("daily", "monthly"):
            key = f"{market}/{period}"
            try:
                syms = bv.list_symbols(market, quote="", kind="liquidationSnapshot", period=period)
            except Exception as e:  # noqa: BLE001
                res[key] = {"error": repr(e)[:200]}
                continue
            info = {"symbols": len(syms), "sample": syms[:8]}
            files = {}
            for s in ([x for x in syms if x in ("BTCUSDT", "ETHUSDT", "DOGEUSDT")] + syms[:3])[:5]:
                try:
                    d = bv.list_files(market, period, "liquidationSnapshot", s)
                    files[s] = {"n_files": len(d), "first": d[:1], "last": d[-1:]}
                except Exception as e:  # noqa: BLE001
                    files[s] = {"error": repr(e)[:120]}
            info["files"] = files
            res[key] = info
            for s, f in files.items():
                if f.get("n_files"):
                    d = f["first"][0] if period == "daily" else f["last"][0]
                    rows = bv.fetch(market, period, "liquidationSnapshot", s, d, None, bv.parse_raw)
                    info["header_probe"] = {"symbol": s, "date": d, "rows": None if rows is None else len(rows), "first_rows": (rows or [])[:2]}
                    break
    out["binance_vision_liquidationSnapshot"] = res


# ---------------------------------------------------------------- B. OKX and Gate APIs
def probe_okx(out):
    res = {}
    base = "https://www.okx.com/api/v5/public/liquidation-orders"
    for uly in ("BTC-USDT", "DOGE-USDT", "PEPE-USDT"):
        q = urlencode({"instType": "SWAP", "uly": uly, "state": "filled", "limit": 100})
        st, d = jget(f"{base}?{q}")
        det = []
        if isinstance(d, dict) and d.get("data"):
            for blk in d["data"]:
                det += blk.get("details") or []
        tss = [int(x["ts"]) for x in det if x.get("ts")]
        res[f"live_{uly}"] = {"status": st, "code": d.get("code") if isinstance(d, dict) else None, "n_details": len(det),
                              "ts_min": min(tss) if tss else None, "ts_max": max(tss) if tss else None,
                              "keys": sorted(det[0]) if det else None}
    old = int((time.time() - 30 * 86400) * 1000)
    q = urlencode({"instType": "SWAP", "uly": "DOGE-USDT", "state": "filled", "limit": 100, "after": old})
    res["after_30d_ago"] = dict(zip(("status", "body"), (lambda s, d: (s, d if isinstance(d, str) else {"code": d.get("code"), "msg": d.get("msg"), "n_blocks": len(d.get("data") or [])}))(*jget(f"{base}?{q}"))))
    inst = jget("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
    res["usdt_swaps"] = len([x for x in (inst[1].get("data") or []) if x["instId"].endswith("-USDT-SWAP")]) if isinstance(inst[1], dict) else inst
    mdh = {}
    for module in range(1, 8):
        q = urlencode({"module": module, "instType": "SWAP", "instFamilyList": "DOGE-USDT", "dateAggrType": "daily", "begin": old, "end": int(time.time() * 1000)})
        st, d = jget(f"https://www.okx.com/api/v5/public/market-data-history?{q}")
        mdh[module] = {"status": st, "resp": d if isinstance(d, str) else {"code": d.get("code"), "msg": d.get("msg"), "data": str(d.get("data"))[:200]}}
    res["market_data_history_modules"] = mdh
    out["okx"] = res


def probe_gate(out):
    res = {}
    base = "https://api.gateio.ws/api/v4/futures/usdt/liq_orders"
    for c in ("DOGE_USDT", "PEPE_USDT"):
        st, d = jget(f"{base}?contract={c}&limit=100")
        res[f"live_{c}"] = {"status": st, "n": len(d) if isinstance(d, list) else None, "sample": d[:1] if isinstance(d, list) else d,
                            "t_min": min(x["time"] for x in d) if isinstance(d, list) and d else None,
                            "t_max": max(x["time"] for x in d) if isinstance(d, list) and d else None}
    now = int(time.time())
    for days in (30, 180, 365):
        st, d = jget(f"{base}?contract=DOGE_USDT&limit=100&from={now - (days + 1) * 86400}&to={now - days * 86400}")
        res[f"window_{days}d_ago"] = {"status": st, "n": len(d) if isinstance(d, list) else None, "sample": d[:1] if isinstance(d, list) else d}
    st, d = jget("https://api.gateio.ws/api/v4/futures/usdt/contracts")
    res["usdt_contracts"] = len(d) if isinstance(d, list) else d
    out["gate"] = res


def probe_other(out):
    res = {}
    for name, url in (("bybit_recent_liq", "https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=DOGEUSDT&limit=5"),
                      ("binance_allForceOrders", "https://fapi.binance.com/fapi/v1/allForceOrders?symbol=DOGEUSDT&limit=5"),
                      ("bitmex_liquidation", "https://www.bitmex.com/api/v1/liquidation?count=5&reverse=true"),
                      ("bitget_liq", "https://api.bitget.com/api/v2/mix/market/oi-limit?symbol=DOGEUSDT&productType=USDT-FUTURES")):
        st, body = get(url)
        res[name] = {"status": st, "body": body[:160]}
    out["other"] = res


# ---------------------------------------------------------------- C. proxy from 1-minute klines
def proxy_counts(sym, months_, out_rows):
    """Per symbol and month: bars available, and counts of 5-minute windows by volume multiple and absolute move. No forward data."""
    per = {}
    for (y, m) in months_:
        rows = bv.fetch("futures/um", "monthly", "klines", sym, (y, m), "1m", bv.parse_kline)
        if rows is None:
            per[f"{y}-{m:02d}"] = "failed"
            continue
        if not rows:
            per[f"{y}-{m:02d}"] = 0
            continue
        w = {}
        for r in rows:
            k = int(r[0] // 300)
            a = w.get(k)
            if a is None:
                w[k] = [r[1], r[4], r[7], r[10]]                       # open, close, quote volume, taker-buy quote volume
            else:
                a[1] = r[4]
                a[2] += r[7]
                a[3] += r[10]
        ks = sorted(w)
        vols = [w[k][2] for k in ks]
        cnt = {"bars_1m": len(rows), "w5": len(ks)}
        trig = {"v10_m2": 0, "v10_m3": 0, "v20_m3": 0, "v20_m5": 0}
        win, last = [], {}
        for i, k in enumerate(ks):
            win.append(vols[i])
            if len(win) > 288:
                win.pop(0)
            if len(win) < 288:
                continue
            med = statistics.median(win)
            o, c, qv, tb = w[k]
            if med <= 0 or o <= 0:
                continue
            mv, mv_move = qv / med, abs(c / o - 1)
            for name, (a, b) in {"v10_m2": (10, .02), "v10_m3": (10, .03), "v20_m3": (20, .03), "v20_m5": (20, .05)}.items():
                if mv >= a and mv_move >= b and k - last.get(name, -99) > 6:      # one cluster = windows less than 30 min apart merge
                    trig[name] += 1
                    last[name] = k
        cnt.update(trig)
        per[f"{y}-{m:02d}"] = cnt
    out_rows[sym] = per


def probe_proxy(out):
    try:
        allsyms = bv.list_symbols("futures/um", "USDT", "klines", "monthly")
    except Exception as e:  # noqa: BLE001
        out["proxy"] = {"error": repr(e)[:200]}
        return
    small = [s for s in allsyms if s[:-4].lstrip("0123456789") not in MAJORS and s.isascii()]
    rng = random.Random(20261126)
    pick = rng.sample(small, min(24, len(small)))
    months_ = [(2026, m) for m in range(5, 11)]
    rows = {}
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda s: proxy_counts(s, months_, rows), pick))
    tot = {k: 0 for k in ("v10_m2", "v10_m3", "v20_m3", "v20_m5")}
    live = 0
    for s, per in rows.items():
        have = [v for v in per.values() if isinstance(v, dict)]
        live += bool(have)
        for v in have:
            for k in tot:
                tot[k] += v[k]
    out["proxy"] = {"usdt_perp_symbols": len(allsyms), "small_symbols": len(small), "sampled": len(pick), "sampled_with_data": live,
                    "months": [f"{y}-{m:02d}" for y, m in months_], "cluster_totals_sample_6m": tot,
                    "per_month_per_symbol": {k: round(v / 6 / max(1, live), 3) for k, v in tot.items()}, "rows": rows}


def probe_metrics(out):
    got = {}
    for s in ("DOGEUSDT", "PEPEUSDT", "1000PEPEUSDT"):
        r = bv.fetch("futures/um", "daily", "metrics", s, (2026, 10, 15), None, bv.parse_metrics)
        got[s] = None if r is None else {"rows": len(r), "first": r[:1]}
    out["metrics"] = got


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    out = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    for fn in (probe_vision, probe_okx, probe_gate, probe_other, probe_metrics, probe_proxy):
        try:
            fn(out)
        except Exception as e:  # noqa: BLE001
            out[fn.__name__] = {"error": repr(e)[:300]}
        print(fn.__name__, json.dumps(out.get({"probe_vision": "binance_vision_liquidationSnapshot", "probe_okx": "okx", "probe_gate": "gate",
                                              "probe_other": "other", "probe_metrics": "metrics", "probe_proxy": "proxy"}[fn.__name__]),
                                      default=str)[:3500], flush=True)
    with open(os.path.join(out_dir, "probe.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
