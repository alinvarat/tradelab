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


def split_of(ts: float, bounds: dict) -> str:
    """bounds = {'train': (start, end), ...} in unix seconds, end exclusive."""
    for k, (a, b) in bounds.items():
        if a <= ts < b:
            return k
    return "out"


def day_key(row: dict) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(row["ts"]))


def judge(rows: list, horizons: list, bounds: dict, cost_extra: float = 0.0, seed: int = 7, pick_trim: int = 0) -> dict:
    """rows: [{'ts', 'symbol', 'venue', 'ret': {h: {'net': x}}}]. Pick the horizon with the best train mean, then
    report validation mean / block p (cluster = UTC day) and test mean, plus the result without the best 1 and 5 events."""
    rng = random.Random(seed)

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
    train_ok = [h for h in horizons if table[h]["train"]["mean"] is not None]
    if not train_ok:
        return {"table": table, "pick": None, "verdict": "no data"}
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
    return {"table": table, "pick": pick, "robust": robust,
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
