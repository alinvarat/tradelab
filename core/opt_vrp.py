"""Pure pieces of the opt_vrp study (research/studies/protocol_opt_vrp_20261125.md): strike picking, fills, fees,
payoffs, margin, sizing, account simulation, controls, hindsight ceiling and the rule judge. No network, stdlib only.
The fetching lives in research/studies/opt_vrp.py; everything that decides a number lives here and is tested offline.

Units: option prices are in coin (BTC/ETH) per 1 unit of underlying; USD = coin price x index_price of the print.
All per-unit values are USD per 1 underlying unit; one "step" is 0.01 BTC or 0.1 ETH.
"""
import calendar
import datetime as dt
import math
import random
import re
from statistics import median, stdev

STEP = {"BTC": 0.01, "ETH": 0.1}
START = 147.0
RUIN = 5.0
RISK = 0.20
MARGIN_CAP = 0.80
TAKER_CAP = 0.0003
DELIV_CAP = 0.00015
FEE_FRAC = 0.125
COSTS = {"base": {"haircut": 0.10, "fee_mult": 1.0}, "high": {"haircut": 0.25, "fee_mult": 2.0}}
FILL_SECONDS = 3600
SEED = 20261125
N_DRAWS = 1000
N_TESTS = 16
BAR = 0.05 / N_TESTS
DEV = ("2021-03-24", "2024-12-31")
CONFIRM = ("2025-01-01", "2026-10-31")
FIRST_DAY, LAST_DAY = "2021-03-24", "2026-10-31"
SHOCK = {"BTC": 0.025, "ETH": 0.035}

# rule: window, k, sides, filter name
RULES = {
    "R1_bull_put_spread_vrp": {"win": "am", "k": 1.0, "sides": ("put",), "filter": "vrp"},
    "R2_bear_call_spread_vrp": {"win": "am", "k": 1.0, "sides": ("call",), "filter": "vrp"},
    "R3_iron_condor_vrp": {"win": "am", "k": 1.0, "sides": ("put", "call"), "filter": "vrp"},
    "R4_high_dvol_condor": {"win": "am", "k": 1.3, "sides": ("put", "call"), "filter": "dvol_pct"},
    "R5_post_shock_condor": {"win": "am", "k": 1.3, "sides": ("put", "call"), "filter": "shock"},
    "R6_weekend_condor": {"win": "am", "k": 1.0, "sides": ("put", "call"), "filter": "weekend"},
    "R7_rich_put_skew_spread": {"win": "am", "k": 1.0, "sides": ("put",), "filter": "skew"},
    "R8_evening_condor_12h": {"win": "pm", "k": 1.0, "sides": ("put", "call"), "filter": "vrp_pm"},
}
SIDE_SPECS = (("am", 1.0), ("am", 1.3), ("pm", 1.0))      # (window, k) rows emitted per day and asset

# ------------------------------------------------------------------ time helpers


def day_ts(date):
    """'YYYY-MM-DD' -> UTC midnight epoch seconds."""
    y, m, d = map(int, date.split("-"))
    return calendar.timegm((y, m, d, 0, 0, 0))


def add_days(date, n):
    return (dt.date.fromisoformat(date) + dt.timedelta(days=n)).isoformat()


def weekday(date):
    return dt.date.fromisoformat(date).weekday()          # Mon=0 .. Sun=6


def entry_times(date, win):
    """(entry seconds, signal hour start seconds). AM 08:05 / 08:00, PM 20:05 / 20:00."""
    h = 8 if win == "am" else 20
    base = day_ts(date) + h * 3600
    return base + 300, base


def expiry_ts(date):
    """Next 08:00 UTC after an entry on `date` (both windows): D+1 08:00."""
    return day_ts(add_days(date, 1)) + 8 * 3600


def month_days(month):
    """All 'YYYY-MM-DD' of 'YYYY-MM' inside [FIRST_DAY, LAST_DAY]."""
    y, m = map(int, month.split("-"))
    n = calendar.monthrange(y, m)[1]
    out = [f"{y:04d}-{m:02d}-{d:02d}" for d in range(1, n + 1)]
    return [d for d in out if FIRST_DAY <= d <= LAST_DAY]


def all_months():
    out, (y, m) = [], (2021, 3)
    while (y, m) <= (2026, 10):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def universe():
    """Shard tokens 'BTC:2021-03' ... (asset x calendar month); no network."""
    return [f"{a}:{m}" for a in ("BTC", "ETH") for m in all_months()]


# ------------------------------------------------------------------ instruments and strikes

