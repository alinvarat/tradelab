"""D3 (short a Binance perp coin BEFORE a delist notice, point-in-time features) and D4 (long spot after a monitoring-tag removal or a survived
delist round). Pure functions, no network. Spec: research/studies/protocol_d3d4_20261126.md (locked before any price of this study was pulled).

Trades are dicts in the core.sweep_engine format (t, te, x, sym, side, gross, cost, fund, net, mfe, mae, reason) so that core.sweep_stats.gate /
evaluate / judge_family apply unchanged. fund is a cost: for a short on a perp it is minus the funding received."""
import bisect
import math
import re
import time

from core import forced_flow as ff

DAY = 86400
HOUR = 3600
SEED = 20261126
COST = 0.006                      # round trip, as forced_flow (fees 0.11% + slippage 0.2% per side)
STOP = 0.25
STOP_SLIP = 0.005
HOLDS_D3 = (3 * DAY, 7 * DAY, 14 * DAY)
SETS = ("s1", "s2", "s3")
JUDGED_SETS = ("s2", "s3")        # s1 (a standing tag short) is a descriptive baseline only
LAST_SIGNAL = ff._t(2026, 10, 15)   # signal days are < this, so a 14-day hold ends inside the window
FIRST_SIGNAL = ff.START
HOLDS_D4 = (3600, 14400, 86400)
DELAYS_D4 = (60, 300)
FAMS_D4 = ("tagrm", "survive")
DEDUPE_D4 = 30 * DAY
SURVIVE_NEAR = 7 * DAY
MIN_TAG_AGE = DAY
START, END, BOUNDS, MONTHS = ff.START, ff.END, ff.BOUNDS, ff.MONTHS
CFG, CFG_STRICT = ff.CFG, ff.CFG_STRICT
SIZE = ff.SIZE
KILL_HAZARD = 0.10
KILL_MIN_COINDAYS = 20
KILL_D4_TRAIN_CLUSTERS = 20
LOW_FRACTION = 1 / 3
FALL_30D = -0.20
HIST_MIN = 25


def split_of(ts):
    return next((k for k, (a, b) in BOUNDS.items() if a <= ts < b), None)


# ---------------------------------------------------------------- rules
def d3_rule(s, hold):
    return f"d3|{s}|h{hold // DAY}d"


def d3_rules():
    return [(d3_rule(s, h), s, h) for s in SETS for h in HOLDS_D3]


def d4_rule(fam, hold, delay):
    return f"d4|{fam}|h{hold // 3600}h|d{delay // 60}m"


def d4_rules():
    return [(d4_rule(f, h, d), f, h, d) for f in FAMS_D4 for h in HOLDS_D4 for d in DELAYS_D4]


# ---------------------------------------------------------------- parsers and names
_PREFIX = re.compile(r"^(1000000|10000|1000)(?=[A-Z])")
_REMOVE = re.compile(r"Remove the Monitoring Tag (?:for|from) (.+?)(?=,?\s*(?:and\s+)?(?:Remove|Extend|Change)\b|\s+on\s+\d{4}-\d{2}-\d{2}|$)")
STABLE = {"USDC", "FDUSD", "BUSD", "TUSD", "USDP", "USDT", "DAI", "EUR", "AEUR", "EURI", "USD1", "USDE", "PAXG", "XAUT"}


def base_of(perp: str):
    """'1000PEPEUSDT' -> 'PEPE'; None when the symbol is not a plain USDT contract."""
    return _PREFIX.sub("", perp[:-4]) if perp.endswith("USDT") and len(perp) > 4 else None


def monitoring_removed(title: str) -> list:
    """Coins named after 'Remove the Monitoring Tag for ...' in a Binance title ('... Include A, B and Remove the Monitoring Tag for CVX & SUN, and
    Remove the Seed Tag for X' -> ['CVX', 'SUN']). Seed-tag removals are not events."""
    out = []
    for m in _REMOVE.finditer((title or "").strip()):
        for s in ff._tokens(m.group(1)):
            if s not in out:
                out.append(s)
    return out


