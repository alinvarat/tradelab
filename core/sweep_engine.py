"""sweep engine: signal primitives, trade simulation and cost models for config-driven rule screens.

Pure functions, standard library only, no network. A rule (see research/sweeps/README via core/sweep_config.py) is
data: entry conditions built from the primitives below, a side, an exit (time, stop, target, trailing), sizing and a
cost model. Bars are a dict of equal-length lists: ts, o, h, l, c, v, tb (taker-buy base volume), fund (settled funding
rate summed per bar, long pays when positive) and prem (premium index close, or None).

Timing contract (no look-ahead): every feature value at index i uses bars <= i only. A signal at bar i is acted on at
the next bar's open (entry "next_open", default) or at bar i's close (entry "close"). Time points: 2k is the open of bar
k and 2k+1 its close. A time exit is `time` bars after the entry on the same phase (open->open), or on the other phase
(exit.on = "open" | "close") 2*time-1 points later: entry next_open + exit.on close + time 1 is the bar's own
open->close (intraday), entry close + exit.on open + time 1 is close->next open (overnight). Stops and targets are
checked on every bar held (stop first when both are hit in one bar; a bar that opens beyond a level fills at the open).
Funding is charged for every bar held (settlements stamped at the start of a held bar).
"""
import bisect
import math
import time
from collections import deque

NAN = float("nan")

OPS = ("gt", "lt", "ge", "le", "between", "in", "eq")
RESERVED = frozenset(("f", "lag") + OPS)


# ------------------------------------------------------------------ rolling helpers
def _prefix(x):
    s, q, k = [0.0], [0.0], [0]
    for v in x:
        if v != v:
            s.append(s[-1])
            q.append(q[-1])
            k.append(k[-1] + 1)
        else:
            s.append(s[-1] + v)
            q.append(q[-1] + v * v)
            k.append(k[-1])
    return s, q, k


def roll_sum(x, n):
    s, _, k = _prefix(x)
    out = [NAN] * len(x)
    for i in range(n - 1, len(x)):
        if k[i + 1] - k[i + 1 - n] == 0:
            out[i] = s[i + 1] - s[i + 1 - n]
    return out


def roll_mean(x, n):
    return [v / n if v == v else NAN for v in roll_sum(x, n)]


def roll_std(x, n):
    """Population standard deviation of the last n values (NaN when the window holds a NaN)."""
    s, q, k = _prefix(x)
    out = [NAN] * len(x)
    for i in range(n - 1, len(x)):
        if k[i + 1] - k[i + 1 - n] == 0:
            m = (s[i + 1] - s[i + 1 - n]) / n
            var = (q[i + 1] - q[i + 1 - n]) / n - m * m
            out[i] = math.sqrt(var) if var > 0 else 0.0
    return out


def roll_max(x, n):
    out, dq = [NAN] * len(x), deque()
    for i, v in enumerate(x):
        while dq and x[dq[-1]] <= v:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - n:
            dq.popleft()
        if i >= n - 1:
            out[i] = x[dq[0]]
    return out


def roll_min(x, n):
    out, dq = [NAN] * len(x), deque()
    for i, v in enumerate(x):
        while dq and x[dq[-1]] >= v:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - n:
            dq.popleft()
        if i >= n - 1:
            out[i] = x[dq[0]]
    return out


def shift(x, k):
    """Value of x from k bars ago (k >= 0); the first k entries are NaN."""
    if k <= 0:
        return list(x)
    return [NAN] * min(k, len(x)) + list(x[:max(0, len(x) - k)])


def pct_rank(x, lb):
    """Share of the previous lb values (positions i-lb..i-1, NaN skipped) that are below x[i]; NaN until the window is full."""
    out, win = [NAN] * len(x), []
    for i, v in enumerate(x):
        if i >= lb and v == v and len(win) >= lb:
            out[i] = bisect.bisect_left(win, v) / len(win)
        if v == v:
            bisect.insort(win, v)
        if i >= lb:
            old = x[i - lb]
            if old == old:
                j = bisect.bisect_left(win, old)
                del win[j]
    return out


