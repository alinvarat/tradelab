"""Pure calculations for the calendar_flow_1 study (protocol research/studies/protocol_calendar_flow_1_20261125.md).

No network here: fetchers and the merge step live in research/studies/calendar_flow.py. Bars are tuples
(t, o, h, l, c, ...) with t the bar open in epoch seconds. Every trade is a dict
{net, gross, cost, dcost, fund, entry, exit, side, hedge, reason} with net = gross - cost + fund, so the 2x-cost check
(net - dcost), the sanity assertion and the random control (the mirrored trade stored under "ctl") need no bars again.
Simulated research only.
"""
import bisect
import math
import random
import time
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from zoneinfo import ZoneInfo

from core import factory as fa
from core import news_backtest as nb
from core import screens as sc

CT = ZoneInfo("America/Chicago")
WEEK = 7 * 86400
SIZE = 0.20                      # share of equity per trade in the forward ledger
LEG_COST = 0.0014                # 0.05% taker + 0.02% slippage per side, one leg round trip
K_VARIANTS = {"R1": 1, "R2": 3, "R3": 1, "R4": 14, "R5": 1, "R6": 2}
K_TOTAL = sum(K_VARIANTS.values())        # 22
BAR = 0.05 / K_TOTAL                      # 0.00227
N_BOOT = 20000
QV_FLOOR = 1e8                            # R3: 30-day quote volume floor for a symbol-week row (top-10 members are far above)
WD = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def utc(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (utc(2021), utc(2023)), "validation": (utc(2023), utc(2025)), "test": (utc(2025), utc(2026, 11))}
BOUNDS_R2 = {"train": (utc(2020), utc(2023)), "validation": (utc(2023), utc(2025)), "test": (utc(2025), utc(2026, 11))}


# ------------------------------------------------------------------ funding, legs, trades
class Funding:
    """Settled funding of one perp. A settlement counts when t0 < settlement <= t1; stamps are rounded to the second
    (files carry a few milliseconds past the hour)."""

    def __init__(self, rows):
        pts = sorted((int(round(t)), r) for t, r in rows)
        self.t = [p[0] for p in pts]
        self.r = [p[1] for p in pts]

    def sum(self, t0, t1):
        a = bisect.bisect_right(self.t, int(round(t0)))
        b = bisect.bisect_right(self.t, int(round(t1)))
        return sum(self.r[a:b])

    def covers(self, t0, t1):
        """True when settlements cover the whole window: one within 9h of its start, one within 9h of its end and no
        hole above 9h between them (a missing month inside a long trade must not read as zero funding)."""
        h = 9 * 3600
        t0, t1 = int(round(t0)), int(round(t1))
        a = bisect.bisect_left(self.t, t0 - h)
        b = bisect.bisect_right(self.t, t1 + h)
        pts = self.t[a:b]
        if not pts or pts[0] > t0 + h or pts[-1] < t1 - h:
            return False
        return all(y - x <= h for x, y in zip(pts, pts[1:]))

    def pnl(self, side, t0, t1):
        """Funding pnl of a position: longs pay a positive rate, shorts receive it."""
        return -side * self.sum(t0, t1)


def leg_gain(side, entry, exit_):
    """Gain on the entry notional: long exit/entry - 1, short 1 - exit/entry (core.screens.short_gain)."""
    return exit_ / entry - 1 if side > 0 else sc.short_gain(entry, exit_)


def make_trade(side, entry, exit_px, cost, fund=0.0, hedge=None, reason="", dcost=None):
    """hedge = (btc_entry, btc_exit) of the opposite-side BTC leg, or None."""
    gross = leg_gain(side, entry, exit_px)
    if hedge:
        gross += leg_gain(-side, hedge[0], hedge[1])
    return {"net": gross - cost + fund, "gross": gross, "cost": cost, "dcost": cost if dcost is None else dcost,
            "fund": fund, "entry": entry, "exit": exit_px, "side": side, "hedge": list(hedge) if hedge else None,
            "reason": reason}


def contiguous(byt, t0, step, n):
    """Bars at t0, t0+step, ... up to n of them, stopping at the first missing one."""
    out = []
    for k in range(n):
        b = byt.get(t0 + k * step)
        if b is None:
            break
        out.append(b)
    return out


