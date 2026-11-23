"""Funding-rate carry: hold spot long + perpetual short (market neutral) and collect funding.
Binance USDT-M funding history for majors. Annualised gross carry, before fees (about 0.1% x 4 legs to open/close).
python3 -m research.funding"""
import json, time, urllib.request

def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
        return json.loads(r.read())

for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]:
    rows, start = [], 0
    while True:
        page = get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&startTime={start}&limit=1000")
        if not page:
            break
        rows += page
        start = page[-1]["fundingTime"] + 1
        if len(page) < 1000:
            break
        time.sleep(0.3)
    by = {}
    for r in rows:
        by.setdefault(time.gmtime(r["fundingTime"] / 1000).tm_year, []).append(float(r["fundingRate"]))
    yrs = {y: f"{sum(v) / len(v) * 3 * 365 * 100:+.1f}%" for y, v in sorted(by.items())}
    neg = sum(float(r["fundingRate"]) < 0 for r in rows) / len(rows) * 100
    print(f"{sym}: carry per year by year {yrs}; negative funding {neg:.0f}% of periods")