def true_range(d):
    h, l, c = d["h"], d["l"], d["c"]
    return [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]


def atr_abs(d, n=14):
    return roll_mean(true_range(d), n)


# ------------------------------------------------------------------ features
def _ret(c, n):
    out = [NAN] * len(c)
    for i in range(n, len(c)):
        out[i] = c[i] / c[i - n] - 1
    return out


def f_ret(ctx, sym, p):
    return _ret(ctx.bars[sym]["c"], int(p.get("n", 1)))


def f_zret(ctx, sym, p):
    n, vn = int(p.get("n", 1)), int(p.get("vol_n", 100))
    c = ctx.bars[sym]["c"]
    sd = roll_std(_ret(c, 1), vn)
    r = _ret(c, n)
    sq = math.sqrt(n)
    return [x / (s * sq) if (x == x and s == s and s > 1e-12) else NAN for x, s in zip(r, sd)]


def f_atrp(ctx, sym, p):
    d = ctx.bars[sym]
    return [a / c if a == a else NAN for a, c in zip(atr_abs(d, int(p.get("n", 14))), d["c"])]


def f_atr_ratio(ctx, sym, p):
    d = ctx.bars[sym]
    a, b = atr_abs(d, int(p.get("a", 5))), atr_abs(d, int(p.get("b", 50)))
    return [x / y if (x == x and y == y and y > 0) else NAN for x, y in zip(a, b)]


def f_nr(ctx, sym, p):
    d = ctx.bars[sym]
    rg = [h - l for h, l in zip(d["h"], d["l"])]
    mn = roll_min(rg, int(p.get("n", 7)))
    return [(1.0 if r <= m else 0.0) if m == m else NAN for r, m in zip(rg, mn)]


def f_inside(ctx, sym, p):
    d = ctx.bars[sym]
    h, l = d["h"], d["l"]
    return [NAN] + [1.0 if (h[i] <= h[i - 1] and l[i] >= l[i - 1]) else 0.0 for i in range(1, len(h))]


def f_brk(ctx, sym, p):
    d = ctx.bars[sym]
    h, l, c = d["h"], d["l"], d["c"]
    return [NAN] + [1.0 if c[i] > h[i - 1] else (-1.0 if c[i] < l[i - 1] else 0.0) for i in range(1, len(c))]


def f_clv(ctx, sym, p):
    d = ctx.bars[sym]
    return [((2 * c - h - l) / (h - l)) if h > l else 0.0 for h, l, c in zip(d["h"], d["l"], d["c"])]


def f_body(ctx, sym, p):
    d = ctx.bars[sym]
    return [((c - o) / (h - l)) if h > l else 0.0 for o, h, l, c in zip(d["o"], d["h"], d["l"], d["c"])]


def f_streak(ctx, sym, p):
    c = ctx.bars[sym]["c"]
    out, s = [0.0] * len(c), 0
    for i in range(1, len(c)):
        if c[i] > c[i - 1]:
            s = s + 1 if s > 0 else 1
        elif c[i] < c[i - 1]:
            s = s - 1 if s < 0 else -1
        else:
            s = 0
        out[i] = float(s)
    return out


def f_gap(ctx, sym, p):
    d = ctx.bars[sym]
    return [NAN] + [d["o"][i] / d["c"][i - 1] - 1 for i in range(1, len(d["c"]))]


def f_intra(ctx, sym, p):
    d = ctx.bars[sym]
    return [c / o - 1 for o, c in zip(d["o"], d["c"])]


def f_dd(ctx, sym, p):
    c = ctx.bars[sym]["c"]
    mx = roll_max(c, int(p.get("n", 168)))
    return [x / m - 1 if m == m else NAN for x, m in zip(c, mx)]


def f_runup(ctx, sym, p):
    c = ctx.bars[sym]["c"]
    mn = roll_min(c, int(p.get("n", 168)))
    return [x / m - 1 if m == m else NAN for x, m in zip(c, mn)]


