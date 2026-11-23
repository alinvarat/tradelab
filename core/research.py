"""Strategy research: evidence-based portfolio methods tested walk-forward on 20+ years of adjusted daily prices.

Methods (literature in research/METHODS.md):
  buy_hold, sixty_forty, equal_weight          baselines
  trend_sma (Faber 2007)                       hold each asset only above its N-day SMA
  dual_mom (Antonacci 2014)                    hold the top-K assets by lookback return, only if above cash
  tsmom_vt (Moskowitz, Ooi, Pedersen 2012)     long assets with positive 12-month return, inverse-volatility weights
  rsi2 (Connors)                               SPY: buy RSI(2) < x above SMA200, exit on close above SMA5
  tom                                           SPY: hold the last day and first 3 days of each month
Rules: weights decided at a close apply from the next day's return; costs charged on turnover.
Params are chosen on TRAIN years only; TEST years are reported, never used to choose."""
import math
import time
import urllib.parse
from datetime import datetime, timezone

from . import data, indicators as ind

COST = 0.0010  # per unit of turnover (0.10% per side)


def history(symbol, start="2000-01-01"):
    p1 = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?period1={p1}&period2={int(time.time())}&interval=1d")
    for attempt in range(4):
        try:
            res = data.get_json(url, ttl=6 * 3600)["chart"]["result"][0]
            break
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(3)
    q, adj = res["indicators"]["quote"][0], res["indicators"].get("adjclose", [{}])[0].get("adjclose")
    out = {}
    for i, t in enumerate(res["timestamp"]):
        c = (adj or q["close"])[i]
        if c is None or q["close"][i] is None:
            continue
        out[time.strftime("%Y-%m-%d", time.gmtime(t + 12 * 3600))] = c
    return out


def panel(symbols, start="2000-01-01"):
    """Dates (union of SPY trading days) and per-symbol adjusted closes (None before listing / gaps)."""
    h = {s: history(s, start) for s in symbols}
    days = sorted(h["SPY"]) if "SPY" in h else sorted(set().union(*[set(v) for v in h.values()]))
    px = {}
    for s, d in h.items():
        last, col = None, []
        for day in days:
            v = d.get(day)
            last = v if v is not None else last
            col.append(last)
        px[s] = col
    return days, px


# ---------------- weight rules: return weights for each day given data up to that day ----------------
def month_ends(days):
    return {i for i in range(len(days) - 1) if days[i][:7] != days[i + 1][:7]}


def w_static(days, px, alloc):
    return lambda i: {s: w for s, w in alloc.items() if px[s][i] is not None}


def make_rule(name, days, px, uni, p):
    me = month_ends(days)
    n = len(days)
    if name == "buy_hold":
        return lambda i, prev: {p["asset"]: 1.0}
    if name == "sixty_forty":
        return lambda i, prev: ({"SPY": 0.6, "IEF": 0.4} if i in me or not prev else prev)
    if name == "equal_weight":
        def f(i, prev):
            if i not in me and prev:
                return prev
            live = [s for s in uni if px[s][i] is not None and i >= 252 and px[s][i - 252] is not None]
            return {s: 1 / len(live) for s in live} if live else {}
        return f
    if name == "trend_sma":
        smas = {s: _sma_none(px[s], p["sma"]) for s in uni}

        def f(i, prev):
            if i not in me and prev is not None:
                return prev
            live = [s for s in uni if px[s][i] is not None and smas[s][i] is not None]
            if not live:
                return {}
            return {s: 1 / len(live) for s in live if px[s][i] > smas[s][i]}
        return f
    if name == "dual_mom":
        lb, k = p["lookback"], p["top"]
        guard, invvol = p.get("guard", False), p.get("invvol", False)
        smas = {s: _sma_none(px[s], 200) for s in uni} if guard else {}

        def f(i, prev):
            if i not in me and prev is not None:
                return prev
            return dual_weights(px, uni, i, lb, k, guard, invvol, smas)
        return f
    if name == "tsmom_vt":
        lb, tv = p["lookback"], p["target_vol"]

        def f(i, prev):
            if i not in me and prev is not None:
                return prev
            if i < max(lb, 63):
                return {}
            w = {}
            for s in uni:
                if px[s][i - lb] is None or px[s][i - 63] is None:
                    continue
                if px[s][i] / px[s][i - lb] - 1 <= 0:
                    continue
                r = [px[s][j] / px[s][j - 1] - 1 for j in range(i - 62, i + 1)]
                vol = _std(r) * math.sqrt(252)
                if vol > 0:
                    w[s] = tv / vol / len(uni)
            tot = sum(w.values())
            return {s: v / tot for s, v in w.items()} if tot > 1 else w
        return f
    if name == "rsi2":
        c = px["SPY"]
        r2 = ind.rsi(c, 2)
        s200, s5 = ind.sma(c, 200), ind.sma(c, 5)

        def f(i, prev):
            held = bool(prev)
            if held and c[i] > s5[i]:
                return {}
            if not held and r2[i] is not None and s200[i] and c[i] > s200[i] and r2[i] < p["entry"]:
                return {"SPY": 1.0}
            return prev or {}
        return f
    if name == "tom":
        first = {i for i in range(1, n) if days[i][:7] != days[i - 1][:7]}
        hold = set(me)
        for f0 in first:
            hold |= {f0, f0 + 1, f0 + 2}
        return lambda i, prev: {"SPY": 1.0} if i + 1 in hold else {}
    raise ValueError(name)


