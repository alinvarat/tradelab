"""Read fresh Kalshi quotes on fixed dates and replay the frozen weather rule."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from statistics import NormalDist, median

from .f1_winner import parse_unsuffixed
from .tail import (API, CENT, ROOT, SERIES, SNAPSHOT, TEMP, boundary, candidate_probability,
                   get, market_day, unix)
from .tail_daily import prepare, simulate
from .tail_forecast_2026 import INPUT as WEATHER

INPUT = ROOT / "tail_market_2026_inputs.json.gz"
RESULT = ROOT / "tail_market_2026_results.json"
DAYS = {date(2026, month, day) for month in range(1, 11) for day in (1, 15)}


def markets():
    output = defaultdict(dict)
    for historical in (True, False):
        cursor = None
        while True:
            args = {"series_ticker": SERIES, "limit": 1000}
            if cursor:
                args["cursor"] = cursor
            page = get(API, "/historical/markets" if historical else "/markets", **args)
            cursor = page["cursor"]
            dated = [(market_day(row["event_ticker"]), row) for row in page["markets"]]
            for day, row in dated:
                if day in DAYS and row["result"] in ("yes", "no"):
                    output[day][row["ticker"]] = (historical, row)
            if not cursor or (dated and max(day for day, _ in dated) < min(DAYS)):
                break
    return output


def quote(job):
    day, historical, row, probability = job
    t, ticker = boundary(day), row["ticker"]
    route = (f"/historical/markets/{ticker}/candlesticks" if historical else
             f"/series/{SERIES}/markets/{ticker}/candlesticks")
    candles = {}
    if unix(row["open_time"]) <= t < unix(row["close_time"]):
        data = get(API, route, start_ts=t-3600, end_ts=t+3600, period_interval=60)
        candles = {x["end_period_ts"]: x for x in (data or {}).get("candlesticks", [])}

    def fields(stamp, which):
        candle = candles.get(stamp, {})
        asks = candle.get("yes_ask") or {}
        value = asks.get(which + "_dollars")
        if value is None:
            value = parse_unsuffixed(asks.get(which))
        return str(value) if value is not None else None, float(candle.get("volume_fp", candle.get("volume", 0)))

    signal, sv = fields(t, "close")
    entry, ev = fields(t+3600, "open")
    return day.isoformat(), {"ticker": ticker, "probability": probability, "result": row["result"],
                             "settlement_ts": row.get("settlement_ts"), "ask_signal": signal,
                             "ask_entry": entry, "volume_signal": sv, "volume_entry": ev,
                             "historical_endpoint": historical}


def acquire():
    weather = gzip.decompress(WEATHER.read_bytes())
    forecasts = json.loads(weather)["rows"]
    fit = json.loads(gzip.decompress(SNAPSHOT.read_bytes()))["fit"]
    catalog = markets()
    output = {}
    jobs = []
    for day in sorted(DAYS):
        iso = day.isoformat()
        high = forecasts[iso]["forecast"][TEMP]
        output[iso] = {"markets": len(catalog[day]), "forecast_high_f": high, "candidates": []}
        if high is None:
            continue
        normal = NormalDist(high + fit["mean_error_f"], fit["sd_error_f"])
        for _, (historical, row) in sorted(catalog[day].items()):
            prob = candidate_probability(row, normal)
            if prob is not None and prob >= .12:
                jobs.append((day, historical, row, prob))
    print(f"{len(jobs)} quotes on {len(output)} dates", flush=True)
    with ThreadPoolExecutor(6) as pool:
        for iso, candidate in pool.map(quote, jobs):
            output[iso]["candidates"].append(candidate)
    snapshot = {"days": output, "weather_sha256": hashlib.sha256(weather).hexdigest()}
    INPUT.write_bytes(gzip.compress(json.dumps(snapshot).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    snapshot = json.loads(raw)
    days = snapshot["days"]
    plan = prepare(days)
    months = [f"2026-{m:02d}" for m in range(1,11)]
    quotes = [q for day in days.values() for q in day["candidates"]]
    output = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "sampled_days": len(days),
              "market_days": sum(x["markets"] > 0 for x in days.values()),
              "quotes": len(quotes), "quote_pairs": sum(q["ask_signal"] is not None and
              q["ask_entry"] is not None for q in quotes), "decision_days": sum(map(len, plan.values())),
              "cases": {}}
    for label, slip in (("base", CENT), ("stress", 2*CENT)):
        actual = simulate(plan, months, slip, details=True)
        rng = random.Random(88001)
        draws = [simulate(plan, months, slip, rng)["ending_usd"] for _ in range(1000)]
        actual["random_median_usd"] = median(draws)
        output["cases"][label] = actual
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
