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
# ---- addendum 2026-11-27 (protocol_poly_rewards_addendum_20261127.md): honest measurement ----
THROUGH = 0.001                        # a quote fills only on a print 0.1% THROUGH it (P1's rule), never on a touch
SNAP_S = 60                            # tape cadence (docs: the book is sampled once a minute)
FRESH_S = 180                          # a snapshot older than this is a gap: no quote, no reward
GAP_S = 150                            # a hole between two ticks longer than this is logged as a gap
TAIL_PRICE = 0.80                      # tail_stress scenario: unresolved inventory bought at or above this price goes to 0


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


def eligible_single(mid):
    """Docs (liquidity-rewards): single-sided liquidity scores only while the midpoint is inside [0.10, 0.90]."""
    return mid is not None and 0.10 <= mid <= 0.90


def resolution_of(market):
    """True / False = YES won / lost, None = not resolved. market: CLOB /markets/{condition} (closed, tokens[].winner)."""
    try:
        toks = market.get("tokens") or []
        if not market.get("closed") or len(toks) != 2:
            return None
        w = [bool(t.get("winner")) for t in toks]
        if w == [True, False]:
            return True
        if w == [False, True]:
            return False
    except (AttributeError, TypeError):
        pass
    return None


def fills_through(trades, B, A, size, want_bid=True, want_ask=True, through=THROUGH):
    """Partial fills of a resting YES bid at B and YES ask at A (= NO bid at 1 - A), `size` shares each, from trades in time
    order. A bid fills only on prints with yes-equivalent price <= B x (1 - through), by the printed size, until `size` is
    used; the ask the same on the NO leg ((1 - y) <= (1 - A) x (1 - through)). A touch (print at or inside the limit) fills
    nothing: it hides adverse selection (P1 rejected it). Returns {'bid': [(t, qty)], 'ask': [(t, qty)]}."""
    out = {"bid": [], "ask": []}
    rem = {"bid": size if want_bid else 0.0, "ask": size if want_ask else 0.0}
    for x in trades:
        y = pf.yes_equiv(x)
        if rem["bid"] > 1e-12 and y <= B * (1 - through) + 1e-12:
            q = min(rem["bid"], x["size"])
            out["bid"].append((x["t"], q))
            rem["bid"] -= q
        if rem["ask"] > 1e-12 and (1 - y) <= (1 - A) * (1 - through) + 1e-12:
            q = min(rem["ask"], x["size"])
            out["ask"].append((x["t"], q))
            rem["ask"] -= q
        if rem["bid"] <= 1e-12 and rem["ask"] <= 1e-12:
            break
    return out


