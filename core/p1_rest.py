"""P1: deep resting limit orders on small Binance USDT-M perps (fills only when a bar trades THROUGH the limit). Pure functions, no network.
Spec: research/studies/protocol_p1p4_20261126.md (locked before any P1 fill or return was computed). Reuses the D1 series, splits and the
core.sweep_stats gate; trades are dicts in the core.sweep_engine format.

Bars are indexed by minute i = (ts - T0) / 60 as in core.d1_liq. A fill row is a list (FIELDS order).
"""
import hashlib
import math
import time
from array import array

from core import d1_liq as d1

NAN = float("nan")
T0, START, END, NM, BOUNDS, MONTHS = d1.T0, d1.START, d1.END, d1.NM, d1.BOUNDS, d1.MONTHS

DS = (0.03, 0.05, 0.08)
HOLDS = (1, 5, 15)                         # minutes after the end of the fill bar
THROUGH = 0.001                            # a fill needs the bar to trade this far beyond the limit
MIN_BAR_QV = 5000.0
MIN_DAY_QV = d1.MIN_DAY_QV
DAY_MIN = 1440
FEE_MAKER, FEE_TAKER, EXIT_SLIP = 0.0002, 0.0005, 0.0015
COST = FEE_MAKER + FEE_TAKER + EXIT_SLIP   # 0.22% round trip, maker in / taker out
COST_TAKER = d1.COST                       # 0.40%: the D1 taker round trip (late-taker control, stress column)
FUND = d1.FUND
STOP, STOP_SLIP = d1.STOP, d1.STOP_SLIP
SIZE = d1.SIZE
CFG = d1.CFG
GAP_MIN = 0.002                            # resting fill must beat the late taker by this much a fill
TOP_SHARE_MAX = 0.5
AUDIT_MOD, AUDIT_CAP, AUDIT_USD = 20, 40, 150.0
AUDIT_UNSUPPORTED_MAX = 0.20
FIELDS = ("sym", "i", "side", "d", "hold", "gross", "ctrl", "taker", "mfe", "mae", "reason", "te", "x")


def cell_id(d, hold, side):
    return f"d{round(d * 100)}|h{hold}m|{'bid' if side > 0 else 'ask'}"


def cells():
    return [(cell_id(d, h, sd), d, h, sd) for d in DS for h in HOLDS for sd in (1, -1)]


# ---------------------------------------------------------------- fills
def day_prefix(s):
    """Cumulative quote volume, pre[k] = sum of qv over minutes < k (a missing minute counts 0)."""
    pre = array("d", [0.0]) * (NM + 1)
    acc = 0.0
    for k in range(NM):
        v = s.qv[k]
        if v == v:
            acc += v
        pre[k + 1] = acc
    return pre


