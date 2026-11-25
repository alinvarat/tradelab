"""Event book: pure functions for the forward paper ledger (research/studies/protocol_event_book_20261125.md).

One 147 USD wallet trades several notice-driven components. Every closed trade is logged once with the net return of the
real trade and of 200 random-control trades (same side, size, hold, stop, entry time, other coins). Wallets, cohorts and
the daily series are then pure functions of that log, so a ledger can be recomputed at any time and tested offline.
No I/O, no network.
"""
import math
import random
import time

START_EQUITY = 147.0
BANK_MULT = 3.0            # bank and reset when equity reaches 3x the start
HALT_MULT = 0.4            # halt the cohort for the rest of its month at 0.4x
COHORT_DAYS = 30
LOSS_CAP = 0.25            # max loss of one risk unit as a share of equity: weight * stop <= LOSS_CAP
MAX_WEIGHT = 3.0           # notional / equity ceiling per risk unit
N_CONTROLS = 200
FEE_ROUND = 0.0011         # Bybit taker 0.055% per side
EXTRA_COST = 0.001         # assumed funding / borrow, as in protocol L1f
STOP_SLIP = 0.005          # fill beyond the stop level
MIN_NOTIONAL_USD = 5.0     # Bybit linear minimum order value (the live instrument value is used when known)
MAX_UNITS = 2              # open risk units at once (real ledger); worst real day = 2 stop-outs = ln(0.53) = -0.63
E_LO = 1.8                 # hard lower bound of the daily paired difference: real >= -0.7, control mean <= ln 3 = 1.1
E_HI = 1.2                 # wins above E_HI are clipped (safe side); scale E_LO + E_HI = 3


# ---------------------------------------------------------------- sizing
def kelly_fraction(returns: list) -> float:
    """Growth-optimal share of equity per unit return for i.i.d. trades: mean / E[r^2] (>= 0)."""
    if len(returns) < 2:
        return 0.0
    m2 = sum(r * r for r in returns) / len(returns)
    mean = sum(returns) / len(returns)
    return max(0.0, mean / m2) if m2 > 0 else 0.0


def frozen_weight(returns: list, stop: float, loss_cap: float = LOSS_CAP, max_weight: float = MAX_WEIGHT) -> dict:
    """Half-Kelly notional weight (notional / equity of one risk unit), capped so that a stop-out loses at most
    `loss_cap` of equity (weight * stop <= loss_cap) and at `max_weight`."""
    half = kelly_fraction(returns) / 2
    cap_loss = loss_cap / stop if stop > 0 else max_weight
    return {"half_kelly": round(half, 4), "loss_cap_weight": round(cap_loss, 4),
            "weight": round(min(half, cap_loss, max_weight), 4)}


def split_unit(weight: float, n_coins: int) -> float:
    """One notice = one risk unit: a notice naming several tradable coins splits the weight between them."""
    return weight / max(1, n_coins)


def order_qty(equity: float, weight: float, price: float, min_notional: float = MIN_NOTIONAL_USD,
              min_qty: float = 0.0, qty_step: float = 0.0):
    """Quantity for notional equity * weight, rounded down to the step; None when below the exchange minimums."""
    if price <= 0 or equity <= 0 or weight <= 0:
        return None
    qty = equity * weight / price
    if qty_step > 0:
        qty = math.floor(qty / qty_step + 1e-9) * qty_step
    if qty <= 0 or qty < min_qty or qty * price < min_notional:
        return None
    return qty


# ---------------------------------------------------------------- one trade
def trade_return(side: int, entry: float, bars: list, exit_px: float, stop: float, slip: float = STOP_SLIP,
                 fee: float = FEE_ROUND, extra: float = EXTRA_COST):
    """Net return per unit notional. side +1 long (entry = ask), -1 short (entry = bid); bars = [(high, low)] of the
    1-minute candles from entry to exit; exit_px = the quote at exit (bid for a long, ask for a short).
    A stop triggers when the adverse extreme reaches entry * (1 -/+ stop); the fill is `slip` beyond it.
    Returns (net, stopped)."""
    if entry <= 0:
        return None, False
    for hi, lo in bars:
        if side > 0 and lo <= entry * (1 - stop):
            return -(stop + slip) - fee - extra, True
        if side < 0 and hi >= entry * (1 + stop):
            return -(stop + slip) - fee - extra, True
    return side * (exit_px / entry - 1) - fee - extra, False


def random_controls(rng: random.Random, universe: list, exclude: set, n: int = N_CONTROLS) -> list:
    """n control symbols drawn with replacement from the tradable universe, never the event coin(s)."""
    pool = [s for s in universe if s not in exclude]
    return [rng.choice(pool) for _ in range(n)] if pool else []


