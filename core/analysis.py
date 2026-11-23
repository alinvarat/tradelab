"""Technical analysis summary: trend, momentum, volatility, levels, performance, risk and a rule-based rating.
The rating is a mechanical summary of indicators, not a forecast or advice."""
import math
import time

from . import data, indicators as ind


def _last(x):
    for v in reversed(x):
        if v is not None:
            return v
    return None


def series(bars: list) -> dict:
    """Indicator series aligned to bars, for the chart."""
    c = [b["c"] for b in bars]
    h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]
    v = [b["v"] for b in bars]
    mid, up, lo = ind.bollinger(c)
    m, s, hist = ind.macd(c)
    k, d = ind.stochastic(h, l, c)
    a, _, _ = ind.adx(h, l, c)
    return {"sma20": ind.sma(c, 20), "sma50": ind.sma(c, 50), "sma200": ind.sma(c, 200),
            "ema12": ind.ema(c, 12), "ema26": ind.ema(c, 26),
            "bb_up": up, "bb_mid": mid, "bb_lo": lo, "rsi": ind.rsi(c), "macd": m, "macd_signal": s,
            "macd_hist": hist, "stoch_k": k, "stoch_d": d, "adx": a, "atr": ind.atr(h, l, c), "obv": ind.obv(c, v)}


def swing_levels(bars, window=5, max_levels=4):
    """Support/resistance from clustered swing highs/lows."""
    pts = []
    for i in range(window, len(bars) - window):
        seg = bars[i - window:i + window + 1]
        if bars[i]["h"] == max(b["h"] for b in seg):
            pts.append(bars[i]["h"])
        if bars[i]["l"] == min(b["l"] for b in seg):
            pts.append(bars[i]["l"])
    if not pts:
        return [], []
    price = bars[-1]["c"]
    tol = price * 0.015
    clusters = []
    for p in sorted(pts):
        if clusters and p - clusters[-1][-1] <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    lv = sorted(((sum(cl) / len(cl), len(cl)) for cl in clusters), key=lambda x: -x[1])
    sup = sorted([round(p, 4) for p, n in lv if p < price], reverse=True)[:max_levels]
    res = sorted([round(p, 4) for p, n in lv if p > price])[:max_levels]
    return sup, res


def perf(bars, days):
    if not bars:
        return None
    cutoff = bars[-1]["t"] - days * 86400
    base = next((b["c"] for b in bars if b["t"] >= cutoff), None)
    return (bars[-1]["c"] / base - 1) * 100 if base else None


def max_drawdown(c):
    peak, mdd = c[0], 0.0
    for v in c:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd * 100


