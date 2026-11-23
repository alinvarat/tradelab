"""Market data: Yahoo Finance chart API (stocks, ETFs, indices, forex, futures, crypto) and Binance REST
(live crypto bid/ask). Standard library only. Every network call goes through a TTL cache."""
import json
import threading
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
_cache: dict = {}
_lock = threading.Lock()


def http_get(url: str, ttl: float = 60, timeout: float = 30) -> bytes:
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < ttl:
            return hit[1]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    with _lock:
        _cache[url] = (now, body)
        if len(_cache) > 2000:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:500]:
                _cache.pop(k, None)
    return body


def get_json(url: str, ttl: float = 60):
    return json.loads(http_get(url, ttl))


# Yahoo interval for each UI range.
RANGES = {
    "1d": ("1d", "5m"), "5d": ("5d", "15m"), "1mo": ("1mo", "1h"), "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"), "1y": ("1y", "1d"), "2y": ("2y", "1d"), "5y": ("5y", "1wk"), "max": ("max", "1mo"),
}


def is_crypto(symbol: str) -> bool:
    return symbol.endswith("-USD") and "=" not in symbol


def binance_symbol(symbol: str) -> str | None:
    return symbol[:-4].replace("-", "") + "USDT" if is_crypto(symbol) else None


def chart(symbol: str, rng: str = "1y", interval: str | None = None) -> dict:
    """OHLCV bars plus meta. Bars with missing values are dropped."""
    r, iv = RANGES.get(rng, (rng, interval or "1d"))
    iv = interval or iv
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?range={r}&interval={iv}&includePrePost=false")
    ttl = 30 if iv in ("1m", "5m", "15m") else 300
    d = get_json(url, ttl)["chart"]
    if d.get("error") or not d.get("result"):
        raise ValueError(f"no data for {symbol}")
    res = d["result"][0]
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(res.get("timestamp") or []):
        o, h, l, c, v = (q[k][i] for k in ("open", "high", "low", "close", "volume"))
        if None in (o, h, l, c):
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    return {"meta": res["meta"], "bars": bars, "interval": iv}


def thb_at_open(equity_usd: float, capital_usd: float, capital_thb: float = 5000.0) -> float:
    """THB value of an account at the exchange rate it was opened with, so THB profit/loss equals the USD return
    (a baht/dollar move on play money is not trading profit)."""
    return equity_usd * capital_thb / capital_usd if capital_usd else 0.0


def quote_fast(symbol: str, ttl: float = 1.5) -> dict:
    """Same fields as quote() but from a one-bar chart request with a ~1 s cache, so positions and shock candidates can be
    polled every few seconds (the Yahoo meta price is within seconds of the exchange for US stocks)."""
    if is_crypto(symbol):
        return quote(symbol)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=1d&interval=1d"
           "&includePrePost=false")
    d = get_json(url, ttl)["chart"]
    if d.get("error") or not d.get("result"):
        raise ValueError(f"no data for {symbol}")
    return _quote_from_meta(symbol, d["result"][0]["meta"])


