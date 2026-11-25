"""Family 5: gold and FX intraday on Dukascopy 1m BID/ASK candles and ticks at XM costs. Pure functions, standard library only.

Rules, splits, costs and the pass rule are locked in research/studies/protocol_fxgold_tick_20261125.md (written before any
candle or tick of this study was downloaded; the probes only looked at availability). Bars: dict of columns from
core.fxgold_data.load_bars: ts (UTC epoch of the minute start), bid o/h/l/c (bo bh bl bc), ask o/h/l/c (ao ah al ac), per symbol.
A signal is decided on the close of minute j and filled at the OPEN of minute j+1 on the real side of the book (long at the ask,
short at the bid); stops and targets trigger on the quote of the side that closes the position (a long exits on the bid).
Money: gross is the mid-to-mid return, cost is max(XM Standard spread, realised spread in + out averaged) as a fraction of the
entry price (no swap: every trade is closed before 21:00 UTC). net = gross - cost; the 2x stress is net - cost.
"""
import bisect
import math
import random
from datetime import date as _date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from core import broker_costs as bc
from core import sweep_stats as ss

LON, NYC = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")
SYMS = ("XAUUSD", "EURUSD", "GBPUSD", "USDJPY")
LEV = {"XAUUSD": 40.0, "EURUSD": 10.0, "GBPUSD": 10.0, "USDJPY": 10.0}       # nominal; K = 1 position at a time per symbol
MIN_UNITS = {"XAUUSD": 1.0, "EURUSD": 1000.0, "GBPUSD": 1000.0, "USDJPY": 1000.0}   # 0.01 lot: oz of gold / units of base currency
CFG = {"alpha": 0.05, "account_usd": 147.0,
       "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
       "pass": {"min_val_trades": 30, "min_test_trades": 20}}


def _ts(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (_ts(2016, 1, 1), _ts(2022, 1, 1)),
          "validation": (_ts(2022, 1, 1), _ts(2024, 7, 1)),
          "test": (_ts(2024, 7, 1), _ts(2026, 11, 20))}
PILOT_BOUNDS = {"train": (_ts(2023, 12, 1), _ts(2024, 12, 1)),          # gold-only pilot (protocol addendum 2026-11-25): same rules, shorter windows
                "validation": (_ts(2024, 12, 1), _ts(2025, 9, 1)),
                "test": (_ts(2025, 9, 1), _ts(2026, 11, 20))}


def use_pilot():
    BOUNDS.update(PILOT_BOUNDS)


MIN = 60
HARD_END_UTC = 21 * 3600          # every trade is closed before 21:00 UTC (XM rollover is 22:00 GMT)
N_CTRL = 5


# ------------------------------------------------------------------ calendar helpers
def loc(d, hh, mm, tz):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz).timestamp()