# ---------------------------------------------------------------- tag book
def tag_book(adds, removes, ends):
    """Event lists ({'sym', 'ts'}) -> (adds, removes, ends), each {sym: sorted [ts]}. `ends` are the coin's delist notices (L1f and futures)."""
    def idx(evs):
        d = {}
        for e in evs:
            d.setdefault(e["sym"], []).append(e["ts"])
        return {k: sorted(v) for k, v in d.items()}
    return idx(adds), idx(removes), idx(ends)


def _last_before(lst, t):
    i = bisect.bisect_left(lst, t)
    return lst[i - 1] if i else None


def tagged(book, sym, t, min_age=0):
    """True when the coin carries the monitoring tag at time t: the last add notice is before t - min_age, and no removal or delist notice came
    after that add and before t."""
    adds, rem, end = book
    la = _last_before(adds.get(sym, []), t)
    if la is None or la > t - min_age:
        return False
    lr = _last_before(rem.get(sym, []), t)
    le = _last_before(end.get(sym, []), t)
    return (lr is None or la > lr) and (le is None or la > le)


# ---------------------------------------------------------------- D3 features and signals
def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def sym_features(bars, d):
    """bars {day index: (close, quote volume)}; day d (day index): features from days up to d-1 only. None without enough history."""
    c1, c8, c31 = bars.get(d - 1), bars.get(d - 8), bars.get(d - 31)
    if not (c1 and c8 and c31) or c31[0] <= 0 or c8[0] <= 0:
        return None
    qs = [bars[k][1] for k in range(d - 30, d) if k in bars]
    if len(qs) < HIST_MIN:
        return None
    return {"vol": median(qs), "ret30": c1[0] / c31[0] - 1, "ret7": c1[0] / c8[0] - 1}


def is_fall(f):
    return f["ret30"] <= FALL_30D and f["ret7"] < 0


def lowvol_flags(feats):
    """{sym: features} -> {sym: True when its median volume is in the lowest third of the cross-section of that day}."""
    vols = sorted(f["vol"] for f in feats.values())
    n = len(vols)
    return {s: bisect.bisect_left(vols, f["vol"]) < n * LOW_FRACTION for s, f in feats.items()}


def in_set(s, tag, low, fall):
    return {"s1": tag, "s2": tag and low and fall, "s3": low and fall}[s]


def build_signals(dbars, days, book, nidx):
    """dbars {perp symbol: {day index: (close, qv)}}, days = day indexes, book = tag_book(...), nidx = notice_index of the L1f and futures-delist notices (a coin with a notice before the day is
    not a candidate: the notice has happened). Returns (rows, pool): rows = one dict per coin-day that is in s1
    (tag) or s3 (lowvol & fall): {'d': day start ts, 'sym', 'tag', 'low', 'fall'}; pool {day start ts: [symbols]} = lowvol & not tag & not fall (the matched control)."""
    rows, pool = [], {}
    for d in days:
        dts = d * DAY
        feats = {}
        for sym, bars in dbars.items():
            if (d - 1) not in bars:
                continue
            b = base_of(sym)
            if not b or b in STABLE or _last_before(nidx.get(b, []), dts) is not None:
                continue
            f = sym_features(bars, d)
            if f:
                feats[sym] = f
        if not feats:
            continue
        low = lowvol_flags(feats)
        for sym, f in feats.items():
            tg = tagged(book, base_of(sym), dts)
            fl = is_fall(f)
            if tg or (low[sym] and fl):
                rows.append({"d": dts, "sym": sym, "tag": tg, "low": low[sym], "fall": fl})
            elif low[sym]:
                pool.setdefault(dts, []).append(sym)
    return rows, pool


