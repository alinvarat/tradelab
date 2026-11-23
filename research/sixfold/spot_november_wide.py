"""Forward time slice for frozen spot rules with point-in-time universe selection."""
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from statistics import median
from urllib.parse import urlencode

from . import spot_activity, spot_flush, spot_volume
from .spot import BASE_COST, HERE, STRESS_COST
from .spot_inputs import download, millis

START = date(2026, 11, 1)
STOP = date(2026, 11, 23)
INPUT = HERE / "spot_november_wide_inputs.json.gz"
RESULT = HERE / "spot_november_wide_results.json"
URL = "https://data-api.binance.vision/api/v3/klines"


def collect(symbol):
    params = dict(symbol=symbol, interval="1d", startTime=millis(START), endTime=millis(STOP)-1, limit=100)
    try:
        rows = json.loads(download(f"{URL}?{urlencode(params)}"))
    except OSError as exc:
        return {}, str(exc)
    bars = {}
    for row in rows:
        delta = row[0] - millis(START)
        assert 0 <= delta < millis(STOP) - millis(START) and delta % 86400000 == 0
        day = START + timedelta(days=delta // 86400000)
        o, h, lo, c = map(float, row[1:5])
        if 0 < lo <= min(o, c) <= max(o, c) <= h and int(row[8]) > 0:
            bars[day.isoformat()] = [o, h, lo, c, float(row[7]), int(row[8])]
    return bars, None


def acquire():
    original = gzip.decompress(spot_volume.INPUT.read_bytes())
    markets = json.loads(original)["markets"]
    october = {symbol: {d: bar for d, bar in bars.items() if d.startswith("2026-10")}
               for symbol, bars in markets.items()}
    rank = sorted((-median(bar[4] for bar in bars.values()), symbol)
                  for symbol, bars in october.items() if len(bars) >= 25)
    selected = [symbol for negative_volume, symbol in rank if negative_volume <= -1_000_000]
    cached = json.loads(gzip.decompress((HERE / "spot_november_inputs.json.gz").read_bytes()))
    def fetch(symbol):
        if symbol in cached["markets"] and symbol not in cached["failures"]:
            return {d: row for d, row in cached["markets"][symbol].items() if d.startswith("2026-11")}, None
        return collect(symbol)

    with ThreadPoolExecutor(6) as pool:
        recent = list(pool.map(fetch, selected))
    output = {"source": URL, "warmup_sha256": hashlib.sha256(original).hexdigest(),
              "markets": {}, "failures": {}, "november_bar_counts": {}}
    for symbol, (bars, error) in zip(selected, recent):
        output["markets"][symbol] = {**october[symbol], **bars}
        output["november_bar_counts"][symbol] = len(bars)
        if error:
            output["failures"][symbol] = error
    INPUT.write_bytes(gzip.compress(json.dumps(output).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    source = json.loads(raw)
    markets = {symbol: {date.fromisoformat(d): bar for d, bar in rows.items()}
               for symbol, rows in source["markets"].items()}
    output = {"partial_month": True, "input_sha256": hashlib.sha256(raw).hexdigest(),
              "failures": source["failures"], "november_bar_counts": source["november_bar_counts"], "rules": {}}
    for name, rule in (("flush", spot_flush), ("volume", spot_volume), ("activity", spot_activity)):
        choices = {day: row for day, row in rule.candidates(markets).items() if START <= day < STOP}
        output["rules"][name] = {case: spot_volume.evaluate(choices, markets, ["2026-11"], cost)
                                 for case, cost in (("base", BASE_COST), ("stress", STRESS_COST))}
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
