"""Run from project dir: python3 -m research.world_signals.football [--refresh]."""

import argparse
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, timedelta
import gzip
import hashlib
from io import StringIO
import json
from pathlib import Path
import random
from statistics import mean
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core import data
from research import events

OUT = Path(__file__).resolve().parent
SNAPSHOT = OUT / "football_inputs.json.gz"
RESULT = OUT / "football_results.json"
SPORTS = "https://raw.githubusercontent.com/martj42/international_results/master/"
NASDAQ = "https://api.nasdaq.com/api/quote/{symbol}/historical?"
ETF = {
    "Brazil": "EWZ", "Germany": "EWG", "France": "EWQ", "Spain": "EWP",
    "Italy": "EWI", "Japan": "EWJ", "Mexico": "EWW", "South Korea": "EWY",
    "Australia": "EWA", "Belgium": "EWK", "Netherlands": "EWN",
    "Switzerland": "EWL", "Canada": "EWC",
}
TOURNAMENTS = {"FIFA World Cup", "UEFA Euro", "Copa América", "AFC Asian Cup", "Gold Cup"}
COST = 0.003 + 0.03 / 365
STRESS_COST = 0.009 + 0.10 / 365
DRAWS = 10000
PERIODS = {"development": (2010, 2020), "holdout": (2021, 2025),
           "holdout_2021_2022": (2021, 2022), "holdout_2023_2025": (2023, 2025)}


def football_losses():
    bodies = {name: data.http_get(SPORTS + name, timeout=25)
              for name in ("results.csv", "shootouts.csv")}
    tables = {name: list(csv.DictReader(StringIO(body.decode("utf-8-sig"))))
              for name, body in bodies.items()}
    shootouts = {
        (row["date"], frozenset((row["home_team"], row["away_team"]))): row["winner"]
        for row in tables["shootouts.csv"]
    }
    signals = []
    for row in tables["results.csv"]:
        day, tournament = row["date"], row["tournament"]
        if not ("2010-01-01" <= day <= "2025-12-31" and tournament in TOURNAMENTS):
            continue
        home, away = row["home_team"], row["away_team"]
        if not (row["home_score"] and row["away_score"]):
            continue
        a, b = int(row["home_score"]), int(row["away_score"])
        if a == b:
            winner = shootouts.get((day, frozenset((home, away))))
            if winner not in (home, away):
                continue
        else:
            winner = home if a > b else away
        loser = away if winner == home else home
        if loser in ETF:
            signals.append({"match": day, "country": loser, "symbol": ETF[loser],
                            "winner": winner, "tournament": tournament, "penalties": a == b})
    digests = {SPORTS + name: hashlib.sha256(body).hexdigest() for name, body in bodies.items()}
    return signals, digests


def nasdaq_prices(symbol):
    query = urlencode({"assetclass": "etf", "fromdate": "2010-01-01",
                       "todate": "2025-12-31", "limit": 5000})
    url = NASDAQ.format(symbol=symbol) + query
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        "Accept": "*/*",
    })
    with urlopen(request, timeout=25) as response:
        body = response.read()
    payload = json.loads(body)["data"]
    rows = payload["tradesTable"]["rows"]
    if len(rows) != payload["totalRecords"]:
        raise RuntimeError(f"{symbol}: incomplete Nasdaq response")
    prices = {}
    for row in rows:
        day = datetime.strptime(row["date"], "%m/%d/%Y").date().isoformat()
        if any(row[field] in ("N/A", "--", "") for field in ("open", "close")):
            continue
        opening, close = [float(row[field].replace("$", "").replace(",", ""))
                          for field in ("open", "close")]
        if opening > 0 and close > 0:
            prices[day] = [opening, close]
    return prices, url, hashlib.sha256(body).hexdigest()


def yahoo_prices(symbol):
    return {(date.fromisoformat(bar["d"]) - timedelta(days=1)).isoformat(): [bar["o"], bar["c"]]
            for bar in events.bars(symbol, start="2010-01-01") if "2010-01-01" < bar["d"] <= "2026-01-01"}


