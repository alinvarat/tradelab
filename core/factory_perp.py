"""Idea factory batch 2 (`factory_crypto_2`, pre-registered in research/studies/RESULTS.md): rules on Binance USDT-M
perpetuals with MEASURED funding instead of factory.FUNDING_DAY.

Pure functions only (no network): parsers for the data.binance.vision CSVs and Deribit DVOL pages, a funding lookup,
the daily perp features, a daily runner with measured funding and the vanished-coin rule, the A1-A5 daily books,
the A6 hour-of-day book and the A7 cointegrated pairs on an hourly panel. Batch 1 (`core/factory.py`) and its
registry are untouched: these rules live in PERP_RULES so batch 1's Bonferroni bar does not change.
Simulated research only."""
import bisect
import math
import random
import time
from array import array
from statistics import mean, median, pstdev

from core import factory as fa

ONE_WAY_COST = fa.ONE_WAY_COST
DAY = 86400
HOUR = 3600
HOURLY_QV = 5e6               # A6/A7 daily average quote volume floor (USDT)
BENCH = "BTCUSDT"
NAN = float("nan")


# ------------------------------------------------------------------ symbols and parsers
def base_of(sym: str) -> str:
    """Base asset of a USDT perp with a leading 1000000 / 1000 multiplier stripped (1000PEPEUSDT -> PEPE)."""
    b = sym[:-4] if sym.endswith("USDT") else sym
    for p in ("1000000", "1000"):
        if b.startswith(p) and len(b) > len(p):
            return b[len(p):]
    return b


def eligible_symbol(sym: str, skip=()) -> bool:
    """USDT-quoted perpetual (no '_' = no quarterly contract) whose base is not on the skip list."""
    return sym.endswith("USDT") and "_" not in sym and base_of(sym) not in skip


def _sec(t: int) -> float:
    """Epoch milliseconds or microseconds (files from 2025 on) -> seconds."""
    return t / 1_000_000 if t > 10**14 else t / 1000


def parse_kline_csv(text: str) -> list:
    """Binance kline CSV -> [(open_ts_s, o, h, l, c, quote_vol, taker_buy_quote_vol)]; header lines are skipped."""
    out = []
    for line in text.splitlines():
        f = line.split(",")
        if len(f) > 10 and f[0].strip().isdigit():
            out.append((int(_sec(int(f[0]))), float(f[1]), float(f[2]), float(f[3]), float(f[4]),
                        float(f[7]), float(f[10])))
    return out


def parse_funding_csv(text: str) -> list:
    """Binance fundingRate CSV -> [(settle_ts_s, rate)], timestamps rounded to the nearest minute so millisecond
    jitter cannot move a 00:00 settlement into the next window."""
    out = []
    for line in text.splitlines():
        f = line.split(",")
        if len(f) >= 2 and f[0].strip().isdigit():
            out.append((int(round(_sec(int(f[0])) / 60.0)) * 60, float(f[-1])))
    return out


