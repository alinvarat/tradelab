"""Transfer the frozen weekend signal onto the 2024 BTC weekly option tape."""
import gzip
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from statistics import median

from .options_fetch import HERE, ms
from .options_weekend import SPOT, schedule
from .options_weekly import UTC, SNAPSHOT, capture, get_settlements, listed
from .options_vix import run

INPUT = HERE / "options_weekend_2024_inputs.json.gz"
RESULT = HERE / "options_weekend_2024_results.json"


def calendar():
    monday = datetime(2024,1,1,9,tzinfo=UTC)
    while monday.year == 2024:
        expiry = monday + timedelta(days=3,hours=23)
        if monday.month == expiry.month:
            yield monday, expiry
        monday += timedelta(days=7)


def acquire():
    windows = list(calendar())
    with ThreadPoolExecutor(6) as pool:
        cat_future = pool.submit(listed, "BTC", {ms(expiry) for _,expiry in windows})
        settlement_future = pool.submit(get_settlements, "BTC")
        catalogue, settlement = cat_future.result(), settlement_future.result()
        def fetch(window):
            return capture("BTC", window, catalogue, settlement)
        rows, sales = [], {}
        for row, tape in pool.map(fetch, windows):
            rows.append(row)
            sales.update(tape)
            if len(rows) % 10 == 0:
                print(len(rows), "of", len(windows), flush=True)
    INPUT.write_bytes(gzip.compress(json.dumps({"rows":rows,"sales":sales}).encode(),mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw, week_raw, spot_raw = [gzip.decompress(p.read_bytes()) for p in (INPUT, SNAPSHOT, SPOT)]
    early = json.loads(raw)
    later = json.loads(week_raw)["assets"]["BTC"]
    bars = json.loads(spot_raw)["markets"]["BTCUSDT"]
    plan = schedule(early["rows"]+later["rows"], bars)
    tape = early["sales"] | later["sales"]
    months = [f"{y}-{m:02d}" for y,n in ((2024,12),(2025,12),(2026,10)) for m in range(1,n+1)]
    out = {"input_sha256":[hashlib.sha256(v).hexdigest() for v in (raw,week_raw,spot_raw)],
           "2024_weeks":len(early["rows"]), "2024_sales":sum(map(len,early["sales"].values())),
           "cases":{}}
    for name, period in (("2024",months[:12]),("continuous",months)):
        cases = out["cases"][name] = {}
        for target in (3,6):
            for label, costs in (("base",(.15,.05)),("stress",(.35,.15))):
                row = cases[f"{target}x_{label}"] = run(plan,period,tape,target,costs,detail=True)
                if name == "2024":
                    rng = random.Random(72178)
                    draws = [run(plan,period,tape,target,costs,rng)["end"] for _ in range(500)]
                    row["random_median_end"] = median(draws)
                    row["random_fraction_ge"] = sum(x>=row["end"] for x in draws)/len(draws)
    RESULT.write_text(json.dumps(out,indent=2)+"\n")


if __name__ == "__main__":
    main()
