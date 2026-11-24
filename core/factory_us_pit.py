"""factory_us_pit_1: four pre-registered US large-cap rules on a point-in-time S&P 500 (RESULTS.md,
'factory_us_pit_1 screen'). Pure functions only; the network loading lives in research/studies/run.py.

Every rule produces a trade ledger (fixed notional w at entry, an entry mark and an exit mark); one function turns
any ledger into a daily portfolio series with SPY hedge, costs and borrow, so rules and controls share the same
accounting. The batch is judged together with a Bonferroni bar. Simulated research only, stdlib only."""
import bisect
import calendar
import math
import random
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
ETFS = ("XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC")
BENCH, VIX = "SPY", "^VIX"
SEED = 20261125
BORROW_DAY = 0.005 / 252            # descriptive shorts: 0.5%/yr borrow on large caps
BOUNDS_DAYS = {"train": ("2017-01-01", "2020-01-01"), "validation": ("2020-01-01", "2023-01-01"),
               "test": ("2023-01-01", "2026-11-01")}
COST = {"B1": 0.0005, "B2": 0.0003, "B3": 0.0005, "B4": 0.0005}


# ------------------------------------------------------------------ time
def ny_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, NY).strftime("%Y-%m-%d")


def et_ts(day: str, hh: int, mm: int = 0) -> int:
    """UTC seconds of New York wall-clock hh:mm on day (YYYY-MM-DD), DST aware."""
    y, m, d = (int(x) for x in day.split("-"))
    return int(datetime(y, m, d, hh, mm, tzinfo=NY).timestamp())


def accept_ts(acc: str) -> int:
    """SEC acceptanceDateTime read as New York wall-clock (the 'Z' suffix is ignored, locked convention): if the
    stamp is really UTC this places a filing 4-5 h later than it happened, never earlier."""
    s = acc.replace("Z", "")[:19]
    return et_ts(s[:10], int(s[11:13]), int(s[14:16])) + int(s[17:19])


def add_days(day: str, k: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=k)).isoformat()


def bound_ts(day: str) -> int:
    return calendar.timegm(time_tuple(day))


def time_tuple(day: str):
    y, m, d = (int(x) for x in day.split("-"))
    return (y, m, d, 0, 0, 0)


BOUNDS = {k: (bound_ts(a), bound_ts(b)) for k, (a, b) in BOUNDS_DAYS.items()}


# ------------------------------------------------------------------ parsing (Yahoo chart, SEC submissions)
def parse_chart(res: dict) -> tuple:
    """Yahoo chart 'result[0]' with events=div,split -> (bars, {ny_date: dividend}, {ny_date of split}).
    OHLC are Yahoo's split-adjusted (not dividend-adjusted) quote arrays; bars with a missing price are dropped."""
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, l, c) or min(o, h, l, c) <= 0:
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    ev = res.get("events") or {}
    divs = {}
    for x in (ev.get("dividends") or {}).values():
        if x.get("date") and x.get("amount"):
            d = ny_date(x["date"])
            divs[d] = divs.get(d, 0.0) + float(x["amount"])
    splits = {ny_date(x["date"]) for x in (ev.get("splits") or {}).values() if x.get("date")}
    return bars, divs, splits