def parse_dvol_pages(pages: list) -> list:
    """Deribit get_volatility_index_data responses -> sorted unique [(ts_s, close)]."""
    seen = {}
    for p in pages:
        for row in ((p or {}).get("result") or {}).get("data") or []:
            seen[int(row[0]) // 1000] = float(row[4])
    return sorted(seen.items())


def ym(ts: float) -> str:
    return time.strftime("%Y-%m", time.gmtime(ts))


def months_between(a: float, b: float) -> list:
    """Calendar months ('YYYY-MM') touched by the half-open window (a, b]."""
    g0, g1 = time.gmtime(a + 1), time.gmtime(b)
    y, m, out = g0.tm_year, g0.tm_mon, []
    while (y, m) <= (g1.tm_year, g1.tm_mon):
        out.append(f"{y}-{m:02d}")
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


# ------------------------------------------------------------------ funding
class Funding:
    """Settled funding per symbol with half-open window sums (a, b] and a coin-month gap gate."""

    def __init__(self, rows: dict, bad_months=()):
        self.ts, self.cum = {}, {}
        for s, rs in rows.items():
            rs = sorted(rs)
            self.ts[s] = [t for t, _ in rs]
            c = [0.0]
            for _, r in rs:
                c.append(c[-1] + r)
            self.cum[s] = c
        self.bad = set(bad_months)          # {(sym, 'YYYY-MM')}

    def _idx(self, s, a, b):
        ts = self.ts.get(s)
        if not ts:
            return 0, 0
        return bisect.bisect_right(ts, a), bisect.bisect_right(ts, b)

    def sum(self, s, a, b) -> float:
        i, j = self._idx(s, a, b)
        return self.cum[s][j] - self.cum[s][i] if j > i else 0.0

    def count(self, s, a, b) -> int:
        i, j = self._idx(s, a, b)
        return j - i

    def ok(self, s, a, b) -> bool:
        """False when any month touched by (a, b] is a funding gap for s."""
        return not any((s, k) in self.bad for k in months_between(a, b))

    def settle_hours(self, h0: int, n: int) -> set:
        """Hour indices k whose window (h0+3600k, h0+3600(k+1)] holds any settlement."""
        out = set()
        for ts in self.ts.values():
            for t in ts:
                k = math.ceil((t - h0) / HOUR) - 1
                if 0 <= k < n:
                    out.add(k)
        return out


# ------------------------------------------------------------------ daily panel
def panel_perp(bars: dict) -> tuple:
    """bars {sym: [(ts, o, h, l, c, qv, taker_qv)]} -> (days, close, qv, taker) via factory.panel."""
    days, close, qv = fa.panel({s: [r[:6] for r in rows] for s, rows in bars.items()})
    taker = {}
    for s, rows in bars.items():
        for r in rows:
            taker.setdefault(r[0], {})[s] = r[6]
    return days, close, qv, taker


def perp_features(days, close, qv, taker, funding: Funding, bench=BENCH) -> list:
    """factory.features plus, per coin and day i (decision time T = days[i] + 1 day), using data up to T only:
    fund7 (average daily settled funding in (T-7d, T], None without settlements), z_imb (taker imbalance z-score
    against the coin's previous 30 bars), beta60 / e1 / e3 (60-day BTC beta and beta-removed 1/3-day returns).
    Coins whose funding windows touch a gap month are dropped."""
    base = fa.features(days, close, qv, bench)
    imb_h, ret_h, out = {}, {}, []
    rb = [None] * len(days)
    for i, d in enumerate(days):
        if i and bench in close[d] and bench in close[days[i - 1]]:
            rb[i] = close[d][bench] / close[days[i - 1]][bench] - 1
        for s, c in close[d].items():
            q = qv[d][s]
            tq = taker.get(d, {}).get(s)
            h = imb_h.setdefault(s, [])
            h.append(2 * tq / q - 1 if q and tq is not None else None)
            if len(h) > 31:
                h.pop(0)
            if i and s in close[days[i - 1]] and close[days[i - 1]][s]:
                r = ret_h.setdefault(s, [])
                r.append((i, c / close[days[i - 1]][s] - 1))
                if len(r) > 60:
                    r.pop(0)
        T = d + DAY
        b3 = None
        if i >= 3 and bench in close[d] and bench in close[days[i - 3]]:
            b3 = close[d][bench] / close[days[i - 3]][bench] - 1
        f = {}
        for s, v in base[i].items():
            if not funding.ok(s, T - 7 * DAY, T + DAY):
                continue
            v = dict(v)
            n7 = funding.count(s, T - 7 * DAY, T)
            v["fund7"] = funding.sum(s, T - 7 * DAY, T) / 7 if n7 else None
            h = imb_h.get(s, [])
            v["z_imb"] = None
            if len(h) == 31 and None not in h:
                prev = h[:-1]
                sd = pstdev(prev)
                if sd > 0:
                    v["z_imb"] = (h[-1] - mean(prev)) / sd
            v["beta60"] = v["e1"] = v["e3"] = None
            r = ret_h.get(s, [])
            if len(r) == 60 and r[0][0] == i - 59 and r[-1][0] == i and b3 is not None:
                xs = [rb[k] for k, _ in r]
                if None not in xs:
                    ys = [y for _, y in r]
                    mx, my = mean(xs), mean(ys)
                    vx = sum((x - mx) ** 2 for x in xs)
                    if vx > 0:
                        beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx
                        v["beta60"] = beta
                        v["e1"] = v["r1"] - beta * rb[i]
                        v["e3"] = v["r3"] - beta * b3
            f[s] = v
        out.append(f)
    return out


def daily_adv(days, qv, n=20) -> list:
    """adv[i][sym] = mean quote volume over calendar days i-n..i-1 (all n must exist): known at day i's open."""
    hist, out = {}, []
    for i, d in enumerate(days):
        a = {}
        for s, h in hist.items():
            if len(h) == n and h[0][0] == i - n and h[-1][0] == i - 1:
                a[s] = math.fsum(q for _, q in h) / n
        out.append(a)
        for s, q in qv[d].items():
            h = hist.setdefault(s, [])
            h.append((i, q))
            if len(h) > n:
                h.pop(0)
    return out


# ------------------------------------------------------------------ daily runner
def run_perp(days, close, feats, strat, funding: Funding, bench=BENCH, hedge=True, cost_mult=1.0, stats=None) -> list:
    """Daily net returns [(ts, r)]: weights set at day i's close (T) earn close(i) -> close(i+1) minus measured funding
    in (T, T+24h] (w * rate: a long pays positive funding). hedge: the net dollar exposure is offset with a BTC leg,
    which pays cost and funding like any position. Cost = cost_mult * ONE_WAY_COST per unit of turnover (funding is
    never scaled). A held coin without a close on day i+1 earns 0 and pays nothing (closed at its last close); its
    exit turnover is charged at the next rebalance. stats (dict) receives vanished counts and event days."""
    out, prev = [], {}
    st = stats if stats is not None else {}
    st.setdefault("vanished_long", 0)
    st.setdefault("vanished_short", 0)
    st.setdefault("event_ts", [])
    for i in range(len(days) - 1):
        w = dict(strat(feats[i], i))
        d0, d1 = days[i], days[i + 1]
        T = d0 + DAY
        if any(x for s, x in w.items() if s != bench):
            st["event_ts"].append(d1)
        if hedge:
            net = sum(w.values())
            if abs(net) > 1e-12:
                w[bench] = w.get(bench, 0.0) - net
        w = {s: x for s, x in w.items() if abs(x) > 1e-15}
        pnl = 0.0
        for s, x in w.items():
            r = fa._ret(close, d0, d1, s)
            if r is None:
                if s != bench and close[d0].get(s):
                    st["vanished_long" if x > 0 else "vanished_short"] += 1
                continue
            pnl += x * r - x * funding.sum(s, T, T + DAY)
        turnover = sum(abs(w.get(s, 0.0) - prev.get(s, 0.0)) for s in set(w) | set(prev))
        out.append((d1, pnl - cost_mult * turnover * ONE_WAY_COST))
        prev = w
    return out


# ------------------------------------------------------------------ A1-A5 books (builders return fresh state per run)
def a1_carry(ctx):
    def fn(f, i):
        g = {s: v for s, v in f.items() if v.get("fund7") is not None}
        return fa._ls(*fa._deciles(g, "fund7"), sign=-1)       # short the highest funding, long the lowest
    return fn


def absorption(f) -> dict:
    """Residual of a cross-sectional OLS of z_imb on r1 (with intercept), scaled by the residuals' pstdev."""
    pts = [(s, v["r1"], v["z_imb"]) for s, v in f.items() if v.get("z_imb") is not None]
    if len(pts) < 3:
        return {}
    mx, my = mean(p[1] for p in pts), mean(p[2] for p in pts)
    sxx = sum((p[1] - mx) ** 2 for p in pts)
    b = sum((p[1] - mx) * (p[2] - my) for p in pts) / sxx if sxx > 0 else 0.0
    a = my - b * mx
    res = {s: z - (a + b * x) for s, x, z in pts}
    sd = pstdev(res.values())
    return {s: e / sd for s, e in res.items()} if sd > 0 else {}


def a2_absorption(ctx):
    state = {"prev": {}}
    days, close, funding = ctx["days"], ctx["close"], ctx["funding"]

    def fn(f, i):
        ab = absorption(f)
        book = fa._ls(*fa._deciles({s: {"ab": x} for s, x in ab.items()}, "ab"), sign=-1)
        T = days[i] + DAY
        prev = {s: x for s, x in state["prev"].items()
                if close[days[i]].get(s) and funding.ok(s, T, T + DAY)}
        state["prev"] = book
        w = {}
        for src in (book, prev):
            for s, x in src.items():
                w[s] = w.get(s, 0.0) + 0.5 * x
        return {s: x for s, x in w.items() if abs(x) > 1e-15}
    return fn


def rv_regime(days, btc_rows, win=30, look=365) -> list:
    """Per panel day: BTC 30-day realised vol (pstdev of the 30 daily returns ending that day) / median of that series
    over the previous 365 days; None until 365 prior values exist. btc_rows [(ts, ..., c, ...)] may start earlier
    than the panel."""
    rows = sorted((r[0], r[4]) for r in btc_rows)
    rets = [None] + [rows[k][1] / rows[k - 1][1] - 1 for k in range(1, len(rows))]
    vol = [None] * len(rows)
    for k in range(win, len(rows)):
        vol[k] = pstdev(rets[k - win + 1:k + 1])
    by_ts = {}
    for k in range(win + look, len(rows)):
        prev = vol[k - look:k]
        if None not in prev:
            m = median(prev)
            by_ts[rows[k][0]] = vol[k] / m if m > 0 else None
    return [by_ts.get(d) for d in days]


def dvol_regime(days, dvol, look=365, period=DAY) -> list:
    """Per panel day i (known at T = days[i] + 1 day): close of the latest DVOL candle whose period has ended by T,
    divided by the median of the previous 365 candle closes; None before that."""
    dvol = sorted(dvol)
    ends = [t + period for t, _ in dvol]
    out = []
    for d in days:
        j = bisect.bisect_right(ends, d + DAY) - 1
        if j < look:
            out.append(None)
            continue
        m = median(c for _, c in dvol[j - look:j])
        out.append(dvol[j][1] / m if m > 0 else None)
    return out


def regime_book(regime, low=0.9, high=1.3):
    mom, rev = fa.STRATEGIES["xs_momentum_r7"], fa.STRATEGIES["xs_reversal_r3"]

    def fn(f, i):
        r = regime[i]
        if r is None:
            return {}
        if r < low:
            return mom(f, i)
        if r > high:
            return rev(f, i)
        return {}
    return fn


def pct_ranks(vals: dict) -> dict:
    """Cross-sectional percentile ranks in [0, 1] (ties get their average rank)."""
    items = sorted(vals.items(), key=lambda kv: kv[1])
    n, out, k = len(items), {}, 0
    if n == 1:
        return {items[0][0]: 0.5}
    while k < n:
        j = k
        while j + 1 < n and items[j + 1][1] == items[k][1]:
            j += 1
        r = (k + j) / 2 / (n - 1)
        for q in range(k, j + 1):
            out[items[q][0]] = r
        k = j + 1
    return out


A5_KEYS = ("e1", "e3", "qv_ratio", "vol30")


def a5_ranks(f) -> dict:
    """{key: {sym: rank of -value}} over coins with age >= 60 and a beta60."""
    g = {s: v for s, v in f.items() if v.get("beta60") is not None and v["age"] >= 60}
    return {k: pct_ranks({s: -v[k] for s, v in g.items()}) for k in A5_KEYS}


def a5_score(f) -> dict:
    rk = a5_ranks(f)
    syms = rk["e1"].keys()
    return {s: mean(rk[k][s] for k in A5_KEYS) for s in syms}


def beta_neutral(longs, shorts, beta, bench=BENCH) -> dict:
    """Equal weight within a side, side grosses gL = Bs/(Bl+Bs), gS = Bl/(Bl+Bs) so sum w*beta = 0 at gross 1;
    0.5/0.5 when a side's mean beta <= 0, then a BTC leg of -sum(w*beta) covers any residual."""
    if not longs or not shorts:
        return {}
    bl, bs = mean(beta[s] for s in longs), mean(beta[s] for s in shorts)
    gl, gs = (bs / (bl + bs), bl / (bl + bs)) if bl > 0 and bs > 0 else (0.5, 0.5)
    w = {s: gl / len(longs) for s in longs}
    w.update({s: -gs / len(shorts) for s in shorts})
    res = sum(x * beta[s] for s, x in w.items())
    if abs(res) > 1e-12:
        w[bench] = w.get(bench, 0.0) - res
    return w


def a5_ensemble(ctx, frac=0.1, keep=0.3, k_min=5):
    state = {"L": set(), "S": set()}

    def fn(f, i):
        sc = a5_score(f)
        n = len(sc)
        if n < 2 * k_min:
            state["L"], state["S"] = set(), set()
            return {}
        order = sorted(sc, key=lambda s: (-sc[s], s))
        k = max(k_min, int(n * frac))
        k30 = max(k, int(n * keep))
        top, bot = set(order[:k]), set(order[-k:])
        top30, bot30 = set(order[:k30]), set(order[-k30:])
        L = (state["L"] & top30) | top
        S = ((state["S"] & bot30) | bot) - L
        state["L"], state["S"] = L, S
        return beta_neutral(sorted(L), sorted(S), {s: f[s]["beta60"] for s in L | S})
    return fn


def a5_component(key):
    """Descriptive single-rank book: long the top 10% by rank(-key), short the bottom 10%, dollar-hedged."""
    def build(ctx):
        def fn(f, i):
            rk = a5_ranks(f)[key]
            return fa._ls(*fa._deciles({s: {"x": x} for s, x in rk.items()}, "x"))
        return fn
    return build


def random_control(builder, seed):
    """Same number of names per side as the rule each day, drawn by seed from the eligible set, 0.5 gross a side."""
    def build(ctx):
        inner, rng = builder(ctx), random.Random(seed)

        def fn(f, i):
            w = inner(f, i)
            nl = sum(1 for s, x in w.items() if x > 0 and s != BENCH)
            ns = sum(1 for s, x in w.items() if x < 0 and s != BENCH)
            pool = sorted(f)
            if nl + ns == 0 or nl + ns > len(pool):
                return {}
            pick = rng.sample(pool, nl + ns)
            out = {s: 0.5 / nl for s in pick[:nl]}
            out.update({s: -0.5 / ns for s in pick[nl:]})
            return out
        return fn
    return build


PERP_RULES = {            # name -> (builder(ctx) -> fn(f, i), dollar hedge with BTC)
    "A1_carry_funding_7d": (a1_carry, True),
    "A2_taker_absorption": (a2_absorption, True),
    "A3_vol_regime_switch_rv": (lambda ctx: regime_book(ctx["regime_rv"]), True),
    "A4_vol_regime_switch_dvol": (lambda ctx: regime_book(ctx["regime_dvol"]), True),
    "A5_residual_reversal_ensemble": (a5_ensemble, False),
}
HOURLY_RULES = ("A6_hour_of_day_xs", "A7_coint_pairs_hourly")
ALL_RULES = tuple(PERP_RULES) + HOURLY_RULES


def descriptive_daily() -> dict:
    """Books that are reported but cannot pass (judged in a separate call)."""
    d = {"A3_parent_xs_momentum_r7": (lambda ctx: fa.STRATEGIES["xs_momentum_r7"], True),
         "A3_parent_xs_reversal_r3": (lambda ctx: fa.STRATEGIES["xs_reversal_r3"], True)}
    for k in A5_KEYS:
        d[f"A5_component_rank_neg_{k}"] = (a5_component(k), True)
    for j, (name, (b, hedge)) in enumerate(PERP_RULES.items()):
        d[f"{name}_random_control"] = (random_control(b, 20261125 + j), True)
    return d


# ------------------------------------------------------------------ hourly panel
def hourly_array(rows, h0: int, n: int) -> array:
    """Hourly closes indexed by (open_ts - h0) // 3600, NaN where there is no bar."""
    a = array("d", [NAN]) * n
    for r in rows:
        k = (r[0] - h0) // HOUR
        if 0 <= k < n:
            a[k] = r[4]
    return a


def _ok(x) -> bool:
    return x == x and x > 0


def same_hour_cumsum(c: array) -> tuple:
    """cs[t] = sum of the valid close-to-close returns at t, t-24, t-48, ...; cnt the number of them."""
    n = len(c)
    cs, cnt = array("d", [0.0]) * n, array("l", [0]) * n
    for t in range(1, n):
        a, b = c[t - 1], c[t]
        v, k = (b / a - 1, 1) if _ok(a) and _ok(b) else (0.0, 0)
        if t >= 24:
            cs[t], cnt[t] = cs[t - 24] + v, cnt[t - 24] + k
        else:
            cs[t], cnt[t] = v, k
    return cs, cnt


def same_hour_score(cs, cnt, t_ref: int, n_days=20):
    """Mean of the returns at clock hour t_ref on the n_days previous days (t_ref - 24k, k = 1..n_days);
    None unless all n_days exist. The day of t_ref is never used."""
    hi, lo = t_ref - 24, t_ref - 24 * (n_days + 1)
    if hi < 0:
        return None
    s, k = cs[hi] - (cs[lo] if lo >= 0 else 0.0), cnt[hi] - (cnt[lo] if lo >= 0 else 0)
    return s / n_days if k == n_days else None


def compound_days(pnl: dict, turn: dict, h0: int, day_starts, cost_mult=1.0) -> list:
    """Hourly P&L and turnover (keyed by hour index) -> [(day_ts, compounded net return)], 0 on idle days."""
    hours = sorted(set(pnl) | set(turn))
    by = {}
    for t in hours:
        d = h0 + (t * HOUR) // DAY * DAY
        r = pnl.get(t, 0.0) - cost_mult * ONE_WAY_COST * turn.get(t, 0.0)
        by[d] = by.get(d, 1.0) * (1 + r)
    return [(d, by.get(d, 1.0) - 1) for d in day_starts]


def run_hour_of_day(hc: dict, prep: dict, adv_at: dict, funding: Funding, h0: int, n: int, settle: set,
                    placebo=False, gate=0.008, min_adv=HOURLY_QV, bench=BENCH, frac=0.1, k_min=5) -> tuple:
    """A6. For each hour t (clock hour H of day D): eligible coins have adv_at[D] >= min_adv, no funding gap in the
    month, a close at t-1 (entry) and a full 20-day same-hour score (clock hour H, or H+12 for the placebo). Trade the
    top/bottom 10% when the score spread >= gate. Returns (pnl, turn, stats) keyed by hour index."""
    pnl, turn, prev = {}, {}, {}
    st = {"traded_hour_ts": [], "vanished_long": 0, "vanished_short": 0}
    for t in range(1, n):
        ts = h0 + t * HOUR
        D = ts - ts % DAY
        H = (ts - D) // HOUR
        t_ref = t if not placebo else (D - h0) // HOUR + (H + 12) % 24
        month = ym(ts)
        sc = {}
        for s, a in adv_at.get(D, {}).items():
            if a < min_adv or s == bench or s not in hc or (s, month) in funding.bad or not _ok(hc[s][t - 1]):
                continue
            x = same_hour_score(prep[s][0], prep[s][1], t_ref)
            if x is not None:
                sc[s] = {"x": x}
        w = {}
        top, bot = fa._deciles(sc, "x", frac, k_min)
        if top and mean(sc[s]["x"] for s in top) - mean(sc[s]["x"] for s in bot) >= gate:
            w = fa._ls(top, bot)
            st["traded_hour_ts"].append(ts)
            net = sum(w.values())
            if abs(net) > 1e-12:
                w[bench] = w.get(bench, 0.0) - net
        p = 0.0
        for s, x in w.items():
            c0, c1 = hc[s][t - 1], hc[s][t]
            if not (_ok(c0) and _ok(c1)):
                if s != bench:
                    st["vanished_long" if x > 0 else "vanished_short"] += 1
                continue
            p += x * (c1 / c0 - 1)
            if t in settle:
                p -= x * funding.sum(s, ts, ts + HOUR)
        tv = sum(abs(w.get(s, 0.0) - prev.get(s, 0.0)) for s in set(w) | set(prev))
        if w or tv:
            pnl[t], turn[t] = p, tv
        prev = w
    return pnl, turn, st


# ------------------------------------------------------------------ A7 cointegrated pairs
def ols(x, y) -> tuple:
    """(intercept, slope) of y on x; slope None when x has no variance."""
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)     # fsum: statistics.mean is slow in the pair loop
    vx = sum((a - mx) ** 2 for a in x)
    if vx <= 0:
        return my, None
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / vx
    return my - b * mx, b


