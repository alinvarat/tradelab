"""Pure calculations for the quick historical screens of ops/lines/ (no network calls here; fetchers live in
research/studies/run.py). Each screen picks its horizon on train, judges it on validation and only reports the sign on test.
"""
import random
import re
import time

from core.news_backtest import block_bootstrap_p

# ------------------------------------------------------------------ L1 listings
_TICK = re.compile(r"^[A-Z0-9]{2,12}$")


def _paren_symbols(title: str) -> list:
    out = []
    for grp in re.findall(r"\(([^()]*)\)", title):
        for tok in grp.split(","):
            tok = tok.strip()
            if _TICK.match(tok) and tok not in out:
                out.append(tok)
    return out


def binance_listing_symbols(title: str) -> list:
    """'Binance Will List Sapien (SAPIEN) with Seed Tag Applied' -> ['SAPIEN']. Futures, margin, Launchpool,
    Alpha and pair-only notices are not spot listings and give []."""
    if not re.match(r"^Binance Will List\b", title.strip()):
        return []
    return _paren_symbols(title)


_SKIP_FUT = ("TradFi", "Equity", "Pre-Market", "Pre-IPO", "Multiple", "COIN-M", "Delivery", "Copy Trading")


def binance_futures_symbols(title: str) -> list:
    """'Binance Futures Will Launch USDⓈ-Margined BANUSDT and AKTUSDT Perpetual Contracts ...' -> ['BAN', 'AKT'].
    TradFi, equity, pre-market, pre-IPO, multi-contract, coin-margined and delivery notices give []."""
    if not title.startswith("Binance Futures Will Launch") or any(k in title for k in _SKIP_FUT):
        return []
    out = []
    for tok in re.findall(r"\b([A-Z0-9]+)USDT\b", title):
        tok = re.sub(r"^(1000000|1000)", "", tok)
        if _TICK.match(tok) and tok not in out:
            out.append(tok)
    return out


def binance_add_symbols(title: str) -> list:
    """'Binance Will Add Cow Protocol (COW) and Cetus Protocol (CETUS) on Earn, Buy Crypto, ...' -> ['COW', 'CETUS']."""
    if not title.startswith("Binance Will Add") or " on " not in title:
        return []
    return _paren_symbols(title.split(" on ")[0])


def upbit_listing_symbols(title: str) -> list:
    """Upbit KRW-market additions: '로켓풀(RPL), 아큐라스트(ACU) 원화 마켓 디지털 자산 추가' or
    'KRW, BTC 마켓 디지털 자산 추가 (NEAR, YGG)'. BTC/USDT-market-only additions give []."""
    if "디지털 자산 추가" not in title or not ("KRW" in title or "원화" in title):
        return []
    return [s for s in _paren_symbols(title) if s not in ("KRW", "BTC", "USDT")]


_KUCOIN_SPOT_SKIP = ("futures", "copy trading", "perpetual", "tokenized stock", "xstock", "pre-market", "pre-ipo",
                     "index", "margin", "delist", "campaign", "airdrop", "trading bot", "convert", "earn", "loan")


def kucoin_listing_symbols(title: str) -> list:
    """'World Premiere: infiniFi (INFI) Listed on KuCoin' -> ['INFI']. Futures, copy-trading, tokenized-stock,
    pre-market, margin and delisting notices give []."""
    t = title.strip()
    low = t.lower()
    if any(k in low for k in _KUCOIN_SPOT_SKIP) or not re.search(r"\b[Ll]ist(ed|s)?\b", t):
        return []
    return _paren_symbols(t)


_BITGET_SPOT_SKIP = ("stock", "perp", "futures", "copy trading", "margin", "pre-market", "pre-ipo", "index",
                     "tokenized", "delist", "campaign", "airdrop", "trading bot", "convert", "earn", "loan")


def bitget_listing_symbols(title: str) -> list:
    """'Bitget Announcement on the Listing of Cow Protocol (COW)' -> ['COW']. Futures, stock-perp, copy-trading,
    margin and delisting notices give []."""
    t = title.strip()
    low = t.lower()
    if any(k in low for k in _BITGET_SPOT_SKIP) or "list" not in low:
        return []
    return _paren_symbols(t)


def close_at(bars: list, t: float, width: int):
    """bars: [(open_ts_s, close)] sorted. Close of the bar that contains t, or None when that bar is missing."""
    lo, hi = 0, len(bars) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        o = bars[mid][0]
        if o <= t < o + width:
            return bars[mid][1]
        if o > t:
            hi = mid - 1
        else:
            lo = mid + 1
    return None


L1_HORIZONS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "7d": 7 * 86400}
L1_DELAY = 60                    # enter one minute after the announcement
L1_COST = 0.006                  # round trip: taker 0.1% + slippage 0.2% per side


def binance_delist_symbols(title: str) -> list:
    """'Binance Will Delist EPIC, QUICK on 2026-10-28' -> ['EPIC', 'QUICK']; pair removals, margin, futures,
    Alpha and fiat notices give []."""
    m = re.match(r"^Binance Will Delist (.+?) on \d{4}-\d{2}-\d{2}", title.strip())
    if not m:
        return []
    out = []
    for tok in re.split(r",|\band\b|&", m.group(1)):
        tok = tok.strip()
        if _TICK.match(tok) and tok not in out:
            out.append(tok)
    return out


