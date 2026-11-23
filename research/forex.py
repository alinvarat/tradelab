"""Forex study on 9 major pairs plus gold, daily bars since 2004 (Yahoo).
1) Classic rules (long and short) with a 0.02% per-side cost (about 1-2 pips): parameters fixed in advance,
   train 2004-2016 and test 2017-2026 reported separately.
2) Retail-style high leverage: how often a month-start position at 1:100 or 1:500 reaches 6x before a margin call.
python3 -m research.forex"""
import time
import urllib.parse
from datetime import datetime, timezone

from core import backtest as bt, data

PAIRS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "EURJPY=X", "GBPJPY=X", "GC=F"]
RULES = [("sma_cross", {"fast": 50, "slow": 200}), ("ema_cross", {"fast": 20, "slow": 50}),
         ("donchian", {"entry": 55, "exit": 20}), ("donchian", {"entry": 20, "exit": 10}),
         ("macd", {}), ("bb_breakout", {}), ("rsi_revert", {}), ("bb_revert", {})]


def ohlc(sym, start="2003-01-01"):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           f"?period1={p1}&period2={int(time.time())}&interval=1d")
    res = data.get_json(url, ttl=24 * 3600)["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(res["timestamp"]):
        o, h, l, c = (q[k][i] for k in ("open", "high", "low", "close"))
        if None in (o, h, l, c) or not (l <= o <= h and l <= c <= h) or h / l > 1.3:
            continue  # drop missing and broken candles
        out.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": 0})
    return out


def seg_ret(curve, t0, t1):
    pts = [v for t, v in curve if t0 <= t <= t1]
    return (pts[-1] / pts[0] - 1) * 100 if len(pts) > 2 else None


def main():
    allb = {s: ohlc(s) for s in PAIRS}
    split = datetime(2017, 1, 1, tzinfo=timezone.utc).timestamp()
    print("1) Rules, long and short, full position, cost 0.02%/side. Total % return train 2004-16 | test 2017-26")
    summary = {}
    for key, p in RULES:
        tr, te = [], []
        for s, b in allb.items():
            r = bt.simulate(b, key, p, 10_000, 0.02, 0.0, 100, 0, True)
            a, z = seg_ret(r["equity"], 0, split), seg_ret(r["equity"], split, 2e9)
            if a is not None and z is not None:
                tr.append(a)
                te.append(z)
        summary[f"{key} {p}"] = (sum(tr) / len(tr), sum(te) / len(te), sum(x > 0 for x in te))
        print(f"  {bt.STRATEGIES[key]['name']:28}{str(p):30} avg train {sum(tr) / len(tr):+7.1f}%  avg test {sum(te) / len(te):+7.1f}%  "
              f"pairs positive in test {sum(x > 0 for x in te)}/{len(te)}")
    bh = [seg_ret([(b2['t'], b2['c']) for b2 in b], split, 2e9) for b in allb.values()]
    print(f"  (for scale: average absolute move of a pair over the test years is {sum(abs(x) for x in bh) / len(bh):.0f}%)")

    print("\n2) Month-start position, pick the right direction afterwards is NOT allowed: always long, then always short.")
    for lev in (100, 500):
        need, stop = 5 / lev * 100 / 100, 1 / lev * 0.9  # +X% move for 6x; margin call near -0.9/lev
        need = 5 / lev
        hit = wipe = tot = 0
        for s, b in allb.items():
            months = {}
            for x in b:
                months.setdefault(time.strftime("%Y-%m", time.gmtime(x["t"])), []).append(x)
            for m, xs in months.items():
                if len(xs) < 15:
                    continue
                for side in (1, -1):
                    p0, res = xs[0]["o"], None
                    for x in xs:
                        adverse = (x["l"] / p0 - 1) if side > 0 else (1 - x["h"] / p0)
                        fav = (x["h"] / p0 - 1) if side > 0 else (1 - x["l"] / p0)
                        if adverse <= -stop:
                            res = "wipe"
                            break
                        if fav >= need:
                            res = "hit"
                            break
                    tot += 1
                    hit += res == "hit"
                    wipe += res == "wipe"
        print(f"  1:{lev}: 6x needs a {need * 100:.2f}% move, margin call at about -{stop * 100:.2f}%. "
              f"6x in {hit / tot * 100:.1f}% of trials, wiped in {wipe / tot * 100:.1f}% (n={tot})")
    return summary


if __name__ == "__main__":
    main()
