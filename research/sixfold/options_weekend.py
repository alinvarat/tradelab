"""Transfer a pre-Monday weekend-only direction signal to BTC option tape."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from .options_fetch import HERE
from .options_vix import run
from .options_weekly import SNAPSHOT
from .spot_volume import INPUT as SPOT


def schedule(rows, bars):
    chosen = defaultdict(list)
    for row in rows:
        monday = date.fromisoformat(row["entry_day"])
        before, after = (bars.get((monday-timedelta(days=d)).isoformat()) for d in (3,1))
        if not before or not after or before[3] == after[3]:
            continue
        chosen[row["month"]].append((row, "C" if after[3] > before[3] else "P"))
    return chosen


def main():
    weekly = gzip.decompress(SNAPSHOT.read_bytes())
    spot = gzip.decompress(SPOT.read_bytes())
    btc = json.loads(weekly)["assets"]["BTC"]
    plan = schedule(btc["rows"], json.loads(spot)["markets"]["BTCUSDT"])
    months = [f"{y}-{m:02d}" for y,n in ((2025,12),(2026,10)) for m in range(1,n+1)]
    output = {"input_sha256": [hashlib.sha256(raw).hexdigest() for raw in (weekly,spot)],
              "weeks": sum(map(len,plan.values())), "periods": {}}
    for label, period in (("2025",months[:12]), ("2026",months[12:]), ("continuous",months)):
        cases = output["periods"][label] = {}
        for target in (3,6):
            for name, costs in (("base",(.15,.05)),("stress",(.35,.15))):
                result = cases[f"{target}x_{name}"] = run(plan,period,btc["sales"],target,costs,detail=True)
                rng = random.Random(92451)
                controls = [run(plan,period,btc["sales"],target,costs,rng)["end"] for _ in range(500)]
                result["random_median_end"] = median(controls)
                result["random_fraction_ge"] = sum(x>=result["end"] for x in controls)/len(controls)
    (HERE / "options_weekend_results.json").write_text(json.dumps(output,indent=2)+"\n")


if __name__ == "__main__":
    main()
