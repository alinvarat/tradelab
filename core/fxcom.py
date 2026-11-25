"""fxcom_1: eight pre-registered rules on FX, gold and commodities (protocol: research/studies/protocol_fxcom_1.md).

Pure calculations: loaders take injected fetchers so everything is testable offline. Yahoo bar timestamps are bar
STARTS; a decision at the close of bar t fills at the open of bar t+1. Local times come from zoneinfo on raw UTC
timestamps (never a +12h shift). Simulated research only."""
import bisect
import calendar
import math
import random
import time
import urllib.request
from collections import deque, namedtuple
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")

FX_PAIRS = {"EURUSD=X": ("EUR", "USD"), "GBPUSD=X": ("GBP", "USD"), "AUDUSD=X": ("AUD", "USD"),
            "NZDUSD=X": ("NZD", "USD"), "USDJPY=X": ("USD", "JPY"), "USDCAD=X": ("USD", "CAD"),
            "USDCHF=X": ("USD", "CHF")}
COMMODITIES = ["GC=F", "SI=F", "HG=F", "CL=F", "BZ=F", "NG=F", "ZC=F"]
COST_SIDE = {"EURUSD=X": 0.00015, "USDJPY=X": 0.00015, "GBPUSD=X": 0.00015, "USDCAD=X": 0.00015,
             "USDCHF=X": 0.00015, "AUDUSD=X": 0.00025, "NZDUSD=X": 0.00025, "GC=F": 0.0006, "SI=F": 0.0010,
             "HG=F": 0.0010, "CL=F": 0.0010, "BZ=F": 0.0010, "NG=F": 0.0015, "ZC=F": 0.0012}
FUND_LONG_DAY, FUND_SHORT_DAY = 0.0004, 0.0001     # commodity perp-style holding cost per calendar day of notional
MARKUP_YEAR = 0.005
FRED = {"USD": ("DFF", 1), "EUR": ("ECBDFR", 1), "JPY": ("IRSTCI01JPM156N", 45), "AUD": ("IR3TIB01AUM156N", 45),
        "CAD": ("IR3TIB01CAM156N", 45), "CHF": ("IR3TIB01CHM156N", 45), "NZD": ("IR3TIB01NZM156N", 45)}
DAILY_R1 = ["GC=F", "SI=F", "HG=F", "CL=F", "BZ=F", "NG=F", "ZC=F", "EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X",
            "USDCAD=X"]
DAILY_R7 = ["EURUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X"]
HOURLY = ["GC=F", "SI=F", "HG=F", "CL=F", "BZ=F", "NG=F", "EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X",
          "USDCAD=X", "USDCHF=X", "NZDUSD=X"]
R5_ASSETS = ["EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X", "GC=F", "SI=F"]
R6_FX_METAL = ["GC=F", "SI=F", "EURUSD=X", "USDJPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X", "USDCHF=X", "NZDUSD=X"]
PAIRS_R8 = [("GC=F", "SI=F"), ("CL=F", "BZ=F")]
DAILY_RULES = ["R1_tsmom_voltarget", "R7_fx_carry_volscaled"]
HOURLY_RULES = ["R2_hourly_breakout", "R3_hourly_overextension_fade", "R4_ny_session_continuation",
                "R5_london_breakout_asia_range", "R6_macro_release_fade", "R8_metal_energy_spread_reversion"]
ALL_RULES = ["R1_tsmom_voltarget", "R2_hourly_breakout", "R3_hourly_overextension_fade",
             "R4_ny_session_continuation", "R5_london_breakout_asia_range", "R6_macro_release_fade",
             "R7_fx_carry_volscaled", "R8_metal_energy_spread_reversion"]
RISK_PER_TRADE, RISK_CAP, START_EQUITY, MIN_NOTIONAL = 0.01, 0.04, 147.0, 5.0

Trade = namedtuple("Trade", "t_in t_out asset side px_in px_out size risk grp")


def is_fx(sym):
    return sym in FX_PAIRS


def lev_cap(sym):
    return 20.0 if is_fx(sym) else 10.0


def utc(y, m=1, d=1, h=0):
    return datetime(y, m, d, h, tzinfo=timezone.utc).timestamp()


def day_ts(d):
    """UTC midnight timestamp of a date."""
    return float(calendar.timegm(d.timetuple()))


# ------------------------------------------------------------------ calendar helpers

def _observed(d):
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def _nth_weekday(y, m, wd, n):
    d = date(y, m, 1)
    d += timedelta(days=(wd - d.weekday()) % 7)
    return d + timedelta(days=7 * (n - 1))


def us_holidays(year):
    """US federal holidays (observed dates) of one calendar year."""
    last_mon_may = max(d for d in (date(year, 5, k) for k in range(25, 32)) if d.weekday() == 0)
    out = {_observed(date(year, 1, 1)), _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3), last_mon_may,
           _observed(date(year, 6, 19)), _observed(date(year, 7, 4)), _nth_weekday(year, 9, 0, 1),
           _nth_weekday(year, 10, 0, 2), _observed(date(year, 11, 11)), _nth_weekday(year, 11, 3, 4),
           _observed(date(year, 12, 25))}
    return out


_HOL = {}


def is_holiday(d):
    for y in (d.year, d.year + 1):
        if y not in _HOL:
            _HOL[y] = us_holidays(y)
    return d in _HOL[d.year] or d in _HOL[d.year + 1]


def week_has_holiday(d):
    """True when the Monday-Sunday week of d has a US federal holiday Monday-Thursday (releases slip)."""
    mon = d - timedelta(days=d.weekday())
    return any(is_holiday(mon + timedelta(days=k)) for k in range(4))


def release_times(sym, d):
    """[(hour, minute)] ET releases of the mechanical R6 calendar for asset `sym` on date d."""
    if week_has_holiday(d):
        return []
    wd, out = d.weekday(), []
    if sym in R6_FX_METAL:
        if wd == 3:
            out.append((8, 30))
        if wd == 4 and d.day <= 7:
            out.append((8, 30))
    elif sym in ("CL=F", "BZ=F"):
        if wd == 2:
            out.append((10, 30))
    elif sym == "NG=F":
        if wd == 3:
            out.append((10, 30))
    return out


# ------------------------------------------------------------------ rolling statistics

def rolling_mean_std(x, n, minn):
    """(mean, std) over x[i-n+1..i] (current included); None until minn values exist. x may hold None (treated as 0)."""
    s1, s2, q = 0.0, 0.0, deque()
    m_out, s_out = [], []
    for v in x:
        v = 0.0 if v is None else v
        q.append(v)
        s1 += v
        s2 += v * v
        if len(q) > n:
            u = q.popleft()
            s1 -= u
            s2 -= u * u
        k = len(q)
        if k >= minn:
            m = s1 / k
            m_out.append(m)
            s_out.append(math.sqrt(max(0.0, s2 / k - m * m)))
        else:
            m_out.append(None)
            s_out.append(None)
    return m_out, s_out


