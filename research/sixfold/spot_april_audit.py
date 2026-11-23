"""Reprice the disclosed April 2026 case using documented public Binance trade aggregates.

An execution sensitivity for one observed path, not a trading strategy. Uses the user's
approximate 147 USDT equivalent and fictional fills against observed prints.
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from research.sixfold.spot_inputs import HERE, download

ROOT = "https://data-api.binance.vision/api/v3/aggTrades"
SYMBOL = "币安人生USDT"
CAPITAL = 147.0
FRICTION = 0.0035


def minute(t):
    start = int(t.timestamp() * 1_000)
    stop = start + 59_999
    params = {"symbol": SYMBOL, "startTime": start, "endTime": stop, "limit": 1000}
    rows = []
    for _ in range(12):
        batch = json.loads(download(f"{ROOT}?{urlencode(params)}"))
        rows.extend(row for row in batch if start <= row["T"] <= stop)
        if len(batch) < 1000 or batch[-1]["T"] > stop:
            return rows
        params = {"symbol": SYMBOL, "fromId": batch[-1]["a"] + 1, "limit": 1000}
    raise ValueError("minute not completely retrieved")


def consume(trades, amount, buy):
    """Buy a gross quote amount or sell a base quantity across same-side prints."""
    units = gross = 0.0
    used = []
    for trade in trades:
        if trade["m"] == buy:
            continue
        price = float(trade["p"])
        qty = min(float(trade["q"]), amount / price if buy else amount)
        gross += qty * price
        units += qty
        amount -= qty * price if buy else qty
        used.append(trade["a"])
        if amount < 1e-9:
            break
    if amount >= 1e-9:
        raise ValueError(f"insufficient observed prints for {'buy' if buy else 'sell'}: {amount}")
    return {"units": units, "gross_usdt": gross, "vwap": gross / units, "source_aggregate_ids": used,
            "net_account_usdt": gross * (1 - FRICTION) if not buy else None}


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main():
    first_entry = t("2026-04-06T00:01:00")
    first_exit = t("2026-04-13T00:00:00")
    second_entry = t("2026-04-13T00:01:00")
    early_target = t("2026-04-18T01:03:00")
    late_target = t("2026-04-18T04:42:00")
    first = consume(minute(first_entry), CAPITAL / (1 + FRICTION), True)
    sale = consume(minute(first_exit), first["units"], False)
    second = consume(minute(second_entry), sale["net_account_usdt"] / (1 + FRICTION), True)
    target = CAPITAL * 6 / (second["units"] * (1 - FRICTION))
    chosen = None
    # Use published target-minute audits as examination windows, not as purchase inputs.
    for window in (early_target, late_target):
        prints = [trade for trade in minute(window) if not trade["m"] and float(trade["p"]) >= target]
        demand = sum(float(trade["q"]) for trade in prints)
        if demand >= second["units"]:
            chosen = {"minute_utc": window.isoformat(), "demand_units_at_or_above_limit": demand,
                      "demand_usdt_at_or_above_limit": sum(float(trade["q"]) * float(trade["p"]) for trade in prints),
                      "demand_aggregate_count": len(prints)}
            break
    out = {"symbol": SYMBOL, "initial_usdt_approximation": CAPITAL, "friction_per_side": FRICTION,
           "first_purchase": {"minute_utc": first_entry.isoformat(), **first},
           "first_sale": {"minute_utc": first_exit.isoformat(), **sale},
           "second_purchase": {"minute_utc": second_entry.isoformat(), **second},
           "second_limit_target_price": target, "second_sale_market_evidence": chosen,
           "interpretation": "Trade prices and volume are historical. Simulated fill ordering and queue are unobserved."}
    (HERE / "spot_april_path_audit.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
