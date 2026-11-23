"""Replay the fixed available-strike Deribit transfer rules."""
import argparse
import gzip
import hashlib
import json
import random
from calendar import monthrange
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from statistics import mean

from .options import analyze_month, summarize, WALLET
from .options_fetch import HERE, HISTORY, LIVE, ms, rpc, trade_range

MONTHS = [(y, m) for y in (2024, 2025, 2026) for m in range(1, 11 if y == 2026 else 13)]
CURRENCIES = ("BTC", "ETH")
PERIODS = {"historical": ("2024-01", "2025-12"), "new_2026": ("2026-01", "2026-10")}
SNAPSHOT = HERE / "options_transfer_inputs.json.gz"


def month_dates(year, month):
    opening = datetime(year, month, 1, 9, tzinfo=timezone.utc)
    expiry = datetime(year, month, monthrange(year, month)[1], 8, tzinfo=timezone.utc)
    return opening, expiry - timedelta(days=(expiry.weekday() - 4) % 7)


def catalogue(asset):
    expiry_dates = {ms(month_dates(y, m)[1]) for y, m in MONTHS}
    raw = rpc(HISTORY, "get_instruments", currency=asset, kind="option", expired="true")
    chains = defaultdict(list)
    for spec in raw:
        expiry = spec["expiration_timestamp"]
        if expiry in expiry_dates and spec["settlement_currency"] == asset:
            chains[expiry].append(spec)
    if set(chains) != expiry_dates:
        raise ValueError(f"Incomplete monthly catalogue for {asset}")
    return chains


def get_settlements(asset):
    name = asset.lower() + "_usd"
    fetch = lambda offset: rpc(LIVE, "get_delivery_prices", index_name=name, count=100, offset=offset)["data"]
    newest = fetch(0)
    recent = datetime.fromisoformat(newest[0]["date"]).date()
    last = (recent - month_dates(*MONTHS[0])[1].date()).days
    with ThreadPoolExecutor(max_workers=4) as pool:
        more = list(pool.map(fetch, range(100, last + 100, 100)))
    return {r["date"]: r["delivery_price"] for page in [newest, *more] for r in page}


def prior_index(asset, timestamp):
    trades = trade_range(asset + "-PERPETUAL", timestamp - 300_000, timestamp - 1,
                         count=1, sorting="desc")["trades"]
    return trades[0] if trades else None


def choose_spec(chain, spot, side, decision):
    scored = []
    for spec in chain:
        if spec["creation_timestamp"] > decision or spec["option_type"] != ("call" if side == "C" else "put"):
            continue
        distance = (spec["strike"] / spot - 1) * (1 if side == "C" else -1)
        if 0.15 <= distance <= 0.25:
            scored.append((round(abs(distance - 0.2), 12), -distance, spec["instrument_name"], spec))
    return min(scored)[-1] if scored else None


def month_row(asset, year, month, chains, delivery):
    opening, expiry = month_dates(year, month)
    decision = ms(opening)
    now = prior_index(asset, decision)
    past = prior_index(asset, ms(opening - timedelta(days=7)))
    expiry_date = expiry.date().isoformat()
    row = {"month": opening.strftime("%Y-%m"), "chosen_at": decision, "expiry": expiry_date,
           "indices": [past, now], "options": {}, "official_settlement_usd": delivery[expiry_date]}
    if not now or not past:
        return row
    for side in "CP":
        spec = choose_spec(chains[ms(expiry)], now["index_price"], side, decision)
        sample = {"spec": spec, "name": spec["instrument_name"] if spec else None,
                  "strike": spec["strike"] if spec else None, "first_print": None}
        row["options"]["20" + side] = sample
        if not spec:
            continue
        trades = trade_range(spec["instrument_name"], decision, decision + 7_200_000)
        for trade in trades["trades"]:
            if (trade["direction"] == "buy" and trade["amount"] >= spec["min_trade_amount"]
                    and not any(trade.get(flag) for flag in ("block_trade_id", "combo_id", "liquidation"))):
                assert decision <= trade["timestamp"] <= decision + 7_200_000
                sample["first_print"] = trade
                break
        if trades["has_more"] and not sample["first_print"]:
            raise ValueError(f"Incomplete print search: {spec['instrument_name']}")
    return row