# ------------------------------------------------------------------ rates (FRED)

def parse_fred_csv(text):
    """[(obs_ts, value)] from a fredgraph.csv body; missing '.' rows are skipped."""
    out = []
    for line in text.strip().splitlines()[1:]:
        p = line.split(",")
        if len(p) < 2 or p[1].strip() in ("", "."):
            continue
        try:
            y, m, d = (int(k) for k in p[0].split("-"))
            out.append((day_ts(date(y, m, d)), float(p[1])))
        except ValueError:
            continue
    return out


def fetch_fred_text(series_id, tries=3, timeout=30):
    """Default urllib User-Agent first (a Mozilla UA failed once); None after the retries."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode()
        except Exception:  # noqa: BLE001
            time.sleep(1 + k)
    return None


class Rates:
    """Point-in-time policy rates in percent per year: a value is usable `lag` days after its observation date."""

    def __init__(self, series=None, lags=None):
        self.avail, self.vals, self.missing = {}, {}, {}
        for ccy, rows in (series or {}).items():
            lag = (lags or {}).get(ccy, 1) * 86400
            rows = sorted(rows)
            self.avail[ccy] = [t + lag for t, _ in rows]
            self.vals[ccy] = [v for _, v in rows]

    def get(self, ccy, ts):
        a = self.avail.get(ccy)
        if not a:
            return None
        i = bisect.bisect_right(a, ts) - 1
        return self.vals[ccy][i] if i >= 0 else None

    def annual(self, ccy, ts):
        """Rate as a fraction per year; a missing rate counts as a gap and is taken as 0."""
        v = self.get(ccy, ts)
        if v is None:
            self.missing[ccy] = self.missing.get(ccy, 0) + 1
            return 0.0
        return v / 100.0

    def diff(self, base, quote, ts):
        return self.annual(base, ts) - self.annual(quote, ts)


def load_rates(fetch_text=fetch_fred_text):
    series, gaps = {}, {}
    for ccy, (sid, _lag) in FRED.items():
        txt = fetch_text(sid)
        rows = parse_fred_csv(txt) if txt else []
        if rows:
            series[ccy] = rows
        else:
            gaps[ccy] = "fetch failed or empty"
    return Rates(series, {c: v[1] for c, v in FRED.items()}), gaps


# ------------------------------------------------------------------ daily data

class Daily:
    def __init__(self, sym, dates, o, c, clipped):
        self.sym, self.dates, self.o, self.c, self.clipped = sym, dates, o, c, clipped
        n = len(c)
        self.ret = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, n)]
        _, sd = rolling_mean_std(self.ret[1:], 60, 60)
        self.sig60 = [None] + [None if s is None else s * math.sqrt(252) for s in sd]   # annualised, incl. bar i
        self.index = {d: i for i, d in enumerate(dates)}


def build_daily(sym, chart, run_ts, guard=True):
    """Daily bars -> Daily. Date key = local date in the chart's exchange timezone; the last bar is dropped when its
    date is not before the run date. Returns clipped to +-4 trailing-60d sigma (clip, symmetric) when guard."""
    tzname = (chart.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
    try:
        tz = ZoneInfo(tzname)
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    today = datetime.fromtimestamp(run_ts, timezone.utc).date()
    by = {}
    for b in chart["bars"]:
        d = datetime.fromtimestamp(b["t"], tz).date()
        if d >= today:
            continue
        by[d] = (b["o"], b["c"])
    dates = sorted(by)
    if not dates:
        return Daily(sym, [], [], [], 0)
    raw_c = [by[d][1] for d in dates]
    raw_o = [by[d][0] for d in dates]
    ac, ao, win, s1, s2, clipped = [raw_c[0]], [raw_o[0]], deque(), 0.0, 0.0, 0
    for i in range(1, len(dates)):
        r = raw_c[i] / raw_c[i - 1] - 1
        if guard and len(win) >= 20:
            k = len(win)
            m = s1 / k
            sd = math.sqrt(max(0.0, s2 / k - m * m))
            if sd > 0 and abs(r) > 4 * sd:
                r = math.copysign(4 * sd, r)
                clipped += 1
        ac.append(ac[-1] * (1 + r))
        ao.append(raw_o[i] * ac[-1] / raw_c[i])
        win.append(r)
        s1 += r
        s2 += r * r
        if len(win) > 60:
            u = win.popleft()
            s1 -= u
            s2 -= u * u
    return Daily(sym, dates, ao, ac, clipped)


# ------------------------------------------------------------------ hourly data

def gate_hourly(bars, min_bars=9000):
    """Bars sorted, deduplicated, last (possibly unfinished) bar dropped, off-the-hour bars dropped.
    -> (ok, info, clean_bars)."""
    by = {}
    for b in bars:
        by[b["t"]] = b
    rows = [by[t] for t in sorted(by)][:-1]
    off = [b for b in rows if b["t"] % 3600 != 0]
    clean = [b for b in rows if b["t"] % 3600 == 0]
    info = {"bars": len(clean), "off_hour": len(off)}
    ok = len(clean) >= min_bars and len(off) <= 0.01 * max(1, len(rows))
    info["ok"] = ok
    return ok, info, clean


class Hourly:
    def __init__(self, sym, ts, o, c, rolls):
        self.sym, self.ts, self.o, self.c, self.rolls = sym, ts, o, c, rolls
        n = len(ts)
        e = [datetime.fromtimestamp(t, ET) for t in ts]
        self.edate = [x.date() for x in e]
        self.ehour = [x.hour for x in e]
        lo = [datetime.fromtimestamp(t, LON) for t in ts]
        self.lhour = [x.hour for x in lo]
        self.uday = [int(t // 86400) for t in ts]
        self.uhour = [int((t % 86400) // 3600) for t in ts]
        self.flag = [self.ehour[i] == 17 or i == 0 or ts[i] - ts[i - 1] > 3600 for i in range(n)]
        self.gap_after = [i == n - 1 or ts[i + 1] - ts[i] > 3600 for i in range(n)]
        self.ret = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, n)]
        self.rmean, self.rstd = rolling_mean_std(self.ret, 480, 240)
        self.idx = {t: i for i, t in enumerate(ts)}
        self.et_idx = {}
        for i in range(n):
            self.et_idx.setdefault((self.edate[i], self.ehour[i]), i)


def adjust_hourly(sym, bars, guard=True):
    """Bars (clean) -> Hourly. With guard, close-to-close returns beyond 8 trailing-480h sigma are set to 0 on an
    adjusted price series (opens carry the same factor); counted as rolls."""
    ts = [b["t"] for b in bars]
    ac, ao, rolls = [bars[0]["c"]], [bars[0]["o"]], 0
    win, s1, s2 = deque(), 0.0, 0.0
    for i in range(1, len(bars)):
        r = bars[i]["c"] / bars[i - 1]["c"] - 1
        if guard and len(win) >= 100:
            k = len(win)
            m = s1 / k
            sd = math.sqrt(max(0.0, s2 / k - m * m))
            if sd > 0 and abs(r) > 8 * sd:
                r = 0.0
                rolls += 1
        ac.append(ac[-1] * (1 + r))
        ao.append(bars[i]["o"] * ac[-1] / bars[i]["c"])
        win.append(r)
        s1 += r
        s2 += r * r
        if len(win) > 480:
            u = win.popleft()
            s1 -= u
            s2 -= u * u
    return Hourly(sym, ts, ao, ac, rolls)


# ------------------------------------------------------------------ costs

def hold_cost_hourly(sym, side, t_in, t_out, rates, mult=1.0):
    """Holding cost as a fraction of notional (negative = credit) for a hold from t_in to t_out (UTC seconds)."""
    if not is_fx(sym):
        rate = FUND_LONG_DAY if side > 0 else FUND_SHORT_DAY
        return rate * (t_out - t_in) / 86400.0 * mult
    base, quote = FX_PAIRS[sym]
    cost = 0.0
    d0 = datetime.fromtimestamp(t_in, ET).date()
    d1 = datetime.fromtimestamp(t_out, ET).date()
    d = d0
    while d <= d1:
        cross = datetime(d.year, d.month, d.day, 17, 0, tzinfo=ET).timestamp()
        if t_in < cross <= t_out:
            days = 3 if d.weekday() == 2 else 1
            cost += days / 365.0 * (MARKUP_YEAR * mult - side * rates.diff(base, quote, cross))
        d += timedelta(days=1)
    return cost


def trade_frac(tr, rates, mult=1.0, flip=False):
    """Equity return of one trade leg: size x (gain - round-trip cost - holding cost); gain = side x (exit/entry - 1)."""
    side = -tr.side if flip else tr.side
    gain = side * (tr.px_out / tr.px_in - 1)
    return tr.size * (gain - 2 * COST_SIDE[tr.asset] * mult
                      - hold_cost_hourly(tr.asset, side, tr.t_in, tr.t_out, rates, mult))


def group_frac(group, rates, mult=1.0, flip=False):
    return sum(trade_frac(t, rates, mult, flip) for t in group)


# ------------------------------------------------------------------ hourly rule engine

def can_enter(h, t, delay=0):
    e = t + 1 + delay
    return (e < len(h.ts) and not h.flag[t] and not h.flag[e] and h.ts[e] - h.ts[t] == 3600 * (1 + delay))


def size_for(sym, stop_frac):
    if stop_frac is None or stop_frac <= 0:
        return None
    return min(lev_cap(sym), RISK_PER_TRADE / stop_frac)


def hold(h, e, side, stop_px=None, max_bars=None, exit_sig=None, fixed_x=None):
    """Walk bar closes after an entry at the open of bar e. -> (px_out, t_out, next_signal_bar).
    Order at each close s: flat before a gap / fixed exit bar (fills at close s), stop, signal, max bars
    (fill at the open of s+1)."""
    s = e
    while True:
        if h.gap_after[s] or (fixed_x is not None and s >= fixed_x):
            return h.c[s], h.ts[s] + 3600, s + 1, h.gap_after[s] and (fixed_x is None or s < fixed_x)
        c = h.c[s]
        hit = stop_px is not None and ((side > 0 and c <= stop_px) or (side < 0 and c >= stop_px))
        if hit or (exit_sig is not None and exit_sig(s)) or (max_bars is not None and s + 1 - e >= max_bars):
            return h.o[s + 1], h.ts[s + 1], s + 1, False
        s += 1


def _mk(h, t_in_idx, side, entry, px_out, t_out, stop_frac, grp):
    size = size_for(h.sym, stop_frac)
    if size is None:
        return None
    return Trade(h.ts[t_in_idx], t_out, h.sym, side, entry, px_out, size, size * stop_frac, grp)


def rule_r2(h, delay=0):
    n, c, out = len(h.ts), h.c, []
    ad = [0.0] + [abs(c[i] - c[i - 1]) for i in range(1, n)]
    t = 48
    while t < n - 1:
        if h.flag[t]:
            t += 1
            continue
        hi, lo = max(c[t - 48:t]), min(c[t - 48:t])
        side = 1 if c[t] > hi else -1 if c[t] < lo else 0
        if not side or not can_enter(h, t, delay):
            t += 1
            continue
        e = t + 1 + delay
        entry = h.o[e]
        dist = 2.0 * (sum(ad[t - 23:t + 1]) / 24.0)
        if dist <= 0:
            t += 1
            continue
        stop_px = entry - side * dist

        def sig(s, side=side):
            w = c[s - 24:s]
            return c[s] < min(w) if side > 0 else c[s] > max(w)
        px, t_out, nxt, forced = hold(h, e, side, stop_px, 48, sig)
        tr = _mk(h, e, side, entry, px, t_out, dist / entry, f"{h.sym}:{h.ts[e]}")
        if tr:
            out.append([tr])
        t = max(nxt, t + 1)
    return out


def release_bars(h):
    """Indices of the R6 release bars of this asset (bar containing the release time), whether or not R6 trades them."""
    out = []
    d, last = h.edate[0], h.edate[-1]
    while d <= last:
        for hh, mm in release_times(h.sym, d):
            ts = datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp()
            i = h.idx.get(ts - ts % 3600)
            if i is not None:
                out.append(i)
        d += timedelta(days=1)
    return out


def rule_r3(h, delay=0):
    n, c, out = len(h.ts), h.c, []
    blocked = set()
    for k in release_bars(h):
        blocked.update(range(k, k + 4))
    t = 6
    while t < n - 1:
        sd = h.rstd[t]
        if t in blocked or sd is None or sd <= 0 or h.flag[t]:
            t += 1
            continue
        r6 = c[t] / c[t - 6] - 1
        if abs(r6) < 3.0 * sd * math.sqrt(6) or not can_enter(h, t, delay):
            t += 1
            continue
        side = -1 if r6 > 0 else 1
        e = t + 1 + delay
        entry = h.o[e]
        stop_frac = 1.5 * abs(r6)
        stop_px = entry * (1 - side * stop_frac)
        px, t_out, nxt, _ = hold(h, e, side, stop_px, 6)
        tr = _mk(h, e, side, entry, px, t_out, stop_frac, f"{h.sym}:{h.ts[e]}")
        if tr:
            out.append([tr])
        t = max(nxt, t + 1)
    return out


def rule_r4(h, delay=0):
    out, c = [], h.c
    ms, hs = [], []                                      # M and 7h-hold returns of previous trading days
    days = sorted({d for d in h.edate})
    for D in days:
        e0 = h.et_idx.get((D, 8))
        i7 = h.et_idx.get((D, 7))
        i18 = h.et_idx.get((D - timedelta(days=1), 18))
        x = h.et_idx.get((D, 14))
        m = hold_ret = None
        if i7 is not None and i18 is not None:
            m = c[i7] / c[i18] - 1
        if e0 is not None and x is not None and h.ts[x] - h.ts[e0] == 6 * 3600:
            hold_ret = c[x] / h.o[e0] - 1
        wm, wh = ms[-60:], hs[-60:]
        if (D.weekday() < 5 and not is_holiday(D) and m is not None and hold_ret is not None
                and len(wm) >= 40 and len(wh) >= 40):
            sg, sgh = pstdev(wm), pstdev(wh)
            e = e0 + delay if e0 is not None else None
            if sg > 0 and sgh > 0 and abs(m) >= 0.5 * sg and e is not None and e <= x and not h.flag[e] \
                    and h.ts[e] - h.ts[e0] == 3600 * delay:
                side = 1 if m > 0 else -1
                entry = h.o[e]
                stop_px = entry * (1 - side * 1.5 * sgh)
                px, t_out, nxt, _ = hold(h, e, side, stop_px, None, None, x)
                tr = _mk(h, e, side, entry, px, t_out, 1.5 * sgh, f"{h.sym}:{h.ts[e]}")
                if tr:
                    out.append([tr])
        if m is not None:
            ms.append(m)
        if hold_ret is not None:
            hs.append(hold_ret)
    return out


def rule_r5(h, delay=0):
    out, c = [], h.c
    by_day = {}
    for i, u in enumerate(h.uday):
        by_day.setdefault(u, []).append(i)
    for u, idxs in sorted(by_day.items()):
        asia = [i for i in idxs if h.uhour[i] <= 5]
        if len(asia) != 6 or h.ts[asia[-1]] - h.ts[asia[0]] != 5 * 3600:
            continue
        hi, lo = max(c[i] for i in asia), min(c[i] for i in asia)
        width = (hi - lo) / c[asia[-1]]
        if not 0.0015 <= width <= 0.012:
            continue
        win = [i for i in idxs if 7 <= h.lhour[i] <= 10 and h.uhour[i] >= 6]
        xs = [i for i in idxs if h.lhour[i] == 15]
        if not xs:
            continue
        x = xs[0]
        sig_t = next((t for t in win if c[t] > hi or c[t] < lo), None)
        if sig_t is None or not can_enter(h, sig_t, delay):
            continue
        side = 1 if c[sig_t] > hi else -1
        e = sig_t + 1 + delay
        if e > x:
            continue
        entry = h.o[e]
        far = (entry - lo) if side > 0 else (hi - entry)
        dist = min(far, 0.015 * entry)
        if dist <= 0:
            continue
        px, t_out, nxt, _ = hold(h, e, side, entry - side * dist, None, None, x)
        tr = _mk(h, e, side, entry, px, t_out, dist / entry, f"{h.sym}:{h.ts[e]}")
        if tr:
            out.append([tr])
    return out


def rule_r6(h, delay=0):
    out, c = [], h.c
    next_free = 0
    for k in release_bars(h):
        sd = h.rstd[k]
        if k < next_free or sd is None or sd <= 0 or h.flag[k] or not can_enter(h, k, delay):
            continue
        move = c[k] - c[k - 1]
        z = (c[k] / c[k - 1] - 1) / sd
        if abs(z) < 1.0 or move == 0:
            continue
        mv = 1 if move > 0 else -1
        side = -mv
        e = k + 1 + delay
        entry = h.o[e]
        stop_px = c[k] + mv * abs(move)
        if (mv > 0 and entry >= stop_px) or (mv < 0 and entry <= stop_px):
            continue
        px, t_out, nxt, _ = hold(h, e, side, stop_px, 3)
        tr = _mk(h, e, side, entry, px, t_out, abs(stop_px - entry) / entry, f"{h.sym}:{h.ts[e]}")
        if tr:
            out.append([tr])
        next_free = nxt
    return out


class PairH:
    """Two Hourly series on the hours where both bars exist."""

    def __init__(self, a, b):
        common = sorted(set(a.ts) & set(b.ts))
        ia, ib = [a.idx[t] for t in common], [b.idx[t] for t in common]
        self.ts = common
        self.a_sym, self.b_sym = a.sym, b.sym
        self.oa, self.ca = [a.o[i] for i in ia], [a.c[i] for i in ia]
        self.ob, self.cb = [b.o[i] for i in ib], [b.c[i] for i in ib]
        n = len(common)
        self.flag = [a.flag[ia[i]] or b.flag[ib[i]] or i == 0 or common[i] - common[i - 1] > 3600 for i in range(n)]
        self.gap_after = [i == n - 1 or common[i + 1] - common[i] > 3600 for i in range(n)]
        self.spread = [math.log(self.ca[i]) - math.log(self.cb[i]) for i in range(n)]
        self.mean, self.std = rolling_mean_std(self.spread, 480, 240)
        self.z = [None if self.std[i] in (None, 0) else (self.spread[i] - self.mean[i]) / self.std[i]
                  for i in range(n)]


def rule_r8(p, delay=0):
    out, n = [], len(p.ts)
    t = 0
    while t < n - 1:
        z = p.z[t]
        e = t + 1 + delay
        if (z is None or abs(z) < 2.5 or abs(z) >= 4.0 or p.flag[t] or e >= n or p.flag[e]
                or p.ts[e] - p.ts[t] != 3600 * (1 + delay)):
            t += 1
            continue
        sa = -1 if z > 0 else 1                           # z > 0: short A, long B
        stop_frac = (4.0 - abs(z)) * p.std[t]
        size = min(3.0, RISK_PER_TRADE / stop_frac) if stop_frac > 0 else None
        if size is None:
            t += 1
            continue
        s = e
        while True:
            zs = p.z[s]
            if p.gap_after[s]:
                xi, t_out, fa, fb, nxt = s, p.ts[s] + 3600, p.ca[s], p.cb[s], s + 1
                break
            if (zs is not None and (abs(zs) <= 0.5 or abs(zs) >= 4.0)) or s + 1 - e >= 72:
                xi, t_out, fa, fb, nxt = s + 1, p.ts[s + 1], p.oa[s + 1], p.ob[s + 1], s + 1
                break
            s += 1
        g = f"{p.a_sym}/{p.b_sym}:{p.ts[e]}"
        out.append([Trade(p.ts[e], t_out, p.a_sym, sa, p.oa[e], fa, size, size * stop_frac, g),
                    Trade(p.ts[e], t_out, p.b_sym, -sa, p.ob[e], fb, size, 0.0, g)])
        t = max(nxt, t + 1)
    return out


def cap_groups(groups, cap=RISK_CAP):
    """Accept groups in entry order; skip one that would push total open risk over `cap` of equity."""
    groups = sorted(groups, key=lambda g: (g[0].t_in, g[0].grp))
    open_, ok, skipped = [], [], 0
    for g in groups:
        t_in = g[0].t_in
        open_ = [(to, r) for to, r in open_ if to > t_in]
        risk = sum(t.risk for t in g)
        if sum(r for _, r in open_) + risk > cap + 1e-12:
            skipped += 1
            continue
        open_.append((max(t.t_out for t in g), risk))
        ok.append(g)
    return ok, skipped


def hourly_trades(hs, rule, delay=0):
    """All groups of one hourly rule over the Hourly dict `hs`, risk-capped. -> (groups, skipped_cap)."""
    allg = []
    if rule == "R8_metal_energy_spread_reversion":
        for a, b in PAIRS_R8:
            if a in hs and b in hs:
                allg += rule_r8(PairH(hs[a], hs[b]), delay)
    else:
        fn = {"R2_hourly_breakout": rule_r2, "R3_hourly_overextension_fade": rule_r3,
              "R4_ny_session_continuation": rule_r4, "R5_london_breakout_asia_range": rule_r5,
              "R6_macro_release_fade": rule_r6}[rule]
        for sym, h in sorted(hs.items()):
            if rule == "R5_london_breakout_asia_range" and sym not in R5_ASSETS:
                continue
            if rule == "R6_macro_release_fade" and not (sym in R6_FX_METAL or sym in ("CL=F", "BZ=F", "NG=F")):
                continue
            allg += fn(h, delay)
    return cap_groups(allg)


# ------------------------------------------------------------------ daily portfolio engine (R1, R7)

def hold_cost_daily(sym, w, d0, d1, rates, mult):
    """Holding cost of weight w over the calendar days from d0 to d1 as a fraction of equity (negative = credit)."""
    days = (d1 - d0).days
    if w == 0 or days <= 0:
        return 0.0
    if not is_fx(sym):
        return abs(w) * (FUND_LONG_DAY if w > 0 else FUND_SHORT_DAY) * days * mult
    base, quote = FX_PAIRS[sym]
    diff = rates.diff(base, quote, day_ts(d1))
    return days / 365.0 * (abs(w) * MARKUP_YEAR * mult - w * diff)


def r1_targets(data, d, units):
    """Raw R1 target weights at date d for assets that have a bar and 253+ bars."""
    out = {}
    for sym, a in data.items():
        k = a.index.get(d)
        if k is None or k < 252 or a.sig60[k] is None or a.sig60[k] <= 0:
            continue
        sg = sum((1 if a.c[k] / a.c[k - L] - 1 > 0 else -1 if a.c[k] / a.c[k - L] - 1 < 0 else 0)
                 for L in (21, 63, 126, 252)) / 4.0
        unit = 0.10 / a.sig60[k] / 12.0
        out[sym] = (sg * unit, unit)
    return out


def r7_targets(data, d, rates, grid_end_of_week):
    """Raw R7 targets on the last FX bar of the ISO week: long top 2 / short bottom 2 currencies by rate differential."""
    if not grid_end_of_week:
        return None
    usd = rates.get("USD", day_ts(d))
    if usd is None:
        return None
    sc = {}
    for sym, a in data.items():
        k = a.index.get(d)
        if k is None or k < 60 or a.sig60[k] is None or a.sig60[k] <= 0:
            continue
        base, quote = FX_PAIRS[sym]
        ccy = base if quote == "USD" else quote
        r = rates.get(ccy, day_ts(d))
        if r is None:
            continue
        sc[sym] = (r - usd, (1 if quote == "USD" else -1), 0.10 / a.sig60[k] / 4.0)
    if len(sc) < 4:
        return None
    order = sorted(sc, key=lambda s: sc[s][0], reverse=True)
    out = {s: (0.0, sc[s][2]) for s in sc}
    for s in order[:2]:
        out[s] = (+1 * sc[s][1] * sc[s][2], sc[s][2])
    for s in order[-2:]:
        out[s] = (-1 * sc[s][1] * sc[s][2], sc[s][2])
    return out


def run_daily(data, rates, rule, mult=1.0, delay=0):
    """Daily book. -> (series [(ts, r)], rec, info). rec[sym] = [(date, seg, plus, minus, tc)] for the random control."""
    dates = sorted({d for a in data.values() for d in a.dates})
    wk_end = {}
    for i, d in enumerate(dates):
        nxt = dates[i + 1] if i + 1 < len(dates) else None
        wk_end[d] = nxt is None or nxt.isocalendar()[:2] != d.isocalendar()[:2]
    wdec = {s: {} for s in data}           # decided weight at bar index k
    last_dec = {s: 0.0 for s in data}
    prev_eff = {s: 0.0 for s in data}
    seg = {s: 0 for s in data}
    last_sign = {s: 0 for s in data}
    rec = {s: [] for s in data}
    series, small, posdays, changes = [], 0, 0, 0
    for d in dates:
        day = 0.0
        for sym, a in data.items():
            k = a.index.get(d)
            if k is None or k < 1:
                continue
            j = k - 1 - delay
            w = wdec[sym].get(j, 0.0) if j >= 0 else 0.0
            trade = abs(w - prev_eff[sym])
            tc = trade * COST_SIDE[sym] * mult
            if trade > 1e-12:
                changes += 1
            sgn = 1 if w > 0 else -1 if w < 0 else 0
            if sgn != 0 and sgn != last_sign[sym]:
                seg[sym] += 1
            if sgn != 0:
                last_sign[sym] = sgn
            else:
                last_sign[sym] = 0
            r = a.ret[k]
            d0 = a.dates[k - 1]
            hc = hold_cost_daily(sym, w, d0, d, rates, mult)
            day += w * r - hc - tc
            if sgn != 0 or tc > 0:
                aw = abs(w)
                plus = aw * r - hold_cost_daily(sym, aw if aw else 0.0, d0, d, rates, mult) if aw else 0.0
                minus = -aw * r - hold_cost_daily(sym, -aw, d0, d, rates, mult) if aw else 0.0
                rec[sym].append((d, seg[sym], plus, minus, tc, sgn))
            if sgn != 0:
                posdays += 1
                if abs(w) * START_EQUITY < MIN_NOTIONAL:
                    small += 1
            prev_eff[sym] = w
        series.append((day_ts(d), day))
        # decisions at today's close
        if rule == "R1_tsmom_voltarget":
            raw = r1_targets(data, d, None)
        else:
            raw = r7_targets(data, d, rates, wk_end[d])
        if raw is not None:
            gross = sum(abs(v[0]) for v in raw.values()) + sum(abs(last_dec[s]) for s in data if s not in raw)
            scale = 5.0 / gross if gross > 5.0 else 1.0
            for sym, (tgt, unit) in raw.items():
                tgt *= scale
                if abs(tgt - last_dec[sym]) >= 0.10 * unit * scale - 1e-15:
                    last_dec[sym] = tgt
        for sym, a in data.items():
            k = a.index.get(d)
            if k is not None:
                wdec[sym][k] = last_dec[sym]
    return series, rec, {"changes": changes, "position_days": posdays, "below_min_notional": small}


# ------------------------------------------------------------------ evaluation helpers

def weekdays(a_ts, b_ts):
    """UTC-midnight timestamps of weekdays in [a_ts, b_ts)."""
    out, t = [], a_ts
    while t < b_ts:
        if datetime.fromtimestamp(t, timezone.utc).weekday() < 5:
            out.append(t)
        t += 86400
    return out


def series_from_groups(groups, rates, grid, mult=1.0, flip_bits=None):
    """Daily returns (one per grid day, 0 when flat) from trade groups booked on the UTC date of their exit."""
    by = {}
    for i, g in enumerate(groups):
        flip = bool(flip_bits[i]) if flip_bits is not None else False
        t_out = max(t.t_out for t in g)
        key = t_out - t_out % 86400
        by[key] = by.get(key, 0.0) + group_frac(g, rates, mult, flip)
    days = sorted(set(grid) | set(by))
    return [(t, by.get(t, 0.0)) for t in days]


def sharpe252(v):
    return mean(v) / pstdev(v) * math.sqrt(252) if len(v) > 1 and pstdev(v) > 0 else None


def split_vals(series, a, b):
    return [r for t, r in series if a <= t < b]


def split_stats(series, bounds):
    out = {}
    for sp, (a, b) in bounds.items():
        v = split_vals(series, a, b)
        out[sp] = {"days": len(v), "mean_day": mean(v) if v else None, "sharpe252": sharpe252(v),
                   "total": sum(v) if v else None}
    return out


def trimmed_mean(vals, ndays, frac=0.05):
    """Mean per day after removing the best `frac` of items, and after removing the single best item."""
    if not vals or ndays <= 0:
        return None, None
    s = sorted(vals, reverse=True)
    k = max(1, int(math.ceil(len(s) * frac)))
    return (sum(s[k:]) / ndays, sum(s[1:]) / ndays)


def control_run(actual_total, draws_fn, ndays, n=2000, seed=20261125):
    """Random-direction control: p = share of draws with a total >= the rule's (one-sided), plus the draw spread."""
    rng = random.Random(seed)
    draws = sorted(draws_fn(rng) for _ in range(n))
    ge = sum(1 for x in draws if x >= actual_total - 1e-12)
    nd = max(1, ndays)
    return {"p": (ge + 1) / (n + 1), "rule_mean_day": actual_total / nd, "ctrl_mean_day": mean(draws) / nd,
            "ctrl_p95_mean_day": draws[int(0.95 * (n - 1))] / nd, "draws": n}


