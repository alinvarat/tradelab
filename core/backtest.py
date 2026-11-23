"""Bar backtester: signal at bar close, fill at the next bar open,
stop-loss checked on bar extremes with gap-aware fills, fees and slippage on every side.
Past results do not predict future returns."""
import math

from . import data, indicators as ind

STRATEGIES = {
    "sma_cross": {"name": "SMA crossover", "params": {"fast": 50, "slow": 200}},
    "ema_cross": {"name": "EMA crossover", "params": {"fast": 12, "slow": 26}},
    "rsi_revert": {"name": "RSI mean reversion", "params": {"period": 14, "low": 30, "high": 55}},
    "macd": {"name": "MACD signal cross", "params": {"fast": 12, "slow": 26, "signal": 9}},
    "bb_breakout": {"name": "Bollinger breakout", "params": {"period": 20, "k": 2.0}},
    "bb_revert": {"name": "Bollinger mean reversion", "params": {"period": 20, "k": 2.0}},
    "donchian": {"name": "Donchian breakout (turtle)", "params": {"entry": 55, "exit": 20}},
    "buy_hold": {"name": "Buy and hold", "params": {}},
}


def make_decider(key, p, o, h, l, c):
    """Return decide(i, side) -> desired side in {-1, 0, 1} at the close of bar i (before shorting filter)."""
    if key == "sma_cross" or key == "ema_cross":
        f = (ind.sma if key == "sma_cross" else ind.ema)(c, int(p["fast"]))
        s = (ind.sma if key == "sma_cross" else ind.ema)(c, int(p["slow"]))
        return lambda i, side: side if f[i] is None or s[i] is None else (1 if f[i] > s[i] else -1)
    if key == "rsi_revert":
        r = ind.rsi(c, int(p["period"]))

        def d(i, side):
            if r[i] is None:
                return side
            if side == 0 and r[i] < p["low"]:
                return 1
            if side > 0 and r[i] > p["high"]:
                return 0
            if side == 0 and r[i] > 100 - p["low"]:
                return -1
            if side < 0 and r[i] < 100 - p["high"]:
                return 0
            return side
        return d
    if key == "macd":
        m, s, _ = ind.macd(c, int(p["fast"]), int(p["slow"]), int(p["signal"]))
        return lambda i, side: side if m[i] is None or s[i] is None else (1 if m[i] > s[i] else -1)
    if key in ("bb_breakout", "bb_revert"):
        mid, up, lo = ind.bollinger(c, int(p["period"]), float(p["k"]))

        def d(i, side):
            if mid[i] is None:
                return side
            if key == "bb_breakout":
                if c[i] > up[i]:
                    return 1
                if c[i] < lo[i]:
                    return -1
                if (side > 0 and c[i] < mid[i]) or (side < 0 and c[i] > mid[i]):
                    return 0
            else:
                if c[i] < lo[i]:
                    return 1
                if c[i] > up[i]:
                    return -1
                if (side > 0 and c[i] >= mid[i]) or (side < 0 and c[i] <= mid[i]):
                    return 0
            return side
        return d
    if key == "donchian":
        ne, nx = int(p["entry"]), int(p["exit"])

        def d(i, side):
            if i < ne + 1:
                return side
            hi_e, lo_e = max(h[i - ne:i]), min(l[i - ne:i])
            hi_x, lo_x = max(h[i - nx:i]), min(l[i - nx:i])
            if c[i] > hi_e:
                return 1
            if c[i] < lo_e:
                return -1
            if (side > 0 and c[i] < lo_x) or (side < 0 and c[i] > hi_x):
                return 0
            return side
        return d
    if key == "buy_hold":
        return lambda i, side: 1
    raise ValueError(f"unknown strategy {key}")