def binance_alpha_remove_symbols(title: str) -> list:
    """'Binance Alpha Will Remove PTB, AA, OWL, SLX (SLIMEX), 哭哭马 (2026-10-23)' -> ['PTB', 'AA', 'OWL', 'SLX'].
    The trailing date and parenthesised names are ignored; non-Latin tickers are skipped."""
    m = re.match(r"^Binance Alpha Will Remove (.+?)(?:\s*\(\d{4}-\d{2}-\d{2}\))?\s*$", title.strip())
    if not m:
        return []
    body = re.sub(r"\([^)]*\)", "", m.group(1))
    out = []
    for tok in re.split(r",|\band\b|&", body):
        tok = tok.strip()
        if _TICK.match(tok) and tok not in out:
            out.append(tok)
    return out


def listing_returns(ts: float, m1: list, h1: list, bench_m1: list, bench_h1: list, cost: float = L1_COST,
                    side: int = 1) -> dict:
    """Net log-free simple return of the coin minus the BTC return over the same window, per horizon.
    Entry at the close of the 1-minute bar containing ts+60s; horizons <= 4h exit on 1-minute bars, longer on 1-hour bars."""
    t0 = ts + L1_DELAY
    p0, b0 = close_at(m1, t0, 60), close_at(bench_m1, t0, 60)
    out = {}
    if not p0 or not b0:
        return out
    for name, h in L1_HORIZONS.items():
        if h <= 4 * 3600:
            p1, b1 = close_at(m1, t0 + h, 60), close_at(bench_m1, t0 + h, 60)
        else:
            p1, b1 = close_at(h1, t0 + h, 3600), close_at(bench_h1, t0 + h, 3600)
        if p1 and b1:
            raw = p1 / p0 - 1
            abn = side * (raw - (b1 / b0 - 1))          # side -1: a short gains when the coin falls against BTC
            out[name] = {"raw": raw, "abn": abn, "net": abn - cost}
    return out


def short_gain(entry: float, exit_: float) -> float:
    """Gain of a short opened at `entry` and closed at `exit_` as a fraction of the entry notional: 1 - exit/entry
    (a halving is +50%, never +100%). Fixed 2026-11-25: L7/L8/L10 used entry/exit - 1, which overstated gains."""
    return 1 - exit_ / entry


def split_of(ts: float, bounds: dict) -> str:
    """bounds = {'train': (start, end), ...} in unix seconds, end exclusive."""
    for k, (a, b) in bounds.items():
        if a <= ts < b:
            return k
    return "out"


def day_key(row: dict) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(row["ts"]))


MIN_SPLIT_N = 10


def row_key(r: dict) -> tuple:
    return (r.get("symbol"), r.get("market"), round(r.get("ts") or 0, 1), r.get("kind"))