def walk(bars, side, stop_px, target_px=None):
    """Follow one position through bars (t, o, h, l, c). Returns (exit price, bar index, reason).
    The stop is checked first when one bar touches both stop and target; a bar that opens beyond the stop fills at its
    open (worse of stop and open). Otherwise the exit is the last bar's close ("time")."""
    for k, b in enumerate(bars):
        o, h, lo, c = b[1], b[2], b[3], b[4]
        if side > 0:
            if lo <= stop_px:
                return min(stop_px, o), k, "stop"
            if target_px is not None and h >= target_px:
                return target_px, k, "target"
        else:
            if h >= stop_px:
                return max(stop_px, o), k, "stop"
            if target_px is not None and lo <= target_px:
                return target_px, k, "target"
    return bars[-1][4], len(bars) - 1, "time"


def run_leg(bars, side, stop_px, target_px, step, fund, btc=None, fund_btc=None, hedge=False, n=None, entry=None):
    """One perp trade over `bars` with real funding, optionally hedged with an opposite BTC perp leg that closes at the
    close of the bar in which the coin leg closed. Returns a trade dict, or None when a price or funding is missing."""
    if not bars or fund is None:
        return None
    px, k, why = walk(bars, side, stop_px, target_px)
    if why == "time" and n is not None and len(bars) < n:
        why = "gap"
    t_in, t_out = bars[0][0], bars[k][0] + step
    if not fund.covers(t_in, t_out):
        return None
    f = fund.pnl(side, t_in, t_out)
    cost, hb = LEG_COST, None
    if hedge:
        b0, b1 = (btc or {}).get(t_in), (btc or {}).get(bars[k][0])
        if b0 is None or b1 is None or fund_btc is None or not fund_btc.covers(t_in, t_out):
            return None
        hb = (b0[1], b1[4])
        cost += LEG_COST
        f += fund_btc.pnl(-side, t_in, t_out)
    return make_trade(side, bars[0][1] if entry is None else entry, px, cost, f, hb, why)


def sane(rows, limit=20):
    """Problems that void a verdict (protocol S0): entry/exit <= 0, a short leg above +100%, net not equal to gross - cost + funding.
    A long leg (the long side of a gap fade, or the random-control long of a new perp) can legitimately gain over +100%."""
    bad = []
    for r in rows:
        for part in ("ret", "ctl"):
            for h, t in (r.get(part) or {}).items():
                if not isinstance(t, dict) or "entry" not in t:
                    continue
                px = [t["entry"], t["exit"]] + list(t.get("hedge") or [])
                tag = f"{r.get('symbol')} {r.get('ts')} {part}/{h}"
                if not all(isinstance(x, (int, float)) and x > 0 for x in px):
                    bad.append(f"{tag}: non-positive price {px}")
                elif t["side"] < 0 and leg_gain(-1, t["entry"], t["exit"]) > 1.0:
                    bad.append(f"{tag}: short gain above +100%")
                elif abs(t["net"] - (t["gross"] - t["cost"] + t["fund"])) > 1e-9:
                    bad.append(f"{tag}: net != gross - cost + fund")
        if len(bad) >= limit:
            break
    return bad


# ------------------------------------------------------------------ R1 stablecoin depeg reversion
STABLE_FEES = (("f0", 0.0), ("f2", 0.0002), ("f10", 0.0010))


def _stable_leg(path, side, spread, stop, band):
    """One stablecoin trade over the 1m bars `path` (entry bar first). Stop (bar high/low) first, then the target
    (a close within `band` of 1.0000, only when band is not None), else the close of the last bar. The spread is
    adverse on entry and on exit. Returns (entry, exit, bar index, reason)."""
    entry = path[0][1] * (1 + side * spread)
    stop_px = entry * (1 - side * stop)
    ex, why, k = None, "time", len(path) - 1
    for k, b in enumerate(path):
        o, h, lo, c = b[1], b[2], b[3], b[4]
        if side > 0 and lo <= stop_px:
            ex, why = min(stop_px, o), "stop"
        elif side < 0 and h >= stop_px:
            ex, why = max(stop_px, o), "stop"
        elif band is not None and abs(c - 1.0) <= band + 1e-9:
            ex, why = c, "target"
        else:
            continue
        break
    else:
        k, ex, why = len(path) - 1, path[-1][4], "time"
    return entry, ex * (1 - side * spread), k, why