def find_fills(s, a=START, b=END):
    """{(d, side): [bar index i, ...]} in time order. Bar i is the live bar of an order set against the close of bar i-2. Side +1 = bid (long), -1 = ask (short).
    A fill needs the bar to trade through the limit by THROUGH, bar quote volume >= MIN_BAR_QV and a trailing 24 h quote volume (to the close of bar i-2) >= MIN_DAY_QV."""
    out = {(d, sd): [] for d in DS for sd in (1, -1)}
    pre = day_prefix(s)
    lo_all, hi_all = 1 - (DS[0] + THROUGH), 1 + (DS[0] + THROUGH)
    i0 = max(DAY_MIN + 2, int((a - T0) // 60))
    i1 = min(NM - 20, int((b - T0) // 60))
    c, lo, hi, qv = s.c, s.l, s.h, s.qv
    for i in range(i0, i1):
        ref = c[i - 2]
        low = lo[i]
        if ref != ref or low != low or ref <= 0:
            continue
        if low > ref * lo_all and hi[i] < ref * hi_all:
            continue
        if not qv[i] >= MIN_BAR_QV:
            continue
        if pre[i - 1] - pre[i - 1 - DAY_MIN] < MIN_DAY_QV:
            continue
        for d in DS:
            if low <= ref * (1 - d - THROUGH):
                out[(d, 1)].append(i)
            if hi[i] >= ref * (1 + d + THROUGH):
                out[(d, -1)].append(i)
    return out


def rest_trade(s, side, i, limit, hold):
    """One filled resting order: entry at `limit` in bar i, exit at the open of bar i+1+hold (<= 3 bars late). Stop 5% from the fill checked on every bar from i,
    stop fill = stop + 0.5% slippage. None when no exit bar exists. Returns dict(gross, mfe, mae, te, x, xi, reason); xi = exit bar index (one position at a time)."""
    xi = next((j for j in range(i + 1 + hold, i + 4 + hold) if j < NM and s.o[j] == s.o[j]), None)
    if xi is None or limit <= 0:
        return None
    fav = adv = limit
    gross, reason, end = None, "time", xi
    for j in range(i, xi):
        h, l = s.h[j], s.l[j]
        if h != h:
            continue
        if side > 0:
            adv = min(adv, l)
            fav = max(fav, s.c[i] if j == i else h)
            hit = l <= limit * (1 - STOP)
        else:
            adv = max(adv, h)
            fav = min(fav, s.c[i] if j == i else l)
            hit = h >= limit * (1 + STOP)
        if hit:
            gross, reason, end = -(STOP + STOP_SLIP), "stop", j + 1
            break
    if gross is None:
        gross = side * (s.o[xi] / limit - 1)
    mfe = (fav - limit) / limit if side > 0 else (limit - fav) / limit
    mae = (limit - adv) / limit if side > 0 else (adv - limit) / limit
    return {"gross": gross, "mfe": max(mfe, 0.0), "mae": max(mae, 0.0), "te": T0 + i * 60, "x": T0 + end * 60, "xi": end, "reason": reason}


def cell_rows(s, sym, fills, d, hold, side):
    """Fill rows of one cell (d, hold, side) on one symbol: one position at a time, with the late-taker and random-time controls (gross)."""
    out, free = [], -1
    for i in fills:
        if i < free:
            continue
        ref = s.c[i - 2]
        limit = ref * (1 - d) if side > 0 else ref * (1 + d)
        t = rest_trade(s, side, i, limit, hold)
        if t is None:
            continue
        free = t["xi"]
        ts = T0 + i * 60
        tk = d1.trade(s, side, ts, 60, hold * 60)
        cg = d1.control_gross(s, sym, ts, side, 0, hold * 60)
        out.append([sym, i, side, d, hold, round(t["gross"], 6), None if cg is None else round(cg, 6), None if tk is None else round(tk["gross"], 6),
                    round(t["mfe"], 5), round(t["mae"], 5), t["reason"], t["te"], t["x"]])
    return out


def symbol_rows(s, sym, a=START, b=END):
    """All cells' rows of one symbol, plus the raw fill counts per (d, side)."""
    fills = find_fills(s, a, b)
    rows = []
    for _, d, h, sd in cells():
        rows += cell_rows(s, sym, fills[(d, sd)], d, h, sd)
    return rows, {f"{round(d * 100)}{'b' if sd > 0 else 'a'}": len(v) for (d, sd), v in fills.items()}


# ---------------------------------------------------------------- trades, clusters
def fill_trade(r):
    g = dict(zip(FIELDS, r))
    t = {"sym": g["sym"], "side": g["side"], "t": T0 + g["i"] * 60, "te": g["te"], "x": g["x"], "gross": g["gross"], "cost": COST, "fund": FUND,
         "net": g["gross"] - COST - FUND, "mfe": g["mfe"], "mae": g["mae"], "reason": g["reason"]}
    if g["ctrl"] is not None:
        t["ctrl_net"] = g["ctrl"] - COST - FUND
    if g["taker"] is not None:
        t["taker_net"] = g["taker"] - COST_TAKER - FUND
    return t


def _mean(x):
    return sum(x) / len(x) if x else None


def clusters(fills):
    """Equal-weight cluster per UTC hour of the fill bar. Returns cluster trades (t = hour start, te = first fill, x = last exit, n_fills)."""
    byh = {}
    for f in fills:
        byh.setdefault(int(f["t"] // 3600), []).append(f)
    out = []
    for h in sorted(byh):
        g = byh[h]
        c = {"sym": f"h{h}", "side": 0, "t": float(h * 3600), "te": min(f["te"] for f in g), "x": max(f["x"] for f in g), "n_fills": len(g),
             "gross": _mean([f["gross"] for f in g]), "cost": COST, "fund": FUND, "net": _mean([f["net"] for f in g]),
             "mfe": _mean([f["mfe"] for f in g]), "mae": _mean([f["mae"] for f in g])}
        cn = [f["ctrl_net"] for f in g if "ctrl_net" in f]
        tn = [f["taker_net"] for f in g if "taker_net" in f]
        if cn:
            c["ctrl_net"] = _mean(cn)
        if tn:
            c["taker_net"] = _mean(tn)
        out.append(c)
    return out


def stats(values, months):
    return d1.stats(values, months)


def top_share(nets, frac=0.01):
    """Share of the total profit (sum of nets) made by the best `frac` of the fills; None when the total is not positive."""
    n = len(nets)
    tot = sum(nets)
    if n == 0 or tot <= 0:
        return None
    k = max(1, int(math.ceil(frac * n)))
    return sum(sorted(nets, reverse=True)[:k]) / tot


def late_taker_gap(fills):
    """Mean of (rule net - late-taker net) over the fills that have both; None if there are none."""
    return _mean([f["net"] - f["taker_net"] for f in fills if "taker_net" in f])


def audit_pick(sym, i, d, side):
    """Deterministic audit sample membership and order key (the lowest keys are audited first)."""
    h = int(hashlib.sha1(f"{sym}:{i}:{round(d * 100)}:{side}".encode()).hexdigest(), 16)
    return h % AUDIT_MOD == 0, h


def through_notional(prints, ts0, limit, side):
    """prints: (ts_s, price, qty, buyer_is_maker). Notional (USDT) of prints inside the fill minute [ts0, ts0 + 60) priced through the limit by THROUGH."""
    tot = 0.0
    for ts, p, q, _ in prints:
        if ts0 <= ts < ts0 + 60 and ((side > 0 and p <= limit * (1 - THROUGH)) or (side < 0 and p >= limit * (1 + THROUGH))):
            tot += p * q
    return tot


def audit_supported(notional):
    return notional >= AUDIT_USD


def now_utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
