"""Replay a spot volume breakout after a quiet week."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import date
from statistics import median

from .spot import BASE_COST, HERE, ONE, STRESS_COST, month_windows

INPUT = HERE / "spot_inputs.json.gz"


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
            pools[day + ONE].append(symbol)
            strength = volume / normal
            if strength < 3 or close < low + .75 * (high - low):
                continue
            prior = [bars[d][3] for d in days[i-7:i]]
            if close < prior[-1] * 1.08 or max(prior) > 1.1 * min(prior):
                continue
            rank = (-strength, symbol)
            if day + ONE not in leaders or rank < leaders[day + ONE]:
                leaders[day + ONE] = rank
    return {d: (row[1], pools[d]) for d, row in leaders.items()}


def evaluate(choices, prices, months, cost, comparison=True):
    by_month = defaultdict(list)
    allowed = set(months)
    for day, (symbol, pool) in sorted(choices.items()):
        month = day.isoformat()[:7]
        if month not in allowed:
            continue
        factor = (1 - cost) / (1 + cost)

        def get_return(s):
            bar = prices[s].get(day)
            return bar[3] / bar[0] * factor if bar else 1.0

        by_month[month].append((day.isoformat(), symbol, get_return(symbol),
                                [get_return(s) for s in pool] if comparison else []))

    def replay(rng=None):
        balance = 1.0
        peak = 1.0
        drawdown = 0.0
        path = []
        for month in months:
            start = balance
            for _, _, growth, random_choices in by_month[month]:
                balance *= rng.choice(random_choices) if rng else growth
                peak = max(peak, balance)
                drawdown = max(drawdown, 1 - balance / peak)
            path.append((month, balance / start))
        return {"3x_months": sum(x >= 3 for _, x in path), "ending_thb": balance * 5000,
                "max_close_drawdown": drawdown, "months": path}

    actual = replay()
    actual["events"] = [row[:3] for items in by_month.values() for row in items]
    if comparison:
        rng = random.Random(48317)
        draws = [replay(rng) for _ in range(1000)]
        actual["random"] = {
            "end_median_thb": median(d["ending_thb"] for d in draws),
            "fraction_at_least_actual": sum(d["ending_thb"] >= actual["ending_thb"] for d in draws) / len(draws),
            "draws_with_3x": sum(d["3x_months"] > 0 for d in draws),
        }
    return actual


def main():
    raw = gzip.decompress(INPUT.read_bytes())
    source = json.loads(raw)
    prices = {s: {date.fromisoformat(d): bar for d, bar in rows.items()} for s, rows in source["markets"].items()}
    choices = candidates(prices)
    months = [a.isoformat()[:7] for a, _ in month_windows()]
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "assets": len(prices), "periods": {}}
    for label, selected in (("reference", months[:36]), ("holdout", months[36:60]),
                            ("later", months[60:]), ("continuous", months)):
        output["periods"][label] = {
            case: evaluate(choices, prices, selected, cost)
            for case, cost in (("base", BASE_COST), ("stress", STRESS_COST))
        }
    (HERE / "spot_volume_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
