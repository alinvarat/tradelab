"""Pure logic for Thin B (RESULTS.md 'Thin B'): thin prediction-market rules filled only against recorded trades (or
Kalshi quotes), basket rules over mutually exclusive outcomes, and the registered verdict. No network here; fetchers are
in research/studies/thin_b.py.

A trade is {'t': unix s, 'side': 'BUY'|'SELL', 'idx': 0 (Yes token) | 1 (No token), 'price': float, 'size': shares,
'tx': hash}. Price history samples are not fills (L4 lesson)."""
import bisect
import random
from datetime import datetime, timezone

from core import screens as sc

DAY, HOUR = 86400, 3600


def _t(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (_t(2024), _t(2025, 7)), "validation": (_t(2025, 7), _t(2026, 4)), "test": (_t(2026, 4), _t(2026, 11))}
LATENCY_S = 300
MIN_FILL_USD = 10.0
HAIRCUT = 0.005
FAV_BAND = (0.90, 0.97)
MAX_FILL = 0.985
BASKET_MAX = 0.97
RULE_HORIZONS = {"B1": ["7d", "3d", "1d"], "B2": ["hold"], "B3": ["hold"], "B4": ["hold"], "B5": ["hold"], "B6": ["hold"], "B7": ["hold"]}
N_RULES = len(RULE_HORIZONS)
B5_EDGE = 0.15
B5_SYSTEM = ("You read the resolution rules of one prediction-market question and decide how they resolve when read "
             "LITERALLY and strictly, as a resolver would, including technicalities, exact dates, sources and definitions. "
             "You have no information after the stated date and must not assume you know the outcome. Reply with JSON only: "
             '{"p_yes": <number 0..1>, "reason": "<one sentence>"}')


def parse_trades(rows: list) -> list:
    """Data-API v2 trade rows -> normalised, de-duplicated (tx, token, price, size), ascending by time. Rows that
    cannot be parsed are dropped."""
    seen, out = set(), []
    for r in rows or []:
        try:
            key = (r.get("transaction_hash"), r.get("token_id"), float(r["price"]), float(r["size"]))
            if key in seen:
                continue
            seen.add(key)
            out.append({"t": int(r["timestamp"]), "side": str(r["side"]).upper(), "idx": int(r["outcome_index"]),
                        "price": float(r["price"]), "size": float(r["size"]), "tx": r.get("transaction_hash") or ""})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: (x["t"], x["tx"], x["idx"]))
    return out


def yes_equiv(tr: dict) -> float:
    return tr["price"] if tr["idx"] == 0 else 1 - tr["price"]


def last_yes_before(trades: list, t: float):
    ts = [x["t"] for x in trades]
    i = bisect.bisect_left(ts, t) - 1
    return yes_equiv(trades[i]) if i >= 0 else None


def first_buy(trades: list, idx: int, t_from: float, t_to: float, min_usd: float = MIN_FILL_USD):
    """First BUY trade on token idx in [t_from, t_to] big enough to hold our order; None when there is none."""
    ts = [x["t"] for x in trades]
    for i in range(bisect.bisect_left(ts, t_from), len(trades)):
        x = trades[i]
        if x["t"] > t_to:
            return None
        if x["idx"] == idx and x["side"] == "BUY" and x["size"] * x["price"] >= min_usd:
            return x
    return None


def bin_net(payoff: float, raw: float, mult: float = 1.0) -> float:
    """Return of buying one share at raw fill price + haircut (x mult) and a (mult-1) x 1% fee on the stake."""
    p = raw + HAIRCUT * mult
    return payoff / p - 1 - (mult - 1) * 0.01


def _ret(payoff, raw):
    return {"net": bin_net(payoff, raw), "net2": bin_net(payoff, raw, 2.0), "gross": payoff / raw - 1}


