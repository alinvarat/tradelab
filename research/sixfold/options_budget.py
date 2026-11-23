"""Compare frozen weekly option signals under full and half available-cash caps."""
import gzip
import hashlib
import json
import random
from statistics import median
from collections import defaultdict

from .options import WALLET
from .options_fetch import HERE
from .options_weekly import SNAPSHOT, assess, month_run, reached


def exposure_stats(replay, cap, target):
    continuous = replay["continuous"]
    trades = [week for row in continuous for week in row["weeks"]]
    fills = [week for week in trades if week["status"] == "filled_proxy"]
    assert all(week["spent_usd"] <= cap * week["starting"] + 1e-10 for week in fills)
    peak = WALLET
    max_drawdown = 0.0
    for row in continuous:
        peak = max(peak, row["ending"])
        max_drawdown = max(max_drawdown, 1 - row["ending"] / peak)
    stats = replay["summary"]
    stats.update(
        severe_loss_continuous_months=sum(
            row["starting"] > 0 and row["ending"] <= 0.5 * row["starting"] for row in continuous
        ),
        continuous_max_month_end_drawdown=max_drawdown,
        continuous_fills=len(fills),
        continuous_no_trade_months=sum(
            not any(w["status"] == "filled_proxy" for w in row["weeks"]) for row in continuous
        ),
        continuous_order_minimum_skips=sum(w["status"] == "minimum_order_over_budget" for w in trades),
        continuous_months_starting_with_at_least_original_and_hitting_target=sum(
            reached(row["starting"], WALLET) and reached(row["ending"], target * row["starting"])
            for row in continuous
        ),
    )


def random_account_paths(months, sales, target, friction, observed):
    rng = random.Random(10231)
    endings, funded_target_months = [], []
    for _ in range(1000):
        balance, hits = WALLET, 0
        for entries in months.values():
            previous = balance
            sides = [rng.choice("CP") for _ in entries]
            balance = month_run(entries, sales, target, friction, previous,
                                sides=sides, budget_fraction=0.5)
            hits += reached(previous, WALLET) and reached(balance, target * previous)
        endings.append(balance / WALLET)
        funded_target_months.append(hits)
    sample = len(endings)
    return {
        "draws": sample, "median_ending_multiple": median(endings),
        "p_ending_ge_observed": (1 + sum(x >= observed["continuous_multiple"] for x in endings)) / (sample + 1),
        "p_funded_hits_ge_observed": (
            1 + sum(x >= observed["continuous_months_starting_with_at_least_original_and_hitting_target"]
                    for x in funded_target_months)
        ) / (sample + 1),
    }


def main():
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    data = json.loads(raw)["assets"]
    result = {"inputs_sha256": hashlib.sha256(raw).hexdigest(), "assets": {}}
    for asset, sample in data.items():
        months = defaultdict(list)
        for row in sample["rows"]:
            months[row["month"]].append(row)
        assert len(months) == 22
        live = result["assets"][asset] = {}
        for phase, begin, end in (("full_path", "2025-01", "2026-10"), ("2026", "2026-01", "2026-10")):
            sub = {m: entries for m, entries in months.items() if begin <= m <= end}
            paths = live[phase] = {}
            for cap in (1.0, 0.5):
                for target in (3, 6):
                    for pricing, friction in (("base", (0.15, 0.05)), ("stress", (0.35, 0.15))):
                        label = f"{target}x_{pricing}_{cap:g}_cap"
                        replay = assess(sub, sample["sales"], target, friction, budget_fraction=cap)
                        exposure_stats(replay, cap, target)
                        if phase == "2026" and cap == 0.5:
                            replay["summary"]["random_continuous"] = random_account_paths(
                                sub, sample["sales"], target, friction, replay["summary"]
                            )
                        paths[label] = replay
                        print(asset, phase, label, replay["summary"])
    (HERE / "options_budget_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
