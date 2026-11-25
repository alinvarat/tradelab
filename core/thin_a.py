"""Pure logic for Thin A (RESULTS.md 'Thin A'): listing and shock rules on small crypto exchanges, a matched random
control, and the registered verdict. No network here; the fetchers are in research/studies/thin_a.py.

Bars are tuples (open_ts_s, open, high, low, close, quote_volume), ascending, one per hour (or day) that had trades.
A bar is known at its close time, open_ts + width."""
import random
import time
from datetime import datetime, timezone

from core import screens as sc

HOUR, DAY = 3600, 86400


def _t(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (_t(2023), _t(2024, 7)), "validation": (_t(2024, 7), _t(2025, 7)), "test": (_t(2025, 7), _t(2026, 11))}
EVENT_START, EVENT_END = _t(2023), _t(2026, 11)
SCAN_START = _t(2022)
MIN_FIRST_DAY_QV = 10_000.0
FEE = {"kucoin": 0.001, "mexc": 0.001, "bitget": 0.001, "gate": 0.002}
RULE_HOLDS = {"A1": {"6h": 6, "24h": 24, "72h": 72}, "A2": {"24h": 24, "72h": 72}, "A3": {"6h": 6, "24h": 24},
              "A4": {"3d": 3, "7d": 7}, "A5": {"1h": 1, "4h": 4, "24h": 24}, "A6": {"4h": 4, "24h": 24, "72h": 72}}
N_RULES = len(RULE_HOLDS)


def side_cost(age_h: float, fee: float, mult: float = 1.0) -> float:
    """One side: taker fee plus a spread/slippage haircut of 1.0% under 24 h of listing age, 0.5% afterwards."""
    return (fee + (0.01 if age_h < 24 else 0.005)) * mult


def trade_net(p_in, p_out, age_in_h, age_out_h, fee, mult=1.0) -> float:
    return p_out / p_in - 1 - side_cost(age_in_h, fee, mult) - side_cost(age_out_h, fee, mult)


def listing_day(daily: list, scan_start: float = SCAN_START):
    """First UTC day (unix s) with quote volume > 0, or None when the pair was already trading in the first 7 days of the
    scan (not a listing in the window) or has no volume."""
    for b in daily:
        if b[5] > 0:
            return b[0] if b[0] > scan_start + 7 * DAY else None
    return None


def first_hour(hbars: list, d0: float):
    """Open timestamp of the first hourly bar with volume at or after the listing day, else None."""
    for b in hbars:
        if b[0] >= d0 and b[5] > 0:
            return b[0]
    return None


