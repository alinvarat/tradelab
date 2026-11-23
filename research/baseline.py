"""Baseline for the evolved rules: buy the same 104 stocks on every day, hold 60 days, same cost.
If a news rule does not beat this, its 'edge' is just owning stocks that went up (plus survivorship bias)."""
import math
from research import events as E
from research.evolve import BLOCKS, COST

spy, allb = E.load_all()
for blk, (lo, hi) in BLOCKS.items():
    for h in (40, 60):
        rets = []
        for s, b in allb.items():
            for i in range(51, len(b) - h, 5):
                if lo <= b[i]["d"] <= hi:
                    rets.append(b[i + h]["c"] / b[i]["c"] - 1 - COST)
        m = sum(rets) / len(rets)
        print(f"{blk:9} hold {h}: any-day entry {m * 100:+.2f}%/trade (n={len(rets)})")
