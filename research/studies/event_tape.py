"""Exchange-notice tape screen (protocol_notice_tape_20261125.md): fetch announcements from OKX, Bybit, KuCoin, Bitget
(+ Bithumb/Coinbase when a feed exists), classify them, price the perp 1-minute paths, evaluate the locked 192-cell grid
with Holm, keep the rows. Runs on GitHub Actions only (workflow event_book.yml, mode tape).

    python research/studies/event_tape.py <out_dir>
"""
import gzip
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import notice_tape as nt   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
START = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
END = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()
MID = datetime(2025, 7, 1, tzinfo=timezone.utc).timestamp()
MONTHS = 34
PRE_S = 3600
POST_S = 72 * 3600 + 15 * 60 + 120


def get(url, timeout=25, tries=4):
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                print("  get failed", url[:100], repr(e)[:80], flush=True)
                return None
            time.sleep(1.5 * (k + 1))


# ---------------------------------------------------------------- announcement feeds -> [{venue, title, ts}]
def okx_notices(gaps):
    out = []
    for typ in ("announcements-new-listings", "announcements-delistings", "announcements-latest-announcements",
                "announcements-api", "announcements-others"):
        page = 1
        while page <= 150:
            d = get(f"https://www.okx.com/api/v5/support/announcements?annType={typ}&page={page}")
            det = ((d or {}).get("data") or [{}])[0].get("details") or []
            if not det:
                if not d:
                    gaps[f"okx:{typ}"] = f"failed at page {page}"
                break
            for a in det:
                out.append({"venue": "okx", "title": a.get("title", ""), "ts": int(a["pTime"]) / 1000})
            if min(int(a["pTime"]) for a in det) / 1000 < START:
                break
            page += 1
    return out


def bybit_notices(gaps):
    out = []
    for typ in ("new_crypto", "delistings", "product_updates", "latest_bybit_news", "latest_activities"):
        page = 1
        while page <= 150:
            d = get(f"https://api.bybit.com/v5/announcements/index?locale=en-US&type={typ}&limit=50&page={page}")
            lst = ((d or {}).get("result") or {}).get("list") or []
            if not lst:
                if not d:
                    gaps[f"bybit:{typ}"] = f"failed at page {page}"
                break
            for a in lst:
                out.append({"venue": "bybit", "title": a.get("title", ""), "ts": int(a.get("dateTimestamp") or a.get("publishTime")) / 1000})
            if min(int(a.get("dateTimestamp") or a.get("publishTime")) for a in lst) / 1000 < START:
                break
            page += 1
    return out


def kucoin_notices(gaps):
    out = []
    for typ in ("new-listings", "delistings", "product-updates", "latest-announcements"):
        page = 1
        while page <= 150:
            d = get(f"https://api.kucoin.com/api/v3/announcements?language=en_US&type={typ}&pageSize=50&currentPage={page}")
            items = ((d or {}).get("data") or {}).get("items") or []
            if not items:
                if not d:
                    gaps[f"kucoin:{typ}"] = f"failed at page {page}"
                break
            for a in items:
                out.append({"venue": "kucoin", "title": a.get("annTitle", ""), "ts": int(a["cTime"]) / 1000})
            if min(int(a["cTime"]) for a in items) / 1000 < START:
                break
            page += 1
    return out


def bitget_notices(gaps):
    out = []
    for typ in ("coin_listings", "symbol_delisting", "product_updates", "latest_news"):
        t = END
        while t > START:
            a = t - 30 * 86400
            d = get("https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=" + typ
                    + f"&startTime={int(a * 1000)}&endTime={int(t * 1000)}")
            if d is None:
                gaps[f"bitget:{typ}"] = f"failed window {time.strftime('%Y-%m', time.gmtime(a))}"
            for n in (d or {}).get("data") or []:
                out.append({"venue": "bitget", "title": n.get("annTitle", ""), "ts": float(n["cTime"]) / 1000})
            t = a
    return out


FEEDS = {"okx": okx_notices, "bybit": bybit_notices, "kucoin": kucoin_notices, "bitget": bitget_notices}


def build_events(gaps):
    raw, reach = [], {}
    for name, fn in FEEDS.items():
        try:
            got = fn(gaps)
        except Exception as e:  # noqa: BLE001
            gaps[name] = repr(e)[:150]
            got = []
        got = [g for g in got if START <= g["ts"] < END]
        reach[name] = {"notices": len(got), "first": time.strftime("%Y-%m-%d", time.gmtime(min((g["ts"] for g in got), default=0))),
                       "last": time.strftime("%Y-%m-%d", time.gmtime(max((g["ts"] for g in got), default=0)))}
        raw += got
    ev, seen = [], {}
    for g in sorted(raw, key=lambda g: g["ts"]):
        for cls, syms in nt.classify_title(g["title"]):
            for s in syms:
                k = (cls, s)
                if k in seen and g["ts"] - seen[k] < 6 * 3600:
                    continue
                seen[k] = g["ts"]
                ev.append({"venue": g["venue"], "cls": cls, "symbol": s, "ts": g["ts"], "title": g["title"][:140]})
    return ev, reach


