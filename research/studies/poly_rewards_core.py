"""Pure logic for P3 (Polymarket liquidity-reward quoting). No network here; fetchers are in research/studies/poly_rewards.py.
Rules are locked in research/studies/protocol_poly_rewards_20261126.md. Kept under research/ (not core/) so a merge does not
redeploy production. Trade rows are poly_fv's: {'t', 'side', 'idx', 'price', 'size'}; yes_equiv() makes them side-agnostic."""
import heapq
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import poly_fv as pf   # noqa: E402

BUDGET = 147.0
OFFSET_FRACS = (0.25, 0.5, 0.75)      # quote distance as a fraction of the maximum spread v
PRIMARY_FRAC = 0.5
C_SINGLE = 3.0                         # single-sided scaling, valid for midpoints in [0.10, 0.90]
MIN_PAYOUT = 1.0                       # USD per day, per maker (docs: amounts below 1 USD are not paid)
REFRESH_S = 3600
MARK_S = 24 * 3600
MARK_S_SHORT = 3600
HAIRCUT = pf.HAIRCUT                   # 0.005 per share, applied against us when inventory is marked at the bid
QUOTE_LO, QUOTE_HI = 0.01, 0.99
STANDALONE_DAILY = 3 ** (1 / 30) - 1   # 0.0373: 3x in 30 days with no leverage
KILL_DAILY = 0.005
KILL_MARKETS = 10
MIN_TAPE_DAYS_VERDICT = 60
KILL_TAPE_DAYS = 14
ALPHA_TAPE = 0.05
CONTROL_N = 20
TRACK_N = 50


def score(v, s):
    """((v - s) / v) ** 2 for 0 <= s < v (both in cents), else 0. The in-game multiplier b is 1."""
    if v <= 0 or s < 0 or s >= v:
        return 0.0
    return ((v - s) / v) ** 2


def qmin(q1, q2, mid):
    """Docs rule: single-sided liquidity scores at 1/c only for midpoints in [0.10, 0.90]."""
    if 0.10 <= mid <= 0.90:
        return max(min(q1, q2), max(q1, q2) / C_SINGLE)
    return min(q1, q2)


