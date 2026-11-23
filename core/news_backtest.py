"""Point-in-time event study: a filing timestamp -> the first session open after it, a fixed hold, costs,
and a random same-class control bought at the same moment.

The point is to test whether an event still pays after cost, not to fit a strategy. No model sees the
outcome in advance; every timestamp is the one the source published (SEC acceptanceDateTime).
"""
import calendar
import json
import math
import os
import random
import time
import urllib.request

HORIZONS = (1, 3, 5)
FEE_PCT, SLIP_PCT = 0.0005, 0.0002          # the engine's assumptions, per side
SPREAD_PCT = {"stock": 0.0004, "etf": 0.0003, "commodity": 0.0003, "fx": 0.0001, "crypto": 0.0005}
SPLITS = (("train", "2022-12-31"), ("validation", "2024-12-31"), ("test", "2100-01-01"))


def cost_per_side(asset_class: str = "stock") -> float:
    return FEE_PCT + SLIP_PCT + SPREAD_PCT.get(asset_class, 0.0004) / 2


def net_return(gross: float, asset_class: str = "stock", cost_mult: float = 1.0) -> float:
    """Both sides pay fee, slippage and half the spread; cost_mult=2 is the protocol's 2x cost check."""
    c = cost_per_side(asset_class) * cost_mult
    return (1 + gross) * (1 - c) ** 2 - 1


def split_of(ts: int) -> str:
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    for name, last in SPLITS:
        if day <= last:
            return name
    return "test"


def event_return(bars: list, accepted_ts: int, horizon: int) -> dict | None:
    """Enter at the open of the first session that starts at/after the acceptance stamp, exit at the close
    of the horizon-th session. A filing accepted mid-session therefore waits for the next open (conservative).
    Returns None when the data does not cover the window."""
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    i = None
    for k, b in enumerate(bars):
        if b["t"] >= accepted_ts:
            i = k
            break
    if i is None or i + horizon - 1 >= len(bars):
        return None
    enter, exit_ = bars[i].get("o"), bars[i + horizon - 1].get("c")
    if not enter or not exit_:
        return None
    return {"entry_t": bars[i]["t"], "exit_t": bars[i + horizon - 1]["t"], "gross": exit_ / enter - 1}


def pick_control(symbol: str, asset_class: str, pool: dict, rng: random.Random):
    """Random other symbol of the same class that has bars. Deterministic for a given rng state."""
    from .universe import asset_class as class_of
    cands = sorted(s for s, cls in ((s, class_of(s)) for s in pool) if s != symbol and cls == asset_class)
    return cands[rng.randrange(len(cands))] if cands else None


def bootstrap_p(values: list, rng: random.Random, n: int = 2000) -> float:
    """One-sided p that the mean is <= 0 (resampling with replacement)."""
    if not values:
        return 1.0
    means = []
    k = len(values)
    for _ in range(n):
        means.append(sum(values[rng.randrange(k)] for _ in range(k)) / k)
    return (1 + sum(1 for m in means if m <= 0)) / (n + 1)


def cluster_key(row: dict) -> str:
    """Filings of one firm in one calendar month move together (same news, same regime), so they are
    resampled as one block. Rows without a timestamp fall back to their own block."""
    ts = row.get("ts")
    month = time.strftime("%Y-%m", time.gmtime(ts)) if ts is not None else str(id(row))
    return f"{row.get('symbol', '?')}:{month}"


def block_bootstrap_p(values: list, keys: list, rng: random.Random, n: int = 2000) -> float:
    """One-sided p that the mean is <= 0, resampling whole clusters (symbol-month) with replacement.
    Wider than bootstrap_p when observations inside a cluster are correlated."""
    if not values:
        return 1.0
    blocks: dict = {}
    for v, k in zip(values, keys):
        b = blocks.setdefault(k, [0.0, 0])
        b[0] += v
        b[1] += 1
    sums = [b[0] for b in blocks.values()]
    counts = [b[1] for b in blocks.values()]
    m = len(sums)
    hits = 0
    for _ in range(n):
        tot = cnt = 0
        for _ in range(m):
            j = rng.randrange(m)
            tot += sums[j]
            cnt += counts[j]
        if tot / cnt <= 0:
            hits += 1
    return (1 + hits) / (n + 1)