def snapshot():
    signals, hashes = football_losses()
    symbols = ["SPY", *ETF.values()]
    try:
        spy = yahoo_prices("SPY")
        with ThreadPoolExecutor(max_workers=4) as pool:
            prices = dict(zip(symbols[1:], pool.map(yahoo_prices, symbols[1:]), strict=True))
        prices["SPY"] = spy
        provider = "Yahoo Finance / research.events.bars (US session date corrected)"
        failure = None
    except (OSError, ValueError, KeyError, TypeError) as error:
        failure = str(error)
        provider = "Nasdaq historical ETF quote API"
        prices = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for symbol, (bars, source, digest) in zip(symbols, pool.map(nasdaq_prices, symbols), strict=True):
                prices[symbol] = bars
                hashes[source] = digest
    inputs = {"provider": provider, "yahoo_failure": failure,
              "upstream_sha256": hashes, "signals": signals, "prices": prices}
    SNAPSHOT.write_bytes(gzip.compress(json.dumps(inputs, sort_keys=True).encode(), mtime=0))
    return inputs


def session_trades(inputs):
    prices = inputs["prices"]
    nyse = sorted(prices["SPY"])
    first_day = max(min(bars) for bars in prices.values())
    start_year = int(first_day[:4])
    first_january_session = next(day for day in nyse if day >= f"{start_year}-01-01")
    if first_day != first_january_session or first_day[5:7] != "01" or int(first_day[8:]) > 7:
        start_year += 1
    if start_year > 2021 or nyse[-1] < "2025-12-29":
        raise ValueError("Incomplete date coverage for holdout")
    trades, missing, duplicates = [], [], []
    used = set()
    for signal in inputs["signals"]:
        match = signal["match"]
        if not f"{start_year}-01-01" <= match <= "2025-12-31":
            continue
        index = bisect_right(nyse, match)
        if index == len(nyse):
            continue
        entry = nyse[index]
        if (match < "2021") != (entry < "2021"):
            continue
        ticker = signal["symbol"]
        if entry not in prices[ticker]:
            missing.append({"entry": entry, **signal})
            continue
        if (entry, ticker) in used:
            duplicates.append({"entry": entry, **signal})
            continue
        used.add((entry, ticker))
        opening, close = prices[ticker][entry]
        sp_open, sp_close = prices["SPY"][entry]
        gross = 1 - close / opening
        trades.append({"entry": entry, "open": opening, "close": close, **signal,
                       "gross_return": gross, "net_return": gross - COST,
                       "stress_return": gross - STRESS_COST, "relative_short": gross - (1 - sp_close / sp_open)})
    return trades, missing, duplicates, start_year


def match_key(day):
    return day[:4], date.fromisoformat(day).weekday()


def control(trades, all_event_dates, prices):
    if not trades:
        return None
    by_day = defaultdict(list)
    for row in trades:
        by_day[row["entry"]].append(row["symbol"])
    grouped = defaultdict(list)
    for day, symbols in sorted(by_day.items()):
        grouped[match_key(day)].append(symbols)
    candidates = defaultdict(list)
    for day in sorted(prices["SPY"]):
        if day in all_event_dates:
            continue
        key = match_key(day)
        if key in grouped and all(day in prices[symbol] for symbols in grouped[key] for symbol in symbols):
            candidates[key].append(day)
    returns = {}
    for key, groups in grouped.items():
        if len(candidates[key]) < len(groups):
            raise RuntimeError(f"too few controls for {key}")
        for day in candidates[key]:
            returns[day] = {}
            for ticker in {symbol for symbols in groups for symbol in symbols}:
                opening, close = prices[ticker][day]
                returns[day][ticker] = 1 - close / opening - COST
    rand = random.Random(8771)
    null = []
    for _ in range(DRAWS):
        total = 0
        for key, groups in grouped.items():
            for tickers, day in zip(groups, rand.sample(candidates[key], len(groups)), strict=True):
                total += sum(returns[day][ticker] for ticker in tickers)
        null.append(total / len(trades))
    observed = mean(row["net_return"] for row in trades)
    null.sort()
    return {"draws": DRAWS, "mean_pct": 100 * mean(null), "p_greater_equal": (
        1 + sum(value >= observed for value in null)) / (DRAWS + 1),
            "central_95_pct": [100 * null[int(DRAWS * p)] for p in (0.025, 0.975)]}


