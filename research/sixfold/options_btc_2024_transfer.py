"""Transfer the original index trend and VIX directions to 2024 option prints."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from statistics import median

from .options_vix import VIX, rules, run
from .options_weekend_2024 import HERE, INPUT


def original(rows):
    chosen = defaultdict(list)
    for row in rows:
        previous, current = row["indices"]
        if not previous or not current:
            continue
        change = current["index_price"] - previous["index_price"]
        if change:
            chosen[row["month"]].append((row, "C" if change > 0 else "P"))
    return chosen


def main():
    raw, vraw = [gzip.decompress(p.read_bytes()) for p in (INPUT,VIX)]
    data = json.loads(raw)
    vix = json.loads(vraw)["indices"]["VIX"]
    months = [f"2024-{month:02d}" for month in range(1,13)]
    output = {"sha256": [hashlib.sha256(r).hexdigest() for r in (raw,vraw)], "rules": {}}
    for label, plan in (("trend",original(data["rows"])),("vix",rules(data["rows"],vix))):
        results = output["rules"][label] = {"eligible_weeks":sum(map(len,plan.values())), "cases":{}}
        for target in (3,6):
            for name,costs in (("base",(.15,.05)),("stress",(.35,.15))):
                row = results["cases"][f"{target}x_{name}"] = run(plan,months,data["sales"],target,costs,detail=True)
                rng = random.Random(60777)
                draws = [run(plan,months,data["sales"],target,costs,rng)["end"] for _ in range(500)]
                row["random_median_end"] = median(draws)
                row["random_fraction_ge"] = sum(d>=row["end"] for d in draws)/len(draws)
    (HERE / "options_btc_2024_transfer_results.json").write_text(json.dumps(output,indent=2)+"\n")


if __name__ == "__main__":
    main()