def acquire():
    result = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {k: pool.submit(fn, asset) for asset in CURRENCIES
                   for k, fn in [((asset, "chain"), catalogue), ((asset, "delivery"), get_settlements)]}
        for asset in CURRENCIES:
            chains = futures[asset, "chain"].result()
            delivery = futures[asset, "delivery"].result()
            jobs = [pool.submit(month_row, asset, y, m, chains, delivery) for y, m in MONTHS]
            result[asset] = [job.result() for job in jobs]
            print(f"Fetched {len(jobs)} months for {asset}", flush=True)
    raw = json.dumps({"sources": [HISTORY, LIVE], "series": result}, separators=(",", ":")).encode()
    SNAPSHOT.write_bytes(gzip.compress(raw, mtime=0))


def evaluate(rows, price_over_print):
    independent = []
    continuous = []
    balance = WALLET
    for row in rows:
        reset = analyze_month(row, 20, price_over_print, 1)
        run = analyze_month(row, 20, price_over_print, 1, starting=balance)
        for calculation in (reset, run):
            if "amount_btc_contracts" in calculation:
                calculation["contract_units"] = calculation.pop("amount_btc_contracts")
        independent.append({"month": row["month"], **reset})
        continuous.append({"month": row["month"], "starting": balance, **run})
        balance = run["ending"]
    summary = summarize(independent, continuous)
    summary["continuous_months_at_6x_of_initial_balance"] = sum(row["ending"] >= 6 * WALLET for row in continuous)
    summary["continuous_crossings_of_6x_initial_balance"] = sum(
        row["starting"] < 6 * WALLET <= row["ending"] for row in continuous
    )
    summary["continuous_months_at_6x_of_month_start"] = sum(
        row["starting"] > 0 and row["ending"] >= 6 * row["starting"] for row in continuous
    )
    choices = [[analyze_month(row, 20, price_over_print, 1, side_override=side)["ending"] >= 6 * WALLET
                for side in "CP"] for row in rows]
    rng = random.Random(73003)
    random_hits = [sum(rng.choice(pair) for pair in choices) for _ in range(3000)]
    summary["random_direction_draws"] = len(random_hits)
    summary["random_direction_mean_6x_months"] = mean(random_hits)
    summary["random_direction_p"] = (1 + sum(n >= summary["months_at_6x"] for n in random_hits)) / (1 + len(random_hits))
    return {"summary": summary, "monthly": independent, "continuous": continuous}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh or not SNAPSHOT.exists():
        acquire()
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    series = json.loads(raw)["series"]
    result = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "assets": {}}
    for asset, history in series.items():
        result["assets"][asset] = {
            period: {
                label: evaluate([row for row in history if begin <= row["month"] <= end], friction)
                for label, friction in (("base", 0.15), ("stress", 0.35))
            } for period, (begin, end) in PERIODS.items()
        }
        for period, scenarios in result["assets"][asset].items():
            for label, output in scenarios.items():
                print(asset, period, label, output["summary"], flush=True)
    latest = [result["assets"][asset]["new_2026"] for asset in CURRENCIES]
    result["gates"] = {
        "multiple_6x_in_new_period": max(row["base"]["summary"]["months_at_6x"] for row in latest) >= 2,
        "at_least_one_hit_in_both_assets": all(row["base"]["summary"]["months_at_6x"] >= 1 for row in latest),
        "cost_and_matched_control": any(
            row["base"]["summary"]["random_direction_p"] <= .05
            and row["stress"]["summary"]["months_at_6x"] >= 2 for row in latest),
        "target_more_common_than_half_loss": any(
            row["base"]["summary"]["months_at_6x"] > row["base"]["summary"]["months_remaining_half_or_less"]
            for row in latest),
    }
    result["pass"] = all(result["gates"].values())
    (HERE / "options_transfer_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