def integrity(rows: list, horizons: list, bounds: dict, min_split_n: int = MIN_SPLIT_N) -> dict:
    """Data checks every screen must pass before any verdict (RUNBOOK 'data gate'). Problems make the verdict invalid;
    warnings are printed with the result. Added 2026-11-24 after L4 counted 75 markets about 40 times each."""
    keys = [row_key(r) for r in rows]
    dup = len(keys) - len(set(keys))
    per_split = {sp: sum(1 for r in rows if split_of(r["ts"], bounds) == sp) for sp in bounds}
    problems, warnings = [], []
    if dup:
        problems.append(f"{dup} duplicate rows of {len(rows)} ({dup / len(rows):.0%})")
    for sp, n in per_split.items():
        if n < min_split_n:     # train and validation decide; a thin test split is only a warning
            (problems if sp in ("train", "validation") else warnings).append(f"split {sp} has {n} rows (< {min_split_n})")
    out_of_range = sum(1 for r in rows if split_of(r["ts"], bounds) == "out")
    if out_of_range:
        warnings.append(f"{out_of_range} rows outside every split")
    for h in horizons:
        for sp in bounds:
            v = [r["ret"][h]["net"] for r in rows if split_of(r["ts"], bounds) == sp and h in r["ret"]]
            if len(v) >= min_split_n and min(v) >= 0:
                warnings.append(f"{h}/{sp}: no losing event in {len(v)} (check the data before believing it)")
            if len(set(round(x, 9) for x in v)) < max(1, len(v) // 4):
                warnings.append(f"{h}/{sp}: only {len(set(round(x, 9) for x in v))} distinct values in {len(v)} rows")
    return {"rows": len(rows), "unique": len(set(keys)), "per_split": per_split, "problems": problems,
            "warnings": warnings, "ok": not problems}


def judge(rows: list, horizons: list, bounds: dict, cost_extra: float = 0.0, seed: int = 7, pick_trim: int = 0) -> dict:
    """rows: [{'ts', 'symbol', 'venue', 'ret': {h: {'net': x}}}]. Pick the horizon with the best train mean, then
    report validation mean / block p (cluster = UTC day) and test mean, plus the result without the best 1 and 5 events."""
    rng = random.Random(seed)
    check = integrity(rows, horizons, bounds)

    def vals(split, h):
        r = [x for x in rows if split_of(x["ts"], bounds) == split and h in x["ret"]]
        return [x["ret"][h]["net"] - cost_extra for x in r], [day_key(x) for x in r]

    table = {}
    for h in horizons:
        t = {}
        for split in bounds:
            v, k = vals(split, h)
            t[split] = {"n": len(v), "mean": round(sum(v) / len(v), 5) if v else None,
                        "p": round(block_bootstrap_p(v, k, rng), 4) if v else None}
        table[h] = t
    if not check["ok"]:
        return {"table": table, "pick": None, "integrity": check,
                "verdict": "invalid data: " + "; ".join(check["problems"])}
    train_ok = [h for h in horizons if table[h]["train"]["mean"] is not None]
    if not train_ok:
        return {"table": table, "pick": None, "verdict": "no data", "integrity": check}
    def train_score(h):                 # pick_trim > 0: mean without the best pick_trim train events (L1c rule)
        v, _ = vals("train", h)
        v = sorted(v)[:-pick_trim] if pick_trim and len(v) > pick_trim else v
        return sum(v) / len(v)

    pick = max(train_ok, key=train_score)
    v, k = vals("validation", pick)
    robust = {}
    for drop in (1, 5):
        if len(v) > drop:
            keep = sorted(zip(v, k), key=lambda z: z[0])[:-drop]
            robust[f"without_best_{drop}"] = round(sum(z[0] for z in keep) / len(keep), 5)
    val = table[pick]["validation"]
    test = table[pick].get("test", {})
    passed = (val["mean"] is not None and val["mean"] > 0 and val["p"] < 0.05
              and all(x > 0 for x in robust.values())
              and (test.get("mean") is None or test["mean"] > 0))
    killed = val["mean"] is None or val["mean"] <= 0 or val["p"] > 0.2 or any(x <= 0 for x in robust.values())
    return {"table": table, "pick": pick, "robust": robust, "integrity": check,
            "verdict": "passed" if passed else ("killed" if killed else "inconclusive")}


# ------------------------------------------------------------------ L1b forward ledger (protocol_L1b_listings_forward.md)
L1B_HOLD_S, L1B_DELAY_S, L1B_FEES, L1B_STAKE = 4 * 3600, 60, 0.002, 0.20


def new_listing_events(seen: set, events: list) -> list:
    """events: [{'venue','symbol','ts'}]; returns those whose key is not in `seen` and adds them to it."""
    out = []
    for e in events:
        k = f"{e['venue']}:{e['symbol']}:{int(e['ts'])}"
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def l1b_result(entry_ask: float, exit_bid: float, btc_entry: float, btc_exit: float) -> dict:
    raw = exit_bid / entry_ask - 1
    abn = raw - (btc_exit / btc_entry - 1)
    return {"raw": raw, "abn": abn, "net": abn - L1B_FEES}


def ledger_result(side: int, entry_px: float, exit_px: float, btc_entry: float, btc_exit: float, extra: float = 0.0) -> dict:
    """side +1 long (buy ask, sell bid), -1 short (sell bid, buy back ask); result relative to BTC, net of fees and extra."""
    raw = side * (exit_px / entry_px - 1)
    abn = raw - side * (btc_exit / btc_entry - 1)
    return {"raw": raw, "abn": abn, "net": abn - L1B_FEES - extra}


# ------------------------------------------------------------------ L4 Polymarket long-shot selling (ops/lines/L4_polymarket_maker.md)
L4_LEADS_D = (7, 3, 1)


def longshot_sells(history: list, close_ts: float, yes_won: bool, lo: float = 0.02, hi: float = 0.10) -> dict:
    """history: [{'t','p'}] of the YES price (daily points). For each lead (days before close), if either side trades
    in [lo, hi], sell that side at that price as a maker (no fee): +price when it loses, -(1-price) when it wins.
    Returns {'T-7d': {'net': return on the locked collateral (1-price), 'monthly': net*30/lead, 'side', 'price'}}."""
    out = {}
    pts = sorted(history, key=lambda x: x["t"])
    for lead in L4_LEADS_D:
        t = close_ts - lead * 86400
        prior = [x for x in pts if t - 2 * 86400 <= x["t"] <= t]
        if not prior:
            continue
        yes = float(prior[-1]["p"])
        for side, price, won in (("yes", yes, yes_won), ("no", 1 - yes, not yes_won)):
            if lo <= price <= hi:
                pnl = -(1 - price) if won else price
                net = pnl / (1 - price)
                out[f"T-{lead}d"] = {"net": net, "monthly": net * 30 / lead, "side": side, "price": round(price, 4)}
    return out


# ------------------------------------------------------------------ L3 small caps with an 8-K outside market hours
L3_ITEMS = ("1.01", "2.02", "5.02", "7.01", "8.01", "3.02", "2.01")
L3_COST, L3_GAP = 0.01, 0.10


def _et(ts: float):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(ts, ZoneInfo("America/New_York"))


def _et_ts(day, hh: int, mm: int) -> float:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=ZoneInfo("America/New_York")).timestamp()


def smallcap_events(symbol: str, bars: list, filings: list, bench: dict, px=(1.0, 20.0), dollar_vol=(1e6, 50e6)) -> list:
    """bars: daily [{'t','o','c','v'}]; filings: [{'ts','items','accession'}]; bench: ET date -> (open, close) of IWM.
    An 8-K accepted after 16:00 ET of the previous session and before 09:00 ET of session D, when the stock closed at
    $1-20 with 20-day average dollar volume $1-50M before D and gapped >= 10% at D's open. Returns rows with
    continuation and reversal returns for D (open->close) and D+1 (open D -> close D+1), IWM-adjusted, net of 1%."""
    days = [(_et(b["t"]).date(), b) for b in bars]
    out = []
    for f in filings:
        for i in range(21, len(days) - 1):
            d, b = days[i]
            prev_d, prev = days[i - 1]
            if not _et_ts(prev_d, 16, 0) <= f["ts"] < _et_ts(d, 9, 0):
                continue
            win = [x for _, x in days[i - 20:i]]
            adv = sum(x["c"] * x["v"] for x in win) / 20
            if not (px[0] <= prev["c"] <= px[1] and dollar_vol[0] <= adv <= dollar_vol[1]):
                break
            gap = b["o"] / prev["c"] - 1
            if abs(gap) < L3_GAP or d not in bench:
                break
            sign = 1 if gap > 0 else -1
            nxt_d, nxt = days[i + 1]
            bo, bc = bench[d]
            bn = bench.get(nxt_d, (None, None))[1]
            r0 = sign * ((b["c"] / b["o"] - 1) - (bc / bo - 1))
            ret = {"cont_d0": {"net": r0 - L3_COST}, "rev_d0": {"net": -r0 - L3_COST}}
            if bn:
                r1 = sign * ((nxt["c"] / b["o"] - 1) - (bn / bo - 1))
                ret |= {"cont_d1": {"net": r1 - L3_COST}, "rev_d1": {"net": -r1 - L3_COST}}
            tag = next((it for it in L3_ITEMS if it in f["items"]), "other")
            out.append({"symbol": symbol, "market": f.get("accession"), "ts": b["t"], "kind": tag,
                        "dir": "up" if sign > 0 else "down", "gap": round(gap, 4), "ret": ret})
            break
    return out


