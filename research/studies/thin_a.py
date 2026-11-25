"""Batch A (small/secondary crypto exchanges): I/O helpers and studies. Pure logic lives in core/thin_a.py.
Runs on GitHub Actions only (never on the owner's computer)."""
import json
import time
from urllib.request import Request, urlopen


def http(url, timeout=25):
    """(status, parsed json or text head, seconds). Never raises: a block or error is a probe result."""
    t0 = time.time()
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 tradelab-research"}), timeout=timeout) as r:
            body = r.read()
            status = r.status
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        head = ""
        try:
            head = e.read()[:200].decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return code or type(e).__name__, head or str(e)[:160], round(time.time() - t0, 2)
    try:
        return status, json.loads(body), round(time.time() - t0, 2)
    except Exception:  # noqa: BLE001
        return status, body[:200].decode("utf-8", "replace"), round(time.time() - t0, 2)


def shape(x, depth=0):
    """Compact description of a JSON value: keys, list length, first element."""
    if isinstance(x, dict):
        return {k: (shape(v, depth + 1) if depth < 2 else type(v).__name__) for k, v in list(x.items())[:14]}
    if isinstance(x, list):
        return {"len": len(x), "first": shape(x[0], depth + 1) if x and depth < 3 else None, "last": x[-1] if x and len(str(x[-1])) < 200 else None}
    return x if not isinstance(x, str) else x[:120]


# ------------------------------------------------------------------ Thin A screen (RESULTS.md 'Thin A')
_LEVERAGED = ("3L", "3S", "5L", "5S", "UP", "DOWN", "BULL", "BEAR")