# ---------------------------------------------------------------- perp prices (Bybit linear 1-minute)
def bybit_bars(base, t0, t1):
    """[(open_ts, high, low, close)] 1-minute bars of <base>USDT linear perp over [t0, t1), or None on failure, [] none."""
    out, cur = {}, t0
    for _ in range(8):
        end = min(t1, cur + 1000 * 60)
        d = get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={base}USDT&interval=1"
                f"&start={int(cur * 1000)}&end={int(end * 1000 - 1)}&limit=1000")
        if not d or d.get("retCode") != 0:
            return None
        for k in d["result"]["list"]:
            out[int(k[0]) // 1000] = (float(k[2]), float(k[3]), float(k[4]))
        cur = end
        if cur >= t1:
            break
    return sorted((t, *v) for t, v in out.items())


def event_path(e):
    """Perp 1-minute path (index 0 = minute of the notice) and BTC closes aligned to it, or a skip reason."""
    ts = int(e["ts"] // 60 * 60)
    for cand in (e["symbol"], "1000" + e["symbol"]):
        bars = bybit_bars(cand, ts - PRE_S, ts + POST_S)
        if bars is None:
            return None, "bars_failed"
        if bars:
            break
    else:
        return None, "no_perp"
    if not any(t < ts for t, *_ in bars):
        return None, "not_trading_before"
    by = {t: (h, lo, c) for t, h, lo, c in bars}
    n = POST_S // 60
    path = [by.get(ts + 60 * k) for k in range(n)]
    btc = bybit_bars("BTC", ts, ts + POST_S)
    if not btc:
        return None, "btc_failed"
    bb = {t: c for t, h, lo, c in btc}
    bench = [bb.get(ts + 60 * k) for k in range(n)]
    return {"path": [[round(x, 8) for x in p] if p else None for p in path], "bench": bench, "price_venue": "bybit"}, None


def evaluate(rows):
    """Grid evaluation: returns {cell: values list with (ts, ret)}."""
    cells = {}
    for typ in nt.TYPES:
        for h, hs in nt.HOLDS.items():
            for dname, ds in nt.DELAYS.items():
                for stop in nt.STOPS:
                    key = f"{typ[0]}|{'long' if typ[1] > 0 else 'short'}|{h}|{dname}|{int(stop * 100)}"
                    vals = []
                    for r in rows:
                        if r["cls"] != typ[0]:
                            continue
                        v = nt.cell_return(r["path"], typ[1], hs, ds, stop, r["bench"])
                        if v is not None:
                            vals.append((r["ts"], v))
                    cells[key] = vals
    return cells


def block_p(values, days, rng):
    from core.news_backtest import block_bootstrap_p
    return block_bootstrap_p(values, days, rng)


def main():
    out_dir = sys.argv[1]
    os.makedirs(os.path.join(out_dir, "tape"), exist_ok=True)
    gaps = {}
    events, reach = build_events(gaps)
    print("events", len(events), reach, gaps, flush=True)
    skipped, rows = {}, []

    def one(e):
        p, why = event_path(e)
        return e, p, why
    with ThreadPoolExecutor(8) as ex:
        for e, p, why in ex.map(one, events):
            if p is None:
                skipped[why] = skipped.get(why, 0) + 1
            else:
                rows.append({**e, **p})
    print("priced rows", len(rows), skipped, flush=True)
    with gzip.open(os.path.join(out_dir, "tape", "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    cells = evaluate(rows)
    rng = random.Random(20261125)
    pvals, table = {}, {}
    for k, vals in cells.items():
        v = [x for _, x in vals]
        if len(v) < 5:
            pvals[k] = None
            continue
        days = [time.strftime("%Y-%m-%d", time.gmtime(t)) for t, _ in vals]
        # one-sided: block-bootstrap p that mean <= 0 (the screens helper tests mean > 0 the same way)
        pvals[k] = block_p(v, days, rng)
    adj = nt.holm(pvals)
    for k, vals in cells.items():
        v = [x for _, x in vals]
        h1 = [x for t, x in vals if t < MID]
        h2 = [x for t, x in vals if t >= MID]
        table[k] = nt.cell_verdict(v, (h1, h2), MONTHS, adj[k][0])
        table[k]["p"] = None if pvals[k] is None else round(pvals[k], 5)
        table[k]["holm_reject"] = adj[k][1]
    passed = sorted(k for k, v in table.items() if v.get("pass"))
    best = sorted(((v.get("x", 0), k) for k, v in table.items() if v.get("n", 0) >= nt.MIN_N), reverse=True)[:15]
    by_class = {c: sum(1 for r in rows if r["cls"] == c) for c in nt.CLASSES}
    by_venue = {v: sum(1 for r in rows if r["venue"] == v) for v in FEEDS}
    summ = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "events": len(events), "priced": len(rows),
            "skipped": skipped, "gaps": gaps, "reach": reach, "by_class": by_class, "by_venue": by_venue,
            "family_size": len(cells), "passed": passed, "top_x_cells": [{"cell": k, "x": x, **{kk: table[k].get(kk) for kk in ("n", "mean", "s", "per_month", "adj_p", "pass")}} for x, k in best],
            "cells_with_n_ge_30": sum(1 for v in table.values() if v.get("n", 0) >= nt.MIN_N)}
    with open(os.path.join(out_dir, "tape", "summary.json"), "w") as f:
        json.dump({"summary": summ, "table": table}, f, indent=1, default=str)
    print(json.dumps(summ, default=str, indent=1))


if __name__ == "__main__":
    main()
