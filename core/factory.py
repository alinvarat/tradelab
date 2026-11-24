"""Idea factory: many pre-registered portfolio rules judged together on one panel of daily bars.

Each strategy turns the panel into target weights per day (decided with data up to that day's close) and earns
the next day's close-to-close returns. Costs are charged on turnover. All strategies are judged together with a
Bonferroni bar, so testing many ideas at once does not manufacture a pass. Simulated research only."""
import math
import random
from statistics import mean, pstdev

ONE_WAY_COST = 0.002          # taker + slippage per unit of turnover
FUNDING_DAY = 0.0009          # assumed cost of holding a short (perp funding), per unit short per day
MIN_QV = 2e6                  # 20-day average quote volume to be tradable (USDT)


def panel(bars: dict) -> tuple:
    """bars: {symbol: [(ts, o, h, l, c, qv)]} daily, ts at 00:00 UTC. -> (days, close, qv) with
    close[d][sym] and qv[d][sym] only where the coin traded that day."""
    close, qv = {}, {}
    for s, rows in bars.items():
        for t, _o, _h, _l, c, q in rows:
            close.setdefault(t, {})[s] = c
            qv.setdefault(t, {})[s] = q
    days = sorted(close)
    return days, close, qv


def _ret(close, a, b, s):
    pa, pb = close[a].get(s), close[b].get(s)
    return pb / pa - 1 if pa and pb else None


def features(days, close, qv, bench="BTCUSDT") -> list:
    """Per day i: {sym: {...}} for liquid coins, using data up to and including day i only."""
    out = []
    hist = {}
    for i, d in enumerate(days):
        f = {}
        for s, c in close[d].items():
            h = hist.setdefault(s, [])
            h.append((c, qv[d][s]))
            if len(h) > 61:
                h.pop(0)
            if s == bench or len(h) < 31:
                continue
            adv = mean(x[1] for x in h[-21:-1])
            if adv < MIN_QV:
                continue
            cs = [x[0] for x in h]
            rets = [cs[k] / cs[k - 1] - 1 for k in range(len(cs) - 30, len(cs))]
            f[s] = {"r1": cs[-1] / cs[-2] - 1, "r3": cs[-1] / cs[-4] - 1, "r7": cs[-1] / cs[-8] - 1,
                    "r14": cs[-1] / cs[-15] - 1, "r28": cs[-1] / cs[-29] - 1, "vol30": pstdev(rets),
                    "qv_ratio": h[-1][1] / adv if adv else 0.0, "hi28": cs[-1] >= max(cs[-29:-1]),
                    "age": len(h)}
        out.append(f)
    return out


def _deciles(f, key, frac=0.1, k_min=5):
    """Top and bottom `frac` of the liquid coins by f[key]; empty when fewer than 2*k_min coins."""
    items = sorted(((v[key], s) for s, v in f.items()), reverse=True)
    k = max(k_min, int(len(items) * frac))
    if len(items) < 2 * k_min:
        return [], []
    return [s for _, s in items[:k]], [s for _, s in items[-k:]]


def _ls(top, bottom, sign=1):
    w = {}
    for s in top:
        w[s] = w.get(s, 0) + sign * 0.5 / len(top)
    for s in bottom:
        w[s] = w.get(s, 0) - sign * 0.5 / len(bottom)
    return w


STRATEGIES = {}


def strategy(name):
    def deco(fn):
        STRATEGIES[name] = fn
        return fn
    return deco


for _lb in ("r3", "r7", "r14", "r28"):
    STRATEGIES[f"xs_momentum_{_lb}"] = (lambda lb: lambda f, i: _ls(*_deciles(f, lb)))(_lb)
for _lb in ("r1", "r3"):
    STRATEGIES[f"xs_reversal_{_lb}"] = (lambda lb: lambda f, i: _ls(*_deciles(f, lb), sign=-1))(_lb)


@strategy("low_vol_minus_high_vol")
def _lowvol(f, i):
    hi, lo = _deciles(f, "vol30")
    return _ls(lo, hi)


@strategy("volume_shock_long")
def _vshock_long(f, i):
    pick = [s for s, v in f.items() if v["qv_ratio"] >= 5 and v["r1"] > 0]
    return {s: 1.0 / len(pick) for s in pick} if pick else {}


@strategy("volume_shock_fade")
def _vshock_fade(f, i):
    pick = [s for s, v in f.items() if v["qv_ratio"] >= 5 and v["r1"] > 0]
    return {s: -1.0 / len(pick) for s in pick} if pick else {}


@strategy("breakout_28d_long")
def _breakout(f, i):
    pick = [s for s, v in f.items() if v["hi28"] and v["r1"] > 0]
    return {s: 1.0 / len(pick) for s in pick} if pick else {}