def control_trades(pairs):
    """pairs: [(actual, flipped)] per trade. -> draw function returning a random-direction total."""
    def f(rng):
        return sum(b if rng.random() < 0.5 else a for a, b in pairs)
    return f


def control_segments(segs):
    """segs: [(plus_sum, minus_sum)] per position run; fixed (side-independent) costs are already subtracted."""
    def f(rng):
        return sum(a if rng.random() < 0.5 else b for a, b in segs)
    return f


def month_mults(points, t0, t1, start_eq):
    """Calendar-month equity multiples from realised-equity points [(ts, equity)] between t0 and t1."""
    ts = [p[0] for p in points]

    def eq_at(t):
        i = bisect.bisect_right(ts, t) - 1
        return points[i][1] if i >= 0 else start_eq
    out = []
    d = datetime.fromtimestamp(t0, timezone.utc)
    y, m = d.year, d.month
    while True:
        a = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
        b = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc).timestamp()
        if a >= t1:
            break
        e0 = eq_at(max(a, t0) - 1e-6)
        e1 = eq_at(min(b, t1) - 1e-6)
        out.append(e1 / e0 if e0 > 0 else 0.0)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def equity_summary(points, t0, t1):
    eqs = [e for _, e in points]
    peak, dd = START_EQUITY, 0.0
    for e in eqs:
        peak = max(peak, e)
        dd = max(dd, 1 - e / peak) if peak > 0 else 1.0
    mm = month_mults(points, t0, t1, START_EQUITY)
    end = eqs[-1] if eqs else START_EQUITY
    return {"end_equity": round(end, 2), "worst_drawdown": round(dd, 4), "months": len(mm),
            "months_3x": sum(m >= 3 for m in mm), "best_month": round(max(mm), 3) if mm else None,
            "worst_month": round(min(mm), 3) if mm else None, "ruined": bool(eqs and min(eqs) <= 0)}