def df_stat(e) -> tuple:
    """Dickey-Fuller without lag or constant on residuals: de_t = g * e_{t-1} + u -> (g, t_g)."""
    lag, de = e[:-1], [e[k] - e[k - 1] for k in range(1, len(e))]
    sxx = sum(x * x for x in lag)
    if sxx <= 0:
        return 0.0, 0.0
    g = sum(x * y for x, y in zip(lag, de)) / sxx
    ssr = sum((y - g * x) ** 2 for x, y in zip(lag, de))
    s2 = ssr / (len(de) - 1)
    se = math.sqrt(s2 / sxx) if s2 > 0 else 0.0
    return g, (g / se if se > 0 else -math.inf)


def half_life(g) -> float:
    return -math.log(2) / math.log(1 + g) if -1 < g < 0 else math.inf


def pair_fit(la, lb) -> dict:
    a, b = ols(lb, la)
    if b is None:
        return None
    e = [y - a - b * x for x, y in zip(lb, la)]
    g, tg = df_stat(e)
    return {"b": b, "g": g, "t": tg, "hl": half_life(g)}


def select_universe(qv30: dict, full: set, n=40, floor=HOURLY_QV, always=("ETHUSDT", "BTCUSDT")) -> list:
    """The n coins (other than `always`) with the highest 30-day quote volume >= floor and full hourly history,
    plus the `always` coins when they have full history."""
    pool = sorted((s for s in qv30 if s in full and qv30[s] >= floor and s not in always), key=lambda s: (-qv30[s], s))
    return pool[:n] + [s for s in always if s in full]


