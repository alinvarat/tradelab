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


BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
              "Accept": "application/json"}


def get(url, timeout=8, headers=None):
    with urlopen(Request(url, headers=headers or UA), timeout=timeout) as r:
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


LEDGERS = {   # name -> state file, side, hold, extra cost (protocol files in research/studies/)
    "l1b": {"file": "listings_state.json", "side": 1, "hold_s": 4 * 3600, "extra": 0.0,
            "kinds": ("listing",), "protocol": "research/studies/protocol_L1b_listings_forward.md"},
    "l1d": {"file": "futures_short_state.json", "side": -1, "hold_s": 7 * 86400, "extra": 0.007,
            "kinds": ("futures",), "protocol": "research/studies/protocol_L1d_futures_short_forward.md"},
    "l4f": {"file": "polymarket_longshot_state.json", "side": 0, "hold_s": 0, "extra": 0.0, "kinds": (),
            "protocol": "research/studies/protocol_L4f_polymarket_longshot_forward.md", "lo": 1.0, "hi": 0.12},
    "l1f": {"file": "delist_short_state.json", "side": -1, "hold_s": 4 * 3600, "extra": 0.001, "stop": 0.25,
            "kinds": ("delist",), "protocol": "research/studies/protocol_L1f_delist_short_forward.md"},
}


def _ledger_path(name="l1b"):
    return DIR / LEDGERS[name]["file"]


def _l1b_load(name="l1b"):
    try:
        return json.loads(_ledger_path(name).read_text())
    except Exception:  # noqa: BLE001  first run or unreadable state starts clean
        return {"seen": [], "pending": [], "closed": [], "equity": L1B_START_EQUITY}


def _l1b_save(st, name="l1b"):
    if not disk_ok():
        return
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = _ledger_path(name).with_suffix(".tmp")
    tmp.write_text(json.dumps(st, separators=(",", ":")))
    tmp.replace(_ledger_path(name))


