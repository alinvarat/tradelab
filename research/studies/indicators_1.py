"""indicators_1: eight classic indicators on crypto perps, XM-cost gold and FX, at 15m / 1h / 4h / 1d (pre-registered in
research/studies/RESULTS.md 'indicators_1' and ops/lines/I1_indicators.md, before any bar was read for this study).

Pure logic plus two fetchers; the study runs on GitHub Actions only (AGENTS.md rule 3). No LLM.

    step0(market, tf)              the all-win ceiling gate (decides which cells exist at all)
    FAMILY                         the Bonferroni family: [(market, tf, rule)]
    positions(a, signals)          position series in {-1, 0, 1} decided at each bar's close, filled at the next open
    bar_returns(...)               per-bar net returns with spread / fee / funding or swap
    judge_cell(...)                one cell's verdict
    study_indicators_1 / study_probe_indicators_1    registered in STUDIES
"""
import bisect
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import mean, pstdev

from core import broker_costs as bc
from core import data as dt
from core import factory as fa
from core import factory_ts as ft
from core import indicators as ind


def T(y, m=1, d=1):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


# ------------------------------------------------------------------ declared constants
MARKETS = {"crypto": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"],      # Binance USDT-M perps via data.binance.vision
           "fx": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"],                              # Yahoo, XM Standard costs
           "gold": ["GC=F"],                                                                    # Yahoo gold futures as the price proxy, XAUUSD XM costs
           "etf": ["SPY", "QQQ", "IWM"]}
TFS = ("15m", "1h", "4h", "1d")
TF_SEC = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
RULES = ("rsi", "macd", "bollinger", "stochastic", "supertrend", "adx", "vwap", "ichimoku")
ATR_N = 14
STOP_ATR = 2.0              # close-based stop, 2 x ATR(14) from the entry close
MAX_HOLD = 48               # time exit, in bars of the cell's timeframe
CRYPTO_SIDE = 0.0007        # 0.05% taker + 0.02% slippage per side (same as factory_crypto_3)
LEVS = (1, 2, 3, 5, 8, 12)
MIN_DAYS = 150              # daily observations required in each of train / validation / test
MIN_ENTRIES_VAL = 30        # entries over the validation split, all symbols of the cell
MIN_COVERAGE = 0.97         # crypto: bars present / bars expected in validation
ALPHA = 0.05
N_BOOT = 20000
BLOCK = 20

# splits (UTC, [start, end)); crypto uses the factory_crypto_3 calendar, Yahoo markets what their free history allows
BOUNDS = {"crypto": {"train": (T(2020), T(2024)), "validation": (T(2024), T(2025)), "test": (T(2025), T(2026, 11))},
          "fx": {"train": (T(2024, 7, 8), T(2025, 7)), "validation": (T(2025, 7), T(2026, 3)), "test": (T(2026, 3), T(2026, 11, 24))},
          "gold": {"train": (T(2024, 7, 8), T(2025, 7)), "validation": (T(2025, 7), T(2026, 3)), "test": (T(2026, 3), T(2026, 11, 24))}}
WARMUP_START = T(2019, 12)      # crypto bars are read from here; the first month only warms indicators up
ANN_DAYS = {"crypto": 365, "fx": 252, "gold": 252}

# step-0 constants (see RESULTS.md): annual volatility, round-trip cost, leverage cap, bars per year
STEP0 = {
    "crypto": {"sigma": 0.60, "round_trip": 2 * CRYPTO_SIDE, "lev": 12,
               "bpy": {"15m": 35040, "1h": 8760, "4h": 2190, "1d": 365}},
    "fx": {"sigma": 0.08, "round_trip": 0.0002 / 1.10, "lev": 30,
           "bpy": {"15m": 24960, "1h": 6240, "4h": 1560, "1d": 260}},
    "gold": {"sigma": 0.16, "round_trip": 0.55 / 3500, "lev": 20,
             "bpy": {"15m": 24960, "1h": 6240, "4h": 1560, "1d": 260}},
    "etf": {"sigma": 0.16, "round_trip": 0.0008, "lev": 5,
            "bpy": {"15m": 6552, "1h": 1764, "4h": 504, "1d": 252}},
}
WIN_ATR = 1.5 * STOP_ATR    # all-win ceiling: every trade wins 1.5 x the stop distance, with ATR taken as one bar sigma
MIN_BARS_PER_ENTRY = 20     # an indicator signal fires at most once per 20 bars on average (generous)
OUT_DEPTH = {("fx", "15m"), ("gold", "15m")}     # Yahoo serves about 60 days of 15m: no train/validation/test of 150 days each


