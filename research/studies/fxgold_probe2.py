"""Probe 2 for family 5: Dukascopy fetch speed with the retrying fetcher, and calendar page structure. Availability only."""
import json
import re
import sys
import time
from datetime import date

from core import fxgold_data as fd
from urllib.request import Request, urlopen

out = {}
for workers in (3, 6):
    t0 = time.time()
    n = fd.fetch_year_file("EURUSD", 2019 if workers == 3 else 2021, f"/tmp/p{workers}.gz", workers=workers, start=date(2019 if workers == 3 else 2021, 3, 1), end=date(2019 if workers == 3 else 2021, 3, 31))
    out[f"candles_workers{workers}"] = dict(n, sec=round(time.time() - t0, 1))
t0 = time.time()
r, st = fd.fetch_ticks_window("XAUUSD", 1583929800, 60, 300)   # 2020-03-11 12:30 UTC
out["tick_window"] = {"status": st, "sec": round(time.time() - t0, 1), "head": (r or [])[55:75:5]}


def page(u):
    try:
        with urlopen(Request(u, headers=fd.UA), timeout=30) as x:
            return x.status, x.read().decode("utf8", "replace")
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", type(e).__name__), ""


def around(txt, key, n=2, w=350):
    res = []
    for m in list(re.finditer(key, txt))[:n]:
        res.append(re.sub(r"\s+", " ", txt[max(0, m.start() - w):m.end() + w]))
    return res


cal = {}
for y in (2016, 2019, 2022, 2025):
    st, t = page(f"https://www.bls.gov/schedule/{y}/home.htm")
    cal[f"bls_{y}"] = {"status": st, "len": len(t), "emp": around(t, "Employment Situation", 1), "cpi": around(t, "Consumer Price Index", 1)}
st, t = page("https://www.bls.gov/schedule/news_release/empsit.htm")
cal["bls_empsit"] = {"status": st, "len": len(t), "table": around(t, "Reference Month", 1, 700)}
st, t = page("https://www.bls.gov/bls/news-release/empsit.htm")
cal["bls_empsit_archive"] = {"status": st, "len": len(t), "head": around(t, "20[12][0-9]", 2, 200)}
st, t = page("https://www.bls.gov/bls/news-release/cpi.htm")
cal["bls_cpi_archive"] = {"status": st, "len": len(t), "head": around(t, "January 20", 2, 250)}
for y in (2016, 2019):
    st, t = page(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm")
    cal[f"fomc_{y}"] = {"status": st, "len": len(t), "head": around(t, "Meeting", 2, 200)}
st, t = page("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
cal["fomccalendars"] = {"status": st, "len": len(t), "head": around(t, "January", 2, 300), "years": sorted(set(re.findall(r"(20[12][0-9]) FOMC Meetings", t)))}
st, t = page("https://alfred.stlouisfed.org/series/downloaddata?seid=PAYEMS")
cal["alfred_dl"] = {"status": st, "len": len(t), "links": re.findall(r'href="([^"]*downloaddata[^"]*)"', t)[:6]}
st, t = page("https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=PAYEMS&vintage_date=2020-02-07,2020-03-06")
cal["alfred_csv"] = {"status": st, "len": len(t), "head": t[:300]}
st, t = page("https://api.stlouisfed.org/fred/release/dates?release_id=50&file_type=json")
cal["fred_api_nokey"] = {"status": st, "head": t[:200]}
out["calendar"] = cal
json.dump(out, sys.stdout, indent=1, default=str)
