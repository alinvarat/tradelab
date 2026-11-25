"""Fetching for the opt_vrp study (protocol_opt_vrp_20261125.md). Runs on GitHub Actions only (AGENTS.md rule 3).

One shard = one asset x calendar month ('BTC:2021-03'). Every decision lives in core/opt_vrp.py; this file only
downloads entry windows and hands them over. A failed fetch is a gap (the day is dropped and counted), never "no print".
"""
import json
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core import opt_vrp as ov
from research.studies import binance_vision as bv

HIST = "https://history.deribit.com/api/v2/public/"
WWW = "https://www.deribit.com/api/v2/public/"
UA = {"User-Agent": "tradelab-research"}
USDC_FROM = "2025-01-01"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def jget(url, tries=4, timeout=60, opener=None, sleep=time.sleep):
    """JSON `result` of a Deribit GET; retries on 429 and transient errors, raises after `tries`."""
    last = None
    for k in range(tries):
        try:
            sleep(0.12)
            if opener:
                body = opener(url)
            else:
                with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                    body = r.read()
            d = json.loads(body)
            if "result" not in d:
                raise ValueError(f"no result: {str(d)[:200]}")
            return d["result"]
        except Exception as e:  # noqa: BLE001
            last = e
            sleep(1.5 * (k + 1) * (3 if isinstance(e, HTTPError) and e.code == 429 else 1))
    raise RuntimeError(f"GET failed after {tries} tries: {url[:150]}: {last}")


def fetch_trades(currency, a_ms, b_ms, get=jget, max_pages=200):
    """All option trades with a_ms <= timestamp <= b_ms, de-duplicated on trade_id, sorted; None on failure (gap)."""
    seen, start = {}, a_ms
    try:
        for _ in range(max_pages):
            q = urlencode({"currency": currency, "kind": "option", "start_timestamp": start, "end_timestamp": b_ms,
                           "count": 1000, "include_old": "true", "sorting": "asc"})
            res = get(HIST + "get_last_trades_by_currency_and_time?" + q)
            trades = res.get("trades") or []
            new = 0
            for t in trades:
                if t["trade_id"] not in seen:
                    seen[t["trade_id"]] = t
                    new += 1
            if not res.get("has_more") or not trades:
                break
            last = max(t["timestamp"] for t in trades)
            start = last if new else last + 1
        else:
            return None
    except Exception as e:  # noqa: BLE001
        log("trades gap:", currency, a_ms, str(e)[:120])
        return None
    return sorted(seen.values(), key=lambda t: (t["timestamp"], str(t["trade_id"])))


def usdc_only(trades, asset):
    """The `USDC` currency tape holds every USDC-settled option (BTC_USDC, ETH_USDC, SOL_USDC ...); keep one asset."""
    if trades is None:
        return None
    return [t for t in trades if str(t.get("instrument_name", "")).startswith(asset + "_USDC-")]


def fetch_instruments(asset, lo_s, hi_s, get=jget):
    """{expiry seconds: [instrument dicts]} for expiries in [lo_s, hi_s]; raises on failure (no fallback grid)."""
    res = get(HIST + "get_instruments?" + urlencode({"currency": asset, "kind": "option", "expired": "true"}), tries=6, timeout=300)
    out = {}
    for i in res:
        e = i["expiration_timestamp"] // 1000
        if lo_s <= e <= hi_s and i.get("option_type") in ("put", "call"):
            out.setdefault(e, []).append({"name": i["instrument_name"], "strike": float(i["strike"]), "type": i["option_type"],
                                          "creation_ms": i["creation_timestamp"], "period": i.get("settlement_period")})
    return out


def fetch_delivery(asset, lo_date, get=jget):
    """{'YYYY-MM-DD': delivery price}: every page of 100 (order-agnostic), so old days are never skipped."""
    name, out, offset = f"{asset.lower()}_usd", {}, 0
    for _ in range(100):
        res = get(WWW + "get_delivery_prices?" + urlencode({"index_name": name, "offset": offset, "count": 100}))
        data = res.get("data") or []
        for r in data:
            out[r["date"]] = float(r["delivery_price"])
        offset += 100
        if not data or offset >= res.get("records_total", 0):
            return out
    raise RuntimeError("delivery paging did not finish")


