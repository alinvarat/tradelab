"""Evaluate the fixed weekly spot rules in spot_protocol.md."""
import gzip
import hashlib
import json
import random
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
ONE = timedelta(days=1)
BASE_COST = 0.0035
STRESS_COST = 0.01
TARGET = 6.0
FILL_BUFFER = 0.0025
WINDOWS = {
    "reference": ("2021-01", "2023-12"),
    "holdout": ("2024-01", "2025-12"),
    "holdout_2024": ("2024-01", "2024-12"),
    "holdout_2025": ("2025-01", "2025-12"),
    "later_2026": ("2026-01", "2026-10"),
}
DRAWS = 2000


def calendar(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def weekly_candidates(prices):
    pools = {}
    for symbol, bars in prices.items():
        days = sorted(bars)
        for i, day in enumerate(days):
            if i < 29 or day.weekday() != 6 or day - days[i - 29] != 29 * ONE:
                continue
            current = bars[day]
            volumes = [bars[d][4] for d in days[i - 29:i]]
            if current[5] < 1000 or median([*volumes, current[4]]) < 1_000_000:
                continue
            drift = current[3] / bars[days[i - 7]][3] - 1
            surge = current[4] >= 2 * median(volumes)
            continuation = surge and drift >= 0.20 and current[3] >= max(bars[d][3] for d in days[i - 29:i])
            reversal = surge and drift <= -0.20 and current[3] > bars[days[i - 1]][3]
            pools.setdefault(day + ONE, []).append((symbol, drift, continuation, reversal))
    return pools


def weekly_slots(start, end):
    days = calendar(start, end)
    for day in days:
        if day.weekday() == 0:
            planned = day + 7 * ONE
            yield day, min(planned, end), planned <= end


def month_windows():
    for year in range(2021, 2027):
        for month in range(1, 13 if year < 2026 else 11):
            yield date(year, month, 1), date(year, month, monthrange(year, month)[1])


def choose(rows, rule):
    if rule == "continuation":
        valid = ((-drift, symbol) for symbol, drift, condition, _ in rows if condition)
    else:
        valid = ((drift, symbol) for symbol, drift, _, condition in rows if condition)
    top = min(valid, default=None)
    return top[1] if top else None


def path_for(bars, entry, last, exit_at_open, cost):
    """Unit-equity values, including opening and exit costs."""
    if entry not in bars or entry > last or (entry == last and exit_at_open):
        return None
    buy = bars[entry][0]
    units = 1 / (buy * (1 + cost))
    sale_factor = units * (1 - cost)
    end_of_exposure = last - ONE if exit_at_open else last
    marks = []
    for day in calendar(entry, end_of_exposure):
        if day not in bars:
            return buy, marks, 0.0, day, None, "missing_bar_zero"
        bar = bars[day]
        marks.append((day, bar[1] * sale_factor, bar[3] * sale_factor))
    if last not in bars:
        return buy, marks, 0.0, last, None, "missing_exit_zero"
    sale = bars[last][0] if exit_at_open else bars[last][3]
    return buy, marks, sale * sale_factor, last, sale, "scheduled"


def run_month(start, end, picks, lookup, details=False, target=TARGET):
    month = start.isoformat()[:7]
    balance = 1.0
    peak = 1.0
    drawdown = 0.0
    highest_close = 1.0
    count = 0
    failed = 0
    trades = []

    def mark(value):
        nonlocal peak, drawdown, highest_close
        peak = max(peak, value)
        highest_close = max(highest_close, value)
        drawdown = max(drawdown, 1 - value / peak)

    for slot, symbol in picks:
        if not symbol:
            continue
        path = lookup(slot, symbol)
        if path is None:
            failed += 1
            continue
        count += 1
        buying, marks, multiplier, exit_, sale, reason = path
        target_day = None
        for day, high_multiple, close_multiple in marks:
            if balance * high_multiple >= target * (1 + FILL_BUFFER):
                target_day = day
                break
            mark(balance * close_multiple)
        # A large scheduled opening gap can reach the target too. Scheduled market
        # proceeds are credited up to the target to keep the target-fill convention.
        if target_day is None and balance * multiplier >= target:
            target_day = exit_
        before = balance
        if target_day is not None:
            balance = target
            exit_ = target_day
            reason = "target"
        else:
            balance *= multiplier
        mark(balance)
        if details:
            trades.append({"symbol": symbol, "scheduled_entry": slot[0].isoformat(),
                           "entry": (marks[0][0] if marks else slot[0]).isoformat(),
                           "exit": exit_.isoformat(), "reason": reason, "raw_entry": buying,
                           "raw_exit": sale if reason != "target" else None,
                           "running_equity_before": before, "running_equity_after": balance})
        if balance in {0.0, target}:
            break
    out = {"month": month, "multiple": balance, f"{target:g}x": balance >= target, "buy_count": count,
           "entry_no_fill": failed, "within_month_close_drawdown": drawdown,
           "max_month_close_or_target_fill": highest_close}
    if details:
        out["trades"] = trades
    return out


def summarize(rows):
    returns = [row["multiple"] for row in rows]
    chained = 1.0
    months_to_6x = None
    for i, multiple in enumerate(returns, start=1):
        chained *= multiple
        if chained >= TARGET and months_to_6x is None:
            months_to_6x = i
    return {"months": len(returns), "hits_6x": sum(r >= TARGET for r in returns),
            "loss_50pct": sum(r <= 0.50 for r in returns), "loss_95pct": sum(r <= 0.05 for r in returns),
            "median_multiple": median(returns), "mean_multiple": mean(returns),
            "best_multiple": max(returns), "worst_multiple": min(returns),
            "total_entries": sum(row["buy_count"] for row in rows),
            "total_entries_without_fill": sum(row["entry_no_fill"] for row in rows),
            "worst_monthly_close_drawdown": max(row["within_month_close_drawdown"] for row in rows),
            "chained_multiple_no_redeposit": chained, "chained_months_until_6x": months_to_6x}


def month_slice(rows, key):
    start, end = WINDOWS[key]
    return [row for row in rows if start <= row["month"] <= end]


def lookup_factory(prices, cost, delay=0):
    cache = {}

    def lookup(slot, symbol):
        key = slot, symbol
        if key not in cache:
            day, end, exit_at_open = slot
            cache[key] = path_for(prices[symbol], day + timedelta(days=delay), end, exit_at_open, cost)
        return cache[key]
    return lookup


def random_runs(month_info, pools, rule, actual, lookup):
    rng = random.Random(54285)
    hits, medians, losses = [], [], []
    active = [(start, end, [(slot, tuple(row[0] for row in pools.get(slot[0], ())))
                            for slot in weekly_slots(start, end)
                            if choose(pools.get(slot[0], ()), rule)])
              for start, end in month_info if "2024-01" <= start.isoformat()[:7] <= "2025-12"]
    for _ in range(DRAWS):
        results = []
        for start, end, slots in active:
            picks = [(slot, rng.choice(universe)) for slot, universe in slots]
            results.append(run_month(start, end, picks, lookup))
        hits.append(sum(row["6x"] for row in results))
        medians.append(median(row["multiple"] for row in results))
        losses.append(sum(row["multiple"] <= 0.50 for row in results))
    return {"draws": DRAWS, "mean_6x_months": mean(hits), "max_6x_months": max(hits),
            "one_tail_6x_p": (1 + sum(x >= actual["hits_6x"] for x in hits)) / (DRAWS + 1),
            "mean_median_multiple": mean(medians), "mean_loss_50pct_months": mean(losses)}


def oracle(month_info, pools, lookup):
    """Measure availability of 6x moves, including an unattainable perfect-timing upper bound."""
    rows = []
    for start, end in month_info:
        opportunities = []
        optimistic_limit = 1.0
        for slot in weekly_slots(start, end):
            best = 1.0
            for symbol, *_ in pools.get(slot[0], ()):
                path = lookup(slot, symbol)
                if path is None:
                    continue
                _, marks, scheduled, _, _, _ = path
                highest = max((value for _, value, _ in marks), default=0.0)
                best = max(best, scheduled, highest)
                if scheduled >= TARGET or highest >= TARGET * (1 + FILL_BUFFER):
                    opportunities.append({"entry": slot[0].isoformat(), "symbol": symbol,
                                          "best_net_intrabar_or_exit_multiple": max(scheduled, highest)})
            optimistic_limit *= best
        rows.append({"month": start.isoformat()[:7], "hypothetical_single_trade_6x": opportunities,
                     "optimistic_hindsight_multiple": optimistic_limit})
    return rows


def main():
    src = HERE / "spot_inputs.json.gz"
    packed = src.read_bytes()
    snapshot = json.loads(gzip.decompress(packed))
    prices = {symbol: {date.fromisoformat(day): bar for day, bar in bars.items()}
              for symbol, bars in snapshot["markets"].items()}
    pools = weekly_candidates(prices)
    months = list(month_windows())
    regular = lookup_factory(prices, BASE_COST)
    stress = lookup_factory(prices, STRESS_COST)
    late = lookup_factory(prices, BASE_COST, delay=1)
    out = {"snapshot_sha256": hashlib.sha256(packed).hexdigest(),
           "primary_rules": 2, "archived_pair_count": len(snapshot["acquisition"]),
           "pairs_with_bars": len(prices), "bars": sum(map(len, prices.values())),
           "inactive_before_last_date": sum(max(p) < max(prices["BTCUSDT"]) for p in prices.values()),
           "explicit_download_failures": {s: x for s, x in snapshot["acquisition"].items() if x.startswith("error:")},
           "cost_per_side": BASE_COST, "stress_cost_per_side": STRESS_COST, "rules": {}}
    for rule in ("continuation", "reversal", "btc_monthly"):
        by_variant = {}
        for label, lookup in (("base", regular), ("stress", stress), ("late", late)):
            if rule == "btc_monthly" and label != "base":
                continue
            rows = []
            for start, end in months:
                if rule == "btc_monthly":
                    picks = [((start, end, False), "BTCUSDT")]
                else:
                    picks = [(slot, choose(pools.get(slot[0], ()), rule)) for slot in weekly_slots(start, end)]
                rows.append(run_month(start, end, picks, lookup, details=True))
            by_variant[label] = {"metrics": {k: summarize(month_slice(rows, k)) for k in WINDOWS}, "monthly": rows}
        if rule != "btc_monthly":
            primary = by_variant["base"]["metrics"]
            h = primary["holdout"]
            controls = random_runs(months, pools, rule, h, regular)
            gates = {"half_months_6x": h["hits_6x"] * 2 >= h["months"],
                     "large_loss_under_10pct": h["loss_50pct"] / h["months"] < 0.10,
                     "beats_random": controls["one_tail_6x_p"] <= 0.025,
                     "each_holdout_year_positive_hit_loss_balance": all(
                         primary[k]["hits_6x"] > primary[k]["loss_50pct"] for k in ("holdout_2024", "holdout_2025")),
                     "cost_and_delay_robust": all(
                         by_variant[k]["metrics"]["holdout"]["hits_6x"] * 2 >= h["months"] for k in ("stress", "late"))}
            by_variant["random_control"] = controls
            by_variant["gates"] = gates
            by_variant["paper_candidate"] = all(gates.values()) and not out["explicit_download_failures"]
        out["rules"][rule] = by_variant
    out["hindsight_opportunities"] = oracle(months, pools, regular)
    (HERE / "spot_results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({rule: {k: value["base"]["metrics"][k] for k in WINDOWS}
                      for rule, value in out["rules"].items()}, indent=2))


if __name__ == "__main__":
    main()
