"""Join a verified public removal notice to current bid/ask depth."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from book_pilot import STAKE, sweep
from source_probe import capture

HERE = Path(__file__).parent
NOTICE = HERE / "delist_event_20261120.json"
DATA = HERE / "delist_depth_20261123.json"
RESULT = HERE / "delist_depth_results.json"


def download(symbol, market):
    url = ("https://api.bytick.com/v5/market/orderbook?" + urlencode(
        {"category":"spot","symbol":symbol,"limit":50}) if market=="bybit" else
        "https://data-api.binance.vision/api/v3/depth?" + urlencode({"symbol":symbol,"limit":50}))
    try:
        return capture(url)
    except HTTPError as exc:
        return {"url":url,"status":exc.code,"error_body":exc.read().decode("utf-8",errors="replace")}
    except URLError as exc:
        return {"url":url,"error":str(exc)}


def acquire(event):
    tasks = [(s, m) for s in event["symbols"] for m in ("bybit","binance")]
    with ThreadPoolExecutor(6) as pool:
        quotes = list(pool.map(lambda t:download(*t), tasks))
    data = {symbol:{} for symbol in event["symbols"]}
    for (symbol,market),quote in zip(tasks,quotes):
        data[symbol][market]=quote
    DATA.write_text(json.dumps({"event":event,"quotes":data},indent=2)+"\n")


def evaluate(payload):
    if payload.get("retCode") != 0 or not payload.get("result"):
        return {"status":"book_unavailable"}
    book = payload["result"]
    asks, bids = book["a"],book["b"]
    if not asks or not bids:
        return {"status":"one_sided"}
    result={"status":"two_sided",
            "spread_ratio":str((D(asks[0][0])-D(bids[0][0]))/D(asks[0][0])), "cases":{}}
    for label, fee in (("base",D(".0035")),("higher",D(".01"))):
        buy = sweep(asks, STAKE/(1+fee),by_quote=True)
        sell = sweep(bids,buy[0]) if buy else None
        result["cases"][label]={"can_sweep_both_legs":bool(sell),
                                "ending_usdt":str(sell[1]*(1-fee)) if sell else None}
    return result


def main():
    event=json.loads(NOTICE.read_text())
    if not DATA.exists():
        acquire(event)
    data=json.loads(DATA.read_text())
    assert data["event"]==event
    published = datetime.fromtimestamp(event["publish_time_ms"]/1000,timezone.utc)
    stop = datetime.fromisoformat(event["stop_utc"])
    output={"notice":event["notice"],"published":published.isoformat(),"diagnostic_only":True,"pairs":{}}
    for s,quotes in data["quotes"].items():
        sample=quotes["bybit"]
        row=evaluate(sample.get("payload",{}))
        if "received_utc" in sample:
            received=datetime.fromisoformat(sample["received_utc"])
            assert published < received < stop
            row["hours_since_publish"]=(received-published).total_seconds()/3600
        other=quotes["binance"].get("payload",{})
        row["same_symbol_binance_book"] = bool(other.get("bids") and other.get("asks"))
        output["pairs"][s]=row
    RESULT.write_text(json.dumps(output,indent=2)+"\n")


if __name__=="__main__":
    main()
