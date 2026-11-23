"""Measure whether funded target sales were isolated prints or sustained opportunities."""
import gzip
import hashlib
import json
from datetime import datetime, timezone

from .options import CONVERSION
from .options_fetch import HERE
from .options_hit_overlap import RESULT as HITS, SOURCES
from .options_weekly import SNAPSHOT


def examine(step, month_target, markets):
    instrument = step["instrument"]
    data = markets["BTC"]
    sample = next(r for r in data["rows"] if r["entry_day"] == step["entry_day"])
    fee = sample["options"]["20" + step["side"]]["spec"]["taker_commission"]
    size = step["contract_units"]
    cash = step["starting"] - step["spent_usd"]
    source = step["sale_print"]
    output = {}
    for haircut in (.05, .10, .15):
        counted = []
        for trade in data["sales"][instrument]:
            if trade["amount"] < size or trade["timestamp"] < source["timestamp"]:
                continue
            premium = trade["price"] * (1-haircut)
            proceeds = cash + size * (premium-min(fee,.125*premium)) * trade["index_price"] * (1-CONVERSION)
            counted.append((trade, proceeds))
        target_sales = [(trade, amount) for trade, amount in counted if amount + 1e-10 >= month_target]
        row = {"full_size_sell_prints": len(counted), "at_target": len(target_sales),
               "best_usd": max((x for _,x in counted), default=None),
               "seconds_until_last_target": ((target_sales[-1][0]["timestamp"] - source["timestamp"]) / 1000
                                              if target_sales else None), "after_delay": {}}
        for minutes in (0, 5, 60, 1440):
            delay = source["timestamp"] + minutes*60_000
            later = next(((tr,val) for tr,val in target_sales if tr["timestamp"] >= delay), None)
            row["after_delay"][minutes] = ({"id": later[0]["trade_id"], "cash": later[1],
                "time": datetime.fromtimestamp(later[0]["timestamp"]/1000,timezone.utc).isoformat()} if later else None)
        output[str(haircut)] = row
    return output


def main():
    hit_raw = HITS.read_bytes()
    hit_data = json.loads(hit_raw)
    weekly_raw = gzip.decompress(SNAPSHOT.read_bytes())
    markets = json.loads(weekly_raw)["assets"]
    output = {"overlap_sha256": hashlib.sha256(hit_raw).hexdigest(),
              "weekly_sha256": hashlib.sha256(weekly_raw).hexdigest(), "events": {}}
    for hit in hit_data["funded_months"]:
        label = hit["rule"]
        keys, orders = SOURCES[label]
        rows = json.loads((HERE / f"options_{label}_results.json").read_bytes())
        for key in keys:
            rows = rows[key]
        month = next(row for row in rows if row["month"] == hit["month"])
        for step in month[orders]:
            if step.get("modeled_exit") == "early":
                ticket = step["sale_print"]["trade_id"]
                output["events"][ticket] = examine(step, 3*hit["start"], markets)
    (HERE / "options_exit_window_results.json").write_text(json.dumps(output,indent=2)+"\n")


if __name__ == "__main__":
    main()
