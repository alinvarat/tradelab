"""Replay fixed BTC/ETH weekly rotation in one simulated wallet."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from statistics import median

from .options import WALLET
from .options_fetch import HERE
from .options_weekly import SNAPSHOT, month_run, reached


def inputs():
    prior = gzip.decompress(SNAPSHOT.read_bytes())
    assets = json.loads(prior)["assets"]
    grouped, sales = defaultdict(dict), {}
    hashes = {"historical": hashlib.sha256(prior).hexdigest()}
    for asset, items in assets.items():
        for row in items["rows"]:
            grouped[row["entry_day"]][asset] = row
        sales.update(items["sales"])
    for asset, file in (("BTC","options_november_inputs.json.gz"), ("ETH","options_eth_november_inputs.json.gz")):
        raw = gzip.decompress((HERE / file).read_bytes())
        hashes[asset] = hashlib.sha256(raw).hexdigest()
        rows, tape = json.loads(raw)
        for row in rows:
            grouped[row["entry_day"]][asset] = row
        sales.update(tape)
    return grouped, sales, hashes


def choices(grouped):
    output = defaultdict(list)
    for day, picks in sorted(grouped.items()):
        valid = []
        for asset, row in sorted(picks.items()):
            previous, current = row["indices"]
            if previous and current:
                strength = abs(current["index_price"] / previous["index_price"] - 1)
                valid.append((strength, asset, row))
        if valid:
            output[day[:7]].append(sorted(valid, key=lambda x: (-x[0], x[1])))
    return output


def replay(choices, sales, months, target, costs, rng=None, detail=False):
    balance = peak = WALLET
    drawdown = 0
    funded_hits = hits = 0
    rows = []
    for month in months:
        start = balance
        selected = [(rng.choice(picks) if rng else picks[0]) for picks in choices[month]]
        balance, trades = month_run([row for _, _, row in selected], sales, target, costs, balance,
                                    detail=True, budget_fraction=.5)
        peak = max(peak, balance)
        drawdown = max(drawdown, 1-balance/peak)
        hit = reached(balance, target * start) if start > 0 else False
        if month != "2026-11":
            hits += hit
            funded_hits += hit and start >= WALLET
        if detail:
            rows.append({"month": month, "starting": start, "ending": balance, "trades": trades,
                         "selection": [[asset, row["entry_day"]] for _, asset, row in selected]})
    return {"end": balance, "hits_complete_months": hits, "funded_hits_complete_months": funded_hits,
            "drawdown_month_end": drawdown} | ({"months": rows} if detail else {})


def main():
    grouped, sales, hashes = inputs()
    months = [f"{y}-{m:02d}" for y, end in ((2025,12),(2026,11)) for m in range(1,end+1)]
    output = {"input_sha256": hashes, "november_partial": True, "periods": {}}
    selection = choices(grouped)
    for label, dates in (("2025",months[:12]), ("2026",months[12:]), ("continuous", months)):
        cases = output["periods"][label] = {}
        for target in (3,6):
            for friction, costs in (("base",(.15,.05)),("stress",(.35,.15))):
                v = cases[f"{target}x_{friction}"] = replay(selection,sales,dates,target,costs,detail=True)
                rng = random.Random(6109)
                draws = [replay(selection,sales,dates,target,costs,rng) for _ in range(1000)]
                v["random_median_end"] = median(d["end"] for d in draws)
                v["random_fraction_ge_end"] = sum(d["end"] >= v["end"] for d in draws)/len(draws)
    (HERE / "options_rotation_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