def fetch_dvol(asset, start_s, end_s, get=jget):
    """{hour bar stamp (seconds): close} for hourly DVOL over [start_s, end_s], 20-day windows. Deribit's `continuation`
    is the end_timestamp for the next (older) page, so it moves the END back; it never moves the start."""
    out, a = {}, start_s
    while a < end_s:
        b = min(a + 20 * 86400, end_s)
        cur_end = b
        for _ in range(20):
            res = get(WWW + "get_volatility_index_data?" + urlencode({"currency": asset, "start_timestamp": a * 1000,
                                                                        "end_timestamp": cur_end * 1000, "resolution": 3600}))
            for row in res.get("data") or []:
                out[int(row[0]) // 1000] = float(row[4])
            cont = res.get("continuation")
            nxt = int(cont) // 1000 if cont else None
            if nxt is None or not a <= nxt < cur_end:
                break
            cur_end = nxt
        a = b
    return out


def fetch_hours(asset, start_s, end_s):
    rows, failed = bv.klines(asset + "USDT", start_s, end_s, "1h", "spot", "monthly")
    if failed:
        raise RuntimeError(f"binance 1h klines failed: {failed}")
    return {int(r[0]): (r[1], r[2], r[3], r[4]) for r in rows}


def shard_unit(asset, month, get=jget, hours_fn=fetch_hours):
    days = ov.month_days(month)
    if not days:
        return [], {}
    t0, t1 = ov.day_ts(days[0]), ov.day_ts(days[-1]) + 2 * 86400
    inst = fetch_instruments(asset, t0, t1, get)
    delivery = fetch_delivery(asset, days[0], get)
    dvol = fetch_dvol(asset, t0 - 86400, t1, get)
    hours = hours_fn(asset, t0 - 9 * 86400, t1 + 86400)
    rows, gaps = [], {"trades": 0, "usdc_trades": 0, "no_dvol_days": 0, "no_expiry_days": 0}
    for date in days:
        e_am, _ = ov.entry_times(date, "am")
        e_pm, _ = ov.entry_times(date, "pm")
        g = []
        am = fetch_trades(asset, (e_am - 3600) * 1000, (e_am + 3600) * 1000, get)
        pm = fetch_trades(asset, (e_pm - 3600) * 1000, (e_pm + 3600) * 1000, get)
        if am is None or pm is None:
            g.append("trades")
            gaps["trades"] += 1
        u_am = u_pm = None
        if date >= USDC_FROM:
            u_am = usdc_only(fetch_trades("USDC", e_am * 1000, (e_am + 3600) * 1000, get), asset)
            u_pm = usdc_only(fetch_trades("USDC", e_pm * 1000, (e_pm + 3600) * 1000, get), asset)
            if u_am is None or u_pm is None:        # USDC is a cross-check only: a failure drops its fields, not the day
                gaps["usdc_trades"] += 1
                u_am = u_pm = None
        instruments = inst.get(ov.expiry_ts(date), [])
        if not instruments:
            gaps["no_expiry_days"] += 1
        r = ov.build_day_rows(asset, date, instruments, am or [], pm or [], u_am, u_pm, dvol, hours,
                              delivery.get(ov.add_days(date, 1)), g)
        if r[0]["dvol_am"] is None:
            gaps["no_dvol_days"] += 1
        rows += r
    log(f"{asset}:{month} rows={len(rows)} gaps={gaps}")
    return rows, gaps


def rows_for(symbols_slice):
    rows, gaps = [], {}
    for tok in symbols_slice:
        asset, month = tok.split(":")
        r, g = shard_unit(asset, month)
        rows += r
        for k, v in g.items():
            gaps[k] = gaps.get(k, 0) + v
    return {"rows": rows, "gaps": gaps}
