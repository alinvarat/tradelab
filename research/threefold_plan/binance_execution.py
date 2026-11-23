"""Simulate a spot round trip using only the book known at each specified time."""
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from binance_replay import replay
from book_pilot import sweep

STAKE = Decimal("147")


def fill_at(path, at, side, amount, max_age):
    state = replay(path, cutoff=at, include_levels=True)
    if state["closed"]:
        return None, "outside_capture"
    if state["levels"] is None or state["received"] is None:
        return None, "unavailable_book"
    if at - state["received"] > max_age:
        return None, "stale_book"
    fill = sweep(state["levels"][1 if side == "buy" else 0], amount, by_quote=side == "buy")
    return (fill, None) if fill else (None, "insufficient_visible_size")


def trial(path, entry, exit_, fee):
    max_age = timedelta(milliseconds=500)
    buy, reason = fill_at(path, entry, "buy", STAKE / (1+fee), max_age)
    if buy is None:
        return {"status": reason, "leg": "buy"}
    sell, reason = fill_at(path, exit_, "sell", buy[0], max_age)
    if sell is None:
        return {"status": reason, "leg": "sell", "unsold_units": str(buy[0])}
    return {"status": "modeled", "buy_vwap": str(buy[1] / buy[0]),
            "sell_vwap": str(sell[1] / sell[0]), "base_units": str(buy[0]),
            "ending_usdt": str(sell[1]*(1-fee))}


def main():
    path = Path(sys.argv[1])
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    start = datetime.fromisoformat(rows[0]["utc"])
    # Fixed relative offsets for a mechanics check, no prediction or choice of price.
    entry, exit_ = (start + timedelta(seconds=x) for x in (3, 9))
    out = {"data_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mechanics_only": True,
           "entry_utc": entry.isoformat(), "exit_utc": exit_.isoformat(), "stake_usdt": str(STAKE),
           "cases": {name: trial(path, entry, exit_, rate) for name, rate in
                     (("base", Decimal(".0035")), ("higher", Decimal(".01")))}}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
