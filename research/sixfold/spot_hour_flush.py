"""Replay an intraday rebound after sell-side pressure."""
import gzip
import hashlib
import json
from datetime import date, timedelta

from .spot import BASE_COST, HERE, STRESS_COST
from .spot_volume import evaluate

FILES = {f"2026-{m:02d}": HERE / f"spot_opening_2026-{m:02d}_inputs.json.gz" for m in (7, 8, 9)}
FILES["2026-10"] = HERE / "spot_opening_october_inputs.json.gz"
FILES["2026-11"] = HERE / "spot_opening_inputs.json.gz"


def generate(markets, start, days):
    choices = {}
    prices = {symbol: {} for symbol in markets}
    for i in range(days):
        day = start + timedelta(days=i)
        for hour in range(22):
            offset = 24 * i + hour
            pool, qual = [], []
            for symbol, rows in markets.items():
                if offset not in rows:
                    continue
                o, high, low, close, volume, buy = rows[offset]
                if min(o, volume) <= 0:
                    continue
                pool.append(symbol)
                if low <= .92 * o and close >= (high + low) / 2 and buy <= .40 * volume:
                    qual.append((-volume, symbol))
            if not qual:
                continue
            choices[day] = (min(qual)[1], pool)
            for symbol in pool:
                rows = markets[symbol]
                if offset + 1 in rows:
                    prices[symbol][day] = [rows[offset+1][0], 0, 0, rows.get(offset+2, (0, 0, 0, 0))[3]]
            break
    return choices, prices


def main():
    choices, prices, sums = {}, {}, {}
    for month, path in FILES.items():
        raw = gzip.decompress(path.read_bytes())
        sums[month] = hashlib.sha256(raw).hexdigest()
        markets = {s: {int(h): row for h, row in rows.items()}
                   for s, rows in json.loads(raw)["markets"].items()}
        start = date.fromisoformat(month + "-01")
        days = (date(start.year, start.month + 1, 1) - start).days if start.month < 11 else 22
        picks, quotes = generate(markets, start, days)
        choices.update(picks)
        for symbol, bars in quotes.items():
            prices.setdefault(symbol, {}).update(bars)
    result = {"inputs": sums, "november_partial": True, "cases": {}}
    for label, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
        case = evaluate(choices, prices, list(FILES), cost)
        case["6x_months"] = sum(value >= 6 for _, value in case["months"])
        result["cases"][label] = case
    (HERE / "spot_hour_flush_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