def day_list(D):
    """[(date, i0, i1)] per UTC day that has bars (i1 exclusive); weekend sessions that start Sunday evening are kept as their own day."""
    ts = D["ts"]
    out, i, n = [], 0, len(ts)
    while i < n:
        k = int(ts[i] // 86400)
        j = i
        while j < n and int(ts[j] // 86400) == k:
            j += 1
        out.append((_date.fromordinal(719163 + k), i, j))
        i = j
    return out


def ix(D, t):
    return bisect.bisect_left(D["ts"], t)


def mid_hi(D, j):
    return (D["bh"][j] + D["ah"][j]) * 0.5


def mid_lo(D, j):
    return (D["bl"][j] + D["al"][j]) * 0.5


def mid_c(D, j):
    return (D["bc"][j] + D["ac"][j]) * 0.5


def hard_end(D, d, t):
    return min(t, loc(d, 0, 0, timezone.utc) + HARD_END_UTC - MIN)


def xm_spread(sym):
    return bc.XM_SPREAD[sym]["standard"]


# ------------------------------------------------------------------ one trade on the book
def run_trade(D, sym, i, side, stop_d, tgt_d, trail_d, end_i):
    """Enter at the open of minute i on the real side (long ask, short bid), manage on minutes i..end_i. Distances in price units.
    A bar that touches both stop and target counts as the stop (pessimistic). A trailing stop trails the favourable quote
    extreme of completed bars. Returns a trade dict (without t/rule fields) or None."""
    ts = D["ts"]
    if end_i < i or end_i >= len(ts):
        return None
    bo, bh, bl, bc_ = D["bo"], D["bh"], D["bl"], D["bc"]
    ao, ah, al, ac = D["ao"], D["ah"], D["al"], D["ac"]
    pe = ao[i] if side > 0 else bo[i]
    s_in = ao[i] - bo[i]
    if pe <= 0 or s_in < 0:
        return None
    stop = pe - side * stop_d if stop_d else None
    tgt = pe + side * tgt_d if tgt_d else None
    ext = pe
    mfe = mae = 0.0
    px, xj, s_out = None, end_i, None
    for j in range(i, end_i + 1):
        if side > 0:
            adv, fav, op = bl[j], bh[j], bo[j]
            if stop is not None and adv <= stop:
                px = min(stop, op)
                s_out, xj = ao[j] - bo[j], j
                mae = max(mae, (pe - px) / pe)
                break
            if tgt is not None and fav >= tgt:
                px, s_out, xj = tgt, ao[j] - bo[j], j
                mfe = max(mfe, (px - pe) / pe)
                break
            mae = max(mae, (pe - adv) / pe)
            mfe = max(mfe, (fav - pe) / pe)
            if trail_d:
                ext = max(ext, fav)
                ns = ext - trail_d
                stop = ns if stop is None else max(stop, ns)
        else:
            adv, fav, op = ah[j], al[j], ao[j]
            if stop is not None and adv >= stop:
                px = max(stop, op)
                s_out, xj = ao[j] - bo[j], j
                mae = max(mae, (px - pe) / pe)
                break
            if tgt is not None and fav <= tgt:
                px, s_out, xj = tgt, ao[j] - bo[j], j
                mfe = max(mfe, (pe - px) / pe)
                break
            mae = max(mae, (adv - pe) / pe)
            mfe = max(mfe, (pe - fav) / pe)
            if trail_d:
                ext = min(ext, fav)
                ns = ext + trail_d
                stop = ns if stop is None else min(stop, ns)
    if px is None:
        px = bc_[end_i] if side > 0 else ac[end_i]
        s_out = ac[end_i] - bc_[end_i]
        xj = end_i
    gross_q = side * (px - pe) / pe
    half = 0.5 * (s_in + max(0.0, s_out))
    gross = gross_q + half / pe                       # mid-to-mid
    cost = max(xm_spread(sym), half) / pe
    return {"t": ts[i], "x": ts[xj] + MIN, "side": side, "gross": gross, "cost": cost, "fund": 0.0, "net": gross - cost,
            "mfe": max(0.0, mfe), "mae": max(0.0, mae), "pe": pe, "sp_in": s_in}


# ------------------------------------------------------------------ signals: (entry_i, side, stop_d, tgt_d, trail_d, end_i)
def _end_idx(D, d, entry_i, minutes):
    t = hard_end(D, d, D["ts"][entry_i] + minutes * MIN)
    return max(entry_i, ix(D, t + 1) - 1)


def _exit_cfg(ex, rd):
    if ex == "t120":
        return rd, None, None, 120
    if ex == "tp":
        return rd, 1.5 * rd, None, 240
    if ex == "trail":
        return rd, None, rd, 240
    raise ValueError(ex)


def sig_orb(D, sym, sess, w, mode, ex):
    """Opening-range breakout (brk) or failure fade (fail) of the first w minutes after 08:00 London (ldn) / 08:00 New York (ny)."""
    ts = D["ts"]
    for d, a, b in day_list(D):
        if d.weekday() >= 5:
            continue
        o = loc(d, 8, 0, LON if sess == "ldn" else NYC)
        i0, i1 = ix(D, o), ix(D, o + w * MIN)
        if i1 - i0 < 0.8 * w or i0 >= len(ts) or ts[i0] - o > 120 or i1 >= len(ts) or ts[i1] - (o + w * MIN) > 120:
            continue
        hi = max(mid_hi(D, j) for j in range(i0, i1))
        lo = min(mid_lo(D, j) for j in range(i0, i1))
        rng = hi - lo
        if rng <= 0:
            continue
        j_end = ix(D, o + 180 * MIN)
        j = i1
        while j < min(j_end, len(ts) - 2):
            mc = mid_c(D, j)
            side = 1 if mc > hi else (-1 if mc < lo else 0)
            if side:
                if mode == "brk":
                    rd = rng
                    entry = j + 1
                else:
                    ext = max(mid_hi(D, j), hi) if side > 0 else min(mid_lo(D, j), lo)
                    k, back = j + 1, None
                    while k <= min(j + 10, len(ts) - 2):
                        ext = max(ext, mid_hi(D, k)) if side > 0 else min(ext, mid_lo(D, k))
                        mk = mid_c(D, k)
                        if (side > 0 and mk <= hi) or (side < 0 and mk >= lo):
                            back = k
                            break
                        k += 1
                    if back is None:
                        break
                    rd = max(abs(ext - mid_c(D, back)), 0.25 * rng)
                    side, entry = -side, back + 1
                sd, td, tr, dur = _exit_cfg(ex, rd)
                yield (entry, side, sd, td, tr, _end_idx(D, d, entry, dur))
                break
            j += 1


def sig_sweep(D, sym, m, target):
    """Asia range (00:00 UTC to 07:00 London) swept after the 08:00 London open and reclaimed within m minutes: fade back to mid / the other side."""
    ts = D["ts"]
    for d, a, b in day_list(D):
        if d.weekday() >= 5:
            continue
        t0 = loc(d, 0, 0, timezone.utc)
        t1 = loc(d, 7, 0, LON)
        i0, i1 = ix(D, t0), ix(D, t1)
        if i1 - i0 < 0.7 * (t1 - t0) / MIN:
            continue
        ah_ = max(mid_hi(D, j) for j in range(i0, i1))
        al_ = min(mid_lo(D, j) for j in range(i0, i1))
        rng = ah_ - al_
        if rng <= 0:
            continue
        s, e = ix(D, loc(d, 8, 0, LON)), ix(D, loc(d, 11, 0, LON))
        up = dn = None                        # sweep start index
        up_x, dn_x = ah_, al_
        for j in range(s, min(e, len(ts) - 2)):
            if up is None and mid_hi(D, j) > ah_:
                up = j
            if dn is None and mid_lo(D, j) < al_:
                dn = j
            if up is not None and j - up <= m:
                up_x = max(up_x, mid_hi(D, j))
                if mid_c(D, j) <= ah_:
                    mc = mid_c(D, j)
                    sd = max(up_x - mc, 0.1 * rng)
                    td = (mc - (ah_ + al_) / 2) if target == "mid" else (mc - al_)
                    if td > 0:
                        yield (j + 1, -1, sd, td, None, max(j + 1, ix(D, hard_end(D, d, loc(d, 13, 0, LON)) + 1) - 1))
                        break
                    up = m + j + 1 and None
            if dn is not None and j - dn <= m:
                dn_x = min(dn_x, mid_lo(D, j))
                if mid_c(D, j) >= al_:
                    mc = mid_c(D, j)
                    sd = max(mc - dn_x, 0.1 * rng)
                    td = ((ah_ + al_) / 2 - mc) if target == "mid" else (ah_ - mc)
                    if td > 0:
                        yield (j + 1, 1, sd, td, None, max(j + 1, ix(D, hard_end(D, d, loc(d, 13, 0, LON)) + 1) - 1))
                        break
                    dn = None
            if up is not None and j - up > m and mid_c(D, j) > ah_:
                up = 10 ** 9
            if dn is not None and j - dn > m and mid_c(D, j) < al_:
                dn = 10 ** 9


def _sigma1(D, j, n=240):
    """Std of 1-minute mid returns over the n minutes before index j (price units per minute)."""
    a = max(1, j - n)
    r = [mid_c(D, k) - mid_c(D, k - 1) for k in range(a, j)]
    if len(r) < 30:
        return None
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))


