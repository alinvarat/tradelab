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


def study_probe_thin_b3(_symbols):
    """Third probe: price history with start/end windows, v2 prices-history, trade counts of thin resolved markets,
    Kalshi historical markets/trades/candlesticks, mutually exclusive Kalshi events, Manifold bets of a resolved market."""
    out = {}

    def rec(name, url, timeout=30):
        st_, body, sec = http(url, timeout)
        out[name] = {"status": st_, "sec": sec, "shape": shape(body) if isinstance(body, (dict, list)) else body}
        return body
    oa = http("https://data-api.polymarket.com/v2/openapi.json")[1]
    if isinstance(oa, dict):
        for path in ("/v2/prices-history", "/v2/resolutions", "/v2/tokens"):
            g = ((oa.get("paths") or {}).get(path) or {}).get("get") or {}
            out["oa" + path] = [(p.get("name"), (p.get("schema") or {}).get("type")) for p in g.get("parameters", [])]
    ks = http("https://gamma-api.polymarket.com/markets/keyset?closed=true&limit=20&volume_num_min=5000&volume_num_max=40000&end_date_min=2025-09-01T00:00:00Z&end_date_max=2026-02-01T00:00:00Z")[1]
    ms = ks.get("markets") if isinstance(ks, dict) else []
    probes = []
    for m in ms[:6]:
        toks = json.loads(m.get("clobTokenIds") or "[]")
        if not toks or not m.get("closedTime"):
            continue
        from datetime import datetime
        ct = int(datetime.fromisoformat(m["closedTime"].replace("+00", "+00:00")).timestamp())
        r = {"q": m["question"][:60], "closed": m["closedTime"], "vol": m.get("volumeNum")}
        for fid, extra in ((1440, "&interval=max"), (60, "&interval=max"), (60, f"&startTs={ct - 14 * 86400}&endTs={ct}"), (5, f"&startTs={ct - 2 * 86400}&endTs={ct}")):
            h = http(f"https://clob.polymarket.com/prices-history?market={toks[0]}&fidelity={fid}{extra}")[1]
            r[f"hist_{fid}_{'win' if 'startTs' in extra else 'max'}"] = len((h or {}).get("history") or []) if isinstance(h, dict) else str(h)[:80]
        n, cur = 0, ""
        for _ in range(12):
            t = http(f"https://data-api.polymarket.com/v2/trades?condition={m['conditionId']}&limit=1000" + (f"&cursor={cur}" if cur else ""))[1]
            if not isinstance(t, dict):
                r["trades_err"] = str(t)[:100]
                break
            n += len(t.get("data") or [])
            cur = (t.get("pagination") or {}).get("next_cursor") or ""
            if not cur or not (t.get("pagination") or {}).get("has_more"):
                break
        r["trades_total"] = n
        if n:
            r["trade_sample"] = (t.get("data") or [None])[0]
        probes.append(r)
        time.sleep(0.2)
    out["pm_thin_markets"] = probes
    rec("kalshi_hist_markets_big", "https://api.elections.kalshi.com/trade-api/v2/historical/markets?limit=1000")
    hm = http("https://api.elections.kalshi.com/trade-api/v2/historical/markets?limit=1000")[1]
    nonmve = [x for x in (hm.get("markets") if isinstance(hm, dict) else []) if not x.get("mve_collection_ticker") and float(x.get("volume_fp") or 0) > 100]
    out["kalshi_hist_nonmve_with_volume"] = len(nonmve)
    if nonmve:
        x = nonmve[0]
        out["kalshi_hist_sample"] = {k: x.get(k) for k in ("ticker", "event_ticker", "volume_fp", "open_interest_fp", "result", "close_time", "settlement_ts", "yes_bid_dollars", "yes_ask_dollars", "last_price_dollars")}
        rec("kalshi_hist_trades", f"https://api.elections.kalshi.com/trade-api/v2/historical/trades?ticker={x['ticker']}&limit=20")
        rec("kalshi_hist_candles", f"https://api.elections.kalshi.com/trade-api/v2/historical/markets/{x['ticker']}/candlesticks?start_ts=1700000000&end_ts=1790000000&period_interval=60")
        rec("kalshi_events_one", f"https://api.elections.kalshi.com/trade-api/v2/events/{x['event_ticker']}?with_nested_markets=true")
    rec("kalshi_events_settled_nested", "https://api.elections.kalshi.com/trade-api/v2/events?status=settled&limit=200&with_nested_markets=true&min_close_ts=1788000000")
    ev = http("https://api.elections.kalshi.com/trade-api/v2/events?status=settled&limit=200&with_nested_markets=true&min_close_ts=1788000000")[1]
    evs = ev.get("events") if isinstance(ev, dict) else []
    out["kalshi_settled_events"] = len(evs)
    out["kalshi_mutex_events"] = sum(1 for e in evs if e.get("mutually_exclusive"))
    out["kalshi_series_sample"] = sorted({e.get("series_ticker") for e in evs})[:25]
    rm = http("https://api.manifold.markets/v0/search-markets?term=&filter=resolved&sort=most-popular&limit=1&contractType=BINARY")[1]
    if isinstance(rm, list) and rm:
        rec("manifold_bets_market", f"https://api.manifold.markets/v0/bets?contractId={rm[0]['id']}&limit=5")
    return {"line": "probe_thin_b3", **out}, []


