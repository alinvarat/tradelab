"""factory_crypto_3: single-asset trend and event rules on liquid USDT-M perps (pre-registered in RESULTS.md).

Pure functions, no network. A rule maps one symbol's 1h grid to a position p (units of that symbol's 1/N slot) decided
at each bar's close; the engine charges costs on |change in p| and measured funding on the position held across a
settlement. Judging reuses core.factory (block_p, judge_all, month_multiples). Simulated research only."""
import math
import time
from statistics import mean, pstdev

from core import factory as fa

HOUR = 3600
TAKER = 0.0005
SLIP = 0.0002
ONE_WAY = TAKER + SLIP            # per unit of |change in position|, each side
ATR_N = 14
STOP_ATR = 3.0
VOL_TARGET = 0.40
SIZE_CAP = 1.5
RESIZE = 0.25
LEVS = (1, 2, 3, 5, 8, 12)
RULE_NAMES = ("don_1h_55", "don_4h_20", "don_4h_55", "ma_4h_20_100", "ma_1d_20_100", "wick_long_4h",
              "wick_long_24h", "wick_short_4h", "weekly_open_break", "trend_pullback_4h")


# ---- grid ----
def grid(bars, start_s, end_s):
    """bars: [(open_ts, o, h, l, c, ...)] -> (ts[], o[], h[], l[], c[], missing) on a regular hourly grid from the first
    bar to end_s; a missing hour is filled flat at the previous close and counted. Duplicates keep the last row."""
    by = {int(b[0]): b for b in bars if start_s <= b[0] < end_s}
    if not by:
        return [], [], [], [], [], 0
    t0, t1 = min(by), max(by)
    ts, o, h, l, c, miss = [], [], [], [], [], 0
    for t in range(t0, t1 + 1, HOUR):
        b = by.get(t)
        if b is None:
            p = c[-1]
            o.append(p), h.append(p), l.append(p), c.append(p)
            miss += 1
        else:
            o.append(b[1]), h.append(b[2]), l.append(b[3]), c.append(b[4])
        ts.append(t)
    return ts, o, h, l, c, miss


def resample(ts, o, h, l, c, k):
    """k-hour bars aligned to UTC multiples of k hours. Returns (o, h, l, c, end_idx) where end_idx[j] is the 1h index
    of the last hour of block j. Only complete blocks."""
    if k == 1:
        return o, h, l, c, list(range(len(ts)))
    ro, rh, rl, rc, end = [], [], [], [], []
    cur = None
    for i, t in enumerate(ts):
        hr = t // HOUR
        if hr % k == 0 or cur is None:
            cur = [i, o[i], h[i], l[i]] if hr % k == 0 else None
        if cur is not None:
            cur[2] = max(cur[2], h[i])
            cur[3] = min(cur[3], l[i])
            if hr % k == k - 1 and i - cur[0] == k - 1:
                ro.append(cur[1]), rh.append(cur[2]), rl.append(cur[3]), rc.append(c[i]), end.append(i)
                cur = None
    return ro, rh, rl, rc, end


def expand(n, end_idx, pj):
    """Hold p between decisions: pos[i] = pj[j] at i = end_idx[j], else the previous value."""
    pos, k, cur = [0.0] * n, 0, 0.0
    for i in range(n):
        if k < len(end_idx) and end_idx[k] == i:
            cur = pj[k]
            k += 1
        pos[i] = cur
    return pos


# ---- indicators (each value uses data up to and including its own bar) ----
def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, v in enumerate(x):
        s += v
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def atr(h, l, c, n=ATR_N):
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    return sma(tr, n)


