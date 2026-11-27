"""S1-S5 stage-0 probes (plan 2026-11-28, pre-registration in research/studies/RESULTS.md "S1-S5 stage-0 probes").

Pure functions only (no network): counts, fee and depth arithmetic. No rule return and no price after a signal is read here.
Network code lives in research/studies/s15_probe.py.
"""
import math
import re
import statistics

# ---------------------------------------------------------------- shared
def poisson_upper95(n):
    """One-sided 95% upper bound of a Poisson mean given n observed events (exact, bisection)."""
    if n < 0:
        raise ValueError("n < 0")
    lo, hi = 0.0, float(n) + 10.0 * math.sqrt(n + 1) + 10.0
    for _ in range(80):
        mid = (lo + hi) / 2
        cdf, term = 0.0, math.exp(-mid)
        for k in range(n + 1):
            cdf += term
            term *= mid / (k + 1)
        if cdf > 0.05:      # P(X <= n | mid) still above 5%: the mean can be larger
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def top_share(counts, n=4):
    """Share of the total held by the n largest keys of a {key: count} dict (0 when empty)."""
    tot = sum(counts.values())
    if tot <= 0:
        return 0.0
    return sum(sorted(counts.values(), reverse=True)[:n]) / tot


def sd_step(closes, step):
    """Sd of non-overlapping `step`-bar log returns of a close series (None when fewer than 20 returns)."""
    rets = []
    i = 0
    while i + step < len(closes):
        a, b = closes[i], closes[i + step]
        if a > 0 and b > 0:
            rets.append(math.log(b / a))
        i += step
    if len(rets) < 20:
        return None
    return statistics.pstdev(rets)


# ---------------------------------------------------------------- S1 Hyperliquid
HL_WEIGHT_PER_MIN = 1200          # public per-IP limit (docs)
HL_PACE_PER_MIN = 1000            # 83%, what the probe uses
HL_CLEARINGHOUSE_WEIGHT = 2


def refresh_seconds(n_addresses, weight=HL_CLEARINGHOUSE_WEIGHT, pace=HL_PACE_PER_MIN):
    """Seconds to read the state of n addresses at `weight` each when at most `pace` weight a minute is spent."""
    return n_addresses * weight / (pace / 60.0)


def book_walk_cost(levels, notional_usd, mult=1.0):
    """Walk one side of a book. levels = [(price, size)] best first; size in contracts, `mult` units per contract.
    Returns (vwap, filled_usd); vwap None if no level."""
    need, cost, qty = notional_usd, 0.0, 0.0
    for p, s in levels:
        lvl = p * s * mult
        if lvl <= 0:
            continue
        take = min(lvl, need)
        cost += take
        qty += take / p
        need -= take
        if need <= 1e-9:
            break
    if qty <= 0:
        return None, 0.0
    return cost / qty, cost


def book_round_trip(bids, asks, notional_usd, mult=1.0):
    """(vwap_ask - vwap_bid) / mid for a notional walked on both sides; None when a side cannot fill it."""
    va, fa = book_walk_cost(asks, notional_usd, mult)
    vb, fb = book_walk_cost(bids, notional_usd, mult)
    if va is None or vb is None or fa < notional_usd * 0.999 or fb < notional_usd * 0.999:
        return None
    mid = (bids[0][0] + asks[0][0]) / 2
    return (va - vb) / mid


def ladder_clusters(positions, width=0.005):
    """positions = [{coin, side ('long'|'short'), liq (price), notional}] -> clusters per coin and side:
    adjacent liquidation prices within `width` of the cluster's first price are one cluster."""
    out = []
    keyed = {}
    for p in positions:
        if not p.get("liq") or p["liq"] <= 0:
            continue
        keyed.setdefault((p["coin"], p["side"]), []).append(p)
    for (coin, side), ps in keyed.items():
        ps.sort(key=lambda x: x["liq"])
        cur = None
        for p in ps:
            if cur and p["liq"] <= cur["lo"] * (1 + width):
                cur["hi"] = p["liq"]
                cur["notional"] += p["notional"]
                cur["n"] += 1
            else:
                if cur:
                    out.append(cur)
                cur = {"coin": coin, "side": side, "lo": p["liq"], "hi": p["liq"], "notional": p["notional"], "n": 1}
        if cur:
            out.append(cur)
    for c in out:
        c["px"] = (c["lo"] + c["hi"]) / 2
    return out


def depth_to(levels, mid, target, mult=1.0):
    """Visible notional USD between mid and target on one side of the book (levels best first)."""
    tot = 0.0
    for p, s in levels:
        if (target >= mid and p > target) or (target < mid and p < target):
            break
        tot += p * s * mult
    return tot


