"""Month-start 20x long on crypto: reach +25% (6x) before -4.5% (liquidation), daily closes since 2014.
python3 -m research.leverage   (results recorded in METHODS.md; intraday wicks and funding make reality worse)"""
from core import research as R

for s in ["BTC-USD", "ETH-USD", "SOL-USD", "NVDA", "TSLA"]:
    h = R.history(s, "2014-01-01")
    m = {}
    for d in sorted(h):
        m.setdefault(d[:7], []).append(h[d])
    out = {"6x": 0, "wiped": 0, "other": 0}
    for v in m.values():
        if len(v) < 15:
            continue
        res = "other"
        for p in v[1:]:
            r = p / v[0] - 1
            if r <= -0.045:
                res = "wiped"
                break
            if r >= 0.25:
                res = "6x"
                break
        out[res] += 1
    n = sum(out.values())
    print(s, {k: f"{x} ({x / n * 100:.0f}%)" for k, x in out.items()})
