"""Inspect paper premium and exit size for one inverse BTC option."""
from datetime import datetime, timedelta
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys

from deribit_replay import replay

HERE = Path(__file__).parent
STAKE = D("147")
CONVERSION = D(".0025")
BOOK_MAX_AGE = timedelta(seconds=2)


def price_levels(levels, size, price_factor, taker):
    notional = fee = D(0)
    remaining = size
    for price, available in levels:
        take = min(remaining, D(str(available)))
        price = D(str(price)) * price_factor
        notional += take * price
        fee += take * min(taker, D(".125") * price)
        remaining -= take
        if remaining == 0:
            return notional, fee
    return None


def get_state(path, at):
    state = replay(path, cutoff=at, include_levels=True)
    if state["closed"] or not state["levels"] or not state["index_price"]:
        return None
    if any(at - state[k] > BOOK_MAX_AGE for k in ("book_time", "index_time")):
        return None
    return state


def simulate(path, entry, exit_, spec, markup, haircut, fraction=D(".5")):
    start = get_state(path, entry)
    if not start:
        return {"status": "entry_data_unavailable_or_stale"}
    assert spec["settlement_currency"] == spec["base_currency"] == "BTC" and spec["contract_size"] == 1
    step, taker = (D(str(spec[k])) for k in ("min_trade_amount", "taker_commission"))
    assert step > 0
    buying_factor = D(str(start["index_price"]))*(1+CONVERSION)
    asks = sorted(start["levels"]["asks"].items())
    if not asks:
        return {"status": "no_asks"}
    minimum = price_levels(asks, step, 1+markup, taker)
    minimum_cost = sum(minimum) * buying_factor if minimum else None
    upper = min(int(sum(D(str(q)) for _,q in asks) / step),
                int(STAKE * fraction / (D(str(asks[0][0])) * (1+markup) * buying_factor * step)))
    for count in range(upper, 0, -1):
        size = count * step
        premium, fee = price_levels(asks, size, 1+markup, taker)
        spent = (premium+fee) * buying_factor
        if spent <= STAKE * fraction:
            break
    else:
        return {"status": "minimum_or_visible_size_over_budget",
                "minimum_cost_usd": str(minimum_cost) if minimum_cost is not None else None}
    result = {"units": str(size), "spent_usd": str(spent), "buy_fee_btc": str(fee)}
    end = get_state(path, exit_)
    if not end:
        return result | {"status": "exit_data_unavailable_or_stale"}
    sold = price_levels(sorted(end["levels"]["bids"].items(),reverse=True), size, 1-haircut, taker)
    if not sold:
        return result | {"status": "insufficient_bid_size"}
    premium, fee = sold
    proceeds = (premium-fee) * D(str(end["index_price"])) * (1-CONVERSION)
    return result | {"status": "modeled", "sale_usd": str(proceeds), "sell_fee_btc": str(fee),
                     "ending_usd": str(STAKE-spent+proceeds)}


def main():
    path = Path(sys.argv[1])
    with path.open() as f:
        header = json.loads(next(f))
    start = datetime.fromisoformat(header["utc"])
    entry, exit_ = (start+timedelta(seconds=x) for x in (4, 12))
    spec = json.loads((HERE/"source_probe.json").read_text())["deribit"]["instrument"]
    if header["data"]["channel"] != f"book.{spec['instrument_name']}.100ms":
        raise ValueError("Capture does not match option metadata")
    out = {"sha256":hashlib.sha256(path.read_bytes()).hexdigest(), "mechanics_only":True,
           "instrument":spec["instrument_name"], "max_premium_usd":str(STAKE/2),
           "entry":entry.isoformat(), "exit":exit_.isoformat(),
           "cases":{label:simulate(path,entry,exit_,spec,D(buy),D(sell)) for label,buy,sell in
                    (("base",".15",".05"),("higher",".35",".15"))}}
    print(json.dumps(out,indent=2))


if __name__ == "__main__":
    main()