def step0(market, tf):
    """All-win ceiling: trades a month needed to compound 147 -> 441 USD if every trade wins WIN_ATR bar sigmas at the
    market's leverage cap, versus the most trades a month an indicator can plausibly fire. ok = needed <= available."""
    p = STEP0[market]
    bpy = p["bpy"][tf]
    sigma_bar = p["sigma"] / math.sqrt(bpy)
    win = WIN_ATR * sigma_bar
    net = p["lev"] * (win - p["round_trip"])
    need = math.log(3) / math.log(1 + net) if net > 0 else math.inf
    avail = bpy / 12 / MIN_BARS_PER_ENTRY
    return {"market": market, "tf": tf, "lev": p["lev"], "win_pct": round(win * 100, 4), "round_trip_pct": round(p["round_trip"] * 100, 4),
            "net_per_trade_pct": round(net * 100, 2), "trades_needed_per_month": round(need, 2) if need != math.inf else None,
            "trades_available_per_month": round(avail, 2), "ok": need <= avail}


def rule_in(market, tf, rule):
    if rule == "vwap" and (tf == "1d" or market == "fx"):     # one bar per session; Yahoo FX has no volume
        return False
    return True


def build_family():
    out = []
    for m in MARKETS:
        for tf in TFS:
            if (m, tf) in OUT_DEPTH or not step0(m, tf)["ok"]:
                continue
            out += [(m, tf, r) for r in RULES if rule_in(m, tf, r)]
    return out


def gate_table():
    rows = []
    for m in MARKETS:
        for tf in TFS:
            s = step0(m, tf)
            s["status"] = "out_step0" if not s["ok"] else "out_depth" if (m, tf) in OUT_DEPTH else "in"
            s["rules_in"] = len([r for r in RULES if rule_in(m, tf, r)]) if s["status"] == "in" else 0
            rows.append(s)
    return rows


FAMILY = build_family()


def cell_name(market, tf, rule):
    return f"{market}|{tf}|{rule}"


# ------------------------------------------------------------------ bars
def arrays(rows):
    """[(t, o, h, l, c, v, ...)] sorted and de-duplicated -> dict of lists."""
    by = {int(r[0]): r for r in rows}
    ks = sorted(by)
    return {"ts": ks, "o": [float(by[k][1]) for k in ks], "h": [float(by[k][2]) for k in ks],
            "l": [float(by[k][3]) for k in ks], "c": [float(by[k][4]) for k in ks], "v": [float(by[k][5] or 0) for k in ks]}


def resample(a, sec, min_count):
    """Blocks aligned to UTC multiples of `sec`; a block with fewer than min_count source bars is dropped."""
    out = {k: [] for k in ("ts", "o", "h", "l", "c", "v")}
    key, cur, cnt = None, None, 0

    def flush():
        if cur is not None and cnt >= min_count:
            for k, x in zip(("ts", "o", "h", "l", "c", "v"), cur):
                out[k].append(x)
    for i, t in enumerate(a["ts"]):
        k = t // sec
        if k != key:
            flush()
            key, cnt = k, 1
            cur = [k * sec, a["o"][i], a["h"][i], a["l"][i], a["c"][i], a["v"][i]]
        else:
            cur[2] = max(cur[2], a["h"][i])
            cur[3] = min(cur[3], a["l"][i])
            cur[4] = a["c"][i]
            cur[5] += a["v"][i]
            cnt += 1
    flush()
    return out


def clip(a, start, end):
    keep = [i for i, t in enumerate(a["ts"]) if start <= t < end]
    return {k: [v[i] for i in keep] for k, v in a.items()}


# ------------------------------------------------------------------ signals: (le, se, lx, sx, flat)
def _blank(n):
    return [False] * n, [False] * n, [False] * n, [False] * n


def sig_rsi(a, tf):
    """RSI(14) Wilder. Long when RSI crosses below 30, exit at RSI >= 50; short when it crosses above 70, exit at <= 50."""
    r = ind.rsi(a["c"], 14)
    le, se, lx, sx = _blank(len(r))
    for i in range(1, len(r)):
        if r[i] is None:
            continue
        lx[i], sx[i] = r[i] >= 50, r[i] <= 50
        if r[i - 1] is not None:
            le[i] = r[i] < 30 <= r[i - 1]
            se[i] = r[i] > 70 >= r[i - 1]
    return le, se, lx, sx, None