def daily_ok(bars: list) -> bool:
    """Lesson 9: reject monthly/weekly bars (median gap between bars above 4 calendar days)."""
    if len(bars) < 30:
        return False
    gaps = sorted(bars[k + 1]["t"] - bars[k]["t"] for k in range(len(bars) - 1))
    return gaps[len(gaps) // 2] <= 4 * 86400


def parse_filing_columns(cols: dict, forms=("8-K", "8-K/A"), since: str = "2016-09-01") -> list:
    """Columnar SEC submissions block (filings.recent, or a whole 'files' page) -> filings of the wanted forms,
    each {'form','date','ts','items','accession'} with ts by the New York wall-clock convention."""
    fl = cols.get("form") or []
    n = len(fl)
    out = []
    for form, acc, fdate, items, accno in zip(fl, cols.get("acceptanceDateTime") or [""] * n,
                                              cols.get("filingDate") or [""] * n, cols.get("items") or [""] * n,
                                              cols.get("accessionNumber") or [""] * n):
        if form not in forms or not acc or (fdate or "") < since:
            continue
        out.append({"form": form, "date": fdate, "ts": accept_ts(acc), "accession": accno,
                    "items": [x.strip() for x in (items or "").split(",") if x.strip()]})
    return out


def sec_filings_all(cik: int, get_json, forms=("8-K", "8-K/A"), since: str = "2016-09-01") -> list:
    """All filings of a CIK from the submissions JSON including the older 'files' pages (skipped when their
    filingTo is before `since`). get_json(url) -> dict; it raises on failure (a failure is never 'no filings')."""
    d = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    f = d.get("filings") or {}
    out = parse_filing_columns(f.get("recent") or {}, forms, since)
    for page in f.get("files") or []:
        if (page.get("filingTo") or "9999") < since or not page.get("name"):
            continue
        p = get_json(f"https://data.sec.gov/submissions/{page['name']}")
        out += parse_filing_columns(p.get("filings", {}).get("recent", p) if "filings" in p else p, forms, since)
    seen, uniq = set(), []
    for x in sorted(out, key=lambda x: x["ts"]):
        k = x["accession"] or (x["form"], x["ts"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def filing_sets(filings: list) -> dict:
    """-> sorted acceptance-ts lists: 'any' (8-K + 8-K/A), 't202' (8-K or 8-K/A with item 2.02, filters),
    'ev202' (8-K with item 2.02, events)."""
    s = {"any": [], "t202": [], "ev202": []}
    for x in filings:
        s["any"].append(x["ts"])
        if "2.02" in x["items"]:
            s["t202"].append(x["ts"])
            if x["form"] == "8-K":
                s["ev202"].append(x["ts"])
    return {k: sorted(v) for k, v in s.items()}


def any_in(sorted_ts: list, a: float, b: float) -> bool:
    """True when some value lies in [a, b)."""
    k = bisect.bisect_left(sorted_ts, a)
    return k < len(sorted_ts) and sorted_ts[k] < b


# ------------------------------------------------------------------ panel
def build_panel(bars_by_sym: dict, divs=None, splits=None, calendar_sym=BENCH) -> dict:
    """Aligns every symbol on the calendar symbol's sessions (New York dates). Arrays hold None where a symbol has
    no bar. open_ts / close_ts are 09:30 / 16:00 ET of each session."""
    days = sorted({ny_date(b["t"]) for b in bars_by_sym[calendar_sym]})
    idx = {d: i for i, d in enumerate(days)}
    n = len(days)
    P = {"days": days, "idx": idx, "n": n, "open_ts": [et_ts(d, 9, 30) for d in days],
         "close_ts": [et_ts(d, 16) for d in days], "o": {}, "h": {}, "l": {}, "c": {}, "v": {}, "div": {}, "split": {}}
    for s, rows in bars_by_sym.items():
        arr = {k: [None] * n for k in "ohlcv"}
        for b in rows:
            i = idx.get(ny_date(b["t"]))
            if i is not None:
                for k in "ohlcv":
                    arr[k][i] = b[k]
        for k in "ohlcv":
            P[k][s] = arr[k]
        P["div"][s] = {idx[d]: a for d, a in ((divs or {}).get(s) or {}).items() if d in idx}
        P["split"][s] = {idx[d] for d in ((splits or {}).get(s) or ()) if d in idx}
    return P


def session_after(P: dict, ts: float) -> int:
    """Index of the first session whose 09:30 ET open is strictly after ts (n if none)."""
    return bisect.bisect_right(P["open_ts"], ts)


def session_on_or_after(P: dict, day: str) -> int:
    return bisect.bisect_left(P["days"], day)


def returns(c: list) -> list:
    return [None] + [c[i] / c[i - 1] - 1 if c[i] and c[i - 1] else None for i in range(1, len(c))]


def rolling_ols(x: list, y: list, win: int = 60) -> list:
    """For each i: OLS of y on x (with intercept) over i-win..i-1 -> (beta, corr, resid_sd) when all win pairs are
    present, else None. Rolling sums, O(1) per step."""
    n = len(y)
    out = [None] * n
    sx = sy = sxx = syy = sxy = 0.0
    cnt = 0
    for i in range(n):
        if i >= 1:                              # add pair i-1
            a, b = x[i - 1], y[i - 1]
            if a is not None and b is not None:
                sx += a; sy += b; sxx += a * a; syy += b * b; sxy += a * b; cnt += 1
        if i - win - 1 >= 0:                    # drop pair i-win-1
            a, b = x[i - win - 1], y[i - win - 1]
            if a is not None and b is not None:
                sx -= a; sy -= b; sxx -= a * a; syy -= b * b; sxy -= a * b; cnt -= 1
        if cnt == win:
            vx, vy, cxy = sxx - sx * sx / win, syy - sy * sy / win, sxy - sx * sy / win
            if vx > 1e-14 and vy > 1e-14:
                beta = cxy / vx
                ssr = max(vy - beta * cxy, 0.0)
                out[i] = (beta, cxy / math.sqrt(vx * vy), math.sqrt(ssr / (win - 2)))
    return out


def members_by_session(P: dict, spells: dict) -> list:
    """members[i] = tickers whose membership spell covers session i (start <= day < end)."""
    out = []
    for d in P["days"]:
        out.append({t for t, sp in spells.items() if any(a <= d and (b is None or d < b) for a, b in sp)})
    return out


def coverage(P: dict, members: list, cik_ok: set) -> dict:
    """Share of member-days with a bar and a CIK, per split."""
    out = {}
    empty = [None] * P["n"]
    for sp in BOUNDS:
        tot = ok = 0
        for i, d in enumerate(P["days"]):
            if not (BOUNDS_DAYS[sp][0] <= d < BOUNDS_DAYS[sp][1]):
                continue
            for m in members[i]:
                tot += 1
                ok += m in cik_ok and P["c"].get(m, empty)[i] is not None
        out[sp] = {"member_days": tot, "usable_share": ok / tot if tot else None,
                   "flag_under_70": bool(tot and ok / tot < 0.7)}
    return out


# ------------------------------------------------------------------ ledger -> daily series
def marks(i0: int, f0: str, i1: int, f1: str) -> list:
    """Ordered price marks from (i0, f0) to (i1, f1); f is 'o' (open) or 'c' (close)."""
    pts = [(i0, f0)]
    i, f = i0, f0
    while (i, f) != (i1, f1):
        if f == "o":
            f = "c"
        elif (i + 1, "o") == (i1, f1):
            i, f = i + 1, "o"
        else:
            i, f = i + 1, "c"
        if i > i1:
            raise ValueError("exit before entry")
        pts.append((i, f))
    return pts


def _increments(P: dict, t: dict, cost: float, borrow_day: float):
    """(session index, P&L) pieces of one trade; see book."""
    s, w, side, beta = t["sym"], t["w"], t["side"], t.get("beta", 0.0)
    pts = marks(t["i0"], t["f0"], t["i1"], t["f1"])
    arr = {"o": P["o"][s], "c": P["c"][s]}
    spy = {"o": P["o"][BENCH], "c": P["c"][BENCH]}
    p0 = arr[pts[0][1]][pts[0][0]]
    h0 = spy[pts[0][1]][pts[0][0]]
    prev, hprev = p0, h0
    yield t["i0"], -w * cost
    for i, f in pts[1:]:
        p = arr[f][i]
        if p is None:
            p = prev
        elif t.get("div") and f == "o" and (i, f) == pts[-1]:
            p = p + P["div"][s].get(i, 0.0)
        h = spy[f][i] if spy[f][i] is not None else hprev
        inc = side * w * (p - prev) / p0
        if beta:
            inc -= side * w * beta * (h - hprev) / h0
        if side < 0 and f == "c":
            inc -= w * borrow_day
        yield i, inc
        prev, hprev = p, h
    yield t["i1"], -w * cost


def book(P: dict, trades: list, cost: float, borrow_day: float = BORROW_DAY) -> list:
    """Daily P&L per session (list of length n) of fixed-notional positions. Trade: {'sym','i0','f0','i1','f1','w',
    'side' (+1/-1), 'beta' (SPY hedge ratio, 0 = none), 'div' (add the dividend to an exit at an open)}.
    Over a hold a position earns side*w*(exit/entry-1) minus beta*w*side*(SPY exit/entry-1), minus w*cost at entry
    and at exit (short_gain semantics for side=-1); a missing bar carries the last price (0 P&L)."""
    pnl = [0.0] * P["n"]
    for t in trades:
        for i, x in _increments(P, t, cost, borrow_day):
            pnl[i] += x
    return pnl


def trade_return(P: dict, t: dict, cost: float, borrow_day: float = BORROW_DAY) -> float:
    """Total return of one trade on its own notional (same accounting as book)."""
    return sum(x for _, x in _increments(P, dict(t, w=1.0), cost, borrow_day))


def to_series(P: dict, pnl: list, first: int = 0) -> list:
    return [(P["close_ts"][i], pnl[i]) for i in range(first, P["n"])]


# ------------------------------------------------------------------ helpers shared by rules
def _ok(P, s, i, *fields):
    return 0 <= i < P["n"] and all(P[f][s][i] is not None for f in fields)


def adv(P, s, a, b):
    """Mean dollar volume over sessions a..b (inclusive); None unless every bar is present."""
    c, v = P["c"][s], P["v"][s]
    if a < 0:
        return None
    xs = []
    for k in range(a, b + 1):
        if c[k] is None or v[k] is None:
            return None
        xs.append(c[k] * v[k])
    return sum(xs) / len(xs)


# ------------------------------------------------------------------ B1 residual reversal, no news
def b1_scores(P: dict, syms: list, etfs=ETFS) -> dict:
    """{sym: {i: (z, beta_spy)}} for every session where the stock has 60 full return pairs with SPY and with at
    least one sector ETF. The ETF is the one with the highest correlation over i-60..i-1."""
    rb = returns(P["c"][BENCH])
    re_ = {e: returns(P["c"][e]) for e in etfs if e in P["c"]}
    out = {}
    for s in syms:
        rs = returns(P["c"][s])
        spy = rolling_ols(rb, rs)
        best = [None] * P["n"]
        for e, rx in re_.items():
            st = rolling_ols(rx, rs)
            for i, v in enumerate(st):
                if v is not None and rs[i] is not None and rx[i] is not None and (best[i] is None or v[1] > best[i][1]):
                    best[i] = (v[1], v[0], v[2], rx[i])
        z = {}
        for i in range(P["n"]):
            if best[i] is None or spy[i] is None or rs[i] is None or best[i][2] <= 0:
                continue
            _corr, beta, sd, rx_i = best[i]
            z[i] = ((rs[i] - beta * rx_i) / sd, spy[i][0])
        out[s] = z
    return out


def vix_gross(P: dict, i: int):
    """1.0 if ^VIX(i) > median of the 252 prior closes, 0.5 otherwise; None without 252 prior closes."""
    v = P["c"].get(VIX)
    if not v or v[i] is None or i < 252:
        return None
    hist = [x for x in v[i - 252:i] if x is not None]
    if len(hist) < 252:
        return None
    hs = sorted(hist)
    med = (hs[125] + hs[126]) / 2
    return 1.0 if v[i] > med else 0.5


def b1_trades(P: dict, scores: dict, members: list, cik_ok: set, any8k: dict, hold: int = 2, side: int = 1,
              rng=None, z_cut: float = 2.5, k_max: int = 10, cap: float = 0.10) -> tuple:
    """Signal at session i (closes through i), entry at i+1 open, exit at the close of i+hold. Long the lowest z
    (z <= -2.5) or, side=-1, short the highest (z >= +2.5). Returns (trades, control trades)."""
    rng = rng or random.Random(SEED)
    trades, ctrl = [], []
    for i in range(2, P["n"] - hold):
        G = vix_gross(P, i)
        if G is None:
            continue
        lo, hi = P["close_ts"][i - 2], P["close_ts"][i]
        elig = []
        for s in members[i]:
            if s not in cik_ok or s not in scores or i not in scores[s]:
                continue
            c = P["c"][s][i]
            if c is None or c < 5:
                continue
            a = adv(P, s, i - 19, i)
            if a is None or a < 20e6 or any_in(any8k.get(s, []), lo, hi):
                continue
            elig.append((scores[s][i][0], s))
        if not elig:
            continue
        elig.sort()
        pick = [x for x in elig if x[0] <= -z_cut][:k_max] if side > 0 else \
            [x for x in sorted(elig, reverse=True) if x[0] >= z_cut][:k_max]
        if not pick:
            continue
        w = min(G / len(pick), cap)
        pool = sorted(s for z, s in elig if abs(z) < 0.5)
        cpick = rng.sample(pool, min(len(pick), len(pool)))
        for lst, names in ((trades, [s for _, s in pick]), (ctrl, cpick)):
            for s in names:
                if not _ok(P, s, i + 1, "o"):
                    continue                     # no bar at entry: stays in cash (not known at the signal)
                lst.append({"sym": s, "i0": i + 1, "f0": "o", "i1": i + hold, "f1": "c", "w": w, "side": side,
                            "beta": scores[s][i][1], "z": scores[s][i][0], "signal_i": i})
    return trades, ctrl


# ------------------------------------------------------------------ B2 overnight tug of war
def _prefix(xs):
    out = [0.0]
    for x in xs:
        out.append(out[-1] + x)
    return out


def b2_features(P: dict, syms: list) -> dict:
    """{sym: {'on','id','miss','split'}} prefix sums over sessions. on[t] = ln(o_t/c_{t-1}) (0 on an ex-dividend
    open), id[t] = ln(c_t/o_t); miss counts sessions without a full bar, split counts split dates."""
    out = {}
    for s in syms:
        o, c = P["o"][s], P["c"][s]
        on, idd, miss, spl = [], [], [], []
        for t in range(P["n"]):
            full = o[t] is not None and c[t] is not None
            miss.append(0 if full else 1)
            spl.append(1 if t in P["split"][s] else 0)
            idd.append(math.log(c[t] / o[t]) if full else 0.0)
            if full and t >= 1 and c[t - 1] is not None and t not in P["div"][s]:
                on.append(math.log(o[t] / c[t - 1]))
            else:
                on.append(0.0)
        out[s] = {"on": _prefix(on), "id": _prefix(idd), "miss": _prefix(miss), "split": _prefix(spl)}
    return out


def b2_trades(P: dict, feats: dict, members: list, cik_ok: set, t202: dict, rng=None, k: int = 25,
              w: float = 0.04) -> tuple:
    """At session i: ON20/ID20 over i-20..i-1; buy the k highest ON20 among eligible names with ID20 below the
    median at i's close, sell at the i+1 open (dividend added back). Returns (trades, control trades)."""
    rng = rng or random.Random(SEED)
    trades, ctrl = [], []
    for i in range(21, P["n"] - 1):
        lo, hi = P["close_ts"][i - 2], P["close_ts"][i]
        elig = []
        for s in members[i]:
            f = feats.get(s)
            if f is None or s not in cik_ok:
                continue
            if f["miss"][i + 2] - f["miss"][i - 21] or f["split"][i + 2] - f["split"][i - 20]:
                continue                         # needs bars i-21..i+1, no split date in i-20..i+1
            if P["c"][s][i - 1] < 10:
                continue
            a = adv(P, s, i - 20, i - 1)
            if a is None or a < 50e6 or any_in(t202.get(s, []), lo, hi):
                continue
            elig.append((f["on"][i] - f["on"][i - 20], f["id"][i] - f["id"][i - 20], s))
        if len(elig) < 2:
            continue
        ids = sorted(x[1] for x in elig)
        m = len(ids)
        med = ids[m // 2] if m % 2 else (ids[m // 2 - 1] + ids[m // 2]) / 2
        low = sorted((x for x in elig if x[1] < med), key=lambda x: (-x[0], x[2]))[:k]
        if not low:
            continue
        cp = rng.sample(sorted(x[2] for x in elig), len(low))
        for lst, names in ((trades, [x[2] for x in low]), (ctrl, cp)):
            for s in names:
                lst.append({"sym": s, "i0": i, "f0": "c", "i1": i + 1, "f1": "o", "w": w, "side": 1, "beta": 1.0,
                            "div": True, "signal_i": i})
    return trades, ctrl


# ------------------------------------------------------------------ B3 earnings premium on the predicted date
def b3_candidates(P: dict, ev202: dict, members: list, cik_ok: set) -> list:
    """[(i, sym, i1)] sorted by (i, sym): on session i the name is predicted to report at session i+5 (P = a past
    2.02's date + 364 days, first session on/after it, from a filing 351-379 days before i) and has no 2.02 in the
    last 60 calendar days. Exit i1 = close of the first session whose open is after the next 2.02, capped at i+10."""
    out = set()
    days = P["days"]
    for s, ts_list in ev202.items():
        if s not in cik_ok or not ts_list or s not in P["c"]:
            continue
        for ts in ts_list:
            fd = ny_date(ts)
            pi = session_on_or_after(P, add_days(fd, 364))
            i = pi - 5
            if i < 0 or pi >= P["n"]:
                continue
            gap = (date.fromisoformat(days[i]) - date.fromisoformat(fd)).days
            if not (351 <= gap <= 379) or ts >= P["close_ts"][i]:
                continue
            if s not in members[i] or P["c"][s][i] is None:
                continue
            if any_in(ts_list, et_ts(add_days(days[i], -60), 0), P["close_ts"][i]):
                continue
            k = bisect.bisect_left(ts_list, P["close_ts"][i])
            i1 = i + 10
            if k < len(ts_list):
                i1 = min(i1, session_after(P, ts_list[k]))
            if i1 >= P["n"]:
                continue
            out.add((i, s, i1))
    return sorted(out)


def window_ret(P: dict, s: str, i0: int, i1: int) -> float | None:
    """SPY-adjusted close-to-close return from i0 to i1."""
    a, b, x, y = P["c"][s][i0], P["c"][s][i1], P["c"][BENCH][i0], P["c"][BENCH][i1]
    if None in (a, b, x, y):
        return None
    return (b / a - 1) - (y / x - 1)


def b3_trades(P: dict, cands: list, ev202: dict, members: list, rng=None, filter_top_half: bool = False,
              cap_n: int = 20, w: float = 0.05) -> tuple:
    """Capacity-limited entries at the candidate's close, ticker order on the same day. With filter_top_half, only
    the top half (ceil) of the day's candidates by mean SPY-adjusted return over their last 4 completed windows
    (names without 4 are out). Returns (trades, control trades)."""
    rng = rng or random.Random(SEED)
    hist = {}
    by_day = {}
    for i, s, i1 in cands:
        by_day.setdefault(i, []).append((s, i1))
    trades, ctrl, open_ = [], [], []
    for i in sorted(by_day):
        todays = by_day[i]
        if filter_top_half:
            scored = []
            for s, i1 in todays:
                past = [r for (j1, r) in hist.get(s, []) if j1 < i][-4:]
                if len(past) == 4:
                    scored.append((-mean(past), s, i1))
            scored.sort()
            pick = [(s, i1) for _, s, i1 in scored[:math.ceil(len(scored) / 2)]] if scored else []
            pick.sort()
        else:
            pick = todays
        for s, i1 in todays:
            r = window_ret(P, s, i, i1)
            if r is not None:
                hist.setdefault(s, []).append((i1, r))
        open_ = [x for x in open_ if x > i]
        for s, i1 in pick:
            if len(open_) >= cap_n:
                break
            open_.append(i1)
            trades.append({"sym": s, "i0": i, "f0": "c", "i1": i1, "f1": "c", "w": w, "side": 1, "beta": 1.0,
                           "signal_i": i})
    for t in trades:
        c = b3_control_entry(P, t["sym"], t["i0"], t["i1"] - t["i0"], ev202.get(t["sym"], []), members, rng)
        if c is not None:
            ctrl.append(dict(t, i0=c, i1=c + t["i1"] - t["i0"], signal_i=c))
    return trades, ctrl


def b3_control_entry(P, s, i, L, ts_list, members, rng):
    """Random session j within 252 sessions of i: member with bars at j and j+L, last 2.02 30-60 sessions before j,
    and no 2.02 accepted from j's close to the close of j+L+1."""
    sess = [session_on_or_after(P, ny_date(t)) for t in ts_list]
    ok = []
    for j in range(max(0, i - 252), min(P["n"] - L - 2, i + 252) + 1):
        if s not in members[j] or P["c"][s][j] is None or P["c"][s][j + L] is None:
            continue
        k = bisect.bisect_left(ts_list, P["close_ts"][j]) - 1
        if k < 0 or not (30 <= j - sess[k] <= 60):
            continue
        if any_in(ts_list, P["close_ts"][j], P["close_ts"][j + L + 1]):
            continue
        ok.append(j)
    return rng.choice(ok) if ok else None


# ------------------------------------------------------------------ B4 earnings reaction drift
def ear(P: dict, s: str, i: int):
    if i < 1:
        return None
    a, b, x, y = P["c"][s][i - 1], P["c"][s][i], P["c"][BENCH][i - 1], P["c"][BENCH][i]
    if None in (a, b, x, y):
        return None
    return (b / a - 1) - (y / x - 1)


def b4_events(P: dict, ev202: dict, members: list, cik_ok: set, side: int = 1) -> list:
    """[(D, sym, EAR)] for 2.02 8-Ks: D = first session whose open is after acceptance. Long: EAR >= +5%, range
    position >= 0.6; short (side=-1): EAR <= -5%, range position <= 0.4; both need volume_D >= 3x mean(D-20..D-1)."""
    out = set()
    for s, ts_list in ev202.items():
        if s not in cik_ok or s not in P["c"]:
            continue
        for ts in ts_list:
            D = session_after(P, ts)
            if D < 21 or D >= P["n"] - 1 or s not in members[D] or not _ok(P, s, D, "h", "l", "c", "v"):
                continue
            e = ear(P, s, D)
            vs = P["v"][s][D - 20:D]
            if e is None or any(v is None for v in vs) or mean(vs) <= 0:
                continue
            h, l, c = P["h"][s][D], P["l"][s][D], P["c"][s][D]
            if h <= l or P["v"][s][D] < 3 * mean(vs):
                continue
            pos = (c - l) / (h - l)
            if (side > 0 and e >= 0.05 and pos >= 0.6) or (side < 0 and e <= -0.05 and pos <= 0.4):
                out.add((D, s, e))
    return sorted(out)


def stop_exit(P: dict, s: str, e: int, hold_to: int, side: int, stop: float = 0.06):
    """Exit index: the first close from e on that is >= stop against the position (entry = open of e), else hold_to."""
    p0 = P["o"][s][e]
    for k in range(e, hold_to + 1):
        c = P["c"][s][k]
        if c is not None and side * (c / p0 - 1) <= -stop:
            return k
    return hold_to


def b4_trades(P: dict, events: list, members: list, cik_ok: set, hold: int = 5, side: int = 1, rng=None,
              cap_n: int = 10, w: float = 0.10) -> tuple:
    """Entry at the D+1 open, exit at the D+hold close or the 6% stop; at most cap_n open, same-day events by
    |EAR| descending. Control: a random member on the same D with |EAR| < 1%."""
    rng = rng or random.Random(SEED)
    by_day = {}
    for D, s, e in events:
        if D + hold < P["n"] and _ok(P, s, D + 1, "o"):
            by_day.setdefault(D, []).append((-abs(e), s))
    trades, ctrl, open_ = [], [], []
    for D in sorted(by_day):
        e0 = D + 1
        open_ = [x for x in open_ if x >= e0]
        taken = []
        for _, s in sorted(by_day[D]):
            if len(open_) >= cap_n:
                break
            i1 = stop_exit(P, s, e0, D + hold, side)
            open_.append(i1)
            taken.append(s)
            trades.append({"sym": s, "i0": e0, "f0": "o", "i1": i1, "f1": "c", "w": w, "side": side, "beta": 1.0,
                           "signal_i": D})
        if taken:
            pool = []
            for m in sorted(members[D]):
                if m in cik_ok and m not in taken and m in P["c"] and _ok(P, m, e0, "o"):
                    x = ear(P, m, D)
                    if x is not None and abs(x) < 0.01:
                        pool.append(m)
            for m in rng.sample(pool, min(len(taken), len(pool))):
                ctrl.append({"sym": m, "i0": e0, "f0": "o", "i1": stop_exit(P, m, e0, D + hold, side), "f1": "c",
                             "w": w, "side": side, "beta": 1.0, "signal_i": D})
    return trades, ctrl


# ------------------------------------------------------------------ judging
def block_p(v: list, block: int = 20, n_boot: int = 2000, seed: int = 11) -> float:
    """One-sided p of mean <= 0 by a moving-block bootstrap (centred under the null)."""
    if len(v) < 2 * block:
        return 1.0
    rng = random.Random(seed)
    m0 = sum(v) / len(v)
    c = [x - m0 for x in v]
    nb = math.ceil(len(v) / block)
    hits = 0
    for _ in range(n_boot):
        s = []
        for _ in range(nb):
            a = rng.randrange(0, len(c) - block + 1)
            s.extend(c[a:a + block])
        if sum(s[:len(v)]) / len(v) >= m0:
            hits += 1
    return (hits + 1) / (n_boot + 1)


def month_multiples(series: list, lev: float) -> list:
    """Equity multiple per calendar month at constant leverage (daily rebalanced); a day below -100% ruins."""
    import time as _t
    by = {}
    for t, r in series:
        by.setdefault(_t.strftime("%Y-%m", _t.gmtime(t)), []).append(r)
    out = []
    for _m, rs in sorted(by.items()):
        eq = 1.0
        for r in rs:
            eq *= max(0.0, 1 + lev * r)
        out.append(eq)
    return out


def equity_stats(v: list) -> dict:
    eq, pk, dd = 1.0, 1.0, 0.0
    for r in v:
        eq *= max(0.0, 1 + r)
        pk = max(pk, eq)
        dd = min(dd, eq / pk - 1 if pk else -1.0)
    return {"end_equity": eq, "worst_drawdown": dd}


def _in(series, a, b):
    return [r for t, r in series if a <= t < b]


def judge_all(rules: dict, coverage_by_split: dict | None = None, alpha: float = 0.05, primary: bool = True) -> dict:
    """rules: {name: {'series', 'series2x', 'control' (series), 'entries' (list of entry ts)}}.
    Pass (primary only): validation mean > 0 with block p < alpha / n_rules, validation > 0 at 2x cost, test > 0,
    >= 3 entries a week in validation, validation and test coverage >= 70%."""
    bar = alpha / max(1, len(rules))
    cov = coverage_by_split or {}
    out = {"n_rules": len(rules), "bonferroni_bar": bar if primary else None, "rules": {}}
    for n, R in rules.items():
        row = {}
        for sp, (a, b) in BOUNDS.items():
            v, v2, vc = _in(R["series"], a, b), _in(R.get("series2x", []), a, b), _in(R.get("control", []), a, b)
            ent = [t for t in R.get("entries", []) if a <= t < b]
            diff = [x - y for x, y in zip(v, vc)] if len(vc) == len(v) else []
            row[sp] = {"days": len(v), "mean_day": mean(v) if v else None,
                       "sharpe_ann": (mean(v) / pstdev(v) * math.sqrt(252)) if len(v) > 1 and pstdev(v) > 0 else None,
                       "mean_day_2x": mean(v2) if v2 else None, **equity_stats(v),
                       "end_equity_2x": equity_stats(v2)["end_equity"] if v2 else None,
                       "entries": len(ent), "entries_per_week": len(ent) / (len(v) / 5) if v else 0.0,
                       "control_mean_day": mean(vc) if vc else None,
                       "diff_mean_day": mean(diff) if diff else None,
                       "diff_p_block": block_p(diff) if diff else None,
                       "p_block": block_p(v) if v else None}
        v, t2 = row["validation"], row["test"]
        cov_ok = all(not (cov.get(sp) or {}).get("flag_under_70") for sp in ("validation", "test"))
        if primary:
            row["passed"] = bool(v["mean_day"] and v["mean_day"] > 0 and v["p_block"] < bar
                                 and (v["mean_day_2x"] or 0) > 0 and (t2["mean_day"] or 0) > 0
                                 and v["entries_per_week"] >= 3 and cov_ok)
        best = None
        val = [(t, r) for t, r in R["series"] if BOUNDS["validation"][0] <= t < BOUNDS["validation"][1]]
        for lev in (1, 2, 3, 5, 8, 12):
            mm = month_multiples(val, lev)
            if mm:
                cand = {"lev": lev, "months_3x": sum(m >= 3 for m in mm), "months": len(mm),
                        "worst_month": min(mm), "median_month": sorted(mm)[len(mm) // 2]}
                if best is None or (cand["months_3x"], cand["median_month"]) > (best["months_3x"], best["median_month"]):
                    best = cand
        row["validation_3x_check"] = best
        out["rules"][n] = row
    if primary:
        out["passed"] = [n for n in rules if out["rules"][n]["passed"]]
    return out
