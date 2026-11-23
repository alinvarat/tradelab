"""Risk diagnostics for the fixed Binance spot selectors."""
import gzip
import json
from datetime import date

from research.sixfold.spot import (
    BASE_COST, FILL_BUFFER, HERE, ONE, TARGET, WINDOWS, calendar, choose, month_slice,
    month_windows, summarize, weekly_candidates, weekly_slots,
)

VARIANTS = {"half_cash": (0.5, None), "stop_at_25pct": (1.0, 0.75)}
EXTRA_STOP_SLIP = 0.0035


def position(bars, slot, equity, allocation, stop_fraction):
    entry, exit_, exit_at_open = slot
    if entry not in bars:
        return equity, [], "no_fill"
    buy = bars[entry][0]
    cash = equity * (1 - allocation)
    units = equity * allocation / (buy * (1 + BASE_COST))
    sell_value = units * (1 - BASE_COST)
    target_price = (TARGET - cash) / sell_value
    stop = buy * stop_fraction if stop_fraction else None
    marks = []
    last_exposure = exit_ - ONE if exit_at_open else exit_
    for day in calendar(entry, last_exposure):
        if day not in bars:
            return cash, marks, "missing_bar_zero"
        open_, high, low, close, *_ = bars[day]
        if open_ >= target_price * (1 + FILL_BUFFER):
            return TARGET, marks, "target"
        if stop is not None and low <= stop:
            fill = min(stop, open_) * (1 - EXTRA_STOP_SLIP)
            return cash + fill * sell_value, marks, "stop"
        if high >= target_price * (1 + FILL_BUFFER):
            return TARGET, marks, "target"
        marks.append(cash + close * sell_value)
    if exit_ not in bars:
        return cash, marks, "missing_exit_zero"
    exit_price = bars[exit_][0 if exit_at_open else 3]
    if exit_at_open and stop is not None and exit_price < stop:
        exit_price *= 1 - EXTRA_STOP_SLIP
    return min(TARGET, cash + exit_price * sell_value), marks, "scheduled"


def evaluate(prices, pools, rule, allocation, stop_fraction):
    outcomes = []
    for start, end in month_windows():
        equity = 1.0
        marks = [equity]
        filled = missing = closes = 0
        for slot in weekly_slots(start, end):
            symbol = choose(pools.get(slot[0], ()), rule)
            if not symbol:
                continue
            equity, extra_marks, reason = position(prices[symbol], slot, equity, allocation, stop_fraction)
            marks.extend([*extra_marks, equity])
            if reason == "no_fill":
                missing += 1
            else:
                filled += 1
                closes += reason == "stop"
            if equity <= 0 or equity >= TARGET:
                break
        peak = 1.0
        drawdown = 0.0
        for value in marks:
            peak = max(peak, value)
            drawdown = max(drawdown, 1 - value / peak)
        outcomes.append({"month": start.isoformat()[:7], "multiple": equity,
                         "6x": equity >= TARGET, "buy_count": filled, "entry_no_fill": missing,
                         "total_stops": closes, "within_month_close_drawdown": drawdown})
    return {"monthly": outcomes, "metrics": {k: summarize(month_slice(outcomes, k)) for k in WINDOWS}}


def main():
    src = json.loads(gzip.decompress((HERE / "spot_inputs.json.gz").read_bytes()))
    prices = {s: {date.fromisoformat(d): b for d, b in prices.items()} for s, prices in src["markets"].items()}
    pools = weekly_candidates(prices)
    results = {rule: {name: evaluate(prices, pools, rule, *params) for name, params in VARIANTS.items()}
               for rule in ("continuation", "reversal")}
    (HERE / "spot_risk_results.json").write_text(json.dumps(results, indent=2) + "\n")
    for rule, experiments in results.items():
        for variant, outcome in experiments.items():
            for period in ("holdout", "later_2026"):
                print(rule, variant, period, outcome["metrics"][period])


if __name__ == "__main__":
    main()