STUDIES["probe_thin_b3"] = study_probe_thin_b3


def study_probe_thin_b4(_symbols):
    """Fourth probe: Kalshi usable markets only (settled, non-combo, mutually exclusive events with volume)."""
    out = {}
    base = "https://api.elections.kalshi.com/trade-api/v2"
    ev = http(f"{base}/events?status=settled&limit=200&with_nested_markets=true&min_close_ts=1788000000")[1]
    evs = [e for e in (ev.get("events") if isinstance(ev, dict) else []) if e.get("mutually_exclusive")]
    cand = []
    for e in evs:
        mk = [m for m in e.get("markets") or [] if float(m.get("volume_fp") or 0) > 0]
        if len(mk) >= 3:
            cand.append((e, mk))
    out["mutex_with_volume"] = len(cand)
    out["mutex_examples"] = [{"event": e["event_ticker"], "title": e.get("title"), "n_markets": len(e.get("markets") or []),
                              "vols": [m.get("volume_fp") for m in mk][:6], "results": [m.get("result") for m in mk][:6]} for e, mk in cand[:5]]
    if cand:
        e, mk = cand[0]
        m = mk[0]
        out["market_fields"] = {k: m.get(k) for k in ("ticker", "volume_fp", "open_interest_fp", "result", "close_time", "settlement_ts", "yes_bid_dollars", "yes_ask_dollars", "last_price_dollars", "open_time")}
        ser = e["series_ticker"]
        for nm, u in (("trades", f"{base}/markets/trades?ticker={m['ticker']}&limit=100"),
                      ("candles_live", f"{base}/series/{ser}/markets/{m['ticker']}/candlesticks?start_ts={int(time.time()) - 60 * 86400}&end_ts={int(time.time())}&period_interval=60"),
                      ("hist_trades", f"{base}/historical/trades?ticker={m['ticker']}&limit=100"),
                      ("hist_market", f"{base}/historical/markets/{m['ticker']}")):
            st_, body, sec = http(u)
            out[nm] = {"status": st_, "shape": shape(body) if isinstance(body, (dict, list)) else body}
            if isinstance(body, dict) and body.get("candlesticks"):
                out[nm]["candle0"] = body["candlesticks"][0]
            if isinstance(body, dict) and body.get("trades"):
                out[nm]["trade0"] = body["trades"][0]
    # older settled events through the historical cutoff
    he = http(f"{base}/historical/markets?limit=1000&event_ticker=")[1]
    out["hist_markets_probe"] = shape(he) if isinstance(he, (dict, list)) else he
    old = http(f"{base}/events?status=settled&limit=50&with_nested_markets=true&max_close_ts=1780000000")[1]
    oe = old.get("events") if isinstance(old, dict) else []
    out["settled_events_before_cutoff_n"] = len(oe)
    out["settled_before_cutoff_sample"] = [(e.get("event_ticker"), e.get("mutually_exclusive")) for e in oe[:8]]
    return {"line": "probe_thin_b4", **out}, []


STUDIES["probe_thin_b4"] = study_probe_thin_b4