def b1_row(m: dict, trades: list):
    """m: {'id','end' (scheduled endDate ts),'closed' (ts),'yes_won'}. One row with the 7d/3d/1d horizons available."""
    ret, fill_t = {}, None
    for name, d in (("7d", 7), ("3d", 3), ("1d", 1)):
        t0 = m["end"] - d * DAY
        if m["closed"] <= t0 + HOUR or not trades or trades[0]["t"] >= t0:
            continue
        y = last_yes_before(trades, t0)
        if y is None:
            continue
        fav_idx, f = (0, y) if y >= 0.5 else (1, 1 - y)
        if not FAV_BAND[0] <= f <= FAV_BAND[1]:
            continue
        fill = first_buy(trades, fav_idx, t0 + LATENCY_S, t0 + 12 * HOUR)
        if not fill or fill["price"] > MAX_FILL:
            continue
        won = m["yes_won"] if fav_idx == 0 else not m["yes_won"]
        ret[name] = _ret(1.0 if won else 0.0, fill["price"])
        fill_t = fill["t"]
    if not ret:
        return None
    return {"symbol": f"pm:{m['id']}", "venue": "polymarket", "rule": "B1", "kind": "B1", "ts": m["closed"], "entry_t": fill_t, "ret": ret}


def b2_row(m: dict, trades: list):
    """First jump of the YES-equivalent price to >= 0.80 (<= 0.20) after a trade <= 0.50 (>= 0.50) in the previous 6 h."""
    ys = [(x["t"], yes_equiv(x)) for x in trades]
    for i, (t, y) in enumerate(ys):
        hi, lo = y >= 0.80, y <= 0.20
        if not (hi or lo):
            continue
        prev = [p for tt, p in ys[:i] if t - 6 * HOUR <= tt <= t]
        if not prev or not ((hi and min(prev) <= 0.50) or (lo and max(prev) >= 0.50)):
            continue
        idx = 0 if hi else 1
        fill = first_buy(trades, idx, t + LATENCY_S, t + 6 * HOUR)
        if not fill or fill["price"] > 0.95 or m["closed"] <= fill["t"]:
            return None                         # the first jump decides; a later one is a different event
        won = m["yes_won"] if idx == 0 else not m["yes_won"]
        return {"symbol": f"pm:{m['id']}", "venue": "polymarket", "rule": "B2", "kind": "B2", "ts": m["closed"], "entry_t": fill["t"],
                "ret": {"hold": _ret(1.0 if won else 0.0, fill["price"])}}
    return None


def b5_row(m: dict, trades: list, p_yes):
    """Haiku's literal-reading probability against the last-trade price at endDate - 3 d."""
    t0 = m["end"] - 3 * DAY
    if p_yes is None or m["closed"] <= t0 + HOUR:
        return None
    y = last_yes_before(trades, t0)
    if y is None or not 0.05 <= y <= 0.95 or abs(p_yes - y) < B5_EDGE:
        return None
    idx = 0 if p_yes > y else 1
    fill = first_buy(trades, idx, t0 + LATENCY_S, t0 + 12 * HOUR)
    if not fill or fill["price"] > MAX_FILL:
        return None
    won = m["yes_won"] if idx == 0 else not m["yes_won"]
    return {"symbol": f"pm:{m['id']}", "venue": "polymarket", "rule": "B5", "kind": "B5", "ts": m["closed"], "entry_t": fill["t"],
            "p_yes": p_yes, "price": y, "ret": {"hold": _ret(1.0 if won else 0.0, fill["price"])}}