def stable_rows(sym, bars, cool0=0.0, t_end=None, spread=1e-4, dev=1e-3, band=2e-4, stop=3e-3, hold=60,
                cooldown=1800, fees=STABLE_FEES):
    """bars: [(t, o, h, l, c)] 1m sorted. Signal: close deviates >= dev from 1.0000 and the 30-minute cooldown after the
    last exit has passed. Entry at the next bar's open (1 bp adverse), fade the deviation. Signals at t >= t_end are
    left to the next chunk (bars beyond t_end are only path context). Returns (rows, gaps, cooldown_until)."""
    byt = {b[0]: b for b in bars}
    ts = [b[0] for b in bars]
    rows, gaps, cool, i = [], 0, cool0, 0
    n = len(bars)
    while i < n:
        t, c = bars[i][0], bars[i][4]
        if t_end is not None and t >= t_end:
            break
        d = round(c - 1.0, 8)
        if t < cool or abs(d) < dev - 1e-9:
            i += 1
            continue
        te = t + 60
        if te not in byt:
            gaps += 1
            i += 1
            continue
        side = -1 if d > 0 else 1                       # d > 0: sell the stablecoin for USDT; d < 0: buy it
        path = contiguous(byt, te, 60, hold)
        entry, ex, k, why = _stable_leg(path, side, spread, stop, band)
        m_entry, m_ex, _mk, m_why = _stable_leg(path, -side, spread, stop, None)
        ret, ctl = {}, {}
        for name, f in fees:
            ret[name] = make_trade(side, entry, ex, 2 * f, 0.0, None, why, dcost=2 * (spread + f))
            ctl[name] = make_trade(-side, m_entry, m_ex, 2 * f, 0.0, None, m_why, dcost=2 * (spread + f))
        rows.append({"symbol": sym, "market": sym, "ts": te, "kind": "stable_revert", "dev": d, "side": side,
                     "exit_reason": why, "ret": ret, "ctl": ctl})
        exit_t = path[k][0] + 60
        cool = exit_t + cooldown
        i = max(i + 1, bisect.bisect_left(ts, exit_t))
    return rows, gaps, cool


# ------------------------------------------------------------------ R2 new perp first-week short
NEWPERP_VARIANTS = {"V1": (24, 168), "V2": (1, 24), "V3": (24, 72)}     # (entry offset, exit end offset) in hours after T0
NEWPERP_STOP = 0.35


def first_bar_is_listing(t0, archive_start=utc(2020)):
    """False when the first bar of the earliest file is the archive start (the symbol listed before 2020)."""
    return t0 > archive_start + 3600


def newperp_row(sym, h1, btc, fund_sym, fund_btc, stop=NEWPERP_STOP):
    """h1: [(t,o,h,l,c,qv)] 1h bars from the earliest file, sorted; btc: {t: bar} BTCUSDT 1h; fund_*: Funding.
    Returns (row or None, skipped variants). Each variant is a coin short hedged with a BTC long and stopped at
    1.35 x entry; the mirrored trade (coin long, BTC short) is the random-control leg."""
    if not h1:
        return None, 0
    t0 = h1[0][0]
    byt = {b[0]: b for b in h1}
    ret, ctl, skipped = {}, {}, 0
    for name, (a, e) in NEWPERP_VARIANTS.items():
        n = e - a
        bars = contiguous(byt, t0 + a * 3600, 3600, n)
        if not bars:
            continue                                    # the coin did not exist that long: not an event
        entry = bars[0][1]
        real = run_leg(bars, -1, entry * (1 + stop), None, 3600, fund_sym, btc, fund_btc, True, n)
        mirror = run_leg(bars, 1, entry * (1 - stop), None, 3600, fund_sym, btc, fund_btc, True, n)
        if real is None or mirror is None:
            skipped += 1
            continue
        ret[name], ctl[name] = real, mirror
    if not ret:
        return None, skipped
    return {"symbol": sym, "market": sym, "ts": t0, "kind": "newperp_short", "ret": ret, "ctl": ctl}, skipped