def form_pairs(logs: dict, qv30: dict, n_pairs=20, cap=3, tcrit=-3.90, hl=(4, 72),
               anchor=("ETHUSDT", "BTCUSDT")) -> list:
    """Engle-Granger screen over every pair of `logs` ({sym: log closes}). B = higher 30-day volume, A = the other.
    The anchor pair always enters first (bypassing the test); the rest are filled by the most negative t_g with each
    coin in at most `cap` pairs. -> [{'A','B','b','t','hl'}] in trading priority order."""
    syms = sorted(logs)

    def orient(x, y):
        return (y, x) if (qv30.get(x, 0), x) > (qv30.get(y, 0), y) else (x, y)   # -> (A, B), B more liquid
    cands = []
    anchor_pair = None
    for i, x in enumerate(syms):
        for y in syms[i + 1:]:
            A, B = orient(x, y)
            fit = pair_fit(logs[A], logs[B])
            if fit is None:
                continue
            row = {"A": A, "B": B, **fit}
            if {A, B} == set(anchor):
                anchor_pair = row
            elif fit["t"] <= tcrit and hl[0] <= fit["hl"] <= hl[1]:
                cands.append(row)
    out, uses = [], {}
    if anchor_pair:
        out.append(anchor_pair)
        for s in (anchor_pair["A"], anchor_pair["B"]):
            uses[s] = uses.get(s, 0) + 1
    for row in sorted(cands, key=lambda r: (r["t"], r["A"], r["B"])):
        if len(out) >= n_pairs:
            break
        if uses.get(row["A"], 0) < cap and uses.get(row["B"], 0) < cap:
            out.append(row)
            uses[row["A"]] = uses.get(row["A"], 0) + 1
            uses[row["B"]] = uses.get(row["B"], 0) + 1
    return out


