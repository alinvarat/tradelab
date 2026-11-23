"""Compare paired weekly options with a fixed budget using archived prints."""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from math import floor

from .options import CONVERSION, WALLET
from .options_fetch import HERE
from .options_weekly import SNAPSHOT


def quote(row, markup):
    legs = [row["options"].get("20" + side) for side in "CP"]
    if any(not leg or not leg["first_print"] for leg in legs):
        return "missing_leg", None
    prints = [leg["first_print"] for leg in legs]
    if abs(prints[0]["timestamp"] - prints[1]["timestamp"]) > 60_000:
        return "prints_over_60_seconds_apart", None
    steps = {leg["spec"]["min_trade_amount"] for leg in legs}
    if len(steps) != 1:
        raise ValueError("Different minimum increments in paired legs")
    step = steps.pop()
    cost, payout = 0, 0
    settlement = row["official_settlement_usd"]
    for side, leg, trade in zip((1, -1), legs, prints):
        premium = trade["price"] * (1 + markup)
        fee = min(leg["spec"]["taker_commission"], .125 * premium)
        cost += (premium + fee) * trade["index_price"] * (1 + CONVERSION)
        intrinsic = max(0, side * (settlement - leg["strike"]) / settlement)
        payout += (intrinsic - min(.00015, .125 * intrinsic)) * settlement * (1 - CONVERSION)
    capacity = min(floor(trade["amount"] / step + 1e-10) for trade in prints)
    return "paired", (step, cost, payout, capacity)


def simulate(months, start_fresh):
    balance = peak = WALLET
    drawdown = 0
    path = []
    counts = Counter()
    for month, weeks in months.items():
        if start_fresh:
            balance = WALLET
        start = balance
        for status, pair in weeks:
            if pair is None:
                counts[status] += 1
                continue
            step, cost, payout, capacity = pair
            units = step * min(capacity, floor(balance * .5 / (step * cost) + 1e-10))
            counts["filled_proxy" if units else "over_budget"] += 1
            balance += units * (payout - cost)
        path.append({"month": month, "start": start, "end": balance, "multiple": balance / start})
        peak = max(peak, balance)
        drawdown = max(drawdown, 1 - balance / peak)
    return {
        "months": path, "status_counts": counts, "3x_months": sum(x["multiple"] >= 3 for x in path),
        "6x_months": sum(x["multiple"] >= 6 for x in path),
        "half_loss_months": sum(x["multiple"] <= .5 for x in path),
        "minimum_multiple": min(x["multiple"] for x in path),
        "max_month_end_drawdown": None if start_fresh else drawdown,
    }


def main():
    packed = gzip.decompress(SNAPSHOT.read_bytes())
    result = {"snapshot_sha256": hashlib.sha256(packed).hexdigest(), "assets": {}}
    for asset, values in json.loads(packed)["assets"].items():
        cases = result["assets"][asset] = {}
        for year in ("2025", "2026"):
            for label, markup in (("base", .15), ("stress", .35)):
                months = defaultdict(list)
                for row in values["rows"]:
                    if row["month"].startswith(year):
                        months[row["month"]].append(quote(row, markup))
                cases[f"{year}_{label}"] = {
                    "reset": simulate(months, True), "continuous": simulate(months, False),
                }
    (HERE / "options_pair_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