# ------------------------------------------------------------------ L6 insider purchases in small caps
L6_COST, L6_HOLDS = 0.01, (5, 20)


def insider_rows(symbol: str, bars: list, events: list, bench: dict, px=(1.0, 20.0), dollar_vol=(0.5e6, 20e6)) -> list:
    """events: [{'accession','date','value','ts'}] (ts = conservative availability time). Entry at the open of the
    first session starting after ts; previous close $1-20 and 20-day average dollar volume $0.5-20M. Returns +5 and
    +20 session returns (open to close), IWM-adjusted, net of 1% round trip."""
    days = [(_et(b["t"]).date(), b) for b in bars]
    out = []
    for e in events:
        i = next((k for k, (d, b) in enumerate(days) if b["t"] > e["ts"]), None)
        if i is None or i < 21:
            continue
        d, b = days[i]
        prev = days[i - 1][1]
        adv = sum(x["c"] * x["v"] for _, x in days[i - 20:i]) / 20
        if not (px[0] <= prev["c"] <= px[1] and dollar_vol[0] <= adv <= dollar_vol[1]) or d not in bench:
            continue
        ret = {}
        for h in L6_HOLDS:
            if i + h - 1 < len(days):
                xd, x = days[i + h - 1]
                if xd in bench:
                    r = (x["c"] / b["o"] - 1) - (bench[xd][1] / bench[d][0] - 1)
                    ret[f"h{h}"] = {"net": r - L6_COST}
        if ret:
            out.append({"symbol": symbol, "market": e["accession"], "ts": b["t"], "kind": "form4_buy",
                        "value": e.get("value"), "ret": ret})
    return out


# ------------------------------------------------------------------ L7 first red day short in small caps
L7_COST, L7_RUN, L7_GREEN = 0.01, 0.15, 3
L7_HOLDS = (1, 2, 5)


def first_red_day_rows(symbol: str, bars: list, bench: dict, px=(1.0, 20.0), dollar_vol=(1e6, 50e6)) -> list:
    """bars: daily [{'t','o','c','v'}] oldest first; bench: ET date -> (open, close) of IWM.
    Session D closes red after L7_GREEN green sessions in a row, with close(D-1)/close(D-L7_GREEN-0) - 1 >= 15%;
    previous close $1-20 and 20-day average dollar volume $1-50M. Short at the open of D+1 (never the close of D,
    which is already known) to the close +1/+2/+5 sessions later, IWM-adjusted, net of 1%. One row per streak."""
    days = [(_et(b["t"]).date(), b) for b in bars]
    out, i = [], L7_GREEN + 21
    while i < len(days):
        d, b = days[i]
        run = [x for _, x in days[i - L7_GREEN:i]]      # D-3, D-2, D-1
        green = all(x["c"] > x["o"] for x in run)
        rise = run[-1]["c"] / run[0]["c"] - 1
        prev = days[i - 1][1]
        adv = sum(x["c"] * x["v"] for _, x in days[i - 21:i]) / 20
        if not (b["c"] < b["o"] and green and rise >= L7_RUN
                and px[0] <= prev["c"] <= px[1] and dollar_vol[0] <= adv <= dollar_vol[1] and d in bench):
            i += 1
            continue
        if i + 1 >= len(days) or days[i + 1][0] not in bench:
            i += 1
            continue
        ed, e = days[i + 1]                               # entry session D+1
        ret = {}
        for h in L7_HOLDS:
            j = i + h
            if j < len(days) and days[j][0] in bench:
                short = short_gain(e["o"], days[j][1]["c"])     # gain on the short from the D+1 open
                bshort = short_gain(bench[ed][0], bench[days[j][0]][1])   # gain on shorting IWM over the same window
                ret[f"h{h}"] = {"net": short - bshort - L7_COST}
        if ret:
            out.append({"symbol": symbol, "market": f"{d}{symbol}", "ts": e["t"], "kind": "first_red_day",
                        "rise": round(rise, 4), "ret": ret})
        i += L7_GREEN + 1                                # skip the streak so one run cannot fire twice
    return out


# ------------------------------------------------------------------ L2 short around large cliff token unlocks
L2_FUNDING_DAY, L2_FEES, L2_MIN_FRAC = 0.0009, 0.002, 0.01
L2_WINDOWS = {"pre14_post7": (-14, 7), "pre7_0": (-7, 0), "post0_7": (0, 7)}


def unlock_events(entry: dict, start_ts: float, end_ts: float, min_frac: float = L2_MIN_FRAC) -> list:
    """One DefiLlama emissionsIndex entry -> cliff unlocks in [start, end) whose size is >= min_frac of the current
    circulating supply (a known size bias: supply today, not at the event). Returns [{'symbol','ts','frac'}]."""
    sym = ((entry.get("tokenPrice") or [{}])[0].get("symbol") or "").upper()
    circ = entry.get("circSupply") or 0
    out = []
    if not sym or circ <= 0:
        return out
    for e in entry.get("unlockEvents") or []:
        amt = (e.get("summary") or {}).get("totalTokensCliff") or 0
        ts = e.get("timestamp") or 0
        if start_ts <= ts < end_ts and amt / circ >= min_frac:
            out.append({"symbol": sym, "ts": ts, "frac": round(amt / circ, 4), "market": entry.get("protocolSlug")})
    return out


