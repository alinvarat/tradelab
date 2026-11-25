"""Data-depth probe for family 5 (gold & FX intraday, tick data at XM costs). Runs on GitHub Actions only.
Prints JSON: Dukascopy bi5 availability (1m BID/ASK candles and hourly ticks) per symbol and year, download speed,
and free economic-calendar history candidates. Looks at availability and spreads only, never at returns."""
import json
import lzma
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "*/*"}
SYMS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY")
DIV = {"XAUUSD": 1000.0, "USDJPY": 1000.0}


def http(url, timeout=30):
    t0 = time.time()
    try:
        with urlopen(Request(url, headers=UA), timeout=timeout) as r:
            return r.status, r.read(), round(time.time() - t0, 2)
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        head = b""
        try:
            head = e.read()[:200]
        except Exception:  # noqa: BLE001
            pass
        return code or type(e).__name__, head or str(e)[:160].encode(), round(time.time() - t0, 2)


def duka(sym, y, m, d, what):
    return f"https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m - 1:02d}/{d:02d}/{what}"


def candles(raw, sym):
    out = []
    dv = DIV.get(sym, 1e5)
    for i in range(0, len(raw) - 19, 24 if len(raw) % 24 == 0 else 20):
        s, o, c, lo, hi, v = struct.unpack(">IIIIIf", raw[i:i + 24])
        out.append((s, o / dv, c / dv, lo / dv, hi / dv, v))
    return out


def probe_candles(sym, y, m, d):
    res = {}
    for side in ("BID", "ASK"):
        st, body, dt = http(duka(sym, y, m, d, f"{side}_candles_min_1.bi5"))
        r = {"status": st, "bytes": len(body) if st == 200 else 0, "sec": dt}
        if st == 200 and body:
            try:
                raw = lzma.decompress(body)
                cs = candles(raw, sym)
                r.update(n=len(cs), first=cs[0][:3] if cs else None, mid=cs[len(cs) // 2][:3] if cs else None)
                res[side + "_rows"] = cs
            except Exception as e:  # noqa: BLE001
                r["err"] = str(e)[:100]
        res[side] = r
    b, a = res.get("BID_rows"), res.get("ASK_rows")
    sp = None
    if b and a:
        am = {x[0]: x for x in a}
        d_ = sorted(am[x[0]][2] - x[2] for x in b if x[0] in am)
        if d_:
            sp = {"n": len(d_), "median": d_[len(d_) // 2], "p90": d_[int(len(d_) * 0.9)]}
    return {"BID": res["BID"], "ASK": res["ASK"], "close_spread": sp}


def probe_ticks(sym, y, m, d, h):
    st, body, dt = http(duka(sym, y, m, d, f"{h:02d}h_ticks.bi5"))
    r = {"status": st, "bytes": len(body) if st == 200 else 0, "sec": dt}
    if st == 200 and body:
        try:
            raw = lzma.decompress(body)
            n = len(raw) // 20
            tk = [struct.unpack(">IIIff", raw[i * 20:i * 20 + 20]) for i in range(n)]
            dv = DIV.get(sym, 1e5)
            r.update(n=n, first=(tk[0][0], tk[0][1] / dv, tk[0][2] / dv) if n else None,
                     median_spread=sorted((t[1] - t[2]) / dv for t in tk)[n // 2] if n else None)
        except Exception as e:  # noqa: BLE001
            r["err"] = str(e)[:100]
    return r


def main():
    out = {"dukascopy": {}, "speed": {}, "calendar": {}}
    jobs = []
    for sym in SYMS:
        for y in (2010, 2013, 2016, 2018, 2020, 2022, 2024, 2026):
            jobs.append((sym, y, 3, 11 if y not in (2022,) else 9))
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: (j, probe_candles(*j)), jobs))
        tres = list(ex.map(lambda j: (j, probe_ticks(*j, 13)), jobs))
    for (sym, y, m, d), r in res:
        out["dukascopy"].setdefault(sym, {})[f"{y}-{m:02d}-{d:02d}"] = {"candles": r}
    for (sym, y, m, d), r in tres:
        out["dukascopy"][sym][f"{y}-{m:02d}-{d:02d}"]["ticks_13h"] = r
    # speed: 64 daily BID candle files in parallel, and 24 tick-hour files
    days = [(2024, 5, 1 + i) for i in range(31)] + [(2024, 6, 1 + i) for i in range(30)]
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        rr = list(ex.map(lambda d: http(duka("XAUUSD", *d, "BID_candles_min_1.bi5"))[0], days))
    out["speed"]["candles_61_files_16threads_sec"] = round(time.time() - t0, 1)
    out["speed"]["candle_status_counts"] = {str(k): rr.count(k) for k in set(rr)}
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        rr = list(ex.map(lambda h: http(duka("EURUSD", 2024, 5, 14, f"{h:02d}h_ticks.bi5")), range(24)))
    out["speed"]["ticks_24_files_16threads_sec"] = round(time.time() - t0, 1)
    out["speed"]["tick_total_bytes"] = sum(len(x[1]) for x in rr if x[0] == 200)
    out["speed"]["tick_status_counts"] = {str(k): [x[0] for x in rr].count(k) for k in set(x[0] for x in rr)}
    # economic calendar candidates
    cands = {
        "ff_thisweek_json": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "ff_thisweek_csv": "https://nfs.faireconomy.media/ff_calendar_thisweek.csv",
        "ff_nextweek_json": "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
        "ff_site_week": "https://www.forexfactory.com/calendar?week=jan5.2025",
        "bls_empsit": "https://www.bls.gov/schedule/news_release/empsit.htm",
        "bls_cpi": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "bls_cpi_history": "https://www.bls.gov/bls/news-release/cpi.htm",
        "fed_fomc_hist": "https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm",
        "fed_fomc_cal": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "fred_release_dates_png": "https://fred.stlouisfed.org/releases/calendar",
        "fred_empsit_release": "https://fred.stlouisfed.org/release/dates?rid=50",
        "alfred_payems": "https://alfred.stlouisfed.org/series/downloaddata?seid=PAYEMS",
        "fred_csv_payems": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PAYEMS",
        "investing_cal": "https://sslecal2.investing.com/",
        "tradingeconomics": "https://tradingeconomics.com/calendar",
        "mql5_cal": "https://www.mql5.com/en/economic-calendar",
        "dukascopy_cal": "https://www.dukascopy.com/swiss/english/marketwatch/calendar/",
        "gh_ff_archive": "https://raw.githubusercontent.com/ejtraderLabs/Forex-Factory-Calendar/main/README.md",
        "bea_gdp": "https://www.bea.gov/news/schedule",
    }
    for k, u in cands.items():
        st, body, dt = http(u)
        txt = body[:400].decode("utf8", "replace") if st == 200 else body[:150].decode("utf8", "replace")
        out["calendar"][k] = {"status": st, "bytes": len(body), "sec": dt, "head": " ".join(txt.split())[:260]}
    json.dump(out, sys.stdout, indent=1, default=str)


if __name__ == "__main__":
    main()