def continuous_trades(groups, rates, t0, t1, mult=1.0):
    """Account from START_EQUITY at t0 to t1: groups entered in [t0, t1) compounded with the equity at entry;
    a group is skipped when any leg's notional is below the 5 USD minimum. -> (points, skipped_min_notional)."""
    ev = []
    for i, g in enumerate(groups):
        if t0 <= g[0].t_in < t1:
            ev.append((g[0].t_in, 1, i))
            ev.append((max(t.t_out for t in g), 0, i))
    ev.sort()
    eq, pts, held, skipped = START_EQUITY, [], {}, 0
    for t, kind, i in ev:
        g = groups[i]
        if kind == 1:
            if eq <= 0 or min(tr.size * eq for tr in g) < MIN_NOTIONAL:
                skipped += 1
                continue
            held[i] = eq
        elif i in held:
            eq = max(0.0, eq + held.pop(i) * group_frac(g, rates, mult))
            pts.append((t, eq))
    return pts, skipped


def continuous_daily(series, t0, t1):
    eq, pts = START_EQUITY, []
    for t, r in series:
        if t0 <= t < t1:
            eq = max(0.0, eq * (1 + r))
            pts.append((t, eq))
    return pts


def ceiling_daily(daily, bounds):
    """Perfect foresight, one trade a day at the leverage cap: best asset/direction open to close after 1x costs."""
    days = {}
    for sym, a in daily.items():
        for i, d in enumerate(a.dates):
            if a.o[i] > 0:
                g = abs(a.c[i] / a.o[i] - 1)
                lev = lev_cap(sym)
                days.setdefault(d, []).append(lev * (g - 2 * COST_SIDE[sym]))
    return _ceiling_months([(day_ts(d), max(v)) for d, v in days.items()], bounds)


