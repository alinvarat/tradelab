"""Deribit DVOL + option-book snapshot for the locked DVOL forward test (research/threefold_plan/dvol_forward/protocol.md),
as a function plus a scheduler so the app can take the Monday 09:00 and 09:05 UTC snapshots by itself (no personal machine).
Read-only public data, no orders, no keys."""
from datetime import datetime, timedelta, timezone
import gzip
import json
import os
from pathlib import Path
import threading
import traceback
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://www.deribit.com/api/v2/public/"
RAW = Path(os.environ.get("TRADELAB_DVOL_DIR") or Path(__file__).resolve().parent.parent / "research/threefold_plan/dvol_forward/raw")


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


WINDOW_END = datetime(2027, 2, 23, tzinfo=timezone.utc)  # protocol window ends with the 2027-02-22 entry


def main():
    started = datetime.now(timezone.utc)
    if started >= WINDOW_END:
        print("outside the locked test window; nothing collected")
        return
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
    return {"path": str(path), "books": len(out.get("books", {})), "errors": len(out["errors"])}


WINDOW_START = datetime(2026, 11, 30, tzinfo=timezone.utc)
SLOTS = ((9, 0), (9, 5))          # Monday UTC hh:mm of the two snapshots (protocol)
STATUS: dict = {"taken": [], "last_error": None, "next_slot": None}


def mark_taken(slot, info):
    """A slot counts as taken only when the snapshot has books and no errors; a partial file is kept for audit but the
    week must stay cash for every arm, and the collector retries inside the same 45-second slot."""
    if info and not info.get("errors") and info.get("books"):
        STATUS["taken"].append(slot)
        return True
    STATUS["last_error"] = f"{slot}: incomplete snapshot (books={(info or {}).get('books', 0)}, errors={(info or {}).get('errors', 'raised')})"
    return False


def due_slot(now):
    """The (date, hh:mm) slot that should be taken at `now` (UTC), or None. Slots last 45 s, protocol window only."""
    if not (WINDOW_START <= now < WINDOW_END) or now.weekday() != 0:
        return None
    for h, m in SLOTS:
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if 0 <= (now - start).total_seconds() < 45:
            return f"{now:%Y-%m-%d} {h:02d}:{m:02d}"
    return None


def loop(take=main):
    """Check the clock every 15 s and take each slot once; a failed snapshot is logged, never retried late (the protocol
    treats a late or partial snapshot as invalid, so the week simply counts as cash)."""
    while True:
        try:
            now = datetime.now(timezone.utc)
            slot = due_slot(now)
            if slot and slot not in STATUS["taken"]:
                info = take()
                mark_taken(slot, info)
        except Exception as exc:  # noqa: BLE001
            STATUS["last_error"] = repr(exc)[:200]
            traceback.print_exc()
        time.sleep(15)


if __name__ == "__main__":
    main()
