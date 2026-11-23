"""Evaluate whether a sell-off with partial recovery continues the next day."""
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import date
from statistics import median

from .spot import BASE_COST, HERE, ONE, STRESS_COST, month_windows
from .spot_volume import INPUT, evaluate


def candidates(prices):
    pools = defaultdict(list)
    leaders = {}
    for symbol, bars in sorted(prices.items()):
        days = sorted(bars)
        for i in range(29, len(days)):
            day = days[i]
            if day - days[i - 29] != 29 * ONE:
                continue
            _, high, low, close, volume, trades = bars[day]
            if trades < 1000:
                continue
            normal = median(bars[d][4] for d in days[i-29:i])
            if normal < 1_000_000:
                continue
            entry = day + ONE
            pools[entry].append(symbol)
            prior = bars[days[i-1]][3]
            if low > .8 * prior or close > .92 * prior or close < (high + low) / 2 or volume < 2 * normal:
                continue
            rank = (low / prior, symbol)
            if entry not in leaders or rank < leaders[entry]:
                leaders[entry] = rank
    return {day: (row[1], pools[day]) for day, row in leaders.items()}


def main():
    raw = gzip.decompress(INPUT.read_bytes())
    markets = json.loads(raw)["markets"]
    prices = {s: {date.fromisoformat(d): v for d, v in rows.items()} for s, rows in markets.items()}
    choices = candidates(prices)
    months = [a.isoformat()[:7] for a, _ in month_windows()]
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "periods": {}}
    for label, selected in (("reference", months[:36]), ("holdout", months[36:60]),
                            ("later", months[60:]), ("continuous", months)):
        cases = output["periods"][label] = {}
        for case, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
            row = cases[case] = evaluate(choices, prices, selected, cost)
            row["6x_months"] = sum(value >= 6 for _, value in row["months"])
    (HERE / "spot_flush_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