def quote(symbol: str) -> dict:
    """Latest price. Crypto uses Binance live bid/ask; everything else the Yahoo chart meta (about 1-6 s old for US stocks)."""
    m = chart(symbol, "5d", "15m")["meta"] if not is_crypto(symbol) else None
    if is_crypto(symbol):
        b = binance_symbol(symbol)
        try:
            bt = get_json(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={b}", ttl=3)
            st = get_json(f"https://api.binance.com/api/v3/ticker/24hr?symbol={b}", ttl=30)
            bid, ask = float(bt["bidPrice"]), float(bt["askPrice"])
            return {"symbol": symbol, "price": (bid + ask) / 2, "bid": bid, "ask": ask,
                    "prev_close": float(st["prevClosePrice"]), "change_pct": float(st["priceChangePercent"]),
                    "high": float(st["highPrice"]), "low": float(st["lowPrice"]), "volume": float(st["volume"]),
                    "currency": "USD", "type": "CRYPTOCURRENCY", "name": symbol, "ts": time.time(),
                    "source": "Binance (live, USDT)", "open": True}
        except Exception:
            m = chart(symbol, "5d", "15m")["meta"]
    return _quote_from_meta(symbol, m)


def _quote_from_meta(symbol, m):
    px = m.get("regularMarketPrice")
    prev = m.get("previousClose") or m.get("chartPreviousClose")
    ts = m.get("regularMarketTime") or 0
    typ = m.get("instrumentType", "")
    spread = SPREAD.get(typ, 0.0005)
    reg = (m.get("currentTradingPeriod") or {}).get("regular") or {}
    now = time.time()
    open_ = typ == "CRYPTOCURRENCY" or (reg.get("start", 0) <= now <= reg.get("end", 0) and now - ts < 1800)
    if typ == "CURRENCY":
        open_ = now - ts < 1800
    return {"symbol": symbol, "price": px, "bid": px * (1 - spread / 2), "ask": px * (1 + spread / 2),
            "prev_close": prev, "change_pct": (px / prev - 1) * 100 if prev else None,
            "high": m.get("regularMarketDayHigh"), "low": m.get("regularMarketDayLow"),
            "volume": m.get("regularMarketVolume"), "currency": m.get("currency", "USD"), "type": typ,
            "name": m.get("shortName") or m.get("longName") or symbol, "ts": ts,
            "w52_high": m.get("fiftyTwoWeekHigh"), "w52_low": m.get("fiftyTwoWeekLow"),
            "exchange": m.get("fullExchangeName"), "source": "Yahoo (US quotes were measured at about 1-6 s old)", "open": open_}


# Simulated full spread when the source gives no bid/ask (fraction of price).
SPREAD = {"EQUITY": 0.0004, "ETF": 0.0003, "INDEX": 0.0004, "FUTURE": 0.0003, "CURRENCY": 0.0001,
          "CRYPTOCURRENCY": 0.0005, "MUTUALFUND": 0.0}


def fx_to_usd(currency: str) -> float:
    """Units of USD per one unit of `currency`. GBp/ILA (pence/agorot) are scaled by 1/100."""
    if not currency or currency.upper() == "USD":
        return 1.0
    scale = 1.0
    if currency in ("GBp", "ILA", "ZAc"):
        currency, scale = {"GBp": "GBP", "ILA": "ILS", "ZAc": "ZAR"}[currency], 0.01
    m = chart(f"{currency.upper()}USD=X", "5d", "1d")["meta"]
    return m["regularMarketPrice"] * scale


def search(q: str) -> list:
    d = get_json("https://query1.finance.yahoo.com/v1/finance/search?"
                 + urllib.parse.urlencode({"q": q, "quotesCount": 10, "newsCount": 0}), ttl=600)
    out = []
    for x in d.get("quotes", []):
        sym = x.get("symbol", "")
        if not sym or sym.endswith(".BK") or x.get("exchange") in ("SET",):
            continue
        out.append({"symbol": sym, "name": x.get("longname") or x.get("shortname") or sym,
                    "type": x.get("typeDisp") or x.get("quoteType"), "exchange": x.get("exchDisp"),
                    "sector": x.get("sectorDisp"), "industry": x.get("industryDisp")})
    return out


def profile(symbol: str) -> dict:
    """Sector/industry from the search endpoint (quoteSummary needs a crumb and returns 401)."""
    for x in search(symbol):
        if x["symbol"] == symbol:
            return x
    return {}


def fear_greed() -> dict | None:
    try:
        d = get_json("https://api.alternative.me/fng/?limit=30", ttl=1800)["data"]
        return {"value": int(d[0]["value"]), "label": d[0]["value_classification"],
                "history": [{"t": int(x["timestamp"]), "v": int(x["value"])} for x in reversed(d)],
                "source": "alternative.me (crypto)"}
    except Exception:
        return None