# ---------------------------------------------------------------- wallet over the trade log
def _day(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def run_wallet(trades: list, which: int, start: float = START_EQUITY, bank: bool = True, t0: float = None,
               t1: float = None) -> dict:
    """Replay the closed-trade log for one ledger. which = -1 the real trades, k >= 0 control ledger k.
    A trade is {'entry_ts','exit_ts','w' (notional weight of the risk unit), 'ret' (real), 'ctrl' [200 returns],
    'min_notional'}. PnL is booked at exit on the equity at entry (trades overlap, so equity at entry is approximated by
    the equity when the trade was opened). Skips a trade whose notional is below the minimum or when halted.
    Returns {'equity', 'banked', 'halted', 'daily': {day: pnl_usd}, 'trades', 'skipped'}."""
    eq, banked, halted, skipped, used = start, 0, False, 0, 0
    daily: dict = {}
    pend = []                                   # (exit_ts, usd) booked at exit
    log_eq = {}                                 # day -> end-of-day equity after bookings
    sel = [t for t in sorted(trades, key=lambda t: t["entry_ts"])
           if (t0 is None or t["entry_ts"] >= t0) and (t1 is None or t["entry_ts"] < t1)]
    events = []
    for t in sel:
        events.append((t["entry_ts"], 0, t))
        events.append((t["exit_ts"], 1, t))
    events.sort(key=lambda e: (e[0], e[1]))
    open_usd = {}
    for ts, kind, t in events:
        key = id(t)
        if kind == 0:
            r = t["ret"] if which < 0 else (t["ctrl"][which] if which < len(t.get("ctrl", [])) else None)
            if halted or r is None or eq * t["w"] < t.get("min_notional", MIN_NOTIONAL_USD):
                skipped += 1
                continue
            open_usd[key] = eq * t["w"] * r
            used += 1
        else:
            usd = open_usd.pop(key, None)
            if usd is None:
                continue
            eq += usd
            daily[_day(ts)] = daily.get(_day(ts), 0.0) + usd
            if bank and eq >= BANK_MULT * start:
                banked += 1
                eq = start
            elif bank and eq <= HALT_MULT * start:
                halted = True
    return {"equity": round(eq, 4), "banked": banked, "halted": halted, "daily": daily, "trades": used, "skipped": skipped}


def daily_log_returns(trades: list, which: int, day0: float, day1: float, start: float = START_EQUITY) -> dict:
    """Reference ledger (no bank, no halt, compounding): daily log return per UTC day from day0 to day1."""
    run = run_wallet(trades, which, start=start, bank=False)
    eq, out = start, {}
    d = day0
    while d < day1:
        k = _day(d)
        pnl = run["daily"].get(k, 0.0)
        new = max(eq + pnl, 1e-6)
        out[k] = math.log(new / eq)
        eq = new
        d += 86400
    return out


def paired_series(trades: list, day0: float, day1: float, n_controls: int = N_CONTROLS) -> list:
    """Daily (real - mean of controls) log-return difference, one value per day."""
    real = daily_log_returns(trades, -1, day0, day1)
    ctrl = [daily_log_returns(trades, k, day0, day1) for k in range(n_controls)]
    out = []
    for k in real:
        c = sum(x[k] for x in ctrl) / max(1, len(ctrl))
        out.append(max(-E_LO, min(E_HI, real[k] - c)))
    return out


def monday_starts(first_ts: float, last_ts: float) -> list:
    """UTC Monday 00:00 timestamps from the first Monday on or after first_ts up to last_ts."""
    t = int(first_ts // 86400) * 86400
    while time.gmtime(t).tm_wday != 0 or t < first_ts:
        t += 86400
    out = []
    while t <= last_ts:
        out.append(t)
        t += 7 * 86400
    return out


def cohort_outcomes(trades: list, starts: list, now: float, n_controls: int = N_CONTROLS) -> list:
    """Per Monday cohort (a fresh wallet for COHORT_DAYS): real result against the controls' share reaching the bank."""
    rows = []
    for s in starts:
        end = s + COHORT_DAYS * 86400
        if end > now:
            status = "open"
        else:
            status = "complete"
        real = run_wallet(trades, -1, t0=s, t1=end)
        ctrl = [run_wallet(trades, k, t0=s, t1=end) for k in range(n_controls)]
        hit = lambda r: 1 if r["banked"] >= 1 else 0
        rows.append({"start": _day(s), "status": status, "real_equity": real["equity"], "real_banked": real["banked"],
                     "real_halted": real["halted"], "real_trades": real["trades"], "real_skipped": real["skipped"],
                     "control_hit_share": round(sum(hit(c) for c in ctrl) / max(1, len(ctrl)), 4),
                     "control_mean_equity": round(sum(c["equity"] for c in ctrl) / max(1, len(ctrl)), 4)})
    return rows
