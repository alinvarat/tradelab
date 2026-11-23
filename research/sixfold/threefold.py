"""Replay established monthly paper rules using the new 3× goal."""
import gzip
import json
import math
import random
from datetime import date
from statistics import mean, median

from . import spot
from .crowding import crowding_events
from .perps import Market, BASE_FEE, STRESS_FEE
from .options import WALLET, analyze_month

HERE = spot.HERE
TARGET = 3.0


def periods(rows):
    windows = spot.WINDOWS
    return {name: summarize([r for month, r in rows if lo <= month <= hi])
            for name, (lo, hi) in windows.items() if any(lo <= m <= hi for m, _ in rows)}


def summarize(multiples):
    return {"months": len(multiples), "hits_3x": sum(x >= TARGET for x in multiples),
            "half_loss_months": sum(x <= 0.5 for x in multiples),
            "median_multiple": median(multiples), "best_multiple": max(multiples),
            "compounded_multiple": math.prod(multiples)}


def spot_scenarios():
    symbols = json.loads(gzip.decompress((HERE / "spot_inputs.json.gz").read_bytes()))["markets"]
    prices = {s: {date.fromisoformat(d): b for d, b in data.items()} for s, data in symbols.items()}
    pools = spot.weekly_candidates(prices)
    months = list(spot.month_windows())
    normal = spot.lookup_factory(prices, spot.BASE_COST)
    scenarios = {}
    for rule in ("continuation", "reversal"):
        plan = [(start, end, [(slot, spot.choose(pools.get(slot[0], ()), rule))
                             for slot in spot.weekly_slots(start, end)]) for start, end in months]
        scans = {}
        for variant, lookup in (("base", normal), ("cost_stress", spot.lookup_factory(prices, spot.STRESS_COST)),
                                ("entry_delayed", spot.lookup_factory(prices, spot.BASE_COST, delay=1))):
            results = [spot.run_month(start, end, picks, lookup, details=True, target=TARGET)
                       for start, end, picks in plan]
            scans[variant] = {"metrics": periods([(r["month"], r["multiple"]) for r in results]),
                              "monthly": results}
        rng = random.Random(10226)
        matched = [(start, end, [(slot, tuple(r[0] for r in pools[slot[0]])) for slot, s in slots if s])
                   for start, end, slots in plan if 2024 <= start.year <= 2025]
        hits = []
        for _ in range(2000):
            hit = 0
            for start, end, slots in matched:
                picks = [(slot, rng.choice(eligible)) for slot, eligible in slots]
                hit += spot.run_month(start, end, picks, normal, target=TARGET)["multiple"] >= TARGET
            hits.append(hit)
        observed = scans["base"]["metrics"]["holdout"]["hits_3x"]
        scans["matched_random"] = {"draws": len(hits), "mean_hits": mean(hits),
                                   "p_one_sided": (1 + sum(x >= observed for x in hits)) / (1 + len(hits))}
        scenarios[rule] = scans
    return scenarios


def futures_scenarios():
    path = HERE / "perps_BTCUSDT_inputs.json.gz"
    results = {}
    for rule in ("compression", "crowding"):
        market = Market(path)
        if rule == "crowding":
            crowding_events(market, path, 0)
        complete = [m for m in sorted(market.months) if "2021-01" <= m <= "2025-12"]
        for scenario, fee in (("base", BASE_FEE), ("cost_stress", STRESS_FEE)):
            data = [market.month(month, market.signals[month], 20, fee, account_target=TARGET) for month in complete]
            results.setdefault(rule, {})[scenario] = {
                "metrics": periods([(r["month"], r["net_multiple"]) for r in data]), "monthly": data}
    return results


def matched_option_control(source_rows, first, last, friction, observed):
    data = [r for r in source_rows if first <= r["month"] <= last]
    pairs = [[analyze_month(row, 20, friction, 1, side_override=side)["ending"] >= TARGET * WALLET
              for side in "CP"] for row in data]
    rng = random.Random(10227)
    hits = [sum(rng.choice(pair) for pair in pairs) for _ in range(3000)]
    return {"draws": len(hits), "mean_hits": mean(hits),
            "p_one_sided": (1 + sum(n >= observed for n in hits)) / (1 + len(hits))}


def settlement_scenarios():
    exact = json.loads((HERE / "options_results.json").read_text())["variants"]["main_otm20"]["monthly"]
    relaxed = json.loads((HERE / "options_transfer_results.json").read_text())["assets"]
    tail = json.loads((HERE / "tail_results.json").read_text())
    option_inputs = json.loads(gzip.decompress((HERE / "options_transfer_inputs.json.gz").read_bytes()))["series"]
    results = {"btc_exact": periods([(r["month"], r["ending"] / WALLET) for r in exact])}
    # These sections preserve the source continuous path and its contract minimums.
    for asset, groups in relaxed.items():
        for variant in ("base", "stress"):
            raw = groups["historical"][variant]["monthly"] + groups["new_2026"][variant]["monthly"]
            s = periods([(r["month"], r["ending"] / WALLET) for r in raw])
            for period, source in (("holdout", "historical"), ("later_2026", "new_2026")):
                continuous = groups[source][variant]["continuous"]
                s[period]["actual_continuous_multiple_including_minimum_order"] = continuous[-1]["ending"] / WALLET
                lower, upper = spot.WINDOWS[period]
                s[period]["matched_random_direction"] = matched_option_control(
                    option_inputs[asset], lower, upper, 0.15 if variant == "base" else 0.35, s[period]["hits_3x"]
                )
            results[f"{asset.lower()}_available_{variant}"] = s
    for variant in ("base", "stress"):
        sample = tail[variant]["holdout"]["entries"]
        results[f"kalshi_{variant}"] = periods([(m, r["ending_multiple"] if r else 1.0) for m, r in sample.items()])
    return results


def main():
    result = {"minimum_target": TARGET, "spot": spot_scenarios(), "futures": futures_scenarios(),
              "settlement": settlement_scenarios()}
    (HERE / "threefold_results.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, scenarios in {**result["spot"], **result["futures"]}.items():
        print(name, scenarios["base"]["metrics"], scenarios.get("matched_random", ""))
    print(result["settlement"])


if __name__ == "__main__":
    main()