NAME_RE = re.compile(r"^(BTC|ETH)(?:_USDC)?-(\d{1,2})([A-Z]{3})(\d{2})-(\d+)(?:d\d+)?-([CP])$")
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def parse_name(name):
    """'BTC-27NOV26-90000-P' / 'BTC_USDC-...' -> (asset, expiry 'YYYY-MM-DD', strike, 'put'|'call') or None."""
    m = NAME_RE.match(name or "")
    if not m or m.group(3) not in MONTHS:
        return None
    asset, d, mon, yy, strike, cp = m.groups()
    return asset, f"{2000 + int(yy):04d}-{MONTHS[mon]:02d}-{int(d):02d}", float(strike), "put" if cp == "P" else "call"


def sigma_d(dvol):
    return dvol / 100.0 / math.sqrt(365)


def pick_strikes(strikes, index, sigma, k, side):
    """Deterministic, BS-free: (short, long) strikes from the listed grid, or (None, reason).
    put: short = highest strike <= index*(1-k*sigma); call: lowest >= index*(1+k*sigma). Long wing = the listed strike
    beyond the short whose distance is the smallest one >= 0.5*sigma*index."""
    g = sorted(set(strikes))
    need = 0.5 * sigma * index
    if side == "put":
        c = [s for s in g if s <= index * (1 - k * sigma)]
        if not c:
            return None, "no_grid"
        short = c[-1]
        w = [s for s in g if s < short and short - s >= need - 1e-9]
        return (short, w[-1]) if w else (None, "no_wing")
    c = [s for s in g if s >= index * (1 + k * sigma)]
    if not c:
        return None, "no_grid"
    short = c[0]
    w = [s for s in g if s > short and s - short >= need - 1e-9]
    return (short, w[0]) if w else (None, "no_wing")


NON_TAKER_FLAGS = ("block_trade_id", "block_rfq_id", "block_trade_leg_count", "combo_id", "combo_trade_id", "liquidation")


def tradable(p):
    """False for prints that are not ordinary order-book taker trades: block trades (negotiated price), combo leg
    prints (price allocated between legs) and liquidations. Their prices are not available to a retail taker."""
    return not any(p.get(f) for f in NON_TAKER_FLAGS)


def first_fill(prints, name, direction, t0_ms, t1_ms):
    """First print of `name` with that taker direction and t0 <= timestamp < t1: the print dict or None."""
    best = None
    for p in prints:
        if p.get("instrument_name") != name or p.get("direction") != direction:
            continue
        t = p["timestamp"]
        if t0_ms <= t < t1_ms and (best is None or (t, str(p.get("trade_id"))) < (best["timestamp"], str(best.get("trade_id")))):
            best = p
    return best


def index_before(prints, entry_s):
    """Index price of the last print in [entry-60 min, entry) or None."""
    lo, hi = (entry_s - 3600) * 1000, entry_s * 1000
    c = [p for p in prints if lo <= p["timestamp"] < hi and p.get("index_price")]
    if not c:
        return None
    return max(c, key=lambda p: (p["timestamp"], str(p.get("trade_id"))))["index_price"]


# ------------------------------------------------------------------ filters inputs


def rv_annual(closes_by_open, last_open_s, n):
    """Annualised stdev x100 of the last n hourly log returns with the last bar opened at last_open_s.
    closes_by_open: {bar open seconds: close}. Any missing hour -> None."""
    ts = [last_open_s - 3600 * i for i in range(n, -1, -1)]
    try:
        c = [closes_by_open[t] for t in ts]
    except KeyError:
        return None
    if any(x is None or x <= 0 for x in c):
        return None
    r = [math.log(c[i + 1] / c[i]) for i in range(n)]
    return stdev(r) * math.sqrt(24 * 365) * 100.0


def ret_24h(closes_by_open, last_open_s):
    a, b = closes_by_open.get(last_open_s - 86400), closes_by_open.get(last_open_s)
    return None if not a or not b else b / a - 1.0


