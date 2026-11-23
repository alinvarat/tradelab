"""Replay weather contract selections with daily decisions and capital recycling."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
from statistics import median

from .spot import ONE
from .tail import CENT, MAX_ASK, NEW_YORK, ROOT, SNAPSHOT, STAKE, TAKER, boundary


def prepare(days):
    prepared = defaultdict(list)
    for day, record in sorted(days.items()):
        decision = boundary(date.fromisoformat(day))
        menu = []
        for row in record["candidates"]:
            if not row["ask_signal"] or row["volume_signal"] <= 0:
                continue
            quote = Decimal(row["ask_signal"])
            if not 0 < quote <= MAX_ASK:
                continue
            cost = quote + CENT
            ratio = row["probability"] / float(cost + TAKER * cost * (1 - cost))
            menu.append((ratio, row))
        if menu:
            ratio, row = max(menu, key=lambda x: (x[0], x[1]["ticker"]))
            if ratio >= 1.25:
                prepared[day[:7]].append((day, decision, row, [candidate for _, candidate in menu]))
    return prepared


def fill(row, slip, cash, decision):
    if not row["ask_entry"] or not row["settlement_ts"] or row["result"] not in ("yes", "no"):
        return None
    ask = Decimal(row["ask_entry"])
    settle = datetime.fromisoformat(row["settlement_ts"]).timestamp()
    if not 0 < ask <= MAX_ASK or settle <= decision:
        return None
    price = ask + slip
    fee_unit = TAKER * price * (1 - price)
    budget = cash / 4
    qty = min(int(budget // (price + fee_unit)), int(row["volume_entry"]))
    while qty > 0:
        spend = qty * price + (qty * fee_unit).quantize(CENT, rounding=ROUND_CEILING)
        if spend <= budget:
            return settle, spend, Decimal(qty if row["result"] == "yes" else 0), qty
        qty -= 1
    return None


def simulate(plan, months, slip, rng=None, details=False):
    cash, active, peak, drawdown = STAKE, None, STAKE, 0.
    results, trades = [], []
    prior = STAKE
    for month in months:
        first = date.fromisoformat(month + "-01")
        next_month = ((first.replace(day=28) + 4 * ONE).replace(day=1))
        month_end = datetime.combine(next_month, datetime.min.time(), NEW_YORK).timestamp()
        for day, decision, model, menu in plan[month]:
            if active and active[0] <= decision:
                cash += active[1]
                active = None
            if active:
                continue
            chosen = rng.choice(menu) if rng else model
            result = fill(chosen, slip, cash, decision)
            if result:
                settle, spend, payout, qty = result
                cash -= spend
                active = settle, payout
                trades.append([day, chosen["ticker"], qty, float(spend), float(payout)])
        if active and active[0] < month_end:
            cash += active[1]
            active = None
        results.append((month, float(cash / prior) if prior else 0, float(cash)))
        prior = cash
        peak = max(peak, cash)
        drawdown = max(drawdown, float(1 - cash / peak))
    output = {"ending_usd": float(cash), "3x_months": sum(r[1] >= 3 for r in results),
              "6x_months": sum(r[1] >= 6 for r in results), "drawdown_monthly_cash": drawdown,
              "wins": sum(r[4] > 0 for r in trades), "trade_count": len(trades)}
    return output | ({"months": results, "trades": trades} if details else {})


def main():
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    plan = prepare(json.loads(raw)["days"])
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "periods": {}}
    for label, years in (("2024",(2024,)), ("2025",(2025,)), ("continuous",(2024,2025))):
        months = [f"{y}-{m:02d}" for y in years for m in range(1,13)]
        report = output["periods"][label] = {}
        for k, slip in (("base",CENT), ("stress",2*CENT)):
            row = report[k] = simulate(plan, months, slip, details=True)
            rng = random.Random(88001)
            draws = [simulate(plan, months, slip, rng) for _ in range(1000)]
            row["random_median_ending"] = median(x["ending_usd"] for x in draws)
            row["random_fraction_ge"] = sum(x["ending_usd"] >= row["ending_usd"] for x in draws)/len(draws)
    (ROOT / "tail_daily_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
