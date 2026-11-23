"""Replay opening-flow on three additional complete months."""
import json
from datetime import date
from math import prod

from . import spot_opening_october as model

PERIODS = ((7, 6), (8, 7), (9, 8))


def main():
    results = {}
    for month, warmup in PERIODS:
        key = f"2026-{month:02d}"
        model.START = date(2026, month, 1)
        model.STOP = date(2026, month + 1, 1)
        model.WARMUP_MONTH = f"2026-{warmup:02d}"
        model.INPUT = model.HERE / f"spot_opening_{key}_inputs.json.gz"
        model.RESULT = model.HERE / f"spot_opening_{key}_results.json"
        model.main()
        results[key] = json.loads(model.RESULT.read_text())
        print(key, {case: (len(row["events"]), row["ending_thb"]) for case, row in results[key]["cases"].items()}, flush=True)
    summary = {case: 5000 * prod(r["cases"][case]["ending_thb"] / 5000 for r in results.values())
               for case in ("base", "stress")}
    path = model.HERE / "spot_opening_q3_results.json"
    path.write_text(json.dumps({"continuous_ending_thb": summary, "months": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