@strategy("young_coin_short")
def _young(f, i):
    pick = [s for s, v in f.items() if v["age"] <= 45]     # 31-45 days of history: recently listed
    return {s: -1.0 / len(pick) for s in pick} if pick else {}


STRATEGY_NAMES = sorted(STRATEGIES)


def run(days, close, feats, strat, bench="BTCUSDT", hedge=True, cost_mult=1.0) -> list:
    """Daily net returns [(ts, r)]: weights decided at day i's close earn day i -> i+1, minus BTC beta (net exposure
    hedged with BTC when hedge), minus turnover cost and funding on shorts."""
    out, prev = [], {}
    for i in range(len(days) - 1):
        w = strat(feats[i], i)
        d0, d1 = days[i], days[i + 1]
        gross, net_exp = 0.0, 0.0
        for s, x in w.items():
            r = _ret(close, d0, d1, s)
            if r is None:
                r = 0.0                       # coin vanished: treated as flat (stated limit, conservative for shorts)
            gross += x * r
            net_exp += x
        if hedge and abs(net_exp) > 1e-12:
            rb = _ret(close, d0, d1, bench) or 0.0
            gross -= net_exp * rb
        turnover = sum(abs(w.get(s, 0) - prev.get(s, 0)) for s in set(w) | set(prev))
        short = sum(-x for x in w.values() if x < 0)
        out.append((d1, gross - cost_mult * (turnover * ONE_WAY_COST + short * FUNDING_DAY)))
        prev = w
    return out


def block_p(v: list, block=20, n_boot=2000, seed=11) -> float:
    """One-sided p of mean <= 0 by moving-block bootstrap of daily returns (keeps short-range dependence)."""
    if len(v) < 2 * block:
        return 1.0
    rng = random.Random(seed)
    m0 = mean(v)
    c = [x - m0 for x in v]                  # centre under the null
    nb = math.ceil(len(v) / block)
    hits = 0
    for _ in range(n_boot):
        s = []
        for _ in range(nb):
            a = rng.randrange(0, len(c) - block + 1)
            s.extend(c[a:a + block])
        if mean(s[:len(v)]) >= m0:
            hits += 1
    return (hits + 1) / (n_boot + 1)


def month_multiples(series: list, lev: float) -> list:
    """Equity multiple per calendar month at constant leverage `lev` (daily rebalanced); a day below -100% ruins."""
    import time as _t
    by = {}
    for t, r in series:
        by.setdefault(_t.strftime("%Y-%m", _t.gmtime(t)), []).append(r)
    out = []
    for _m, rs in sorted(by.items()):
        eq = 1.0
        for r in rs:
            eq *= max(0.0, 1 + lev * r)
        out.append(eq)
    return out


def judge_all(results: dict, bounds: dict, alpha=0.05) -> dict:
    """results: {name: [(ts, r)]} at base cost; also needs results2x for the cost check (passed in as names+'@2x').
    Pass: validation mean > 0 with block p < alpha / n_strategies, validation > 0 at double cost, test mean > 0."""
    names = [n for n in results if not n.endswith("@2x")]
    bar = alpha / max(1, len(names))
    out = {"n_strategies": len(names), "bonferroni_bar": bar, "strategies": {}}
    for n in names:
        row = {}
        for sp, (a, b) in bounds.items():
            v = [r for t, r in results[n] if a <= t < b]
            v2 = [r for t, r in results.get(n + "@2x", []) if a <= t < b]
            row[sp] = {"days": len(v), "mean_day": mean(v) if v else None,
                       "sharpe_ann": (mean(v) / pstdev(v) * math.sqrt(365)) if len(v) > 1 and pstdev(v) > 0 else None,
                       "mean_day_2x": mean(v2) if v2 else None}
        val = [r for t, r in results[n] if bounds["validation"][0] <= t < bounds["validation"][1]]
        row["validation"]["p_block"] = block_p(val)
        v, t2 = row["validation"], row["test"]
        row["passed"] = bool(v["mean_day"] and v["mean_day"] > 0 and v["p_block"] < bar
                             and (v["mean_day_2x"] or 0) > 0 and (t2["mean_day"] or 0) > 0)
        best = None
        for lev in (1, 2, 3, 5, 8, 12):
            mm = month_multiples([(t, r) for t, r in results[n] if bounds["validation"][0] <= t < bounds["validation"][1]], lev)
            if mm:
                cand = {"lev": lev, "months_3x": sum(m >= 3 for m in mm), "months": len(mm),
                        "worst_month": min(mm), "median_month": sorted(mm)[len(mm) // 2]}
                if best is None or (cand["months_3x"], cand["median_month"]) > (best["months_3x"], best["median_month"]):
                    best = cand
        row["validation_3x_check"] = best
        out["strategies"][n] = row
    out["passed"] = [n for n in names if out["strategies"][n]["passed"]]
    return out
