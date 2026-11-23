"""Test fixed 3× and 6× early exits using actual sell-aggressor option prints."""
import argparse
import gzip
import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from statistics import mean, median
from functools import partial

from .options import CONVERSION, WALLET, analyze_month
from .options_fetch import HERE, HISTORY, ms, trade_range
from .options_transfer import PERIODS, SNAPSHOT

SALES = HERE / "options_exit_sales.json.gz"
MIN_HOLD = 15 * 60_000


def tape(symbol, begin, end):
    batch = trade_range(symbol, begin, end)
    if not batch["has_more"]:
        return batch["trades"]
    if begin >= end:
        raise ValueError(f"Too many prints in one millisecond: {symbol}")
    split = (begin + end) // 2
    return tape(symbol, begin, split) + tape(symbol, split + 1, end)


def get_sample(row_side):
    row, side = row_side
    sample = row["options"]["20" + side]
    first = sample["first_print"]
    spec = sample["spec"]
    symbol = sample["name"]
    begin = first["timestamp"] + MIN_HOLD
    end = spec["expiration_timestamp"] - 1
    assert end == ms(datetime.fromisoformat(row["expiry"] + "T08:00:00").replace(tzinfo=timezone.utc)) - 1
    trades = tape(symbol, begin, end)
    if len({tr["trade_id"] for tr in trades}) != len(trades):
        raise ValueError(f"Archive returned duplicate IDs for {symbol}")
    sales = [tr for tr in trades if tr["direction"] == "sell"
             and not any(tr.get(flag) for flag in ("block_trade_id", "combo_id", "liquidation"))]
    if not all(begin <= t["timestamp"] <= end for t in sales):
        raise ValueError(f"Archive boundary mismatch for {symbol}")
    return symbol, sorted(sales, key=lambda tr: (tr["timestamp"], tr["trade_seq"]))


def acquisition(series):
    targets = [(row, side) for rows in series.values() for row in rows for side in "CP"
               if row["options"].get("20" + side, {}).get("first_print")]
    with ThreadPoolExecutor(max_workers=5) as pool:
        observations = dict(pool.map(get_sample, targets))
    assert len(observations) == len(targets), "unexpected repeated contract"
    raw = json.dumps({"archive": HISTORY, "sales": observations}, separators=(",", ":")).encode()
    SALES.write_bytes(gzip.compress(raw, mtime=0))
    print(f"Captured {sum(map(len, observations.values()))} option sales across {len(targets)} contracts", flush=True)


def one(row, sales, limit, markup, haircut, balance=WALLET, side=None, budget_fraction=1.0):
    result = analyze_month(row, 20, markup, budget_fraction, starting=balance, side_override=side)
    result["month"] = row["month"]
    result["starting"] = balance
    if result["status"] != "filled_proxy":
        return result
    result["modeled_exit"] = "expiry"
    units = result.pop("amount_btc_contracts")
    result["contract_units"] = units
    remaining = balance - result["spent_usd"]
    spec = row["options"]["20" + result["side"]]["spec"]
    for sale in sales[result["instrument"]]:
        if sale["amount"] < units:
            continue
        premium = sale["price"] * (1 - haircut)
        fee = min(spec["taker_commission"], 0.125 * premium)
        net = units * (premium - fee) * sale["index_price"] * (1 - CONVERSION)
        if remaining + net >= limit * balance:
            result.update({"modeled_exit": "early", "sale_print": sale,
                           "net_if_sold_on_print": remaining + net,
                           "ending": limit * balance})
            return result
    return result


def evaluate(rows, sales, target, friction):
    calculate = partial(one, sales=sales, limit=target, markup=friction[0], haircut=friction[1])
    resets = [calculate(row) for row in rows]
    continuous = []
    balance = WALLET
    for row in rows:
        balance_row = calculate(row, balance=balance)
        continuous.append(balance_row)
        balance = balance_row["ending"]
    hits = sum(r["ending"] >= target * WALLET for r in resets)
    choices = [[calculate(row, side=side)["ending"] >= target * WALLET for side in "CP"] for row in rows]
    rng = random.Random(10228)
    control = [sum(rng.choice(p) for p in choices) for _ in range(3000)]
    stats = {"months": len(rows), "hits": hits,
             "early_exits": sum(r.get("modeled_exit") == "early" for r in resets),
             "loss_half": sum(r["ending"] <= 0.5 * WALLET for r in resets),
             "median_multiple": median(r["ending"] / WALLET for r in resets),
             "max_multiple": max(r["ending"] / WALLET for r in resets),
             "continuous_ending": balance / WALLET,
             "continuous_target_months": sum(r["starting"] > 0 and r["ending"] >= target * r["starting"] for r in continuous),
             "random_direction_mean": mean(control),
             "random_direction_p": (1 + sum(n >= hits for n in control)) / (len(control) + 1)}
    return {"summary": stats, "monthly": resets, "continuous": continuous}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    series = json.loads(raw)["series"]
    if args.refresh or not SALES.exists():
        acquisition(series)
    raw_tape = gzip.decompress(SALES.read_bytes())
    sales = json.loads(raw_tape)["sales"]
    report = {"option_snapshot_sha256": hashlib.sha256(raw).hexdigest(),
              "sales_snapshot_sha256": hashlib.sha256(raw_tape).hexdigest(), "assets": {}}
    for asset, data in series.items():
        results = report["assets"][asset] = {}
        for period, (start, stop) in PERIODS.items():
            rows = [r for r in data if start <= r["month"] <= stop]
            results[period] = {}
            for limit in (3, 6):
                for cost, friction in (("base", (0.15, 0.05)), ("stress", (0.35, 0.15))):
                    name = f"{limit}x_{cost}"
                    output = results[period][name] = evaluate(rows, sales, limit, friction)
                    print(asset, period, name, output["summary"], flush=True)
    (HERE / "options_exit_results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
