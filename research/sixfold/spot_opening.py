"""Replay an early-session taker imbalance with archived hourly Binance bars."""
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from urllib.parse import urlencode

from .spot import BASE_COST, HERE, STRESS_COST
from .spot_inputs import download, millis
from .spot_november import INPUT as UNIVERSE, START, STOP, URL
from .spot_volume import evaluate

INPUT = HERE / "spot_opening_inputs.json.gz"
RESULT = HERE / "spot_opening_results.json"


def collect(symbol):
    query = urlencode(dict(symbol=symbol, interval="1h", startTime=millis(START),
                           endTime=millis(STOP)-1, limit=600))
    try:
        rows = json.loads(download(f"{URL}?{query}"))
    except OSError as exc:
        return {}, str(exc)
    output = {}
    for row in rows:
        offset, extra = divmod(row[0] - millis(START), 3600000)
        assert not extra and 0 <= offset < 24 * (STOP - START).days
        output[offset] = [float(row[i]) for i in (1, 2, 3, 4, 7, 10)]
    return output, None


def acquire():
    universe = gzip.decompress(UNIVERSE.read_bytes())
    symbols = sorted(json.loads(universe)["markets"])
    with ThreadPoolExecutor(6) as pool:
        gathered = list(pool.map(collect, symbols))
    output = {"universe_sha256": hashlib.sha256(universe).hexdigest(), "source": URL,
              "markets": {}, "failures": {}}
    for symbol, (rows, error) in zip(symbols, gathered):
        output["markets"][symbol] = rows
        if error:
            output["failures"][symbol] = error
    INPUT.write_bytes(gzip.compress(json.dumps(output).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    source = json.loads(raw)
    markets = {s: {int(h): row for h, row in rows.items()} for s, rows in source["markets"].items()}
    choices = {}
    prices = {s: {} for s in markets}
    for i in range((STOP - START).days):
        day = START + timedelta(days=i)
        base = i * 24
        pool, candidates = [], []
        for symbol, rows in markets.items():
            first = [rows.get(base + h) for h in range(4)]
            if any(row is None for row in first):
                continue
            volume = sum(row[4] for row in first)
            if volume <= 0:
                continue
            pool.append(symbol)
            ratio = sum(row[5] for row in first) / volume
            high, low = max(r[1] for r in first), min(r[2] for r in first)
            if ratio >= .60 and first[-1][3] >= first[0][0] * 1.04 and first[-1][3] >= low + .75 * (high - low):
                candidates.append((-ratio, symbol))
            if base + 4 in rows:
                complete = all(base + h in rows for h in range(5, 24))
                prices[symbol][day] = [rows[base+4][0], 0, 0, rows[base+23][3] if complete else 0]
        if candidates:
            choices[day] = (min(candidates)[1], pool)
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "partial_month": True,
              "bars": {s: len(rows) for s, rows in markets.items()}, "failures": source["failures"],
              "cases": {name: evaluate(choices, prices, ["2026-11"], cost)
                        for name, cost in (("base", BASE_COST), ("stress", STRESS_COST))}}
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