def f_rngpct(ctx, sym, p):
    d = ctx.bars[sym]
    return pct_rank([(h - l) / c for h, l, c in zip(d["h"], d["l"], d["c"])], int(p.get("lb", 100)))


def f_rvpct(ctx, sym, p):
    c = ctx.bars[sym]["c"]
    return pct_rank(roll_std(_ret(c, 1), int(p.get("n", 24))), int(p.get("lb", 500)))


def f_volz(ctx, sym, p):
    """Volume of this bar over the mean volume of the previous n bars."""
    v = ctx.bars[sym]["v"]
    base = shift(roll_mean(v, int(p.get("n", 24))), 1)
    return [x / b if (b == b and b > 0) else NAN for x, b in zip(v, base)]


def _imbalance(d):
    return [(2 * tb / v - 1) if v > 0 else 0.0 for v, tb in zip(d["v"], d["tb"])]


def f_taker(ctx, sym, p):
    return roll_mean(_imbalance(ctx.bars[sym]), int(p.get("n", 1)))


def f_takerz(ctx, sym, p):
    n, lb = int(p.get("n", 1)), int(p.get("lb", 168))
    im = _imbalance(ctx.bars[sym])
    m_n, m_lb, sd = roll_mean(im, n), roll_mean(im, lb), roll_std(im, lb)
    sq = math.sqrt(n)
    return [(a - b) / (s / sq) if (a == a and b == b and s == s and s > 1e-12) else NAN for a, b, s in zip(m_n, m_lb, sd)]


