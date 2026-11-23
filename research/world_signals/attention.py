"""Run from TradeLab: python3 -m research.world_signals.attention [--refresh]."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import random
from statistics import mean, median
from urllib.request import Request, urlopen

from research.events import bars, summary

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "attention_inputs.json.gz"
RESULT = HERE / "attention_results.json"
DAY = timedelta(days=1)
WARMUP = "2017-12-01"
ASSETS = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum"}
PERIODS = {
    "development": ("2018-01-01", "2020-12-31"),
    "holdout": ("2021-01-01", "2025-12-31"),
    "early_holdout": ("2021-01-01", "2022-12-31"),
    "late_holdout": ("2023-01-01", "2025-12-31"),
}
LAST_DAY = PERIODS["holdout"][1]
CONFIGS = {
    "primary_BTC": ("BTC-USD", 3),
    "slower_BTC": ("BTC-USD", 4),
    "external_ETH": ("ETH-USD", 3),
}
NORMAL_COST, STRESS_COST = 0.0025, 0.01  # each side
DRAWS = 10_000
HOLD = 5 * DAY


def calendar(start, end):
    return (start + i * DAY for i in range((end - start).days + 1))


def download_asset(asset):
    article = ASSETS[asset]
    first = WARMUP.replace("-", "") + "00"
    last = LAST_DAY.replace("-", "") + "00"
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           f"en.wikipedia.org/all-access/user/{article}/daily/{first}/{last}")
    request = Request(url, headers={"User-Agent": "TradeLabWorldSignals/1.0 (public research)"})
    with urlopen(request, timeout=30) as response:
        rows = json.load(response)["items"]

    views = {
        f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}": row["views"]
        for row in rows if (stamp := row["timestamp"])
    }
    prices = {r["d"]: [r["o"], r["c"]] for r in bars(asset, WARMUP) if r["d"] <= LAST_DAY}
    return asset, {"pageviews_url": url, "prices_source": f"Yahoo Finance daily chart, {asset}",
                   "views": views, "prices": prices}


def load_inputs(refresh):
    if refresh or not SNAPSHOT.exists():
        with ThreadPoolExecutor() as pool:
            series = dict(pool.map(download_asset, ASSETS))
        payload = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "series": series}
        SNAPSHOT.write_bytes(gzip.compress(json.dumps(payload, sort_keys=True).encode(), mtime=0))
    return json.loads(gzip.decompress(SNAPSHOT.read_bytes()))


def entry_days(views, delay):
    entries = set()
    for day, count in views.items():
        prior = [views.get(day - i * DAY) for i in range(1, 29)]
        if None in prior:
            continue
        typical = median(prior)
        if typical > 0 and count >= 2 * typical:
            entries.add(day + delay * DAY)
    return entries


def candidates(days, prices, start, end):
    eligible = []
    for day in sorted(days):
        if start <= day <= end - HOLD and all(d in prices for d in calendar(day, day + HOLD)):
            eligible.append(day)
    return eligible


def deconflict(eligible):
    trades = []
    for day in eligible:
        if not trades or day >= trades[-1] + HOLD:
            trades.append(day)
    return trades


def net_return(day, prices, cost):
    return prices[day + HOLD][0] * (1 - cost) / (prices[day][0] * (1 + cost)) - 1


def account_metrics(trades, prices, cost, start, end):
    day_entries = set(trades)
    day_exits = {day + HOLD for day in trades}
    cash, shares, peak, max_drawdown = 1.0, 0.0, 1.0, 0.0
    last_value = month_start_value = 1.0
    month = (start.year, start.month)
    monthly = {}
    monthly_exit_peaks = {}
    for day in calendar(start, end):
        key = (day.year, day.month)
        if key != month:
            monthly[f"{month[0]}-{month[1]:02d}"] = (last_value / month_start_value - 1) * 100
            month_start_value, month = last_value, key
        if day in day_exits:
            cash, shares = shares * prices[day][0] * (1 - cost), 0.0
            exit_gain = (cash / month_start_value - 1) * 100
            monthly_exit_peaks[key] = max(exit_gain, monthly_exit_peaks.get(key, exit_gain))
        if day in day_entries:
            cash, shares = 0.0, cash / (prices[day][0] * (1 + cost))
        last_value = shares * prices[day][1] if shares else cash
        peak = max(peak, last_value)
        max_drawdown = max(max_drawdown, 1 - last_value / peak)
    monthly[f"{month[0]}-{month[1]:02d}"] = (last_value / month_start_value - 1) * 100
    return {"daily_close_max_drawdown_pct": max_drawdown * 100,
            "ending_multiple": last_value,
            "month_end_6x_hits": sum(v >= 500 for v in monthly.values()),
            "month_exit_6x_hits": sum(v >= 500 for v in monthly_exit_peaks.values()),
            "best_month_at_exit_pct": max(monthly_exit_peaks.values(), default=None),
            "months": len(monthly),
            "best_month_pct": max(monthly.values()),
            "monthly_net_returns_pct": monthly}


def measure(trades, possible, signals, prices, cost, start, end):
    if not trades:
        return {"n": 0}
    values = [net_return(day, prices, cost) for day in trades]
    weekday_pools, month_pools = defaultdict(list), defaultdict(list)
    for day in possible:
        if day in signals:
            continue
        year_month = (day.year, day.month)
        value = net_return(day, prices, cost)
        weekday_pools[(*year_month, day.weekday())].append(value)
        month_pools[year_month].append(value)

    pools, relax = [], 0
    for day in trades:
        year_month = (day.year, day.month)
        controls = weekday_pools.get((*year_month, day.weekday()))
        if not controls:
            controls = month_pools[year_month]
            relax += 1
        if not controls:
            raise ValueError(f"No control within the same month for {day}")
        pools.append(controls)

    rng = random.Random(271828)
    threshold = sum(values)
    above = sum(sum(rng.choice(pool) for pool in pools) >= threshold for _ in range(DRAWS))
    baseline = mean(mean(pool) for pool in pools)
    p = (above + 1) / (DRAWS + 1)
    years = (end - start).days / 365.2425 + 1 / 365.2425
    out = summary(values)
    out.pop("t", None)
    out.update({
        "mean_pct": mean(values) * 100,
        "median_pct": median(values) * 100,
        "win_pct": sum(v > 0 for v in values) * 100 / len(values),
        "worst_trade_pct": min(values) * 100,
        "trades_per_year": len(values) / years,
        "matched_random_mean_pct": baseline * 100,
        "edge_pp": (mean(values) - baseline) * 100,
        "randomization_upper_tail_p": p,
        "family_adjusted_p": min(1.0, len(CONFIGS) * p),
        "weekday_relaxations": relax,
        "account": account_metrics(trades, prices, cost, start, end),
    })
    return out


def run_config(series, delay):
    views = {date.fromisoformat(k): v for k, v in series["views"].items()}
    prices = {date.fromisoformat(k): v for k, v in series["prices"].items()}
    signals = entry_days(views, delay)
    result = {}
    all_holdout_trades = []
    for name, bounds in PERIODS.items():
        start, end = map(date.fromisoformat, bounds)
        possible = candidates(prices, prices, start, end)
        eligible = candidates(signals, prices, start, end)
        if name.endswith("_holdout"):
            trades = [d for d in all_holdout_trades if start <= d <= end - HOLD]
        else:
            trades = deconflict(eligible)
        if name == "holdout":
            all_holdout_trades = trades
        result[name] = {
            "qualifying_entry_dates": len(eligible),
            "calendar_days_without_prices": sum(d not in prices for d in calendar(start, end)),
            "calendar_days_without_views": sum(d not in views for d in calendar(start, end)),
            "base": measure(trades, possible, signals, prices, NORMAL_COST, start, end),
            "stress": measure(trades, possible, signals, prices, STRESS_COST, start, end),
            "trade_dates_utc": [day.isoformat() for day in trades],
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="replace archived inputs with current source data")
    args = parser.parse_args()
    inputs = load_inputs(args.refresh)
    configs = {name: run_config(inputs["series"][asset], delay)
               for name, (asset, delay) in CONFIGS.items()}
    primary = configs["primary_BTC"]
    h = primary["holdout"]
    base, stress = h["base"], h["stress"]
    gates = {
        "holdout_at_least_30": base["n"] >= 30,
        "holdout_net_positive": base.get("mean_pct", 0) > 0,
        "holdout_beats_random_adjusted_p_under_005": base.get("family_adjusted_p", 1) < 0.05,
        "both_holdout_subdivisions_positive_and_beat_random": all(
            primary[period]["base"].get("mean_pct", 0) > 0
            and primary[period]["base"].get("edge_pp", 0) > 0
            for period in ("early_holdout", "late_holdout")
        ),
        "positive_at_stress_cost": stress.get("mean_pct", 0) > 0,
        "positive_edge_in_delayed_BTC_and_ETH": all(
            configs[name]["holdout"]["base"].get("edge_pp", 0) > 0
            for name in ("slower_BTC", "external_ETH")
        ),
    }
    result = {
        "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256((HERE / "attention_protocol.md").read_bytes()).hexdigest(),
        "retrieved_at_utc": inputs["retrieved_at_utc"],
        "tested_configurations": len(CONFIGS),
        "matched_random_draws_per_period": DRAWS,
        "paper_candidate": all(gates.values()),
        "gates": gates,
        "cost_per_side_pct": {"base": NORMAL_COST * 100, "stress": STRESS_COST * 100},
        "configurations": configs,
    }
    RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for label, config in configs.items():
        for period, metrics in config.items():
            b = metrics["base"]
            keys = ("n", "mean_pct", "win_pct", "worst_trade_pct", "trades_per_year",
                    "matched_random_mean_pct", "edge_pp", "family_adjusted_p")
            print(label, period, {k: round(b[k], 5) for k in keys if k in b})
    print("gates", gates)


if __name__ == "__main__":
    main()
