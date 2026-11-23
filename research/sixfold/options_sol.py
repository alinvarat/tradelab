"""SOL linear-option transfer using the frozen BTC/ETH weekly schedule."""
import argparse
import gzip
import hashlib
import json
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .options import CONVERSION, WALLET
from .options_fetch import HERE, HISTORY, LIVE, ms, rpc, trade_range
from .options_weekly import assess, calendar, capture

SNAPSHOT = HERE / "options_sol_inputs.json.gz"


def sol_index(asset, timestamp):
    rows = trade_range(asset + "_USDC-PERPETUAL", timestamp - 300_000, timestamp - 1,
                       count=1, sorting="desc")["trades"]
    return rows[0] if rows else None


def catalogue(expiries):
    chains = defaultdict(list)
    for spec in rpc(HISTORY, "get_instruments", currency="USDC", kind="option", expired="true"):
        expiry = spec["expiration_timestamp"]
        if (expiry in expiries and spec.get("price_index") == "sol_usdc"
                and spec.get("settlement_currency") == "USDC" and spec.get("base_currency") == "SOL"):
            chains[expiry].append(spec)
    if set(chains) != expiries:
        raise ValueError(f"SOL weekly expiry catalogue coverage {len(chains)}/{len(expiries)}")
    return chains


def settlement():
    def page(offset):
        return rpc(LIVE, "get_delivery_prices", index_name="sol_usdc", count=100, offset=offset)["data"]

    latest = page(0)
    offset = (date.fromisoformat(latest[0]["date"]) - date(2025, 1, 1)).days
    with ThreadPoolExecutor(max_workers=4) as pool:
        older = list(pool.map(page, range(100, offset + 100, 100)))
    return {r["date"]: r["delivery_price"] for batch in [latest, *older] for r in batch}


def acquire():
    weeks = list(calendar())
    expiries = {ms(expiry) for _, expiry in weeks}
    rows, sales = [], {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        chains_job = pool.submit(catalogue, expiries)
        settles_job = pool.submit(settlement)
        chains, settles = chains_job.result(), settles_job.result()
        jobs = [pool.submit(capture, "SOL", pair, chains, settles, sol_index) for pair in weeks]
        for i, job in enumerate(jobs, start=1):
            row, prints = job.result()
            rows.append(row)
            sales.update(prints)
            if i % 20 == 0:
                print(f"SOL {i}/{len(jobs)} weeks retrieved", flush=True)
    raw = json.dumps({"sources": [HISTORY, LIVE], "rows": rows, "sales": sales},
                     separators=(",", ":")).encode()
    SNAPSHOT.write_bytes(gzip.compress(raw, mtime=0))


def quantity(print_, multiplier):
    underlying = print_["amount"]
    if "contracts" not in print_ or not math.isclose(underlying, print_["contracts"] * multiplier,
                                                    rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError(f"Cannot verify units for {print_['trade_id']}")
    return underlying


def fee(premium, index, rate):
    return min(0.125 * premium, rate * index)


def fill_sol(row, sales, limit, markup, haircut, balance=WALLET, side=None, budget_fraction=1.0):
    result = {"month": row["month"], "starting": balance, "ending": balance, "status": "missing_predecision_index"}
    previous, current = row["indices"]
    if previous is None or current is None:
        return result
    if side is None:
        move = current["index_price"] - previous["index_price"]
        if move == 0:
            return {**result, "status": "unchanged_index"}
        side = "C" if move > 0 else "P"
    sample = row["options"]["20" + side]
    spec = sample["spec"]
    if spec is None:
        return {**result, "status": "instrument_not_listed_yet"}
    result["instrument"] = sample["name"]
    entry = sample["first_print"]
    if entry is None:
        return {**result, "status": "no_eligible_trade_within_2h"}
    multiplier = spec["contract_size"]
    rate = spec["taker_commission"]
    premium = entry["price"] * (1 + markup)
    purchase = (premium + fee(premium, entry["index_price"], rate)) * (1 + CONVERSION)
    units = multiplier * math.floor(
        min(balance * budget_fraction / purchase, quantity(entry, multiplier)) / multiplier + 1e-10)
    if units < spec["min_trade_amount"]:
        return {**result, "status": "minimum_order_over_budget"}
    spent = units * purchase
    cash = balance - spent
    result.update(status="filled_proxy", side=side, contract_units=units / multiplier,
                  underlying_sol_units=units, spent_usd=spent, entry_print=entry)
    for sale in sales[sample["name"]]:
        if quantity(sale, multiplier) < units:
            continue
        sale_premium = sale["price"] * (1 - haircut)
        proceeds = units * (sale_premium - fee(sale_premium, sale["index_price"], rate)) * (1 - CONVERSION)
        if cash + proceeds >= limit * balance:
            return {**result, "ending": limit * balance, "modeled_exit": "early",
                    "net_if_sold_on_print": cash + proceeds, "sale_print": sale}
    settlement = row["official_settlement_usd"]
    intrinsic = max(0.0, (settlement - spec["strike"]) * (1 if side == "C" else -1))
    payout = units * (intrinsic - fee(intrinsic, settlement, 0.00015)) * (1 - CONVERSION)
    return {**result, "ending": cash + payout, "modeled_exit": "expiry",
            "settlement_index_usd": settlement, "settled_value_usd": payout}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh or not SNAPSHOT.exists():
        acquire()
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    source = json.loads(raw)
    report = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(),
              "sales": sum(map(len, source["sales"].values())), "contracts": len(source["sales"]), "periods": {}}
    for period in ("2025", "2026"):
        months = defaultdict(list)
        for row in source["rows"]:
            if row["month"].startswith(period):
                months[row["month"]].append(row)
        assert len(months) == (12 if period == "2025" else 10)
        output = report["periods"][period] = {}
        for cap in (1.0, 0.5):
            for target in (3, 6):
                for label, friction in (("base", (0.15, 0.05)), ("stress", (0.35, 0.15))):
                    name = f"{target}x_{label}_{cap:g}_cap"
                    evaluation = output[name] = assess(months, source["sales"], target, friction,
                                                        budget_fraction=cap, fill=fill_sol)
                    print(period, name, evaluation["summary"], flush=True)
    (HERE / "options_sol_results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
