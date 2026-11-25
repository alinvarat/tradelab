"""Data-depth probe for family 7 (US small-cap intraday long events). Runs on GitHub Actions only.
Prints JSON: Yahoo 5m/1m/15m/1h depth with pre/post, Alpaca/Polygon/Stooq without keys, Nasdaq halt feeds."""
import json
import sys
import time
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "*/*"}


def http(url, timeout=25):
    t0 = time.time()
    try:
        with urlopen(Request(url, headers=UA), timeout=timeout) as r:
            body = r.read()
            return r.status, body, round(time.time() - t0, 2)
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        head = b""
        try:
            head = e.read()[:300]
        except Exception:  # noqa: BLE001
            pass
        return code or type(e).__name__, head or str(e)[:200].encode(), round(time.time() - t0, 2)


def yahoo_depth(sym, rng, iv):
    st, body, dt = http(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}&includePrePost=true")
    out = {"status": st, "sec": dt}
    try:
        res = json.loads(body)["chart"]["result"][0]
        ts = res.get("timestamp") or []
        off = res["meta"].get("gmtoffset", 0)
        hrs = {}
        for t in ts:
            h = int(((t + off) % 86400) // 3600)
            hrs[h] = hrs.get(h, 0) + 1
        out.update(n=len(ts), first=time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts[0])) if ts else None,
                   last=time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts[-1])) if ts else None,
                   gmtoffset=off, bars_by_local_hour=dict(sorted(hrs.items())))
    except Exception as e:  # noqa: BLE001
        out["err"] = f"{type(e).__name__} {str(body[:120])}"
    return out


def main():
    res = {}
    for sym in ("AMC", "SNDL", "PLUG"):
        for rng, iv in (("60d", "5m"), ("1mo", "1m"), ("60d", "15m"), ("2y", "1h"), ("730d", "1h")):
            res[f"yahoo_{sym}_{rng}_{iv}"] = yahoo_depth(sym, rng, iv)
    urls = {
        "alpaca_iex_nokey": "https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL&timeframe=5Min&start=2022-01-03T14:30:00Z&end=2022-01-03T15:30:00Z&feed=iex",
        "polygon_nokey": "https://api.polygon.io/v2/aggs/ticker/AAPL/range/5/minute/2022-01-03/2022-01-03",
        "stooq_5m": "https://stooq.com/q/d/l/?s=aapl.us&i=5",
        "nasdaq_halts_rss": "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts",
        "nasdaq_halts_page": "https://www.nasdaqtrader.com/Trader.aspx?id=TradeHalts",
        "nasdaq_halts_hist": "https://www.nasdaqtrader.com/Trader.aspx?id=TradeHaltHistory",
        "nasdaq_halts_hist_csv": "https://www.nasdaqtrader.com/dynamic/symdir/tradehaltshistory.txt",
        "nyse_halts": "https://www.nyse.com/api/trade-halts/current",
        "sec_tickers_exch": "https://www.sec.gov/files/company_tickers_exchange.json",
        "nasdaq_premarket_api": "https://api.nasdaq.com/api/marketmovers/pre-market",
    }
    for name, u in urls.items():
        st, body, dt = http(u)
        res[name] = {"status": st, "sec": dt, "bytes": len(body), "head": body[:400].decode("utf-8", "replace")}
    json.dump(res, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
