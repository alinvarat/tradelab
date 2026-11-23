"""Check what actual BITX bars permit under perfect, unrealizable timing."""
import gzip
import hashlib
import json
from collections import defaultdict
from math import prod

from .bitx_fomc import INPUT as ORIGINAL
from .bitx_fomc_2026 import INPUT as LATER
from .vix_fear import HERE


def calculate(bars, cost):
    factor = (1 - cost) / (1 + cost)
    sessions = defaultdict(list)
    previous = None
    for day, (open_, close) in sorted(bars.items()):
        month = day[:7]
        # Both legs must begin and end in one calendar month.
        overnight = open_ / previous[1] if previous and previous[0][:7] == month else 1
        intraday = close / open_
        sessions[month].append((intraday, overnight, open_, close))
        previous = (day, close)
    output = {}
    for month, legs in sessions.items():
        cash, shares = 1.0, 0.0
        for _, _, open_, close in legs:
            for price in (open_, close):
                cash, shares = (max(cash, shares * price * (1 - cost)),
                                max(shares, cash / (price * (1 + cost))))
        # Relax the execution constraints. Both legs can be selected independently
        # with no friction, which is an upper bound on either-leg trading.
        output[month] = {
            "intraday_after_cost": prod(max(1, day * factor) for day, _, _, _ in legs),
            "overnight_after_cost": prod(max(1, night * factor) for _, night, _, _ in legs),
            "combined_after_cost_bound": cash,
            "both_legs_zero_cost_bound": prod(max(1, day) * max(1, night) for day, night, _, _ in legs),
        }
    return output


def main():
    bars, inputs = {}, {}
    for path in (ORIGINAL, LATER):
        raw = gzip.decompress(path.read_bytes())
        inputs[path.name] = hashlib.sha256(raw).hexdigest()
        part = json.loads(raw)["bars"]
        assert not set(bars) & set(part)
        bars.update(part)
    output = {"sessions": len(bars), "inputs": inputs,
              "cases": {label: calculate(bars, cost) for label, cost in (("base", .0025), ("stress", .005))}}
    (HERE / "bitx_ceiling_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
