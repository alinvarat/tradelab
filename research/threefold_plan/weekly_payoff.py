"""Solve required expiry movement for the saved inverse option quotes."""
from datetime import date, timedelta
from decimal import Decimal as D
import gzip
import hashlib
import json
from pathlib import Path

from deribit_execution import CONVERSION, STAKE, price_levels

HERE = Path(__file__).parent
QUOTE = HERE / "weekly_depth_20261123.json"
SPOT = HERE.parent / "sixfold/spot_inputs.json.gz"


def history(rows):
    past = []
    for day, bar in rows.items():
        d = date.fromisoformat(day)
        if d.weekday() != 0 or not 2024 <= d.year <= 2026:
            continue
        friday = d + timedelta(days=4)
        if friday.month != d.month or friday.isoformat() not in rows:
            continue
        past.append(D(str(rows[friday.isoformat()][0]))/D(str(bar[0]))-1)
    return past


def evaluate(choice, markup, target):
    spec = choice["instrument"]
    book = choice["book"]["payload"]["result"]
    step, fee, strike = [D(str(spec[k])) for k in ("min_trade_amount","taker_commission","strike")]
    spot = D(str(book["index_price"]))
    ask = book["asks"]
    fx = spot*(1+CONVERSION)
    upper = min(int(sum(D(str(q)) for _,q in ask)/step),
                int(STAKE/2/(D(str(ask[0][0]))*(1+markup)*fx*step)))
    for n in range(upper,0,-1):
        size = n*step
        spent = sum(price_levels(ask,size,1+markup,fee))*fx
        if spent<=STAKE/2:
            break
    else:
        return None

    def net(settlement):
        delta = settlement-strike if spec["option_type"]=="call" else strike-settlement
        intrinsic = max(D(0),delta)
        delivery = min(D(".00015")*settlement,D(".125")*intrinsic)
        return STAKE-spent+size*(intrinsic-delivery)*(1-CONVERSION)

    up = spec["option_type"]=="call"
    low, high = (strike,strike*2) if up else (D(0),strike)
    if not up and net(low)<STAKE*target:
        return {"size":str(size),"spent_usd":str(spent),"target_impossible_even_at_zero":True}
    while up and net(high)<STAKE*target:
        high *= 2
    for _ in range(75):
        midpoint = (low+high)/2
        if (net(midpoint)>=STAKE*target) == up:
            high = midpoint
        else:
            low = midpoint
    level = high if up else low
    assert abs(net(level)-STAKE*target)<D(".00001")
    return {"size":str(size),"spent_usd":str(spent),"settlement":str(level),
            "move_from_book_index":str(level/spot-1)}


def main():
    raw, hraw = QUOTE.read_bytes(), gzip.decompress(SPOT.read_bytes())
    saved, prices = json.loads(raw)["assets"], json.loads(hraw)["markets"]
    out={"mechanics_only":True,"quote_sha256":hashlib.sha256(raw).hexdigest(),
         "spot_sha256":hashlib.sha256(hraw).hexdigest(),"assets":{}}
    for asset,v in saved.items():
        past = history(prices[asset+"USDT"])
        rows = out["assets"][asset] = {"historical_windows":len(past),"sides":{}}
        for side,choice in v["choices"].items():
            values = rows["sides"][side] = {}
            for label,markup in (("base", D(".15")),("higher",D(".35"))):
                for target in (3,6):
                    result = evaluate(choice,markup,target)
                    if result and (move:=result.get("move_from_book_index")):
                        result["historical_move_count"] = sum(
                            (x>=D(move) if side=="call" else x<=D(move)) for x in past)
                    values[f"{label}_{target}x"] = result
    (HERE/"weekly_payoff_results.json").write_text(json.dumps(out,indent=2)+"\n")


if __name__=="__main__":
    main()
