"""Replay weekly inverse options with the 3× and 6× monthly cash targets."""
import argparse
import gzip
import hashlib
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from statistics import mean, median

from .options import WALLET
from .options_exit import get_sample, one, tape
from .options_fetch import HERE, HISTORY, LIVE, ms, rpc
from .options_transfer import get_settlements, prior_index

UTC = timezone.utc
ASSETS = ("BTC", "ETH")
SNAPSHOT = HERE / "options_weekly_inputs.json.gz"


def calendar():
    day = datetime(2025, 1, 6, 9, tzinfo=UTC)
    last = datetime(2026, 10, 31, tzinfo=UTC)
    while day < last:
        expiry = (day + timedelta(days=4)).replace(hour=8)
        if day.month == expiry.month and expiry <= last:
            yield day, expiry
        day += timedelta(days=7)


def contract_for(chain, decision, spot, side):
    proposals = []
    for spec in chain:
        if spec["option_type"] != ("call" if side == "C" else "put") or spec["creation_timestamp"] > decision:
            continue
        distance = (spec["strike"] / spot - 1) * (1 if side == "C" else -1)
        if 0.06 <= distance <= 0.11:
            proposals.append((round(abs(distance - 0.085), 12), -distance, spec["instrument_name"], spec))
    return min(proposals)[-1] if proposals else None


def listed(asset, expiries):
    chains = defaultdict(list)
    for spec in rpc(HISTORY, "get_instruments", currency=asset, kind="option", expired="true"):
        expiry = spec["expiration_timestamp"]
        if expiry in expiries and spec["settlement_currency"] == asset:
            chains[expiry].append(spec)
    return chains


def capture(asset, dates, chains, settlement, index_provider=prior_index):
    start, expiry = dates
    decision = ms(start)
    current = index_provider(asset, decision)
    previous = index_provider(asset, ms(start - timedelta(days=7)))
    day = expiry.date().isoformat()
    row = {"month": start.strftime("%Y-%m"), "chosen_at": decision, "entry_day": start.date().isoformat(),
           "expiry": day, "indices": [previous, current], "options": {},
           "official_settlement_usd": settlement[day]}
    sales = {}
    if not current or not previous:
        return row, sales
    for side in "CP":
        spec = contract_for(chains.get(ms(expiry), ()), decision, current["index_price"], side)
        symbol = spec["instrument_name"] if spec else None
        sample = {"name": symbol, "spec": spec, "strike": spec["strike"] if spec else None, "first_print": None}
        row["options"]["20" + side] = sample  # schema shared with the monthly fill evaluator
        if not spec:
            continue
        trades = tape(symbol, decision, decision + 7_200_000)
        for tr in sorted(trades, key=lambda x: (x["timestamp"], x["trade_seq"])):
            if (tr["direction"] == "buy" and tr["amount"] >= spec["min_trade_amount"]
                    and not any(tr.get(k) for k in ("block_trade_id", "combo_id", "liquidation"))):
                sample["first_print"] = tr
                _, sales[symbol] = get_sample((row, side))
                break
    return row, sales


def acquire():
    weeks = list(calendar())
    expiries = {ms(expiry) for _, expiry in weeks}
    output = {"sources": [HISTORY, LIVE], "assets": {}}
    with ThreadPoolExecutor(max_workers=6) as pool:
        catalogues = {a: pool.submit(listed, a, expiries) for a in ASSETS}
        settlements = {a: pool.submit(get_settlements, a) for a in ASSETS}
        for a in ASSETS:
            chains = catalogues[a].result()
            settlement = settlements[a].result()
            jobs = [pool.submit(capture, a, pair, chains, settlement) for pair in weeks]
            rows, all_sales = [], {}
            for idx, job in enumerate(jobs, start=1):
                row, sales = job.result()
                rows.append(row)
                all_sales.update(sales)
                if idx % 20 == 0:
                    print(a, idx, "/", len(jobs), flush=True)
            output["assets"][a] = {"rows": rows, "sales": all_sales, "expiry_catalogues": len(chains)}
    raw = json.dumps(output, separators=(",", ":")).encode()
    SNAPSHOT.write_bytes(gzip.compress(raw, mtime=0))