# ------------------------------------------------------------------ R3 weekend-move fade
def weekend_times(friday):
    """(F, S, X) epoch seconds for the Chicago calendar Friday `friday` (a datetime.date): F = Friday 16:00 CT (CME
    BTC close), S = Sunday 17:00 CT (CME reopen), X = Tuesday 17:00 CT (time exit). DST is handled by zoneinfo."""
    def at(d, h):
        return int(datetime(d.year, d.month, d.day, h, 0, tzinfo=CT).astimezone(timezone.utc).timestamp())
    return at(friday, 16), at(friday + timedelta(days=2), 17), at(friday + timedelta(days=4), 17)


def fridays(start_s, end_s):
    """Every Friday date (UTC calendar of start_s, Chicago Friday) whose S falls in [start_s, end_s)."""
    d = datetime.fromtimestamp(start_s, timezone.utc).date()
    d += timedelta(days=(4 - d.weekday()) % 7)
    out = []
    while True:
        s = weekend_times(d)[1]
        if s >= end_s:
            return out
        if s >= start_s:
            out.append(d)
        d += timedelta(days=7)


def weekend_rows(sym, h1, btc, fund_sym, fund_btc, start_s, end_s, floor=QV_FLOOR, hedge=True, gap_sigma=1.5):
    """One row per symbol-week with 30 days of history and 30d quote volume >= floor (the study ranks the top 10 per
    week across symbols). Signal rows (|gap| >= 1.5 sigma) also carry the faded trade: entry at open(S), target = the F
    price, stop a further |gap| against entry, time exit at the Tuesday bar close, BTC hedge for non-BTC symbols.
    Everything before F uses data strictly before F. Returns (rows, gaps)."""
    byt = {b[0]: b for b in h1}
    ts = [b[0] for b in h1]
    cum = [0.0]
    for b in h1:
        cum.append(cum[-1] + b[5])
    daily = {}
    for b in h1:
        daily[b[0] - b[0] % 86400] = b[4]               # close of the last bar of each UTC day
    rows, gaps = [], {"no_bar": 0, "short_history": 0, "trade_gap": 0}
    for d in fridays(start_s, end_s):
        F, S, X = weekend_times(d)
        lo, hi = bisect.bisect_left(ts, F - 720 * 3600), bisect.bisect_left(ts, F)
        if hi - lo < 600:
            gaps["short_history"] += 1
            continue
        qv30 = cum[hi] - cum[lo]
        if qv30 < floor:
            continue
        fb, sb = byt.get(F), byt.get(S)
        if fb is None or sb is None:
            gaps["no_bar"] += 1
            continue
        day_f = F - F % 86400
        rets = []
        for k in range(1, 31):
            dk = day_f - k * 86400
            if dk in daily and dk - 86400 in daily:
                rets.append(daily[dk] / daily[dk - 86400] - 1)
        sigma = stdev(rets) if len(rets) >= 25 else None
        gap = sb[1] / fb[1] - 1
        row = {"symbol": sym, "market": sym, "kind": "wk_cand", "F": F, "S": S, "ts": F, "qv30": qv30, "gap": gap,
               "sigma": sigma, "signal": False}
        if sigma and abs(gap) >= gap_sigma * sigma:
            side = -1 if gap > 0 else 1                 # fade: gap up = short
            entry = sb[1]
            n = (X - S) // 3600
            bars = contiguous(byt, S, 3600, n)
            hedged = hedge and sym != "BTCUSDT"
            real = run_leg(bars, side, entry * (1 - side * abs(gap)), fb[1], 3600, fund_sym, btc, fund_btc, hedged, n)
            mirror = run_leg(bars, -side, entry * (1 + side * abs(gap)), None, 3600, fund_sym, btc, fund_btc, hedged, n)
            if real is None or mirror is None:
                gaps["trade_gap"] += 1
            else:
                row.update(signal=True, ts=S, ret={"gapfade": real}, ctl={"gapfade": mirror})
        rows.append(row)
    return rows, gaps


