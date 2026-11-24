"""Forward data collectors for the untested ideas in research/IDEAS_codex_20261124.md (no trading, no keys, no LLM).

- venues: best bid/ask for BTC, ETH and stablecoins on Coinbase, Kraken and Binance every 5 s, fetched in parallel and
  stamped on receipt (cross-venue lead-lag, stablecoin de-pegs).
- deribit: every BTC/ETH option expiring within 30 days (bid, ask, mark IV, open interest, volume) every 30 min
  (option smile dislocations).
Each stream appends gzip JSON lines to <dir>/<stream>/YYYY-MM-DD.jsonl.gz. Writing stops when the volume has less than
MIN_FREE_BYTES free, so the collectors can never fill the disk the trading state lives on.
"""
import gzip
import json
import os
import re
import shutil
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

DIR = Path(os.environ.get("TRADELAB_COLLECT_DIR") or Path(__file__).resolve().parent.parent / "data/collect")
VENUE_EVERY, DERIBIT_EVERY = 5, 30 * 60
MIN_FREE_BYTES = 200e6
MAX_DAYS = 30                      # option expiries kept
UA = {"User-Agent": "tradelab-research"}
STATUS = {"venues": {"rows": 0, "last_ts": None, "errors": 0}, "deribit": {"rows": 0, "last_ts": None, "errors": 0},
          "last_error": None, "paused_low_disk": False}
_lock = threading.Lock()

COINBASE = ("BTC-USD", "ETH-USD", "USDT-USD")
KRAKEN = "XBTUSD,ETHUSD,USDCUSD,USDTUSD"
BINANCE = ("BTCUSDT", "ETHUSDT", "USDCUSDT")


def get(url, timeout=8):
    with urlopen(Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read())


# ------------------------------------------------------------------ parsers (pure, tested offline)
def parse_coinbase(product: str, d: dict) -> dict:
    return {"venue": "coinbase", "pair": product, "bid": float(d["bid"]), "ask": float(d["ask"]),
            "venue_time": d.get("time")}


def parse_kraken(d: dict) -> list:
    out = []
    for pair, v in (d.get("result") or {}).items():
        out.append({"venue": "kraken", "pair": pair, "bid": float(v["b"][0]), "ask": float(v["a"][0])})
    return out


def parse_binance(rows: list) -> list:
    return [{"venue": "binance", "pair": r["symbol"], "bid": float(r["bidPrice"]), "ask": float(r["askPrice"])}
            for r in rows]


_MON = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


def deribit_expiry(name: str):
    """'BTC-29NOV26-90000-C' -> expiry timestamp (08:00 UTC), or None."""
    m = re.match(r"^[A-Z]+-(\d{1,2})([A-Z]{3})(\d{2})-", name)
    if not m or m.group(2) not in _MON:
        return None
    return datetime(2000 + int(m.group(3)), _MON[m.group(2)], int(m.group(1)), 8, tzinfo=timezone.utc).timestamp()


def slim_deribit(rows: list, now: float, max_days: int = MAX_DAYS) -> list:
    out = []
    for r in rows:
        exp = deribit_expiry(r.get("instrument_name", ""))
        if exp is None or not now < exp <= now + max_days * 86400:
            continue
        out.append({"i": r["instrument_name"], "b": r.get("bid_price"), "a": r.get("ask_price"), "iv": r.get("mark_iv"),
                    "m": r.get("mark_price"), "u": r.get("underlying_price"), "oi": r.get("open_interest"),
                    "v": r.get("volume")})
    return out


# ------------------------------------------------------------------ storage
def disk_ok(path: Path = None) -> bool:
    path = path or DIR
    probe = path if path.exists() else path.parent
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free >= MIN_FREE_BYTES


def append(stream: str, obj: dict, now: float = None, base: Path = None) -> bool:
    base = base or DIR
    if not disk_ok(base):
        STATUS["paused_low_disk"] = True
        return False
    STATUS["paused_low_disk"] = False
    day = time.strftime("%Y-%m-%d", time.gmtime(now or time.time()))
    d = base / stream
    d.mkdir(parents=True, exist_ok=True)
    with _lock, gzip.open(d / f"{day}.jsonl.gz", "at") as f:    # gzip members concatenate into one readable file
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    return True


# ------------------------------------------------------------------ collectors
_pool = ThreadPoolExecutor(6)


def venues_once():
    t0 = time.time()
    jobs = {p: _pool.submit(get, f"https://api.exchange.coinbase.com/products/{p}/ticker") for p in COINBASE}
    jobs["kraken"] = _pool.submit(get, f"https://api.kraken.com/0/public/Ticker?pair={KRAKEN}")
    jobs["binance"] = _pool.submit(get, "https://api.binance.com/api/v3/ticker/bookTicker?symbols="
                                   + json.dumps(list(BINANCE), separators=(",", ":")))
    quotes, errors = [], {}
    for key, fut in jobs.items():
        try:
            d = fut.result(timeout=10)
            if key == "kraken":
                quotes += parse_kraken(d)
            elif key == "binance":
                quotes += parse_binance(d)
            else:
                quotes.append(parse_coinbase(key, d))
        except Exception as e:  # noqa: BLE001  (a venue blocked from this region is just a gap)
            errors[key] = repr(e)[:120]
    row = {"t": round(t0, 3), "rx": round(time.time(), 3), "q": quotes, "err": errors or None}
    if append("venues", row, t0):
        STATUS["venues"]["rows"] += 1
        STATUS["venues"]["last_ts"] = t0
    if errors:
        STATUS["venues"]["errors"] += 1
    return row


def deribit_once():
    now = time.time()
    out = {"t": round(now, 1)}
    for cur in ("BTC", "ETH"):
        d = get(f"https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={cur}&kind=option", 20)
        out[cur] = slim_deribit(d.get("result") or [], now)
    if append("deribit", out, now):
        STATUS["deribit"]["rows"] += 1
        STATUS["deribit"]["last_ts"] = now
    return out


def loop():
    last_deribit = 0.0
    while True:
        t0 = time.time()
        try:
            venues_once()
        except Exception as e:  # noqa: BLE001
            STATUS["last_error"] = repr(e)[:200]
            traceback.print_exc()
        if t0 - last_deribit >= DERIBIT_EVERY:
            last_deribit = t0
            try:
                deribit_once()
            except Exception as e:  # noqa: BLE001
                STATUS["deribit"]["errors"] += 1
                STATUS["last_error"] = repr(e)[:200]
        time.sleep(max(0.5, VENUE_EVERY - (time.time() - t0)))


def view() -> dict:
    files = {}
    if DIR.exists():
        for f in sorted(DIR.glob("*/*.jsonl.gz"))[-20:]:
            files[f"{f.parent.name}/{f.name}"] = f.stat().st_size
    return {**STATUS, "files": files, "dir": str(DIR)}
