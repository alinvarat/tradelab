"""Capture closed November weeks and replay the frozen BTC weekly rule."""
import gzip
import hashlib
import json
from datetime import datetime, timedelta
from itertools import product

from .options_fetch import HERE, ms
from .options_weekly import UTC, capture, get_settlements, listed, month_run

INPUT = HERE / "options_november_inputs.json.gz"
RESULT = HERE / "options_november_results.json"


def acquire():
    dates = []
    for day in (2, 9, 16):
        decision = datetime(2026, 11, day, 9, tzinfo=UTC)
        dates.append((decision, decision + timedelta(days=3, hours=23)))
    chains = listed("BTC", {ms(expiry) for _, expiry in dates})
    settlement = get_settlements("BTC")
    rows, tape = [], {}
    for pair in dates:
        row, sales = capture("BTC", pair, chains, settlement)
        rows.append(row)
        tape.update(sales)
    INPUT.write_bytes(gzip.compress(json.dumps([rows, tape]).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    rows, sales = json.loads(raw)
    output = {"partial_month": True, "input_sha256": hashlib.sha256(raw).hexdigest(), "cases": {}}
    for target in (3, 6):
        for label, costs in (("base", (.15, .05)), ("stress", (.35, .15))):
            balance, fills = month_run(rows, sales, target, costs, 147, detail=True, budget_fraction=.5)
            controls = {
                "".join(sides): month_run(rows, sales, target, costs, 147, sides=sides, budget_fraction=.5)
                for sides in product("CP", repeat=len(rows))
            }
            output["cases"][f"{target}x_{label}"] = {
                "balance": balance, "fills": fills, "random_direction_balances": controls,
            }
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