def stats(trades, years):
    if not trades:
        return {"n": 0, "events_per_year": 0}
    daily = defaultdict(list)
    for row in trades:
        daily[row["entry"]].append(row["net_return"])
    monthly = {f"{year}-{month:02}": 1.0 for year in range(years[0], years[1] + 1)
               for month in range(1, 13)}
    equity, peak, drawdown = 1.0, 1.0, 0.0
    for day, returns in sorted(daily.items()):
        factor = 1 + mean(returns)
        equity *= factor
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
        monthly[day[:7]] *= factor
    return {
        "n": len(trades), "entry_sessions": len(daily), "months": len(monthly),
        "events_per_year": len(trades) / (years[1] - years[0] + 1),
        "mean_gross_pct": 100 * mean(row["gross_return"] for row in trades),
        "mean_net_pct": 100 * mean(row["net_return"] for row in trades),
        "mean_stress_pct": 100 * mean(row["stress_return"] for row in trades),
        "mean_relative_gross_pct": 100 * mean(row["relative_short"] for row in trades),
        "win_pct": 100 * sum(row["net_return"] > 0 for row in trades) / len(trades),
        "worst_net_pct": 100 * min(row["net_return"] for row in trades),
        "max_close_to_close_drawdown_pct": 100 * drawdown,
        "months_at_or_over_sixfold": sum(factor >= 6 for factor in monthly.values()),
        "best_month_pct": 100 * (max(monthly.values()) - 1),
        "end_equity_multiple": equity,
    }


def run(inputs):
    trades, missing, duplicates, start_year = session_trades(inputs)
    prices = inputs["prices"]
    all_dates = {row["entry"] for row in trades + missing}
    results, by_period = {}, {}
    for name, (start, end) in PERIODS.items():
        start = max(start, start_year)
        selected = [row for row in trades if start <= int(row["entry"][:4]) <= end]
        by_period[name] = selected
        results[name] = {"years": [start, end], **stats(selected, (start, end)),
                         "random_control": control(selected, all_dates, prices)}
    holdout = by_period["holdout"]
    subgroups = {name: stats([row for row in holdout if (row["tournament"] == "FIFA World Cup") == world],
                             PERIODS["holdout"])
                 for name, world in (("world_cup", True), ("continental", False))}
    leave_one_out = {}
    for ticker in ETF.values():
        other = [row["net_return"] for row in holdout if row["symbol"] != ticker]
        if other:
            leave_one_out[ticker] = 100 * mean(other)
    main = results["holdout"]
    passed = {"holdout_net_positive": main["mean_net_pct"] > 0,
              "holdout_beats_random_p_under_0_05": main["random_control"]["p_greater_equal"] < .05,
              "both_holdout_subperiods_positive": all(results[name]["mean_net_pct"] > 0 for name in (
                  "holdout_2021_2022", "holdout_2023_2025")),
              "holdout_stress_positive": main["mean_stress_pct"] > 0,
              "positive_when_any_etf_omitted": all(value > 0 for value in leave_one_out.values())}
    return {
        "provider": inputs["provider"], "yahoo_failure": inputs["yahoo_failure"],
        "upstream_sha256": inputs["upstream_sha256"],
        "price_coverage": {symbol: {"first": min(bars), "last": max(bars), "rows": len(bars)}
                           for symbol, bars in prices.items()},
        "cost_pct": {"base": 100 * COST, "stress": 100 * STRESS_COST}, "strategy_trials": 1,
        "missing": missing, "duplicate_signals": duplicates, "results": results,
        "holdout_by_tournament_group": subgroups,
        "holdout_mean_net_pct_leaving_one_etf_out": leave_one_out, "pass_tests": passed,
        "trades": sorted(trades, key=lambda row: (row["entry"], row["symbol"])),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Replace the local input snapshot from upstream")
    args = parser.parse_args()
    inputs = snapshot() if args.refresh or not SNAPSHOT.exists() else json.loads(gzip.decompress(SNAPSHOT.read_bytes()))
    result = run(inputs)
    RESULT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("provider", "results", "pass_tests")}, indent=2))