def unlock_short_returns(ts: float, d1: list, bench_d1: list) -> dict:
    """Daily closes [(open_ts, close)] -> short return minus BTC, fees and assumed funding, for each window around ts."""
    out = {}
    for name, (a, b) in L2_WINDOWS.items():
        p0, p1 = close_at(d1, ts + a * 86400, 86400), close_at(d1, ts + b * 86400, 86400)
        b0, b1 = close_at(bench_d1, ts + a * 86400, 86400), close_at(bench_d1, ts + b * 86400, 86400)
        if p0 and p1 and b0 and b1:
            abn = -((p1 / p0 - 1) - (b1 / b0 - 1))
            out[name] = {"net": abn - L2_FEES - L2_FUNDING_DAY * (b - a)}
    return out


# ------------------------------------------------------------------ L8 fade the day's top crypto gainers
L8_THRESH, L8_MIN_QV = 0.20, 2e6          # UTC-day gain (close/open - 1) and 20-day average quote volume in USDT
L8_FEES, L8_FUNDING_DAY = 0.004, 0.0009   # round trip taker + slippage; assumed perp funding paid by the short
L8_HOLDS = (1, 3, 7)
L8_COOLDOWN = 7                           # days before the same coin can fire again (no overlapping rows)


def gainer_fade_rows(symbol: str, d1: list, btc: dict) -> list:
    """d1: daily [(open_ts, o, h, l, c, quote_vol)] oldest first (UTC days); btc: open_ts -> (o, c) of BTCUSDT.
    Day D gains >= L8_THRESH (close/open) with 20-day average quote volume >= L8_MIN_QV. Short at the open of D+1
    (the first price after D's close is known) to the close of D+h, minus BTC over the same window, minus fees and
    assumed funding for h days. One row per coin per L8_COOLDOWN days."""
    out, i = [], 21
    while i + 1 < len(d1):
        t, o, _h, _l, c, _qv = d1[i]
        adv = sum(x[5] for x in d1[i - 20:i]) / 20
        if not (o > 0 and c / o - 1 >= L8_THRESH and adv >= L8_MIN_QV):
            i += 1
            continue
        e = d1[i + 1]
        if e[0] - t != 86400 or e[0] not in btc:        # gap in the data: no clean next-day entry
            i += 1
            continue
        ret = {}
        for h in L8_HOLDS:
            j = i + h
            if j < len(d1) and d1[j][0] - e[0] == (h - 1) * 86400 and d1[j][0] in btc:
                short = short_gain(e[1], d1[j][4])
                bshort = short_gain(btc[e[0]][0], btc[d1[j][0]][1])
                ret[f"h{h}"] = {"net": short - bshort - L8_FEES - L8_FUNDING_DAY * h}
        if ret:
            out.append({"symbol": symbol, "market": f"{t}{symbol}", "ts": e[0], "kind": "gainer_fade",
                        "gain": round(c / o - 1, 4), "ret": ret})
        i += L8_COOLDOWN
    return out


# ------------------------------------------------------------------ L9 buy the day's biggest crypto losers
L9_THRESH = -0.20                         # UTC-day move (close/open - 1) at or below -20%
L9_FEES = 0.004                           # round trip taker + slippage; spot long, no funding
L9_HOLDS = (1, 3, 7)


def loser_bounce_rows(symbol: str, d1: list, btc: dict) -> list:
    """Mirror of gainer_fade_rows: day D falls >= 20% (close/open) with 20-day average quote volume >= L8_MIN_QV.
    Buy spot at the open of D+1, sell at the close of D+h, minus BTC over the same window and L9_FEES.
    One row per coin per L8_COOLDOWN days."""
    out, i = [], 21
    while i + 1 < len(d1):
        t, o, _h, _l, c, _qv = d1[i]
        adv = sum(x[5] for x in d1[i - 20:i]) / 20
        if not (o > 0 and c / o - 1 <= L9_THRESH and adv >= L8_MIN_QV):
            i += 1
            continue
        e = d1[i + 1]
        if e[0] - t != 86400 or e[0] not in btc:
            i += 1
            continue
        ret = {}
        for h in L9_HOLDS:
            j = i + h
            if j < len(d1) and d1[j][0] - e[0] == (h - 1) * 86400 and d1[j][0] in btc:
                long = d1[j][4] / e[1] - 1
                blong = btc[d1[j][0]][1] / btc[e[0]][0] - 1
                ret[f"h{h}"] = {"net": long - blong - L9_FEES}
        if ret:
            out.append({"symbol": symbol, "market": f"{t}{symbol}", "ts": e[0], "kind": "loser_bounce",
                        "drop": round(c / o - 1, 4), "ret": ret})
        i += L8_COOLDOWN
    return out


# ------------------------------------------------------------------ L10 fade large small-cap opening gaps
L10_GAP, L10_COST = 0.30, 0.01
L10_HOLDS = (0, 1, 5)                     # sessions after the gap day: 0 = cover at the same day's close


