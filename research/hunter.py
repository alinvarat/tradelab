"""Hunter mode research: leveraged crypto trend following aimed at large monthly gains.
Rule (per coin, daily close, decided at close, filled next open): long when close > SMA(fast) and the
`mom`-day return > 0; flat otherwise. Leverage L on equity split equally across active coins.
Costs: 0.05% per side, funding 0.01% per 8h on notional (0.03%/day). A day whose low (intraday) wipes the
margin of a position liquidates it. Account ruin = equity below 5% of start.
Measures, per month: share of months with >= 6x, share ruined, median month; plus whole-period path.
Train 2018-2022, test 2023-2026. python3 -m research.hunter"""
import json
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from core import data, indicators as ind

COINS = ["BTC-USD", "ETH-USD", "SOL-USD"]
FEE, FUND = 0.0005, 0.0003
OUT = Path(__file__).resolve().parent


def ohlc(sym, start="2017-01-01"):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?period1={p1}&period2={int(time.time())}&interval=1d")
    r = data.get_json(url, ttl=24 * 3600)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    return {time.strftime("%Y-%m-%d", time.gmtime(t)): (q["open"][i], q["low"][i], q["close"][i])
            for i, t in enumerate(r["timestamp"]) if None not in (q["open"][i], q["low"][i], q["close"][i])}


def month_runs(days, px, lev, fast, mom, start, end):
    """Each calendar month starts fresh at 1.0: returns the month-end multiple (what a monthly 6x target means)."""
    sig = {}
    for s in COINS:
        ds = [d for d in days if d in px[s]]
        c = [px[s][d][2] for d in ds]
        sm = ind.sma(c, fast)
        sig[s] = {ds[i]: (sm[i] is not None and i >= mom and c[i] > sm[i] and c[i] / c[i - mom] > 1) for i in range(len(ds))}
    months = {}
    for d in days:
        if start <= d <= end:
            months.setdefault(d[:7], []).append(d)
    out = []
    for m, ds in months.items():
        eq, pos = 1.0, {}  # pos: coin -> (units, entry)
        prev = days[days.index(ds[0]) - 1]
        for d in ds:
            active = [s for s in COINS if sig[s].get(prev)]
            # rebalance at today's open to target
            for s in list(pos):
                if s not in active and d in px[s]:
                    u, e = pos.pop(s)
                    eq += u * (px[s][d][0] - e) - abs(u) * px[s][d][0] * FEE
            for s in active:
                if s not in pos and d in px[s] and eq > 0:
                    notional = eq * lev / len(active)
                    o = px[s][d][0]
                    pos[s] = (notional / o, o)
                    eq -= notional * FEE
            # intraday liquidation check, funding, mark to close
            for s in list(pos):
                if d not in px[s]:
                    continue
                u, e = pos[s]
                eq -= u * px[s][d][2] * FUND
                worst = eq + sum(uu * (px[k][d][1] - ee) for k, (uu, ee) in pos.items() if d in px[k])
                if worst <= 0:
                    eq, pos = 0.0, {}
                    break
            if eq <= 0:
                break
            mark = eq + sum(u * (px[s][d][2] - e) for s, (u, e) in pos.items() if d in px[s])
            if mark <= 0:
                eq = 0
                break
            prev = d
        final = eq + sum(u * (px[s][ds[-1]][2] - e) for s, (u, e) in pos.items() if ds[-1] in px[s]) if eq > 0 else 0.0
        out.append(max(final, 0.0))
    return out


def summarize(ms):
    ms_sorted = sorted(ms)
    return {"months": len(ms), "p6x": sum(m >= 6 for m in ms) / len(ms) * 100,
            "p2x": sum(m >= 2 for m in ms) / len(ms) * 100, "ruin": sum(m <= 0.05 for m in ms) / len(ms) * 100,
            "median": ms_sorted[len(ms) // 2], "mean": sum(ms) / len(ms)}


if __name__ == "__main__":
    px = {s: ohlc(s) for s in COINS}
    days = sorted(set().union(*[set(v) for v in px.values()]))
    rows = []
    for lev in (1, 3, 5, 10, 20):
        for fast, mom in ((20, 20), (50, 30), (10, 10)):
            tr = summarize(month_runs(days, px, lev, fast, mom, "2018-01-01", "2022-12-31"))
            te = summarize(month_runs(days, px, lev, fast, mom, "2023-01-01", "2099"))
            rows.append({"lev": lev, "fast": fast, "mom": mom, "train": tr, "test": te})
            print(f"lev {lev:2} sma{fast:2} mom{mom:2} | train 6x {tr['p6x']:4.1f}% 2x {tr['p2x']:4.1f}% ruin {tr['ruin']:4.1f}% "
                  f"median {tr['median']:.2f} mean {tr['mean']:.2f} | test 6x {te['p6x']:4.1f}% 2x {te['p2x']:4.1f}% "
                  f"ruin {te['ruin']:4.1f}% median {te['median']:.2f} mean {te['mean']:.2f}")
    (OUT / "result_hunter.json").write_text(json.dumps(rows, indent=1))
