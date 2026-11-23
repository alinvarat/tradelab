"""Measure concentration and month-block uncertainty of the frozen spot flush rule."""
import hashlib
import json
import random
from math import prod
from statistics import median

from .spot import HERE


def assess(case):
    months = case["months"]
    events = case["events"]
    wealth = case["ending_thb"]
    strongest = max(events, key=lambda row: row[2])
    leave_one = [wealth / x if x else prod(e[2] for j, e in enumerate(events) if j != i) * 5000
                 for i, (_, _, x) in enumerate(events)]
    rng = random.Random(18007)
    blocks = [growth for _, growth in months]
    outcomes = sorted(5000 * prod(rng.choices(blocks, k=len(blocks))) for _ in range(10000))
    return {"events": len(events), "positive_events": sum(e[2] > 1 for e in events),
            "strongest_event": strongest, "ending_without_strongest_thb": min(leave_one),
            "leave_one_paths_below_start": sum(end < 5000 for end in leave_one),
            "ending_without_best_month_thb": wealth / max(blocks),
            "bootstrap_months": len(blocks), "bootstrap_draws": len(outcomes),
            "bootstrap_median_thb": median(outcomes),
            "bootstrap_p05_thb": outcomes[499], "bootstrap_p95_thb": outcomes[9499],
            "bootstrap_below_start": sum(x < 5000 for x in outcomes) / len(outcomes)}


def main():
    raw = (HERE / "spot_flush_results.json").read_bytes()
    result = {"source_sha256": hashlib.sha256(raw).hexdigest(),
              "bootstrap_assumption": "Observed calendar months are resampled independently; descriptive, does not address regime changes or unseen extremes.",
              "periods": {period: {name: assess(case) for name, case in cases.items()}
                          for period, cases in json.loads(raw)["periods"].items()}}
    (HERE / "spot_flush_robustness_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
