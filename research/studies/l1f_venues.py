"""L1f short venues: which exchange offered a shortable instrument for each Binance delist-notice coin at notice time, and what the
short earns there. Spec: research/studies/protocol_l1f_venues_20261125.md. GitHub Actions only (workflow l1f_venues.yml).

    python research/studies/l1f_venues.py <out_dir> probe  <events.json>     existence only: bar counts per venue, NO prices stored
    python research/studies/l1f_venues.py <out_dir> margin                   Binance margin evidence (announcements + public endpoints)
    python research/studies/l1f_venues.py <out_dir> price  <events.json> <probe.json>   price the short per venue (locked protocol)
"""
import gzip
import io
import json
import os
import random
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import forced_flow as ff   # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
HOLD = 14400
DELAY = 60
VENUES = ("binance_um", "okx", "bybit", "bitget", "gate", "mexc", "kucoin_fut", "hyperliquid")   # fixed priority (protocol)
STABLES = {"USDP", "IDRT", "VAI", "BUSD", "TUSD", "USDC", "FDUSD", "UST", "USTC"}
ERR = {}


def http(url, data=None, timeout=30, tries=3, method=None, head=False):
    """-> (status, text|None). status is the HTTP code, or 0 on a network failure."""
    last = 0
    for k in range(tries):
        try:
            req = Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})},
                          method="HEAD" if head else method)
            with urlopen(req, timeout=timeout) as r:
                b = r.read()
            if b[:2] == b"\x1f\x8b" and not head:
                b = gzip.decompress(b)
            return r.status, b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = getattr(e, "code", 0) or 0
            ERR[f"{last}{type(e).__name__}"] = ERR.get(f"{last}{type(e).__name__}", 0) + 1
            if last in (400, 403, 404, 451):
                return last, None
            time.sleep(1.5 * (k + 1))
    return last, None


def jget(url, **kw):
    st, t = http(url, **kw)
    if t is None:
        return st, None
    try:
        return st, json.loads(t)
    except ValueError:
        return st, None


# ---------------------------------------------------------------- 1-minute bars per venue: {open ts s: (o, h, l, c)} | {} none | None failed
def bars_binance_um(sym, t0, t1):
    for cand in (sym, "1000" + sym, "1000000" + sym):
        out = {}
        for y, m in bv.months(t0, t1):
            d = bv.fetch("futures/um", "monthly", "klines", cand + "USDT", (y, m), "1m", bv.parse_kline)
            if d is None:
                return None
            out.update({r[0]: (r[1], r[2], r[3], r[4]) for r in d if t0 <= r[0] < t1})
        if out:
            return out
    return {}


def bars_spot(sym, t0, t1, quote="USDT"):
    out = {}
    for y, m in bv.months(t0, t1):
        d = bv.fetch("spot", "monthly", "klines", sym + quote, (y, m), "1m", bv.parse_kline)
        if d is None:
            return None
        out.update({r[0]: (r[1], r[2], r[3], r[4]) for r in d if t0 <= r[0] < t1})
    return out


def bars_okx(sym, t0, t1):
    out, after = {}, int(t1 * 1000)
    for _ in range(12):
        time.sleep(0.12)
        st, d = jget(f"https://www.okx.com/api/v5/market/history-candles?instId={sym}-USDT-SWAP&bar=1m&after={after}&limit=100")
        if d is None:
            return None
        if d.get("code") != "0":
            return {}
        rows = d.get("data") or []
        if not rows:
            break
        for k in rows:
            out[int(k[0]) // 1000] = (float(k[1]), float(k[2]), float(k[3]), float(k[4]))
        oldest = min(int(k[0]) for k in rows)
        if oldest / 1000 <= t0:
            break
        after = oldest
    return {t: v for t, v in out.items() if t0 <= t < t1}


def bars_gate(sym, t0, t1):
    st, d = jget(f"https://api.gateio.ws/api/v4/futures/usdt/candlesticks?contract={sym}_USDT&interval=1m&from={int(t0)}&to={int(t1)}")
    if d is None:
        return {} if st in (400, 404) else None
    if not isinstance(d, list):
        return {}
    return {int(k["t"]): (float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])) for k in d if t0 <= int(k["t"]) < t1}


