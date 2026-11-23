"""Measure next-session GLD returns after a frozen GVZ shock."""
import csv
import gzip
import hashlib
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.data import get_json, http_get
from .vix_fear import END, HERE, study

INPUT = HERE / "gold_fear_inputs.json.gz"
RESULT = HERE / "gold_fear_results.json"
GVZ = "https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv"
PRICE = "https://query1.finance.yahoo.com/v8/finance/chart/GLD"


def acquire():
    index = {
        datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat(): float(row["GVZ"])
        for row in csv.DictReader(http_get(GVZ).decode("utf-8-sig").splitlines())
    }
    start = int(datetime(2018, 12, 1, tzinfo=timezone.utc).timestamp())
    stop = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())
    chart = get_json(f"{PRICE}?period1={start}&period2={stop}&interval=1d")["chart"]["result"][0]
    quote = chart["indicators"]["quote"][0]
    ny = ZoneInfo("America/New_York")
    bars = []
    for t, o, c in zip(chart["timestamp"], quote["open"], quote["close"]):
        day = datetime.fromtimestamp(t, ny).date().isoformat()
        if day <= END and o and c:
            bars.append({"d": day, "o": o, "c": c, "gvz": index.get(day)})
    INPUT.write_bytes(gzip.compress(json.dumps({"sources": [GVZ, PRICE], "bars": bars}).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    rows = json.loads(raw)["bars"]
    days = [row["d"] for row in rows]
    assert days == sorted(set(days)) and days[0] <= "2018-12-03" and days[-1] == "2026-10-30"
    signals = {
        i for i in range(1, len(rows))
        if rows[i]["gvz"] and rows[i - 1]["gvz"] and rows[i]["gvz"] >= 1.2 * rows[i - 1]["gvz"]
    }
    result = {"input_sha256": hashlib.sha256(raw).hexdigest(),
              "missing_gvz_days": [r["d"] for r in rows if r["gvz"] is None], "periods": {}}
    for period, start, end in (("reference", "2019-01-01", "2022-12-31"),
                               ("holdout", "2023-01-01", END), ("continuous", "2019-01-01", END)):
        result["periods"][period] = {
            name: study(rows, signals, start, end, friction, delay)
            for name, friction, delay in (("base", .0025, 1), ("stress", .005, 1), ("delay", .005, 2))
        }
    RESULT.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
