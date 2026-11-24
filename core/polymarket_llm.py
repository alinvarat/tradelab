"""Pure pieces of research/studies/protocol_polymarket_llm.md (network loaders are in research/studies/run.py)."""
import calendar
import json
import random
import re
import time

from . import news_backtest as nb

FIRST_DAY = "2026-10-20"
MIN_VOLUME, MIN_DAYS, LEAD_S, MAX_AGE_S = 10_000.0, 4, 72 * 3600, 24 * 3600
EDGE, SLIP, STRESS_SLIP = 0.10, 0.01, 0.03
MIN_BETS = 100
SYSTEM = ("You are a careful forecaster. You will get one prediction-market question with its rules. Estimate the "
          "probability that it resolves YES. You have no information after the stated date; do not assume you know "
          'the outcome. Reply with JSON only: {"p_yes": <number 0..1>, "reason": "<one sentence>"}')


def iso_ts(s: str):
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}:\d{2}))?", s)
    if not m:
        return None
    return calendar.timegm(time.strptime(m.group(1) + "T" + (m.group(2) or "00:00:00"), "%Y-%m-%dT%H:%M:%S"))


def eligible(m: dict, now_ts: int, first_day: str = FIRST_DAY):
    """Gamma market -> normalised dict, or None when it is outside the protocol."""
    try:
        prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        toks = json.loads(m.get("clobTokenIds") or "[]")
    except (ValueError, TypeError):
        return None
    if len(prices) != 2 or len(toks) != 2 or sorted(prices) != [0.0, 1.0]:
        return None
    start, end = iso_ts(m.get("startDate")), iso_ts(m.get("endDate"))
    if start is None or end is None or start < iso_ts(first_day) or end > now_ts or end - start < MIN_DAYS * 86400:
        return None
    if float(m.get("volumeNum") or 0) < MIN_VOLUME:
        return None
    t0 = end - LEAD_S
    if t0 < start + 86400:
        return None
    events = m.get("events") or [{}]
    return {"id": str(m.get("id")), "question": m.get("question", ""), "description": (m.get("description") or "")[:2500],
            "start": start, "end": end, "t0": t0, "yes_token": toks[0], "yes_won": prices[0] == 1.0,
            "volume": float(m.get("volumeNum") or 0), "event": str((events[0] or {}).get("id") or m.get("slug") or m.get("id")),
            "category": m.get("category") or ""}


def price_at(history: list, t0: int):
    """Last history point at or before t0, if it is at most 24 h old."""
    pts = [h for h in history if h.get("t", 0) <= t0]
    if not pts:
        return None
    last = max(pts, key=lambda h: h["t"])
    return float(last["p"]) if t0 - last["t"] <= MAX_AGE_S else None


def parse_p(text: str):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        v = float(json.loads(m.group(0))["p_yes"]) if m else None
    except (ValueError, KeyError, TypeError):
        return None
    return v if v is not None and 0.0 <= v <= 1.0 else None


def side_for(q, p, edge: float = EDGE):
    if q is None or p is None:
        return None
    if q - p >= edge:
        return "yes"
    if p - q >= edge:
        return "no"
    return None


def bet_return(side: str, p_yes: float, yes_won: bool, slip: float = SLIP):
    """Return per 1 USD, or None when the entry price is outside (0.01, 0.99)."""
    entry = (p_yes if side == "yes" else 1 - p_yes) + slip
    if entry >= 0.99 or entry <= 0.01:
        return None
    won = yes_won if side == "yes" else not yes_won
    return 1 / entry - 1 if won else -1.0


def control_side(market_id: str) -> str:
    return random.Random(f"pm:{market_id}").choice(("yes", "no"))


def summarize(rows: list) -> dict:
    """rows: one per market with a model bet: {'event','t0','ret','ret_stress','ctrl_ret','q','p','yes_won'}."""
    n = len(rows)
    if n < MIN_BETS:
        return {"verdict": f"too few ({n}/{MIN_BETS} bets)", "n": n}
    keys = [r["event"] for r in rows]                               # blocks = event
    rng = random.Random(20261124)
    ret = [r["ret"] for r in rows]
    paired = [r for r in rows if r["ctrl_ret"] is not None]
    diff = [r["ret"] - r["ctrl_ret"] for r in paired]
    brier_m = sum((r["q"] - r["yes_won"]) ** 2 for r in rows) / n
    brier_p = sum((r["p"] - r["yes_won"]) ** 2 for r in rows) / n
    out = {"n": n, "hit": sum(1 for x in ret if x > 0) / n, "mean_ret": sum(ret) / n,
           "mean_ret_stress": sum(r["ret_stress"] for r in rows if r["ret_stress"] is not None) /
           max(1, sum(1 for r in rows if r["ret_stress"] is not None)),
           "mean_diff": sum(diff) / len(diff) if diff else 0.0, "n_paired": len(paired),
           "p_ret_block": nb.block_bootstrap_p(ret, keys, rng),
           "p_diff_block": nb.block_bootstrap_p(diff, [r["event"] for r in paired], rng),
           "brier_model": brier_m, "brier_market": brier_p}
    ok = (out["mean_ret"] > 0 and out["p_ret_block"] < 0.05 and out["mean_ret_stress"] > 0 and out["mean_diff"] > 0
          and out["p_diff_block"] < 0.05 and brier_m < brier_p)
    out["verdict"] = "edge" if ok else "no edge shown"
    return out


def account_path(rows: list, stake: float, start: float = 147.0) -> dict:
    """Bets in t0 order, each stakes `stake` of equity at t0 and settles at end."""
    events = sorted([(r["t0"], 1, i) for i, r in enumerate(rows)] + [(r["end"], 0, i) for i, r in enumerate(rows)])
    cash, held, curve = start, {}, []
    for ts, kind, i in events:
        if kind == 1:
            amt = min(cash, stake * (cash + sum(held.values())))
            if amt <= 0:
                continue
            cash -= amt
            held[i] = amt
        elif i in held:
            cash += held.pop(i) * (1 + rows[i]["ret"])
            curve.append((ts, cash + sum(held.values())))
    months, peak, dd = {}, start, 0.0
    for ts, eq in curve:
        months[time.strftime("%Y-%m", time.gmtime(ts))] = eq
        peak, dd = max(peak, eq), min(dd, eq / max(peak, eq) - 1)
    prev, m3 = start, 0
    for k in sorted(months):
        m3 += months[k] >= 3 * prev
        prev = months[k]
    return {"end_equity": cash + sum(held.values()), "worst_drawdown": dd, "months_3x": m3, "month_end": months}