def beta_corr(bars, bench):
    bm = {b["t"] // 86400: b["c"] for b in bench}
    pairs = [(b["c"], bm[b["t"] // 86400]) for b in bars if b["t"] // 86400 in bm]
    if len(pairs) < 30:
        return None, None
    ra = [pairs[i][0] / pairs[i - 1][0] - 1 for i in range(1, len(pairs))]
    rb = [pairs[i][1] / pairs[i - 1][1] - 1 for i in range(1, len(pairs))]
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / len(ra)
    va = sum((x - ma) ** 2 for x in ra) / len(ra)
    vb = sum((y - mb) ** 2 for y in rb) / len(rb)
    if not va or not vb:
        return None, None
    return cov / vb, cov / math.sqrt(va * vb)


def analyze(symbol: str) -> dict:
    ch = data.chart(symbol, "2y", "1d")
    bars = ch["bars"]
    if len(bars) < 30:
        raise ValueError("not enough history")
    c = [b["c"] for b in bars]
    h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]
    v = [b["v"] for b in bars]
    price = c[-1]
    s50, s200, s20 = _last(ind.sma(c, 50)), _last(ind.sma(c, 200)), _last(ind.sma(c, 20))
    r = _last(ind.rsi(c))
    m, sg, hist = ind.macd(c)
    k, d = ind.stochastic(h, l, c)
    a, pdi, mdi = ind.adx(h, l, c)
    at = _last(ind.atr(h, l, c))
    mid, up, lo = ind.bollinger(c)
    ob = ind.obv(c, v)
    sma50_series = ind.sma(c, 50)
    sma200_series = ind.sma(c, 200)

    signals = []  # (name, value text, vote -1/0/+1)

    def vote(name, val, sc):
        signals.append({"name": name, "value": val, "vote": sc})

    if s20:
        vote("Price vs SMA20", f"{(price / s20 - 1) * 100:+.1f}%", 1 if price > s20 else -1)
    if s50:
        vote("Price vs SMA50", f"{(price / s50 - 1) * 100:+.1f}%", 1 if price > s50 else -1)
    if s200:
        vote("Price vs SMA200", f"{(price / s200 - 1) * 100:+.1f}%", 1 if price > s200 else -1)
    if s50 and s200:
        vote("SMA50 vs SMA200", "golden cross zone" if s50 > s200 else "death cross zone", 1 if s50 > s200 else -1)
    if r is not None:
        vote("RSI(14)", f"{r:.1f}", 1 if r < 30 else -1 if r > 70 else 0)
    if _last(hist) is not None:
        vote("MACD histogram", f"{_last(hist):+.4g}", 1 if _last(hist) > 0 else -1)
    if _last(k) is not None:
        vote("Stochastic %K", f"{_last(k):.1f}", 1 if _last(k) < 20 else -1 if _last(k) > 80 else 0)
    if _last(a) is not None:
        trend_dir = 1 if _last(pdi) > _last(mdi) else -1
        vote("ADX(14) / DI", f"{_last(a):.1f}, {'+DI' if trend_dir > 0 else '-DI'} leads",
             trend_dir if _last(a) > 25 else 0)
    if _last(up) is not None:
        pos = (price - _last(lo)) / (_last(up) - _last(lo)) if _last(up) != _last(lo) else 0.5
        vote("Bollinger %B", f"{pos:.2f}", 1 if pos < 0 else -1 if pos > 1 else 0)
    if len(ob) > 20:
        vote("OBV 20-bar trend", "rising" if ob[-1] > ob[-21] else "falling", 1 if ob[-1] > ob[-21] else -1)

    score = round(sum(s["vote"] for s in signals) / len(signals) * 100) if signals else 0
    rating = ("Strong sell" if score <= -50 else "Sell" if score <= -15 else "Neutral" if score < 15
              else "Buy" if score < 50 else "Strong buy")

    # Recent crossovers
    events = []
    for i in range(max(1, len(c) - 60), len(c)):
        if sma50_series[i] and sma200_series[i] and sma50_series[i - 1] and sma200_series[i - 1]:
            if sma50_series[i - 1] <= sma200_series[i - 1] and sma50_series[i] > sma200_series[i]:
                events.append({"t": bars[i]["t"], "event": "Golden cross (SMA50 above SMA200)"})
            if sma50_series[i - 1] >= sma200_series[i - 1] and sma50_series[i] < sma200_series[i]:
                events.append({"t": bars[i]["t"], "event": "Death cross (SMA50 below SMA200)"})
        if m[i] is not None and sg[i] is not None and m[i - 1] is not None and sg[i - 1] is not None:
            if m[i - 1] <= sg[i - 1] and m[i] > sg[i]:
                events.append({"t": bars[i]["t"], "event": "MACD bullish crossover"})
            if m[i - 1] >= sg[i - 1] and m[i] < sg[i]:
                events.append({"t": bars[i]["t"], "event": "MACD bearish crossover"})

    last = bars[-2] if len(bars) > 1 else bars[-1]  # previous completed session for pivots
    pp = (last["h"] + last["l"] + last["c"]) / 3
    pivots = {"P": pp, "R1": 2 * pp - last["l"], "S1": 2 * pp - last["h"], "R2": pp + (last["h"] - last["l"]),
              "S2": pp - (last["h"] - last["l"])}
    yr = bars[-252:]
    hi, lo52 = max(b["h"] for b in yr), min(b["l"] for b in yr)
    fib = {f"{int(f * 1000) / 10}%": hi - (hi - lo52) * f for f in (0.236, 0.382, 0.5, 0.618, 0.786)}
    sup, res = swing_levels(bars[-180:])

    periods = 365 if ch["meta"].get("instrumentType") in ("CRYPTOCURRENCY",) else 252
    bench_beta = bench_corr = None
    if symbol != "^GSPC":
        try:
            bench_beta, bench_corr = beta_corr(yr, data.chart("^GSPC", "2y", "1d")["bars"])
        except Exception:
            pass
    rets = ind.returns(c[-periods:])
    mu = sum(rets) / len(rets) if rets else 0
    sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / len(rets)) if rets else 0
    year_start = time.mktime((time.gmtime(bars[-1]["t"]).tm_year, 1, 1, 0, 0, 0, 0, 0, 0))
    ytd_base = next((b["c"] for b in bars if b["t"] >= year_start), None)

    return {
        "symbol": symbol, "price": price, "currency": ch["meta"].get("currency"),
        "type": ch["meta"].get("instrumentType"), "name": ch["meta"].get("longName") or ch["meta"].get("shortName"),
        "as_of": bars[-1]["t"], "score": score, "rating": rating, "signals": signals, "events": events[-6:],
        "trend": {"sma20": s20, "sma50": s50, "sma200": s200, "adx": _last(a)},
        "momentum": {"rsi": r, "macd": _last(m), "macd_signal": _last(sg), "stoch_k": _last(k)},
        "volatility": {"atr": at, "atr_pct": at / price * 100 if at else None,
                       "hist_vol_pct": ind.hist_vol(c[-periods:], periods),
                       "bb_width_pct": (_last(up) - _last(lo)) / _last(mid) * 100 if _last(mid) else None},
        "levels": {"support": sup, "resistance": res, "pivots": pivots, "fib_52w": fib, "high_52w": hi, "low_52w": lo52},
        "performance": {"1w": perf(bars, 7), "1m": perf(bars, 30), "3m": perf(bars, 91), "6m": perf(bars, 182),
                        "1y": perf(bars, 365), "ytd": (price / ytd_base - 1) * 100 if ytd_base else None},
        "risk": {"max_drawdown_1y_pct": max_drawdown([b["c"] for b in yr]),
                 "sharpe_1y": mu / sd * math.sqrt(periods) if sd else None,
                 "beta_vs_sp500": bench_beta, "corr_vs_sp500": bench_corr,
                 "suggested_stop_2atr": price - 2 * at if at else None},
    }
