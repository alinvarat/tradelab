"""Check public aggregate trades around the near-target ALPACA daily bar."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from zipfile import ZipFile

from .spot import BASE_COST, HERE, STRESS_COST
from .spot_inputs import ARCHIVE, download

SYMBOL = "ALPACAUSDT"
DAY = "2025-04-30"
URL = f"{ARCHIVE}/data/spot/daily/aggTrades/{SYMBOL}/{SYMBOL}-aggTrades-{DAY}.zip"
START = int(datetime.fromisoformat(DAY).replace(tzinfo=timezone.utc).timestamp()) * 1000
END = START + 86_400_000


def observations(tape):
    windows = {"first": [], "second": [], "last": [], "penultimate": []}
    with ZipFile(io.BytesIO(tape)) as archive:
        with archive.open(archive.namelist()[0]) as member:
            for row in csv.reader(io.TextIOWrapper(member, encoding="utf-8")):
                if not row[0].isdigit():
                    continue
                stamp = int(row[5])
                if stamp >= 10**14:
                    stamp //= 1000
                offset = stamp - START
                label = {0: "first", 1: "second", 1438: "penultimate", 1439: "last"}.get(offset // 60000)
                if label:
                    windows[label].append((stamp, float(row[1]), float(row[2]), row[6].lower() == "true"))
    return windows


def consume(records, amount, buy):
    filled = cost = 0.
    count = 0
    for _, price, size, buyer_maker in records:
        if buyer_maker == buy:
            continue
        qty = min(size, (amount - cost) / price if buy else amount - filled)
        filled += qty
        cost += qty * price
        count += 1
        if (cost if buy else filled) >= amount * (1 - 1e-12):
            return {"base_units": filled, "quote_units": cost, "vwap": cost / filled, "observed_prints": count}
    return {"base_units": filled, "quote_units": cost, "vwap": cost / filled if filled else None,
            "observed_prints": count, "unfilled": max(0, amount - (cost if buy else filled))}


def main():
    archive = HERE / f"spot_flush_{SYMBOL}-{DAY}.zip"
    if not archive.exists():
        archive.write_bytes(download(URL))
    wire = archive.read_bytes()
    windows = observations(wire)
    output = {"source": URL, "sha256": hashlib.sha256(wire).hexdigest(),
              "first_trade": windows["first"][0], "last_trade": windows["last"][-1],
              "assumptions": "Aggressor trade capacity proxy, no historical quotes or order queue",
              "cases": {}}
    for name, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
        for label, start, finish in (("boundary", "first", "last"),
                                     ("buffer", "second", "penultimate")):
            entry = consume(windows[start], 147 / (1 + cost), True)
            exit_ = consume(windows[finish], entry["base_units"], False)
            output["cases"][f"{name}_{label}"] = {"buy": entry, "sell": exit_,
                "liquidated_fraction": exit_["base_units"] / entry["base_units"],
                "multiple": (exit_["quote_units"] * (1 - cost) / 147
                             if exit_.get("unfilled", 0) == 0 and entry.get("unfilled", 0) == 0 else None)}
    (HERE / "spot_flush_execution_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