def ceiling_hourly(hs, bounds):
    days = {}
    for sym, h in hs.items():
        lev = lev_cap(sym)
        by = {}
        for i, u in enumerate(h.uday):
            by.setdefault(u, []).append(i)
        for u, idxs in by.items():
            lo_o, hi_o, best = float("inf"), 0.0, 0.0
            for i in idxs:
                lo_o, hi_o = min(lo_o, h.o[i]), max(hi_o, h.o[i])
                best = max(best, h.c[i] / lo_o - 1, 1 - h.c[i] / hi_o)
            days.setdefault(u, []).append(lev * (best - 2 * COST_SIDE[sym]))
    return _ceiling_months([(u * 86400.0, max(v)) for u, v in days.items()], bounds)


def _ceiling_months(rows, bounds):
    out = {}
    for sp in ("validation", "test"):
        a, b = bounds[sp]
        by = {}
        for t, r in sorted(rows):
            if a <= t < b:
                k = time.strftime("%Y-%m", time.gmtime(t))
                by[k] = by.get(k, 1.0) * max(0.0, 1 + r)
        mm = list(by.values())
        out[sp] = {"months": len(mm), "months_3x": sum(m >= 3 for m in mm),
                   "max_month_multiple": round(max(mm), 2) if mm else None}
    return out


