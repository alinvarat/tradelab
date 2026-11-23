"""Compare a fixed cross-asset agreement gate with the original BTC rule."""
import json
import random
from collections import defaultdict
from statistics import median

from .options_rotation import choices, inputs, replay
from .options_weekly import HERE


def split(grouped):
    candidate = defaultdict(list)
    comparison = defaultdict(list)
    for month, weeks in choices(grouped).items():
        for week in weeks:
            rows = {asset: (strength, asset, row) for strength, asset, row in week}
            if "BTC" in rows:
                comparison[month].append([rows["BTC"]])
            if rows.keys() != {"BTC", "ETH"}:
                continue
            changes = [row["indices"][1]["index_price"] - row["indices"][0]["index_price"]
                       for _, _, row in rows.values()]
            if changes[0] * changes[1] > 0:
                candidate[month].append([rows["BTC"]])
    return candidate, comparison


def main():
    grouped, sales, hashes = inputs()
    candidate, comparison = split(grouped)
    months = [f"{y}-{m:02d}" for y,n in ((2025,12),(2026,11)) for m in range(1,n+1)]
    output = {"input_sha256": hashes, "november_partial": True,
              "eligible_weeks": {m: [len(candidate[m]), len(comparison[m])] for m in months}, "cases": {}}
    for period, selected in (("2025", months[:12]), ("2026", months[12:]), ("continuous", months)):
        cases = output["cases"][period] = {}
        for target in (3,6):
            for label, costs in (("base",(.15,.05)),("stress",(.35,.15))):
                row = cases[f"{target}x_{label}"] = {
                    name: replay(weeks, sales, selected, target, costs, detail=True)
                    for name, weeks in (("agreement", candidate), ("all_btc", comparison))
                }
                rng = random.Random(81479)
                draws = []
                for _ in range(500):
                    subsample = {m: [comparison[m][i] for i in sorted(
                        rng.sample(range(len(comparison[m])), len(candidate[m])))] for m in selected}
                    draws.append(replay(subsample, sales, selected, target, costs)["end"])
                row["random_skip"] = {"draws": len(draws), "median_end": median(draws),
                                      "fraction_at_least_agreement": sum(
                                          x >= row["agreement"]["end"] for x in draws) / len(draws)}
    (HERE / "options_agreement_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