def dual_weights(px, uni, i, lb, k, guard=False, invvol=False, smas=None):
    """Top-k assets by lookback return that beat cash (SHY); optional SMA200 guard and inverse-vol weights."""
    if i < lb:
        return {}
    cash = px["SHY"][i] / px["SHY"][i - lb] - 1 if px.get("SHY") and px["SHY"][i - lb] else 0
    rets = [(px[s][i] / px[s][i - lb] - 1, s) for s in uni if px[s][i - lb] is not None and px[s][i] is not None]
    top = [s for r, s in sorted(rets, reverse=True)[:k] if r > cash]
    if guard:
        top = [s for s in top if smas.get(s) and smas[s][i] is not None and px[s][i] > smas[s][i]]
    if not top:
        return {}
    if invvol:
        iv = {}
        for s in top:
            r = [px[s][j] / px[s][j - 1] - 1 for j in range(max(1, i - 62), i + 1)]
            v = _std(r)
            iv[s] = 1 / v if v else 0
        tot = sum(iv.values()) or 1
        return {s: v / tot * len(top) / k for s, v in iv.items()}
    return {s: 1 / k for s in top}


def _sma_none(x, n):
    out = [None] * len(x)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if None not in w:
            out[i] = sum(w) / n
    return out


def _std(r):
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / len(r))


def run(days, px, rule, cost=COST):
    """Daily equity of a weight rule. Weights set at close i earn the return from i to i+1."""
    eq, w, curve, turn = 1.0, {}, [1.0], 0.0
    for i in range(len(days) - 1):
        new = rule(i, w)
        to = sum(abs(new.get(s, 0) - w.get(s, 0)) for s in set(new) | set(w))
        eq *= 1 - to * cost
        turn += to
        w = new
        r = sum(wt * (px[s][i + 1] / px[s][i] - 1) for s, wt in w.items() if px[s][i] and px[s][i + 1])
        eq *= 1 + r
        curve.append(eq)
    return curve, turn


def stats(days, curve, a, b):
    seg = curve[a:b + 1]
    if len(seg) < 30:
        return None
    yrs = (datetime.fromisoformat(days[b]) - datetime.fromisoformat(days[a])).days / 365.25
    r = [seg[i] / seg[i - 1] - 1 for i in range(1, len(seg))]
    pk, mdd = seg[0], 0.0
    for v in seg:
        pk = max(pk, v)
        mdd = max(mdd, 1 - v / pk)
    sd = _std(r) * math.sqrt(252)
    cagr = (seg[-1] / seg[0]) ** (1 / yrs) - 1
    years = {}
    for i in range(a, b + 1):
        years.setdefault(days[i][:4], [curve[i], curve[i]])[1] = curve[i]
    yr = {y: v[1] / v[0] - 1 for y, v in years.items()}
    return {"cagr": cagr * 100, "vol": sd * 100, "sharpe": (sum(r) / len(r) * 252) / sd if sd else 0,
            "mdd": mdd * 100, "total": (seg[-1] / seg[0] - 1) * 100, "worst_year": min(yr.values()) * 100,
            "pos_years": f"{sum(v > 0 for v in yr.values())}/{len(yr)}"}
