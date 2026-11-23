"""Screen fixed BTC/ETH weekly choices using public current quote depth."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal as D
import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from deribit_execution import CONVERSION, price_levels
from source_probe import capture

API = "https://www.deribit.com/api/v2/public/"
BUDGET = D("73.5")


def fetch(method, **params):
    return capture(API + method + "?" + urlencode(params))


def screen(asset, expiry):
    index = fetch("get_index_price", index_name=asset.lower()+"_usd")
    spot = index["payload"]["result"]["index_price"]
    catalog = fetch("get_instruments", currency=asset, kind="option", expired="false")
    rows = catalog["payload"]["result"]
    choices = {}
    for side, sign in (("call",1),("put",-1)):
        eligible = []
        for row in rows:
            if (not row["is_active"] or row["settlement_currency"] != asset or row["option_type"] != side
                    or row["expiration_timestamp"] != expiry or row["creation_timestamp"] > int(
                        datetime.fromisoformat(index["received_utc"]).timestamp()*1000)):
                continue
            distance = sign * (row["strike"]/spot - 1)
            if .06 <= distance <= .11:
                eligible.append((round(abs(distance-.085),12), -distance,row["instrument_name"],row))
        if not eligible:
            choices[side] = {"status":"no_eligible_strike"}
            continue
        _, reverse, symbol, spec = min(eligible)
        quote = fetch("get_order_book", instrument_name=symbol, depth=10)
        data = quote["payload"]["result"]
        step, fee = (D(str(spec[k])) for k in ("min_trade_amount","taker_commission"))
        index_price = D(str(data["index_price"]))
        terms = {}
        for name, markup in (("base",D(".15")),("higher",D(".35"))):
            purchase = price_levels(data["asks"], step, 1+markup, fee)
            cost = sum(purchase)*index_price*(1+CONVERSION) if purchase is not None else None
            terms[name] = {"minimum_cost_usd":str(cost) if cost is not None else None,
                           "fits":cost is not None and cost <= BUDGET}
        choices[side] = {"instrument":spec,"distance":-reverse,"eligible_strikes":len(eligible),
                         "book":quote,"quoted_bid_covers_minimum":sum(D(str(q)) for _,q in data["bids"]) >= step,
                         "cases":terms}
    return {"index":index,"choices":choices}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expiry", help="Friday date in UTC YYYY-MM-DD")
    parser.add_argument("output",type=Path)
    args = parser.parse_args()
    expiry = datetime.fromisoformat(args.expiry).replace(hour=8,tzinfo=timezone.utc)
    if expiry.weekday() != 4:
        parser.error("expiry must be Friday")
    with ThreadPoolExecutor(2) as pool:
        rows = dict(zip(("BTC","ETH"),pool.map(lambda a:screen(a,int(expiry.timestamp()*1000)),("BTC","ETH"))))
    output = {"mechanics_only":True,"expiry":expiry.isoformat(),"budget_usd":str(BUDGET),"assets":rows}
    with args.output.open("x") as handle:
        json.dump(output,handle,indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