def approaches(clusters, mids, books, near=0.01, ratio=3.0):
    """Clusters with mid within `near` of the cluster price and notional >= ratio x visible depth to it.
    books = {coin: {"bids": [...], "asks": [...]}} (price, size in coin units)."""
    out = []
    for c in clusters:
        mid = mids.get(c["coin"])
        b = books.get(c["coin"])
        if not mid or not b:
            continue
        if abs(c["px"] / mid - 1) > near:
            continue
        side_levels = b["asks"] if c["px"] > mid else b["bids"]
        d = depth_to(side_levels, mid, c["px"])
        if c["notional"] >= ratio * max(d, 1e-9):
            out.append({**c, "mid": mid, "visible_depth": d})
    return out


# ---------------------------------------------------------------- S2 DEX pool
DEX_FEE = {"uniswap_v2": 0.003, "pancakeswap_v2": 0.0025, "pancakeswap-v2-bsc": 0.0025, "raydium": 0.0025,
           "pumpswap": 0.0025, "pump-fun": 0.01}
DEX_FEE_DEFAULT = 0.003


def pool_fee(name, dex_id=None):
    """Fee fraction: an 'x%' suffix of the pool name, else the DEX table, else 0.30%."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*$", name or "")
    if m:
        return float(m.group(1)) / 100.0
    return DEX_FEE.get((dex_id or "").lower(), DEX_FEE_DEFAULT)


def cp_round_trip(reserve_usd, fee, size_usd=49.0):
    """Constant-product pool with reserve_usd of total value (half quote, half base): buy size_usd of base, sell it all
    back. Fee on each side, kept in the pool. Returns the loss as a fraction of size_usd (None if reserve is unusable)."""
    if not reserve_usd or reserve_usd <= 0:
        return None
    q = b = reserve_usd / 2.0           # both in USD at the pre-trade price
    ein = size_usd * (1 - fee)
    out = b * ein / (q + ein)           # base received (USD at the pre-trade price)
    q1, b1 = q + size_usd, b - out
    eout = out * (1 - fee)
    back = q1 * eout / (b1 + eout)
    return 1.0 - back / size_usd


def new_entrants(polls):
    """polls = [{"t": s, "ids": [pool id...]}] in time order. Returns [{id, first_t, prev_t}] for ids absent from every
    earlier poll; the first poll is the baseline."""
    seen, out = set(), []
    for k, p in enumerate(polls):
        for i in p["ids"]:
            if i not in seen and k > 0:
                out.append({"id": i, "first_t": p["t"], "prev_t": polls[k - 1]["t"]})
            seen.add(i)
    return out


def distinct_sellers(trades, first_t, window=3600):
    """Distinct selling wallets in [first_t - window, first_t]. trades = [{kind, wallet, t}]."""
    return len({x["wallet"] for x in trades if x.get("kind") == "sell" and x.get("wallet")
                and first_t - window <= x["t"] <= first_t})


# ---------------------------------------------------------------- S3 anchored perps
# base name (upper, _USDT/USDT/trailing STOCK removed) -> (underlying Yahoo symbol, class). Locked before the first run.
S3_UNDERLYING = {}
for _s in ("AAPL MSFT NVDA TSLA AMZN GOOGL GOOG META NFLX AMD COIN MSTR PLTR INTC AVGO ORCL CRM ADBE UBER ABNB SHOP PYPL "
           "BABA DIS JPM BAC V MA WMT COST NKE BA XOM CVX PFE KO PEP MCD SBUX HOOD SOFI RIOT MARA CRCL SNOW NIO QCOM MU TSM "
           "SPY QQQ IWM DIA GLD SLV TLT ARKK").split():
    S3_UNDERLYING[_s] = (_s, "stock")
for _s, _y in (("EURUSD", "EURUSD=X"), ("GBPUSD", "GBPUSD=X"), ("USDJPY", "JPY=X"), ("AUDUSD", "AUDUSD=X"),
               ("USDCAD", "CAD=X"), ("USDCHF", "CHF=X"), ("NZDUSD", "NZDUSD=X"), ("EURJPY", "EURJPY=X"), ("GBPJPY", "GBPJPY=X")):
    S3_UNDERLYING[_s] = (_y, "fx")
for _s, _y in (("XAUUSD", "GC=F"), ("GOLD", "GC=F"), ("XAGUSD", "SI=F"), ("SILVER", "SI=F"), ("USOIL", "CL=F"), ("WTI", "CL=F"),
               ("OIL", "CL=F"), ("UKOIL", "BZ=F"), ("BRENT", "BZ=F"), ("NATGAS", "NG=F"), ("COPPER", "HG=F")):
    S3_UNDERLYING[_s] = (_y, "commodity")
for _s, _y in (("SPX", "^GSPC"), ("US500", "^GSPC"), ("SP500", "^GSPC"), ("NAS100", "^NDX"), ("US100", "^NDX"), ("NASDAQ", "^NDX"),
               ("US30", "^DJI"), ("DJI", "^DJI")):
    S3_UNDERLYING[_s] = (_y, "index")
SESSION_CLASSES = ("stock", "index")      # book snapshots are valid only in the US regular session


def norm_base(name):
    """'AAPLSTOCK_USDT' / 'AAPL_USDT' / 'AAPLUSDT' -> 'AAPL'."""
    b = (name or "").upper().strip()
    for suf in ("_USDT", "USDT"):
        if b.endswith(suf):
            b = b[: -len(suf)]
            break
    if b.endswith("STOCK") and len(b) > 5:
        b = b[:-5]
    return b


def pick_s3_universe(perps, n=40):
    """perps = [{venue, name, vol}] -> up to n unique underlyings by venue-reported 24h quote volume, a symbol on both
    venues kept once at its larger-volume venue. Returns [{venue, name, base, yahoo, cls, vol}]."""
    best = {}
    for p in perps:
        b = norm_base(p["name"])
        if b not in S3_UNDERLYING:
            continue
        if b not in best or (p.get("vol") or 0) > (best[b].get("vol") or 0):
            best[b] = {**p, "base": b, "yahoo": S3_UNDERLYING[b][0], "cls": S3_UNDERLYING[b][1]}
    rows = sorted(best.values(), key=lambda r: -(r.get("vol") or 0))
    # one row per Yahoo underlying (GOLD and XAUUSD are the same)
    seen, out = set(), []
    for r in rows:
        if r["yahoo"] in seen:
            continue
        seen.add(r["yahoo"])
        out.append(r)
    return out[:n]


def gap_series(perp, under):
    """perp, under = {t: close}; -> sorted [(t, perp/under - 1)] at identical timestamps."""
    return [(t, perp[t] / under[t] - 1.0) for t in sorted(perp) if t in under and under[t] > 0 and perp[t] > 0]


def episodes(series, thr, min_len=2, step=300):
    """Maximal runs of >= min_len consecutive bars (t spaced `step`) with |value| >= thr. series = [(t, v)]. Returns [(t0, t1)]."""
    out, run = [], []
    for t, v in series:
        if abs(v) >= thr and (not run or t - run[-1] == step):
            run.append(t)
            continue
        if len(run) >= min_len:
            out.append((run[0], run[-1]))
        run = [t] if abs(v) >= thr else []
    if len(run) >= min_len:
        out.append((run[0], run[-1]))
    return out


def same_sign_days(series, frac=0.9):
    """-> (n_days, n_same_sign_days) by UTC date; a day is same-sign when >= frac of its bars share a sign (min 12 bars)."""
    days = {}
    for t, v in series:
        days.setdefault(int(t // 86400), []).append(v)
    n = same = 0
    for vs in days.values():
        if len(vs) < 12:
            continue
        n += 1
        pos = sum(1 for v in vs if v > 0)
        neg = sum(1 for v in vs if v < 0)
        if max(pos, neg) / len(vs) >= frac:
            same += 1
    return n, same


def month_scale(first_t, last_t):
    """30.44-day month divided by the span covered (>= 1 day)."""
    span = max((last_t - first_t) / 86400.0, 1.0)
    return 30.44 / span


# ---------------------------------------------------------------- S4 Kalshi x Polymarket
ASSETS = {"bitcoin": "BTC", "btc": "BTC", "ethereum": "ETH", "eth": "ETH", "ether": "ETH", "solana": "SOL", "sol": "SOL",
          "xrp": "XRP", "dogecoin": "DOGE", "doge": "DOGE"}
CITIES = ("new york", "chicago", "los angeles", "miami", "austin", "denver", "philadelphia", "houston", "phoenix", "seattle",
          "boston", "atlanta", "dallas", "san francisco", "washington", "las vegas", "minneapolis")
ECON = {"cpi": "CPI", "inflation": "CPI", "payroll": "NFP", "nonfarm": "NFP", "unemployment": "UNRATE", "jobless": "CLAIMS",
        "fomc": "FED", "fed ": "FED", "gdp": "GDP"}
SOURCES = (("cf benchmarks", "cfb"), ("coinbase", "coinbase"), ("binance", "binance"), ("kraken", "kraken"),
           ("national weather service", "nws"), ("noaa", "nws"), ("nws", "nws"), ("bureau of labor", "bls"), ("bls", "bls"),
           ("bureau of economic analysis", "bea"), ("federal reserve", "fed"), ("espn", "espn"), ("associated press", "ap"),
           ("official league", "league"), ("nfl.com", "league"), ("nba.com", "league"))


def parse_number(txt):
    """'$100,000' -> 100000.0; '96k' -> 96000.0; None if absent."""
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\s*([kKmM])?", txt or "")
    if not m:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*°", txt or "")
        if not m:
            return None
        return float(m.group(1))
    v = float(m.group(1).replace(",", ""))
    if m.group(2):
        v *= 1000.0 if m.group(2) in "kK" else 1e6
    return v


def direction_of(txt, strike_type=None):
    if strike_type:
        s = strike_type.lower()
        if s.startswith("greater"):
            return "above"
        if s.startswith("less"):
            return "below"
        return None
    t = (txt or "").lower()
    if re.search(r"\b(above|over|higher|at least|or more|greater|exceed)\b", t):
        return "above"
    if re.search(r"\b(below|under|lower|at most|or less|less than)\b", t):
        return "below"
    return None


def features(title, strike=None, strike_type=None):
    """Locked classifier -> {cat, entity, level, direction} or None when no category applies."""
    t = (title or "").lower()
    lvl = strike if strike is not None else parse_number(title)
    d = direction_of(title, strike_type)
    for k, v in ASSETS.items():
        if re.search(r"\b%s\b" % re.escape(k), t) and lvl is not None and d:
            return {"cat": "crypto", "entity": v, "level": float(lvl), "direction": d}
    if "temperature" in t or "high temp" in t or "highest temp" in t:
        for c in CITIES:
            if c in t and lvl is not None and d:
                return {"cat": "weather", "entity": c, "level": float(lvl), "direction": d}
    for k, v in ECON.items():
        if k in t + " " and lvl is not None and d:
            return {"cat": "econ", "entity": v, "level": float(lvl), "direction": d}
    return None


def pair_match(a, b, close_a, close_b, tol=3600):
    """a, b = features dicts; close_* epoch seconds. Locked rule: same cat, entity, level, direction, close within tol."""
    if not a or not b:
        return False
    return (a["cat"] == b["cat"] and a["entity"] == b["entity"] and a["direction"] == b["direction"]
            and abs(a["level"] - b["level"]) <= 1e-9 * max(1.0, abs(a["level"])) and abs(close_a - close_b) <= tol)


def sources_of(text):
    t = (text or "").lower()
    return frozenset(v for k, v in SOURCES if k in t)


def source_mismatch(a, b):
    """True only when both name a source and the sets differ."""
    return bool(a) and bool(b) and a != b


def kalshi_fee(contracts, price, mult=1.0):
    """Taker fee USD: ceil to the cent of 0.07 x mult x C x P (1 - P)."""
    return math.ceil(round(0.07 * mult * contracts * price * (1 - price) * 100, 9)) / 100.0


def lock_net(price_a, price_b, fee_a, fee_b, contracts):
    """Net USD locked by paying price_a and price_b (0..1 per contract, payoff 1 USD for the pair) plus fees."""
    return contracts * (1.0 - price_a - price_b) - fee_a - fee_b


def allocate(pairs, capital=147.0, per_pair=20.0):
    """pairs = [{net_usd, cost_usd, days}] (net lock and capital tied for one 20 USD pair). Greedy by net per capital per day,
    each pair used once. Returns daily yield on capital (fraction)."""
    ranked = sorted(pairs, key=lambda p: -(p["net_usd"] / p["cost_usd"] / max(p["days"], 0.25)) if p["cost_usd"] > 0 else 0)
    left, tot = capital, 0.0
    for p in ranked:
        if p["cost_usd"] <= 0 or p["net_usd"] <= 0:
            continue
        take = min(p["cost_usd"], left)
        if take <= 0:
            break
        tot += p["net_usd"] * take / p["cost_usd"] / max(p["days"], 0.25)
        left -= take
    return tot / capital


# ---------------------------------------------------------------- S5 stale quote, bar arm
def bar_gap_events(a, b, vol_a, vol_b, thr=0.015, merge_s=300):
    """a, b = {t: close} of the two venues on 1-minute bars; vol_* = {t: volume}. A minute counts when
    |ln(a/b)| >= thr and both venues traded (volume > 0). Event = maximal run of >= 2 consecutive minutes; events closer
    than merge_s merge. Returns [(t0, t1)]."""
    ok = []
    for t in sorted(a):
        if t in b and a[t] > 0 and b[t] > 0 and vol_a.get(t, 0) > 0 and vol_b.get(t, 0) > 0 and abs(math.log(a[t] / b[t])) >= thr:
            ok.append((t, 1.0))
        else:
            ok.append((t, 0.0))
    ev = episodes([(t, v) for t, v in ok], 1.0, 2, 60)
    merged = []
    for e in ev:
        if merged and e[0] - merged[-1][1] < merge_s:
            merged[-1] = (merged[-1][0], e[1])
        else:
            merged.append(e)
    return merged


def median_abs_log_gap(a, b):
    xs = [abs(math.log(a[t] / b[t])) for t in a if t in b and a[t] > 0 and b[t] > 0]
    return statistics.median(xs) if xs else None