def notice_index(events):
    """Delist notices ({'sym', 'ts'}) -> {sym: sorted [ts]}."""
    d = {}
    for e in events:
        d.setdefault(e["sym"], []).append(e["ts"])
    return {k: sorted(v) for k, v in d.items()}


def first_notice_after(nidx, sym, t):
    """First delist notice of the coin at or after t, or None."""
    lst = nidx.get(sym, [])
    i = bisect.bisect_left(lst, t)
    return lst[i] if i < len(lst) else None


def hazard_table(rows, nidx, a, b):
    """Stage A (flags and timestamps only, no returns): for each set the coin-days with day start in [a, b), and how many of them have a delist notice of the coin
    inside the entry day (01:00 UTC to the next 01:00) and within 3 / 7 / 14 days of the entry."""
    out = {}
    for s in SETS:
        n = h1 = h3 = h7 = h14 = 0
        for r in rows:
            if not (a <= r["d"] < b) or not in_set(s, r["tag"], r["low"], r["fall"]):
                continue
            e0 = r["d"] + HOUR
            nt = first_notice_after(nidx, base_of(r["sym"]), e0)
            n += 1
            if nt is not None:
                dt = nt - e0
                h1 += dt <= DAY
                h3 += dt <= 3 * DAY
                h7 += dt <= 7 * DAY
                h14 += dt <= 14 * DAY
        out[s] = {"coin_days": n, "hits_day": h1, "hazard_day": round(h1 / n, 5) if n else None,
                  "hazard_3d": round(h3 / n, 5) if n else None, "hazard_7d": round(h7 / n, 5) if n else None, "hazard_14d": round(h14 / n, 5) if n else None}
    return out


def kill1_d3(table):
    """Kill 1: neither judged set has train hazard per coin-day >= 10% on >= 20 train coin-days. Returns (killed, detail)."""
    ok = {s: (table[s]["coin_days"] >= KILL_MIN_COINDAYS and (table[s]["hazard_day"] or 0) >= KILL_HAZARD) for s in JUDGED_SETS}
    return (not any(ok.values())), ok


def notice_calendar(notices):
    """Descriptive timestamps only: weekday (0 = Monday) and UTC hour histograms of unique notice times."""
    wd, hr = [0] * 7, [0] * 24
    for t in sorted({e["ts"] for e in notices}):
        g = time.gmtime(t)
        wd[g.tm_wday] += 1
        hr[g.tm_hour] += 1
    return {"weekday": wd, "hour_utc": hr}


def tag_leads(adds, nidx):
    """Days from each tag add to the coin's next delist notice (None = never in the window): quantiles and shares inside 30 / 90 / 180 days."""
    leads = []
    for e in adds:
        nt = first_notice_after(nidx, e["sym"], e["ts"])
        leads.append(None if nt is None else (nt - e["ts"]) / DAY)
    got = sorted(x for x in leads if x is not None)
    n = len(leads)
    q = (lambda p: round(got[int(p * (len(got) - 1))], 1)) if got else (lambda p: None)
    return {"adds": n, "delisted_later": len(got), "lead_days_p10": q(0.1), "lead_days_p50": q(0.5), "lead_days_p90": q(0.9),
            **{f"share_{d}d": round(sum(1 for x in got if x <= d) / n, 4) if n else None for d in (30, 90, 180)}}