def skew_from_prints(prints, date):
    """Rich put skew on [07:05, 08:05): median put IV (strike/index 0.80-0.95) minus median call IV (1.05-1.20) on the
    instruments expiring D+1 08:00; falls back to the ones expiring D 08:00 (prints before 08:00). None if < 3 each."""
    d0 = day_ts(date)
    lo, hi = (d0 + 7 * 3600 + 300) * 1000, (d0 + 8 * 3600 + 300) * 1000
    target, prior = add_days(date, 1), date
    for exp_date, cut in ((target, hi), (prior, d0 * 1000 + 8 * 3600 * 1000)):
        put, call = [], []
        for p in prints:
            if not lo <= p["timestamp"] < min(hi, cut) or p.get("iv") is None or not p.get("index_price"):
                continue
            pn = parse_name(p.get("instrument_name"))
            if not pn or pn[1] != exp_date:
                continue
            mny = pn[2] / p["index_price"]
            if pn[3] == "put" and 0.80 <= mny <= 0.95:
                put.append(p["iv"])
            elif pn[3] == "call" and 1.05 <= mny <= 1.20:
                call.append(p["iv"])
        if len(put) >= 3 and len(call) >= 3:
            return median(put) - median(call)
    return None


def percentile(values, q):
    v = sorted(values)
    if not v:
        return None
    pos = (len(v) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


# ------------------------------------------------------------------ row builder (one asset-day)


def build_day_rows(asset, date, instruments, prints_am, prints_pm, usdc_am, usdc_pm, dvol, hours, delivery,
                   gaps=None):
    """Rows for one asset-day, independent of any rule filter.

    instruments: instrument dicts (name, strike, type 'put'|'call', creation_ms, period) of the target expiry only.
    prints_am: prints in [07:05, 09:05); prints_pm: [19:05, 21:05); usdc_*: USDC prints in the fill window or None
    (None = not collected, e.g. before 2025). dvol: {hour start seconds: close}. hours: {bar open s: (o, h, l, c)}.
    delivery: settlement price of the D+1 08:00 expiry or None. gaps: list of fetch failures for this day (day is dropped)."""
    gaps = list(gaps or [])
    prints_am = [p for p in (prints_am or []) if tradable(p)]
    prints_pm = [p for p in (prints_pm or []) if tradable(p)]
    usdc_am = None if usdc_am is None else [p for p in usdc_am if tradable(p)]
    usdc_pm = None if usdc_pm is None else [p for p in usdc_pm if tradable(p)]
    closes = {t: v[3] for t, v in hours.items()}
    e_am, h_am = entry_times(date, "am")
    e_pm, h_pm = entry_times(date, "pm")
    exp = expiry_ts(date)
    day = {"kind": "day", "date": date, "asset": asset, "gaps": gaps,
           "dvol_am": dvol.get(h_am - 3600), "dvol_pm": dvol.get(h_pm - 3600),
           "rv168": rv_annual(closes, h_am - 3600, 168), "rv72": rv_annual(closes, h_pm - 3600, 72),
           "ret24": ret_24h(closes, h_am - 3600), "skew": skew_from_prints(prints_am, date) if prints_am else None,
           "n_prints_am": len(prints_am or []), "n_prints_pm": len(prints_pm or [])}
    rows = [day]
    if gaps:
        return rows
    periods = sorted({i.get("period") for i in instruments})
    day["period"] = periods[0] if len(periods) == 1 else "|".join(map(str, periods))
    for win, k in SIDE_SPECS:
        e, h = (e_am, h_am) if win == "am" else (e_pm, h_pm)
        prints = prints_am if win == "am" else prints_pm
        usdc = usdc_am if win == "am" else usdc_pm
        dv = day["dvol_am"] if win == "am" else day["dvol_pm"]
        idx = index_before(prints, e)
        src = "print"
        if idx is None:
            bar = hours.get(h - 3600)
            idx, src = (bar[3], "binance_1h") if bar else (None, None)
        listed = [i for i in instruments if i["creation_ms"] <= e * 1000]
        for side in ("put", "call"):
            row = {"kind": "side", "date": date, "asset": asset, "win": win, "k": k, "side": side, "status": "ok",
                   "expiry_ts": exp, "period": day["period"], "index": idx, "index_src": src, "delivery": delivery}
            rows.append(row)
            if dv is None:
                row["status"] = "no_dvol"
                continue
            if idx is None:
                row["status"] = "no_index"
                continue
            grid = {i["strike"]: i["name"] for i in listed if i["type"] == side}
            if not grid:
                row["status"] = "no_expiry"
                continue
            ks, why = pick_strikes(list(grid), idx, sigma_d(dv), k, side)
            if ks is None:
                row["status"] = why
                continue
            kl = why
            row.update(short_k=ks, long_k=kl, sigma=sigma_d(dv))
            ps = first_fill(prints, grid[ks], "sell", e * 1000, (e + FILL_SECONDS) * 1000)
            pl = first_fill(prints, grid[kl], "buy", e * 1000, (e + FILL_SECONDS) * 1000)
            if usdc is not None:
                row["usdc"] = usdc_legs(usdc, date, ks, kl, side, e, asset)
            if ps is None:
                row["status"] = "no_short_print"
                continue
            if pl is None:
                row["status"] = "no_long_print"
                continue
            row.update(s_px=ps["price"], s_idx=ps["index_price"], s_ts=ps["timestamp"],
                       l_px=pl["price"], l_idx=pl["index_price"], l_ts=pl["timestamp"])
            lo = [v for t, v in hours.items() if h <= t < exp]
            if lo:
                row["path_min"], row["path_max"] = min(v[2] for v in lo), max(v[1] for v in lo)
    return rows


def usdc_legs(usdc, date, ks, kl, side, entry_s, asset=None):
    """First sell print of the short strike and first buy print of the long strike on the USDC tape (USD per unit)."""
    exp_date = add_days(date, 1)
    out = {}
    for tag, strike, direction in (("s", ks, "sell"), ("l", kl, "buy")):
        best = None
        for p in usdc:
            pn = parse_name(p.get("instrument_name"))
            if not pn or pn[1] != exp_date or pn[2] != strike or pn[3] != side or p.get("direction") != direction or (asset and pn[0] != asset):
                continue
            if entry_s * 1000 <= p["timestamp"] < (entry_s + FILL_SECONDS) * 1000 and (best is None or p["timestamp"] < best["timestamp"]):
                best = p
        out[tag] = best["price"] if best else None
        out[tag + "_ts"] = best["timestamp"] if best else None
    return out


# ------------------------------------------------------------------ economics


def intrinsic(side, strike, settle):
    return max(0.0, strike - settle) if side == "put" else max(0.0, settle - strike)


def side_econ(row, cost):
    """Per-unit economics of one filled side row at a cost level, or {'reason': ...}."""
    if row.get("status") != "ok":
        return {"reason": row.get("status") or "unknown"}
    c = COSTS[cost]
    if row.get("delivery") is None:
        return {"reason": "no_delivery"}
    h, fm = c["haircut"], c["fee_mult"]
    sp, lp = row["s_px"] * (1 - h), row["l_px"] * (1 + h)
    fee_s = fm * min(TAKER_CAP, FEE_FRAC * sp)
    fee_l = fm * min(TAKER_CAP, FEE_FRAC * lp)
    s_usd, l_usd = sp * row["s_idx"], lp * row["l_idx"]
    fees = fee_s * row["s_idx"] + fee_l * row["l_idx"]
    S = row["delivery"]
    i_s, i_l = intrinsic(row["side"], row["short_k"], S), intrinsic(row["side"], row["long_k"], S)
    dfee = sum(fm * min(DELIV_CAP, FEE_FRAC * i / S) * S for i in (i_s, i_l) if i > 0)
    credit = s_usd - l_usd - fees
    width = abs(row["short_k"] - row["long_k"])
    idx = row["index"]
    otm = max(0.0, ((idx - row["short_k"]) if row["side"] == "put" else (row["short_k"] - idx)) / idx)
    return {"credit": credit, "width": width, "pnl": s_usd - l_usd - fees - i_s + i_l - dfee,
            "margin_b": max(0.15 - otm, 0.10) * idx + s_usd + l_usd}


def struct_econ(rows, cost, asset):
    """Combine the side rows of one structure (1 spread or 2 for a condor) -> econ dict with 'reason' on failure."""
    parts = []
    for r in rows:
        e = side_econ(r, cost)
        if "reason" in e:
            return {"reason": f"{r['side']}:{e['reason']}" if len(rows) > 1 else e["reason"]}
        parts.append(e)
    credit = sum(p["credit"] for p in parts)
    if credit <= 0:
        return {"reason": "no_credit"}
    max_loss = max(p["width"] for p in parts) - credit
    if max_loss <= 0:
        return {"reason": "credit_ge_width"}
    return {"credit": credit, "max_loss": max_loss, "pnl": sum(p["pnl"] for p in parts),
            "margin_a": max_loss, "margin_b": sum(p["margin_b"] for p in parts), "step": STEP[asset]}


def size_steps(equity, econ, margin):
    """(steps, reason). Risk cap 20% of equity at max loss; margin <= 80% of equity at entry."""
    step = econ["step"]
    q = math.floor(RISK * equity / (econ["max_loss"] * step) + 1e-9)
    if q < 1:
        return 0, "size_below_minimum"
    m = econ["margin_a"] if margin == "A" else econ["margin_b"]
    qm = math.floor(MARGIN_CAP * equity / (m * step) + 1e-9)
    if qm < 1:
        return 0, "margin"
    return min(q, qm), None


# ------------------------------------------------------------------ account simulation


def sim(trades, months, margin="B", start=START):
    """Continuous wallet. trades: [(date, econ)] sorted by date with econ from struct_econ (no 'reason').
    months: every 'YYYY-MM' of the split (months without a trade keep their equity)."""
    eq, peak, mdd = start, start, 0.0
    out_trades, attr, ruined = [], {}, False
    month_start, ptr = {}, 0
    months = sorted(months)
    for date, e in sorted(trades, key=lambda x: x[0]):
        while ptr < len(months) and months[ptr] <= date[:7]:
            month_start[months[ptr]] = eq
            ptr += 1
        if ruined:
            attr["ruined"] = attr.get("ruined", 0) + 1
            continue
        q, why = size_steps(eq, e, margin)
        if why:
            attr[why] = attr.get(why, 0) + 1
            continue
        pnl = q * e["step"] * e["pnl"]
        out_trades.append({"date": date, "steps": q, "pnl": pnl, "ret": pnl / eq, "ror": e["pnl"] / e["max_loss"],
                           "win": pnl > 0, "equity_before": eq})
        eq = max(eq + pnl, 0.0)
        peak = max(peak, eq)
        mdd = max(mdd, 1 - eq / peak if peak else 0)
        if eq < RUIN:
            ruined = True
    while ptr < len(months):
        month_start[months[ptr]] = eq
        ptr += 1
    ends = {m: month_start[months[i + 1]] if i + 1 < len(months) else eq for i, m in enumerate(months)}
    funded = [m for m in months if month_start[m] >= start - 1e-9]
    mult = {m: ends[m] / month_start[m] if month_start[m] > 0 else 0.0 for m in months}
    return {"trades": out_trades, "attrition": attr, "ending_equity": eq, "max_drawdown": mdd, "ruined": ruined,
            "funded_months": len(funded), "funded_3x": [m for m in funded if mult[m] >= 3.0],
            "months_3x_any": [m for m in months if mult[m] >= 3.0 and month_start[m] > 0],
            "month_multiple": mult}


def fresh_month_multiples(trades, months, margin="A"):
    """Each calendar month restarted at 147 USD (diagnostic and ceiling)."""
    by = {}
    for d, e in trades:
        by.setdefault(d[:7], []).append((d, e))
    return {m: sim(by.get(m, []), [m], margin)["ending_equity"] / START for m in months}


def ceiling(trades, months):
    """STEP 0 at the given econs: (a) all-win path (every trade earns its full net credit), (b) oracle that skips
    losing days (actual outcomes). Share of months reaching 3x, fresh 147 wallet each month, margin A."""
    allwin = [(d, dict(e, pnl=e["credit"])) for d, e in trades]
    oracle = [(d, e) for d, e in trades if e["pnl"] > 0]
    out = {}
    for tag, tr in (("all_win", allwin), ("oracle", oracle)):
        mm = fresh_month_multiples(tr, months, "A")
        out[tag] = {"share_3x": sum(v >= 3.0 for v in mm.values()) / len(mm) if mm else 0.0,
                    "months_3x": sum(v >= 3.0 for v in mm.values()), "months": len(mm),
                    "median_multiple": sorted(mm.values())[len(mm) // 2] if mm else None}
    return out


def draw_share(signal, pool, n_draws=N_DRAWS, seed=SEED):
    """Share of random draws (same count, uniform, without replacement from pool) whose mean >= the signal mean."""
    n = len(signal)
    if n == 0 or len(pool) < n:
        return None
    target = sum(signal) / n
    rng = random.Random(seed)
    hits = sum(sum(rng.sample(pool, n)) / n >= target - 1e-12 for _ in range(n_draws))
    return hits / n_draws


# ------------------------------------------------------------------ features and filters across days


def add_features(days):
    """days: [{'date','dvol_am','skew',...}] of ONE asset. Adds dvol_pct_ok (R4) and skew_ok (R7) in place using only
    earlier days: previous 90 calendar days of 08:00 DVOL closes (>= 60 values, 60th percentile), previous 30 calendar
    days of skew (>= 15 values, median)."""
    by = {d["date"]: d for d in days}
    for d in days:
        prev = [by[add_days(d["date"], -i)] for i in range(1, 91) if add_days(d["date"], -i) in by]
        vals = [p["dvol_am"] for p in prev if p.get("dvol_am") is not None]
        if d.get("dvol_am") is None or len(vals) < 60:
            d["dvol_pct_ok"] = None
        else:
            d["dvol_pct_ok"] = d["dvol_am"] >= percentile(vals, 0.6)
        sk = [p["skew"] for p in prev if p["date"] >= add_days(d["date"], -30) and p.get("skew") is not None]
        d["skew_ok"] = None if d.get("skew") is None or len(sk) < 15 else d["skew"] >= median(sk)
    return days


def rule_filter(rule, day, asset):
    """True / False / None (None = input missing, with reason) for one day."""
    f = RULES[rule]["filter"]
    if f == "vrp":
        a, b = day.get("dvol_am"), day.get("rv168")
        return (None, "no_rv") if a is None or b is None or b <= 0 else (a / b >= 1.15, None)
    if f == "vrp_pm":
        a, b = day.get("dvol_pm"), day.get("rv72")
        return (None, "no_rv") if a is None or b is None or b <= 0 else (a / b >= 1.15, None)
    if f == "dvol_pct":
        v = day.get("dvol_pct_ok")
        return (None, "no_dvol_history") if v is None else (v, None)
    if f == "shock":
        r = day.get("ret24")
        return (None, "no_return") if r is None else (abs(r) >= SHOCK[asset], None)
    if f == "weekend":
        return weekday(day["date"]) >= 4, None
    if f == "skew":
        v = day.get("skew_ok")
        return (None, "no_skew") if v is None else (v, None)
    raise KeyError(f)


def split_of(date):
    if DEV[0] <= date <= DEV[1]:
        return "dev"
    if CONFIRM[0] <= date <= CONFIRM[1]:
        return "confirm"
    return None


def split_months(split):
    lo, hi = (DEV if split == "dev" else CONFIRM)
    return [m for m in all_months() if lo[:7] <= m <= hi[:7]]


def split_days(split):
    lo, hi = (DEV if split == "dev" else CONFIRM)
    return (dt.date.fromisoformat(hi) - dt.date.fromisoformat(lo)).days + 1


# ------------------------------------------------------------------ summarize


def _index_rows(rows):
    days, sides = {}, {}
    for r in rows:
        if r.get("kind") == "day":
            days.setdefault(r["asset"], {})[r["date"]] = r
        elif r.get("kind") == "side":
            sides[(r["asset"], r["date"], r["win"], r["k"], r["side"])] = r
    return days, sides


def candidates(rule, asset, days, sides, cost):
    """Per day of one test: dict date -> {'filter': bool|None, 'filter_reason', 'econ': econ|{'reason'}} (structure
    economics ignoring the filter, so the same rows feed the signal, the unconditional control and the random pool)."""
    spec, out = RULES[rule], {}
    for date in sorted(days[asset]):
        day = days[asset][date]
        if day["gaps"]:
            continue
        fl, why = rule_filter(rule, day, asset)
        keys = [(asset, date, spec["win"], spec["k"], s) for s in spec["sides"]]
        if any(k not in sides for k in keys):
            econ = {"reason": "no_rows"}
        else:
            econ = struct_econ([sides[k] for k in keys], cost, asset)
        out[date] = {"filter": fl, "filter_reason": why, "econ": econ}
    return out


def month_concentration(trades):
    """Report-only guard against clustered signals (the random draw treats days as independent, which is generous when a
    filter fires in a few volatile months): share of months with a positive sum of ROR, and the mean ROR without the
    best month."""
    by = {}
    for x in trades:
        by.setdefault(x["date"][:7], []).append(x["ror"])
    if not by:
        return {"signal_months": 0, "positive_month_share": None, "mean_ror_without_best_month": None}
    best = max(by, key=lambda m: sum(by[m]))
    rest = [v for m, vs in by.items() if m != best for v in vs]
    return {"signal_months": len(by), "positive_month_share": sum(sum(v) > 0 for v in by.values()) / len(by),
            "mean_ror_without_best_month": sum(rest) / len(rest) if rest else None}


def _stats(sim_res, n_days):
    t = sim_res["trades"]
    n = len(t)
    return {"month_concentration": month_concentration(t), "trades": n, "trades_per_week": round(n / (n_days / 7.0), 3) if n_days else 0.0,
            "win_rate": sum(x["win"] for x in t) / n if n else None,
            "mean_ret_equity": sum(x["ret"] for x in t) / n if n else None,
            "mean_ror": sum(x["ror"] for x in t) / n if n else None,
            "worst_loss_pct_equity": min((x["ret"] for x in t), default=None),
            "worst_loss_usd": min((x["pnl"] for x in t), default=None),
            "ending_equity": sim_res["ending_equity"], "max_drawdown": sim_res["max_drawdown"], "ruined": sim_res["ruined"],
            "funded_months": sim_res["funded_months"], "funded_3x_months": len(sim_res["funded_3x"]),
            "funded_3x_list": sim_res["funded_3x"], "any_3x_months": len(sim_res["months_3x_any"]),
            "sizing_attrition": sim_res["attrition"]}


def score_test(rule, asset, days, sides):
    """Everything for one (rule, asset) test."""
    res = {"rule": rule, "asset": asset}
    cand = {c: candidates(rule, asset, days, sides, c) for c in COSTS}
    base = cand["base"]
    # attrition and funnel by split (BASE cost view of the reasons; identical reasons at HIGH except credit checks)
    funnel = {}
    for sp in ("dev", "confirm"):
        f = {"days": 0, "filtered_out": 0, "filter_missing": {}, "attrition": {}, "executable": 0}
        for date, c in base.items():
            if split_of(date) != sp:
                continue
            f["days"] += 1
            if c["filter"] is None:
                f["filter_missing"][c["filter_reason"]] = f["filter_missing"].get(c["filter_reason"], 0) + 1
            elif not c["filter"]:
                f["filtered_out"] += 1
            elif "reason" in c["econ"]:
                r = c["econ"]["reason"]
                f["attrition"][r] = f["attrition"].get(r, 0) + 1
            else:
                f["executable"] += 1
        funnel[sp] = f
    res["funnel"] = funnel
    res["splits"] = {}
    for sp in ("dev", "confirm"):
        months, n_days = split_months(sp), split_days(sp)
        sres = {}
        sig = {c: [(d, v["econ"]) for d, v in cand[c].items() if split_of(d) == sp and v["filter"] is True
                   and "reason" not in v["econ"]] for c in COSTS}
        pool = {c: [(d, v["econ"]) for d, v in cand[c].items() if split_of(d) == sp and "reason" not in v["econ"]]
                for c in COSTS}
        sres["ceiling_high"] = ceiling(sig["high"], months)
        stopped = sres["ceiling_high"]["all_win"]["share_3x"] < 0.5
        sres["step0_pass"] = not stopped
        sres["n_signal_days"] = len(sig["base"])
        if stopped and sp == "confirm":
            sres["verdict_note"] = "structure cannot reach target (step 0)"
        for c in COSTS:
            sres[c] = {"unconditional_mean_ror": (sum(e["pnl"] / e["max_loss"] for _, e in pool[c]) / len(pool[c])) if pool[c] else None,
                       "pool_days": len(pool[c])}
            for m in ("A", "B"):
                sres[c][f"margin_{m}"] = _stats(sim(sig[c], months, m), n_days)
        sres["fresh_month_3x_high_A"] = sum(v >= 3.0 for v in fresh_month_multiples(sig["high"], months, "A").values())
        if not stopped or sp == "dev":
            for c in COSTS:
                s_ror = [e["pnl"] / e["max_loss"] for _, e in sig[c]]
                p_ror = [e["pnl"] / e["max_loss"] for _, e in pool[c]]
                sres[c]["mean_ror"] = sum(s_ror) / len(s_ror) if s_ror else None
                sres[c]["draw_share"] = draw_share(s_ror, p_ror)
        if rule == "R6_weekend_condor":
            for c in COSTS:
                wk = [e["pnl"] / e["max_loss"] for d, e in pool[c] if weekday(d) >= 4]
                mt = [e["pnl"] / e["max_loss"] for d, e in pool[c] if weekday(d) < 4]
                sres[c]["calendar_control"] = {"fri_sun_mean_ror": sum(wk) / len(wk) if wk else None,
                                               "mon_thu_mean_ror": sum(mt) / len(mt) if mt else None,
                                               "n_fri_sun": len(wk), "n_mon_thu": len(mt)}
        res["splits"][sp] = sres
    res["verdict"] = verdict(res)
    return res


def verdict(res):
    """PASS / CONDITIONAL / FAIL on the confirm split (protocol section 6)."""
    s = res["splits"]["confirm"]
    if not s["step0_pass"]:
        return {"label": "STOPPED", "why": "structure cannot reach target (step 0)"}
    checks = {}
    h, b = s["high"], s["base"]
    checks["draw_share_base"] = b.get("draw_share") is not None and b["draw_share"] <= BAR
    checks["draw_share_high"] = h.get("draw_share") is not None and h["draw_share"] <= BAR
    checks["freq_ge_3_per_week"] = h["margin_B"]["trades_per_week"] >= 3.0
    checks["mean_pnl_positive_high"] = (h["margin_B"]["mean_ror"] or 0) > 0
    for m in ("A", "B"):
        checks[f"funded_3x_{m}"] = h[f"margin_{m}"]["funded_3x_months"] >= 1
    common = all(checks[k] for k in ("draw_share_base", "draw_share_high", "freq_ge_3_per_week", "mean_pnl_positive_high"))
    label = "PASS" if common and checks["funded_3x_B"] else "CONDITIONAL" if common and checks["funded_3x_A"] else "FAIL"
    return {"label": label, "checks": checks}


def usdc_report(sides):
    """USDC liquidity attrition by rule structure and the haircut cross-check (2025+ rows only)."""
    out = {"by_win_k": {}, "ratio_samples": 0}
    ratios, better = [], 0
    for r in sides.values():
        u = r.get("usdc")
        if u is None:
            continue
        key = f"{r['win']}_k{r['k']}_{r['side']}"
        g = out["by_win_k"].setdefault(key, {"rows": 0, "both_legs_usdc": 0, "coin_both_legs": 0})
        g["rows"] += 1
        both = u.get("s") is not None and u.get("l") is not None
        g["both_legs_usdc"] += both
        if r.get("status") == "ok":
            g["coin_both_legs"] += 1
            for tag, px, idx, ts, direction in (("s", r["s_px"], r["s_idx"], r["s_ts"], "sell"), ("l", r["l_px"], r["l_idx"], r["l_ts"], "buy")):
                if u.get(tag) is not None and abs(u[tag + "_ts"] - ts) <= 600000 and px * idx > 0:
                    ratios.append(u[tag] / (px * idx))
                    h = COSTS["base"]["haircut"]
                    better += (u[tag] >= px * idx * (1 - h)) if direction == "sell" else (u[tag] <= px * idx * (1 + h))
    for g in out["by_win_k"].values():
        g["share_both_legs_usdc"] = g["both_legs_usdc"] / g["rows"] if g["rows"] else None
    out["ratio_samples"] = len(ratios)
    out["median_usdc_over_coin"] = median(ratios) if ratios else None
    out["share_usdc_better_than_base_model"] = better / len(ratios) if ratios else None
    return out


def summarize(all_rows):
    days, sides = _index_rows(all_rows)
    gap_days = {a: sorted(d for d, r in days[a].items() if r["gaps"]) for a in days}
    total_days = {a: len(days[a]) for a in days}
    for a in days:
        add_features([days[a][d] for d in sorted(days[a])])
    tests = {}
    for rule in RULES:
        for asset in sorted(days):
            t = score_test(rule, asset, days, sides)
            tests[f"{rule}|{asset}"] = t
    # episodes: BTC and ETH on the same day count once (confirm, HIGH, margin B executed days per rule)
    episodes = {}
    for rule in RULES:
        ds = set()
        for asset in days:
            c = candidates(rule, asset, days, sides, "high")
            tr = [(d, v["econ"]) for d, v in c.items() if split_of(d) == "confirm" and v["filter"] is True and "reason" not in v["econ"]]
            ds |= {x["date"] for x in sim(tr, split_months("confirm"), "B")["trades"]}
        episodes[rule] = {"episodes": len(ds), "episodes_per_week": round(len(ds) / (split_days("confirm") / 7.0), 3)}
    per_period = {}
    for (asset, date, win, k, side), r in sides.items():
        per_period[r.get("period")] = per_period.get(r.get("period"), 0) + (r["status"] == "ok")
    passed = sorted(k for k, t in tests.items() if t["verdict"]["label"] == "PASS")
    cond = sorted(k for k, t in tests.items() if t["verdict"]["label"] == "CONDITIONAL")
    gap_total = sum(len(v) for v in gap_days.values())
    return {"line": "opt_vrp", "n_tests": len(tests), "bonferroni_bar": BAR, "days": total_days, "gap_days": {a: len(v) for a, v in gap_days.items()},
            "gap_days_examples": {a: v[:10] for a, v in gap_days.items()},
            "data_ok": gap_total <= 0.02 * max(1, sum(total_days.values())),
            "passed": passed, "conditional": cond,
            "stopped_step0": sorted(k for k, t in tests.items() if t["verdict"]["label"] == "STOPPED"),
            "episodes_confirm_high_B": episodes, "ok_side_rows_by_settlement_period": per_period,
            "usdc": usdc_report(sides), "tests": tests}