def sig_macd(a, tf):
    """MACD(12,26,9) histogram sign flip: long on a flip to positive, short on a flip to negative, always reversing."""
    _, _, hist = ind.macd(a["c"], 12, 26, 9)
    le, se, lx, sx = _blank(len(hist))
    for i in range(1, len(hist)):
        if hist[i] is None or hist[i - 1] is None:
            continue
        up, dn = hist[i] > 0 >= hist[i - 1], hist[i] < 0 <= hist[i - 1]
        le[i], se[i], lx[i], sx[i] = up, dn, dn, up
    return le, se, lx, sx, None


def sig_bollinger(a, tf):
    """Bollinger(20, 2): long when the close crosses below the lower band, exit at the middle band; short mirrored."""
    c = a["c"]
    mid, up, lo = ind.bollinger(c, 20, 2.0)
    le, se, lx, sx = _blank(len(c))
    for i in range(1, len(c)):
        if mid[i] is None:
            continue
        lx[i], sx[i] = c[i] >= mid[i], c[i] <= mid[i]
        if lo[i - 1] is not None:
            le[i] = c[i] < lo[i] and c[i - 1] >= lo[i - 1]
            se[i] = c[i] > up[i] and c[i - 1] <= up[i - 1]
    return le, se, lx, sx, None


def sig_stochastic(a, tf):
    """Stochastic(14, 3): raw %K and %D = SMA3(%K). Long when %K crosses above %D below 20, exit at %K >= 50; short mirrored (above 80)."""
    k, d = ind.stochastic(a["h"], a["l"], a["c"], 14, 3)
    le, se, lx, sx = _blank(len(k))
    for i in range(1, len(k)):
        if k[i] is None or d[i] is None:
            continue
        lx[i], sx[i] = k[i] >= 50, k[i] <= 50
        if k[i - 1] is not None and d[i - 1] is not None:
            le[i] = k[i - 1] <= d[i - 1] and k[i] > d[i] and k[i] < 20
            se[i] = k[i - 1] >= d[i - 1] and k[i] < d[i] and k[i] > 80
    return le, se, lx, sx, None


def sig_supertrend(a, tf):
    """Supertrend(ATR 10 Wilder, multiplier 3): long on a flip to up-trend, short on a flip to down-trend, always reversing."""
    h, l, c = a["h"], a["l"], a["c"]
    n = len(c)
    at = ind.atr(h, l, c, 10)
    d_arr, fu, fl, d = [0] * n, None, None, 0
    for i in range(n):
        if at[i] is None:
            continue
        mid = (h[i] + l[i]) / 2
        bu, bl = mid + 3 * at[i], mid - 3 * at[i]
        if fu is None:
            fu, fl, d = bu, bl, (1 if c[i] >= mid else -1)
        else:
            pfu, pfl = fu, fl
            fu = bu if (bu < pfu or c[i - 1] > pfu) else pfu
            fl = bl if (bl > pfl or c[i - 1] < pfl) else pfl
            if d == -1 and c[i] > pfu:
                d = 1
            elif d == 1 and c[i] < pfl:
                d = -1
        d_arr[i] = d
    le, se, lx, sx = _blank(n)
    for i in range(1, n):
        if d_arr[i] and d_arr[i - 1]:
            up, dn = d_arr[i] == 1 and d_arr[i - 1] == -1, d_arr[i] == -1 and d_arr[i - 1] == 1
            le[i], se[i], lx[i], sx[i] = up, dn, dn, up
    return le, se, lx, sx, None


def sig_adx(a, tf):
    """ADX(14) Wilder with DI: long on the bar where ADX > 25 and +DI > -DI becomes true, exit when ADX < 20 or -DI > +DI; short mirrored."""
    ax, pdi, mdi = ind.adx(a["h"], a["l"], a["c"], 14)
    n = len(ax)
    le, se, lx, sx = _blank(n)
    cl, cs = [False] * n, [False] * n
    for i in range(n):
        if ax[i] is None or pdi[i] is None:
            continue
        cl[i] = ax[i] > 25 and pdi[i] > mdi[i]
        cs[i] = ax[i] > 25 and mdi[i] > pdi[i]
        lx[i] = ax[i] < 20 or mdi[i] > pdi[i]
        sx[i] = ax[i] < 20 or pdi[i] > mdi[i]
    for i in range(1, n):
        le[i], se[i] = cl[i] and not cl[i - 1], cs[i] and not cs[i - 1]
    return le, se, lx, sx, None