# ---------------------------------------------------------------- D3 simulation (hourly perp bars)
def short_hourly(bars: dict, entry_ts, hold, notice_ts=None, bars1m=None, stop: float = STOP):
    """One short on {hour open ts: (o, h, l, c)}. Entry at the open of the first bar at or after entry_ts (at most 3 bars late). Exit at the first of: the
    open of the 1-minute bar at or after notice_ts + 60 s (the hourly bar open when no 1-minute bars; reason 'notice'), the open of the hourly bar `hold` after
    entry (at most 3 bars late), a 25% stop on an hourly high (fill at the stop plus 0.5%, reason 'stop'). When the bars end before the exit (the contract was
    delisted) the exit is the close of the last bar (reason 'ended'). Returns dict(te, x, gross, mfe, mae, reason) or None (no usable bar)."""
    e = next((t for t in range(int(entry_ts), int(entry_ts) + 3 * HOUR, HOUR) if t in bars), None)
    if e is None or bars[e][0] <= 0:
        return None
    entry = bars[e][0]
    target = e + hold
    reason, exit_t, xp = "time", None, None
    nt = None if notice_ts is None else notice_ts + 60
    if nt is not None and nt <= e:
        return None
    if nt is not None and nt < target:
        reason = "notice"
        m = int(math.ceil(nt / 60) * 60)
        mm = next((t for t in range(m, m + 3 * 60, 60) if bars1m and t in bars1m), None)
        if mm is not None:
            exit_t, xp = mm, bars1m[mm][0]
        else:
            h = int(math.ceil(nt / HOUR) * HOUR)
            hh = next((t for t in range(h, h + 3 * HOUR, HOUR) if t in bars), None)
            if hh is None:
                return None
            exit_t, xp = hh, bars[hh][0]
    else:
        x_t = next((t for t in range(target, target + 3 * HOUR, HOUR) if t in bars), None)
        if x_t is not None:
            exit_t, xp = x_t, bars[x_t][0]
        else:
            last = max(bars)
            if last >= target:
                return None
            reason, exit_t, xp = "ended", last + HOUR, bars[last][3]
    hi = lo = entry
    gross = None
    for t in range(e, int(exit_t), HOUR):
        b = bars.get(t)
        if b is None:
            continue
        hi, lo = max(hi, b[1]), min(lo, b[2])
        if b[1] >= entry * (1 + stop):
            gross, reason, exit_t = -(stop + STOP_SLIP), "stop", t + HOUR
            break
    if gross is None:
        gross = -(xp / entry - 1)
    return {"te": e, "x": exit_t, "gross": gross, "mfe": max((entry - lo) / entry, 0.0), "mae": max((hi - entry) / entry, 0.0), "reason": reason}


def fund_income(rates, t0, t1):
    """Funding received by a short between entry and exit: sum of the settled rates with t0 < ts <= t1 (rates = [(ts, rate)])."""
    return sum(r for ts, r in rates if t0 < ts <= t1)


def make_short(sym, t, sim, income, ctrl_total=None):
    """Sweep-format short on a perp. fund (a cost) = -income. ctrl_total = control gross + control funding income (mean over the drawn coins)."""
    fund = -income
    tr = {"sym": sym, "side": -1, "t": t, "te": sim["te"], "x": sim["x"], "ep": 0.0, "xp": 0.0, "gross": sim["gross"], "cost": COST, "fund": fund,
          "net": sim["gross"] - COST - fund, "mfe": sim["mfe"], "mae": sim["mae"], "reason": sim["reason"]}
    if ctrl_total is not None:
        tr["ctrl_net"] = ctrl_total - COST
    return tr


def make_long(sym, t, sim, ctrl_gross=None):
    """Sweep-format long on spot: no funding or borrow (fund 0)."""
    tr = {"sym": sym, "side": 1, "t": t, "te": sim["te"], "x": sim["x"], "ep": 0.0, "xp": 0.0, "gross": sim["gross"], "cost": COST, "fund": 0.0,
          "net": sim["gross"] - COST, "mfe": sim["mfe"], "mae": sim["mae"], "reason": sim["reason"]}
    if ctrl_gross is not None:
        tr["ctrl_net"] = ctrl_gross - COST
    return tr