def listing_notices():
    from core import screens as sc
    ev, errors = [], {}
    try:
        d = get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=1&pageSize=20", 10)
        for a in (((d.get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []):
            for kind, fn in (("listing", sc.binance_listing_symbols), ("futures", sc.binance_futures_symbols)):
                for sym in fn(a.get("title", "")):
                    ev.append({"kind": kind, "venue": "binance", "symbol": sym, "ts": a["releaseDate"] / 1000,
                               "title": a["title"][:120]})
    except Exception as e:  # noqa: BLE001  one blocked venue must not stop the other
        errors["binance"] = repr(e)[:120]
    try:
        d = get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=161&pageNo=1&pageSize=20", 10)
        for a in (((d.get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []):
            for sym in sc.binance_delist_symbols(a.get("title", "")):
                ev.append({"kind": "delist", "venue": "binance", "symbol": sym, "ts": a["releaseDate"] / 1000,
                           "title": a["title"][:120]})
    except Exception as e:  # noqa: BLE001
        errors["binance_delist"] = repr(e)[:120]
    try:
        d = get("https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=20&category=trade", 10,
                BROWSER_UA)   # the notice API answers 403 to non-browser user agents
        for n in ((d.get("data") or {}).get("notices") or []):
            for sym in sc.upbit_listing_symbols(n.get("title", "")):
                ev.append({"kind": "listing", "venue": "upbit", "symbol": sym, "title": n["title"][:120],
                           "ts": datetime.fromisoformat(n["first_listed_at"]).timestamp()})
    except Exception as e:  # noqa: BLE001
        errors["upbit"] = repr(e)[:120]
    try:   # addendum 2026-11-25 in protocol_L1b_listings_forward.md
        d = get("https://api.kucoin.com/api/v3/announcements?language=en_US&type=new-listings&pageSize=50", 10, BROWSER_UA)
        for n in (((d.get("data") or {}).get("items")) or []):
            if "new-listings" not in (n.get("annType") or []):
                continue
            for sym in sc.kucoin_listing_symbols(n.get("annTitle", "")):
                ev.append({"kind": "listing", "venue": "kucoin", "symbol": sym, "title": n["annTitle"][:120],
                           "ts": n["cTime"] / 1000})
    except Exception as e:  # noqa: BLE001
        errors["kucoin"] = repr(e)[:120]
    try:   # Bitget answers the 10 latest coin_listings; the subtype is not filterable, so the title parser filters spot
        d = get("https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings", 10, BROWSER_UA)
        for n in (d.get("data") or []):
            if n.get("annSubType") != "spot":
                continue
            for sym in sc.bitget_listing_symbols(n.get("annTitle", "")):
                ev.append({"kind": "listing", "venue": "bitget", "symbol": sym, "title": n["annTitle"][:120],
                           "ts": float(n["cTime"]) / 1000})
    except Exception as e:  # noqa: BLE001
        errors["bitget"] = repr(e)[:120]
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


def _ledger_step(name, fresh, now):
    from core import screens as sc
    cfg = LEDGERS[name]
    st = _l1b_load(name)
    for e in fresh:
        if e.get("kind", "listing") in cfg["kinds"]:
            append(f"ledger_{name}_events", {**e, "first_seen": round(now, 1)}, now)
            st["pending"].append({**e, "first_seen": now, "entry_due": now + sc.L1B_DELAY_S})
    keep = []
    for p in st["pending"]:
        try:
            if "entry_px" not in p and now >= p["entry_due"]:
                q = quote(p["symbol"])
                if not q:
                    st["closed"].append({**p, "skipped": "no USDT market on KuCoin or Binance", "ts": now})
                    continue
                p.update(px_venue=q[0], entry_px=q[2] if cfg["side"] > 0 else q[1], btc_entry=_btc_mid(q[0]),
                         entry_ts=now, exit_due=now + cfg["hold_s"], stake=round(st["equity"] * sc.L1B_STAKE, 4))
            elif "entry_px" in p:
                due = now >= p["exit_due"]
                q = quote(p["symbol"]) if (due or cfg.get("stop")) else None
                stopped = bool(q and cfg.get("stop") and q[0] == p["px_venue"]
                               and cfg["side"] * ((q[1] if cfg["side"] > 0 else q[2]) / p["entry_px"] - 1) <= -cfg["stop"])
                if (due or stopped) and q and q[0] == p["px_venue"]:
                    exit_px = q[1] if cfg["side"] > 0 else q[2]
                    r = sc.ledger_result(cfg["side"], p["entry_px"], exit_px, p["btc_entry"], _btc_mid(q[0]), cfg["extra"])
                    st["equity"] = round(st["equity"] + p["stake"] * r["net"], 4)
                    row = {**p, **r, "exit_px": exit_px, "ts": now, "equity_after": st["equity"], "stopped": stopped and not due}
                    st["closed"].append(row)
                    append(f"ledger_{name}_trades", row, now)
                    continue
        except Exception as e:  # noqa: BLE001  a quote failure retries on the next poll
            STATUS["listings"]["last_error"] = repr(e)[:200]
        keep.append(p)
    st["pending"] = keep
    _l1b_save(st, name)
    return st


def listings_once(now=None):
    """Poll the notices once and step every ledger; returns the L1b state (kept for callers and tests)."""
    from core import screens as sc
    now = now or time.time()
    st = _l1b_load("l1b")
    seen = set(st["seen"])
    fresh = sc.new_listing_events(seen, listing_notices())
    fresh = [e for e in fresh if e["ts"] >= now - MAX_NOTICE_AGE_S]   # old notices (first poll, restarts) are not events
    st["seen"] = sorted(seen)[-3000:]
    _l1b_save(st, "l1b")
    out = {name: _ledger_step(name, fresh, now) for name, cfg in LEDGERS.items() if cfg["kinds"]}   # l4f has its own loop
    STATUS["listings"]["polls"] += 1
    return out["l1b"]


def ledger_view(name) -> dict:
    from core import sequential as sq
    st = _l1b_load(name)
    done = [c for c in st["closed"] if "net" in c]
    cfg = LEDGERS[name]
    ev = sq.run(sq.daily_means([{"ts": c["ts"], "ret": c["net"]} for c in done]), lo=cfg.get("lo", 1.0), hi=cfg.get("hi", 5.0))
    return {"equity_usd": st["equity"], "start_usd": L1B_START_EQUITY, "goal_usd": 3 * L1B_START_EQUITY,
            "pending": st["pending"], "closed": st["closed"][-30:], "n_closed": len(done), "sequential": ev,
            "protocol": LEDGERS[name]["protocol"]}


def listings_view() -> dict:
    return ledger_view("l1b")



# ------------------------------------------------------------------ L4f Polymarket long-shot selling (forward paper ledger)
# research/studies/protocol_L4f_polymarket_longshot_forward.md
L4F_EVERY, L4F_STAKE, L4F_LO, L4F_HI = 30 * 60, 0.05, 0.02, 0.10
GAMMA = "https://gamma-api.polymarket.com"


def l4f_pick(m: dict):
    """-> (side, price) to sell, or None. Uses the YES best bid/ask; selling NO is priced at 1 - YES ask."""
    bb, ba = m.get("bestBid"), m.get("bestAsk")
    try:
        outs = json.loads(m.get("outcomes") or "[]")
    except Exception:  # noqa: BLE001
        return None
    if bb is None or ba is None or len(outs) != 2 or not 0 < bb <= ba < 1:
        return None
    mid = (bb + ba) / 2
    if L4F_LO <= mid <= L4F_HI:
        return "yes", float(bb)
    if L4F_LO <= 1 - mid <= L4F_HI:
        return "no", round(1 - float(ba), 6)
    return None


def l4f_result(side: str, price: float, yes_won: bool) -> float:
    """Return on collateral (1 - price) for selling `side` at `price`."""
    lost = (side == "yes" and not yes_won) or (side == "no" and yes_won)
    return price / (1 - price) if lost else -1.0


def l4f_once(now=None):
    from urllib.parse import quote as _q
    now = now or time.time()
    st = _l1b_load("l4f")
    open_ids = {p["id"] for p in st["pending"]} | {c.get("id") for c in st["closed"]}
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
    cursor, pages = "", 0
    while pages < 5:
        d = get(f"{GAMMA}/markets/keyset?closed=false&active=true&limit=100&volume_num_min=50000"
                f"&end_date_min={iso(now + 12 * 3600)}&end_date_max={iso(now + 36 * 3600)}"
                + (f"&after_cursor={_q(cursor)}" if cursor else ""), 15)
        for m in d.get("markets") or []:
            pick = l4f_pick(m)
            if not pick or m["id"] in open_ids:
                continue
            side, price = pick
            stake = round(st["equity"] * L4F_STAKE, 4)
            row = {"id": m["id"], "question": (m.get("question") or "")[:120], "end": m.get("endDate"), "side": side,
                   "price": price, "stake": stake, "entry_ts": now, "volume": m.get("volumeNum")}
            st["pending"].append(row)
            open_ids.add(m["id"])
            append("ledger_l4f_events", row, now)
        cursor, pages = d.get("next_cursor") or "", pages + 1
        if not cursor:
            break
    keep = []
    for p in st["pending"]:
        try:
            m = get(f"{GAMMA}/markets/{p['id']}", 15)
            prices = json.loads(m.get("outcomePrices") or "[]")
            if m.get("closed") and sorted(prices) == ["0", "1"]:
                r = l4f_result(p["side"], p["price"], prices[0] == "1")
                st["equity"] = round(st["equity"] + p["stake"] * r, 4)
                row = {**p, "net": r, "ts": now, "yes_won": prices[0] == "1", "equity_after": st["equity"]}
                st["closed"].append(row)
                append("ledger_l4f_trades", row, now)
                continue
        except Exception as e:  # noqa: BLE001  retry next poll
            STATUS["listings"]["last_error"] = repr(e)[:200]
        keep.append(p)
    st["pending"] = keep
    _l1b_save(st, "l4f")
    return st

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
    return {**STATUS, "files": files, "dir": str(DIR), "l1b": ledger_view("l1b"), "l1d": ledger_view("l1d"), "l1f": ledger_view("l1f")}