def drift(closes_by_ts, a, b):
    """Buy-and-hold return of an asset over [a, b): [(ts, close)] -> fraction or None."""
    v = [c for t, c in closes_by_ts if a <= t < b]
    return v[-1] / v[0] - 1 if len(v) > 1 else None




# ------------------------------------------------------------------ the study

def _bounds():
    bd = {"train": (utc(2018), utc(2022)), "validation": (utc(2022), utc(2025)), "test": (utc(2025), utc(2026, 11, 25))}
    bh = {"train": (utc(2025, 2, 1), utc(2025, 8, 1)), "validation": (utc(2025, 8, 1), utc(2026, 2, 1)),
          "test": (utc(2026, 2, 1), utc(2026, 11, 25))}
    return bd, bh


def _mean_val_test(series, b):
    out = {}
    for sp in ("validation", "test"):
        v = split_vals(series, *b[sp])
        out[sp] = {"mean_day": mean(v) if v else None, "days": len(v)}
    return out


def _daily_control(rec, series, b):
    """Random-sign control for a daily book: flip each position run (segment) at random."""
    out = {}
    for sp in ("validation", "test"):
        a, z = b[sp]
        segs, tc_total = {}, 0.0
        for sym, rows in rec.items():
            for d, sg, plus, minus, tc, _sgn in rows:
                if a <= day_ts(d) < z:
                    k = (sym, sg)
                    p0, m0 = segs.get(k, (0.0, 0.0))
                    segs[k] = (p0 + plus, m0 + minus)
                    tc_total += tc
        v = split_vals(series, a, z)
        actual = sum(v)
        draw = control_segments(list(segs.values()))
        out[sp] = control_run(actual, lambda rng, draw=draw, tc=tc_total: draw(rng) - tc, len(v))
    return out