def gap_fade_rows(symbol: str, bars: list, bench: dict, px=(1.0, 20.0), dollar_vol=(1e6, 50e6)) -> list:
    """bars: daily [{'t','o','c','v'}] oldest first; bench: ET date -> (open, close) of IWM.
    Session D opens >= 30% above the previous close; previous close $1-20 and 20-day average dollar volume $1-50M
    (both known before D's open). Short at D's open to the close of D (+0), D+1 and D+5, IWM-adjusted, net of 1%.
    One row per symbol per 5 sessions."""
    days = [(_et(b["t"]).date(), b) for b in bars]
    out, i = [], 21
    while i < len(days):
        d, b = days[i]
        prev = days[i - 1][1]
        adv = sum(x["c"] * x["v"] for _, x in days[i - 21:i - 1]) / 20
        if not (prev["c"] > 0 and b["o"] / prev["c"] - 1 >= L10_GAP and px[0] <= prev["c"] <= px[1]
                and dollar_vol[0] <= adv <= dollar_vol[1] and d in bench):
            i += 1
            continue
        ret = {}
        for h in L10_HOLDS:
            j = i + h
            if j < len(days) and days[j][0] in bench:
                short = short_gain(b["o"], days[j][1]["c"])
                bshort = short_gain(bench[d][0], bench[days[j][0]][1])
                ret[f"h{h}"] = {"net": short - bshort - L10_COST}
        if ret:
            out.append({"symbol": symbol, "market": f"{d}{symbol}", "ts": b["t"], "kind": "gap_fade",
                        "gap": round(b["o"] / prev["c"] - 1, 4), "ret": ret})
        i += 5
    return out


# ------------------------------------------------------------------ L11 short crowded longs (extreme perp funding)
L11_FUNDING, L11_FEES = 0.001, 0.004      # a settled funding rate >= 0.10% per interval; round trip taker + slippage
L11_HOLDS = (1, 3, 7)


