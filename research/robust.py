"""Robustness of the leading methods: yearly returns, triple costs, test halves, parameter neighbours, BTC removed."""
from core import research as R
from research.run_research import ETF

uni = ETF + ["BTC-USD"]
days, px = R.panel(uni + ["SHY"], "2004-01-01")
idx = lambda d: max(i for i, x in enumerate(days) if x <= d)
a, s, m, e = idx("2006-01-03"), idx("2016-12-31"), idx("2021-12-31"), len(days) - 1
cands = [("dual_mom", {"lookback": 63, "top": 3}), ("dual_mom", {"lookback": 126, "top": 3}),
         ("dual_mom", {"lookback": 126, "top": 2}), ("dual_mom", {"lookback": 252, "top": 3}),
         ("trend_sma", {"sma": 150}), ("trend_sma", {"sma": 200}), ("equal_weight", {}), ("buy_hold", {"asset": "SPY"})]
for name, p in cands:
    rule = R.make_rule(name, days, px, uni, p)
    c, turn = R.run(days, px, rule)
    c3, _ = R.run(days, px, R.make_rule(name, days, px, uni, p), cost=0.003)
    t1, t2, t3 = R.stats(days, c, s, m), R.stats(days, c, m, e), R.stats(days, c3, s, e)
    yrs = {}
    for i in range(s, e + 1):
        yrs.setdefault(days[i][:4], [c[i], c[i]])[1] = c[i]
    print(f"{name:12}{str(p):32} 2017-21 {t1['cagr']:6.1f}%/y mdd {t1['mdd']:4.1f} | 2022-26 {t2['cagr']:6.1f}%/y mdd {t2['mdd']:4.1f} | 3x cost {t3['cagr']:5.1f}%/y | turnover/yr {turn / ((e - a) / 252):.1f}")
    print("   years:", " ".join(f"{y}:{(v[1] / v[0] - 1) * 100:+.0f}" for y, v in yrs.items()))
# without BTC, BTC share of weights
rule = R.make_rule("dual_mom", days, px, uni, {"lookback": 63, "top": 3})
w, held = {}, 0
for i in range(s, e):
    w = rule(i, w)
    held += "BTC-USD" in w
print(f"dual_mom 63/3: BTC held on {held / (e - s) * 100:.0f}% of test days")
