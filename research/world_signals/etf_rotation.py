"""Test a cash-or-one-fund rotation and its perfect-timing ceiling."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from math import prod
from statistics import median

from .vix_fear import HERE, months_in, summarize

INPUTS = {
    "BITX": ("bitx_fomc", "bitx_fomc_2026"),
    "GLD": ("gold_fear",),
    "USO": ("oil_fear",),
    "UVXY": ("vix_fear",),
}
START = "2023-07-01"
END = "2026-10-31"


def load():
    books, hashes = {}, {}
    for symbol, snapshots in INPUTS.items():
        book = {}
        for name in snapshots:
            source = gzip.decompress((HERE / f"{name}_inputs.json.gz").read_bytes())
            hashes[name] = hashlib.sha256(source).hexdigest()
            bars = json.loads(source)["bars"]
            if isinstance(bars, list):
                bars = {x["d"]: [x["o"], x["c"]] for x in bars}
            assert not set(book) & set(bars)
            book.update({day: close / op for day, (op, close) in bars.items()})
        books[symbol] = book
    return books, hashes


def run(days, books, cost, start, end):
    factor = (1 - cost) / (1 + cost)
    months = list(months_in(start, end))
    events, menus, trades = [], [], []
    ceiling = defaultdict(list)
    for i, day in enumerate(days):
        if not start <= day <= end:
            continue
        current = [book[day] * factor for book in books.values()]
        ceiling[day[:7]].append(max(1.0, *current))
        if i < 5:
            continue
        trails = days[i-5:i]
        score, symbol = min((-prod(book[d] for d in trails), symbol)
                            for symbol, book in books.items())
        if -score >= 1.05:
            net = books[symbol][day] * factor - 1
            events.append((day, net))
            trades.append([day, symbol, net])
            menus.append(current)
    output = summarize(events, months)
    output["ending_thb_after_fx"] = output["balance_thb"] * .995**2
    output["trades"] = trades
    output["perfect_months"] = {m: prod(ceiling[m]) for m in months}
    rng = random.Random(47050)
    draws = [5000 * .995**2 * prod(rng.choice(x) for x in menus) for _ in range(1000)]
    output["random_ending_median_thb"] = median(draws)
    output["random_fraction_ge"] = sum(x >= output["ending_thb_after_fx"] for x in draws) / len(draws)
    return output


def main():
    books, hashes = load()
    days = sorted(set.intersection(*(set(x) for x in books.values())))
    result = {"input_sha256": hashes, "overlap_sessions": len(days), "periods": {}}
    for label, start, end in (("reference", START, "2024-12-31"),
                              ("holdout", "2025-01-01", END), ("continuous", START, END)):
        result["periods"][label] = {k: run(days, books, fee, start, end)
                                    for k, fee in (("base", .0025), ("stress", .005))}
    (HERE / "etf_rotation_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
