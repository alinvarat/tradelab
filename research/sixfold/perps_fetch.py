"""Retrieve, verify and freeze public Binance futures trades, marks and funding."""
import csv
import gzip
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = "https://data.binance.vision/data/futures/um/monthly/"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
MONTHS = ["2020-12"] + [f"{year}-{month:02}" for year in range(2021, 2026) for month in range(1, 13)]
KINDS = ("klines", "markPriceKlines", "fundingRate")


def fetch(job):
    instrument, month, kind = job
    path = (f"{kind}/{instrument}/{instrument}-fundingRate-{month}.zip" if kind == "fundingRate"
            else f"{kind}/{instrument}/15m/{instrument}-15m-{month}.zip")
    req = Request(ROOT + path, headers={"User-Agent": "TradeLab research"})
    for n in range(4):
        try:
            with urlopen(req, timeout=20) as response:
                raw = response.read()
            with ZipFile(io.BytesIO(raw)) as archive:
                with archive.open(archive.namelist()[0]) as source:
                    rows = [row for row in csv.reader(io.TextIOWrapper(source))
                            if row and row[0].isdigit()]
            selected = 3 if kind == "fundingRate" else 5
            parsed = [[int(row[0]), *map(float, row[1:selected])] for row in rows]
            assert parsed
            return job, parsed, hashlib.sha256(raw).hexdigest()
        except (OSError, ValueError) as err:
            if n == 3:
                raise RuntimeError(path) from err
            time.sleep(n + 1)
    raise RuntimeError(path)


def main():
    jobs = [(symbol, month, kind) for month in MONTHS for symbol in SYMBOLS for kind in KINDS]
    inputs = {symbol: {kind: [] for kind in KINDS} for symbol in SYMBOLS}
    checksums = {}
    with ThreadPoolExecutor(max_workers=18) as pool:
        for (instrument, month, kind), rows, sha in pool.map(fetch, jobs):
            inputs[instrument][kind].extend(rows)
            checksums[f"{instrument}/{month}/{kind}"] = sha
    for symbol, snapshot in inputs.items():
        for kind in KINDS:
            snapshot[kind].sort()
            d = [r[0] for r in snapshot[kind]]
            assert d == sorted(set(d)), (symbol, kind, "duplicate timestamps")
        market = snapshot["klines"]
        mark = snapshot["markPriceKlines"]
        start = min(market[0][0], mark[0][0])
        end = max(market[-1][0], mark[-1][0])
        timeline = set(range(start, end + 900_000, 900_000))
        print(symbol, "missing trade marks", len(timeline - {x[0] for x in market}),
              "missing mark prices", len(timeline - {x[0] for x in mark}),
              "sample times", sorted(timeline - {x[0] for x in market})[:10],
              sorted(timeline - {x[0] for x in mark})[:10], flush=True)
        for rows in [market, mark]:
            assert all(low > 0 and high >= max(open_, close) and min(open_, close) >= low
                       for _, open_, high, low, close in rows), symbol
        raw = json.dumps(snapshot, separators=(",", ":")).encode()
        path = HERE / f"perps_{symbol}_inputs.json.gz"
        path.write_bytes(gzip.compress(raw, mtime=0))
        print(symbol, len(market), len(snapshot["fundingRate"]), hashlib.sha256(raw).hexdigest())
    (HERE / "perps_sources.json").write_text(json.dumps({"base_url": ROOT, "archive_sha256": checksums}, indent=2) + "\n")


if __name__ == "__main__":
    main()
