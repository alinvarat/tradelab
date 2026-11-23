"""Run with python3 -m research.sixfold.perps after perps_fetch."""
import gzip
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from statistics import mean, median

from .perps_fetch import HERE, SYMBOLS

INTERVAL = 900_000
ISOLATED_FRACTION = 0.5
STOP_PCT = 0.0075
TARGET_PCT = 0.03
MAINTENANCE = 0.005
BASE_FEE = 0.00075
STRESS_FEE = 0.0015
RANDOM_RUNS = 1_000


@dataclass(frozen=True)
class Fill:
    exit_index: int
    return_fraction: float
    reason: str


class Market:
    def __init__(self, path):
        raw = gzip.decompress(path.read_bytes())
        self.hash = hashlib.sha256(raw).hexdigest()
        inputs = json.loads(raw)
        trades = {row[0]: row[1:] for row in inputs["klines"]}
        marks = {row[0]: row[1:] for row in inputs["markPriceKlines"]}
        self.timestamps = list(range(min(min(trades), min(marks)), max(max(trades), max(marks)) + INTERVAL, INTERVAL))
        self.trades = [trades.get(ms) for ms in self.timestamps]
        self.marks = [marks.get(ms) or trades.get(ms) for ms in self.timestamps]
        self.gaps = {"trade_missing": len(self.timestamps) - len(trades),
                     "mark_missing": len(self.timestamps) - len(marks),
                     "both_missing": sum(ms not in trades and ms not in marks for ms in self.timestamps)}
        self.funding = {}
        for ms, _, rate in inputs["fundingRate"]:
            stamp = round(ms / INTERVAL) * INTERVAL
            if abs(stamp - ms) > 90_000 or stamp in self.funding:
                raise ValueError(f"unaligned or repeated funding event at {ms}")
            self.funding[stamp] = rate
        self.months = defaultdict(list)
        self.hour_bars = defaultdict(list)
        for i, ms in enumerate(self.timestamps):
            dt = datetime.fromtimestamp(ms / 1_000, tz=timezone.utc)
            month = dt.strftime("%Y-%m")
            self.months[month].append(i)
            if self.trades[i] is not None:
                self.hour_bars[month, dt.hour].append(i)
        assert all(self.trades[days[-1]] for days in self.months.values()), "cannot fill at month end"
        self.month_end = {i: days[-1] for days in self.months.values() for i in days}
        self.signals = defaultdict(list)
        for signal in range(32, len(self.trades) - 2):
            original = self.trades[signal - 32:signal]
            entry = signal + 2
            if any(c is None for c in [*original, self.trades[signal], self.trades[entry]]):
                continue
            ceiling = max(c[1] for c in original)
            floor = min(c[2] for c in original)
            if ceiling / floor - 1 > 0.015:
                continue
            close = self.trades[signal][3]
            direction = int(close > ceiling * 1.0005) - int(close < floor * 0.9995)
            if direction and self.month_end[signal] >= entry:
                ms = self.timestamps[entry]
                dt = datetime.fromtimestamp(ms / 1_000, tz=timezone.utc)
                self.signals[dt.strftime("%Y-%m")].append((entry, direction, dt.hour))

    @lru_cache(maxsize=None)
    def execute(self, entry, direction, leverage, fee):
        px = self.trades[entry][0]
        stop = px * (1 - direction * STOP_PCT)
        target = px * (1 + direction * TARGET_PCT)
        units = ISOLATED_FRACTION * leverage / px
        initial_fee = units * px * fee
        end = min(entry + 47, self.month_end[entry])
        funding = 0.0
        last_mark = px
        for i in range(entry, self.month_end[entry] + 1):
            mark = self.marks[i]
            if i > entry:
                open_mark = mark[0] if mark else last_mark
                funding += direction * units * open_mark * self.funding.get(self.timestamps[i], 0)
            if mark:
                last_mark = mark[3]
                adverse_mark = mark[2] if direction > 0 else mark[1]
                margin = ISOLATED_FRACTION + units * direction * (adverse_mark - px) - initial_fee - funding
                if margin <= units * adverse_mark * MAINTENANCE:
                    return Fill(i, -ISOLATED_FRACTION, "liquidation")
            trade = self.trades[i]
            if trade is None:
                continue
            open_price, high, low, close = trade
            adverse_trade = low if direction > 0 else high
            favorable_trade = high if direction > 0 else low
            if direction * (adverse_trade - stop) <= 0:
                price = min(open_price, stop) if direction > 0 else max(open_price, stop)
                reason = "stop"
                break
            if direction * (favorable_trade - target) > 0:
                price, reason = target, "limit"
                break
            if i >= end:
                price, reason = (close if i == end else open_price), "timed"
                break
        change = units * direction * (price - px) - initial_fee - units * price * fee - funding
        return Fill(i, max(-ISOLATED_FRACTION, change), reason)

    def month(self, month, entries, leverage, fee, account_target=6.0):
        wallet = peak = 1.0
        drawdown = 0.0
        free_after = -1
        outcomes = Counter()
        for entry, direction, _hour in entries:
            if entry <= free_after:
                continue
            result = self.execute(entry, direction, leverage, fee)
            wallet *= 1 + result.return_fraction
            peak = max(peak, wallet)
            drawdown = min(drawdown, wallet / peak - 1)
            free_after = result.exit_index
            outcomes[result.reason] += 1
            if wallet >= account_target or wallet <= 0.1:
                break
        return {"month": month, "net_multiple": wallet, "max_exit_drawdown_pct": -drawdown * 100,
                "trades": sum(outcomes.values()), "outcomes": dict(outcomes)}

    def permutations(self, months, leverage, fee, score):
        rng = random.Random(20261123)
        sets = [defaultdict(list) for _ in months]
        for month, groups in zip(months, sets):
            for _entry, direction, hour in self.signals[month]:
                groups[hour].append(direction)
        monthly_medians, hits = [], []
        for _ in range(RANDOM_RUNS):
            rows = []
            for month, groups in zip(months, sets):
                candidates = []
                for hour, directions in groups.items():
                    dates = rng.sample(self.hour_bars[month, hour], len(directions))
                    candidates.extend((i, d, hour) for i, d in zip(dates, directions))
                rows.append(self.month(month, sorted(candidates), leverage, fee)["net_multiple"])
            monthly_medians.append(median(rows))
            hits.append(sum(r >= 6 for r in rows))
        return {
            "draws": RANDOM_RUNS,
            "mean_of_random_monthly_medians": mean(monthly_medians),
            "p_random_median_at_least_observed": (1 + sum(x >= score["median_multiple"] for x in monthly_medians)) / (1 + RANDOM_RUNS),
            "mean_random_6x_months": mean(hits),
            "p_random_6x_months_at_least_observed": (1 + sum(x >= score["months_6x"] for x in hits)) / (1 + RANDOM_RUNS),
        }


