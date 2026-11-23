"""Test a pre-specified post-funding contrarian signal on archived futures."""
import gzip
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .perps import BASE_FEE, INTERVAL, STRESS_FEE, Market, summarize
from .perps_fetch import HERE, SYMBOLS

HIGH_FUNDING = 0.0003
LOW_FUNDING = -0.0001


def calendar_slot(timestamp):
    date = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    return date.strftime("%Y-%m"), date.hour


def first_entry(timestamp, first_stamp, delay):
    eligible_stamp = timestamp + delay
    return (eligible_stamp - first_stamp + INTERVAL - 1) // INTERVAL


def crowding_events(market, source, additional_lag):
    archive = json.loads(gzip.decompress(source.read_bytes()))["fundingRate"]
    groups = defaultdict(list)
    entries = defaultdict(list)
    first_stamp = market.timestamps[0]
    delay = INTERVAL + additional_lag
    former = None
    missing_fills = 0
    for timestamp, _, funding in archive:
        side = 0
        if former is not None:
            if former < HIGH_FUNDING <= funding:
                side = -1
            elif former > LOW_FUNDING >= funding:
                side = 1
        former = funding
        index = first_entry(timestamp, first_stamp, delay)
        original_month, _ = calendar_slot(timestamp)
        if index >= len(market.timestamps):
            missing_fills += bool(side)
            continue
        month, hour = calendar_slot(market.timestamps[index])
        if month != original_month or market.trades[index] is None:
            missing_fills += bool(side)
            continue
        groups[month, hour].append(index)
        if side:
            entries[month].append((index, side, hour))
    assert all(len(v) == len(set(v)) for v in groups.values())
    market.signals = entries
    market.hour_bars = groups
    return missing_fills


def run(symbol, leverage, fee, delay, random):
    path = HERE / f"perps_{symbol}_inputs.json.gz"
    market = Market(path)
    missing = crowding_events(market, path, delay)
    months = sorted(m for m in market.months if m >= "2021-01")
    monthly = [market.month(month, market.signals[month], leverage, fee) for month in months]
    period_indices = {"reference": slice(0, 36), "2024": slice(36, 48),
                      "2025": slice(48, 60), "holdout": slice(36, 60)}
    periods = {}
    for period, window in period_indices.items():
        periods[period] = summarize(monthly[window])
        directions = Counter(side for m in months[window] for _, side, _ in market.signals[m])
        periods[period]["long_signal_count"] = directions[1]
        periods[period]["short_signal_count"] = directions[-1]
    if random:
        score = periods["holdout"]
        score["matched_random"] = market.permutations(months[36:], leverage, fee, score)
    print(symbol, leverage, fee, delay, periods["holdout"], flush=True)
    return {"symbol": symbol, "leverage_on_collateral": leverage, "fee_per_side": fee, "extra_delay_ms": delay,
            "uncapturable_signals": missing, "market_snapshot_hash": market.hash, "periods": periods, "months": monthly}


def main():
    btc, eth = SYMBOLS
    variants = {
        "base": run(btc, 20, BASE_FEE, 0, True),
        "cost_stress": run(btc, 20, STRESS_FEE, 0, False),
        "lower_leverage": run(btc, 10, BASE_FEE, 0, False),
        "entry_delayed": run(btc, 20, BASE_FEE, 3_600_000, False),
        "eth_transfer": run(eth, 20, BASE_FEE, 0, False),
    }
    main_periods = variants["base"]["periods"]
    holdout = main_periods["holdout"]
    gates = {
        "sixfold_both_years": all(main_periods[y]["months_6x"] > 0 for y in ("2024", "2025")),
        "median_profitable": holdout["median_multiple"] > 1,
        "median_beats_random": holdout["matched_random"]["p_random_median_at_least_observed"] < 0.05,
        "sixfold_at_stress_cost": variants["cost_stress"]["periods"]["holdout"]["months_6x"] > 0,
        "hits_more_than_half_loss": holdout["months_6x"] > holdout["months_left_at_most_half"],
        "eth_median_profitable": variants["eth_transfer"]["periods"]["holdout"]["median_multiple"] > 1,
    }
    result = {"variants": variants, "gates": gates, "qualifies": all(gates.values())}
    (HERE / "crowding_results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(gates)


if __name__ == "__main__":
    main()
