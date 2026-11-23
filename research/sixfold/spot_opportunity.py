"""Measure hindsight opportunity in liquid same-day Binance spot trades."""
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import date
from math import prod
from statistics import median

from .spot import BASE_COST, HERE, ONE, STRESS_COST, month_windows


def daily_returns(markets):
    returns = defaultdict(list)
    for symbol, series in sorted(markets.items()):
        bars = sorted((date.fromisoformat(day), row) for day, row in series.items())
        for i in range(30, len(bars)):
            day, entry = bars[i]
            if day - bars[i-30][0] != 30 * ONE:
                continue
            previous = bars[i-1][1]
            if previous[5] < 1000:
                continue
            normal = median(row[4] for _, row in bars[i-30:i-1])
            if normal >= 1_000_000:
                returns[day.isoformat()].append((entry[3] / entry[0], symbol))
    return returns


def quantify(returns, cost):
    grouped = defaultdict(list)
    factor = (1 - cost) / (1 + cost)
    for day, choices in sorted(returns.items()):
        ranked = sorted(choices, reverse=True)
        grouped[day[:7]].append({
            "day": day, "symbol": ranked[0][1], "best": max(1, ranked[0][0] * factor),
            "fifth": max(1, ranked[4][0] * factor) if len(ranked) >= 5 else 1,
            "choices": len(ranked),
        })
    output = {}
    for start, _ in month_windows():
        month = start.isoformat()[:7]
        days = grouped[month]
        winners = sorted((d for d in days if d["best"] > 1), key=lambda d: d["best"], reverse=True)
        row = {"eligible_days": len(days), "perfect_daily": prod(d["best"] for d in days),
               "perfect_fifth": prod(d["fifth"] for d in days), "top_4_days": prod(d["best"] for d in winners[:4]),
               "needed": {}, "perfect_winners": winners}
        for target in (3, 6):
            gain = 1.0
            count = None
            for i, d in enumerate(winners, 1):
                gain *= d["best"]
                if gain >= target:
                    count = i
                    break
            row["needed"][str(target)] = count
        output[month] = row
    return output


def main():
    raw = gzip.decompress((HERE / "spot_inputs.json.gz").read_bytes())
    returns = daily_returns(json.loads(raw)["markets"])
    result = {"input_sha256": hashlib.sha256(raw).hexdigest(), "hindsight_only": True,
              "cases": {label: quantify(returns, cost) for label, cost in
                        (("base", BASE_COST), ("stress", STRESS_COST))}}
    (HERE / "spot_opportunity_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