def rsi(c, n=14):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    g = [max(c[i] - c[i - 1], 0.0) for i in range(1, n + 1)]
    ls = [max(c[i - 1] - c[i], 0.0) for i in range(1, n + 1)]
    ag, al = sum(g) / n, sum(ls) / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def roll_std_logret(c, n):
    """value[i] = population stdev of the n log returns ending at bar i (None before n returns exist). O(len) with
    running sums; a result below 1e-12 variance is reported as 0."""
    lr = [0.0] + [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
    out = [None] * len(c)
    s1 = s2 = 0.0
    for i in range(1, len(c)):
        s1 += lr[i]
        s2 += lr[i] * lr[i]
        if i > n:
            s1 -= lr[i - n]
            s2 -= lr[i - n] * lr[i - n]
        if i >= n:
            out[i] = math.sqrt(max(0.0, s2 / n - (s1 / n) ** 2))
    return out


# ---- rules: each returns pos[] on the 1h grid ----
def rule_donchian(g, k, n_in, n_out):
    ts, o, h, l, c = g
    ro, rh, rl, rc, end = resample(ts, o, h, l, c, k)
    a = atr(rh, rl, rc)
    p, pos, stop = [], 0, None
    for j in range(len(rc)):
        if j >= n_in and a[j] is not None:
            hi, lo = max(rh[j - n_in:j]), min(rl[j - n_in:j])
            xhi, xlo = max(rh[j - n_out:j]), min(rl[j - n_out:j])
            if pos == 1 and (rc[j] < xlo or rc[j] <= stop):
                pos = 0
            elif pos == -1 and (rc[j] > xhi or rc[j] >= stop):
                pos = 0
            if pos == 0:
                if rc[j] > hi:
                    pos, stop = 1, rc[j] - STOP_ATR * a[j]
                elif rc[j] < lo:
                    pos, stop = -1, rc[j] + STOP_ATR * a[j]
        p.append(float(pos))
    return expand(len(ts), end, p)


def rule_trend_vt(g, k, fast, slow, vol_n, bars_per_year):
    ts, o, h, l, c = g
    ro, rh, rl, rc, end = resample(ts, o, h, l, c, k)
    f, s, sd = sma(rc, fast), sma(rc, slow), roll_std_logret(rc, vol_n)
    p, d, size = [], 0, 0.0
    for j in range(len(rc)):
        if s[j] is None or sd[j] is None:
            p.append(0.0)
            continue
        nd = 1 if f[j] > s[j] else -1
        tgt = min(SIZE_CAP, VOL_TARGET / (sd[j] * math.sqrt(bars_per_year))) if sd[j] > 1e-9 else SIZE_CAP
        if nd != d or size == 0 or abs(tgt - size) / size > RESIZE:
            d, size = nd, tgt
        p.append(d * size)
    return expand(len(ts), end, p)


def rule_wick(g, side, hold, x_sigma=3.0, vol_n=168):
    ts, o, h, l, c = g
    sd = roll_std_logret(c, vol_n)
    pos, left, cur = [0.0] * len(ts), 0, 0.0
    for i in range(len(ts)):
        if left > 0:
            left -= 1
            if left == 0:
                cur = 0.0
        if cur == 0.0 and i >= 1 and sd[i - 1]:
            mid = (h[i] + l[i]) / 2
            if side > 0 and (o[i] - l[i]) / o[i] >= x_sigma * sd[i - 1] and c[i] > mid:
                cur, left = 1.0, hold
            elif side < 0 and (h[i] - o[i]) / o[i] >= x_sigma * sd[i - 1] and c[i] < mid:
                cur, left = -1.0, hold
        pos[i] = cur
    return pos


def rule_weekly_open(g, frac=0.5):
    ts, o, h, l, c = g
    pos, cur = [0.0] * len(ts), 0.0
    wopen, wh, wl, prev_r, entered = None, None, None, None, False
    for i, t in enumerate(ts):
        if (t // 86400 + 3) % 7 == 0 and t % 86400 == 0:           # Monday 00:00 UTC
            if wh is not None and wopen is not None:
                prev_r = wh - wl
            wopen, wh, wl, entered, cur = o[i], h[i], l[i], False, 0.0
        elif wopen is not None:
            wh, wl = max(wh, h[i]), min(wl, l[i])
        if wopen is not None and prev_r:
            if cur == 0.0 and not entered:
                if c[i] >= wopen + frac * prev_r:
                    cur, entered = 1.0, True
                elif c[i] <= wopen - frac * prev_r:
                    cur, entered = -1.0, True
            elif cur == 1.0 and c[i] <= wopen or cur == -1.0 and c[i] >= wopen:
                cur = 0.0
            if ((t + HOUR) // 86400 + 3) % 7 == 0 and (t + HOUR) % 86400 == 0:   # last hour of the week
                cur = 0.0
        pos[i] = cur
    return pos


def rule_pullback(g, k=4, sma_n=200, rsi_n=14, lo_in=35, hi_in=65, lo_out=55, hi_out=45, max_hold=42):
    ts, o, h, l, c = g
    ro, rh, rl, rc, end = resample(ts, o, h, l, c, k)
    m, r, a = sma(rc, sma_n), rsi(rc, rsi_n), atr(rh, rl, rc)
    p, pos, held, stop = [], 0, 0, None
    for j in range(len(rc)):
        if m[j] is None or r[j] is None or a[j] is None:
            p.append(0.0)
            continue
        if pos != 0:
            held += 1
            out = held >= max_hold
            if pos == 1:
                out = out or r[j] > lo_out or rc[j] < m[j] or rc[j] <= stop
            else:
                out = out or r[j] < hi_out or rc[j] > m[j] or rc[j] >= stop
            if out:
                pos = 0
        if pos == 0:
            if rc[j] > m[j] and r[j] < lo_in:
                pos, held, stop = 1, 0, rc[j] - STOP_ATR * a[j]
            elif rc[j] < m[j] and r[j] > hi_in:
                pos, held, stop = -1, 0, rc[j] + STOP_ATR * a[j]
        p.append(float(pos))
    return expand(len(ts), end, p)


RULES = {
    "don_1h_55": lambda g: rule_donchian(g, 1, 55, 20),
    "don_4h_20": lambda g: rule_donchian(g, 4, 20, 10),
    "don_4h_55": lambda g: rule_donchian(g, 4, 55, 20),
    "ma_4h_20_100": lambda g: rule_trend_vt(g, 4, 20, 100, 180, 6 * 365),
    "ma_1d_20_100": lambda g: rule_trend_vt(g, 24, 20, 100, 30, 365),
    "wick_long_4h": lambda g: rule_wick(g, +1, 4),
    "wick_long_24h": lambda g: rule_wick(g, +1, 24),
    "wick_short_4h": lambda g: rule_wick(g, -1, 4),
    "weekly_open_break": lambda g: rule_weekly_open(g),
    "trend_pullback_4h": lambda g: rule_pullback(g),
}
assert tuple(RULES) == RULE_NAMES


# ---- engine ----
def hourly_returns(ts, c, pos, funding, cost_mult=1.0):
    """[(t_{i+1}, r)] for i = 0..n-2 (stamped at the start of the hour the return is earned in): position decided at bar i's close earns bar i+1's close-to-close return, minus the
    cost of changing the position at that close and the measured funding settled at t_{i+1} (funding: {hour_ts: rate},
    long pays when positive)."""
    out, prev = [], 0.0
    for i in range(len(ts) - 1):
        p = pos[i]
        r = p * (c[i + 1] / c[i] - 1) - cost_mult * ONE_WAY * abs(p - prev) - p * funding.get(ts[i + 1], 0.0)
        out.append((ts[i + 1], r))
        prev = p
    return out


def entries(ts, pos, a, b):
    """Number of entries (flat -> position, or a sign flip) with a <= ts < b."""
    n, prev = 0, 0.0
    for t, p in zip(ts, pos):
        if a <= t < b and p != 0 and (prev == 0 or (p > 0) != (prev > 0)):
            n += 1
        prev = p
    return n


def portfolio(per_symbol, n_slots):
    """per_symbol: [[(t, r)]] -> summed hourly series with every symbol weighted 1/n_slots; t union, missing = 0."""
    acc = {}
    for s in per_symbol:
        for t, r in s:
            acc[t] = acc.get(t, 0.0) + r / n_slots
    return sorted(acc.items())


def daily(series):
    by = {}
    for t, r in series:
        d = t // 86400 * 86400
        by[d] = by.get(d, 0.0) + r
    return sorted(by.items())


def funding_map(rows):
    """[(ts_s, rate)] -> {hour_ts: summed rate}; a settlement stamped a few ms past the hour belongs to that hour."""
    out = {}
    for t, r in rows:
        k = int(t) // HOUR * HOUR
        out[k] = out.get(k, 0.0) + r
    return out


def lev_table(hourly, a, b, levs=LEVS):
    """Per leverage on [a, b): months with equity multiple >= 3, median, worst, and months that fell to <= 10% of the
    month's start at any hour (ruined). Constant leverage rebalanced hourly; a bar of -100% or worse is ruin."""
    by = {}
    for t, r in hourly:
        if a <= t < b:
            by.setdefault(time.strftime("%Y-%m", time.gmtime(t)), []).append(r)
    out = []
    for lev in levs:
        mults, ruined = [], 0
        for _m, rs in sorted(by.items()):
            eq, low = 1.0, 1.0
            for r in rs:
                eq *= max(0.0, 1 + lev * r)
                low = min(low, eq)
            mults.append(eq)
            ruined += low <= 0.10
        if mults:
            out.append({"lev": lev, "months": len(mults), "months_3x": sum(m >= 3 for m in mults),
                        "median_month": sorted(mults)[len(mults) // 2], "worst_month": min(mults), "ruined": ruined})
    return out


def split_stats(daily_series, bounds):
    out = {}
    for sp, (a, b) in bounds.items():
        v = [r for t, r in daily_series if a <= t < b]
        out[sp] = {"days": len(v), "mean_day": mean(v) if v else None,
                   "p_block": fa.block_p(v) if sp != "train" or len(v) > 40 else None,
                   "losing_days": sum(r < 0 for r in v), "nonzero_days": sum(r != 0 for r in v)}
    return out


def integrity(coverage, bounds, min_bars=0.97, min_funding=0.90):
    """coverage: {sym: {"bars": {split: n_present}, "hours": {split: n_expected}, "funding": {split: n}, "failed": [dates]}}
    Expected hours are counted from the symbol's first bar. ok is False when the run is void."""
    problems, warnings = [], []
    v0, v1 = bounds["validation"]
    for s, c in coverage.items():
        if c["failed"]:
            problems.append(f"{s}: monthly files failed {c['failed'][:5]}")
        exp = c["hours"].get("validation", 0)
        if exp and c["bars"].get("validation", 0) / exp < min_bars:
            problems.append(f"{s}: validation bars {c['bars'].get('validation', 0)}/{exp}")
        if exp and c["funding"].get("validation", 0) < min_funding * exp / 8:
            problems.append(f"{s}: validation funding settlements {c['funding'].get('validation', 0)} < {min_funding:.0%} of {exp / 8:.0f}")
        if exp == 0:
            problems.append(f"{s}: no validation hours")
        for sp in ("train", "test"):                      # not part of the void rule: reported so a gap is visible
            e = c["hours"].get(sp, 0)
            if e and c["bars"].get(sp, 0) / e < min_bars:
                warnings.append(f"{s}: {sp} bars {c['bars'].get(sp, 0)}/{e}")
            if e and c["funding"].get(sp, 0) < min_funding * e / 8:
                warnings.append(f"{s}: {sp} funding settlements {c['funding'].get(sp, 0)} < {min_funding:.0%} of {e / 8:.0f}")
    return {"ok": not problems, "problems": problems, "warnings": warnings}


def red_flags(per_rule):
    """Sanity warnings: results identical across rules, p at the floor on most rules, no losing day in a split."""
    w = []
    means = [round(r["validation"]["mean_day"], 12) for r in per_rule.values() if r["validation"]["mean_day"] is not None]
    if len(means) > 1 and len(set(means)) < len(means):
        w.append("two rules have an identical validation mean")
    floor = [n for n, r in per_rule.items() if r["validation"]["p_block"] is not None and r["validation"]["p_block"] <= 0.0006]
    if len(floor) >= max(3, len(per_rule) // 2):
        w.append(f"p at the floor on {len(floor)} rules")
    for n, r in per_rule.items():
        for sp, x in r.items():
            if isinstance(x, dict) and x.get("days", 0) > 30 and x.get("nonzero_days", 0) > 30 and x.get("losing_days") == 0:
                w.append(f"{n}/{sp}: no losing day")
    return w