def summarize(rows: list, rng: random.Random | None = None, cost_mult: float = 1.0) -> dict:
    """rows: [{'gross','ctrl_gross','asset_class', optional 'symbol','ts'}] -> gross and net means, paired
    difference, iid bootstrap p and symbol-month block bootstrap p."""
    rng = rng or random.Random(20261124)
    if not rows:
        return {"n": 0}
    net = [net_return(r["gross"], r.get("asset_class", "stock"), cost_mult) for r in rows]
    ctrl = [net_return(r["ctrl_gross"], r.get("asset_class", "stock"), cost_mult) for r in rows]
    diff = [a - b for a, b in zip(net, ctrl)]
    keys = [cluster_key(r) for r in rows]
    k = len(rows)
    return {"n": k, "clusters": len(set(keys)), "cost_mult": cost_mult,
            "mean_gross": sum(r["gross"] for r in rows) / k,
            "mean_ctrl_gross": sum(r["ctrl_gross"] for r in rows) / k,
            "mean_net": sum(net) / k, "mean_ctrl": sum(ctrl) / k,
            "mean_diff": sum(diff) / k, "hit": sum(1 for x in net if x > 0) / k,
            "p_mean": bootstrap_p(net, rng), "p_diff": bootstrap_p(diff, rng),
            "p_mean_block": block_bootstrap_p(net, keys, rng), "p_diff_block": block_bootstrap_p(diff, keys, rng)}


def contributions(rows: list, cost_mult: float = 1.0, key=None) -> list:
    """Per symbol (or per key(row), e.g. month): events, summed net and summed paired difference (net minus
    control), largest |sum| first. Shows whether one firm or one month carries the pooled mean."""
    key = key or (lambda r: r.get("symbol", "?"))
    agg: dict = {}
    for r in rows:
        cls = r.get("asset_class", "stock")
        g = key(r)
        a = agg.setdefault(g, {"symbol": g, "n": 0, "sum_net": 0.0, "sum_diff": 0.0})
        net = net_return(r["gross"], cls, cost_mult)
        a["n"] += 1
        a["sum_net"] += net
        a["sum_diff"] += net - net_return(r["ctrl_gross"], cls, cost_mult)
    total = sum(a["sum_diff"] for a in agg.values())
    for a in agg.values():
        a["mean_diff"] = a["sum_diff"] / a["n"]
        a["share_of_total_diff"] = a["sum_diff"] / total if total else None
    return sorted(agg.values(), key=lambda a: -abs(a["sum_diff"]))


# ---------------------------------------------------------------- data sources (network, not used in tests)
# SEC wants a contact in the User-Agent; set TRADELAB_SEC_UA="<name> <contact email>" before a network run.
# The generic fallback keeps contact details out of the repo and may get HTTP 403 from SEC.
SEC_UA = os.environ.get("TRADELAB_SEC_UA", "TradeLab paper research")
_sec_cache: dict = {}


def _sec_json(url: str):
    now = time.time()
    hit = _sec_cache.get(url)
    if hit and now - hit[0] < 86400:
        return hit[1]
    req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    _sec_cache[url] = (now, body)
    time.sleep(0.15)                     # SEC asks for <= 10 requests/second
    return body


def sec_company_tickers() -> dict:
    """{TICKER: cik} from the SEC's own ticker map."""
    d = _sec_json("https://www.sec.gov/files/company_tickers.json")
    return {str(v["ticker"]).upper(): int(v["cik_str"]) for v in d.values()}


def sec_filings(cik: int, forms=("8-K",), since: str | None = None) -> list:
    """Recent filings with the SEC acceptance timestamp (UTC seconds). Only the forms requested."""
    d = _sec_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    recent = (d.get("filings") or {}).get("recent") or {}
    out = []
    forms_l = recent.get("form", [])
    items_l = recent.get("items") or [""] * len(forms_l)
    for form, acc, date, doc, items, accno in zip(forms_l, recent.get("acceptanceDateTime", []),
                                                  recent.get("filingDate", []), recent.get("primaryDocument", []),
                                                  items_l, recent.get("accessionNumber") or [""] * len(forms_l)):
        if form not in forms or not acc:
            continue
        if since and date < since:
            continue
        out.append({"form": form, "accepted": acc, "date": date, "doc": doc, "accession": accno,
                    "items": [x.strip() for x in (items or "").split(",") if x.strip()],
                    "ts": calendar.timegm(time.strptime(acc.replace("Z", "")[:19], "%Y-%m-%dT%H:%M:%S"))})
    return out