def pair_z(ca: array, cb: array, b: float, m0: int, m1: int, win=168) -> list:
    """z of s = log A - b log B over the last `win` closed hours (inclusive) for t in [m0, m1); None when a close in
    the window is missing."""
    lo = max(0, m0 - win + 1)
    s = [math.log(ca[t]) - b * math.log(cb[t]) if _ok(ca[t]) and _ok(cb[t]) else None for t in range(lo, m1)]
    ref = next((x for x in s if x is not None), 0.0)          # shift for numerically stable rolling sums
    sm = sq = 0.0
    bad = 0
    out = []
    for k, x in enumerate(s):
        if x is None:
            bad += 1
        else:
            sm += x - ref
            sq += (x - ref) ** 2
        if k >= win:
            y = s[k - win]
            if y is None:
                bad -= 1
            else:
                sm -= y - ref
                sq -= (y - ref) ** 2
        if k + lo < m0:
            continue
        if k + 1 < win or bad:
            out.append(None)
            continue
        mu = sm / win
        var = sq / win - mu * mu
        sd = math.sqrt(var) if var > 0 else 0.0
        out.append((x - ref - mu) / sd if sd > 1e-6 else None)    # flat spread: no z
    return out


def a7_schedule(hc: dict, months: list, entry=2.5, stop=4.5, max_hold=72, max_open=6, win=168) -> list:
    """months: [(m0, m1, pairs)] with hour index range [m0, m1). Signals at the close of hour t trade at the next open
    (positions earn from hour t+1). Exits: z crosses or touches 0, held >= max_hold hours, |z| >= stop, the month's
    last hour, or a leg without a bar (closed at the previous close). No re-entry in the hour of an exit.
    -> trades [{'A','B','b','sign','et','xt','month'}] where sign is the position in s (+1 long A / short b*B)."""
    trades = []
    for mi, (m0, m1, pairs) in enumerate(months):
        zs = [pair_z(hc[p["A"]], hc[p["B"]], p["b"], m0, m1, win) for p in pairs]
        open_ = {}
        for t in range(m0, m1):
            just_closed = set()
            for j in sorted(open_):
                et, sign = open_[j]
                p = pairs[j]
                if not (_ok(hc[p["A"]][t]) and _ok(hc[p["B"]][t])):
                    trades.append({**_leg(p), "sign": sign, "et": et, "xt": t - 1, "month": mi})
                    del open_[j]
                    just_closed.add(j)
                    continue
                z = zs[j][t - m0]
                if (z is not None and (z * -sign <= 0 or abs(z) >= stop)) or t - et >= max_hold or t == m1 - 1:
                    trades.append({**_leg(p), "sign": sign, "et": et, "xt": t, "month": mi})
                    del open_[j]
                    just_closed.add(j)
            if t == m1 - 1:
                continue
            for j, p in enumerate(pairs):
                if len(open_) >= max_open:
                    break
                if j in open_ or j in just_closed:
                    continue
                z = zs[j][t - m0]
                if z is not None and entry <= abs(z) < stop:
                    open_[j] = (t, -1 if z > 0 else 1)
    return trades


