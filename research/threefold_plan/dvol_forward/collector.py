"""Read-only Deribit snapshot for the DVOL forward test (see protocol.md). No orders, no keys."""
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://www.deribit.com/api/v2/public/"
RAW = Path(__file__).parent / "raw"


def call(method, **params):
    for wait in (0.5, 2, 5, None):
        try:
            return _call(method, **params)
        except HTTPError as exc:
            if exc.code != 429 or wait is None:
                raise
            time.sleep(wait)


def _call(method, **params):
    time.sleep(0.12)
    req = Request(API + method + "?" + urlencode(params), headers={"User-Agent": "tradelab-research"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read())["result"]


def friday_expiry(now):
    friday = (now + timedelta(days=(4 - now.weekday()) % 7)).date()
    return datetime(friday.year, friday.month, friday.day, 8, tzinfo=timezone.utc)


def main():
    started = datetime.now(timezone.utc)
    ms = lambda d: int(d.timestamp() * 1000)
    out = {"started_utc": started.isoformat(), "errors": []}
    try:
        out["dvol_hourly"] = call("get_volatility_index_data", currency="BTC", resolution="3600",
                                  start_timestamp=ms(started - timedelta(hours=6)), end_timestamp=ms(started))
        out["dvol_daily"] = call("get_volatility_index_data", currency="BTC", resolution="1D",
                                 start_timestamp=ms(started - timedelta(days=100)), end_timestamp=ms(started))
        out["index"] = call("get_index_price", index_name="btc_usd")
        expiry = ms(friday_expiry(started))
        out["expiry_ms"] = expiry
        instruments = [i for i in call("get_instruments", currency="BTC", kind="option", expired="false")
                       if i["expiration_timestamp"] == expiry
                       and 0.75 <= i["strike"] / out["index"]["index_price"] <= 1.25]
        out["instruments"] = instruments
        out["books"] = {}
        for inst in instruments:
            name = inst["instrument_name"]
            try:
                book = call("get_order_book", instrument_name=name, depth=10)
                book["received_utc"] = datetime.now(timezone.utc).isoformat()
                out["books"][name] = book
            except Exception as exc:  # keep partial snapshot, record gap
                out["errors"].append([name, repr(exc)])
    except Exception as exc:
        out["errors"].append(["fatal", repr(exc)])
    out["finished_utc"] = datetime.now(timezone.utc).isoformat()
    RAW.mkdir(exist_ok=True)
    path = RAW / (started.strftime("%Y%m%dT%H%M%SZ") + ".json.gz")
    path.write_bytes(gzip.compress(json.dumps(out).encode()))
    print(path, len(out.get("books", {})), "books", len(out["errors"]), "errors")


if __name__ == "__main__":
    main()