def features(bars):
    """Per-bar context used by filters and by the mistake analysis (all known at the bar close)."""
    c = [b["c"] for b in bars]
    h = [b["h"] for b in bars]
    l = [b["l"] for b in bars]
    s200 = ind.sma(c, 200)
    s50 = ind.sma(c, 50)
    a, _, _ = ind.adx(h, l, c)
    at = ind.atr(h, l, c)
    r = ind.rsi(c)
    atr_pct = [x / c[i] * 100 if x else None for i, x in enumerate(at)]
    # trailing 80th percentile of ATR% over the previous 252 bars: known at bar i, no look-ahead
    hi_vol = [None] * len(c)
    for i in range(len(c)):
        w = sorted(v for v in atr_pct[max(0, i - 252):i] if v is not None)
        hi_vol[i] = w[int(len(w) * 0.8)] if len(w) >= 60 else None
    return {"sma200": s200, "sma50": s50, "adx": a, "rsi": r, "atr_pct": atr_pct, "hi_vol": hi_vol, "close": c}


FILTERS = {
    "trend": "trade only with the 200-bar trend (long above SMA200, short below)",
    "adx20": "skip entries when ADX is under 20 (no trend)",
    "calm": "skip entries when volatility (ATR %) is in its top 20%",
    "no_event": "skip entries within one day of FOMC, CPI or NFP",
    "rsi_ext": "skip longs with RSI over 75 and shorts with RSI under 25 (chasing)",
}


def entry_tags(fe, i, side, events=()):
    """Conditions present when a trade was entered at the close of bar i."""
    tags = []
    s200, adx, atrp, r, c = fe["sma200"][i], fe["adx"][i], fe["atr_pct"][i], fe["rsi"][i], fe["close"][i]
    if s200 and (side > 0) != (c > s200):
        tags.append("trend")
    if adx is not None and adx < 20:
        tags.append("adx20")
    if atrp is not None and fe["hi_vol"][i] and atrp >= fe["hi_vol"][i]:
        tags.append("calm")
    if r is not None and ((side > 0 and r > 75) or (side < 0 and r < 25)):
        tags.append("rsi_ext")
    if events and fe.get("t") and any(abs(fe["t"][i] - e) < 86400 for e in events):
        tags.append("no_event")
    return tags


def run(symbol, strategy="sma_cross", params=None, rng="5y", interval="1d", capital=10_000.0, fee_pct=0.05,
        slip_pct=0.02, position_pct=100.0, stop_atr=0.0, allow_short=False, filters=()):
    ch = data.chart(symbol, rng, interval)
    r = simulate(ch["bars"], strategy, params, capital, fee_pct, slip_pct, position_pct, stop_atr, allow_short, filters)
    r.update(symbol=symbol, currency=ch["meta"].get("currency"), interval=ch["interval"])
    return r