def f_hour(ctx, sym, p):
    return [float((t // 3600) % 24) for t in ctx.bars[sym]["ts"]]


def f_dow(ctx, sym, p):
    return [float((t // 86400 + 3) % 7) for t in ctx.bars[sym]["ts"]]       # Monday = 0


def f_dom(ctx, sym, p):
    return [float(time.gmtime(t).tm_mday) for t in ctx.bars[sym]["ts"]]


def _fundlast(d):
    out, last = [], 0.0
    for f in d["fund"]:
        if f != 0.0:
            last = f
        out.append(last)
    return out


def f_fundlast(ctx, sym, p):
    return _fundlast(ctx.bars[sym])


def f_fsum(ctx, sym, p):
    return roll_sum(ctx.bars[sym]["fund"], int(p.get("n", 24)))


def _z(x, n):
    m, s = roll_mean(x, n), roll_std(x, n)
    return [(v - a) / b if (v == v and a == a and b == b and b > 1e-15) else NAN for v, a, b in zip(x, m, s)]


def f_fz(ctx, sym, p):
    return _z(_fundlast(ctx.bars[sym]), int(p.get("n", 720)))


def f_prem(ctx, sym, p):
    pr = ctx.bars[sym].get("prem")
    return list(pr) if pr is not None else [NAN] * len(ctx.bars[sym]["ts"])


def f_premz(ctx, sym, p):
    return _z(f_prem(ctx, sym, p), int(p.get("n", 168)))


def _aligned_close(ctx, sym, ref):
    """Close of the reference asset at this symbol's timestamps (NaN where the reference has no bar)."""
    r = ctx.bars[ref]
    by = dict(zip(r["ts"], r["c"]))
    return [by.get(t, NAN) for t in ctx.bars[sym]["ts"]]


def f_xret(ctx, sym, p):
    return _ret(_aligned_close(ctx, sym, p["ref"]), int(p.get("n", 1)))


def f_xzret(ctx, sym, p):
    n, vn = int(p.get("n", 1)), int(p.get("vol_n", 100))
    rc = _aligned_close(ctx, sym, p["ref"])
    sd = roll_std(_ret(rc, 1), vn)
    r = _ret(rc, n)
    sq = math.sqrt(n)
    return [x / (s * sq) if (x == x and s == s and s > 1e-12) else NAN for x, s in zip(r, sd)]


def f_rel(ctx, sym, p):
    n = int(p.get("n", 24))
    own, ref = _ret(ctx.bars[sym]["c"], n), _ret(_aligned_close(ctx, sym, p["ref"]), n)
    return [a - b if (a == a and b == b) else NAN for a, b in zip(own, ref)]


def f_ratio_mom(ctx, sym, p):
    n = int(p.get("n", 72))
    c, rc = ctx.bars[sym]["c"], _aligned_close(ctx, sym, p["ref"])
    ratio = [a / b if (b == b and b > 0) else NAN for a, b in zip(c, rc)]
    out = [NAN] * len(c)
    for i in range(n, len(c)):
        if ratio[i] == ratio[i] and ratio[i - n] == ratio[i - n]:
            out[i] = ratio[i] / ratio[i - n] - 1
    return out


def f_sma_dist(ctx, sym, p):
    c = ctx.bars[sym]["c"]
    m = roll_mean(c, int(p.get("n", 200)))
    return [x / a - 1 if a == a else NAN for x, a in zip(c, m)]


def _by_day(d):
    """Index ranges of each UTC day: list of (start_idx, end_idx_exclusive)."""
    ts, out, a = d["ts"], [], 0
    for i in range(1, len(ts) + 1):
        if i == len(ts) or ts[i] // 86400 != ts[a] // 86400:
            out.append((a, i))
            a = i
    return out


def f_pd_sweep(ctx, sym, p):
    """Prior-UTC-day high/low sweep and reclaim: +1 when this bar's low is below the previous day's low but it closes back
    above it, -1 when its high is above the previous day's high but it closes back below, else 0."""
    d = ctx.bars[sym]
    h, l, c = d["h"], d["l"], d["c"]
    out = [0.0] * len(c)
    days = _by_day(d)
    for j in range(1, len(days)):
        a, b = days[j - 1]
        ph, pl = max(h[a:b]), min(l[a:b])
        for i in range(*days[j]):
            if l[i] < pl and c[i] > pl:
                out[i] = 1.0
            elif h[i] > ph and c[i] < ph:
                out[i] = -1.0
    if days:
        for i in range(*days[0]):
            out[i] = NAN
    return out


def f_asia_sweep(ctx, sym, p):
    """Asia range (UTC hours 0..7 of the day, known from hour 8): from hour 8 to 15 +1 when a bar's low is below the Asia low
    and it closes back above it, -1 for the high side."""
    d = ctx.bars[sym]
    ts, h, l, c = d["ts"], d["h"], d["l"], d["c"]
    out = [0.0] * len(c)
    for a, b in _by_day(d):
        idx = [i for i in range(a, b) if (ts[i] // 3600) % 24 < 8]
        if not idx or (ts[idx[0]] // 3600) % 24 != 0:
            for i in range(a, b):
                out[i] = NAN
            continue
        ah, al = max(h[i] for i in idx), min(l[i] for i in idx)
        for i in range(a, b):
            hr = (ts[i] // 3600) % 24
            if 8 <= hr < 16:
                if l[i] < al and c[i] > al:
                    out[i] = 1.0
                elif h[i] > ah and c[i] < ah:
                    out[i] = -1.0
            elif hr < 8:
                out[i] = NAN
    return out


def f_orb(ctx, sym, p):
    """Opening-range breakout: the range of the first `hours` hours of the UTC day (known when they close); afterwards +1
    for a close above its high, -1 for a close below its low, else 0. NaN inside the range."""
    d = ctx.bars[sym]
    ts, h, l, c = d["ts"], d["h"], d["l"], d["c"]
    hours = int(p.get("hours", 4))
    out = [NAN] * len(c)
    for a, b in _by_day(d):
        rng = [i for i in range(a, b) if (ts[i] // 3600) % 24 < hours]
        if not rng or (ts[rng[0]] // 3600) % 24 != 0 or (ts[rng[-1]] // 3600) % 24 != hours - 1:
            continue
        oh, ol = max(h[i] for i in rng), min(l[i] for i in rng)
        for i in range(rng[-1] + 1, b):
            out[i] = 1.0 if c[i] > oh else (-1.0 if c[i] < ol else 0.0)
    return out


def f_rnd(ctx, sym, p):
    """Position of the close inside the grid of round numbers of size `step` (price units, or step as a fraction of the
    price's power of ten when `rel` is set): (c mod step) / step in [0, 1). Near 1 = just below a round number."""
    c = ctx.bars[sym]["c"]
    step = float(p["step"])
    return [(x % step) / step for x in c]


# name -> (function, sign). signed: the mirror (short) of "x > v" is "x < -v". sym: unchanged under mirror.
# none: no meaningful mirror (calendar, one-sided features): a short rule must list its own conditions.
FEATURES = {
    "ret": (f_ret, "signed"), "zret": (f_zret, "signed"), "atrp": (f_atrp, "sym"), "atr_ratio": (f_atr_ratio, "sym"),
    "nr": (f_nr, "sym"), "inside": (f_inside, "sym"), "brk": (f_brk, "signed"), "clv": (f_clv, "signed"),
    "body": (f_body, "signed"), "streak": (f_streak, "signed"), "gap": (f_gap, "signed"), "intra": (f_intra, "signed"),
    "dd": (f_dd, "none"), "runup": (f_runup, "none"), "rngpct": (f_rngpct, "sym"), "rvpct": (f_rvpct, "sym"),
    "volz": (f_volz, "sym"), "taker": (f_taker, "signed"), "takerz": (f_takerz, "signed"),
    "hour": (f_hour, "none"), "dow": (f_dow, "none"), "dom": (f_dom, "none"),
    "fundlast": (f_fundlast, "signed"), "fsum": (f_fsum, "signed"), "fz": (f_fz, "signed"),
    "prem": (f_prem, "signed"), "premz": (f_premz, "signed"),
    "xret": (f_xret, "signed"), "xzret": (f_xzret, "signed"), "rel": (f_rel, "signed"),
    "ratio_mom": (f_ratio_mom, "signed"), "sma_dist": (f_sma_dist, "signed"),
    "pd_sweep": (f_pd_sweep, "signed"), "asia_sweep": (f_asia_sweep, "signed"), "orb": (f_orb, "signed"),
    "rnd": (f_rnd, "none"),
}
NEEDS_REF = frozenset(("xret", "xzret", "rel", "ratio_mom"))
NEEDS_FUNDING = frozenset(("fundlast", "fsum", "fz"))
NEEDS_PREMIUM = frozenset(("prem", "premz"))


class Ctx:
    """Bars of every symbol of one data group plus a cache of computed feature series."""

    def __init__(self, bars):
        self.bars = bars
        self.cache = {}

    def series(self, sym, cond):
        name = cond["f"]
        p = {k: v for k, v in cond.items() if k not in RESERVED}
        key = (sym, name, tuple(sorted((k, str(v)) for k, v in p.items())))
        if key not in self.cache:
            self.cache[key] = FEATURES[name][0](self, sym, p)
        return self.cache[key]


def cond_op(cond):
    ops = [k for k in OPS if k in cond]
    if len(ops) != 1:
        raise ValueError(f"condition needs exactly one of {OPS}: {cond}")
    return ops[0]


def mirror_cond(cond):
    """The short-side twin of a long condition (see FEATURES for what is mirrorable)."""
    name = cond["f"]
    if name not in FEATURES:
        raise ValueError(f"unknown feature {name!r}")
    sign = FEATURES[name][1]
    if sign == "none":
        raise ValueError(f"feature {name!r} has no mirror: list the short conditions explicitly")
    if sign == "sym":
        return dict(cond)
    out = dict(cond)
    op = cond_op(cond)
    v = out.pop(op)
    if op == "between":
        out["between"] = [-v[1], -v[0]]
    else:
        flip = {"gt": "lt", "lt": "gt", "ge": "le", "le": "ge", "eq": "eq"}
        if op == "in":
            out["in"] = [-x for x in v]
        else:
            out[flip[op]] = -v
    return out


def cond_bools(series, cond):
    s = shift(series, int(cond.get("lag", 0)))
    op = cond_op(cond)
    t = cond[op]
    if op == "gt":
        return [x > t for x in s]
    if op == "lt":
        return [x < t for x in s]
    if op == "ge":
        return [x >= t for x in s]
    if op == "le":
        return [x <= t for x in s]
    if op == "eq":
        return [x == t for x in s]
    if op == "between":
        lo, hi = t
        return [lo <= x <= hi for x in s]
    tset = set(float(v) for v in t)
    return [x in tset for x in s]


def signal(ctx, sym, conds):
    """AND of all conditions as a list of bool; no conditions means never."""
    if not conds:
        return [False] * len(ctx.bars[sym]["ts"])
    out = None
    for c in conds:
        b = cond_bools(ctx.series(sym, c), c)
        out = b if out is None else [x and y for x, y in zip(out, b)]
    return out


def side_conditions(rule):
    """(long_conds, short_conds) of a rule; short may be 'mirror' (the long list mirrored) or None."""
    lg = rule.get("long")
    sh = rule.get("short")
    if sh == "mirror":
        if not lg:
            raise ValueError("short 'mirror' needs a long list")
        sh = [mirror_cond(c) for c in lg]
    return (lg or []), (sh or [])


# ------------------------------------------------------------------ costs
def make_cost_fn(rule):
    """cost_fn(symbol, entry_price, days_held) -> round-trip cost as a fraction of notional (spread/fee/slippage and, for
    xm, swap). Funding is separate (measured). The 2x stress adds this amount a second time."""
    cm = rule["cost"]
    model = cm["model"]
    if model == "perp":
        side = float(cm.get("fee", 0.0005)) + float(cm.get("slip", 0.0002))
        return lambda sym, px, days: 2 * side
    if model == "spot":
        side = float(cm.get("fee", 0.001)) + float(cm.get("slip", 0.0002))
        return lambda sym, px, days: 2 * side
    if model == "etf":
        from core import news_backtest as nb
        side = float(cm.get("per_side", nb.cost_per_side("etf")))
        return lambda sym, px, days: 2 * side
    if model == "xm":
        from core import broker_costs as bc
        acct = cm.get("account", "standard")
        return lambda sym, px, days: bc.xm_cfd_cost_fraction(sym, acct, px, nights=max(0.0, days))["round_trip"]
    raise ValueError(f"unknown cost model {model!r}")


# ------------------------------------------------------------------ simulation
def _price_at(d, pt):
    k = pt // 2
    return d["o"][k] if pt % 2 == 0 else d["c"][k]


def simulate_symbol(d, sym, long_sig, short_sig, rule, t_from, t_to, cost_fn):
    """Trades of one symbol: list of dicts {sym, side, t (signal bar ts), te (entry ts), x (exit bar ts), ep, xp, gross, cost, fund, net,
    mfe, mae, reason}. Signals only inside [t_from, t_to); one open trade per symbol at a time."""
    ts, o, h, l, c = d["ts"], d["o"], d["h"], d["l"], d["c"]
    n = len(ts)
    ex = rule["exit"]
    hold = int(ex["time"])
    exit_on = ex.get("on", "same")
    close_entry = rule.get("entry", "next_open") == "close"
    stop, target, trail = ex.get("stop"), ex.get("target"), ex.get("trail")
    atr = atr_abs(d, int(ex.get("atr_n", 14))) if any(x and "atr" in x for x in (stop, target, trail)) else None
    fp = [0.0]
    for f in d["fund"]:
        fp.append(fp[-1] + f)
    out = []
    i = 0
    while i < n - 1:
        if ts[i] < t_from:
            i += 1
            continue
        if ts[i] >= t_to:
            break
        if long_sig[i] == short_sig[i]:
            i += 1
            continue
        s = 1 if long_sig[i] else -1
        p0 = 2 * i + 1 if close_entry else 2 * (i + 1)
        if p0 // 2 >= n:
            break
        ep = c[i] if close_entry else o[i + 1]
        same = exit_on == "same" or (exit_on == "open" and p0 % 2 == 0) or (exit_on == "close" and p0 % 2 == 1)
        px_pt = p0 + 2 * hold if same else p0 + 2 * hold - 1
        x_bar = px_pt // 2
        if x_bar >= n:
            break
        first = p0 // 2 if p0 % 2 == 0 else p0 // 2 + 1
        last = x_bar if px_pt % 2 == 1 else x_bar - 1

        def dist(spec):
            if spec is None:
                return None
            if "pct" in spec:
                return float(spec["pct"]) * ep
            a = atr[i]
            return float(spec["atr"]) * a if (a == a and a > 0) else NAN

        ds, dt, dtr = dist(stop), dist(target), dist(trail)
        if any(v is not None and v != v for v in (ds, dt, dtr)):
            i += 1
            continue
        level = ep - s * ds if ds is not None else (ep - s * dtr if dtr is not None else None)
        goal = ep + s * dt if dt is not None else None
        xp, reason, exit_bar, mfe, mae = None, "time", x_bar, 0.0, 0.0
        for k in range(first, last + 1):
            ok, hk, lk = o[k], h[k], l[k]
            if s > 0:
                fav, adv = hk / ep - 1, 1 - lk / ep
                if level is not None and lk <= level:
                    xp, reason = (ok if ok <= level else level), "stop"
                elif goal is not None and hk >= goal:
                    xp, reason = (ok if ok >= goal else goal), "target"
            else:
                fav, adv = 1 - lk / ep, hk / ep - 1
                if level is not None and hk >= level:
                    xp, reason = (ok if ok >= level else level), "stop"
                elif goal is not None and lk <= goal:
                    xp, reason = (ok if ok <= goal else goal), "target"
            mfe, mae = max(mfe, fav), max(mae, adv)
            if xp is not None:
                exit_bar = k
                break
            if dtr is not None:
                nl = hk - dtr if s > 0 else lk + dtr
                if level is None or (nl > level if s > 0 else nl < level):
                    level = nl
        if xp is None:
            xp = _price_at(d, px_pt)
            ex_pt = px_pt
            end_k = last
        else:
            ex_pt = 2 * exit_bar + 1
            end_k = exit_bar
        days = (ts[exit_bar] - ts[i]) / 86400.0
        cost = cost_fn(sym, ep, days)
        fcost = s * (fp[end_k + 1] - fp[first]) if end_k >= first else 0.0
        gross = s * (xp / ep - 1)
        out.append({"sym": sym, "side": s, "t": ts[i], "te": ts[i] if close_entry else ts[i + 1], "x": ts[exit_bar], "ep": ep, "xp": xp, "gross": gross,
                    "cost": cost, "fund": fcost, "net": gross - cost - fcost, "mfe": mfe, "mae": mae, "reason": reason})
        j = (ex_pt // 2) if close_entry else ((ex_pt + 1) // 2 - 1)
        i = max(i + 1, j)
    return out


def apply_cap(trades, k):
    """At most k trades open at once across symbols, earliest entry first (ties by symbol); a slot frees at the exit time."""
    keep, open_x = [], []
    for tr in sorted(trades, key=lambda z: (z["te"], z["sym"])):
        open_x = [x for x in open_x if x > tr["te"]]
        if len(open_x) < k:
            keep.append(tr)
            open_x.append(tr["x"])
    return keep


def rule_trades(ctx, rule, symbols, t_from, t_to):
    """All capped trades of a rule over its symbols."""
    lg, sh = side_conditions(rule)
    cost_fn = make_cost_fn(rule)
    allt = []
    for sym in symbols:
        d = ctx.bars[sym]
        ls, ss = signal(ctx, sym, lg), signal(ctx, sym, sh)
        allt.extend(simulate_symbol(d, sym, ls, ss, rule, t_from, t_to, cost_fn))
    return apply_cap(allt, int(rule["size"].get("k", 1)))