def weekly_members(rows, top=10):
    """Signal rows of the `top` symbols by 30-day quote volume on each Friday (membership frozen at F). Returns
    (events as kind weekend_fade rows, number of weeks ranked, lowest member qv30)."""
    by_week = {}
    for r in rows:
        if r.get("kind") == "wk_cand":
            by_week.setdefault(r["F"], []).append(r)
    events, low = [], None
    for _f, rs in sorted(by_week.items()):
        rs = sorted(rs, key=lambda r: (-r["qv30"], r["symbol"]))[:top]
        for r in rs:
            low = r["qv30"] if low is None else min(low, r["qv30"])
            if r.get("signal"):
                events.append({**r, "kind": "weekend_fade"})
    return events, len(by_week), low


# ------------------------------------------------------------------ R5 / R6 Deribit expiry calendar
def last_friday(y, m):
    """datetime.date of the last Friday of the month."""
    nxt = datetime(y + (m == 12), m % 12 + 1, 1).date()
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 4) % 7)


def expiry_type(day_ts):
    """daily / weekly (a Friday) / monthly (last Friday) / quarterly (last Friday of Mar, Jun, Sep, Dec)."""
    d = datetime.fromtimestamp(day_ts, timezone.utc).date()
    if d == last_friday(d.year, d.month):
        return "quarterly" if d.month in (3, 6, 9, 12) else "monthly"
    return "weekly" if d.weekday() == 4 else "daily"


