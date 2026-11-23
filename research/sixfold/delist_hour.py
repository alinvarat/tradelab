"""Replay early Bybit spot recovery after a timestamped removal announcement."""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import mean

from .delist_delayed import STOP
from .delist_rebound import FRESH
from .delist_rebound_articles import CATALOG
from .delisting import fetch
from .spot import BASE_COST, HERE, STRESS_COST

HOUR = 3_600_000
WEEK = 168 * HOUR
INPUT = HERE / "delist_hour_inputs.json.gz"
RESULT = HERE / "delist_hour_results.json"


def utc(x):
    return datetime.fromtimestamp(x / 1000, timezone.utc)


def quote(job):
    symbol, entry, stop = job
    args = {"category": "spot", "symbol": symbol + "USDT", "interval": "60",
            "start": entry - WEEK - 4 * HOUR, "end": entry + 6 * HOUR - 1, "limit": 200}
    try:
        rows = fetch("/v5/market/kline", **args)["list"]
    except (OSError, ValueError) as exc:
        return symbol, {}, str(exc)
    return symbol, {int(t): [float(o), float(c)] for t, o, _, _, c, v, _ in rows if float(v) > 0}, None


def acquire():
    catalog = json.loads(CATALOG.read_bytes())
    raw = gzip.decompress(FRESH.read_bytes())
    articles = json.loads(raw)["archive"]
    output = []
    with ThreadPoolExecutor(6) as pool:
        for row in catalog["accepted"]:
            url = row["url"]
            published = articles[url]["publishTime"]
            stop = next(v for k,v in STOP.items() if k in url)
            entry = (published // HOUR + 2) * HOUR
            prices = list(pool.map(quote, ((s, entry, stop) for s in row["symbols"])))
            output.append({"url": url, "published": published, "entry": entry, "stop": stop, "prices": prices})
    INPUT.write_bytes(gzip.compress(json.dumps(output).encode(), mtime=0))


def simulate(data, fee):
    counts = Counter()
    by_time = defaultdict(list)
    factor = (1 - fee) / (1 + fee)
    for event in data:
        entry, stop = event["entry"], event["stop"]
        for symbol, quotes, failure in event["prices"]:
            counts["listed_pairs"] += 1
            bars = {int(t): row for t,row in quotes.items()}
            if failure or any(t not in bars for t in (entry-3*HOUR, entry-HOUR)):
                counts["missing_signal"] += 1
                continue
            counts["observed_signal"] += 1
            change = bars[entry-HOUR][1] / bars[entry-3*HOUR][1] - 1
            if change > -.10:
                continue
            if utc(entry+6*HOUR-1).date().isoformat() >= stop or utc(entry).month != utc(entry+6*HOUR-1).month:
                counts["crosses_stop_boundary"] += 1
                continue
            by_time[entry].append((symbol, change, bars))
    balance, next_free, peak, dd = 5000., 0, 5000., 0.
    events = []
    months = dict.fromkeys((f"2026-{m:02d}" for m in range(1, 11)), 1.)
    paired = []
    for entry, candidates in sorted(by_time.items()):
        if entry < next_free:
            counts["overlap_skips"] += len(candidates)
            continue
        def fill(bars, t):
            if t not in bars:
                return None
            if any(t + i*HOUR not in bars for i in range(1, 6)):
                return 0.
            return bars[t+5*HOUR][1] / bars[t][0] * factor
        legs = []
        for symbol, change, bars in candidates:
            growth, prior = fill(bars, entry), fill(bars, entry-WEEK)
            legs.append([symbol, change, growth, prior])
            if growth is not None and prior is not None:
                paired.append((growth, prior))
        if any(x[2] is not None for x in legs):
            next_free = entry + 6*HOUR
        growth = mean(x[2] if x[2] is not None else 1 for x in legs)
        balance *= growth
        peak = max(balance, peak)
        dd = max(dd, 1-balance/peak)
        months[utc(entry).strftime("%Y-%m")] *= growth
        events.append({"entry": utc(entry).isoformat(), "legs": legs, "multiple": growth})
    return {"coverage": counts, "events": events, "ending_thb": balance, "drawdown_trade_closes": dd,
            "months": months, "3x_months": sum(x >= 3 for x in months.values()),
            "6x_months": sum(x >= 6 for x in months.values()), "paired": len(paired),
            "mean_actual_net": mean(x-1 for x,_ in paired) if paired else None,
            "mean_control_net": mean(x-1 for _,x in paired) if paired else None}


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    data = json.loads(raw)
    out = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(),
           "cases": {name: simulate(data, fee) for name,fee in (("base",BASE_COST),("stress",STRESS_COST))}}
    RESULT.write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