def _last_weekdays_of_month(d, k=3):
    n, x = 0, d
    while True:
        x += timedelta(days=1)
        if x.month != d.month:
            return n < k
        if x.weekday() < 5:
            n += 1
            if n >= k:
                return False


def sig_fix(D, sym, kind, theta=None):
    """London 16:00 fixing window. cont: continue the 14:00-15:30 move through 15:55-16:05; me: the same only on the last 3 weekdays of the
    month; fade: fade the 15:54-15:59 move when it is >= theta sigma(5m), hold 15 minutes."""
    ts = D["ts"]
    for d, a, b in day_list(D):
        if d.weekday() >= 5:
            continue
        f = loc(d, 16, 0, LON)
        ia, ib, ic = ix(D, loc(d, 14, 0, LON)), ix(D, f - 30 * MIN), ix(D, f)
        if ic >= len(ts) - 20 or ts[ic] - f > 120 or ib - ia < 60:
            continue
        sg = _sigma1(D, ib)
        if not sg:
            continue
        if kind in ("cont", "me"):
            if kind == "me" and not _last_weekdays_of_month(d):
                continue
            r = mid_c(D, ib) - mid_c(D, ia)
            if r == 0:
                continue
            side = 1 if r > 0 else -1
            e = ix(D, f - 5 * MIN)
            yield (e, side, 3 * sg * math.sqrt(10), None, None, ix(D, f + 5 * MIN))
        else:
            i5 = ix(D, f - 6 * MIN)
            r5 = mid_c(D, ic - 1) - mid_c(D, i5)
            if abs(r5) >= theta * sg * math.sqrt(5):
                yield (ic, -1 if r5 > 0 else 1, 3 * sg * math.sqrt(15), None, None, ix(D, f + 15 * MIN))