def basket_row(event_id: str, legs: list, closed: float, rule: str):
    """Polymarket negative-risk basket from recorded trades. legs = [{'trades': [...], 'won': bool}] (won = Yes resolved);
    rule 'B3' buys every Yes, 'B4' every No. Hourly grid; every leg needs a qualifying BUY within 30 minutes; the highest
    such price is the leg's ask. First grid time meeting the cost cap enters. Nothing winning is a loss, never dropped."""
    n = len(legs)
    idx = 0 if rule == "B3" else 1
    if n < 3 or any(not lg["trades"] for lg in legs):
        return None
    start = max(lg["trades"][0]["t"] for lg in legs)
    cap = BASKET_MAX if rule == "B3" else BASKET_MAX * (n - 1)
    t = int(start // HOUR * HOUR) + HOUR
    while t < closed - HOUR:
        asks = []
        for lg in legs:
            buys = [x["price"] for x in lg["trades"] if t <= x["t"] <= t + 1800 and x["idx"] == idx and x["side"] == "BUY"
                    and x["size"] * x["price"] >= MIN_FILL_USD]
            if not buys:
                break
            asks.append(max(buys))
        else:
            if sum(a + HAIRCUT for a in asks) <= cap:
                wins = sum(1 for lg in legs if lg["won"])
                payoff = wins if rule == "B3" else n - wins
                s1, s2 = sum(a + HAIRCUT for a in asks), sum(a + 2 * HAIRCUT for a in asks)
                return {"symbol": f"pm:{event_id}", "venue": "polymarket", "rule": rule, "kind": rule, "ts": closed, "entry_t": t + 1800,
                        "legs": n, "winners": wins, "ret": {"hold": {"net": payoff / s1 - 1, "net2": payoff / s2 - 1 - 0.01,
                                                                      "gross": payoff / sum(asks) - 1}}}
        t += HOUR
    return None


def kalshi_fee(p: float) -> float:
    return 0.07 * p * (1 - p)


def kalshi_basket_row(event_id: str, legs: list, closed: float, rule: str):
    """legs = [{'candles': {end_ts: (yes_bid, yes_ask)}, 'won': bool}] (hourly candle closes, decimal dollars); B6 buys
    every Yes at the ask, B7 every No at 1 - bid. Taker fee 0.07 p (1 - p) per leg plus a 0.5 cent haircut; a missing
    quote (ask >= 0.999 or bid <= 0.001) blocks that hour. Nothing winning pays 0 (B6) / N (B7) and is kept."""
    n = len(legs)
    if n < 3 or not all(lg["candles"] for lg in legs):
        return None
    common = sorted(set.intersection(*[set(lg["candles"]) for lg in legs]))
    cap = BASKET_MAX if rule == "B6" else BASKET_MAX * (n - 1)
    for t in common:
        if t >= closed:
            break
        prices = []
        for lg in legs:
            bid, ask = lg["candles"][t]
            if rule == "B6":
                if ask is None or ask >= 0.999 or ask <= 0:
                    break
                prices.append(ask)
            else:
                if bid is None or bid <= 0.001 or bid >= 1:
                    break
                prices.append(1 - bid)
        else:
            def cost(mult):
                return sum(p + mult * kalshi_fee(p) + HAIRCUT * mult for p in prices)
            if cost(1.0) <= cap:
                wins = sum(1 for lg in legs if lg["won"])
                payoff = wins if rule == "B6" else n - wins
                return {"symbol": f"kx:{event_id}", "venue": "kalshi", "rule": rule, "kind": rule, "ts": closed, "entry_t": t, "legs": n,
                        "winners": wins, "ret": {"hold": {"net": payoff / cost(1.0) - 1, "net2": payoff / cost(2.0) - 1,
                                                          "gross": payoff / sum(prices) - 1}}}
    return None


def quantile_bounds(rows: list, fr=(0.4, 0.7)) -> dict:
    """B5 splits: the first 40% / next 30% / last 30% of rows by time (a small, time-ordered sample)."""
    ts = sorted(r["ts"] for r in rows)
    if len(ts) < 10:
        return BOUNDS
    a, b = ts[int(len(ts) * fr[0])], ts[int(len(ts) * fr[1])]
    return {"train": (0, a), "validation": (a, b), "test": (b, 1e12)}


# ------------------------------------------------------------------ verdict
def _mean(v):
    return sum(v) / len(v) if v else None


def verdict(rows: list, horizons: list, n_rules: int = N_RULES, bounds: dict = None, seed: int = 7) -> dict:
    """Registered verdict (RESULTS.md 'Thin B'). Validation week count uses the validation window."""
    bounds = bounds or BOUNDS
    rng = random.Random(seed)
    check = sc.integrity(rows, horizons, bounds)
    by_split = {sp: [r for r in rows if sc.split_of(r["ts"], bounds) == sp] for sp in bounds}
    table, losing = {}, {}
    for h in horizons:
        table[h] = {}
        for sp, rs in by_split.items():
            v = [r["ret"][h]["net"] for r in rs if h in r["ret"]]
            table[h][sp] = {"n": len(v), "mean": None if not v else round(_mean(v), 5), "losing": sum(1 for x in v if x < 0)}
    out = {"integrity": check, "table": table}
    if not check["ok"]:
        return {**out, "pick": None, "verdict": "invalid data: " + "; ".join(check["problems"])}

    def tr(h):
        v = sorted(r["ret"][h]["net"] for r in by_split["train"] if h in r["ret"])
        v = v[:-5] if len(v) > 5 else v
        return _mean(v)
    ok = [h for h in horizons if tr(h) is not None]
    if not ok:
        return {**out, "pick": None, "verdict": "no data"}
    pick = max(ok, key=tr)
    val = [r for r in by_split["validation"] if pick in r["ret"]]
    v = [r["ret"][pick]["net"] for r in val]
    p = sc.block_bootstrap_p(v, [sc.day_key(r) for r in val], rng) if v else 1.0
    srt = sorted(v)
    trimmed = {f"without_best_{d}": _mean(srt[:-d]) for d in (1, 5) if len(srt) > d}
    v2 = [r["ret"][pick]["net2"] for r in val]
    test = [r["ret"][pick]["net"] for r in by_split["test"] if pick in r["ret"]]
    a, b = bounds["validation"]
    weeks = max((min(b, max([r["ts"] for r in rows] + [a])) - a) / (7 * DAY), 1.0)
    res = {"validation_mean": _mean(v), "validation_p": round(p, 4), "validation_double_cost": _mean(v2), **trimmed,
           "test_mean": _mean(test), "test_n": len(test), "per_week_validation": round(len(v) / weeks, 2)}
    passed = (bool(v) and _mean(v) > 0 and p < 0.05 / n_rules and (_mean(v2) or 0) > 0
              and all((x or 0) > 0 for x in trimmed.values()) and bool(test) and _mean(test) > 0 and res["per_week_validation"] >= 3)
    killed = (not v) or _mean(v) <= 0 or p > 0.2 or (_mean(v2) or 0) <= 0 or any((x or 0) <= 0 for x in trimmed.values())
    return {**out, "pick": pick, **res, "verdict": "pass" if passed else ("killed" if killed else "inconclusive")}


def audit_rows(rows: list, k: int = 8) -> list:
    flat = sorted(rows, key=lambda r: -max(x["net"] for x in r["ret"].values()))
    return [{"symbol": r["symbol"], "rule": r["rule"], "ts": r["ts"], "best_net": round(max(x["net"] for x in r["ret"].values()), 3),
             "gross": {h: round(x["gross"], 3) for h, x in r["ret"].items()}, **({"legs": r["legs"], "winners": r["winners"]} if "legs" in r else {})}
            for r in flat[:k]]


def summarize(rows: list, extra: dict = None) -> dict:
    out = {"rows": len(rows), "bonferroni_alpha": round(0.05 / N_RULES, 5), "per_rule": {}, **(extra or {})}
    for rule, hs in RULE_HORIZONS.items():
        rs = [r for r in rows if r["rule"] == rule]
        if not rs:
            out["per_rule"][rule] = {"verdict": "no data", "rows": 0}
            continue
        out["per_rule"][rule] = {**verdict(rs, hs, bounds=quantile_bounds(rs) if rule == "B5" else None), "audit_top": audit_rows(rs)}
        out["per_rule"][rule]["winners_when_basket"] = (sum(r["winners"] for r in rs) / len(rs)) if "winners" in rs[0] else None
    return out
