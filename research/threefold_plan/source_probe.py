"""Capture two public order-book samples. Does not send or simulate an order."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUT = Path(__file__).with_name("source_probe.json")


def capture(url):
    start = datetime.now(timezone.utc)
    with urlopen(Request(url, headers={"User-Agent": "TradeLab research"}), timeout=15) as r:
        data = json.load(r)
    return {"url": url, "sent_utc": start.isoformat(),
            "received_utc": datetime.now(timezone.utc).isoformat(), "payload": data}


def deribit():
    base = "https://www.deribit.com/api/v2/public/"
    catalog = capture(base + "get_instruments?currency=BTC&kind=option&expired=false")
    rows = [r for r in catalog["payload"]["result"] if r["is_active"] and r["option_type"] == "call"]
    expiry = min(r["expiration_timestamp"] for r in rows)
    index = capture(base + "get_index_price?index_name=btc_usd")
    spot = index["payload"]["result"]["index_price"]
    spec = min((r for r in rows if r["expiration_timestamp"] == expiry),
               key=lambda r: (abs(r["strike"]-spot), r["instrument_name"]))
    url = base + "get_order_book?" + urlencode({"instrument_name": spec["instrument_name"], "depth": 10})
    return {"instrument": spec, "index": index, "book": capture(url)}


def main():
    with ThreadPoolExecutor(2) as pool:
        spot = pool.submit(capture, "https://data-api.binance.vision/api/v3/depth?symbol=BTCUSDT&limit=10")
        opt = pool.submit(deribit)
        result = {"binance": spot.result(), "deribit": opt.result()}
    OUT.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
