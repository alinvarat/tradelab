"""Paper test. Run: python3 -m research.sixfold.tail [--refresh]."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, time as clock, timedelta
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from threading import Lock
from urllib.error import HTTPError
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from core.data import get_json

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "tail_inputs.json.gz"
RESULT = ROOT / "tail_results.json"
QUOTES = ROOT / "tail_quotes_checkpoint.jsonl"
QUOTE_START_LOCK = Lock()
NEXT_QUOTE_START = 0.0
NOAA = ROOT.parent / "world_signals/weather_noaa_daily.csv"
API = "https://external-api.kalshi.com/trade-api/v2"
RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"
SERIES = "KXHIGHNY"
TEMP = "temperature_2m_previous_day2"
NEW_YORK = ZoneInfo("America/New_York")
START = date(2024, 1, 1)
END = date(2025, 12, 31)
STAKE = Decimal("147")
TAKER = Decimal("0.07")
CENT = Decimal("0.01")
MAX_ASK = Decimal("0.15")


def get(base, path="", **params):
    url = base + path + ("?" + urlencode(params) if params else "")
    for attempt in range(6):
        if path.endswith("/candlesticks"):
            throttle_quote()
        try:
            return get_json(url)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
            if exc.code == 429:
                pause = exc.headers.get("Retry-After")
                delay_quote(float(pause) if pause and pause.isdigit() else 5)
        except (OSError, TimeoutError):
            if attempt == 5:
                raise
        time.sleep(1 + 1.5 * attempt)
    raise AssertionError("unreachable")


def throttle_quote():
    global NEXT_QUOTE_START
    while True:
        with QUOTE_START_LOCK:
            now = time.monotonic()
            wait = NEXT_QUOTE_START - now
            if wait <= 0:
                # A historical quote costs 50 tokens and public headers here show
                # about 0.25s to replenish one request.
                NEXT_QUOTE_START = now + .27
                return
        time.sleep(wait)


def delay_quote(seconds):
    global NEXT_QUOTE_START
    with QUOTE_START_LOCK:
        NEXT_QUOTE_START = max(NEXT_QUOTE_START, time.monotonic() + seconds)


def choose_dates(start, last):
    for i in range((last - start).days + 1):
        yield start + timedelta(days=i)


def load_forecast():
    start = date(2022, 1, 1)
    values = {}
    urls = []
    for year in range(start.year, END.year + 1):
        query = dict(latitude=40.779, longitude=-73.969, timezone="GMT",
                     start_date=f"{year}-01-01",
                     end_date=f"{year}-12-31" if year != END.year else "2026-01-01",
                     hourly=TEMP, temperature_unit="fahrenheit", models="gfs_global")
        response = get(RUNS, **query)
        urls.append(RUNS + "?" + urlencode(query))
        data = response["hourly"]
        values.update(zip(data["time"], data[TEMP]))
    highs = {}
    for day in choose_dates(start, END):
        first_hour = datetime.combine(day, clock(5), UTC)
        temps = [values.get((first_hour + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M"))
                 for i in range(24)]
        if all(t is not None for t in temps):
            highs[day] = max(temps)
    errors = []
    with NOAA.open() as f:
        for row in csv.DictReader(f):
            if row["STATION"] != "USW00094728" or not row["TMAX"]:
                continue
            day = date.fromisoformat(row["DATE"])
            if start <= day < START and day in highs and not row["TMAX_ATTRIBUTES"].split(",")[1]:
                errors.append(float(row["TMAX"]) - highs[day])
    if len(errors) < 657:
        raise ValueError(f"Only {len(errors)} days for forecast calibration")
    return highs, {"mean_error_f": statistics.mean(errors), "sd_error_f": statistics.stdev(errors),
                   "fit_days": len(errors), "source_urls": urls,
                   "noaa_sha256": hashlib.sha256(NOAA.read_bytes()).hexdigest()}


def market_day(ticker):
    return datetime.strptime(ticker.rsplit("-", 1)[-1], "%y%b%d").date()


def load_markets():
    fields = ("ticker", "open_time", "close_time", "settlement_ts", "floor_strike", "cap_strike",
              "strike_type", "result", "rules_primary")
    by_day = defaultdict(list)
    cursor = ""
    while True:
        args = {"limit": 1000, "series_ticker": SERIES}
        if cursor:
            args["cursor"] = cursor
        response = get(API, "/historical/markets", **args)
        cursor = response["cursor"]
        days = []
        for row in response["markets"]:
            event = row["event_ticker"]
            if not event.startswith((f"{SERIES}-", "HIGHNY-")):
                raise ValueError(f"Unrecognized event ticker in {SERIES} catalog: {event}")
            day = market_day(event)
            days.append(day)
            if START <= day <= END:
                by_day[day].append({k: row.get(k) for k in fields})
        if not cursor or (days and max(days) < START):
            break
    return by_day


def unix(iso):
    return int(datetime.fromisoformat(iso).timestamp())


def boundary(day):
    return int(datetime.combine(day, clock(8), NEW_YORK).timestamp())


def candidate_probability(market, normal):
    if market["strike_type"] == "less":
        return normal.cdf(market["cap_strike"] - 0.5)
    if market["strike_type"] == "greater":
        return 1 - normal.cdf(market["floor_strike"] + 0.5)
    if market["strike_type"] == "between":
        return normal.cdf(market["cap_strike"] + 0.5) - normal.cdf(market["floor_strike"] - 0.5)
    return None


def get_quotes(datum):
    day, market = datum
    cutoff = boundary(day)
    if not unix(market["open_time"]) <= cutoff < unix(market["close_time"]):
        return market | {"ask_signal": None, "ask_entry": None, "volume_signal": 0, "volume_entry": 0}
    data = get(API, f"/historical/markets/{market['ticker']}/candlesticks",
               start_ts=cutoff - 3600, end_ts=cutoff + 3600, period_interval=60)
    candles = {x["end_period_ts"]: x for x in (data or {}).get("candlesticks", [])}
    signal, entry = candles.get(cutoff, {}), candles.get(cutoff + 3600, {})
    return market | {"ask_signal": signal.get("yes_ask", {}).get("close"),
                     "ask_entry": entry.get("yes_ask", {}).get("open"),
                     "volume_signal": float(signal.get("volume", 0)),
                     "volume_entry": float(entry.get("volume", 0))}


def download(refresh=False):
    highs, fit = load_forecast()
    markets = load_markets()
    days = {}
    asks = []
    for day in choose_dates(START, END):
        rows = markets.get(day, [])
        high = highs.get(day)
        normal = statistics.NormalDist(high + fit["mean_error_f"], fit["sd_error_f"]) if high is not None else None
        days[day.isoformat()] = {"markets": len(rows), "forecast_high_f": high, "candidates": []}
        for market in rows:
            prob = candidate_probability(market, normal) if normal else None
            if prob is not None and prob >= 0.12:
                asks.append((day, market | {"probability": prob}))
    expected = {row["ticker"]: day for day, row in asks}
    if len(expected) != len(asks):
        raise ValueError("Duplicate quote ticker in archive")
    checkpoint = {}
    if QUOTES.exists() and not refresh:
        with QUOTES.open() as file:
            checkpoint = {row["ticker"]: row for line in file if (row := json.loads(line))["ticker"] in expected}
    remaining = [(day, row) for day, row in asks if row["ticker"] not in checkpoint]
    # Round-robin across calendar months so a partial diagnostic has time coverage.
    remaining.sort(key=lambda item: ((item[0].day - 1) % 4, item[0].day, item[0].year, item[0].month))
    print(f"Forecast fit {fit['fit_days']} days; {len(markets)} event days; {len(asks)} markout queries; "
          f"{len(checkpoint)} available locally", flush=True)
    errors = []
    with QUOTES.open("w" if refresh else "a") as cache, ThreadPoolExecutor(max_workers=8) as pool:
        tasks = {pool.submit(get_quotes, item): item for item in remaining}
        for future in as_completed(tasks):
            ticker = tasks[future][1]["ticker"]
            try:
                row = future.result()
            except (OSError, TimeoutError) as error:
                errors.append((ticker, str(error)))
                continue
            checkpoint[ticker] = row
            cache.write(json.dumps(row, sort_keys=True) + "\n")
            cache.flush()
            if not len(checkpoint) % 250:
                print(f"Quotes {len(checkpoint)}/{len(asks)}", flush=True)
    if errors:
        raise RuntimeError(f"{len(errors)} transient query failures; rerun to continue from checkpoint: {errors[:5]}")
    for day, market in asks:
        days[day.isoformat()]["candidates"].append(checkpoint[market["ticker"]])
    payload = {"fit": fit, "days": days, "kalshi_endpoint": API, "archive_series": SERIES}
    SNAPSHOT.write_bytes(gzip.compress(json.dumps(payload, sort_keys=True).encode(), mtime=0))
    return payload


def signal_entry(market):
    value = market["ask_signal"]
    if value is None:
        return None
    price = Decimal(value)
    if not 0 < price <= MAX_ASK:
        return None
    fill = price + CENT
    break_even = fill + TAKER * fill * (1 - fill)
    return market["probability"] - float(break_even)


def quantity(price):
    fee_per = TAKER * price * (1 - price)
    size = int(STAKE // (price + fee_per))
    while size:
        fee = (size * fee_per).quantize(CENT, rounding=ROUND_CEILING)
        cost = price * size + fee
        if cost <= STAKE:
            return size, fee, cost
        size -= 1
    return 0, Decimal(0), Decimal(0)


def simulate_fill(row, day, slip):
    if row["ask_entry"] is None or not (row["volume_signal"] or row["volume_entry"]):
        return None
    ask = Decimal(row["ask_entry"])
    if not 0 < ask <= MAX_ASK:
        return None
    price = ask + slip
    size, fee, cost = quantity(price)
    if not size or cost * 6 > size:
        return None
    if row["result"] not in ("yes", "no") or not row["settlement_ts"]:
        return None
    settled = datetime.fromisoformat(row["settlement_ts"]).astimezone(NEW_YORK)
    if settled.timestamp() <= boundary(day):
        return None
    yes = row["result"] == "yes"
    ending = STAKE - cost + (size if yes else 0)
    return {"ticker": row["ticker"], "event_day": day.isoformat(), "won": yes,
            "contracts": size, "observed_entry_ask": float(ask), "fill_price": float(price),
            "volume_signal_hour": row["volume_signal"], "volume_entry_hour": row["volume_entry"],
            "model_prob": row["probability"], "fee_usd": float(fee),
            "cost_usd": float(cost), "settled_at": settled.isoformat(),
            "same_month_as_entry": (settled.year, settled.month) == (day.year, day.month),
            "ending_multiple": float(ending / STAKE)}


def years_summary(entries, random_eligible, year):
    months = [f"{year}-{month:02d}" for month in range(1, 13)]
    picks = {m: entries.get(m) for m in months}
    filled = [v for v in picks.values() if v]
    credited = [v for v in filled if v["same_month_as_entry"]]
    hits = sum(r["ending_multiple"] >= 6 for r in credited)
    severe = sum(r["ending_multiple"] <= .5 for r in credited)
    avg = [v["ending_multiple"] if v else 1.0 for v in picks.values() if v is None or v["same_month_as_entry"]]
    n = len(months)
    z = 1.959963984540054
    phat = hits / n
    den = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / den
    error = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / den

    def hit(row):
        return row["same_month_as_entry"] and row["ending_multiple"] >= 6

    rng = random.Random(602325)
    pools = [random_eligible[m] for m, v in picks.items() if v]
    draws = [sum(hit(rng.choice(pool)) for pool in pools) for _ in range(5000)]
    p = (sum(x >= hits for x in draws) + 1) / (len(draws) + 1)
    return {"months": n, "selected_entries": len(filled), "no_trade_months": n - len(filled),
            "carried_past_month": len(filled) - len(credited), "months_6x": hits,
            "months_half_loss": severe, "mean_ending_multiple": statistics.mean(avg),
            "median_ending_multiple": statistics.median(avg), "payouts_on_wins": [r["ending_multiple"] for r in filled if r["won"]],
            "months_6x_ci_95_wilson": [max(0, center - error), min(1, center + error)],
            "random_draws": len(draws), "random_candidates_in_strategy_months": [len(pool) for pool in pools],
            "random_mean_6x_count": statistics.mean(draws), "random_p_ge_observed": p,
            "first_half_6x": sum(bool(picks[m] and hit(picks[m])) for m in months[:6]),
            "second_half_6x": sum(bool(picks[m] and hit(picks[m])) for m in months[6:]),
            "first_half_severe": sum(bool(picks[m] and picks[m]["same_month_as_entry"] and picks[m]["ending_multiple"] <= .5)
                                     for m in months[:6]),
            "second_half_severe": sum(bool(picks[m] and picks[m]["same_month_as_entry"] and picks[m]["ending_multiple"] <= .5)
                                      for m in months[6:]),
            "gates": {"positive_net_mean": statistics.mean(avg) > 1, "majority_6x": hits > n / 2,
                      "severe_loss_no_more_than_25pct": severe <= n / 4 and len(filled) == len(credited),
                      "beats_random": p <= .05},
            "entries": picks}


def evaluate(days, slip):
    entries, random_candidates = {}, defaultdict(list)
    diagnostic = {"missing_market_days": 0, "missing_forecast_days": 0, "queried_quotes": 0,
                  "quotes_with_both_endpoint_prices": 0, "entry_eligible": 0,
                  "forecast_signal_days": 0, "forecast_signal_days_without_fill": 0,
                  "forecast_signal_days_with_fill": 0}
    all_filled_days = []
    for iso, record in days.items():
        day = date.fromisoformat(iso)
        mo = iso[:7]
        diagnostic["missing_market_days"] += not record["markets"]
        diagnostic["missing_forecast_days"] += record["forecast_high_f"] is None
        options = []
        for row in record["candidates"]:
            diagnostic["queried_quotes"] += 1
            diagnostic["quotes_with_both_endpoint_prices"] += (row["ask_signal"] is not None and row["ask_entry"] is not None)
            edge = signal_entry(row)
            if edge is not None:
                options.append((edge, row["ticker"], row))
                demo = simulate_fill(row, day, slip)
                if demo:
                    diagnostic["entry_eligible"] += 1
                    random_candidates[mo].append(demo)
        if not options:
            continue
        edge, _, row = max(options, key=lambda x: (x[0], x[1]))
        if edge < .03:
            continue
        diagnostic["forecast_signal_days"] += 1
        filled = simulate_fill(row, day, slip)
        if filled is None:
            diagnostic["forecast_signal_days_without_fill"] += 1
            continue
        diagnostic["forecast_signal_days_with_fill"] += 1
        all_filled_days.append(filled)
        entries.setdefault(mo, filled)
    single_events = {}
    for year in (2024, 2025):
        selected = [r for r in all_filled_days if r["event_day"].startswith(str(year))]
        single_events[year] = {"eligible_filled": len(selected),
                               "winning": sum(r["won"] for r in selected),
                               "average_multiple": statistics.mean(r["ending_multiple"] for r in selected) if selected else None}
    return {"diagnostics": diagnostic, "all_qualified_events": single_events,
            "reference": years_summary(entries, random_candidates, 2024),
            "holdout": years_summary(entries, random_candidates, 2025)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    snapshot = download(args.refresh) if args.refresh or not SNAPSHOT.exists() else json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
    base = evaluate(snapshot["days"], CENT)
    stress = evaluate(snapshot["days"], 2 * CENT)
    result = {"snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
              "fit": snapshot["fit"], "base": base, "stress": stress,
              "deployment_pass": all(base["holdout"]["gates"].values()) and all(stress["holdout"]["gates"].values())}
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    for key in ("base", "stress"):
        for period in ("reference", "holdout"):
            print(key, period, {k: v for k, v in result[key][period].items() if k != "entries"})


if __name__ == "__main__":
    main()