def sig_round(D, sym, step, mode):
    """Gold round numbers every `step` USD: a minute that touches a level from one side. fade = it closed back on the near side (rejection);
    brk = it closed beyond the level. Stop and target 1 R, R = 3 x mean 1-minute range of the previous 60 minutes, exit after 60 minutes."""
    ts = D["ts"]
    for d, a, b in day_list(D):
        if d.weekday() >= 5:
            continue
        s, e = ix(D, loc(d, 7, 0, timezone.utc)), min(ix(D, loc(d, 19, 0, timezone.utc)), len(ts) - 2)
        last_hit = {}
        for j in range(max(s, a + 61), e):
            hi, lo, c = mid_hi(D, j), mid_lo(D, j), mid_c(D, j)
            p = mid_c(D, j - 1)
            lv_up = math.floor(hi / step) * step
            lv_dn = math.ceil(lo / step) * step
            ev = None
            if p < lv_up <= hi:
                ev = (lv_up, 1)                # touched from below
            elif p > lv_dn >= lo:
                ev = (lv_dn, -1)               # touched from above
            if not ev:
                continue
            lv, frm = ev
            if j - last_hit.get(lv, -10 ** 9) < 120:
                continue
            last_hit[lv] = j
            beyond = (c > lv) if frm > 0 else (c < lv)
            if (mode == "brk") != beyond:
                continue
            side = frm if mode == "brk" else -frm
            r = 3.0 * sum(mid_hi(D, k) - mid_lo(D, k) for k in range(j - 60, j)) / 60.0
            if r <= 0:
                continue
            yield (j + 1, side, r, r, None, max(j + 1, ix(D, hard_end(D, d, ts[j + 1] + 60 * MIN) + 1) - 1))


# ------------------------------------------------------------------ rule registry
def build_rules():
    """All pre-registered rules: {id: spec}. Symbol-level cells are rule x symbol."""
    rules = {}
    for sess in ("ldn", "ny"):
        for w in (15, 30, 60):
            for mode in ("brk", "fail"):
                for ex in ("t120", "tp", "trail"):
                    rules[f"orb_{sess}_{w}_{mode}_{ex}"] = {"fam": "A", "args": (sess, w, mode, ex), "syms": SYMS}
    for m in (15, 30):
        for tg in ("mid", "opp"):
            rules[f"sweep_{m}_{tg}"] = {"fam": "B", "args": (m, tg), "syms": SYMS}
    rules["fix_cont"] = {"fam": "D", "args": ("cont", None), "syms": SYMS}
    rules["fix_monthend"] = {"fam": "D", "args": ("me", None), "syms": SYMS}
    for th in (1.5, 3.0):
        rules[f"fix_fade_{th:g}"] = {"fam": "D", "args": ("fade", th), "syms": SYMS}
    for step in (50, 100):
        for mode in ("fade", "brk"):
            rules[f"round_{step}_{mode}"] = {"fam": "E", "args": (step, mode), "syms": ("XAUUSD",)}
    for mode in ("mom", "fade"):
        for th in (2.0, 4.0):
            for hold in (60, 300):
                rules[f"macro_{mode}_{th:g}_{hold}"] = {"fam": "C", "args": (mode, th, hold), "syms": SYMS}
    return rules


def signals(D, sym, spec):
    fam, a = spec["fam"], spec["args"]
    if fam == "A":
        return sig_orb(D, sym, *a)
    if fam == "B":
        return sig_sweep(D, sym, *a)
    if fam == "D":
        return sig_fix(D, sym, *a)
    if fam == "E":
        return sig_round(D, sym, *a)
    raise ValueError(fam)