def _by_asset_year_daily(rec):
    by_a, by_y = {}, {}
    for sym, rows in rec.items():
        for d, _sg, plus, minus, tc, sgn in rows:
            x = (plus if sgn > 0 else minus if sgn < 0 else 0.0) - tc
            by_a[sym] = by_a.get(sym, 0.0) + x
            by_y[d.year] = by_y.get(d.year, 0.0) + x
    return ({k: round(v, 5) for k, v in sorted(by_a.items())}, {k: round(v, 5) for k, v in sorted(by_y.items())})


def study(chart_fn, fred_fn, run_ts, n_ctrl=2000):
    """Whole fxcom_1 run on injected fetchers. -> (summary, series_by_rule)."""
    from core import factory as fa
    bd, bh = _bounds()
    bar = 0.05 / 8
    rates, rate_gaps = load_rates(fred_fn)
    gaps = {"rates": rate_gaps, "daily_fetch": {}, "hourly_fetch": {}}
    gates = {}
    # ---- data
    daily_g, daily_raw = {}, {}
    for s in sorted(set(DAILY_R1) | set(DAILY_R7)):
        try:
            ch = chart_fn(s, "10y", "1d")
            daily_g[s] = build_daily(s, ch, run_ts, True)
            daily_raw[s] = build_daily(s, ch, run_ts, False)
        except Exception as e:  # noqa: BLE001
            gaps["daily_fetch"][s] = f"{type(e).__name__}: {e}"[:200]
    hs_g, hs_raw, h_start, h_end = {}, {}, utc(2024, 11, 25), utc(2026, 11, 25)
    for s in HOURLY:
        try:
            ch = chart_fn(s, "2y", "1h")
        except Exception as e:  # noqa: BLE001
            gaps["hourly_fetch"][s] = f"{type(e).__name__}: {e}"[:200]
            gates[s] = {"ok": False, "error": "fetch"}
            continue
        ok, info, clean = gate_hourly(ch["bars"])
        clean = [b for b in clean if h_start <= b["t"] < h_end]
        gates[s] = info
        if ok and len(clean) > 600:
            hs_g[s] = adjust_hourly(s, clean, True)
            hs_raw[s] = adjust_hourly(s, clean, False)
    gaps["roll_hourly"] = {s: h.rolls for s, h in hs_g.items()}
    gaps["clipped_daily"] = {s: a.clipped for s, a in daily_g.items()}
    gaps["gbp_rate_zero"] = "GBP has no usable rate series: differential taken as 0 for GBPUSD"
    # ---- ceiling first
    ceil = {"daily": ceiling_daily(daily_g, bd), "hourly": ceiling_hourly(hs_g, bh)}
    zero = all(ceil[k][sp]["months_3x"] == 0 for k in ceil for sp in ("validation", "test"))
    first = ("CEILING: perfect foresight, one trade a day at the leverage caps, after 1x costs, gives ZERO 3x months in "
             "validation and test for this universe" if zero else
             "CEILING: perfect foresight reaches 3x in some months (see ceiling); a real rule must still be judged")
    # ---- daily rules
    results = {}
    rows = {}
    ds = {"R1_tsmom_voltarget": {s: daily_g[s] for s in DAILY_R1 if s in daily_g},
          "R7_fx_carry_volscaled": {s: daily_g[s] for s in DAILY_R7 if s in daily_g}}
    dr = {"R1_tsmom_voltarget": {s: daily_raw[s] for s in DAILY_R1 if s in daily_raw},
          "R7_fx_carry_volscaled": {s: daily_raw[s] for s in DAILY_R7 if s in daily_raw}}
    for rule in DAILY_RULES:
        data = ds[rule]
        if not data:
            results[rule], results[rule + "@2x"] = [], []
            rows[rule] = {"error": "no daily data", "kind": "daily", "low_count": True}
            continue
        base, rec, info = run_daily(data, rates, rule, 1.0, 0)
        s2 = run_daily(data, rates, rule, 2.0, 0)[0]
        sd = run_daily(data, rates, rule, 1.0, 1)[0]
        sr = run_daily(dr[rule], rates, rule, 1.0, 0)[0]
        results[rule], results[rule + "@2x"] = base, s2
        by_a, by_y = _by_asset_year_daily(rec)
        wk = max(1.0, (bd["test"][1] - bd["train"][0]) / 604800)
        row = {"kind": "daily", "info": info, "splits": split_stats(base, bd), "splits_2x": split_stats(s2, bd),
               "delayed": _mean_val_test(sd, bd), "no_clip": _mean_val_test(sr, bd),
               "control": _daily_control(rec, base, bd), "by_asset": by_a, "by_year": by_y,
               "per_week": round(info["changes"] / wk, 2), "low_count": True}
        vv = split_vals(base, *bd["validation"])
        row["validation_trim"] = dict(zip(("without_best_5pct_days", "without_best_day"), trimmed_mean(vv, len(vv))))
        v0, t1 = bd["validation"][0], bd["test"][1]
        row["continuous"] = {"base": equity_summary(continuous_daily(base, v0, t1), v0, t1),
                             "x2": equity_summary(continuous_daily(s2, v0, t1), v0, t1)}
        rows[rule] = row
    # ---- hourly rules
    grid = weekdays(bh["train"][0], bh["test"][1])
    weeks = (bh["test"][1] - bh["train"][0]) / 604800
    for rule in HOURLY_RULES:
        groups, skipped = hourly_trades(hs_g, rule, 0)
        gdel, _ = hourly_trades(hs_g, rule, 1)
        graw, _ = hourly_trades(hs_raw, rule, 0)
        base = series_from_groups(groups, rates, grid, 1.0)
        s2 = series_from_groups(groups, rates, grid, 2.0)
        results[rule], results[rule + "@2x"] = base, s2
        sd = series_from_groups(gdel, rates, grid, 1.0)
        sr = series_from_groups(graw, rates, grid, 1.0)
        inb = [g for g in groups if bh["train"][0] <= max(t.t_out for t in g) < bh["test"][1]]
        row = {"kind": "hourly", "trades": len(inb), "skipped_risk_cap": skipped,
               "per_week": round(len(inb) / weeks, 2), "low_count": len(inb) / weeks < 3,
               "splits": split_stats(base, bh), "splits_2x": split_stats(s2, bh),
               "delayed": _mean_val_test(sd, bh), "no_clip": _mean_val_test(sr, bh)}
        ctrl, trims = {}, {}
        for sp in ("validation", "test"):
            a, z = bh[sp]
            gs = [g for g in groups if a <= max(t.t_out for t in g) < z]
            pairs = [(group_frac(g, rates), group_frac(g, rates, 1.0, True)) for g in gs]
            ndays = len(split_vals(base, a, z))
            ctrl[sp] = control_run(sum(p[0] for p in pairs), control_trades(pairs), ndays, n_ctrl)
            trims[sp] = dict(zip(("without_best_5pct_trades", "without_best_trade"),
                                 trimmed_mean([p[0] for p in pairs], ndays)))
        row["control"], row["validation_trim"], row["test_trim"] = ctrl, trims["validation"], trims["test"]
        by_a, by_y = {}, {}
        for g in inb:
            for t in g:
                x = trade_frac(t, rates)
                by_a[t.asset] = by_a.get(t.asset, 0.0) + x
                y = datetime.fromtimestamp(t.t_out, timezone.utc).year
                by_y[y] = by_y.get(y, 0.0) + x
        row["by_asset"] = {k: round(v, 5) for k, v in sorted(by_a.items())}
        row["by_year"] = {k: round(v, 5) for k, v in sorted(by_y.items())}
        v0, t1 = bh["validation"][0], bh["test"][1]
        p1, k1 = continuous_trades(groups, rates, v0, t1, 1.0)
        p2, k2 = continuous_trades(groups, rates, v0, t1, 2.0)
        row["continuous"] = {"base": {**equity_summary(p1, v0, t1), "skipped_min_notional": k1},
                             "x2": {**equity_summary(p2, v0, t1), "skipped_min_notional": k2}}
        rows[rule] = row
    # ---- judge (two calls, alpha scaled so both use the same bar 0.05/8)
    jd = fa.judge_all({k: v for k, v in results.items() if k.split("@")[0] in DAILY_RULES}, bd, alpha=0.05 * 2 / 8)
    jh = fa.judge_all({k: v for k, v in results.items() if k.split("@")[0] in HOURLY_RULES}, bh, alpha=0.05 * 6 / 8)
    screen, main_route = [], []
    for rule in ALL_RULES:
        j = (jd if rule in DAILY_RULES else jh)["strategies"][rule]
        row = rows[rule]
        row["judge"] = {"validation": j["validation"], "test": j["test"], "passed_judge_all": j["passed"],
                        "validation_3x_check": j["validation_3x_check"]}
        trim = row.get("validation_trim") or {}
        ctrl_ok = (row.get("control", {}).get("validation", {}).get("p", 1.0)) < bar
        trim_ok = bool(trim) and all((x or 0) > 0 for x in trim.values())
        row["beats_control_at_bar"], row["survives_trims"] = ctrl_ok, trim_ok
        row["screen_pass"] = bool(j["passed"] and ctrl_ok and trim_ok)
        row["main_route_pass"] = bool(row["screen_pass"] and not row["low_count"])
        if row["screen_pass"]:
            screen.append(rule)
        if row["main_route_pass"]:
            main_route.append(rule)
    drift_d = {}
    for s, a in daily_g.items():
        pts = [(day_ts(d), a.c[i]) for i, d in enumerate(a.dates)]
        drift_d[s] = {sp: drift(pts, *bd[sp]) for sp in bd}
    drift_h = {}
    for s, h in hs_g.items():
        pts = list(zip(h.ts, h.c))
        drift_h[s] = {sp: drift(pts, *bh[sp]) for sp in bh}
    gaps["rate_missing_calls"] = dict(rates.missing)
    summary = {"first_line": first, "ceiling": ceil, "bonferroni_bar": bar, "n_rules": 8,
               "gates": gates, "gaps": gaps, "rules": rows, "screen_pass": screen, "main_route_pass": main_route,
               "judge_daily_bar": jd["bonferroni_bar"], "judge_hourly_bar": jh["bonferroni_bar"],
               "buy_hold_drift_daily": drift_d, "buy_hold_drift_hourly": drift_h,
               "note": "sharpe252 on trading-day series; judge_all sharpe_ann (sqrt 365) is ignored; hourly validation ~6 months, low power"}
    return summary, {k: v for k, v in results.items() if not k.endswith("@2x")}