def sig_vwap(a, tf):
    """Session VWAP (UTC day, typical price weighted by volume): long when the close crosses above it, short when it crosses below,
    reversing; no entry before 2 hours of the session have closed; flat at the last bar of every session."""
    ts, h, l, c, v = a["ts"], a["h"], a["l"], a["c"], a["v"]
    n = len(c)
    sec = TF_SEC[tf]
    sess = [t // 86400 for t in ts]
    vw, pv, vv, tps, k = [None] * n, 0.0, 0.0, 0.0, 0
    for i in range(n):
        if i == 0 or sess[i] != sess[i - 1]:
            pv = vv = tps = 0.0
            k = 0
        tp = (h[i] + l[i] + c[i]) / 3
        pv, vv, tps, k = pv + tp * v[i], vv + v[i], tps + tp, k + 1
        vw[i] = pv / vv if vv > 0 else tps / k
    le, se, lx, sx = _blank(n)
    flat = [i == n - 1 or sess[i + 1] != sess[i] for i in range(n)]
    for i in range(1, n):
        if sess[i] != sess[i - 1]:
            continue
        up, dn = c[i] > vw[i] and c[i - 1] <= vw[i - 1], c[i] < vw[i] and c[i - 1] >= vw[i - 1]
        late = (ts[i] + sec - sess[i] * 86400) >= 2 * 3600
        le[i], se[i], lx[i], sx[i] = up and late, dn and late, dn, up
    return le, se, lx, sx, flat


def sig_ichimoku(a, tf):
    """Ichimoku (9, 26, 52): cloud at bar i is spans A/B computed 26 bars earlier. Long on the bar where close > cloud top and
    tenkan > kijun becomes true, exit when tenkan < kijun; short mirrored (close < cloud bottom and tenkan < kijun)."""
    h, l, c = a["h"], a["l"], a["c"]
    n = len(c)
    th, tl = ind.donchian(h, l, 9)
    kh, kl = ind.donchian(h, l, 26)
    sh, sl = ind.donchian(h, l, 52)
    ten = [None if th[i] is None else (th[i] + tl[i]) / 2 for i in range(n)]
    kij = [None if kh[i] is None else (kh[i] + kl[i]) / 2 for i in range(n)]
    spa = [None if kij[i] is None else (ten[i] + kij[i]) / 2 for i in range(n)]
    spb = [None if sh[i] is None else (sh[i] + sl[i]) / 2 for i in range(n)]
    le, se, lx, sx = _blank(n)
    cl, cs = [False] * n, [False] * n
    for i in range(78, n):
        j = i - 26
        top, bot = max(spa[j], spb[j]), min(spa[j], spb[j])
        cl[i] = c[i] > top and ten[i] > kij[i]
        cs[i] = c[i] < bot and ten[i] < kij[i]
        lx[i], sx[i] = ten[i] < kij[i], ten[i] > kij[i]
    for i in range(79, n):
        le[i], se[i] = cl[i] and not cl[i - 1], cs[i] and not cs[i - 1]
    return le, se, lx, sx, None


SIGNALS = {"rsi": sig_rsi, "macd": sig_macd, "bollinger": sig_bollinger, "stochastic": sig_stochastic,
           "supertrend": sig_supertrend, "adx": sig_adx, "vwap": sig_vwap, "ichimoku": sig_ichimoku}
assert tuple(SIGNALS) == RULES


def positions(a, signals):
    """Position in {-1, 0, 1} decided at each bar's close. Exit on the rule's exit condition, a close-based stop STOP_ATR x ATR(14)
    from the entry close, MAX_HOLD bars, or the session end (vwap); a stopped bar does not re-enter; an exit and an opposite
    entry on one bar is a reversal."""
    le, se, lx, sx, flat = signals
    c = a["c"]
    at = ind.atr(a["h"], a["l"], c, ATR_N)
    n = len(c)
    pos, cur, ent_i, ent_px, ent_atr = [0] * n, 0, 0, 0.0, 0.0
    for i in range(n):
        stopped = False
        if cur:
            ex = (lx[i] if cur > 0 else sx[i]) or bool(flat and flat[i]) or i - ent_i >= MAX_HOLD
            if cur > 0 and c[i] <= ent_px - STOP_ATR * ent_atr:
                ex = stopped = True
            elif cur < 0 and c[i] >= ent_px + STOP_ATR * ent_atr:
                ex = stopped = True
            if ex:
                cur = 0
        if cur == 0 and not stopped and at[i] is not None and not (flat and flat[i]):
            if le[i] and not se[i]:
                cur = 1
            elif se[i] and not le[i]:
                cur = -1
            if cur:
                ent_i, ent_px, ent_atr = i, c[i], at[i]
        pos[i] = cur
    return pos


# ------------------------------------------------------------------ costs and returns
class Cost:
    """Per-side trading cost and holding cost of one symbol. Crypto: 0.07% a side and the measured funding; XM markets: the
    XM Standard spread from core.broker_costs (half the round-trip spread a side) and a 3% a year swap estimate."""

    def __init__(self, sym, funding=None):
        self.sym = sym
        self.crypto = sym.endswith("USDT")
        rows = sorted((int(t) // 3600 * 3600, r) for t, r in (funding or []))
        self.ft = [t for t, _ in rows]
        self.fc = [0.0]
        for _, r in rows:
            self.fc.append(self.fc[-1] + r)

    def side(self, price):
        if self.crypto:
            return CRYPTO_SIDE
        return bc.xm_cfd_cost_fraction(self.sym, "standard", price)["trade_per_side"]

    def hold(self, t0, t1, p, mult):
        """Cost fraction of holding signed position p over [t0, t1)."""
        if p == 0:
            return 0.0
        if self.crypto:
            return p * (self.fc[bisect.bisect_left(self.ft, t1)] - self.fc[bisect.bisect_left(self.ft, t0)])
        return abs(p) * bc.XM_SWAP_ANNUAL * (t1 - t0) / (365 * 86400) * mult


def bar_returns(a, pos, cost, dur, mult=1.0, sign=1):
    """[(t_{i+1}, r)]: the position held during bar i (decided at bar i-1's close) earns the gap close_i -> open_{i+1}; the position
    decided at bar i's close is filled at open_{i+1} and earns open_{i+1} -> close_{i+1}. A change of position pays
    mult x side cost x |change|; holding pays funding (crypto, measured, not scaled) or swap (XM, scaled by mult). sign=-1 flips every
    position (the control)."""
    ts, o, c = a["ts"], a["o"], a["c"]
    n = len(ts)
    out, prev = [], 0
    for i in range(n - 1):
        p = sign * pos[i]
        r = prev * (o[i + 1] / c[i] - 1) + p * (c[i + 1] / o[i + 1] - 1)
        if p != prev:
            r -= mult * cost.side(c[i]) * abs(p - prev)
        t1 = ts[i + 2] if i + 2 < n else ts[i + 1] + dur
        r -= cost.hold(ts[i + 1], t1, p, mult)
        out.append((ts[i + 1], r))
        prev = p
    return out


def entry_counts(a, pos, bounds):
    return {sp: ft.entries(a["ts"], pos, lo, hi) for sp, (lo, hi) in bounds.items()}


# ------------------------------------------------------------------ per-symbol work
def tf_arrays(market, base):
    """{tf: arrays} for the timeframes this market has cells in. base: {'15m': arrays or None, '1h': arrays}."""
    out = {}
    need = {tf for (m, tf, _r) in FAMILY if m == market}
    for tf in need:
        if tf == "15m":
            out[tf] = base["15m"]
        elif tf == "1h":
            out[tf] = base["1h"]
        else:
            k = TF_SEC[tf] // 3600
            out[tf] = resample(base["1h"], TF_SEC[tf], k if market == "crypto" else max(2, k // 2))
    return out


def symbol_rows(market, sym, base, funding=None):
    """Series rows for one symbol: daily slot returns at 1x cost, 2x cost and sign-flipped, plus entries per split."""
    bounds = BOUNDS[market]
    cost = Cost(sym, funding)
    rows = []
    for tf, a in sorted(tf_arrays(market, base).items()):
        if not a or not a["ts"]:
            continue
        for rule in RULES:
            if (market, tf, rule) not in FAMILY_SET():
                continue
            pos = positions(a, SIGNALS[rule](a, tf))
            dur = TF_SEC[tf]
            rows.append({"kind": "series", "market": market, "symbol": sym, "tf": tf, "rule": rule,
                         "base": ft.daily(bar_returns(a, pos, cost, dur)),
                         "x2": ft.daily(bar_returns(a, pos, cost, dur, mult=2.0)),
                         "flip": ft.daily(bar_returns(a, pos, cost, dur, sign=-1)),
                         "entries": entry_counts(a, pos, bounds), "first": a["ts"][0], "bars": len(a["ts"])})
    return rows


def FAMILY_SET():
    return set(FAMILY)


def coverage_row(market, sym, feed, a, failed):
    """Bars present vs expected per split from the symbol's first bar (crypto, regular grid), distinct days with bars (all)."""
    bounds = BOUNDS[market]
    sec = TF_SEC[feed]
    row = {"kind": "coverage", "market": market, "symbol": sym, "feed": feed, "failed": list(failed), "n": len(a["ts"]) if a else 0,
           "first": a["ts"][0] if a and a["ts"] else None, "last": a["ts"][-1] if a and a["ts"] else None, "splits": {}}
    for sp, (lo, hi) in bounds.items():
        ts = [t for t in (a["ts"] if a else []) if lo <= t < hi]
        first = row["first"] if row["first"] is not None else hi
        lo2 = max(lo, first)
        expected = int((hi - lo2) // sec) if lo2 < hi else 0
        row["splits"][sp] = {"bars": len(ts), "expected": expected, "days": len({t // 86400 for t in ts})}
    return row


# ------------------------------------------------------------------ fetchers (network)
def fetch_crypto(sym):
    """{'15m': (rows, failed), '1h': (rows, failed), 'funding': (rows, failed)} from data.binance.vision futures/um."""
    from research.studies import binance_vision as bv
    end = T(2026, 11)
    return {"15m": bv.klines(sym, WARMUP_START, end, "15m", market="futures/um"),
            "1h": bv.klines(sym, WARMUP_START, end, "1h", market="futures/um"),
            "funding": bv.funding(sym, WARMUP_START, end)}


def fetch_yahoo(sym, tries=4):
    """1h bars as [(t, o, h, l, c, v)]; Yahoo serves roughly the last 2-3 years of 1h."""
    err = None
    for k in range(tries):
        try:
            bars = dt.chart(sym, "730d", "1h")["bars"]
            return [(b["t"], b["o"], b["h"], b["l"], b["c"], b["v"]) for b in bars]
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"{sym}: Yahoo 1h failed: {err!r}")


def work(market, sym):
    """All rows of one symbol (fetch + compute)."""
    if market == "crypto":
        got = fetch_crypto(sym)
        failed = {k: v[1] for k, v in got.items()}
        a15, a1 = arrays(got["15m"][0]), arrays(got["1h"][0])
        rows = [coverage_row(market, sym, "15m", a15, failed["15m"]), coverage_row(market, sym, "1h", a1, failed["1h"])]
        rows[0]["failed_funding"] = failed["funding"]
        rows += symbol_rows(market, sym, {"15m": a15, "1h": a1}, got["funding"][0])
        return rows
    a1 = clip(arrays(fetch_yahoo(sym)), BOUNDS[market]["train"][0] - 90 * 86400, BOUNDS[market]["test"][1])
    rows = [coverage_row(market, sym, "1h", a1, [])]
    rows += symbol_rows(market, sym, {"15m": None, "1h": a1})
    return rows


# ------------------------------------------------------------------ judging
def combine(series_list, n_slots):
    acc = {}
    for s in series_list:
        for t, r in s:
            acc[t] = acc.get(t, 0.0) + r / n_slots
    return sorted(acc.items())


def split_vals(series, lo, hi):
    return [r for t, r in series if lo <= t < hi]


def equity_stats(v):
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in v:
        eq *= max(0.0, 1 + r)
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak) if peak else 0.0
    return eq, dd


def three_x_check(series, lo, hi):
    """Best constant leverage among LEVS on the validation split by (months >= 3x, median month)."""
    v = [(t, r) for t, r in series if lo <= t < hi]
    best = None
    for lev in LEVS:
        mm = fa.month_multiples(v, lev)
        if mm:
            cand = {"lev": lev, "months": len(mm), "months_3x": sum(m >= 3 for m in mm), "median_month": sorted(mm)[len(mm) // 2],
                    "worst_month": min(mm)}
            if best is None or (cand["months_3x"], cand["median_month"]) > (best["months_3x"], best["median_month"]):
                best = cand
    return best


def judge_cell(base, x2, flip, bounds, bar, ann_days, n_boot=N_BOOT):
    """Verdict on daily portfolio return series. valid-data checks are done by the caller; this computes the numbers and the pass rule:
    validation mean > 0, block p < bar, validation and test means > 0 at 1x and at 2x cost."""
    out = {}
    for sp, (lo, hi) in bounds.items():
        v, v2 = split_vals(base, lo, hi), split_vals(x2, lo, hi)
        eq, dd = equity_stats(v)
        sd = pstdev(v) if len(v) > 1 else 0.0
        out[sp] = {"days": len(v), "mean_day": mean(v) if v else None, "mean_day_2x": mean(v2) if v2 else None,
                   "sharpe_ann": (mean(v) / sd * math.sqrt(ann_days)) if sd > 0 else None, "ending_equity": round(eq, 4),
                   "worst_drawdown": round(dd, 4), "mean_day_flipped": (mean(split_vals(flip, lo, hi)) if split_vals(flip, lo, hi) else None)}
    val, tst = out["validation"], out["test"]
    val["p_block"] = fa.block_p(split_vals(base, *bounds["validation"]), BLOCK, n_boot) if val["mean_day"] and val["mean_day"] > 0 else None
    out["passed"] = bool(val["mean_day"] and val["mean_day"] > 0 and val["p_block"] is not None and val["p_block"] < bar
                         and (val["mean_day_2x"] or 0) > 0 and (tst["mean_day"] or 0) > 0 and (tst["mean_day_2x"] or 0) > 0)
    out["three_x_check_validation"] = three_x_check(base, *bounds["validation"])
    return out


def problems_for(market, tf, series_rows, cov_rows, base, bounds):
    """Reasons a cell cannot be judged ('invalid'); empty list = judged."""
    why = []
    syms = MARKETS[market]
    have = {r["symbol"] for r in series_rows}
    missing = [s for s in syms if s not in have]
    if missing:
        why.append(f"no bars/series for {missing}")
    feed = "15m" if tf == "15m" else "1h"
    for c in cov_rows:
        if c["feed"] != feed or c["symbol"] not in syms:
            continue
        if c["failed"] or c.get("failed_funding"):
            why.append(f"{c['symbol']}: failed files {c['failed'][:3]} funding {c.get('failed_funding', [])[:3]}")
        v = c["splits"]["validation"]
        if market == "crypto" and (not v["expected"] or v["bars"] / v["expected"] < MIN_COVERAGE):
            why.append(f"{c['symbol']}: validation bars {v['bars']}/{v['expected']}")
    for sp, (lo, hi) in bounds.items():
        n = len(split_vals(base, lo, hi))
        if n < MIN_DAYS:
            why.append(f"{sp}: {n} daily rows < {MIN_DAYS}")
    ent = sum(r["entries"]["validation"] for r in series_rows)
    if ent < MIN_ENTRIES_VAL:
        why.append(f"validation entries {ent} < {MIN_ENTRIES_VAL}")
    return why


def summarize(rows):
    series = [r for r in rows if r["kind"] == "series"]
    cov = [r for r in rows if r["kind"] == "coverage"]
    by = {}
    for r in series:
        by.setdefault((r["market"], r["tf"], r["rule"]), []).append(r)
    bar = ALPHA / len(FAMILY)
    cells, out_rows = {}, []
    for (m, tf, rule) in FAMILY:
        name = cell_name(m, tf, rule)
        sr = by.get((m, tf, rule), [])
        n_slots = len(MARKETS[m])
        base = combine([r["base"] for r in sr], n_slots)
        x2 = combine([r["x2"] for r in sr], n_slots)
        flip = combine([r["flip"] for r in sr], n_slots)
        bounds = BOUNDS[m]
        why = problems_for(m, tf, sr, cov, base, bounds)
        s0 = step0(m, tf)
        lo, hi = bounds["validation"]
        months, weeks = (hi - lo) / (30.4375 * 86400), (hi - lo) / (7 * 86400)
        ent = sum(r["entries"]["validation"] for r in sr)
        cell = {"market": m, "tf": tf, "rule": rule, "status": "invalid" if why else None, "invalid_reasons": why,
                "entries_validation": ent, "entries_per_week_validation": round(ent / weeks, 2),
                "entries_per_slot_month_validation": round(ent / n_slots / months, 2),
                "trades_needed_per_month_step0": s0["trades_needed_per_month"]}
        cell["step0_ceiling_met_by_observed_rate"] = (s0["trades_needed_per_month"] is not None
                                                      and cell["entries_per_slot_month_validation"] >= s0["trades_needed_per_month"])
        if not why:
            cell.update(judge_cell(base, x2, flip, bounds, bar, ANN_DAYS[m]))
            cell["status"] = "passed" if cell["passed"] else "failed"
        cells[name] = cell
        out_rows.append({"cell": name, "daily_base": base})
    counts = {k: sum(1 for c in cells.values() if c["status"] == k) for k in ("passed", "failed", "invalid")}
    judged = [(n, c) for n, c in cells.items() if c["status"] in ("passed", "failed")]
    top = sorted(judged, key=lambda x: ((x[1]["validation"]["p_block"] if x[1]["validation"].get("p_block") is not None else 1.0),
                                        -(x[1]["validation"]["mean_day"] or -1)))[:8]
    flags = []
    if sum(1 for _, c in judged if (c["validation"].get("p_block") or 1) <= 0.0001) >= max(3, len(judged) // 2):
        flags.append("p at the floor on many cells")
    return {"family_size": len(FAMILY), "bonferroni_bar": bar, "n_boot": N_BOOT, "counts": counts, "passed": sorted(n for n, c in judged if c["passed"]),
            "best_by_validation_p": [{"cell": n, "validation_mean_day": c["validation"]["mean_day"], "validation_p_block": c["validation"].get("p_block"),
                                      "test_mean_day": c["test"]["mean_day"], "validation_mean_day_2x": c["validation"]["mean_day_2x"],
                                      "test_mean_day_2x": c["test"]["mean_day_2x"], "passed": c["passed"]} for n, c in top],
            "red_flags": flags, "step0_gate": gate_table(), "cells": cells,
            "coverage": [{k: v for k, v in c.items() if k != "kind"} for c in cov]}, out_rows


# ------------------------------------------------------------------ studies
def study_indicators_1(_symbols, workers=6):
    jobs = [(m, s) for m in ("crypto", "fx", "gold") for s in MARKETS[m] if any(x[0] == m for x in FAMILY)]
    rows, errors = [], []

    def one(j):
        try:
            return work(*j)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{j[1]}: {e!r}"[:300])
            return []
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, jobs):
            rows += r
    summ, out_rows = summarize(rows)
    summ["fetch_errors"] = errors
    summ["splits"] = {m: {sp: [time.strftime("%Y-%m-%d", time.gmtime(x)) for x in b] for sp, b in BOUNDS[m].items()} for m in BOUNDS}
    return summ, out_rows


def study_probe_indicators_1(_symbols):
    """Depth probe: counts and first/last dates only (no prices, no returns)."""
    from research.studies import binance_vision as bv
    from research.studies.thin_a import http
    out = {"yahoo": {}, "crypto": {}, "http": {}}
    for sym in MARKETS["fx"] + MARKETS["gold"] + MARKETS["etf"]:
        for rng, iv in (("60d", "15m"), ("730d", "1h"), ("10y", "1d")):
            key = f"{sym}|{iv}"
            try:
                bars = dt.chart(sym, rng, iv)["bars"]
                ts = [b["t"] for b in bars]
                out["yahoo"][key] = {"n": len(bars), "first": time.strftime("%Y-%m-%d", time.gmtime(ts[0])) if ts else None,
                                     "last": time.strftime("%Y-%m-%d", time.gmtime(ts[-1])) if ts else None,
                                     "zero_volume_frac": round(sum(1 for b in bars if not b["v"]) / len(bars), 3) if bars else None}
            except Exception as e:  # noqa: BLE001
                out["yahoo"][key] = {"error": repr(e)[:160]}
    for iv in ("15m", "1h"):
        rows, failed = bv.klines("BTCUSDT", T(2020), T(2020, 2), iv, market="futures/um")
        out["crypto"][f"BTCUSDT|{iv}|2020-01"] = {"n": len(rows), "failed": failed}
    rows, failed = bv.funding("BTCUSDT", T(2020), T(2020, 2))
    out["crypto"]["BTCUSDT|funding|2020-01"] = {"n": len(rows), "failed": failed}
    for name, url in (("okx_15m", "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT-SWAP&bar=15m&limit=3"),
                      ("bybit_15m", "https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=15&limit=3")):
        status, _body, secs = http(url)
        out["http"][name] = {"status": status, "seconds": secs}
    out["gate_table"] = gate_table()
    out["family_size"] = len(FAMILY)
    return out, []


STUDIES = {"indicators_1": study_indicators_1, "probe_indicators_1": study_probe_indicators_1}