def trades_for(D, sym, rid, spec, flip_seed=None):
    """All trades of one rule on one symbol. flip_seed: the random-side control (same entries, exits and distances, side drawn at random)."""
    rng = random.Random(flip_seed) if flip_seed is not None else None
    out = []
    last_exit = 0
    for entry, side, sd, td, tr, end_i in signals(D, sym, spec):
        if D["ts"][entry] < last_exit:
            continue                                   # one position at a time per symbol
        if rng is not None:
            side = 1 if rng.random() < 0.5 else -1
        tdict = run_trade(D, sym, entry, side, sd, td, tr, end_i)
        if tdict is None:
            continue
        tdict.update(rule=rid, sym=sym)
        last_exit = tdict["x"]
        out.append(tdict)
    return out


# ------------------------------------------------------------------ macro release minute, from per-second ticks
def macro_trades(events, sym, rid, mode, th, hold, sig_by_ev):
    """events: [{'ts','name','sec': [[dt,bid,ask]...] dt=-120..+1200 }]; sig_by_ev[ts] = sigma of 1-minute mid returns before the release.
    The release move is mid(t0+10s) - mid(t0-5s); if |move| >= th x sigma1 x sqrt(15/60)... see protocol: th x sigma1 x sqrt(1) per minute. Enter at
    t0+10s (long at the ask, short at the bid; mom = with the move, fade = against), stop = |move|, exit after `hold` seconds."""
    out = []
    for ev in events:
        sg = sig_by_ev.get(ev["ts"])
        sec = ev["sec"]
        if not sg or not sec:
            continue
        by = {r[0]: r for r in sec}
        a, b, e0 = by.get(-5), by.get(10), by.get(11)
        if not a or not b or not e0 or None in a[1:] or None in b[1:] or None in e0[1:]:
            continue
        m0, m1 = (a[1] + a[2]) / 2, (b[1] + b[2]) / 2
        mv = m1 - m0
        if abs(mv) < th * sg:
            continue
        side = (1 if mv > 0 else -1) * (1 if mode == "mom" else -1)
        pe = e0[2] if side > 0 else e0[1]
        s_in = e0[2] - e0[1]
        stop = pe - side * abs(mv)
        px, s_out, xs = None, None, 11 + hold
        mfe = mae = 0.0
        for dt in range(12, 11 + hold + 1):
            r = by.get(dt)
            if not r or r[1] is None:
                continue
            q = r[1] if side > 0 else r[2]          # the quote that closes the position
            adv = (pe - q) / pe * side
            mae = max(mae, adv)
            mfe = max(mfe, -adv)
            if (side > 0 and q <= stop) or (side < 0 and q >= stop):
                px, s_out, xs = q, r[2] - r[1], dt
                break
        if px is None:
            r = by.get(11 + hold)
            if not r or r[1] is None:
                continue
            px = r[1] if side > 0 else r[2]
            s_out = r[2] - r[1]
        half = 0.5 * (s_in + max(0.0, s_out))
        gross = side * (px - pe) / pe + half / pe
        cost = max(xm_spread(sym), half) / pe
        out.append({"t": ev["ts"] + 11, "x": ev["ts"] + xs + 1, "side": side, "gross": gross, "cost": cost, "fund": 0.0,
                    "net": gross - cost, "mfe": mfe, "mae": mae, "pe": pe, "sp_in": s_in, "rule": rid, "sym": sym, "ev": ev.get("name")})
    return out


# ------------------------------------------------------------------ evaluation of one cell
def rule_size(sym):
    return {"lev": LEV[sym], "k": 1}


def gate_cell(sym, trades):
    tr = ss.in_split(trades, *BOUNDS["train"])
    days = (BOUNDS["train"][1] - BOUNDS["train"][0]) / 86400.0
    price = sum(t["pe"] for t in tr) / len(tr) if tr else 0.0
    notional = MIN_UNITS[sym] * (price if sym in ("XAUUSD", "EURUSD", "GBPUSD") else 1.0)
    if sym == "GBPUSD" and tr:
        notional = MIN_UNITS[sym] * price
    ok, info = ss.gate(tr, {"size": rule_size(sym)}, CFG, days, min_notional_usd=notional)
    info["min_lot_usd"] = round(notional, 1)
    return ok, info


def mean_net(trades, a, b):
    return ss.mean([t["net"] for t in ss.in_split(trades, a, b)])
