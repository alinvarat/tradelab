"""Survivorship check: the evolved dip-buy rule on stocks that were big once and then shrank or struggled.
If the edge over random-day entry vanishes here, the main result is mostly survivorship bias."""
from research import events as E
from research.evolve import BLOCKS, COST

LOSERS = """INTC WBA PARA VFC MMM BA F AAL CCL KHC LUMN M KSS GAP PFE T VZ CVS EL NKE DG DLTR SBUX LUV UAL NCLH BIIB
ILMN PYPL ZM PTON SNAP ROKU TDOC LCID RIVN BBWI HBI MPW WBD DISH XRX HPQ IBM GE C AIG MO BMY CMCSA DIS TGT""".split()
spy = {b["d"]: b for b in E.bars("SPY")}
allb = {}
for s in LOSERS:
    try:
        allb[s] = E.bars(s)
    except Exception as e:  # noqa: BLE001
        print("skip", s, e)
ev = E.find_events(allb, gap=0.03, vmult=1.5)
for blk, (lo, hi) in list(BLOCKS.items()) + [("all", ("2010", "9999"))]:
    rule, base = [], []
    for e in ev:
        if lo <= e["d"] <= hi and e["gap"] < 0:
            b = allb[e["s"]]
            if e["i"] + 60 < len(b):
                rule.append(b[e["i"] + 60]["c"] / b[e["i"]]["c"] - 1 - COST)
    for s, b in allb.items():
        for i in range(51, len(b) - 60, 5):
            if lo <= b[i]["d"] <= hi:
                base.append(b[i + 60]["c"] / b[i]["c"] - 1 - COST)
    m = lambda x: sum(x) / len(x) * 100 if x else float("nan")  # noqa: E731
    print(f"{blk:9} dip-buy after news gap down: {m(rule):+.2f}%/trade (n={len(rule)})  random day: {m(base):+.2f}%  edge {m(rule) - m(base):+.2f}")