def summarize(rows):
    outcomes = Counter()
    for row in rows:
        outcomes.update(row["outcomes"])
    multiples = [row["net_multiple"] for row in rows]
    balances = [1.0]
    end_drawdown = 0.0
    peak = 1.0
    for change in multiples:
        balance = balances[-1] * change
        balances.append(balance)
        peak = max(peak, balance)
        end_drawdown = min(end_drawdown, balance / peak - 1)
    return {
        "months": len(multiples),
        "months_6x": sum(m >= 6 for m in multiples),
        "months_left_at_most_half": sum(m <= 0.5 for m in multiples),
        "months_left_at_most_tenth": sum(m <= 0.1 for m in multiples),
        "median_multiple": median(multiples),
        "mean_multiple": mean(multiples),
        "geometric_mean_multiple": math.exp(mean(map(math.log, multiples))),
        "max_multiple": max(multiples),
        "min_multiple": min(multiples),
        "account_multiple_no_top_up_simulation": balances[-1],
        "continuous_month_end_drawdown_pct": -end_drawdown * 100,
        "worst_individual_month_exit_drawdown_pct": max(row["max_exit_drawdown_pct"] for row in rows),
        "trades": sum(row["trades"] for row in rows),
        "trade_outcomes": dict(outcomes),
    }


def run_variant(market, leverage, fee, with_controls):
    months = [month for month in market.months if month >= "2021-01"]
    rows = [market.month(month, market.signals[month], leverage, fee) for month in months]
    groups = {
        name: [row for row in rows if start <= row["month"] <= end]
        for name, start, end in [
            ("reference", "2021-01", "2023-12"),
            ("holdout", "2024-01", "2025-12"),
            ("2024", "2024-01", "2024-12"),
            ("2025", "2025-01", "2025-12"),
        ]
    }
    score = {name: summarize(group) for name, group in groups.items()}
    if with_controls:
        control_months = [m for m in months if m >= "2024-01"]
        score["holdout"]["matched_random"] = market.permutations(control_months, leverage, fee, score["holdout"])
    print(leverage, fee, score["holdout"], flush=True)
    return {"leverage_on_collateral": leverage, "fee_per_side": fee,
            "snapshot_sha256": market.hash, "coverage_gaps": market.gaps, "periods": score, "monthly_results": rows}


def main():
    btc, eth = [Market(HERE / f"perps_{symbol}_inputs.json.gz") for symbol in SYMBOLS]
    variants = {
        "btc_base": run_variant(btc, 20, BASE_FEE, True),
        "btc_cost_stress": run_variant(btc, 20, STRESS_FEE, False),
        "btc_lower_leverage": run_variant(btc, 10, BASE_FEE, False),
        "eth_transfer": run_variant(eth, 20, BASE_FEE, False),
    }
    primary = variants["btc_base"]["periods"]
    base = primary["holdout"]
    checks = {
        "6x_in_both_holdout_years": all(primary[y]["months_6x"] > 0 for y in ("2024", "2025")),
        "holdout_median_above_1": base["median_multiple"] > 1,
        "median_advantage_over_random": base["matched_random"]["p_random_median_at_least_observed"] < 0.05,
        "6x_after_higher_cost": variants["btc_cost_stress"]["periods"]["holdout"]["months_6x"] > 0,
        "sixfold_months_exceed_half_loss_months": base["months_6x"] > base["months_left_at_most_half"],
    }
    output = {"gates": checks, "qualifies": all(checks.values()), "variants": variants}
    (HERE / "perps_results.json").write_text(json.dumps(output, indent=2) + "\n")
    print(checks)


if __name__ == "__main__":
    main()