def cluster(trades, key):
    """One observation per group: the mean of the numeric fields (ctrl_net over the members that have one); t = first member's t, x = the latest exit."""
    groups = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    out = []
    for k, g in groups.items():
        c = {f: sum(t[f] for t in g) / len(g) for f in ("gross", "cost", "fund", "net", "mfe", "mae")}
        cn = [t["ctrl_net"] for t in g if t.get("ctrl_net") is not None]
        c.update(sym=f"{len(g)} coins", side=g[0]["side"], t=min(t["t"] for t in g), te=min(t["te"] for t in g), x=max(t["x"] for t in g), ep=0.0, xp=0.0,
                 reason="cluster", n_coins=len(g), nid=str(k))
        if cn:
            c["ctrl_net"] = sum(cn) / len(cn)
        out.append(c)
    return sorted(out, key=lambda t: t["t"])


# ---------------------------------------------------------------- D4 events
def dedupe30(events):
    """One event per (family, coin) within 30 days: the first counts."""
    seen, out = {}, []
    for e in sorted(events, key=lambda e: e["ts"]):
        k = (e["fam"], e["sym"])
        if k in seen and e["ts"] - seen[k] < DEDUPE_D4:
            continue
        seen[k] = e["ts"]
        out.append(e)
    return out


def d4_events(adds, removals, l1f, fut):
    """Event lists ({'sym', 'ts', 'title'?}) -> frozen D4 events. tagrm: coins of a removal notice. survive: at each L1f notice time T, coins tagged for >= 1 day at T
    that no L1f / futures-delist notice names within +-7 days of T. Window 2024-01-01 .. 2026-10-29; each event gets nid = family|notice time."""
    ends = list(l1f) + list(fut)
    book = tag_book(adds, removals, ends)
    ev = [{"fam": "tagrm", "sym": r["sym"], "ts": r["ts"], "title": r.get("title", "")} for r in removals]
    near = notice_index(ends)
    coins = sorted({a["sym"] for a in adds})
    for T in sorted({e["ts"] for e in l1f}):
        for c in coins:
            if not tagged(book, c, T, MIN_TAG_AGE):
                continue
            if any(abs(x - T) <= SURVIVE_NEAR for x in near.get(c, [])):
                continue
            ev.append({"fam": "survive", "sym": c, "ts": T, "title": "L1f round"})
    ev = dedupe30([e for e in ev if START <= e["ts"] < END])
    for e in ev:
        e["nid"] = f"{e['fam']}|{int(e['ts'])}"
    return ev


def d4_counts(events):
    """Clusters (unique notices) per family and split, plus the train total used by kill 1 (stage A, no prices)."""
    c = {f: {k: set() for k in BOUNDS} for f in FAMS_D4}
    for e in events:
        sp = split_of(e["ts"])
        if sp:
            c[e["fam"]][sp].add(e["ts"])
    out = {f: {k: len(v) for k, v in d.items()} for f, d in c.items()}
    out["train_total"] = sum(out[f]["train"] for f in FAMS_D4)
    out["killed"] = out["train_total"] < KILL_D4_TRAIN_CLUSTERS
    return out


# ---------------------------------------------------------------- correlation with L1f (bucketed by exit day)
def exit_series(trades, a, b, week=False):
    """Per exit day (or 7-day week) of [a, b): the sum of the trades' net, by their exit time x."""
    step = 7 * DAY if week else DAY
    n = int((b - a) // step)
    out = [0.0] * n
    for t in trades:
        k = int((t["x"] - a) // step)
        if 0 <= k < n:
            out[k] += t["net"]
    return out


def l1f_exit_trades(rows, rid="l1f_ref|h4h|d1m"):
    """Frozen forced-flow rows -> the book component l1f's trades (net = gross - cost - funding assumed for the 4 h hold), with exit time x."""
    out = []
    for r in rows:
        if r.get("fam") != "l1f_ref":
            continue
        v = (r.get("rules") or {}).get(rid)
        if v:
            out.append({"t": r["ts"], "x": v[6], "net": v[0] - ff.COST - ff.FUND[14400]})
    return out


# ---------------------------------------------------------------- statistics helpers
def mean_of(x):
    return sum(x) / len(x) if x else None


def ctrl_mean(trades):
    return mean_of([t["ctrl_net"] for t in trades if t.get("ctrl_net") is not None])