def funding_short_rows(symbol: str, d1: list, btc: dict, funding: list) -> list:
    """d1: daily [(open_ts, o, h, l, c, quote_vol)] (spot prices stand in for the perp); funding: [(ts, rate)] settled
    rates of the USDT perp. Day D has a settled rate >= L11_FUNDING and 20-day average quote volume >= L8_MIN_QV.
    Short at the open of D+1 to the close of D+h; gain = short_gain - BTC short gain - fees + the funding the short
    actually received (sum of settled rates from the entry to the exit). One row per coin per L8_COOLDOWN days."""
    by_day = {}
    for ts, r in funding:
        by_day.setdefault(int(ts // 86400) * 86400, []).append((ts, r))
    out, i = [], 21
    while i + 1 < len(d1):
        t = d1[i][0]
        adv = sum(x[5] for x in d1[i - 20:i]) / 20
        if not (max((r for _, r in by_day.get(t, [])), default=0.0) >= L11_FUNDING and adv >= L8_MIN_QV):
            i += 1
            continue
        e = d1[i + 1]
        if e[0] - t != 86400 or e[0] not in btc:
            i += 1
            continue
        ret = {}
        for h in L11_HOLDS:
            j = i + h
            if j < len(d1) and d1[j][0] - e[0] == (h - 1) * 86400 and d1[j][0] in btc:
                end = d1[j][0] + 86400
                paid = sum(r for ts, r in funding if e[0] <= ts < end)
                ret[f"h{h}"] = {"net": short_gain(e[1], d1[j][4]) - short_gain(btc[e[0]][0], btc[d1[j][0]][1])
                                - L11_FEES + paid, "funding": paid}
        if ret:
            out.append({"symbol": symbol, "market": f"{t}{symbol}", "ts": e[0], "kind": "funding_short", "ret": ret})
        i += L8_COOLDOWN
    return out


# ------------------------------------------------------------------ L12 / L13 fade one-hour crypto shocks
L12_MOVE, L12_REL = 0.08, 0.06             # hour return >= 8% and >= 6% beyond BTC's same hour
L12_MIN_QV = 2e5                           # 30-day average hourly quote volume (USDT)
L12_FEES, L12_FUNDING_H = 0.004, 0.0009 / 24
L12_HOLDS = (1, 4, 24)                     # hours after entry
L12_COOLDOWN_H = 24


def hourly_shock_rows(symbol: str, h1: list, btc: dict, side: int) -> list:
    """h1: hourly [(open_ts, o, h, l, c, quote_vol)] oldest first; btc: open_ts -> (o, c) of BTCUSDT hours.
    side -1 (L12): hour H rose >= L12_MOVE and >= L12_REL more than BTC -> short at the open of H+1.
    side +1 (L13): hour H fell <= -L12_MOVE and <= -L12_REL vs BTC -> buy at the open of H+1.
    Exit at the close of hour H+k (k = 1, 4, 24 hours held), BTC-adjusted, minus fees (and funding for shorts).
    Needs 720 prior hours for the volume screen. One row per coin per L12_COOLDOWN_H hours."""
    out, i = [], 720
    qv_sum = sum(x[5] for x in h1[:720]) if len(h1) >= 720 else 0.0
    while i + 1 < len(h1):
        t, o, _hh, _l, c, _qv = h1[i]
        adv = qv_sum / 720
        qv_sum += h1[i][5] - h1[i - 720][5]
        b = btc.get(t)
        if not (o > 0 and b and adv >= L12_MIN_QV):
            i += 1
            continue
        r, br = c / o - 1, b[1] / b[0] - 1
        hit = (r >= L12_MOVE and r - br >= L12_REL) if side < 0 else (r <= -L12_MOVE and r - br <= -L12_REL)
        e = h1[i + 1]
        if not hit or e[0] - t != 3600 or e[0] not in btc:
            i += 1
            continue
        ret = {}
        for k in L12_HOLDS:
            j = i + k
            if j < len(h1) and h1[j][0] - e[0] == (k - 1) * 3600 and h1[j][0] in btc:
                if side < 0:
                    g = short_gain(e[1], h1[j][4]) - short_gain(btc[e[0]][0], btc[h1[j][0]][1]) - L12_FEES - L12_FUNDING_H * k
                else:
                    g = (h1[j][4] / e[1] - 1) - (btc[h1[j][0]][1] / btc[e[0]][0] - 1) - L12_FEES
                ret[f"h{k}"] = {"net": g}
        if ret:
            out.append({"symbol": symbol, "market": f"{t}{symbol}{side}", "ts": e[0],
                        "kind": "hour_spike_fade" if side < 0 else "hour_crash_bounce", "move": round(r, 4), "ret": ret})
        i += L12_COOLDOWN_H
        qv_sum = sum(x[5] for x in h1[i - 720:i])   # window of the 720 hours before i (events are rare: cheap)
    return out


# ------------------------------------------------------------------ L12b: L12 restricted to coins with a live perp
L12B_STOP = 0.30                           # reported variant: buy back if the price trades 30% above the entry


def perp_shock_rows(symbol: str, h1: list, btc: dict, funding: list) -> list:
    """L12 events (side -1, same thresholds, volume screen and cooldown) kept only when the coin's USDT perp settled
    a funding rate in the 24 hours before entry (a short was actually possible). Net adds the funding really settled
    between entry and exit (positive rate = longs pay shorts) instead of an assumed cost. Each hold also reports
    `net_stop`: the same trade with a buy-back stop at +L12B_STOP from the entry, filled at the stop price or at the
    first hour's open beyond it (gap), whichever is worse."""
    fts = sorted(funding)
    times = [t for t, _ in fts]
    import bisect
    out = []
    idx = {x[0]: n for n, x in enumerate(h1)}
    for r in hourly_shock_rows(symbol, h1, btc, -1):
        e_ts = r["ts"]
        k0 = bisect.bisect_left(times, e_ts - 86400)
        if k0 >= len(times) or times[k0] >= e_ts:
            continue
        ei = idx.get(e_ts)
        if ei is None:
            continue
        entry = h1[ei][1]
        stop_px = entry * (1 + L12B_STOP)
        ret = {}
        for k in L12_HOLDS:
            j = ei + k - 1
            if j >= len(h1) or h1[j][0] - e_ts != (k - 1) * 3600 or h1[j][0] not in btc:
                continue
            end = h1[j][0] + 3600
            a, b = bisect.bisect_left(times, e_ts), bisect.bisect_left(times, end)
            paid = sum(rate for _, rate in fts[a:b])
            bshort = short_gain(btc[e_ts][0], btc[h1[j][0]][1])
            net = short_gain(entry, h1[j][4]) - bshort - L12_FEES + paid
            exit_px = h1[j][4]
            for m in range(ei, j + 1):                     # first hour that reaches the stop
                if h1[m][2] >= stop_px:
                    exit_px = max(stop_px, h1[m][1])       # gapped open above the stop fills at the open
                    break
            net_stop = short_gain(entry, exit_px) - bshort - L12_FEES + paid
            ret[f"h{k}"] = {"net": net, "net_stop": net_stop, "funding": paid}
        if ret:
            out.append({**r, "kind": "perp_spike_fade", "ret": ret})
    return out


# ------------------------------------------------------------------ H2: open-interest deleveraging flush (perps)
H2_DROP = 0.15                  # open interest (contracts, not USD) down >= 15% over 24 h
H2_MOVE = 0.10                  # and the hourly close down (up) >= 10% over the same 24 h
H2_MIN_QV = 2e5                 # 30-day (720 h) average hourly perp quote volume before the decision hour (USDT)
H2_MIN_OI_USD = 1e6             # open interest value 24 h earlier (USDT)
H2_FEES = 0.004                 # round trip, taker + slippage (perp)
H2_HOLDS = (1, 3, 7)            # days held
H2_COOLDOWN_H = 168             # one row per coin per 7 days
H2_ALPHA = 0.05 / 2             # Bonferroni across the two rules (long after a down flush, short after an up flush)
H2_START, H2_END = "2022-01-01", "2026-11-01"


def oi_hourly_row(fields):
    """One 5-minute futures `metrics` row (create_time, symbol, sum_open_interest, sum_open_interest_value, ...) ->
    (ts_s, open_interest, open_interest_value) when the row sits on the hour and both numbers exist, else None."""
    t = fields[0].strip()
    if t.isdigit():
        ts = int(t) // 1000 if int(t) < 10**14 else int(t) // 1000000
    else:
        if not t.endswith(":00:00"):
            return None
        import calendar
        ts = calendar.timegm(time.strptime(t, "%Y-%m-%d %H:%M:%S"))
    if ts % 3600:
        return None
    try:
        a, b = float(fields[2]), float(fields[3])
    except (ValueError, IndexError):
        return None
    return (ts, a, b)


def oi_flush_rows(symbol: str, h1: list, oi: dict, btc: dict, funding: list, start_ts: float = 0.0) -> list:
    """Perp open-interest flush. h1: hourly perp klines [(open_ts, o, h, l, c, quote_vol)], oldest first; oi: hour
    timestamp -> (open_interest, open_interest_value) snapshot taken at that hour; btc: open_ts -> (o, c) of the BTCUSDT
    perp hours; funding: [(ts, rate)] settled rates (positive = longs pay shorts).
    Decision time D = end of hour i (everything used is known at D): open interest at D <= (1 - H2_DROP) x open interest
    at D - 24 h AND close(i) / close(i - 24 h) - 1 <= -H2_MOVE (long) or >= +H2_MOVE (short). Also needed: open interest
    value at D - 24 h >= H2_MIN_OI_USD and 720 prior contiguous hours averaging >= H2_MIN_QV quote volume (hour i itself
    excluded). Entry at the open of the hour starting D + 1 h (one hour of delay for publication and execution).
    Exit at the close of the last hour of 1, 3 and 7 days held. Return = coin gain - BTC gain over the same window -
    H2_FEES + funding settled in the window (a long pays the rate, a short receives it). `net_unhedged` omits the BTC leg.
    One row per coin per H2_COOLDOWN_H hours; rows before start_ts are dropped."""
    import bisect
    fts = sorted(funding)
    times = [t for t, _ in fts]
    out, i = [], 720
    while i + 2 < len(h1):
        t = h1[i][0]
        D = t + 3600
        if h1[i - 24][0] != t - 86400:
            i += 1
            continue
        mv = h1[i][4] / h1[i - 24][4] - 1
        if abs(mv) < H2_MOVE:
            i += 1
            continue
        now, then = oi.get(D), oi.get(D - 86400)
        if not (now and then and then[0] > 0 and then[1] >= H2_MIN_OI_USD and now[0] / then[0] - 1 <= -H2_DROP):
            i += 1
            continue
        e = h1[i + 2]
        if h1[i + 1][0] != D or e[0] != D + 3600 or e[0] < start_ts or e[0] not in btc or not e[1] > 0:
            i += 1
            continue
        if h1[i - 720][0] != t - 720 * 3600 or sum(x[5] for x in h1[i - 720:i]) / 720 < H2_MIN_QV:
            i += 1
            continue
        side = 1 if mv <= -H2_MOVE else -1
        ret = {}
        for d in H2_HOLDS:
            j = i + 2 + 24 * d - 1
            if j >= len(h1) or h1[j][0] - e[0] != (24 * d - 1) * 3600 or h1[j][0] not in btc:
                continue
            a, b = bisect.bisect_left(times, e[0]), bisect.bisect_left(times, h1[j][0] + 3600)
            paid = sum(r for _, r in fts[a:b])
            if side > 0:
                coin, bt, fund = h1[j][4] / e[1] - 1, btc[h1[j][0]][1] / btc[e[0]][0] - 1, -paid
            else:
                coin, bt, fund = short_gain(e[1], h1[j][4]), short_gain(btc[e[0]][0], btc[h1[j][0]][1]), paid
            ret[f"d{d}"] = {"net": coin - bt - H2_FEES + fund, "net_unhedged": coin - H2_FEES + fund, "funding": fund}
        if ret:
            out.append({"symbol": symbol, "market": f"{D}{symbol}{side}", "ts": e[0],
                        "kind": "oi_flush_long" if side > 0 else "oi_flush_short",
                        "oi_drop": round(now[0] / then[0] - 1, 4), "move": round(mv, 4), "ret": ret})
        i += H2_COOLDOWN_H
    return out


def h2_bounds():
    import calendar
    T = lambda y, m=1, d=1: float(calendar.timegm((y, m, d, 0, 0, 0)))  # noqa: E731
    return {"train": (T(2022), T(2023)), "validation": (T(2023), T(2025)), "test": (T(2025), T(2026, 11))}


def oi_flush_summary(all_rows: list) -> dict:
    """Verdict per rule (pre-registered in RESULTS.md 'H2 screen'). A rule passes only if judge() passes at base cost,
    the validation block p is below H2_ALPHA (Bonferroni over 2 rules), the validation mean stays > 0 at double cost
    (another H2_FEES) and the test mean at the picked hold is > 0, and the rule has >= 3 events a week."""
    bounds = h2_bounds()
    hs = [f"d{d}" for d in H2_HOLDS]
    weeks = (bounds["test"][1] - bounds["train"][0]) / (7 * 86400)
    summ = {"rows": len(all_rows), "alpha_bonferroni": H2_ALPHA, "weeks": round(weeks, 1)}
    for kind in ("oi_flush_long", "oi_flush_short"):
        rows = [dict(r, split=split_of(r["ts"], bounds)) for r in all_rows if r.get("kind") == kind]
        base = judge(rows, hs, bounds, pick_trim=5)
        dbl = judge(rows, hs, bounds, cost_extra=H2_FEES, pick_trim=5)
        unh = judge([dict(r, ret={h: {"net": v["net_unhedged"]} for h, v in r["ret"].items()}) for r in rows],
                    hs, bounds, pick_trim=5)
        per_week = sum(1 for r in rows if r["split"] != "out") / weeks
        pick = base.get("pick")
        checks = {}
        if pick:
            val, test = base["table"][pick]["validation"], base["table"][pick].get("test", {})
            dval = dbl["table"][pick]["validation"]
            checks = {"base_judge_passed": base["verdict"] == "passed",
                      "validation_p_below_bonferroni": val["p"] is not None and val["p"] < H2_ALPHA,
                      "double_cost_validation_positive": dval["mean"] is not None and dval["mean"] > 0,
                      "test_positive": test.get("mean") is not None and test["mean"] > 0,
                      "three_a_week": per_week >= 3}
        by_day = {}
        for r in rows:
            by_day[day_key(r)] = by_day.get(day_key(r), 0) + 1
        summ[kind] = {"rows": len(rows), "per_week": round(per_week, 2), "coins": len({r["symbol"] for r in rows}),
                      "max_events_one_day": max(by_day.values(), default=0), "base": base, "double_cost": dbl,
                      "unhedged_descriptive": unh, "checks": checks,
                      "mean_funding": round(sum(v["funding"] for r in rows for v in r["ret"].values())
                                            / max(1, sum(len(r["ret"]) for r in rows)), 5),
                      "passed": bool(checks) and all(checks.values())}
    return summ
