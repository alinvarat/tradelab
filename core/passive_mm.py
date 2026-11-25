"""H3 screen: inventory-limited passive market making on small Binance USDT perps, simulated from aggTrades.
Pure calculations (no network, no files); the fetching is rows_h3_passive_mm in research/studies/run.py and the rule is
pre-registered in research/studies/RESULTS.md ('H3 screen'). One clip is one coin unit per fill, and every hour's money is divided by the
hour's first reference price, so P&L is a fraction of one clip's notional (0.001 = 10 bps of a clip; multiply by the clip in USDT).
"""
import hashlib
import time
from array import array
from bisect import bisect_left
from datetime import datetime, timezone

from core import screens as sc

MAKER_FEE = 0.0002          # per side, as specified
TAKER_FEE = 0.0005          # hourly flatten (Binance USD-M regular taker rate)
RULES = {"k1": 1, "k2": 2, "k4": 4, "k8": 8}      # quote distance from the reference trade, in ticks
CAP = 3                     # inventory limit in clips (a side switches off at the cap)
STEP = 60                   # quotes are re-posted every 60 s
LATENCY = 1.0               # a quote is live only 1 s after it was decided
MAX_AGE = 300               # no quote when the reference trade is older than 5 minutes
MIN_TRADES = 100            # a day with fewer trades cannot give a tick size: no row
SAMPLE_MOD, SAMPLE_REM = 10, 3        # sampled days: (epoch_day % 10) == 3
SEED = "h3-20261125"
N_SYMBOLS = 30
BONFERRONI = 0.05 / len(RULES)
MAJORS = ("BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "TRX", "AVAX", "LINK", "DOT", "LTC", "BCH", "1000SHIB",
          "SHIB", "TON", "UNI", "ATOM", "NEAR", "APT", "ETC", "FIL", "XLM", "HBAR", "SUI", "ARB", "OP", "INJ", "AAVE",
          "MATIC", "POL", "1000PEPE", "PEPE", "LDO", "MKR", "RUNE", "BTCDOM", "DEFI", "USDC")


def T(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (T(2022), T(2023)), "validation": (T(2023), T(2025)), "test": (T(2025), T(2026, 11))}
START, END = T(2022), T(2026, 11)


# ------------------------------------------------------------------ universe and sampled days
def pick_universe(symbols, exclude_bases=(), n=N_SYMBOLS, seed=SEED, majors=MAJORS):
    """n symbols chosen by a seeded hash from every USDT perp ever listed, minus majors and the exclude list."""
    skip = set(majors) | set(exclude_bases)
    ok = [s for s in set(symbols) if s.endswith("USDT") and s[:-4] not in skip and s[:-4]]
    return sorted(sorted(ok, key=lambda s: hashlib.sha256(f"{seed}:{s}".encode()).hexdigest())[:n])