def last_friday_days(first_y, last_y_m):
    """UTC day starts (epoch s) of the last Friday of every month from Jan first_y to month last_y_m = (y, m)."""
    out, y, m = [], first_y, 1
    while (y, m) <= last_y_m:
        d = last_friday(y, m)
        out.append(int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def nearest_strike(price, strikes, step):
    """Listed strike (multiple of `step`) nearest to price; ties go to the lower strike. None when none qualifies."""
    cand = [k for k in (strikes or []) if abs(k / step - round(k / step)) < 1e-9]
    return min(cand, key=lambda k: (abs(k - price), k)) if cand else None


def pin_rows(sym, day_info, spot00, perp, fund, step, lo=0.003, hi=0.010, stop=0.008):
    """R5. day_info {day_start: {"strikes": [...] | None}}; spot00 {day_start: spot open at 00:00 UTC}; perp {t: 1m bar}.
    At E-8h with P = spot open and K the listed round strike nearest to P: |P-K|/P in [lo, hi] -> trade the perp toward K
    from the open of the 00:00 bar to the close of the 07:59 bar (the price at the 08:00:00 expiry), stop 0.8% adverse.
    With no listed strikes (API failure) the grid of multiples of `step` around P is used and counted.
    Returns (rows, counts)."""
    rows = []
    cnt = {"days": 0, "no_price": 0, "grid_strikes": 0, "signals": 0, "trade_gap": 0}
    for X in sorted(day_info):
        cnt["days"] += 1
        P, b0 = spot00.get(X), perp.get(X)
        if not P or b0 is None:
            cnt["no_price"] += 1
            continue
        K = nearest_strike(P, day_info[X].get("strikes"), step)
        if K is None:
            lo_k = math.floor(P / step) * step
            K = min((lo_k, lo_k + step), key=lambda k: (abs(k - P), k))
            cnt["grid_strikes"] += 1
        dist = abs(P - K) / P
        if not (lo - 1e-12 <= dist <= hi + 1e-12):
            continue
        side = 1 if K > P else -1
        bars = contiguous(perp, X, 60, 480)
        entry = bars[0][1]
        real = run_leg(bars, side, entry * (1 - side * stop), None, 60, fund, n=480)
        mirror = run_leg(bars, -side, entry * (1 + side * stop), None, 60, fund, n=480)
        if real is None or mirror is None:
            cnt["trade_gap"] += 1
            continue
        cnt["signals"] += 1
        rows.append({"symbol": sym, "market": sym, "ts": X, "kind": "expiry_pin", "etype": expiry_type(X),
                     "dist": dist, "src": "api" if day_info[X].get("strikes") else "grid",
                     "ret": {"pin": real}, "ctl": {"pin": mirror}})
    return rows, cnt


def unpin_rows(sym, days, perp, fund, stop=0.03):
    """R6. days: UTC day starts of last Fridays. Entry at the close of the 07:59 bar (the price at 08:00:00), exit 24h
    later at the close of the 07:59 bar of the next day, stop 3% adverse; V1 long, V2 short. The control of each
    variant is the opposite variant. Returns (rows, counts)."""
    rows, cnt = [], {"days": 0, "no_price": 0, "trade_gap": 0}
    for X in days:
        cnt["days"] += 1
        eb = perp.get(X + 8 * 3600 - 60)
        bars = contiguous(perp, X + 8 * 3600, 60, 1440)
        if eb is None or not bars:
            cnt["no_price"] += 1
            continue
        entry = eb[4]
        long_, short_ = (run_leg(bars, s, entry * (1 - s * stop), None, 60, fund, n=1440, entry=entry) for s in (1, -1))
        if long_ is None or short_ is None:
            cnt["trade_gap"] += 1
            continue
        rows.append({"symbol": sym, "market": sym, "ts": X + 8 * 3600, "kind": "expiry_unpin",
                     "ret": {"V1": long_, "V2": short_}, "ctl": {"V1": short_, "V2": long_}})
    return rows, cnt


# ------------------------------------------------------------------ R4 day-of-week legs on the daily panel
def _ret(close, a, b, s):
    pa, pb = close[a].get(s), close[b].get(s)
    return pb / pa - 1 if pa and pb else None


def top_by_volume(days, close, qv, top_n=30, min_qv=fa.MIN_QV, bench="BTCUSDT"):
    """Per day i the tradable coins (31+ days of history, average quote volume of the previous 20 days >= min_qv,
    exactly factory_crypto_1) ranked by that average, best top_n, decided with data up to day i's close."""
    hist, age, out = {}, {}, []
    for d in days:
        cand = []
        for s in close[d]:
            h = hist.setdefault(s, [])
            h.append(qv[d][s])
            if len(h) > 21:
                h.pop(0)
            age[s] = age.get(s, 0) + 1
            if s == bench or age[s] < 31:
                continue
            adv = mean(h[-21:-1])
            if adv >= min_qv:
                cand.append((adv, s))
        cand.sort(reverse=True)
        out.append([s for _a, s in cand[:top_n]])
    return out


def dow_legs(days, close, qv, fund_day, cost_mult=1.0, top_n=30, min_picks=5, bench="BTCUSDT", unit=fa.ONE_WAY_COST):
    """14 legs, each a daily series [(day_ts, r)] that is 0 on the other six weekdays. Holding UTC day d1 = close of the
    previous bar to close of d1 (the bar at d1). (a) long BTC: costs 2 units (entry + exit). (b) equal-weight top-30 coins
    minus BTC: costs 4 units and the real BTC perp funding of d1 for the short leg (fund_day[d1] = settled rates in
    (d1, d1+1d], short receives). Returns (series, number of (b) days without funding data, which are left flat)."""
    picks = top_by_volume(days, close, qv, top_n, bench=bench)
    out = {}
    for w in range(7):
        out[f"btc_long_{WD[w]}"] = []
        out[f"alt_minus_btc_{WD[w]}"] = []
    missing = 0
    for i in range(len(days) - 1):
        d0, d1 = days[i], days[i + 1]
        wd = time.gmtime(d1).tm_wday
        rb = _ret(close, d0, d1, bench) or 0.0
        alt = None
        if len(picks[i]) >= min_picks:
            alt = mean((_ret(close, d0, d1, s) or 0.0) for s in picks[i])
        for w in range(7):
            on = w == wd
            a = rb - 2 * unit * cost_mult if on else 0.0
            b = 0.0
            if on and alt is not None:
                f = fund_day.get(d1)
                if f is None:
                    missing += 1
                else:
                    b = alt - rb - 4 * unit * cost_mult + f
            out[f"btc_long_{WD[w]}"].append((d1, a))
            out[f"alt_minus_btc_{WD[w]}"].append((d1, b))
    return out, missing


def funding_by_day(fund, days):
    """{day_ts: settled rates in (day_ts, day_ts + 1 day]} for the days where the series covers the window."""
    out = {}
    for d in days:
        if fund.covers(d, d + 86400):
            out[d] = fund.sum(d, d + 86400)
    return out


def dow_report(series, series2x, bounds=BOUNDS, bar=BAR, n_boot=N_BOOT, seed=11):
    """Per leg: mean per active day in each split (base and 2x cost), block p on validation (20-day blocks over the
    calendar-day series that is flat on other days), 3x-month check (100% of equity, no leverage), same-sign rule."""
    out = {}
    for name, s in series.items():
        wd = WD.index(name.rsplit("_", 1)[1])
        s2 = dict(series2x[name])
        row = {}
        for sp, (a, b) in bounds.items():
            act = [r for t, r in s if a <= t < b and time.gmtime(t).tm_wday == wd]
            act2 = [s2[t] for t, r in s if a <= t < b and time.gmtime(t).tm_wday == wd]
            row[sp] = {"active_days": len(act), "mean_active": mean(act) if act else None,
                       "mean_active_2x": mean(act2) if act2 else None}
        val = [r for t, r in s if bounds["validation"][0] <= t < bounds["validation"][1]]
        p = fa.block_p(val, 20, n_boot, seed) if val else 1.0
        mm = fa.month_multiples([(t, r) for t, r in s if bounds["validation"][0] <= t < bounds["validation"][1]], 1)
        m = {k: row[k]["mean_active"] for k in ("train", "validation", "test")}
        same_sign = all(v is not None and v > 0 for v in m.values())
        row.update(p_block_validation=p, validation_months=len(mm), validation_months_3x=sum(x >= 3 for x in mm),
                   passed=bool(same_sign and p < bar and (row["validation"]["mean_active_2x"] or 0) > 0))
        out[name] = row
    return out


def weekend_contrast(days, close, bounds=BOUNDS, bench="BTCUSDT"):
    """Descriptive, no pass authority: mean gross BTC daily return on Sat+Sun vs Mon-Fri per split."""
    out = {}
    for sp, (a, b) in bounds.items():
        we, wk = [], []
        for i in range(len(days) - 1):
            d1 = days[i + 1]
            if not (a <= d1 < b):
                continue
            r = _ret(close, days[i], d1, bench)
            if r is not None:
                (we if time.gmtime(d1).tm_wday >= 5 else wk).append(r)
        out[sp] = {"weekend_mean": mean(we) if we else None, "weekday_mean": mean(wk) if wk else None,
                   "weekend_n": len(we), "weekday_n": len(wk)}
    return out


# ------------------------------------------------------------------ the judgement of one event rule
def _vals(rows, bounds, split, h, dbl=False):
    out = []
    for r in rows:
        if sc.split_of(r["ts"], bounds) != split:
            continue
        t = (r.get("ret") or {}).get(h)
        if t is not None:
            out.append((t["net"] - (t["dcost"] if dbl else 0.0), r))
    return out


def _m(x):
    return None if not x else mean(x)


def rule_report(rows, horizons, bounds=BOUNDS, bar=BAR, n_boot=N_BOOT, size=SIZE, seed=7):
    """Pass test of one event rule (protocol S0). `rows` need ts, symbol, market, kind, ret {h: trade}, ctl {h: trade}.
    Pass = validation mean > 0 with block p < bar, > 0 at double cost, > 0 without the best 1 and best 5 trades,
    test mean > 0; and >= 3 events a week for the verdict to be PASS (otherwise a pass is diagnostic only)."""
    out = {"rows": len(rows), "horizons": list(horizons)}
    bad = sane(rows)
    if bad:
        out.update(verdict="invalid", passed=False, problems=bad[:10])
        return out
    in_scope = [r for r in rows if sc.split_of(r["ts"], bounds) != "out"]
    weeks = (bounds["test"][1] - bounds["train"][0]) / WEEK
    vweeks = (bounds["validation"][1] - bounds["validation"][0]) / WEEK
    out["events_per_week"] = round(len(in_scope) / weeks, 3)
    out["validation_events_per_week"] = round(sum(1 for r in in_scope if sc.split_of(r["ts"], bounds) == "validation") / vweeks, 3)
    gate = out["events_per_week"] >= 3
    out["gate_3_per_week"] = gate
    j = sc.judge(rows, list(horizons), bounds, pick_trim=5)
    out.update(table=j["table"], integrity=j["integrity"], robust=j.get("robust"), pick=j.get("pick"))
    pick = j.get("pick")
    if pick is None:
        out.update(verdict=j["verdict"], passed=False)
        return out
    val = _vals(rows, bounds, "validation", pick)
    v = [x for x, _r in val]
    keys = [sc.day_key(r) for _x, r in val]
    p = nb.block_bootstrap_p(v, keys, random.Random(seed), n=n_boot)
    v2 = [x for x, _r in _vals(rows, bounds, "validation", pick, dbl=True)]
    test = [x for x, _r in _vals(rows, bounds, "test", pick)]
    robust = j.get("robust") or {}
    crit = {"validation_mean_positive": bool(v) and mean(v) > 0, "p_below_bar": p < bar,
            "double_cost_positive": bool(v2) and mean(v2) > 0,
            "without_best_1_and_5_positive": len(robust) == 2 and all(x > 0 for x in robust.values()),
            "test_mean_positive": bool(test) and mean(test) > 0}
    passed = all(crit.values())
    out.update(criteria=crit, passed_stats=passed, p_validation=p, bar=bar, n_boot=n_boot, passed=passed and gate,
               verdict="PASS" if passed and gate else ("stats pass but below the 3/week gate: diagnostic only" if passed else "fail"))
    splits = {}
    for sp in bounds:
        a = [x for x, _r in _vals(rows, bounds, sp, pick)]
        b = [x for x, _r in _vals(rows, bounds, sp, pick, dbl=True)]
        splits[sp] = {"n": len(a), "mean": _m(a), "mean_2x": _m(b), "worst": min(a) if a else None,
                      "best": max(a) if a else None}
    out["splits"] = splits
    series = sorted((r["ts"], size * x) for x, r in val)
    mm = fa.month_multiples(series, 1)
    out["validation_3x_month"] = {"months": len(mm), "months_3x": sum(m >= 3 for m in mm), "best_month": max(mm) if mm else None,
                                  "median_month": sorted(mm)[len(mm) // 2] if mm else None, "size": size, "leverage": 1}
    out["worst_trade_all_splits"] = min((t["net"] for r in in_scope for t in [(r.get("ret") or {}).get(pick)] if t), default=None)
    out["max_loss_per_trade_of_equity"] = None if out["worst_trade_all_splits"] is None else round(size * -min(0.0, out["worst_trade_all_splits"]), 5)
    rng = random.Random(20261125)
    cv, ct = [], []
    for r in rows:
        c = (r.get("ctl") or {}).get(pick)
        if c is None:
            continue                       # the control is only defined where a mirrored trade exists
        t = c if rng.random() < 0.5 else (r.get("ret") or {}).get(pick)
        sp = sc.split_of(r["ts"], bounds)
        if t is not None and sp == "validation":
            cv.append(t["net"])
        elif t is not None and sp == "test":
            ct.append(t["net"])
    beats = bool(v and cv and mean(v) > mean(cv))
    out["control"] = {"validation_mean": _m(cv), "test_mean": _m(ct), "n_validation": len(cv), "real_beats_control_validation": beats}
    crit["beats_random_control"] = beats
    out["criteria"] = crit
    out["passed_stats"] = passed = all(crit.values())
    out["passed"] = passed and gate
    out["verdict"] = "PASS" if passed and gate else ("stats pass but below the 3/week gate: diagnostic only" if passed else "fail")
    return out


def breakdown(rows, bounds, h, keyfn):
    """Descriptive: {group: {split: {n, mean}}} of horizon h net, grouped by keyfn(row)."""
    g = {}
    for r in rows:
        t = (r.get("ret") or {}).get(h)
        sp = sc.split_of(r["ts"], bounds)
        if t is None or sp == "out":
            continue
        s = g.setdefault(keyfn(r), {}).setdefault(sp, [])
        s.append(t["net"])
    return {k: {sp: {"n": len(v), "mean": mean(v)} for sp, v in d.items()} for k, d in sorted(g.items(), key=lambda kv: str(kv[0]))}
