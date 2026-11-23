"""NOAA GHCN cold shocks and US natural gas fund opens. Python standard library.

Run from repo root: python3 -m research.world_signals.weather
Pass --refresh to fetch the frozen observation window again and replace the local snapshots.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import random
from bisect import bisect_left
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from statistics import mean
from subprocess import PIPE, CalledProcessError, TimeoutExpired, check_output
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from core import data
from research.events import summary

OUT = Path(__file__).parent
STATIONS = ("USW00094728", "USW00094846", "USW00013874")
STAGES = {
    "reference": (date(2014, 1, 1), date(2020, 12, 31)),
    "holdout": (date(2021, 1, 1), date(2025, 12, 31)),
    "2021-22": (date(2021, 1, 1), date(2022, 12, 31)),
    "2023-25": (date(2023, 1, 1), date(2025, 12, 31)),
}
ONE_DAY = timedelta(days=1)
WINTER = {11, 12, 1, 2, 3}
NOAA_QUERY = urlencode({
    "dataset": "daily-summaries",
    "stations": ",".join(STATIONS),
    "startDate": "2008-12-20",
    "endDate": "2025-12-31",
    "dataTypes": "TMAX,TMIN",
    "units": "standard",
    "format": "csv",
    "includeAttributes": "true",
    "includeStationName": "true",
})
NOAA = f"https://www.ncei.noaa.gov/access/services/data/v1?{NOAA_QUERY}"
PRICE_QUERY = "?period1=1388534400&period2=1767225600&interval=1d"
NY = ZoneInfo("America/New_York")


def load_raw(filename, urls, refresh):
    path = OUT / filename
    cache = path.exists() and not refresh
    if cache:
        return path.read_bytes(), None
    failures = []
    for url in urls:
        try:
            body = data.http_get(url, timeout=12)
        except OSError as exc:
            failures.append(f"{url} via urllib: {exc}")
            try:
                body = check_output(
                    ["curl", "-fsSL", "--max-time", "20", "-A", data.UA["User-Agent"], url],
                    timeout=22, stderr=PIPE,
                )
            except (OSError, CalledProcessError, TimeoutExpired) as curl_error:
                failures.append(f"{url} via curl: {curl_error}")
                continue
            client = "curl"
        else:
            client = "core.data.http_get"
        path.write_bytes(body)
        return body, {"url": url, "client": client, "prior_failures": failures}
    raise RuntimeError("\n".join(failures))


def read_daily_summaries(body):
    rows = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    stations = defaultdict(dict)
    rejected = Counter()
    for row in rows:
        station = row["STATION"]
        limits = (row["TMAX"], row["TMIN"])
        if (
            any(not value.strip() for value in limits)
            or row["TMAX_ATTRIBUTES"].split(",")[1]
            or row["TMIN_ATTRIBUTES"].split(",")[1]
        ):
            rejected[station] += 1
            continue
        day = date.fromisoformat(row["DATE"])
        assert day not in stations[station], (station, day)
        stations[station][day] = max(65 - mean(map(float, limits)), 0)
    return stations, rejected


def read_station_file(station, body):
    limits = defaultdict(dict)
    for line in body.decode("ascii").splitlines():
        year = int(line[11:15])
        element = line[17:21]
        if year < 2008 or year > 2025 or element not in {"TMAX", "TMIN"}:
            continue
        assert line[:11] == station
        month = int(line[15:17])
        for day in range(1, 32):
            start = 21 + 8 * (day - 1)
            value = int(line[start:start + 5])
            if value != -9999 and line[start + 6] == " ":
                limits[date(year, month, day)][element] = value * 0.18 + 32
    result = {}
    rejected = 0
    for day, pair in limits.items():
        if len(pair) == 2:
            result[day] = max(65 - mean(pair.values()), 0)
        else:
            rejected += 1
    return result, rejected


def observation_days(load):
    try:
        body = load("weather_noaa_daily.csv", [NOAA])
    except RuntimeError:
        stations = {}
        rejected = {}
        for station in STATIONS:
            url = f"https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station}.dly"
            stations[station], rejected[station] = read_station_file(
                station, load(f"weather_{station}.dly", [url])
            )
    else:
        stations, rejected = read_daily_summaries(body)
    assert set(stations) == set(STATIONS)
    shared = set.intersection(*(set(values) for values in stations.values()))
    combined = {day: mean(values[day] for values in stations.values()) for day in shared}
    return combined, {s: {"valid_days": len(stations[s]), "flagged_or_partial_rows": rejected.get(s, 0)}
                      for s in STATIONS}


def prices(symbol, load):
    """Adjust opens with the same factor as closes, as in research.events.bars."""
    urls = [f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}{PRICE_QUERY}"
            for host in ("query1", "query2")]
    chart = json.loads(load(f"weather_{symbol}.json", urls))["chart"]["result"][0]
    quote = chart["indicators"]["quote"][0]
    adjusted = chart["indicators"]["adjclose"][0]["adjclose"]
    dates = [datetime.fromtimestamp(timestamp, NY).date() for timestamp in chart["timestamp"]]
    assert sorted(set(dates)) == dates, symbol
    rows = {}
    for day, opening, close, adj, volume in zip(
        dates, quote["open"], quote["close"], adjusted, quote["volume"], strict=True
    ):
        if opening and close and adj and min(opening, close, adj) > 0:
            rows[day] = (opening * adj / close, adj, volume or 0)
    assert len(rows) > 2800 and min(rows) <= date(2014, 1, 3) and max(rows) == date(2025, 12, 31)
    return rows, len(dates) - len(rows)


def cold_events(hdd):
    anomalies = {}
    for day in sorted(hdd):
        if day.year < 2013 or (day.month, day.day) == (2, 29):
            continue
        bases = []
        for year in range(day.year - 5, day.year):
            target = day.replace(year=year)
            values = [hdd.get(target + timedelta(days=lag)) for lag in range(-7, 8)]
            if None not in values:
                bases.append(mean(values))
        if len(bases) >= 4:
            anomalies[day] = hdd[day] - mean(bases)
    events = [
        day for day, anomaly in anomalies.items()
        if day.year >= 2014 and day.month in WINTER and anomaly >= 8
        and anomalies.get(day - ONE_DAY, math.inf) < 8
    ]
    return events, anomalies


def period_trades(events, rows, bounds, lag):
    start, end = bounds
    dates = [day for day in rows if start <= day <= end]
    by_month = defaultdict(list)
    usable = {i for i in range(len(dates) - 2)
              if rows[dates[i]][2] and rows[dates[i + 2]][2]}
    blocked = set()
    entries = []
    counts = Counter()
    for event in events:
        if not start <= event <= end:
            continue
        counts["candidates"] += 1
        i = bisect_left(dates, event + 2 * ONE_DAY) + lag
        if i in blocked:
            counts["same_entry"] += 1
        if i >= len(dates) - 2:
            counts["end_of_period"] += 1
            continue
        if i not in usable:
            counts["zero_fill_volume"] += 1
            continue
        blocked.add(i)
        if entries and i < entries[-1][1] + 3:
            counts["overlapping"] += 1
            continue
        entries.append((event, i))
    for i in sorted(usable - blocked):
        by_month[dates[i].strftime("%Y-%m")].append(i)
    return dates, entries, by_month, dict(counts)


def fills(rows, dates, cost):
    return [rows[dates[i + 2]][1] * (1 - cost) / (rows[day][0] * (1 + cost)) - 1
            for i, day in enumerate(dates[:-2])]


def random_control(dates, entries, by_month, returns):
    if not entries:
        return None
    sizes = Counter(dates[i].strftime("%Y-%m") for _, i in entries)
    nonoverlapping = [
        [group for group in combinations(by_month[month], n)
         if all(later - earlier >= 3 for earlier, later in zip(group, group[1:]))]
        for month, n in sorted(sizes.items())
    ]
    if not all(nonoverlapping):
        raise ValueError("Insufficient random dates for matching")
    rng = random.Random(450459)
    means = []
    attempts = 0
    while len(means) < 5000:
        attempts += 1
        if attempts > 1_000_000:
            raise RuntimeError("Cannot draw adequate non-overlapping date samples by month")
        groups = [rng.choice(options) for options in nonoverlapping]
        if any(later[0] - earlier[-1] < 3 for earlier, later in zip(groups, groups[1:])):
            continue
        means.append(mean(returns[i] for group in groups for i in group))
    means.sort()
    return means, attempts


def equity_path(rows, dates, entries, cost):
    indexes = {i for _, i in entries}
    equity = 1.0
    peak = equity
    drawdown = 0.0
    position = None
    monthly_high = {}
    month = None
    for i, day in enumerate(dates):
        new_month = day.strftime("%Y-%m")
        if new_month != month:
            month = new_month
            month_start = equity
            monthly_high[month] = 0.0
        if position and i == position[0]:
            position = None
        opening, close, _ = rows[day]
        if i in indexes:
            position = (i + 3, equity / (opening * (1 + cost)))
        if position:
            equity = position[1] * close * (1 - cost)
        monthly_high[month] = max(monthly_high[month], equity / month_start * (0.995 / 1.005))
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
    return {
        "portfolio_drawdown_pct": 100 * drawdown,
        "total_net_pct": 100 * (equity - 1),
        "months_tested": len(monthly_high),
        "months_touched_6x_close": sum(high >= 6 for high in monthly_high.values()),
        "best_monthly_close_multiple": max(monthly_high.values(), default=None),
    }


def run(rows, events, anomalies, bounds, cost, lag):
    dates, entries, by_month, skipped = period_trades(events, rows, bounds, lag)
    returns = fills(rows, dates, cost)
    trades = [returns[i] for _, i in entries]
    random_result = random_control(dates, entries, by_month, returns)
    if random_result is None:
        return {"n": 0, "filter_counts": skipped}
    random_means, attempts = random_result
    sample_mean = mean(trades)
    random_mean = mean(random_means)
    years = bounds[1].year - bounds[0].year + 1
    return {
        **summary(trades),
        "net_mean_pct": 100 * sample_mean,
        "win_rate_pct": 100 * sum(trade > 0 for trade in trades) / len(trades),
        "min_trade_net_pct": 100 * min(trades),
        "worst_intratrade_close_pct": 100 * min(
            rows[dates[j]][1] * (1 - cost) / (rows[dates[i]][0] * (1 + cost)) - 1
            for _, i in entries for j in range(i, i + 3)
        ),
        "frequency_per_year": len(trades) / years,
        "random_mean_pct": 100 * random_mean,
        "random_middle_95_pct": [100 * random_means[125], 100 * random_means[4874]],
        "random_one_tail_p": (1 + len(random_means) - bisect_left(random_means, sample_mean)) / 5001,
        "net_excess_pct_points": 100 * (sample_mean - random_mean),
        "random_draw_attempts": attempts,
        "filter_counts": skipped,
        "median_entry_volume_shares": sorted(rows[dates[i]][2] for _, i in entries)[len(entries) // 2],
        **equity_path(rows, dates, entries, cost),
        "trades": [{"weather_day": str(day), "hdd_anomaly": round(anomalies[day], 4),
                    "entered": str(dates[i]), "exited": str(dates[i + 2]),
                    "return_net": round(returns[i], 10)}
                   for day, i in entries],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    provenance_path = OUT / "weather_provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}

    def load(filename, urls):
        body, source = load_raw(filename, urls, args.refresh)
        sha256 = hashlib.sha256(body).hexdigest()
        if source is not None:
            provenance[filename] = {
                **source, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "sha256": sha256,
            }
        elif filename not in provenance:
            raise ValueError(f"Missing download provenance for {filename}; use --refresh")
        elif provenance[filename]["sha256"] != sha256:
            raise ValueError(f"Snapshot changed for {filename}; use --refresh")
        return body

    with ThreadPoolExecutor(max_workers=3) as workers:
        weather = workers.submit(observation_days, load)
        price_jobs = {symbol: workers.submit(prices, symbol, load) for symbol in ("UNG", "UNL")}
        hdd, weather_coverage = weather.result()
        priced = {symbol: job.result() for symbol, job in price_jobs.items()}
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    events, anomalies = cold_events(hdd)
    variants = {
        "main": ("UNG", 0.0015, 0),
        "expensive": ("UNG", 0.005, 0),
        "late": ("UNG", 0.0015, 1),
        "transfer": ("UNL", 0.0015, 0),
    }
    output = {
        "protocol": "weather_protocol.md",
        "weather_coverage": weather_coverage,
        "common_observation_days": len(hdd),
        "price_coverage": {symbol: {"sessions": len(rows), "dropped_missing": dropped}
                           for symbol, (rows, dropped) in priced.items()},
        "configured_rule_count": len(variants),
        "variants": {},
    }
    for name, (symbol, cost, lag) in variants.items():
        rows = priced[symbol][0]
        results = {period: run(rows, events, anomalies, bounds, cost, lag)
                   for period, bounds in STAGES.items()}
        output["variants"][name] = {
            "symbol": symbol, "cost_per_side": cost, "extra_session_lag": lag, "periods": results,
        }
        for period, report in results.items():
            print(name, period, {key: round(report[key], 4) for key in (
                "n", "net_mean_pct", "random_mean_pct", "random_one_tail_p", "win_rate_pct",
                "min_trade_net_pct", "portfolio_drawdown_pct",
            )})
    main_results = output["variants"]["main"]["periods"]
    holdout = main_results["holdout"]
    output["passing_gates"] = {
        "positive_and_beats_random_in_all_holdout_slices": all(
            main_results[period]["net_mean_pct"] > 0 and main_results[period]["net_excess_pct_points"] > 0
            for period in ("holdout", "2021-22", "2023-25")
        ),
        "holdout_random_p_le_0_01": holdout["random_one_tail_p"] <= 0.01,
        "robust_positive_and_beats_random": {
            name: variant["periods"]["holdout"]["net_mean_pct"] > 0
            and variant["periods"]["holdout"]["net_excess_pct_points"] > 0
            for name, variant in output["variants"].items() if name != "main"
        },
        "verified_point_in_time_weather_delivery": False,
    }
    (OUT / "weather_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
