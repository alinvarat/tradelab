"""Batch B (low-liquidity prediction markets): I/O helpers and studies. Pure logic lives in core/thin_b.py.
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


def study_probe_thin_b(_symbols):
    """Which prediction-market endpoints answer from a GitHub runner and what they return: Polymarket gamma / clob /
    data-api (trades), Kalshi public v2, Manifold v0."""
    now = int(time.time())
    urls = {}
    urls["pm_markets_closed"] = "https://gamma-api.polymarket.com/markets?closed=true&limit=3&order=volumeNum&ascending=false"
    urls["pm_markets_keyset"] = "https://gamma-api.polymarket.com/markets/keyset?closed=true&limit=3&volume_num_min=1000&volume_num_max=50000"
    urls["pm_events_negrisk"] = "https://gamma-api.polymarket.com/events?closed=true&limit=3&order=volume&ascending=false"
    urls["pm_events_active"] = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=3"
    urls["pm_prices_hourly"] = "https://clob.polymarket.com/prices-history?market=21742633143463906290569050155826241533067272736897614950488156847949938836455&interval=max&fidelity=60"
    urls["pm_book"] = "https://clob.polymarket.com/book?token_id=21742633143463906290569050155826241533067272736897614950488156847949938836455"
    urls["pm_data_trades"] = "https://data-api.polymarket.com/trades?limit=5"
    urls["pm_data_trades_market"] = "https://data-api.polymarket.com/trades?limit=5&market=0xdd22472e552920b8438158ea7238bfadfa4f736aa4cee91a6b86c39ead110917"
    urls["kalshi_markets_settled"] = "https://api.elections.kalshi.com/trade-api/v2/markets?status=settled&limit=3"
    urls["kalshi_markets_open"] = "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit=3"
    urls["kalshi_trades"] = "https://api.elections.kalshi.com/trade-api/v2/markets/trades?limit=5"
    urls["kalshi_events"] = "https://api.elections.kalshi.com/trade-api/v2/events?status=settled&limit=3&with_nested_markets=true"
    urls["manifold_markets"] = "https://api.manifold.markets/v0/markets?limit=3"
    urls["manifold_bets"] = "https://api.manifold.markets/v0/bets?limit=3"
    urls["manifold_search"] = "https://api.manifold.markets/v0/search-markets?term=&filter=resolved&sort=liquidity&limit=3"
    for name, u in list(urls.items()):
        pass
    out = {}
    for name, u in urls.items():
        st_, body, sec = http(u)
        rec = {"status": st_, "sec": sec}
        if isinstance(body, (dict, list)):
            rec["shape"] = shape(body)
        else:
            rec["head"] = body
        out[name] = rec
        time.sleep(0.2)
    return {"line": "probe_thin_b", "endpoints": out}, []


STUDIES = {"probe_thin_b": study_probe_thin_b}


def study_probe_thin_b2(_symbols):
    """Second probe: Polymarket v2 trades (recorded fills), gamma event/market fields, hourly price history of a thin
    resolved market, Kalshi trades/candlesticks/historical cutoff, Manifold bets."""
    out = {}

    def rec(name, url, timeout=30):
        st_, body, sec = http(url, timeout)
        out[name] = {"status": st_, "sec": sec, "shape": shape(body) if isinstance(body, (dict, list)) else body}
        return body
    oa = rec("pm_v2_openapi", "https://data-api.polymarket.com/v2/openapi.json")
    if isinstance(oa, dict):
        tr = (oa.get("paths") or {}).get("/v2/trades") or {}
        out["pm_v2_trades_params"] = [(p.get("name"), (p.get("schema") or {}).get("type"), (p.get("schema") or {}).get("maximum")) for p in (tr.get("get") or {}).get("parameters", [])]
        out["pm_v2_paths"] = sorted((oa.get("paths") or {}))[:40]
    ks = http("https://gamma-api.polymarket.com/markets/keyset?closed=true&limit=5&volume_num_min=5000&volume_num_max=40000&end_date_min=2026-06-01T00:00:00Z&end_date_max=2026-10-01T00:00:00Z")[1]
    ms = (ks or {}).get("markets") or [] if isinstance(ks, dict) else []
    if ms:
        m = ms[0]
        out["gamma_market_keys"] = sorted(m.keys())
        out["gamma_market_sample"] = {k: m.get(k) for k in ("id", "question", "conditionId", "volumeNum", "liquidityNum", "negRisk", "closedTime", "endDate", "umaResolutionStatus", "enableOrderBook", "outcomes", "outcomePrices", "events") if k in m}
        toks = json.loads(m.get("clobTokenIds") or "[]")
        if toks:
            rec("pm_prices_60", f"https://clob.polymarket.com/prices-history?market={toks[0]}&interval=max&fidelity=60")
            rec("pm_prices_1", f"https://clob.polymarket.com/prices-history?market={toks[0]}&interval=max&fidelity=1")
        rec("pm_v2_trades_cond", f"https://data-api.polymarket.com/v2/trades?condition={m['conditionId']}&limit=20")
        rec("pm_v2_trades_cond_b", f"https://data-api.polymarket.com/v2/trades?market={m['conditionId']}&limit=20")
    ev = http("https://gamma-api.polymarket.com/events?closed=true&limit=5&order=volume&ascending=false&end_date_min=2026-01-01T00:00:00Z")[1]
    if isinstance(ev, list) and ev:
        e0 = ev[0]
        out["gamma_event_keys"] = sorted(e0.keys())
        out["gamma_event_sample"] = {k: e0.get(k) for k in ("id", "title", "negRisk", "enableNegRisk", "closed", "volume", "liquidity", "openInterest") if k in e0}
        out["gamma_event_markets_n"] = len(e0.get("markets") or [])
    rec("kalshi_market_one", "https://api.elections.kalshi.com/trade-api/v2/markets?status=settled&limit=1")
    km = http("https://api.elections.kalshi.com/trade-api/v2/markets?status=settled&limit=200&min_close_ts=1780000000")[1]
    kms = km.get("markets") if isinstance(km, dict) else []
    if kms:
        out["kalshi_market_keys"] = sorted(kms[0].keys())
        out["kalshi_market_sample"] = {k: kms[0].get(k) for k in kms[0] if any(w in k for w in ("ticker", "volume", "liquidity", "result", "close", "settle", "price", "interest"))}
        t = kms[0]["ticker"]
        rec("kalshi_trades_ticker", f"https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker={t}&limit=50")
        et = kms[0].get("event_ticker")
        st_ = (et or "").split("-")[0]
        rec("kalshi_candles", f"https://api.elections.kalshi.com/trade-api/v2/series/{st_}/markets/{t}/candlesticks?start_ts=1780000000&end_ts=1795000000&period_interval=60")
        rec("kalshi_event_one", f"https://api.elections.kalshi.com/trade-api/v2/events/{et}")
    rec("kalshi_hist_cutoff", "https://api.elections.kalshi.com/trade-api/v2/historical/cutoff")
    rec("kalshi_hist_markets", "https://api.elections.kalshi.com/trade-api/v2/historical/markets?limit=2")
    rec("manifold_resolved", "https://api.manifold.markets/v0/search-markets?term=&filter=resolved&sort=most-popular&limit=2&contractType=BINARY")
    return {"line": "probe_thin_b2", **out}, []


STUDIES["probe_thin_b2"] = study_probe_thin_b2