def bars_mexc(sym, t0, t1):
    st, d = jget(f"https://contract.mexc.com/api/v1/contract/kline/{sym}_USDT?interval=Min1&start={int(t0)}&end={int(t1)}")
    if d is None:
        return {} if st in (400, 404) else None
    x = d.get("data") if isinstance(d, dict) else None
    if not x or not x.get("time"):
        return {}
    return {int(t): (float(o), float(h), float(l), float(c)) for t, o, h, l, c in zip(x["time"], x["open"], x["high"], x["low"], x["close"])
            if t0 <= int(t) < t1}


def bars_bitget(sym, t0, t1):
    out, end = {}, int(t1 * 1000)
    for _ in range(6):
        st, d = jget(f"https://api.bitget.com/api/v2/mix/market/history-candles?symbol={sym}USDT&productType=usdt-futures"
                     f"&granularity=1m&startTime={int(t0 * 1000)}&endTime={end}&limit=200")
        if d is None:
            return {} if st in (400, 404) else None
        rows = d.get("data") or []
        if not rows:
            break
        for k in rows:
            out[int(k[0]) // 1000] = (float(k[1]), float(k[2]), float(k[3]), float(k[4]))
        oldest = min(int(k[0]) for k in rows)
        if oldest / 1000 <= t0:
            break
        end = oldest - 1
        time.sleep(0.1)
    return {t: v for t, v in out.items() if t0 <= t < t1}


def bars_kucoin_fut(sym, t0, t1):
    out = {}
    t = int(t0)
    while t < t1:
        te = min(int(t1), t + 199 * 60)
        st, d = jget(f"https://api-futures.kucoin.com/api/v1/kline/query?symbol={sym}USDTM&granularity=1&from={t * 1000}&to={te * 1000}")
        if d is None:
            return {} if st in (400, 404) else None
        if d.get("code") != "200000":
            return {}
        for k in d.get("data") or []:
            out[int(k[0]) // 1000] = (float(k[1]), float(k[2]), float(k[3]), float(k[4]))
        t = te
        time.sleep(0.1)
    return {t_: v for t_, v in out.items() if t0 <= t_ < t1}


def bars_hyperliquid(sym, t0, t1):
    """Hyperliquid keeps only the newest 5000 candles per interval: only recent events reach (reported as a reach limit)."""
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": sym, "interval": "1m", "startTime": int(t0 * 1000), "endTime": int(t1 * 1000)}})
    st, d = jget("https://api.hyperliquid.xyz/info", data=body.encode(), method="POST")
    if d is None:
        return {} if st in (400, 404, 422, 500) else None
    if not isinstance(d, list):
        return {}
    return {int(k["t"]) // 1000: (float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])) for k in d}


def bars_bybit(sym, t0, t1):
    """Bybit API is blocked from Actions; the public archive (kline_for_metatrader4, monthly 1m, linear USDT) is tried instead."""
    out = {}
    for y, m in bv.months(t0, t1):
        last = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
        url = (f"https://public.bybit.com/kline_for_metatrader4/{sym}USDT/{y}/{sym}USDT_{y}-{m:02d}-01_{y}-{m:02d}-{last}_1m.csv.gz")
        st, t = http(url, tries=2)
        if t is None:
            if st in (403, 404):
                return {}
            return None
        for ln in t.splitlines():
            f = ln.split(",")
            if len(f) < 6 or not f[0][:1].isdigit():
                continue
            try:
                ts = time.mktime(time.strptime(f[0] + " " + f[1], "%Y.%m.%d %H:%M")) - time.timezone
                out[int(ts)] = (float(f[2]), float(f[3]), float(f[4]), float(f[5]))
            except (ValueError, IndexError):
                continue
    return {t_: v for t_, v in out.items() if t0 <= t_ < t1}


FETCH = {"binance_um": bars_binance_um, "okx": bars_okx, "bybit": bars_bybit, "bitget": bars_bitget, "gate": bars_gate, "mexc": bars_mexc,
         "kucoin_fut": bars_kucoin_fut, "hyperliquid": bars_hyperliquid}


def span(ts):
    return ts - 3600, ts + DELAY + HOLD + 900


def shortable(bars, ts):
    """Locked rule: a bar before the entry (instrument live at the notice) and a bar at the exit (still tradable 4 h later)."""
    if not bars:
        return False
    e = int(-(-(ts + DELAY) // 60) * 60)
    has_before = any(t < ts + DELAY for t in bars)
    has_entry = any(e <= t < e + 180 for t in bars)
    has_exit = any(e + HOLD <= t < e + HOLD + 180 for t in bars)
    return has_before and has_entry and has_exit


def probe_one(e):
    ts = e["ts"]
    t0, t1 = span(ts)
    res = {}
    for v in VENUES:
        b = FETCH[v](e["sym"], t0, t1)
        res[v] = {"status": "failed" if b is None else "ok", "bars": 0 if not b else len(b), "shortable": bool(b) and shortable(b, ts)}
    b = bars_spot(e["sym"], t0, t1)
    res["binance_spot"] = {"status": "failed" if b is None else "ok", "bars": 0 if not b else len(b), "shortable": bool(b) and shortable(b, ts)}
    return {**e, "venues": res}


def mode_probe(out, events_path):
    doc = json.load(open(events_path))
    ev = doc["l1f"]
    with ThreadPoolExecutor(4) as ex:
        rows = list(ex.map(probe_one, ev))
    cover = {}
    for v in list(VENUES) + ["binance_spot"]:
        cover[v] = {"shortable": sum(r["venues"][v]["shortable"] for r in rows), "failed": sum(r["venues"][v]["status"] == "failed" for r in rows)}
    nop = [r for r in rows if not r["venues"]["binance_um"]["shortable"]]
    cover_nop = {v: {"shortable": sum(r["venues"][v]["shortable"] for r in nop), "failed": sum(r["venues"][v]["status"] == "failed" for r in nop)}
                 for v in list(VENUES) + ["binance_spot"]}
    any_perp = sum(any(r["venues"][v]["shortable"] for v in VENUES) for r in rows)
    any_perp_nop = sum(any(r["venues"][v]["shortable"] for v in VENUES) for r in nop)
    summ = {"events": len(rows), "no_binance_perp": len(nop), "cover_all": cover, "cover_no_binance_perp": cover_nop,
            "any_perp_all": any_perp, "any_perp_among_no_binance_perp": any_perp_nop, "errors": dict(ERR),
            "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump({"summary": summ, "rows": rows}, open(os.path.join(out, "probe.json"), "w"))
    print(json.dumps(summ, indent=1))


# ---------------------------------------------------------------- Binance margin evidence
def mode_margin(out):
    res = {"endpoints": {}}
    for name, url in (("sapi_allPairs", "https://api.binance.com/sapi/v1/margin/allPairs"),
                      ("sapi_allAssets", "https://api.binance.com/sapi/v1/margin/allAssets"),
                      ("bapi_vip_spec", "https://www.binance.com/bapi/margin/v1/friendly/margin/vip/spec/list-all"),
                      ("bapi_cross_pairs", "https://www.binance.com/bapi/margin/v1/public/margin/pair/list"),
                      ("bapi_cross_assets", "https://www.binance.com/bapi/margin/v1/public/margin/asset/list")):
        st, t = http(url, tries=2)
        res["endpoints"][name] = {"status": st, "head": (t or "")[:300]}
    arts = {}
    for cid in (48, 49, 93, 128, 161):
        page = 1
        while page <= 200:
            st, d = jget(f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={cid}&pageNo={page}&pageSize=50")
            a = (((d or {}).get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []
            if not a:
                break
            for x in a:
                if re.search(r"margin", x.get("title", ""), re.I):
                    arts[x.get("code") or x["title"]] = {"title": x["title"], "ts": x["releaseDate"] / 1000, "cid": cid}
            page += 1
        res.setdefault("pages", {})[cid] = page
    res["margin_titles"] = sorted(arts.values(), key=lambda a: a["ts"])
    json.dump(res, open(os.path.join(out, "margin.json"), "w"))
    print(json.dumps({"endpoints": res["endpoints"], "pages": res["pages"], "margin_titles": len(arts)}, indent=1))


def main():
    out, mode = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    if mode == "probe":
        mode_probe(out, sys.argv[3])
    elif mode == "margin":
        mode_margin(out)
    elif mode == "price":
        from research.studies import l1f_venues_price as P
        P.run(out, sys.argv[3], sys.argv[4])
    else:
        raise SystemExit("mode must be probe, margin or price")


if __name__ == "__main__":
    main()