def sample_days(start_s=START, end_s=END, mod=SAMPLE_MOD, rem=SAMPLE_REM):
    """UTC day starts in [start_s, end_s) whose epoch day number % mod == rem."""
    first = int(start_s // 86400)
    return [d * 86400.0 for d in range(first, int(end_s // 86400)) if d % mod == rem]


# ------------------------------------------------------------------ trades
def load_trades(rows):
    """rows: (ts_s, price, qty, buyer_is_maker) in file order -> (ts array, price array, notional). Sorted by time."""
    ts, px, notional, ordered = array("d"), array("d"), 0.0, True
    for t, p, q, _m in rows:
        if ts and t < ts[-1]:
            ordered = False
        ts.append(t)
        px.append(p)
        notional += p * q
    if not ordered:
        order = sorted(range(len(ts)), key=ts.__getitem__)
        ts, px = array("d", (ts[i] for i in order)), array("d", (px[i] for i in order))
    return ts, px, notional


def infer_tick(px):
    """Smallest positive gap between distinct traded prices (the day's tick size); 0.0 when it cannot be seen."""
    u = sorted(set(px))
    best = 0.0
    for a, b in zip(u, u[1:]):
        d = b - a
        if d > b * 1e-9 and (best == 0.0 or d < best):
            best = d
    return best


def reverse_day(ts, px, day_start):
    """Time-reversed copy of one day (control): the same prices and bounces in the opposite order."""
    c = 2 * day_start + 86400
    return array("d", (c - t for t in reversed(ts))), array("d", reversed(px))


# ------------------------------------------------------------------ simulation
def simulate_day(ts, px, day_start, tick, k, cap=CAP, step=STEP, latency=LATENCY, max_age=MAX_AGE, hours=24):
    """Quote a bid and an ask at (last trade seen before the step) -/+ k ticks every `step` seconds, live from
    `latency` seconds after the decision to the next step. A side fills (at its own price, one clip) only when a trade
    prints STRICTLY through it, at most once per side per step, never beyond +/-cap clips. Every hour starts flat and
    is flattened at its end at the hour's last trade price, one tick against us, as a taker. No position ever crosses
    an hour boundary, so none crosses a funding time (00/08/16 UTC): funding is zero by construction.
    Returns gross P&L (before fees, after the flatten tick), maker and taker notionals, fill counts and inventory risk."""
    eps = tick * 1e-3
    out = {"gross": 0.0, "maker_n": 0.0, "taker_n": 0.0, "fills": 0, "buys": 0, "sells": 0, "max_inv": 0,
           "abs_inv_sum": 0, "steps": 0, "steps_cap": 0, "worst_hour": 0.0, "flat_slip": 0.0, "flattens": 0}
    for h in range(hours):
        hs = day_start + h * 3600
        lo, hi = bisect_left(ts, hs), bisect_left(ts, hs + 3600)
        if hi == lo:
            continue
        inv, cash, mk, scale = 0, 0.0, 0.0, None     # inventory in coin units; money divided by `scale` at the end
        for s in range(3600 // step):
            t0 = hs + s * step
            idx = bisect_left(ts, t0)
            if idx == 0 or t0 - ts[idx - 1] > max_age:
                continue
            ref = px[idx - 1]
            bid, ask = ref - k * tick, ref + k * tick
            scale = scale or ref
            out["steps"] += 1
            out["abs_inv_sum"] += abs(inv)
            out["steps_cap"] += abs(inv) >= cap
            can_b, can_a = bid > 0, True
            for i in range(bisect_left(ts, t0 + latency), bisect_left(ts, t0 + step)):
                p = px[i]
                if can_b and inv < cap and p < bid - eps:
                    inv += 1
                    cash -= bid
                    mk += bid
                    can_b = False
                    out["buys"] += 1
                elif can_a and inv > -cap and p > ask + eps:
                    inv -= 1
                    cash += ask
                    mk += ask
                    can_a = False
                    out["sells"] += 1
                else:
                    continue
                out["fills"] += 1
                out["max_inv"] = max(out["max_inv"], abs(inv))
                if not (can_b or can_a):
                    break
        if scale is None:
            continue
        if inv:
            q = max(px[hi - 1] - tick, tick) if inv > 0 else px[hi - 1] + tick
            cash += inv * q
            out["taker_n"] += abs(inv) * q / scale
            out["flat_slip"] += abs(inv) * tick / scale
            out["flattens"] += 1
        out["maker_n"] += mk / scale
        out["gross"] += cash / scale
        out["worst_hour"] = min(out["worst_hour"], cash / scale)
    return out


def net_pnl(res, mult=1.0):
    """P&L after fees; mult=2 doubles both fees (the double-cost check)."""
    return res["gross"] - mult * (MAKER_FEE * res["maker_n"] + TAKER_FEE * res["taker_n"])


def process_day(ts, px, day_start, notional=0.0, rules=RULES):
    """One symbol-day -> a row for every rule and for its time-reversed control; None if the tick cannot be read."""
    if len(ts) < MIN_TRADES:
        return None
    tick = infer_tick(px)
    if tick <= 0:
        return None
    rts, rpx = reverse_day(ts, px, day_start)
    return {"ts": day_start, "tick": tick, "price": px[len(px) // 2], "trades": len(ts), "notional": notional,
            "res": {r: simulate_day(ts, px, day_start, tick, k) for r, k in rules.items()},
            "ctl": {r: simulate_day(rts, rpx, day_start, tick, k) for r, k in rules.items()}}


# ------------------------------------------------------------------ summary
def _mean(v):
    return round(sum(v) / len(v), 6) if v else None


def _table(rows, rules, bounds):
    out = {}
    for r in rules:
        out[r] = {}
        for sp in bounds:
            x = [w for w in rows if sc.split_of(w["ts"], bounds) == sp]
            net = [net_pnl(w["res"][r]) for w in x]
            steps = sum(w["res"][r]["steps"] for w in x)
            out[r][sp] = {
                "n": len(x), "mean_net": _mean(net), "mean_gross": _mean([w["res"][r]["gross"] for w in x]),
                "mean_control_net": _mean([net_pnl(w["ctl"][r]) for w in x]),
                "mean_net_2x_fees": _mean([net_pnl(w["res"][r], 2.0) for w in x]),
                "positive_days": round(sum(1 for v in net if v > 0) / len(net), 3) if net else None,
                "fills_per_day": _mean([w["res"][r]["fills"] for w in x]),
                "max_inv_mean": _mean([w["res"][r]["max_inv"] for w in x]),
                "mean_abs_inv": round(sum(w["res"][r]["abs_inv_sum"] for w in x) / steps, 4) if steps else None,
                "share_steps_at_cap": round(sum(w["res"][r]["steps_cap"] for w in x) / steps, 4) if steps else None,
                "worst_hour": round(min((w["res"][r]["worst_hour"] for w in x), default=0.0), 5),
                "worst_day": round(min(net, default=0.0), 5)}
    return out


def summarize(all_rows, rules=tuple(RULES), bounds=None, weeks=None):
    """Pick the rule with the best TRAIN mean, judge it on validation, report test. Pass needs ALL of: judge 'passed'
    (validation > 0 with block p < 0.05 clustered by UTC day, still > 0 without the best 1 and 5 symbol-days, test not
    negative), validation p < 0.05 / number of rules, validation > 0 with fees doubled, validation paired difference
    over the time-reversed control > 0, and >= 3 fills a week across the sample."""
    bounds = bounds or BOUNDS
    weeks = weeks or (END - START) / (7 * 86400)
    rows = [w for w in all_rows if w.get("res")]
    rules = list(rules)

    def judge_rows(f):
        return [{"ts": w["ts"], "symbol": w["symbol"], "ret": {r: {"net": f(w, r)} for r in rules}} for w in rows]
    base = sc.judge(judge_rows(lambda w, r: net_pnl(w["res"][r])), rules, bounds)
    double = sc.judge(judge_rows(lambda w, r: net_pnl(w["res"][r], 2.0)), rules, bounds)
    diff = sc.judge(judge_rows(lambda w, r: net_pnl(w["res"][r]) - net_pnl(w["ctl"][r])), rules, bounds)
    pick = base.get("pick")
    summ = {"line": "h3_passive_mm", "rows": len(rows), "symbol_days_per_week": round(len(rows) / weeks, 2),
            "symbols_with_rows": len({w["symbol"] for w in rows}), "table": _table(rows, rules, bounds),
            "base": base, "double_fees": double, "vs_reversed_control": diff, "pick": pick}
    if not pick:
        summ["verdict"] = base.get("verdict", "no data")
        return summ
    val = base["table"][pick]["validation"]
    val2 = double["table"][pick]["validation"]
    valc = diff["table"][pick]["validation"]
    fills_week = sum(w["res"][pick]["fills"] for w in rows) / weeks
    gates = {"judge_passed": base["verdict"] == "passed",
             "bonferroni": val["p"] is not None and val["p"] < BONFERRONI,
             "double_fees_validation_positive": val2["mean"] is not None and val2["mean"] > 0,
             "beats_reversed_control_validation": valc["mean"] is not None and valc["mean"] > 0,
             "fills_per_week_ge_3": fills_week >= 3}
    summ.update(gates=gates, fills_per_week=round(fills_week, 1), bonferroni_p=BONFERRONI,
                pnl_usd_per_day_per_100_clip=round(100 * (val["mean"] or 0), 4))
    years, by_sym = {}, {}
    for w in rows:
        years.setdefault(time.strftime("%Y", time.gmtime(w["ts"])), []).append(net_pnl(w["res"][pick]))
        by_sym.setdefault(w["symbol"], []).append(net_pnl(w["res"][pick]))
    summ["pick_by_year"] = {y: {"n": len(v), "mean_net": _mean(v)} for y, v in sorted(years.items())}
    summ["pick_by_symbol"] = {s: {"n": len(v), "mean_net": _mean(v)} for s, v in sorted(by_sym.items())}
    vol = sorted(w["notional"] for w in rows)
    if len(vol) >= 3:
        cut = [vol[len(vol) // 3], vol[2 * len(vol) // 3]]
        thirds = {"low": [], "mid": [], "high": []}
        for w in rows:
            thirds["low" if w["notional"] < cut[0] else "mid" if w["notional"] < cut[1] else "high"].append(
                net_pnl(w["res"][pick]))
        summ["pick_by_daily_volume_third"] = {"cuts_usdt": cut, **{k: {"n": len(v), "mean_net": _mean(v)}
                                                                    for k, v in thirds.items()}}
    summ["tick_bps_median"] = sorted(w["tick"] / w["price"] * 1e4 for w in rows)[len(rows) // 2]
    if all(gates.values()):
        summ["verdict"] = "passed"
    elif base["verdict"] == "killed" or not gates["double_fees_validation_positive"]:
        summ["verdict"] = "killed"
    else:
        summ["verdict"] = "inconclusive"
    return summ
