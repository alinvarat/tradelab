"""calendar_flow_1: fetch, per-item rows and merge for the sharded runner (protocol_calendar_flow_1_20261125.md).

Work items (the "symbols" of the sharded interface, one prefix each):
  P:<SYM>  USDT perp, 1h bars: R2 new-perp first-week short and R3 weekend-fade candidates
  D:<SYM>  spot USDT coin, daily bars: R4 panel (the BTCUSDT item also carries BTC perp funding)
  S:<PAIR> stablecoin pair, 1m bars: R1
  X:<ASSET> BTC / ETH: R5 pin fade and R6 unpin drift (Deribit history + Binance 1m)
Runs on GitHub Actions only (AGENTS.md rule 3). Pure calculations are in core/calendar_flow.py.
"""
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from core import calendar_flow as cf
from core import factory as fa
from research.studies import binance_vision as bv

SKIP_BASES = ("USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "EUR", "TRY", "BRL", "AEUR", "USDE", "PAXG", "WBTC", "WBETH")
STABLE_PAIRS = ("USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "USDPUSDT", "BUSDUSDT")
DEPEG = (("USDCUSDT", cf.utc(2023, 3, 10), cf.utc(2023, 3, 15)), ("TUSDUSDT", cf.utc(2023, 6), cf.utc(2023, 7)),
         ("FDUSDUSDT", cf.utc(2025, 4), cf.utc(2025, 5)))
END = cf.utc(2026, 11)
R3_START = cf.utc(2020, 11, 15)


def log(*a):
    import sys
    print(*a, file=sys.stderr, flush=True)


def symbols_calendar_flow_1():
    perps = [s for s in bv.list_symbols("futures/um", "USDT") if re.fullmatch(r"[A-Z0-9]+USDT", s)]
    spot = [s for s in bv.list_symbols("spot", "USDT")
            if s[:-4] not in SKIP_BASES and not re.search(r"(UP|DOWN|BULL|BEAR)$", s[:-4])]
    if "BTCUSDT" not in spot:
        spot.append("BTCUSDT")
    return (["P:" + s for s in perps] + ["D:" + s for s in spot] + ["S:" + s for s in STABLE_PAIRS]
            + ["X:BTC", "X:ETH"])


def _prev_month(now):
    t = time.gmtime(now)
    return (t.tm_year, t.tm_mon - 1) if t.tm_mon > 1 else (t.tm_year - 1, 12)


def hbars(sym, start_s, end_s, gaps, now=None, market="futures/um", interval="1h"):
    """{t: (t,o,h,l,c,qv)} from monthly files; a month with no monthly file yet (the current and previous one) is read
    from the daily files. A failed download is counted in gaps, never read as no data."""
    now = time.time() if now is None else now
    out = {}
    for (y, m) in bv.months(start_s, end_s):
        rows = bv.fetch(market, "monthly", "klines", sym, (y, m), interval, bv.parse_kline)
        if rows is None:
            gaps["month_failed"] += 1
            continue
        if not rows and (y, m) >= _prev_month(now):
            rows = []
            for d in bv.days(max(start_s, cf.utc(y, m)), min(end_s, now, cf.utc(y + (m == 12), m % 12 + 1))):
                got = bv.fetch(market, "daily", "klines", sym, d, interval, bv.parse_kline)
                if got is None:
                    gaps["day_failed"] += 1
                else:
                    rows += got
        for r in rows:
            out[r[0]] = (r[0], r[1], r[2], r[3], r[4], r[7])
    return out


def _funding(sym, start_s, end_s, gaps):
    rows, failed = bv.funding(sym, start_s, end_s)
    if failed:
        gaps["funding_failed"] += len(failed)
        return None
    return cf.Funding(rows) if rows else None


class Ctx:
    """BTCUSDT 1h bars and funding shared by the P items of one shard."""

    def __init__(self, gaps):
        self.btc = hbars("BTCUSDT", cf.utc(2020), END + 10 * 86400, gaps)
        self.fund = _funding("BTCUSDT", cf.utc(2020), END + 10 * 86400, gaps)


def p_item(sym, ctx):
    gaps, rows = Counter(), []
    months = bv.list_files("futures/um", "monthly", "klines", sym, "1h")
    if months:
        y, m = int(months[0][:4]), int(months[0][5:7])
        start0 = cf.utc(y, m)
        ly, lm = int(months[-1][:4]), int(months[-1][5:7])
        last_s = cf.utc(ly + (lm == 12), lm % 12 + 1)
    else:
        days = bv.list_files("futures/um", "daily", "klines", sym, "1h")
        if not days:
            gaps["no_files"] += 1
            return rows, gaps
        start0 = cf.utc(int(days[0][:4]), int(days[0][5:7]), int(days[0][8:10]))
        last_s = END + 10 * 86400
    bars = hbars(sym, start0, min(start0 + 45 * 86400, END + 10 * 86400), gaps)
    fund = _funding(sym, start0, END + 10 * 86400, gaps)
    if bars and fund is None:
        gaps["no_funding_series"] += 1
    if bars:
        h1 = [bars[t] for t in sorted(bars)]
        if not cf.first_bar_is_listing(h1[0][0]):
            gaps["listed_before_2020"] += 1
        elif cf.utc(2020) <= h1[0][0] < cf.utc(2026, 11):
            row, skipped = cf.newperp_row(sym, h1, ctx.btc, fund, ctx.fund)
            gaps["r2_variants_skipped"] += skipped
            if row:
                cur = _prev_month(time.time())
                row["delisted"] = (cur[0] * 12 + cur[1]) - (int(months[-1][:4]) * 12 + int(months[-1][5:7])) > 1 if months else False
                row["k1000"] = bool(re.match(r"^1000", sym))
                rows.append(row)
    if last_s > cf.utc(2020, 12):
        full = hbars(sym, max(start0, R3_START), min(END + 10 * 86400, last_s + 10 * 86400), gaps)
        full.update(bars)
        h1 = [full[t] for t in sorted(full)]
        r3, g3 = cf.weekend_rows(sym, h1, ctx.btc, fund, ctx.fund, cf.utc(2021), END)
        rows += r3
        for k, v in g3.items():
            gaps["r3_" + k] += v
    return rows, gaps


def d_item(sym):
    gaps = Counter()
    got, failed = bv.klines(sym, cf.utc(2020, 11), END, "1d")
    gaps["daily_failed"] += len(failed)
    if len(got) < 31 and sym != "BTCUSDT":
        return [], gaps
    row = {"kind": "daily_bars", "symbol": sym, "market": sym, "ts": cf.utc(2021), "t": [r[0] for r in got],
           "c": [r[4] for r in got], "q": [r[7] for r in got]}
    if sym == "BTCUSDT":
        f, failed = bv.funding("BTCUSDT", cf.utc(2020, 11), END + 2 * 86400)
        gaps["btc_funding_failed"] += len(failed)
        row["funding"] = f
    return [row], gaps


def s_item(sym):
    gaps, rows = Counter(), []
    months = bv.months(cf.utc(2021), END)
    cool, nxt = 0.0, None

    def month(k):
        if k >= len(months):
            return []
        got = bv.fetch("spot", "monthly", "klines", sym, months[k], "1m", bv.parse_kline)
        if got is None:
            gaps["month_failed"] += 1
            return []
        return [(r[0], r[1], r[2], r[3], r[4]) for r in got]

    cur = month(0)
    for k, (y, m) in enumerate(months):
        nxt = month(k + 1)
        t_end = cf.utc(y + (m == 12), m % 12 + 1)
        if cur:
            r, g, cool = cf.stable_rows(sym, cur + nxt[:70], cool0=cool, t_end=t_end)
            rows += r
            gaps["entry_bar_missing"] += g
        cur = nxt
    return rows, gaps


def deribit_days(asset, gaps):
    """{day_start: {"strikes": [...]}} of every 08:00 UTC option expiry in the Deribit history, or None on failure."""
    from urllib.request import Request, urlopen
    url = f"https://history.deribit.com/api/v2/public/get_instruments?currency={asset}&kind=option&expired=true"
    try:
        with urlopen(Request(url, headers=bv.UA), timeout=180) as r:
            res = json.load(r).get("result") or []
    except Exception as e:  # noqa: BLE001
        gaps["deribit_failed"] += 1
        log("deribit", asset, e)
        return None
    out = {}
    for ins in res:
        ts = ins.get("expiration_timestamp", 0) / 1000
        if ts % 86400 != 8 * 3600 or ins.get("strike") is None:
            continue
        out.setdefault(int(ts - 8 * 3600), set()).add(float(ins["strike"]))
    if not out:
        gaps["deribit_empty"] += 1
        return None
    gaps["deribit_instruments"] += len(res)
    return {d: {"strikes": sorted(s)} for d, s in out.items()}


def x_item(asset):
    gaps, rows = Counter(), []
    sym, step = asset + "USDT", 1000 if asset == "BTC" else 50
    fridays = cf.last_friday_days(2020, (2026, 10))
    fri_set = set(fridays)
    spot00, perp = {}, {}
    for (y, m) in bv.months(cf.utc(2020), END):
        s = bv.fetch("spot", "monthly", "klines", sym, (y, m), "1m", bv.parse_kline)
        p = bv.fetch("futures/um", "monthly", "klines", sym, (y, m), "1m", bv.parse_kline)
        if s is None:
            gaps["spot_month_failed"] += 1
        else:
            for r in s:
                if r[0] % 86400 == 0:
                    spot00[r[0]] = r[1]
        if p is None:
            gaps["perp_month_failed"] += 1
        else:
            for r in p:
                if r[0] % 86400 <= 8 * 3600 or (r[0] - r[0] % 86400) in fri_set:
                    perp[r[0]] = (r[0], r[1], r[2], r[3], r[4])
    f, failed = bv.funding(sym, cf.utc(2020), END + 2 * 86400)
    gaps["funding_failed"] += len(failed)
    fund = cf.Funding(f) if f else None
    info = deribit_days(asset, gaps)
    lo, hi = cf.utc(2021), END
    if info is None:
        day_info = {d: {"strikes": None} for d in range(int(lo), int(hi), 86400)}
    else:
        day_info = {d: v for d, v in info.items() if lo <= d < hi}
        gaps["api_expiry_days"] += len(day_info)
        gaps["range_days"] += int((hi - lo) // 86400)
    r5, c5 = cf.pin_rows(sym, day_info, spot00, perp, fund, step)
    r6, c6 = cf.unpin_rows(sym, fridays, perp, fund)
    for k, v in c5.items():
        gaps["r5_" + k] += v
    for k, v in c6.items():
        gaps["r6_" + k] += v
    return r5 + r6, gaps


def rows_calendar_flow_1(items, workers=8):
    gaps, rows = Counter(), []
    ctx = Ctx(gaps) if any(i.startswith("P:") for i in items) else None

    def one(item):
        kind, name = item.split(":", 1)
        try:
            if kind == "P":
                return item, p_item(name, ctx)
            if kind == "D":
                return item, d_item(name)
            if kind == "S":
                return item, s_item(name)
            if kind == "X":
                return item, x_item(name)
            raise ValueError("unknown item " + item)
        except Exception as e:  # noqa: BLE001
            return item, ([], Counter({"failed_item": 1, "failed_item_names": str(item) + ": " + str(e)[:120]}))
    names = []
    with ThreadPoolExecutor(workers) as ex:
        for item, (r, g) in ex.map(one, items):
            rows += r
            for k, v in g.items():
                if k == "failed_item_names":
                    names.append(v)
                else:
                    gaps[k] += v
    out = dict(gaps)
    if names:
        out["failed_item_names"] = "; ".join(names)[:2000]
    return {"rows": rows, "gaps": out}


# ---------------------------------------------------------------------------------------------- merge
def _yahoo_cme_gap(rows, gaps):
    """R3b, descriptive: true CME BTC=F weekend gap vs the Binance gap of the same week."""
    from urllib.request import Request, urlopen
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/BTC=F?interval=1d&period1=1513000000&period2=%d"
           % int(time.time()))
    try:
        with urlopen(Request(url, headers=bv.UA), timeout=60) as r:
            res = json.load(r)["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        bars = [(t, q["open"][i], q["high"][i], q["low"][i], q["close"][i]) for i, t in enumerate(res["timestamp"])
                if None not in (q["open"][i], q["high"][i], q["low"][i], q["close"][i])]
    except Exception as e:  # noqa: BLE001
        gaps["yahoo_btcf_failed"] = str(e)[:100]
        return {"error": "yahoo failed"}
    binance = {time.strftime("%Y-%m-%d", time.gmtime(r["F"])): r["gap"] for r in rows
               if r.get("kind") == "wk_cand" and r["symbol"] == "BTCUSDT"}
    cme, signs, fills, n_roll = [], [], 0, 0
    for i in range(len(bars) - 2):
        if time.gmtime(bars[i][0]).tm_wday != 4 or time.gmtime(bars[i + 1][0]).tm_wday != 0:
            continue
        d = time.gmtime(bars[i][0])
        if cf.last_friday(d.tm_year, d.tm_mon).day == d.tm_mday:
            n_roll += 1
            continue
        fri_close, mon_open = bars[i][4], bars[i + 1][1]
        gap = mon_open / fri_close - 1
        key = time.strftime("%Y-%m-%d", time.gmtime(bars[i][0]))
        bg = binance.get(key)
        touched = any(b[3] <= fri_close <= b[2] for b in bars[i + 1:i + 3])
        cme.append((gap, bg, touched))
    pairs = [(g, b) for g, b, _t in cme if b is not None]
    out = {"weeks": len(cme), "skipped_roll_weeks": n_roll, "weeks_with_binance_gap": len(pairs),
           "fill_rate_monday_tuesday": (sum(1 for _g, _b, t in cme if t) / len(cme)) if cme else None}
    if len(pairs) > 5:
        out["sign_agreement"] = sum(1 for g, b in pairs if (g > 0) == (b > 0)) / len(pairs)
        mg, mb = sum(g for g, _b in pairs) / len(pairs), sum(b for _g, b in pairs) / len(pairs)
        cov = sum((g - mg) * (b - mb) for g, b in pairs)
        vg = sum((g - mg) ** 2 for g, _b in pairs) ** 0.5
        vb = sum((b - mb) ** 2 for _g, b in pairs) ** 0.5
        out["correlation"] = cov / (vg * vb) if vg and vb else None
    return out


def summarize_calendar_flow_1(all_rows):
    from statistics import mean
    out = {"line": "calendar_flow_1", "bonferroni_bar": cf.BAR, "k_variants": cf.K_VARIANTS, "n_rows": len(all_rows)}
    by = {}
    for r in all_rows:
        by.setdefault(r.get("kind"), []).append(r)
    gaps = {}

    def guard(name, fn):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            out[name] = {"verdict": "error", "error": f"{type(e).__name__}: {e}"[:300]}

    def r1():
        rows = by.get("stable_revert", [])
        rep = {"max_loss_per_trade_of_equity_fee0": round(cf.SIZE * (0.003 + 0.0002), 5)}
        rep["fee0_decides"] = cf.rule_report(rows, ["f0"])
        for h in ("f2", "f10"):
            rep[h] = cf.rule_report(rows, [h])
        dep = [r for r in rows if not any(r["symbol"] == s and a <= r["ts"] < b for s, a, b in DEPEG)]
        rep["fee0_without_depeg_windows"] = cf.rule_report(dep, ["f0"])
        rep["per_pair_f0"] = cf.breakdown(rows, cf.BOUNDS, "f0", lambda r: r["symbol"])
        rep["exit_reasons_f0"] = cf.breakdown(rows, cf.BOUNDS, "f0", lambda r: r["exit_reason"])
        scope = [r for r in rows if r["ts"] >= cf.BOUNDS["train"][0] and r["ts"] < cf.BOUNDS["test"][1]]
        weeks = (cf.BOUNDS["test"][1] - cf.BOUNDS["train"][0]) / cf.WEEK
        tot = sum(r["ret"]["f0"]["net"] for r in scope)
        rep["pnl_per_week_usd_147_book_fee0"] = {f"{lev}x": round(tot * cf.SIZE * 147 * lev / weeks, 4) for lev in (1, 3, 5, 10)}
        rep["trades_per_week"] = round(len(scope) / weeks, 3)
        return rep

    def r2():
        rows = by.get("newperp_short", [])
        rep = cf.rule_report(rows, list(cf.NEWPERP_VARIANTS), cf.BOUNDS_R2)
        rep["stop_loss_of_equity"] = round(cf.SIZE * cf.NEWPERP_STOP, 4)
        pick = rep.get("pick")
        if pick:
            rep["by_delisted"] = cf.breakdown(rows, cf.BOUNDS_R2, pick, lambda r: "delisted" if r.get("delisted") else "alive")
            rep["by_1000_prefix"] = cf.breakdown(rows, cf.BOUNDS_R2, pick, lambda r: "1000" if r.get("k1000") else "plain")
        rep["flag"] = "frequency flagged: below 3 a week it is diagnostic only"
        return rep

    def r3():
        events, n_weeks, low = cf.weekly_members(by.get("wk_cand", []))
        rep = cf.rule_report(events, ["gapfade"])
        rep.update(weeks_ranked=n_weeks, weeks_with_event=len({e["S"] for e in events}), lowest_member_qv30=low,
                   floor=cf.QV_FLOOR, floor_binds=bool(low is not None and low < cf.QV_FLOOR * 1.0001))
        wk = {}
        for e in events:
            wk.setdefault(e["S"], []).append(e["ret"]["gapfade"]["net"])
        rep["per_week_mean_of_means"] = mean(mean(v) for v in wk.values()) if wk else None
        rep["worst_trade_of_equity_note"] = "stop is 1.0 x |gap|, so the loss per trade is about |gap| (see worst_trade_all_splits)"
        rep["R3b_cme_gap_check"] = _yahoo_cme_gap(by.get("wk_cand", []), gaps)
        return rep

    def r4():
        bars, fund_rows = {}, []
        for r in by.get("daily_bars", []):
            bars[r["symbol"]] = [(t, c, c, c, c, q) for t, c, q in zip(r["t"], r["c"], r["q"])]
            if r.get("funding"):
                fund_rows = r["funding"]
        if "BTCUSDT" not in bars:
            return {"verdict": "no BTCUSDT bars"}
        days, close, qv = fa.panel(bars)
        fund_day = cf.funding_by_day(cf.Funding([tuple(x) for x in fund_rows]), days) if fund_rows else {}
        s1, miss = cf.dow_legs(days, close, qv, fund_day)
        s2, _m = cf.dow_legs(days, close, qv, fund_day, cost_mult=2.0)
        legs = cf.dow_report(s1, s2)
        return {"coins": len(bars), "days": len(days), "days_without_funding": miss, "legs": legs,
                "passed": sorted(k for k, v in legs.items() if v["passed"]),
                "weekend_vs_weekday_btc_gross": cf.weekend_contrast(days, close),
                "round_trip_cost": {"btc_long": 0.004, "alt_minus_btc": 0.008}}

    def r5():
        return {"all": cf.rule_report(by.get("expiry_pin", []), ["pin"]),
                "by_asset": cf.breakdown(by.get("expiry_pin", []), cf.BOUNDS, "pin", lambda r: r["symbol"]),
                "by_expiry_type": cf.breakdown(by.get("expiry_pin", []), cf.BOUNDS, "pin", lambda r: r["etype"]),
                "by_strike_source": cf.breakdown(by.get("expiry_pin", []), cf.BOUNDS, "pin", lambda r: r["src"]),
                "max_loss_per_trade_of_equity": round(cf.SIZE * (0.008 + cf.LEG_COST), 5)}

    def r6():
        rep = cf.rule_report(by.get("expiry_unpin", []), ["V1", "V2"])
        rep["gate_exempt_note"] = "about 0.25 events a week: fails the 3/week gate by construction, diagnostic only"
        rep["passed"] = False
        return rep

    for name, fn in (("R1_stable_revert", r1), ("R2_newperp_short", r2), ("R3_weekend_fade", r3),
                     ("R4_day_of_week", r4), ("R5_expiry_pin", r5), ("R6_expiry_unpin", r6)):
        guard(name, fn)
    out["R3_gaps_note"] = gaps
    return out
