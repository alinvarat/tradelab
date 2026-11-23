"""Apply a fixed CPI-release calendar gate to the original BTC weekly option."""
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime
from statistics import median
from zoneinfo import ZoneInfo

from .options_rotation import choices, inputs, replay
from .options_weekly import HERE, UTC

CALENDAR = HERE / "options_cpi_releases.json"


def main():
    packed = CALENDAR.read_bytes()
    dates = [datetime.strptime(s, "%m%d%Y").replace(hour=8, minute=30, tzinfo=ZoneInfo("America/New_York"))
             for s in json.loads(packed)]
    months = [f"2025-{m:02d}" for m in range(1,10)] + [f"2026-{m:02d}" for m in range(1,11)]
    grouped, sales, sources = inputs()
    chosen, eligible = defaultdict(list), defaultdict(list)
    release_matches = {}
    for month, weeks in choices(grouped).items():
        if month not in months:
            continue
        for week in weeks:
            btc = next((x for x in week if x[1] == "BTC"), None)
            if btc is None:
                continue
            row = btc[2]
            decision = row["chosen_at"] / 1000
            expiry = datetime.fromisoformat(row["expiry"]).replace(hour=8, tzinfo=UTC).timestamp()
            eligible[month].append([btc])
            if matches := [d.isoformat() for d in dates if decision < d.timestamp() < expiry]:
                chosen[month].append([btc])
                release_matches[row["entry_day"]] = matches
    output = {"input_sha256": sources, "calendar_sha256": hashlib.sha256(packed).hexdigest(),
              "release_matches": release_matches, "periods": {}}
    for label, dates in (("2025", months[:9]), ("2026", months[9:]), ("continuous", months)):
        row = output["periods"][label] = {}
        for target in (3,6):
            for friction, costs in (("base",(.15,.05)),("stress",(.35,.15))):
                result = row[f"{target}x_{friction}"] = replay(chosen,sales,dates,target,costs,detail=True)
                rng = random.Random(51153)
                draws = []
                for _ in range(500):
                    rng_weeks = {m: [eligible[m][i] for i in sorted(rng.sample(range(len(eligible[m])),len(chosen[m])))]
                                 for m in dates}
                    draws.append(replay(rng_weeks,sales,dates,target,costs)["end"])
                result["random_median_end"] = median(draws)
                result["random_fraction_ge"] = sum(v >= result["end"] for v in draws)/len(draws)
    (HERE / "options_cpi_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
