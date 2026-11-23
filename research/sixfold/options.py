"""Evaluate archived Deribit inverse options bought once monthly in paper cash."""
import gzip
import hashlib
import json
import math
import random
from collections import Counter
from statistics import mean, median

from .options_fetch import HERE

WALLET = 147.0
CONVERSION = 0.0025
BASE_PRICE_OVER_PRINT = 0.15
STRESS_PRICE_OVER_PRINT = 0.35
RANDOM_DRAWS = 1000


def analyze_month(row, otm, price_over_print, budget_fraction, starting=WALLET, side_override=None):
    if not all(row["indices"]):
        return {"status": "missing_predecision_index", "ending": starting}
    previous, current = row["indices"]
    direction = (current["index_price"] > previous["index_price"]) - (
        current["index_price"] < previous["index_price"]
    )
    if not direction and side_override is None:
        return {"status": "unchanged_index", "ending": starting}
    side = side_override or ("C" if direction > 0 else "P")
    sample = row["options"][f"{otm}{side}"]
    base = {"instrument": sample["name"], "ending": starting}
    if sample["spec"] is None or sample["spec"]["creation_timestamp"] > row["chosen_at"]:
        return {"status": "instrument_not_listed_yet", **base}
    trade = sample["first_print"]
    if trade is None:
        return {"status": "no_eligible_trade_within_2h", **base}
    premium = trade["price"] * (1 + price_over_print)
    entry_fee = min(sample["spec"]["taker_commission"], 0.125 * premium)
    purchase = (premium + entry_fee) * trade["index_price"] * (1 + CONVERSION)
    step = sample["spec"]["min_trade_amount"]
    units = min(math.floor(starting * budget_fraction / (step * purchase) + 1e-10),
                math.floor(trade["amount"] / step + 1e-10)) * step
    quote = {"trade_timestamp": trade["timestamp"], "minimum_premium_with_cost_usd": step * purchase}
    if not units:
        return {"status": "minimum_order_over_budget", **base, **quote}
    settled = row["official_settlement_usd"]
    difference = settled - sample["strike"] if side == "C" else sample["strike"] - settled
    intrinsic_btc = max(0, difference / settled)
    delivery_fee = min(0.00015, 0.125 * intrinsic_btc)
    payment = units * (intrinsic_btc - delivery_fee) * settled * (1 - CONVERSION)
    spent = units * purchase
    return {**base, **quote, "status": "filled_proxy", "ending": round(starting - spent + payment, 12),
            "amount_btc_contracts": units, "spent_usd": spent, "settled_value_usd": payment,
            "settlement_index_usd": settled, "side": side}


def summarize(rows, continuous):
    numbers = [row["ending"] / WALLET for row in rows]
    status = Counter(row["status"] for row in rows)
    return {
        "months": len(numbers), "months_at_6x": sum(x >= 6 for x in numbers),
        "months_remaining_half_or_less": sum(x <= 0.5 for x in numbers),
        "months_remaining_tenth_or_less": sum(x <= 0.1 for x in numbers),
        "highest_month_multiple": max(numbers), "lowest_month_multiple": min(numbers),
        "median_month_multiple": median(numbers), "mean_month_multiple": mean(numbers),
        "continuous_total_multiple": continuous[-1]["ending"] / WALLET,
        "continuous_fills": sum(r["status"] == "filled_proxy" for r in continuous),
        "status_counts": status,
    }


def replay(source_rows, otm, price_over_print, budget_fraction):
    def calculate(budget, row):
        return {"month": row["month"], **analyze_month(row, otm, price_over_print, budget_fraction, budget)}

    def one_period(rows):
        independent = [calculate(WALLET, row) for row in rows]
        continuous = []
        wallet = WALLET
        for row in rows:
            current = calculate(wallet, row)
            continuous.append(current)
            wallet = current["ending"]
        return summarize(independent, continuous)

    periods = {
        "reference": one_period(source_rows[:36]),
        "holdout": one_period(source_rows[36:]),
        "2024": one_period(source_rows[36:48]),
        "2025": one_period(source_rows[48:]),
    }
    return periods, [calculate(WALLET, row) for row in source_rows]


def control(source_rows, observed_hits):
    rng = random.Random(20261123)
    possibilities = [
        [analyze_month(row, 20, BASE_PRICE_OVER_PRINT, 1, side_override=side)["ending"] / WALLET
         for side in "CP"]
        for row in source_rows[36:]
    ]
    hits = []
    medians = []
    for _ in range(RANDOM_DRAWS):
        numbers = [rng.choice(pair) for pair in possibilities]
        hits.append(sum(x >= 6 for x in numbers))
        medians.append(median(numbers))
    return {"draws": RANDOM_DRAWS, "mean_months_at_6x": mean(hits),
            "mean_of_median_multiple": mean(medians),
            "p_months_at_6x_at_least_observed": (1 + sum(x >= observed_hits for x in hits)) / (1 + RANDOM_DRAWS)}


def main():
    raw = gzip.decompress((HERE / "options_inputs.json.gz").read_bytes())
    rows = json.loads(raw)["rows"]
    variants = {
        name: replay(rows, otm, spread, budget)
        for name, otm, spread, budget in [
            ("main_otm20", 20, BASE_PRICE_OVER_PRINT, 1),
            ("stress_price_uplift", 20, STRESS_PRICE_OVER_PRINT, 1),
            ("closer_otm10", 10, BASE_PRICE_OVER_PRINT, 1),
            ("at_most_half_cash", 20, BASE_PRICE_OVER_PRINT, 0.5),
        ]
    }
    main_summary = variants["main_otm20"][0]
    holdout = main_summary["holdout"]
    random_control = control(rows, holdout["months_at_6x"])
    gates = {
        "6x_both_years": all(main_summary[y]["months_at_6x"] > 0 for y in ("2024", "2025")),
        "6x_in_stress": variants["stress_price_uplift"][0]["holdout"]["months_at_6x"] > 0,
        "sixfold_more_than_half_losses": holdout["months_at_6x"] > holdout["months_remaining_half_or_less"],
        "median_profitable": holdout["median_month_multiple"] > 1,
        "sixfold_outperforms_random": random_control["p_months_at_6x_at_least_observed"] < 0.05,
    }
    result = {"qualifies": all(gates.values()), "gates": gates, "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
              "control": random_control,
              "variants": {name: {"summary": summary, "monthly": monthly}
                           for name, (summary, monthly) in variants.items()}}
    (HERE / "options_results.json").write_text(json.dumps(result, indent=2) + "\n")
    for variant, (p, _) in variants.items():
        print(variant, p["holdout"], flush=True)
    print(gates)


if __name__ == "__main__":
    main()