def simulate(bars, strategy="sma_cross", params=None, capital=10_000.0, fee_pct=0.05, slip_pct=0.02,
             position_pct=100.0, stop_atr=0.0, allow_short=False, filters=(), events=(), risk_pct=None):
    """Backtest on a bar list. risk_pct (optional) sizes each trade so a stop hit loses that % of equity."""
    if len(bars) < 60:
        raise ValueError("not enough bars for a backtest (need 60+)")
    p = dict(STRATEGIES[strategy]["params"], **(params or {}))
    t = [b["t"] for b in bars]
    o, h, l, c = ([b[k] for b in bars] for k in "ohlc")
    decide = make_decider(strategy, p, o, h, l, c)
    a = ind.atr(h, l, c, 14)
    fe = features(bars)
    fe["t"] = t
    fee, slip, frac = fee_pct / 100, slip_pct / 100, position_pct / 100
    pos_tags, pending_tags = [], []
    eq = capital
    side, qty, entry, sl, entry_t, entry_fee = 0, 0.0, 0.0, None, 0, 0.0
    peak, mdd, curve, trades, pending, exposure = eq, 0.0, [], [], None, 0

    def close(px, i, why):
        nonlocal eq, side, qty
        px *= (1 - side * slip)
        f = px * qty * fee
        pnl = (px - entry) * qty * side - f
        eq += pnl
        trades.append({"side": side, "entry_t": entry_t, "exit_t": t[i], "entry": entry, "exit": px, "qty": qty,
                       "pnl": pnl - entry_fee, "ret_pct": ((px / entry - 1) * side) * 100, "reason": why,
                       "tags": pos_tags})
        side, qty = 0, 0.0

    for i in range(len(bars)):
        if pending is not None:
            (want, want_tags), pending = pending, None
            if side != 0 and want != side:
                close(o[i], i, "signal")
            if side == 0 and want != 0:
                px = o[i] * (1 + want * slip)
                qty = eq * frac / px
                if risk_pct and stop_atr and a[i - 1]:
                    qty = min(qty, eq * risk_pct / 100 / (stop_atr * a[i - 1]))
                if qty > 0:
                    side, entry, entry_t, pos_tags = want, px, t[i], want_tags
                    entry_fee = px * qty * fee
                    eq -= entry_fee
                    sl = px - side * stop_atr * a[i - 1] if stop_atr and a[i - 1] else None
        if side != 0 and sl is not None and ((side > 0 and l[i] <= sl) or (side < 0 and h[i] >= sl)):
            close(min(sl, o[i]) if side > 0 else max(sl, o[i]), i, "stop")
        if side != 0:
            exposure += 1
        m2m = eq + ((c[i] - entry) * qty * side if side else 0.0)
        peak = max(peak, m2m)
        mdd = max(mdd, (peak - m2m) / peak if peak else 0)
        curve.append([t[i], round(m2m, 2)])
        want = decide(i, side)
        if want < 0 and not allow_short:
            want = 0
        pending_tags = []
        if want != 0 and want != side:
            pending_tags = entry_tags(fe, i, want, events)
            if any(f in pending_tags for f in filters):
                want = 0
        if want != side and i < len(bars) - 1:
            pending = (want, pending_tags)
    # position the rule wants after the last bar (for live parity): last-bar signal, else current holding
    final = {"side": want if want != side else side, "tags": pending_tags if want != side else pos_tags, "stop": sl if side else None}
    if side != 0:
        close(c[-1], len(bars) - 1, "end of test")
        curve[-1][1] = round(eq, 2)

    years = max((t[-1] - t[0]) / (365.25 * 86400), 1e-9)
    rets = [curve[i][1] / curve[i - 1][1] - 1 for i in range(1, len(curve)) if curve[i - 1][1]]
    mu = sum(rets) / len(rets) if rets else 0
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets)) if rets else 0
    ppy = len(bars) / years
    wins = [x["pnl"] for x in trades if x["pnl"] > 0]
    losses = [-x["pnl"] for x in trades if x["pnl"] <= 0]
    bh = [[t[i], round(capital * c[i] / c[0], 2)] for i in range(len(bars))]
    bh_mdd, pk = 0.0, bh[0][1]
    for _, v in bh:
        pk = max(pk, v)
        bh_mdd = max(bh_mdd, (pk - v) / pk)
    return {
        "strategy": STRATEGIES[strategy]["name"], "key": strategy, "final": final, "params": p, "filters": list(filters),
        "start": t[0], "end": t[-1], "bars": len(bars),
        "metrics": {"final_equity": eq, "return_pct": (eq / capital - 1) * 100,
                    "cagr_pct": ((eq / capital) ** (1 / years) - 1) * 100 if eq > 0 else -100,
                    "max_drawdown_pct": mdd * 100, "sharpe": mu / sd * math.sqrt(ppy) if sd else None,
                    "trades": len(trades), "win_rate": len(wins) / len(trades) * 100 if trades else None,
                    "profit_factor": sum(wins) / sum(losses) if sum(losses) else None,
                    "avg_trade_pct": sum(x["ret_pct"] for x in trades) / len(trades) if trades else None,
                    "exposure_pct": exposure / len(bars) * 100,
                    "buy_hold_return_pct": (c[-1] / c[0] - 1) * 100, "buy_hold_max_drawdown_pct": bh_mdd * 100},
        "equity": curve, "buy_hold": bh, "trades": trades[-200:], "all_trades": trades,
        "costs": {"fee_pct_per_side": fee_pct, "slippage_pct_per_side": slip_pct},
    }