def _leg(p):
    return {"A": p["A"], "B": p["B"], "b": p["b"]}


def simulate_trades(trades, hc: dict, funding: Funding, h0: int, settle: set, gross=1 / 6) -> tuple:
    """Buy-and-hold legs, notionals 1 : |b| scaled to `gross` (fractions of equity at entry). Hour t's P&L uses
    closes t-1 -> t and settlements in (open, close] of hour t. Entry turnover is booked at the entry hour, exit
    turnover at the exit hour; a leg without a bar closes the trade at the previous close. -> (pnl, turn)."""
    pnl, turn = {}, {}
    for tr in trades:
        k = gross / (1 + abs(tr["b"]))
        legs = {tr["A"]: tr["sign"] * k, tr["B"]: -tr["sign"] * tr["b"] * k}
        et, xt = tr["et"], tr["xt"]
        turn[et] = turn.get(et, 0.0) + sum(abs(x) for x in legs.values())
        end = xt
        for t in range(et + 1, xt + 1):
            if not all(_ok(hc[s][t - 1]) and _ok(hc[s][t]) for s in legs):
                end = t - 1
                break
            p = 0.0
            for s in legs:
                r = hc[s][t] / hc[s][t - 1] - 1
                p += legs[s] * r
                if t in settle:
                    p -= legs[s] * funding.sum(s, h0 + t * HOUR, h0 + (t + 1) * HOUR)
                legs[s] *= 1 + r
            pnl[t] = pnl.get(t, 0.0) + p
        turn[end] = turn.get(end, 0.0) + sum(abs(x) for x in legs.values())
    return pnl, turn


def a7_random_control(trades, months, hc: dict, seed=20261125) -> list:
    """Each realised trade re-drawn on the same pair in the same month at a random entry hour (legs must have bars)
    and a random direction, with its realised holding time."""
    rng = random.Random(seed)
    out = []
    for tr in trades:
        m0, m1, _ = months[tr["month"]]
        dur = tr["xt"] - tr["et"]
        hi = m1 - 1 - dur
        if hi < m0:
            continue
        et = rng.randint(m0, hi)
        sign = rng.choice((-1, 1))
        if not (_ok(hc[tr["A"]][et]) and _ok(hc[tr["B"]][et])):
            continue
        out.append({**_leg(tr), "sign": sign, "et": et, "xt": et + dur, "month": tr["month"]})
    return out


# ------------------------------------------------------------------ judging helpers
def events_per_week(event_ts, a, b) -> float:
    n = sum(1 for t in event_ts if a <= t < b)
    return n / ((b - a) / (7 * DAY)) if b > a else 0.0
