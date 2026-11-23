"""Fetch public Deribit expired instruments, prints and official BTC delivery prices."""
import gzip
import hashlib
import json
import math
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
HISTORY = "https://history.deribit.com/api/v2/public/"
LIVE = "https://www.deribit.com/api/v2/public/"
MONTHS = [(year, month) for year in range(2021, 2026) for month in range(1, 13)]


def rpc(host, name, **params):
    url = host + name + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "TradeLab research"})
    for retry in range(4):
        try:
            with urlopen(request, timeout=12) as response:
                raw = json.load(response)
            return raw["result"]
        except HTTPError as exc:
            body = exc.read()
            try:
                reason = json.loads(body)["error"]["data"]["reason"]
            except (ValueError, KeyError, TypeError):
                reason = ""
            if exc.code == 400 and name == "get_instrument" and reason in {
                "instrument name is invalid", "instrument is invalid", "unknown instrument name",
                "instrument not found", "wrong format"
            }:
                return None
            if exc.code != 429 and exc.code < 500:
                raise ValueError(url, str(body[:900])) from exc
            if retry == 3:
                raise
        except OSError:
            if retry == 3:
                raise
        time.sleep(1 + retry)
    raise RuntimeError(url)


def ms(utc):
    return int(utc.timestamp()) * 1000


def trade_range(symbol, start, end, count=1000, sorting="asc"):
    return rpc(HISTORY, "get_last_trades_by_instrument_and_time", instrument_name=symbol,
               start_timestamp=start, end_timestamp=end, count=count, sorting=sorting)


def pre_index(stamp):
    rows = trade_range("BTC-PERPETUAL", stamp - 60_000, stamp - 1, count=1, sorting="desc")["trades"]
    return rows[0] if rows else None


def delivery(offset):
    return rpc(LIVE, "get_delivery_prices", index_name="btc_usd", count=100, offset=offset)["data"]


def options_month(month):
    year, mo = month
    open_time = datetime(year, mo, 1, 9, tzinfo=timezone.utc)
    expiry = datetime(year, mo, monthrange(year, mo)[1], 8, tzinfo=timezone.utc)
    expiry -= timedelta(days=(expiry.weekday() - 4) % 7)
    t0 = ms(open_time)
    now = pre_index(t0)
    week_ago = pre_index(ms(open_time - timedelta(days=7)))
    row = {"month": open_time.strftime("%Y-%m"), "expiry": expiry.date().isoformat(),
           "chosen_at": t0, "indices": [week_ago, now], "options": {}}
    if now is None or week_ago is None:
        return row
    for otm in (20, 10):
        for sign in ("C", "P"):
            if sign == "C":
                strike = math.ceil(now["index_price"] * (1 + otm / 100) / 1000) * 1000
            else:
                strike = math.floor(now["index_price"] * (1 - otm / 100) / 1000) * 1000
            name = f"BTC-{expiry.day}{expiry:%b%y}-{strike}-{sign}".upper()
            spec = rpc(LIVE, "get_instrument", instrument_name=name)
            sample = {"name": name, "strike": strike, "spec": spec, "first_print": None}
            row["options"][f"{otm}{sign}"] = sample
            if spec is None or spec["creation_timestamp"] > t0:
                continue
            assert spec["expiration_timestamp"] == ms(expiry) and spec["strike"] == strike
            trades = trade_range(name, t0, t0 + 7_200_000)
            for tr in trades["trades"]:
                if (tr["direction"] == "buy" and tr["amount"] >= spec["min_trade_amount"]
                        and not any(tr.get(flag) for flag in ("block_trade_id", "combo_id", "liquidation"))):
                    assert t0 <= tr["timestamp"] <= t0 + 7_200_000, tr
                    sample["first_print"] = tr
                    break
            if trades["has_more"] and sample["first_print"] is None:
                raise ValueError("Incomplete prints for", name, t0)
    return row


def main():
    # The newest settlement page establishes the offset. API counts limit each page to 100.
    recent = delivery(0)
    recent_day = datetime.fromisoformat(recent[0]["date"]).date()
    start = (recent_day - datetime(2025, 12, 31).date()).days
    end = (recent_day - datetime(2021, 1, 1).date()).days
    with ThreadPoolExecutor(8) as pool:
        price_iter = pool.map(delivery, range(max(0, start), end + 1, 100))
        months_iter = pool.map(options_month, MONTHS)
        prices = {r["date"]: r["delivery_price"] for page in price_iter for r in page}
        months = list(months_iter)
    for row in months:
        row["official_settlement_usd"] = prices[row["expiry"]]
    result = {"trade_source_root": HISTORY, "delivery_source_root": LIVE, "rows": months}
    raw = json.dumps(result, separators=(",", ":")).encode()
    (HERE / "options_inputs.json.gz").write_bytes(gzip.compress(raw, mtime=0))
    print("options_inputs.json.gz", len(months), hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
