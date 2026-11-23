"""Portfolio simulation of the news-shock dip-buy rule found by research/evolve.py.
Each day after the close: stocks that gapped down >= G% at the open on >= V x 50-day volume are candidates.
Buy at the NEXT day's open (no same-close fill), hold H trading days, at most K positions of equity/K each.
Cost 0.10% per side. Compared with SPY buy and hold. python3 -m research.dipbuy_portfolio"""
import math

from research import events as E

FEE = 0.001


def simulate(spy, allb, gap=0.03, vmult=1.5, hold=60, slots=10, start="2010-01-01", end="9999", trend=None):
    days = [d for d in sorted(spy) if start <= d <= end]
    idx = {s: {b["d"]: i for i, b in enumerate(bs)} for s, bs in allb.items()}
    signals = {}
    for e in E.find_events(allb, gap, vmult):
        if e["gap"] < 0 and (trend is None or (trend == "falling") == (e["trend"] < 0)):
            signals.setdefault(e["d"], []).append(e)
    cash, pos, curve, trades = 1.0, [], [], []
    for k, d in enumerate(days):
        # exits at today's close
        keep = []
        for p in pos:
            b = allb[p["s"]]
            i = idx[p["s"]].get(d)
            if i is not None and i >= p["exit_i"]:
                val = p["qty"] * b[i]["c"] * (1 - FEE)
                cash += val
                trades.append(val / p["cost"] - 1)
            else:
                keep.append(p)
        pos = keep
        # entries at today's open from yesterday's signals
        if k > 0:
            for e in sorted(signals.get(days[k - 1], []), key=lambda e: e["gap"]):
                if len(pos) >= slots or any(p["s"] == e["s"] for p in pos):
                    continue
                i = idx[e["s"]].get(d)
                if i is None:
                    continue
                eq = cash + sum(p["qty"] * allb[p["s"]][idx[p["s"]].get(d, p["last_i"])]["c"] for p in pos)
                size = min(eq / slots, cash)
                if size <= 0:
                    break
                px = allb[e["s"]][i]["o"]
                pos.append({"s": e["s"], "qty": size * (1 - FEE) / px, "cost": size, "exit_i": i + hold, "last_i": i})
                cash -= size
        for p in pos:
            p["last_i"] = idx[p["s"]].get(d, p["last_i"])
        curve.append((d, cash + sum(p["qty"] * allb[p["s"]][p["last_i"]]["c"] for p in pos)))
    return curve, trades


def stats(curve):
    v = [x[1] for x in curve]
    yrs = len(v) / 252
    r = [v[i] / v[i - 1] - 1 for i in range(1, len(v))]
    m = sum(r) / len(r)
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / len(r))
    pk, mdd = v[0], 0
    for x in v:
        pk = max(pk, x)
        mdd = max(mdd, 1 - x / pk)
    yr = {}
    for d, x in curve:
        yr.setdefault(d[:4], [x, x])[1] = x
    return {"cagr": ((v[-1] / v[0]) ** (1 / yrs) - 1) * 100, "mdd": mdd * 100, "sharpe": m / sd * math.sqrt(252) if sd else 0,
            "years": {y: round((b / a - 1) * 100) for y, (a, b) in yr.items()}}


if __name__ == "__main__":
    spy, allb = E.load_all()
    spy_curve = [(d, b["c"]) for d, b in sorted(spy.items()) if d >= "2010-01-01"]
    for lab, (lo, hi) in {"search 2010-16": ("2010-01-01", "2016-12-31"), "validate 2017-20": ("2017-01-01", "2020-12-31"),
                          "lockbox 2021-26": ("2021-01-01", "9999"), "all 2010-26": ("2010-01-01", "9999")}.items():
        sp = stats([x for x in spy_curve if lo <= x[0] <= hi])
        print(f"\n{lab}: SPY {sp['cagr']:+.1f}%/y mdd {sp['mdd']:.0f}%")
        for slots in (5, 10, 20):
            for hold in (40, 60):
                c, t = simulate(spy, allb, hold=hold, slots=slots, start=lo, end=hi)
                s = stats(c)
                print(f"  slots {slots:2} hold {hold}: {s['cagr']:+.1f}%/y mdd {s['mdd']:.0f}% sharpe {s['sharpe']:.2f} trades {len(t)} win {sum(x > 0 for x in t) / max(len(t), 1) * 100:.0f}%")
    c, _ = simulate(spy, allb, hold=60, slots=10)
    print("\nyears, slots 10 hold 60:", stats(c)["years"])
    print("years, SPY:", stats(spy_curve)["years"])
