"""News-shock event study. A news shock is a day when a stock gaps at the open by at least G% on volume at least
V times its 50-day average (scandals, earnings, lawsuits, guidance: the market's footprint of big news).
For each shock we measure what the stock did afterwards relative to SPY, and what trading it would have earned
after costs. Train 2010-2018, test 2019-2026 (never used to choose). python3 -m research.events"""
import json
import math
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from core import data

TICKERS = """AAPL MSFT NVDA AMZN GOOGL META TSLA BRK-B JPM V MA UNH XOM JNJ PG HD COST ABBV MRK LLY AVGO PEP KO WMT
BAC CVX ORCL CRM ADBE NFLX AMD INTC CSCO QCOM TXN IBM DIS NKE MCD SBUX BA CAT GE HON MMM UPS FDX LMT RTX GS MS C
WFC AXP BLK SCHW PFE BMY AMGN GILD CVS CI TMO DHR ABT MDT ISRG VRTX REGN T VZ CMCSA TMUS PYPL INTU NOW AMAT MU
LRCX ADI KLAC SNPS CDNS PANW F GM UBER ABNB BKNG MAR LOW TGT DG DLTR KR EL CL KHC MO PM SLB COP OXY DE""".split()
OUT = Path(__file__).resolve().parent


def bars(symbol, start="2009-01-01"):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?period1={p1}&period2={int(time.time())}&interval=1d")
    for attempt in range(4):
        try:
            res = data.get_json(url, ttl=24 * 3600)["chart"]["result"][0]
            break
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(3)
    q = res["indicators"]["quote"][0]
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    out = []
    for i, t in enumerate(res["timestamp"]):
        o, c, v, a = q["open"][i], q["close"][i], q["volume"][i], adj[i]
        if None in (o, c, v, a) or not c:
            continue
        k = a / c  # adjustment factor so open and close share the adjusted scale
        out.append({"d": time.strftime("%Y-%m-%d", time.gmtime(t + 12 * 3600)), "o": o * k, "c": a, "v": v})
    return out


def load_all():
    spy = {b["d"]: b for b in bars("SPY")}
    allb = {}
    for s in TICKERS:
        try:
            allb[s] = bars(s)
        except Exception as e:  # noqa: BLE001
            print("skip", s, e)
    return spy, allb


def find_events(allb, gap=0.04, vmult=2.5):
    ev = []
    for s, b in allb.items():
        for i in range(51, len(b) - 21):
            g = b[i]["o"] / b[i - 1]["c"] - 1
            avgv = sum(x["v"] for x in b[i - 50:i]) / 50
            if abs(g) >= gap and avgv and b[i]["v"] >= vmult * avgv:
                ev.append({"s": s, "i": i, "d": b[i]["d"], "gap": g, "day": b[i]["c"] / b[i]["o"] - 1,
                           "trend": b[i - 1]["c"] / b[i - 51]["c"] - 1})
    return ev


def fwd(b, spy, i, h, entry="close"):
    """Abnormal return (stock minus SPY) from day i close (or day i+1 open) to the close h days later."""
    j = i + h
    if j >= len(b):
        return None
    p0 = b[i]["c"] if entry == "close" else b[i + 1]["o"]
    d0 = b[i]["d"] if entry == "close" else b[i + 1]["d"]
    s0, s1 = spy.get(d0), spy.get(b[j]["d"])
    if not s0 or not s1:
        return None
    sp0 = s0["c"] if entry == "close" else s0["o"]
    return (b[j]["c"] / p0 - 1) - (s1["c"] / sp0 - 1), b[j]["c"] / p0 - 1


def summary(rets):
    if len(rets) < 5:
        return {"n": len(rets)}
    m = sum(rets) / len(rets)
    sd = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    return {"n": len(rets), "mean_pct": m * 100, "t": m / (sd / math.sqrt(len(rets))) if sd else 0,
            "win_pct": sum(r > 0 for r in rets) / len(rets) * 100}


def study(spy, allb, ev, cost=0.002):
    rows = []
    for label, cond in [("gap down >=4%, heavy volume", lambda e: e["gap"] < 0),
                        ("gap up >=4%, heavy volume", lambda e: e["gap"] > 0),
                        ("gap down, kept falling that day", lambda e: e["gap"] < 0 and e["day"] < 0),
                        ("gap down, recovered that day", lambda e: e["gap"] < 0 and e["day"] > 0),
                        ("gap up, kept rising that day", lambda e: e["gap"] > 0 and e["day"] > 0),
                        ("gap down in a stock already falling 50d", lambda e: e["gap"] < 0 and e["trend"] < 0)]:
        for period, lo, hi in [("train 2010-2018", "2010", "2018-12-31"), ("test 2019-2026", "2019", "9999")]:
            sel = [e for e in ev if cond(e) and lo <= e["d"] <= hi]
            row = {"event": label, "period": period}
            for h in (1, 5, 20, 60):
                ab = [r[0] for e in sel if (r := fwd(allb[e["s"]], spy, e["i"], h))]
                st = summary(ab)
                row[f"{h}d"] = st
            rows.append(row)
    return rows


if __name__ == "__main__":
    spy, allb = load_all()
    ev = find_events(allb)
    print(f"{len(allb)} stocks, {len(ev)} news-shock days")
    rows = study(spy, allb, ev)
    for r in rows:
        cells = "  ".join(f"{h}: {r[h].get('mean_pct', 0):+5.2f}% t{r[h].get('t', 0):+4.1f}" for h in ("1d", "5d", "20d", "60d"))
        print(f"{r['event']:42}{r['period']:16} n={r['1d']['n']:5}  {cells}")
    (OUT / "result_events.json").write_text(json.dumps(rows, indent=1))