def parse_bars(venue, rows):
    """Exchange candle rows -> [(open_ts_s, open, high, low, close, quote_volume)] (unsorted). Column orders differ:
    KuCoin [t, o, c, h, l, vol, turnover] (t in s); MEXC [t_ms, o, h, l, c, vol, close_t, quote_vol]; Bitget
    [t_ms, o, h, l, c, base_vol, usdt_vol, quote_vol]; Gate [t, quote_vol, c, h, l, o, base_vol, closed]."""
    out = []
    for r in rows or []:
        try:
            if venue == "kucoin":
                out.append((int(r[0]), float(r[1]), float(r[3]), float(r[4]), float(r[2]), float(r[6])))
            elif venue == "mexc":
                out.append((int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])))
            elif venue == "bitget":
                out.append((int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6])))
            elif venue == "gate":
                out.append((int(r[0]), float(r[5]), float(r[3]), float(r[4]), float(r[2]), float(r[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


def clean_bars(bars, start, end, gaps=None):
    """Sort, drop duplicates and every bar outside [start, end): a venue that ignores the window and returns the latest
    bars must never be priced as history. Counted in gaps['out_of_window']."""
    keep = {}
    for b in bars:
        if start <= b[0] < end:
            keep[b[0]] = b
        elif gaps is not None:
            gaps["out_of_window"] = gaps.get("out_of_window", 0) + 1
    return [keep[k] for k in sorted(keep)]


def _get(url, tries=3):
    for k in range(tries):
        st, body, _ = http(url, timeout=25)
        if st == 200:
            return body
        if st in (400, 404):
            return None
        time.sleep(1.5 * (k + 1))
    return None


def fetch_bars(venue, base, interval, start, end, gaps):
    """Candles of BASE/USDT in [start, end) from `venue`; interval '1h' or '1d'. Windows are sent to every venue and the
    result is cleaned by clean_bars."""
    width = 3600 if interval == "1h" else 86400
    end = min(end, int(time.time()) // width * width)
    raw = []
    if venue == "kucoin":
        step = 1400 * width
        t = start
        while t < end:
            u = f"https://api.kucoin.com/api/v1/market/candles?symbol={base}-USDT&type={'1hour' if width == 3600 else '1day'}&startAt={t}&endAt={min(t + step, end)}"
            b = _get(u)
            raw += parse_bars("kucoin", (b or {}).get("data") if isinstance(b, dict) else None)
            t += step
            time.sleep(0.05)
    elif venue == "mexc":
        step = 480 * width
        t = start
        while t < end:
            u = f"https://api.mexc.com/api/v3/klines?symbol={base}USDT&interval={'60m' if width == 3600 else '1d'}&startTime={t * 1000}&endTime={min(t + step, end) * 1000 - 1}&limit=500"
            b = _get(u)
            raw += parse_bars("mexc", b if isinstance(b, list) else None)
            t += step
            time.sleep(0.05)
    elif venue == "bitget":
        e = end
        for _ in range(400):
            u = f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol={base}USDT&granularity={'1h' if width == 3600 else '1day'}&endTime={e * 1000}&limit=200"
            b = _get(u)
            page = parse_bars("bitget", (b or {}).get("data") if isinstance(b, dict) else None)
            raw += page
            if len(page) < 200:
                break
            oldest = min(x[0] for x in page)
            if oldest <= start:
                break
            e = oldest
            time.sleep(0.05)
    elif venue == "gate":
        step = 900 * width
        t = start
        while t < end:
            u = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={base}_USDT&interval={'1h' if width == 3600 else '1d'}&from={t}&to={min(t + step, end) - 1}"
            b = _get(u)
            raw += parse_bars("gate", b if isinstance(b, list) else None)
            t += step
            time.sleep(0.05)
    return clean_bars(raw, start, end, gaps)


def _rank_lists():
    """{venue: [(base, quote_volume_24h, extra)]} for today's active USDT pairs (survivors only)."""
    out = {}
    _, ku, _ = http("https://api.kucoin.com/api/v2/symbols")
    _, kt, _ = http("https://api.kucoin.com/api/v1/market/allTickers")
    kv = {x["symbol"]: float(x.get("volValue") or 0) for x in ((kt.get("data") or {}).get("ticker") or [])} if isinstance(kt, dict) else {}
    out["kucoin"] = [(x["baseCurrency"], kv.get(x["symbol"], 0.0), "") for x in (ku.get("data") or []) if x.get("quoteCurrency") == "USDT" and x.get("enableTrading")] if isinstance(ku, dict) else []
    _, me, _ = http("https://api.mexc.com/api/v3/exchangeInfo")
    _, mt, _ = http("https://api.mexc.com/api/v3/ticker/24hr")
    mv = {x["symbol"]: float(x.get("quoteVolume") or 0) for x in mt} if isinstance(mt, list) else {}
    out["mexc"] = [(x["baseAsset"], mv.get(x["symbol"], 0.0), "") for x in (me.get("symbols") or []) if x.get("quoteAsset") == "USDT" and x.get("isSpotTradingAllowed")] if isinstance(me, dict) else []
    _, bg, _ = http("https://api.bitget.com/api/v2/spot/public/symbols")
    _, bt, _ = http("https://api.bitget.com/api/v2/spot/market/tickers")
    bv = {x["symbol"]: float(x.get("usdtVolume") or 0) for x in (bt.get("data") or [])} if isinstance(bt, dict) else {}
    out["bitget"] = [(x["baseCoin"], bv.get(x["symbol"], 0.0), "") for x in (bg.get("data") or []) if x.get("quoteCoin") == "USDT" and x.get("status") == "online"] if isinstance(bg, dict) else []
    _, ga, _ = http("https://api.gateio.ws/api/v4/spot/currency_pairs")
    out["gate"] = [(x["base"], 0.0, str(x.get("buy_start") or 0)) for x in ga if x.get("quote") == "USDT" and x.get("trade_status") == "tradable"] if isinstance(ga, list) else []
    return out


def universe_symbols(lists):
    """['venue:BASE:flags[:buy_start]'] flags: L = listing rules A1-A3 (A4 for Gate), S = also shock rules A5/A6 (ranks
    51-350 by 24 h quote volume per venue). Leveraged tokens are dropped."""
    syms = []
    for venue, items in lists.items():
        items = [(b, v, x) for b, v, x in items if b and not b.endswith(_LEVERAGED)]
        ranked = sorted(items, key=lambda z: -z[1])
        shock = {b for b, _, _ in ranked[50:350]} if venue != "gate" else set()
        for b, _, extra in items:
            syms.append(f"{venue}:{b}:{'LS' if b in shock else 'L'}" + (f":{extra}" if extra else ""))
    return sorted(set(syms))


def symbols_thin_a():
    return universe_symbols(_rank_lists())


def rows_thin_a(symbols_slice):
    """One shard: rows for every pair in the slice. Returns {'rows': [...], 'gaps': {...}}."""
    from concurrent.futures import ThreadPoolExecutor
    from core import thin_a as ta
    gaps = {}
    now = int(time.time())

    def one(sym):
        parts = sym.split(":")
        venue, base, flags = parts[0], parts[1], parts[2]
        g = {}
        out = []
        daily = fetch_bars(venue, base, "1d", int(ta.SCAN_START), now, g)
        if not daily:
            g["no_daily"] = 1
            return out, g
        if venue == "gate":
            d0 = ta.listing_day(daily)
            if d0 is not None and len(parts) > 3 and abs(int(parts[3]) - d0) > 2 * 86400:
                g["buy_start_mismatch"] = 1
                return out, g
            rows, why = ta.listing_rows(venue, base, daily, None, gate=True)
            g["skip:" + why] = 1 if why and not rows else 0
            return rows, g
        d0 = ta.listing_day(daily)
        if d0 is not None and ta.EVENT_START <= d0 < ta.EVENT_END:
            h = fetch_bars(venue, base, "1h", int(d0), int(d0) + 42 * 86400, g)
            rows, why = ta.listing_rows(venue, base, daily, h)
            out += rows
            if why:
                g["skip:" + why] = 1
        if "S" in flags:
            hl = fetch_bars(venue, base, "1h", int(ta._t(2022, 12)), min(now, int(ta.EVENT_END)), g)
            out += ta.shock_rows(venue, base, hl)
        return out, g
    rows = []
    with ThreadPoolExecutor(12) as ex:
        for r, g in ex.map(one, symbols_slice):
            rows += r
            for k, v in g.items():
                gaps[k] = gaps.get(k, 0) + v
    return {"rows": rows, "gaps": gaps}


def summarize_thin_a(all_rows):
    from core import thin_a as ta
    return {"line": "thin_a", **ta.summarize(all_rows)}


def study_probe_thin_a(_symbols):
    """Which public endpoints of KuCoin, Gate.io, MEXC and Bitget answer from a GitHub runner, how far back their
    candles go, whether delisted pairs still return candles, and whether listing announcements are machine readable."""
    now = int(time.time())
    DAY = 86400
    out, urls = {}, {}
    # exchange info
    urls["kucoin_symbols"] = "https://api.kucoin.com/api/v2/symbols"
    urls["gate_pairs"] = "https://api.gateio.ws/api/v4/spot/currency_pairs"
    urls["mexc_info"] = "https://api.mexc.com/api/v3/exchangeInfo"
    urls["bitget_symbols"] = "https://api.bitget.com/api/v2/spot/public/symbols"
    # candles: BTC old (2022-01-01) and recent, hourly
    t22 = 1640995200
    urls["kucoin_1h_2022"] = f"https://api.kucoin.com/api/v1/market/candles?symbol=BTC-USDT&type=1hour&startAt={t22}&endAt={t22 + 3 * 3600}"
    urls["kucoin_1h_2025"] = f"https://api.kucoin.com/api/v1/market/candles?symbol=BTC-USDT&type=1hour&startAt=1735689600&endAt={1735689600 + 3 * 3600}"
    urls["gate_1h_2022"] = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=1h&from={t22}&to={t22 + 3 * 3600}"
    urls["gate_1h_2025"] = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=1h&from=1735689600&to={1735689600 + 3 * 3600}"
    urls["gate_1d_2022"] = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=1d&from={t22}&to={t22 + 3 * DAY}"
    urls["mexc_1h_2022"] = f"https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=60m&startTime={t22 * 1000}&endTime={(t22 + 4 * 3600) * 1000}&limit=5"
    urls["mexc_1h_2025"] = f"https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=60m&startTime=1735689600000&endTime={(1735689600 + 4 * 3600) * 1000}&limit=5"
    urls["mexc_1d_2022"] = f"https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime={t22 * 1000}&limit=3"
    urls["bitget_1h_2022"] = f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol=BTCUSDT&granularity=1h&endTime={(t22 + 4 * 3600) * 1000}&limit=5"
    urls["bitget_1h_2025"] = f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol=BTCUSDT&granularity=1h&endTime={(1735689600 + 4 * 3600) * 1000}&limit=5"
    urls["bitget_candles_recent"] = "https://api.bitget.com/api/v2/spot/market/candles?symbol=BTCUSDT&granularity=1min&limit=3"
    # minute candles a month back (for entry timing)
    m = now - 30 * DAY
    urls["kucoin_1m_30d"] = f"https://api.kucoin.com/api/v1/market/candles?symbol=BTC-USDT&type=1min&startAt={m}&endAt={m + 600}"
    urls["gate_1m_30d"] = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=1m&from={m}&to={m + 600}"
    urls["mexc_1m_30d"] = f"https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=1m&startTime={m * 1000}&limit=5"
    urls["bitget_1m_30d"] = f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol=BTCUSDT&granularity=1min&endTime={(m + 600) * 1000}&limit=5"
    # delisted-pair candidates (checked against the active symbol lists below)
    for k, sym in (("kucoin", "LUNA-USDT"), ("kucoin", "FTT-USDT"), ("kucoin", "UST-USDT"), ("kucoin", "BSW-USDT")):
        urls[f"{k}_dead_{sym}"] = f"https://api.kucoin.com/api/v1/market/candles?symbol={sym}&type=1day&startAt={t22}&endAt={t22 + 5 * DAY}"
    for sym in ("LUNA_USDT", "UST_USDT", "FTT_USDT", "BSW_USDT"):
        urls[f"gate_dead_{sym}"] = f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={sym}&interval=1d&from={t22}&to={t22 + 5 * DAY}"
    for sym in ("LUNAUSDT", "USTUSDT", "FTTUSDT", "BSWUSDT"):
        urls[f"mexc_dead_{sym}"] = f"https://api.mexc.com/api/v3/klines?symbol={sym}&interval=1d&startTime={t22 * 1000}&limit=5"
        urls[f"bitget_dead_{sym}"] = f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol={sym}&granularity=1day&endTime={(t22 + 5 * DAY) * 1000}&limit=5"
    # announcements
    urls["kucoin_ann"] = "https://api.kucoin.com/api/v3/announcements?annType=new-listings&lang=en_US&pageSize=5&currentPage=1"
    urls["bitget_ann"] = "https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=coin_listings&limit=5"
    urls["gate_ann"] = "https://www.gate.io/api/web/v1/announcement/list?type=newlisted&page=1&limit=5"
    urls["gate_ann2"] = "https://www.gate.com/announcements/newlisted"
    urls["mexc_ann"] = "https://www.mexc.com/api/operation/new_coin_calendar"
    urls["mexc_ann2"] = "https://www.mexc.com/api/operateactivity/activity/list"
    # books and trades for spread / depth (forward collector)
    urls["kucoin_book"] = "https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=BTC-USDT"
    urls["gate_book"] = "https://api.gateio.ws/api/v4/spot/order_book?currency_pair=BTC_USDT&limit=5"
    urls["mexc_book"] = "https://api.mexc.com/api/v3/depth?symbol=BTCUSDT&limit=5"
    urls["bitget_book"] = "https://api.bitget.com/api/v2/spot/market/orderbook?symbol=BTCUSDT&limit=5"
    urls["kucoin_tickers"] = "https://api.kucoin.com/api/v1/market/allTickers"
    urls["gate_tickers"] = "https://api.gateio.ws/api/v4/spot/tickers"
    urls["mexc_tickers"] = "https://api.mexc.com/api/v3/ticker/bookTicker"
    urls["bitget_tickers"] = "https://api.bitget.com/api/v2/spot/market/tickers"
    # Binance reference (data-api) and bulk archive
    urls["binance_vision_1h"] = "https://data-api.binance.vision/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=2"
    for name, u in urls.items():
        st, body, sec = http(u)
        rec = {"status": st, "sec": sec}
        if isinstance(body, (dict, list)):
            rec["shape"] = shape(body)
        else:
            rec["head"] = body
        out[name] = rec
        time.sleep(0.15)
    # extra: symbol-list sizes and listing-time fields
    lst = {}
    _, ku, _ = http(urls["kucoin_symbols"])
    kd = ku.get("data") if isinstance(ku, dict) else None
    lst["kucoin_usdt_pairs"] = len([x for x in kd or [] if x.get("quoteCurrency") == "USDT"])
    lst["kucoin_fields"] = sorted((kd or [{}])[0].keys()) if kd else None
    _, ga, _ = http(urls["gate_pairs"])
    lst["gate_usdt_pairs"] = len([x for x in ga or [] if x.get("quote") == "USDT"]) if isinstance(ga, list) else None
    lst["gate_fields"] = sorted(ga[0].keys()) if isinstance(ga, list) and ga else None
    lst["gate_buy_start_sample"] = [x.get("buy_start") for x in (ga or [])[:5]] if isinstance(ga, list) else None
    _, me, _ = http(urls["mexc_info"])
    syms = me.get("symbols") if isinstance(me, dict) else None
    lst["mexc_usdt_pairs"] = len([x for x in syms or [] if x.get("quoteAsset") == "USDT"])
    lst["mexc_fields"] = sorted(syms[0].keys()) if syms else None
    _, bg, _ = http(urls["bitget_symbols"])
    bd = bg.get("data") if isinstance(bg, dict) else None
    lst["bitget_usdt_pairs"] = len([x for x in bd or [] if x.get("quoteCoin") == "USDT"])
    lst["bitget_fields"] = sorted(bd[0].keys()) if bd else None
    lst["bitget_status_counts"] = {}
    for x in bd or []:
        lst["bitget_status_counts"][x.get("status")] = lst["bitget_status_counts"].get(x.get("status"), 0) + 1
    for name, active in (("kucoin", {x["symbol"] for x in kd or []}),):
        lst[f"{name}_dead_in_active_list"] = [s for s in ("LUNA-USDT", "FTT-USDT", "UST-USDT", "BSW-USDT") if s in active]
    return {"line": "probe_thin_a", "endpoints": out, "lists": lst}, []


STUDIES = {"probe_thin_a": study_probe_thin_a}