def parse_levels(side):
    out = []
    for x in side or []:
        try:
            p, s = float(x["price"]), float(x["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 < p < 1 and s > 0:
            out.append((p, s))
    return out


def top_of_book(book):
    """(best_bid, best_ask, bids, asks) of the YES-token book; None when a side is empty."""
    bids, asks = parse_levels(book.get("bids")), parse_levels(book.get("asks"))
    bb = max((p for p, _ in bids), default=None)
    ba = min((p for p, _ in asks), default=None)
    return bb, ba, bids, asks


def mid_of(bb, ba):
    return None if bb is None or ba is None or ba < bb else (bb + ba) / 2


def band_q(bids, asks, mid, v):
    """(Q_one, Q_two) of everything resting in the band, all depth counted as fully scoring (conservative for us). Q_one =
    YES bids (= NO asks), Q_two = YES asks (= NO bids); spreads in cents."""
    q1 = sum(score(v, (mid - p) * 100) * s for p, s in bids)
    q2 = sum(score(v, (p - mid) * 100) * s for p, s in asks)
    return q1, q2


def competition(book, v):
    """(mid, Q_comp) with Q_comp = qmin of the aggregated depth (aggregation overstates the rivals, conservative)."""
    bb, ba, bids, asks = top_of_book(book)
    mid = mid_of(bb, ba)
    if mid is None:
        return None, None
    q1, q2 = band_q(bids, asks, mid, v)
    return mid, qmin(q1, q2, mid)


def unit_cost(mid, min_size, d_cents, mode):
    """USD for one min-size unit. two: YES bid + NO bid = min_size * (1 - 2d). single: the cheaper token's bid only."""
    d = d_cents / 100
    if mode == "two":
        return min_size * (1 - 2 * d)
    return min_size * (min(mid, 1 - mid) - d)


def our_q(k, min_size, v, d_cents, mid, mode):
    q = score(v, d_cents) * k * min_size
    return q if mode == "two" else qmin(q, 0.0, mid)


def reward_for(m, k, frac, mode):
    """Expected daily USD for k units of one market. m: pool, min_size, v, mid, qc."""
    if k <= 0:
        return 0.0
    d = frac * m["v"]
    q = our_q(k, m["min_size"], m["v"], d, m["mid"], mode)
    if mode == "single" and not (0.10 <= m["mid"] <= 0.90):
        return 0.0
    tot = q + m["qc"]
    return m["pool"] * q / tot if tot > 0 else 0.0


def qualifies(m, frac, mode):
    d = frac * m["v"]
    if not (0 < m["mid"] < 1) or m["v"] <= 0 or m["pool"] <= 0 or m["min_size"] <= 0:
        return False
    if m["mid"] - d / 100 < QUOTE_LO or m["mid"] + d / 100 > QUOTE_HI:
        return False
    if mode == "single" and not (0.10 <= m["mid"] <= 0.90):
        return False
    return unit_cost(m["mid"], m["min_size"], d, mode) <= BUDGET


def allocate(markets, frac, mode, budget=BUDGET):
    """Greedy by marginal reward per USD, one min-size unit at a time. Returns ({cond: k}, gross_daily_usd, spent)."""
    ms = {m["cond"]: m for m in markets if qualifies(m, frac, mode)}
    k = {c: 0 for c in ms}
    cost = {c: unit_cost(m["mid"], m["min_size"], frac * m["v"], mode) for c, m in ms.items()}

    def gain(c):
        return (reward_for(ms[c], k[c] + 1, frac, mode) - reward_for(ms[c], k[c], frac, mode)) / cost[c]
    heap = [(-gain(c), c) for c in ms]
    heapq.heapify(heap)
    spent = 0.0
    while heap:
        g, c = heapq.heappop(heap)
        if -g <= 0:
            break
        if spent + cost[c] > budget + 1e-9:
            continue
        spent += cost[c]
        k[c] += 1
        heapq.heappush(heap, (-gain(c), c))
    k = {c: n for c, n in k.items() if n}
    gross = sum(reward_for(ms[c], n, frac, mode) for c, n in k.items())
    return k, gross, spent


def after_min_payout(gross_daily):
    return gross_daily if gross_daily >= MIN_PAYOUT else 0.0


def decide(rows):
    """Probe decision (protocol step 5). rows: per (frac, mode): {gross_daily_pct, n_qualifying, ...} for the primary
    quote shape. Returns 'kill_complete' | 'kill_standalone' | 'standalone_pass'."""
    best = max((r["gross_pct"] for r in rows), default=0.0)
    nq = max((r["n_qualifying"] for r in rows), default=0)
    if best < KILL_DAILY or nq < KILL_MARKETS:
        return "kill_complete"
    if best < STANDALONE_DAILY:
        return "kill_standalone"
    return "standalone_pass"


def _last_before(trades, ts, t):
    import bisect
    i = bisect.bisect_right(ts, t) - 1
    return trades[i] if i >= 0 else None


def simulate_market(trades, t0, t1, v, frac, units, min_size, share_at, mid_at, daily_pool, refresh=REFRESH_S, mark_s=MARK_S,
                    haircut=HAIRCUT):
    """Paper two-sided quoting of one market. Every `refresh` seconds in [t0, t1) quote YES-bid mid-d and YES-ask mid+d (= NO
    bid) of units*min_size shares, d = frac*v cents. A bid fills in full on the first trade in the window whose yes-equivalent
    price is <= our bid (ask: >=); a filled side stays out until the next refresh. A fill is marked at the last yes-equivalent
    trade price within `mark_s` after the fill (at the bid: against us by `haircut`). Reward = daily_pool * share / 24 per
    hour with both sides live. Returns {day: {'reward', 'fill_pnl', 'fills', 'quote_hours'}}."""
    size = units * min_size
    d = frac * v / 100
    ts = [x["t"] for x in trades]
    import bisect
    out = {}
    T = t0
    while T + refresh <= t1:
        m = mid_at(T)
        if m is not None and QUOTE_LO <= m - d and m + d <= QUOTE_HI:
            B, A = m - d, m + d
            day = pf.day_of(T)
            row = out.setdefault(day, {"reward": 0.0, "fill_pnl": 0.0, "fills": 0, "quote_hours": 0.0})
            sh = share_at(T)
            if sh:
                row["reward"] += daily_pool * sh * refresh / 86400
            row["quote_hours"] += refresh / 3600
            lo, hi = bisect.bisect_left(ts, T), bisect.bisect_left(ts, T + refresh)
            fb = fa = None
            for x in trades[lo:hi]:
                y = pf.yes_equiv(x)
                if fb is None and y <= B + 1e-9:
                    fb = x["t"]
                if fa is None and y >= A - 1e-9:
                    fa = x["t"]
                if fb is not None and fa is not None:
                    break
            for t_fill, side in ((fb, "bid"), (fa, "ask")):
                if t_fill is None:
                    continue
                mk = _last_before(trades, ts, t_fill + mark_s)
                if mk is None:
                    continue
                y = pf.yes_equiv(mk)
                pnl = (y - haircut - B) if side == "bid" else (A - y - haircut)
                fday = pf.day_of(t_fill)
                frow = out.setdefault(fday, {"reward": 0.0, "fill_pnl": 0.0, "fills": 0, "quote_hours": 0.0})
                frow["fill_pnl"] += size * pnl
                frow["fills"] += 1
        T += refresh
    return out


def equity_stats(daily_returns):
    """Compound a list of daily returns: (ending equity from 1.0, worst drawdown)."""
    eq, peak, dd = 1.0, 1.0, 0.0
    for r in daily_returns:
        eq *= 1 + r
        peak = max(peak, eq)
        dd = max(dd, 1 - eq / peak)
    return eq, dd


def monthly(daily_mean):
    return (1 + daily_mean) ** 30 - 1 if daily_mean > -1 else -1.0


def combine(per_market, capital, days=None):
    """per_market: {cond: {day: row}}. Returns daily net return series (sum over markets / capital) for the days with data."""
    tot = {}
    for rows in per_market.values():
        for d, r in rows.items():
            x = tot.setdefault(d, [0.0, 0.0, 0])
            x[0] += r["reward"]
            x[1] += r["fill_pnl"]
            x[2] += r["fills"]
    ds = sorted(tot) if days is None else days
    return ds, [tot.get(d, [0, 0, 0])[0] / capital for d in ds], [tot.get(d, [0, 0, 0])[1] / capital for d in ds], \
        [tot.get(d, [0, 0, 0])[2] for d in ds]


def summarise(per_market, capital, days=None, boot=2000, seed=7):
    """Net / reward-only / fill-only daily means, day-clustered p, compounded equity, worst drawdown, 2x-haircut-free numbers."""
    ds, rew, fil, nf = combine(per_market, capital, days)
    net = [a + b for a, b in zip(rew, fil)]
    st = pf.cluster_stats(net, ds)
    eq, dd = equity_stats(net)
    n = len(net)
    return {"days": n, "reward_mean": sum(rew) / n if n else None, "fill_mean": sum(fil) / n if n else None,
            "net_mean": st["mean"], "net_se": st["se"], "net_p": st["p"], "monthly_net": monthly(st["mean"]) if n else None,
            "end_equity": eq, "worst_dd": dd, "fills": sum(nf)}
