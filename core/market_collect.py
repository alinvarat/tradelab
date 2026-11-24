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
VENUE_EVERY, DERIBIT_EVERY, LISTING_EVERY = 5, 30 * 60, 30
MIN_FREE_BYTES = 200e6
MAX_DAYS = 30                      # option expiries kept
UA = {"User-Agent": "tradelab-research"}
STATUS = {"venues": {"rows": 0, "last_ts": None, "errors": 0}, "deribit": {"rows": 0, "last_ts": None, "errors": 0},
          "listings": {"polls": 0, "errors": 0, "last_error": None}, "last_error": None, "paused_low_disk": False}
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



# ------------------------------------------------------------------ L1b listing notices + forward paper ledger
# research/studies/protocol_L1b_listings_forward.md: enter 60 s after a notice is first seen, exit 4 h later.
L1B_START_EQUITY = 147.0
MAX_NOTICE_AGE_S = 15 * 60


def _l1b_path():
    return DIR / "listings_state.json"


def _l1b_load():
    try:
        return json.loads(_l1b_path().read_text())
    except Exception:  # noqa: BLE001  first run or unreadable state starts clean
        return {"seen": [], "pending": [], "closed": [], "equity": L1B_START_EQUITY}


def _l1b_save(st):
    if not disk_ok():
        return
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = _l1b_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(st, separators=(",", ":")))
    tmp.replace(_l1b_path())


def listing_notices():
    from core import screens as sc
    ev, errors = [], {}
    try:
        d = get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=1&pageSize=20", 10)
        for a in (((d.get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []):
            for sym in sc.binance_listing_symbols(a.get("title", "")):
                ev.append({"venue": "binance", "symbol": sym, "ts": a["releaseDate"] / 1000, "title": a["title"][:120]})
    except Exception as e:  # noqa: BLE001  one blocked venue must not stop the other
        errors["binance"] = repr(e)[:120]
    try:
        d = get("https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=20&category=trade", 10)
        for n in ((d.get("data") or {}).get("notices") or []):
            for sym in sc.upbit_listing_symbols(n.get("title", "")):
                ev.append({"venue": "upbit", "symbol": sym, "title": n["title"][:120],
                           "ts": datetime.fromisoformat(n["first_listed_at"]).timestamp()})
    except Exception as e:  # noqa: BLE001
        errors["upbit"] = repr(e)[:120]
    STATUS["listings"]["venue_errors"] = errors or None
    return ev


def quote(sym):
    """(venue, bid, ask) for SYM-USDT: KuCoin level 1, else Binance spot book ticker, else None."""
    try:
        d = get(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={sym}-USDT", 8).get("data")
        if d and d.get("bestBid") and d.get("bestAsk"):
            return "kucoin", float(d["bestBid"]), float(d["bestAsk"])
    except Exception:  # noqa: BLE001
        pass
    try:
        d = get(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={sym}USDT", 8)
        if d.get("bidPrice") and float(d["bidPrice"]) > 0:
            return "binance", float(d["bidPrice"]), float(d["askPrice"])
    except Exception:  # noqa: BLE001
        pass
    return None


def _btc_mid(venue):
    if venue == "kucoin":
        d = get("https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT", 8)["data"]
        return (float(d["bestBid"]) + float(d["bestAsk"])) / 2
    d = get("https://api.binance.com/api/v3/ticker/bookTicker?symbol=BTCUSDT", 8)
    return (float(d["bidPrice"]) + float(d["askPrice"])) / 2


def listings_once(now=None):
    from core import screens as sc
    now = now or time.time()
    st = _l1b_load()
    seen = set(st["seen"])
    fresh = sc.new_listing_events(seen, listing_notices())
    st["seen"] = sorted(seen)[-2000:]
    fresh = [e for e in fresh if e["ts"] >= now - MAX_NOTICE_AGE_S]   # old notices (first poll, restarts) are not events
    for e in fresh:
        append("listings", {**e, "first_seen": round(now, 1)}, now)
        st["pending"].append({**e, "first_seen": now, "entry_due": now + sc.L1B_DELAY_S})
    keep = []
    for p in st["pending"]:
        try:
            if "entry_ask" not in p and now >= p["entry_due"]:
                q = quote(p["symbol"])
                if not q:
                    st["closed"].append({**p, "skipped": "no USDT market on KuCoin or Binance", "ts": now})
                    continue
                p.update(px_venue=q[0], entry_ask=q[2], btc_entry=_btc_mid(q[0]), entry_ts=now,
                         exit_due=now + sc.L1B_HOLD_S, stake=round(st["equity"] * sc.L1B_STAKE, 4))
            elif "entry_ask" in p and now >= p["exit_due"]:
                q = quote(p["symbol"])
                if q and q[0] == p["px_venue"]:
                    r = sc.l1b_result(p["entry_ask"], q[1], p["btc_entry"], _btc_mid(q[0]))
                    st["equity"] = round(st["equity"] + p["stake"] * r["net"], 4)
                    row = {**p, **r, "exit_bid": q[1], "ts": now, "equity_after": st["equity"]}
                    st["closed"].append(row)
                    append("listing_trades", row, now)
                    continue
        except Exception as e:  # noqa: BLE001  a quote failure retries on the next poll
            STATUS["listings"]["last_error"] = repr(e)[:200]
        keep.append(p)
    st["pending"] = keep
    _l1b_save(st)
    STATUS["listings"]["polls"] += 1
    return st


def listings_view() -> dict:
    from core import sequential as sq
    st = _l1b_load()
    done = [c for c in st["closed"] if "net" in c]
    ev = sq.run(sq.daily_means([{"ts": c["ts"], "ret": c["net"]} for c in done]), lo=1.0, hi=5.0)
    return {"equity_usd": st["equity"], "start_usd": L1B_START_EQUITY, "goal_usd": 3 * L1B_START_EQUITY,
            "pending": st["pending"], "closed": st["closed"][-30:], "n_closed": len(done), "sequential": ev,
            "protocol": "research/studies/protocol_L1b_listings_forward.md"}

def loop():
    last_deribit = last_listing = 0.0
    while True:
        t0 = time.time()
        try:
            venues_once()
        except Exception as e:  # noqa: BLE001
            STATUS["last_error"] = repr(e)[:200]
            traceback.print_exc()
        if t0 - last_listing >= LISTING_EVERY:
            last_listing = t0
            try:
                listings_once(t0)
            except Exception as e:  # noqa: BLE001
                STATUS["listings"]["errors"] += 1
                STATUS["listings"]["last_error"] = repr(e)[:200]
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
    return {**STATUS, "files": files, "dir": str(DIR), "l1b": listings_view()}
