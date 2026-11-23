"""Capture closed November weeks and replay the frozen ETH weekly rule."""
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from itertools import product

from .options_fetch import HERE, ms
from .options_weekly import UTC, capture, get_settlements, listed, month_run

INPUT = HERE / "options_eth_november_inputs.json.gz"
RESULT = HERE / "options_eth_november_results.json"


def acquire():
    dates = []
    for day in (2, 9, 16):
        decision = datetime(2026, 11, day, 9, tzinfo=UTC)
        dates.append((decision, decision + timedelta(days=3, hours=23)))
    chains = listed("ETH", {ms(expiry) for _, expiry in dates})
    settlement = get_settlements("ETH")
    rows, tape = [], {}
    for pair in dates:
        row, sales = capture("ETH", pair, chains, settlement)
        rows.append(row)
        tape.update(sales)
    INPUT.write_bytes(gzip.compress(json.dumps([rows, tape]).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    rows, sales = json.loads(raw)
    prior_raw = (HERE / "options_budget_results.json").read_bytes()
    prior = json.loads(prior_raw)["assets"]["ETH"]["2026"]
    output = {"partial_month": True, "input_sha256": hashlib.sha256(raw).hexdigest(),
              "prior_result_sha256": hashlib.sha256(prior_raw).hexdigest(), "cases": {}}
    for target in (3, 6):
        for label, costs in (("base", (.15, .05)), ("stress", (.35, .15))):
            balance, fills = month_run(rows, sales, target, costs, 147, detail=True, budget_fraction=.5)
            controls = {
                "".join(sides): month_run(rows, sales, target, costs, 147, sides=sides, budget_fraction=.5)
                for sides in product("CP", repeat=len(rows))
            }
            key = f"{target}x_{label}"
            carried = prior[key + "_0.5_cap"]["continuous"][-1]["ending"]
            carried_end, carried_fills = month_run(rows, sales, target, costs, carried, detail=True, budget_fraction=.5)
            output["cases"][key] = {
                "balance": balance, "fills": fills, "random_direction_balances": controls,
                "carried_start": carried, "carried_end": carried_end, "carried_fills": carried_fills,
            }
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
