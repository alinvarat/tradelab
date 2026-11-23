"""Rebuild Bybit event books at fixed receipt times and model depth sweeps."""
from datetime import datetime, timedelta
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import sys

from book_pilot import STAKE, sweep


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def at_time(records, cutoff):
    states = {}
    for record in records:
        seen = datetime.fromisoformat(record["utc"])
        if seen > cutoff:
            break
        if record["kind"] == "stop":
            return {}
        row = record["data"]
        if record["kind"] != "message" or row.get("type") not in ("snapshot","delta"):
            continue
        data = row["data"]
        symbol = data["s"]
        if row["type"] == "snapshot":
            states[symbol] = {"seq": None, "last": None, "b": {}, "a": {}, "valid": True}
        state = states.get(symbol)
        if not state or not state["valid"]:
            continue
        if state["seq"] is not None and (data["seq"] <= state["seq"] or data["u"] <= state["last"]):
            state["valid"] = False
            continue
        for side in ("b","a"):
            for price, size in data[side]:
                price, size = D(price),D(size)
                if size:
                    state[side][price] = size
                else:
                    state[side].pop(price,None)
        state.update(seq=data["seq"],last=data["u"],received=seen)
    return {symbol:state for symbol,state in states.items() if state["valid"]}


def estimate(records, entry, exit_):
    before = at_time(records,entry)
    after = at_time(records,exit_)
    cases = {}
    for topic in records[0]["data"]["topics"]:
        symbol = topic.rsplit(".",1)[-1]
        s,e = before.get(symbol),after.get(symbol)
        quotes = {}
        for label,fee in (("base",D(".0035")),("higher",D(".01"))):
            if not s or not e or max(entry-s["received"],exit_-e["received"])>timedelta(seconds=2):
                quotes[label]={"status":"stale_or_missing"}
                continue
            buy = sweep(sorted(s["a"].items()),STAKE/(1+fee),by_quote=True)
            sell = sweep(sorted(e["b"].items(),reverse=True),buy[0]) if buy else None
            quotes[label] = ({"status":"modeled","end_usdt":str(sell[1]*(1-fee))} if sell else
                             {"status":"visible_size_insufficient"})
        cases[symbol]=quotes
    return cases


def main():
    path = Path(sys.argv[1])
    records = read(path)
    start = datetime.fromisoformat(records[0]["utc"])
    entry,exit_ = (start+timedelta(seconds=s) for s in (4,12))
    print(json.dumps({"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                     "diagnostic_only":True,"entry":entry.isoformat(),"exit":exit_.isoformat(),
                     "capture_stop":records[-1]["data"],"pairs":estimate(records,entry,exit_)},indent=2))


if __name__=="__main__":
    main()
