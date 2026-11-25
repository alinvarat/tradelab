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