def reached(balance, target):
    return balance >= target * (1 - 1e-12)


def month_run(rows, sales, target, friction, starting, sides=None, detail=False, budget_fraction=1.0, fill=one):
    cash = starting
    trades = []
    for i, row in enumerate(rows):
        if cash <= 0 or reached(cash, target * starting):
            break
        outcome = fill(row, sales, target * starting / cash, *friction, balance=cash,
                      side=sides[i] if sides else None, budget_fraction=budget_fraction)
        cash = outcome["ending"]
        if detail:
            trades.append({"entry_day": row["entry_day"], **outcome})
    return (cash, trades) if detail else cash


def assess(months, sales, target, friction, budget_fraction=1.0, fill=one):
    initial = WALLET
    rows = []
    single = []
    for month, entries in months.items():
        cash, fills = month_run(entries, sales, target, friction, WALLET, detail=True, budget_fraction=budget_fraction, fill=fill)
        rows.append({"month": month, "ending": cash, "weeks": fills})
        cash, fills = month_run(entries, sales, target, friction, initial, detail=True, budget_fraction=budget_fraction, fill=fill)
        single.append({"month": month, "starting": initial, "ending": cash, "weeks": fills})
        initial = cash
    hits = sum(reached(x["ending"], target * WALLET) for x in rows)
    rng = random.Random(10229)
    # Cache the at-most 32 possible direction permutations of each month.
    alternatives = []
    for entries in months.values():
        choices = []
        for code in range(2 ** len(entries)):
            sides = ["P" if code & (1 << i) else "C" for i in range(len(entries))]
            cash = month_run(entries, sales, target, friction, WALLET, sides=sides, budget_fraction=budget_fraction, fill=fill)
            choices.append(reached(cash, target * WALLET))
        alternatives.append(choices)
    controls = [sum(rng.choice(x) for x in alternatives) for _ in range(3000)]
    return {"summary": {"months": len(rows), "hits": hits,
                        "half_loss_months": sum(r["ending"] <= .5 * WALLET for r in rows),
                        "median_multiple": median(x["ending"] / WALLET for x in rows),
                        "continuous_multiple": initial / WALLET,
                        "continuous_target_months": sum(
                            x["starting"] > 0 and reached(x["ending"], target * x["starting"]) for x in single),
                        "months_with_entry": sum(any(w["status"] == "filled_proxy" for w in x["weeks"]) for x in rows),
                        "orders_modelled": sum(w["status"] == "filled_proxy" for x in rows for w in x["weeks"]),
                        "random_mean_hits": mean(controls),
                        "p_random_ge_observed": (1 + sum(x >= hits for x in controls)) / (len(controls) + 1)},
            "reset": rows, "continuous": single}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh or not SNAPSHOT.exists():
        acquire()
    packed = gzip.decompress(SNAPSHOT.read_bytes())
    data = json.loads(packed)["assets"]
    report = {"snapshot_sha256": hashlib.sha256(packed).hexdigest(), "assets": {}}
    for asset, values in data.items():
        output = report["assets"][asset] = {"eligible_calendar_weeks": len(values["rows"]),
                                          "observed_sales": sum(map(len, values["sales"].values()))}
        for year in ("2025", "2026"):
            months = defaultdict(list)
            for row in values["rows"]:
                if row["month"].startswith(year):
                    months[row["month"]].append(row)
            assert len(months) == (12 if year == "2025" else 10)
            outcomes = output[year] = {}
            for target in (3, 6):
                for label, friction in (("base", (0.15, 0.05)), ("stress", (0.35, 0.15))):
                    case = f"{target}x_{label}"
                    outcomes[case] = assess(months, values["sales"], target, friction)
                    print(asset, year, case, outcomes[case]["summary"], flush=True)
    (HERE / "options_weekly_results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