def simulate_market(trades, t0, t1, v, frac, units, min_size, share_at, mid_at, daily_pool, refresh=REFRESH_S, mark_s=MARK_S,
                    haircut=HAIRCUT, mode="two", reward_step=REFRESH_S, yes_won=None, stress=False):
    """Paper quoting of one market (addendum 2026-11-27). Every `refresh` seconds in [t0, t1) quote at mid -/+ d (d = frac*v
    cents): mode 'two' = YES bid mid-d and YES ask mid+d (= NO bid) of units*min_size shares each; mode 'single' = only the
    cheaper token's bid, and only while the midpoint is inside [0.10, 0.90]. Fills: `fills_through` (a print 0.1% through the
    price, partial by printed size). Reward: every `reward_step` seconds while the quote is live (until the first side is
    completely filled) daily_pool * share_at(t, B, A) * step / 86400; single-sided pays only while the midpoint at that moment is
    in [0.10, 0.90]. Inventory is valued at resolution when `yes_won` is known (payoff 1 or 0, no haircut), else at the last
    yes-equivalent print within `mark_s` after the fill, against us by `haircut`; `fill_pnl_mtm` always uses the latter, and
    `stress` sends unresolved inventory bought at >= TAIL_PRICE to 0. Returns {day: {'reward', 'fill_pnl', 'fill_pnl_mtm',
    'fills', 'quote_hours', 'filled_shares', 'open_usd'}}."""
    size = units * min_size
    d = frac * v / 100
    ts = [x["t"] for x in trades]
    import bisect
    out = {}

    def row_of(day):
        return out.setdefault(day, {"reward": 0.0, "fill_pnl": 0.0, "fill_pnl_mtm": 0.0, "fills": 0, "quote_hours": 0.0,
                                    "filled_shares": 0.0, "open_usd": 0.0})
    T = t0
    while T + refresh <= t1:
        m = mid_at(T)
        ok = m is not None and QUOTE_LO <= m - d and m + d <= QUOTE_HI
        if ok and mode == "single":
            ok = eligible_single(m)
        if ok:
            B, A = m - d, m + d
            want_bid, want_ask = True, True
            if mode == "single":
                want_bid, want_ask = (m < 0.5), (m >= 0.5)
            lo, hi = bisect.bisect_left(ts, T), bisect.bisect_left(ts, T + refresh)
            fl = fills_through(trades[lo:hi], B, A, size, want_bid, want_ask)
            full = [f[-1][0] for f in fl.values() if f and sum(q for _, q in f) >= size - 1e-9]
            live_until = min(full) if full else T + refresh
            k = 0
            while k * reward_step < refresh:
                tt = T + k * reward_step
                k += 1
                if tt >= live_until:
                    break
                if mode == "single" and not eligible_single(mid_at(tt)):
                    continue
                row = row_of(pf.day_of(tt))
                sh = share_at(tt, B, A)
                if sh:
                    row["reward"] += daily_pool * sh * reward_step / 86400
                row["quote_hours"] += reward_step / 3600
            for side, chunks in fl.items():
                for t_fill, q in chunks:
                    cost = B if side == "bid" else 1 - A          # price paid per share of the token held
                    mk = _last_before(trades, ts, t_fill + mark_s)
                    if mk is None and yes_won is None:
                        continue
                    mtm = None
                    if mk is not None:
                        y = pf.yes_equiv(mk)
                        mtm = (y - haircut - B) if side == "bid" else (A - y - haircut)
                    if yes_won is not None:
                        yf = 1.0 if yes_won else 0.0
                        pnl = (yf - B) if side == "bid" else (A - yf)
                    elif stress and cost >= TAIL_PRICE:
                        pnl = -cost
                    else:
                        pnl = mtm
                    if mtm is None:
                        mtm = pnl
                    frow = row_of(pf.day_of(t_fill))
                    frow["fill_pnl"] += q * pnl
                    frow["fill_pnl_mtm"] += q * mtm
                    frow["fills"] += 1
                    frow["filled_shares"] += q
                    if yes_won is None:
                        frow["open_usd"] += q * cost
        T += refresh
    return out


def tick_gaps(ticks, gap_s=GAP_S):
    """ticks: tape snapshot times. Returns {'ticks', 'span_s', 'covered_s', 'coverage', 'gaps': [(from, to, seconds)] (first 50),
    'n_gaps', 'gap_s'}; a tick covers the SNAP_S seconds after it, a hole longer than gap_s is a gap."""
    ts = sorted(set(ticks))
    if len(ts) < 2:
        return {"ticks": len(ts), "span_s": 0, "covered_s": 0, "coverage": None, "gaps": [], "n_gaps": 0, "gap_s": 0}
    gaps = [(a, b, b - a) for a, b in zip(ts, ts[1:]) if b - a > gap_s]
    span = ts[-1] - ts[0]
    lost = sum(g[2] - SNAP_S for g in gaps)
    return {"ticks": len(ts), "span_s": span, "covered_s": span - lost, "coverage": (span - lost) / span if span else None,
            "gaps": gaps[:50], "n_gaps": len(gaps), "gap_s": sum(g[2] for g in gaps)}


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
    mtm = sum(r.get("fill_pnl_mtm", r["fill_pnl"]) for rows in per_market.values() for r in rows.values())
    open_usd = sum(r.get("open_usd", 0.0) for rows in per_market.values() for r in rows.values())
    net = [a + b for a, b in zip(rew, fil)]
    st = pf.cluster_stats(net, ds)
    eq, dd = equity_stats(net)
    n = len(net)
    return {"days": n, "reward_mean": sum(rew) / n if n else None, "fill_mean": sum(fil) / n if n else None,
            "net_mean": st["mean"], "net_se": st["se"], "net_p": st["p"], "monthly_net": monthly(st["mean"]) if n else None,
            "end_equity": eq, "worst_dd": dd, "fills": sum(nf),
            "fill_mtm_mean": mtm / capital / n if n and capital else None, "open_usd": open_usd}