def price_at(bars: list, t: float, width: int = HOUR):
    """(close, stale_bars) of the last bar closed by time t (open_ts + width <= t); None when there is none.
    A missing hour carries the last close; stale_bars counts the hours carried (reported as gaps)."""
    lo, hi, best = 0, len(bars) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if bars[mid][0] + width <= t:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    if best < 0:
        return None
    return bars[best][4], int((t - (bars[best][0] + width)) // width)


def _median(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def listing_entries(hbars: list, hour0: float) -> list:
    """[(rule, entry_close_time, entry_price, age_hours)] for A1-A3, at most one per rule."""
    h = [b for b in hbars if b[0] >= hour0]
    out = []
    a1 = next((b for b in h if b[0] >= hour0 + 2 * HOUR and b[0] <= hour0 + 6 * HOUR), None)
    if a1:
        out.append(("A1", a1[0] + HOUR, a1[4], (a1[0] - hour0) / HOUR))
    run_high = 0.0
    prior = []
    got2 = got3 = False
    for b in h:
        age = (b[0] - hour0) / HOUR
        if not got2 and 3 <= age <= 47 and prior and b[4] <= 0.70 * run_high:
            out.append(("A2", b[0] + HOUR, b[4], age))
            got2 = True
        if not got3 and 6 <= age <= 71:
            win = [p for p in prior if p[0] >= b[0] - 24 * HOUR]
            if len(win) >= 6 and b[4] > max(p[2] for p in win) and b[5] >= 3 * _median([p[5] for p in prior]):
                out.append(("A3", b[0] + HOUR, b[4], age))
                got3 = True
        run_high = max(run_high, b[2])
        prior.append(b)
    return out


def shock_entries(hbars: list, first_ts: float, up_ret=0.08, down_ret=-0.12, vol_x=10.0, min_qv=5000.0) -> list:
    """[(rule, entry_time, entry_open, age_hours)] for A5 (up shock) and A6 (down shock). Entry is the next bar's open
    (that bar must exist); the bar volume is compared with the median of the trailing 168 h bars (>= 48 bars needed);
    pair age >= 30 days; one entry per rule per 24 h."""
    out, last = [], {"A5": -1e18, "A6": -1e18}
    by_ts = {b[0]: b for b in hbars}
    j = 0
    for b in hbars:
        if b[0] < first_ts + 30 * DAY or b[1] <= 0:
            continue
        r = b[4] / b[1] - 1
        rule = "A5" if r >= up_ret else ("A6" if r <= down_ret else None)
        if not rule or b[5] < min_qv or b[0] - last[rule] < DAY:
            continue
        while j < len(hbars) and hbars[j][0] < b[0] - 168 * HOUR:
            j += 1
        trail = [x[5] for x in hbars[j:] if x[0] < b[0]]
        if len(trail) < 48 or b[5] < vol_x * _median(trail):
            continue
        nxt = by_ts.get(b[0] + HOUR)
        if not nxt:
            continue
        last[rule] = b[0]
        out.append((rule, nxt[0], nxt[1], (nxt[0] - first_ts) / HOUR))
    return out


def control_net(bars, lo, hi, hold_s, fee, mult, rng, k=5, width=HOUR):
    """Mean net of k random entries (bar close, same hold and costs) with entry close time in [lo, hi - hold]."""
    cand = [b for b in bars if b[5] > 0 and lo <= b[0] + width <= hi - hold_s]
    if not cand:
        return None
    vals = []
    for b in rng.sample(cand, min(k, len(cand))):
        out = price_at(bars, b[0] + width + hold_s, width)
        if out:
            age = (b[0] + width - lo) / HOUR
            vals.append(trade_net(b[4], out[0], max(age, 24.0), max(age, 24.0) + hold_s / HOUR, fee, mult))
    return sum(vals) / len(vals) if vals else None


def make_row(symbol, venue, rule, entry_ts, entry_px, age_h, bars, holds, ctl_window, width=HOUR, flat_age=False):
    """One event row with a result per hold. ctl_window = (lo, hi) for the same-pair random control."""
    fee = FEE[venue]
    rng = random.Random(f"{symbol}:{rule}")
    ret, gaps = {}, 0
    for name, units in holds.items():
        hold_s = units * (DAY if width == DAY else HOUR)
        out = price_at(bars, entry_ts + hold_s, width)
        if not out or out[0] <= 0 or entry_px <= 0:
            continue
        a_in = 0.0 if flat_age else age_h
        a_out = 0.0 if flat_age else age_h + hold_s / HOUR
        net = trade_net(entry_px, out[0], a_in, a_out, fee, 1.0)
        ctl = control_net(bars, ctl_window[0], ctl_window[1], hold_s, fee, 1.0, rng, width=width)
        ret[name] = {"net": net, "net2": trade_net(entry_px, out[0], a_in, a_out, fee, 2.0), "gross": out[0] / entry_px - 1,
                     "ctl": ctl, "excess": None if ctl is None else net - ctl}
        gaps += out[1]
    if not ret:
        return None
    return {"symbol": f"{venue}:{symbol}", "venue": venue, "rule": rule, "kind": rule, "ts": entry_ts, "age_h": round(age_h, 2),
            "stale_bars": gaps, "ret": ret}


def listing_rows(venue, base, daily, hbars, gate=False):
    """All A1-A4 rows for one pair. `daily` are daily bars from 2022-01-01 and `hbars` hourly bars from the listing
    (None for Gate, which only has A4). Returns (rows, skip_reason)."""
    d0 = listing_day(daily)
    if d0 is None:
        return [], "not a listing in the window"
    if not (EVENT_START <= d0 < EVENT_END):
        return [], "listing outside 2023-01..2026-10"
    if gate:
        later = [b for b in daily if b[0] >= d0]
        if len(later) < 3 or later[0][5] < MIN_FIRST_DAY_QV:
            return [], "low first-day volume or too short"
        entry = later[1] if later[1][0] == d0 + DAY else None
        if not entry:
            return [], "no day d0+1"
        row = make_row(base, venue, "A4", entry[0] + DAY, entry[4], 0.0, later, RULE_HOLDS["A4"],
                       (d0 + 5 * DAY, d0 + 40 * DAY), width=DAY, flat_age=True)
        return ([row] if row else []), "no exit price"
    hour0 = first_hour(hbars, d0)
    if hour0 is None:
        return [], "no hourly bars"
    qv24 = sum(b[5] for b in hbars if hour0 <= b[0] < hour0 + 24 * HOUR)
    if qv24 < MIN_FIRST_DAY_QV:
        return [], "low first-day volume"
    rows = []
    for rule, ts, px, age in listing_entries(hbars, hour0):
        r = make_row(base, venue, rule, ts, px, age, hbars, RULE_HOLDS[rule], (hour0 + 10 * DAY, hour0 + 40 * DAY))
        if r:
            rows.append(r)
    return rows, ""


def shock_rows(venue, base, hbars):
    """A5/A6 rows for a mid-rank pair with a long hourly history."""
    if not hbars:
        return []
    first_ts = hbars[0][0]
    rows = []
    for rule, ts, px, age in shock_entries(hbars, first_ts):
        r = make_row(base, venue, rule, ts, px, max(age, 24.0), hbars, RULE_HOLDS[rule], (first_ts + 30 * DAY, hbars[-1][0] + HOUR))
        if r:
            rows.append(r)
    return rows


# ------------------------------------------------------------------ verdict
def _mean(v):
    return sum(v) / len(v) if v else None


def verdict(rows: list, holds: list, n_rules: int = N_RULES, bounds: dict = BOUNDS, seed: int = 7) -> dict:
    """Registered verdict for one rule (RESULTS.md 'Thin A'): horizon picked on train by the mean without its best 5
    events; pass needs validation net > 0 with block p < 0.05 / n_rules, double cost > 0, > 0 without the best 1 and 5,
    excess over the control > 0, test > 0 and >= 3 events a week in validation; kill on validation <= 0, p > 0.2 or
    double-cost / trimmed <= 0."""
    rng = random.Random(seed)
    check = sc.integrity(rows, holds, bounds)
    by_split = {sp: [r for r in rows if sc.split_of(r["ts"], bounds) == sp] for sp in bounds}
    per_venue_split = {}
    for r in rows:
        k = f"{r['venue']}/{sc.split_of(r['ts'], bounds)}"
        per_venue_split[k] = per_venue_split.get(k, 0) + 1
    table = {}
    for h in holds:
        t = {}
        for sp, rs in by_split.items():
            v = [r["ret"][h]["net"] for r in rs if h in r["ret"]]
            t[sp] = {"n": len(v), "mean": None if not v else round(_mean(v), 5)}
        table[h] = t
    out = {"integrity": check, "per_venue_split": per_venue_split, "table": table}
    if not check["ok"]:
        return {**out, "pick": None, "verdict": "invalid data: " + "; ".join(check["problems"])}

    def tr(h):
        v = sorted(r["ret"][h]["net"] for r in by_split["train"] if h in r["ret"])
        v = v[:-5] if len(v) > 5 else v
        return _mean(v)
    ok = [h for h in holds if tr(h) is not None]
    if not ok:
        return {**out, "pick": None, "verdict": "no data"}
    pick = max(ok, key=tr)
    val = [r for r in by_split["validation"] if pick in r["ret"]]
    v = [r["ret"][pick]["net"] for r in val]
    keys = [sc.day_key(r) for r in val]
    p = sc.block_bootstrap_p(v, keys, rng) if v else 1.0
    srt = sorted(v)
    trimmed = {f"without_best_{d}": _mean(srt[:-d]) for d in (1, 5) if len(srt) > d}
    v2 = [r["ret"][pick]["net2"] for r in val]
    ex = [r["ret"][pick]["excess"] for r in val if r["ret"][pick]["excess"] is not None]
    test = [r["ret"][pick]["net"] for r in by_split["test"] if pick in r["ret"]]
    weeks = (bounds["validation"][1] - bounds["validation"][0]) / (7 * DAY)
    res = {"validation_mean": _mean(v), "validation_p": round(p, 4), "validation_double_cost": _mean(v2), **trimmed,
           "validation_excess_over_control": _mean(ex), "validation_n_control": len(ex), "test_mean": _mean(test),
           "test_n": len(test), "per_week_validation": round(len(v) / weeks, 2),
           "weeks_all": round(sum(len(x) for x in by_split.values()) / ((bounds["test"][1] - bounds["train"][0]) / (7 * DAY)), 2)}
    passed = (bool(v) and _mean(v) > 0 and p < 0.05 / n_rules and (_mean(v2) or 0) > 0
              and all((x or 0) > 0 for x in trimmed.values()) and (_mean(ex) or 0) > 0
              and test and _mean(test) > 0 and res["per_week_validation"] >= 3)
    killed = (not v) or _mean(v) <= 0 or p > 0.2 or (_mean(v2) or 0) <= 0 or any((x or 0) <= 0 for x in trimmed.values())
    return {**out, "pick": pick, **res, "verdict": "pass" if passed else ("killed" if killed else "inconclusive")}


def audit_rows(rows: list, k: int = 8) -> list:
    """The k most extreme rows (by net at the best horizon of each row), so impossible values are read by a human."""
    flat = [(max(x["net"] for x in r["ret"].values()), r) for r in rows]
    flat.sort(key=lambda z: -z[0])
    return [{"symbol": r["symbol"], "rule": r["rule"], "ts": time.strftime("%Y-%m-%d %H:%M", time.gmtime(r["ts"])),
             "best_net": round(n, 3), "ret": {h: round(x["gross"], 3) for h, x in r["ret"].items()}} for n, r in flat[:k]]


def summarize(rows: list, gaps: dict = None) -> dict:
    out = {"rows": len(rows), "per_rule": {}, "bonferroni_alpha": round(0.05 / N_RULES, 5), "gaps": gaps or {}}
    for rule, holds in RULE_HOLDS.items():
        rs = [r for r in rows if r["rule"] == rule]
        out["per_rule"][rule] = verdict(rs, list(holds)) if rs else {"verdict": "no data", "rows": 0}
        if rs:
            out["per_rule"][rule]["audit_top"] = audit_rows(rs)
    return out


# ------------------------------------------------------------------ forward collectors (protocol_thin_a_forward.md)
F2_GAP_MIN = 0.015            # executable gap needed on top of the 0.7% cost proxy before a row is stored
F2_MIN_SIZE_USD = 30.0
F2_COLLISION = 0.25           # a mid-price ratio beyond 25% is a ticker collision, audited and never traded
F1_WATCH_S = 72 * HOUR
F3_OFFSETS = (HOUR, 4 * HOUR, 24 * HOUR)


def diff_listings(seen: dict, current: dict, now: float, missing: dict) -> tuple:
    """seen/current: {venue: {base: first_seen_ts or any}} and {venue: set(base)}. Returns (new, gone, seen, missing).
    A pair is new when absent from `seen`; a venue with an empty `current` (fetch failure) changes nothing. A seen pair is
    'gone' after two consecutive polls without it. The first call (empty `seen` for the venue) only seeds."""
    new, gone = [], []
    for venue, bases in current.items():
        if not bases:
            continue
        s = seen.setdefault(venue, {})
        m = missing.setdefault(venue, {})
        seeding = not s
        for b in sorted(bases):
            if b not in s:
                s[b] = now
                if not seeding:
                    new.append((venue, b))
            m.pop(b, None)
        for b in list(s):
            if b not in bases:
                m[b] = m.get(b, 0) + 1
                if m[b] == 2:
                    gone.append((venue, b))
    return new, gone, seen, missing


def mid_ratio_ok(mid_a: float, mid_b: float) -> bool:
    return mid_a > 0 and mid_b > 0 and abs(mid_a / mid_b - 1) <= F2_COLLISION


def exec_gap(small: dict, ref: dict):
    """small/ref: {'bid','ask','bid_sz','ask_sz'} (sizes in base units). Positive gap = the small venue is dear:
    sell there at its bid, buy at the reference ask. Returns (gap, side, size_usd) of the better direction or None."""
    best = None
    for side, sell, buy in (("sell_small", small, ref), ("buy_small", ref, small)):
        if not (sell.get("bid", 0) > 0 and buy.get("ask", 0) > 0):
            continue
        gap = sell["bid"] / buy["ask"] - 1
        size = min(sell.get("bid_sz", 0) * sell["bid"], buy.get("ask_sz", 0) * buy["ask"])
        if best is None or gap > best[0]:
            best = (gap, side, size)
    return best


def f2_candidates(small_books: dict, ref_books: dict, status: dict, prev: set) -> tuple:
    """small_books/ref_books: {base: quote dict}. Returns (candidates, n_compared, n_collisions). A candidate has an
    executable gap >= F2_GAP_MIN with top-of-book size >= F2_MIN_SIZE_USD on both sides; `persist` is True when the same
    base was a candidate in the previous poll; `status` carries deposit/withdraw flags (None = unknown)."""
    out, n, coll = [], 0, 0
    for base, s in small_books.items():
        r = ref_books.get(base)
        if not r:
            continue
        n += 1
        mid_s, mid_r = (s["bid"] + s["ask"]) / 2, (r["bid"] + r["ask"]) / 2
        if not mid_ratio_ok(mid_s, mid_r):
            coll += 1
            continue
        g = exec_gap(s, r)
        if g and g[0] >= F2_GAP_MIN and g[2] >= F2_MIN_SIZE_USD:
            out.append({"base": base, "gap": round(g[0], 5), "side": g[1], "size_usd": round(g[2], 1),
                        "persist": base in prev, "status": status.get(base)})
    return out, n, coll


def f3_due(watch: list, now: float) -> tuple:
    """watch: [{'key','t0','done': [offset,...], ...}]. Returns (due [(entry, offset)], remaining watch)."""
    due, keep = [], []
    for w in watch:
        for off in F3_OFFSETS:
            if off not in w["done"] and now >= w["t0"] + off:
                due.append((w, off))
                w["done"].append(off)
        if len(w["done"]) < len(F3_OFFSETS):
            keep.append(w)
    return due, keep
