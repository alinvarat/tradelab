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
