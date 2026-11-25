"""Forced-flow families, stage A (no prices, no outcomes): collect announcement titles and probe archives/mirrors from a GitHub
runner so the event parsers and the protocol can be fixed before any price is looked at. Workflow forced_flow.yml, mode probe.

    python research/studies/forced_flow_probe.py <out_dir>

Writes <out>/binance_titles.jsonl (catalog, ts, title, code), <out>/okx_depth.json, <out>/wayback.json, <out>/mirrors.json.
"""
import json
import os
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
START = 1704067200          # 2024-01-01
CATALOGS = {161: "delisting", 49: "latest activities", 93: "latest news", 48: "new listings", 157: "wallet maintenance", 51: "api updates"}


def get(url, timeout=30, tries=3, raw=False):
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b.decode("utf-8", "replace") if raw else json.loads(b)
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:120]
            if k == tries - 1:
                return {"_error": err} if not raw else "ERR " + err
            time.sleep(1.5 * (k + 1))


def binance_titles(out):
    stats = {}
    with open(os.path.join(out, "binance_titles.jsonl"), "w", encoding="utf-8") as f:
        for cid in CATALOGS:
            page, n, oldest = 1, 0, None
            while page <= 120:
                d = get(f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={cid}&pageNo={page}&pageSize=50")
                arts = (((d or {}).get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []
                if not arts:
                    break
                for a in arts:
                    ts = a["releaseDate"] / 1000
                    oldest = ts if oldest is None else min(oldest, ts)
                    if ts >= START:
                        f.write(json.dumps({"cat": cid, "ts": ts, "title": a.get("title", ""), "code": a.get("code")}, ensure_ascii=False) + "\n")
                        n += 1
                if min(a["releaseDate"] for a in arts) / 1000 < START:
                    break
                page += 1
            stats[cid] = {"name": CATALOGS[cid], "titles_from_2024": n, "pages": page, "oldest": oldest and time.strftime("%Y-%m-%d", time.gmtime(oldest))}
            print("binance catalog", cid, stats[cid], flush=True)
    return stats


def okx_depth():
    out = {}
    types = get("https://www.okx.com/api/v5/support/announcement-types")
    out["types"] = types
    for item in (types or {}).get("data") or []:
        typ = item.get("annType")
        page, first, last, n = 1, None, None, 0
        while page <= 200:
            d = get(f"https://www.okx.com/api/v5/support/announcements?annType={typ}&page={page}")
            det = ((d or {}).get("data") or [{}])[0].get("details") or []
            if not det:
                break
            ts = [int(a["pTime"]) / 1000 for a in det]
            first = max(ts) if first is None else first
            last = min(ts) if last is None else min(last, min(ts))
            n += len(det)
            page += 1
        out[typ] = {"notices": n, "newest": first and time.strftime("%Y-%m-%d", time.gmtime(first)),
                    "oldest": last and time.strftime("%Y-%m-%d", time.gmtime(last))}
        print("okx", typ, out[typ], flush=True)
    return out


WAYBACK = {
    "upbit_api": "api-manager.upbit.com/api/v1/announcements",
    "upbit_notice_old": "api-manager.upbit.com/api/v1/notices",
    "upbit_page": "upbit.com/service_center/notice",
    "bithumb_feed": "feed.bithumb.com/notice",
    "bithumb_cafe": "cafe.bithumb.com/notice",
    "bybit_api": "api.bybit.com/v5/announcements/index",
    "bybit_page": "announcements.bybit.com/en",
    "bybit_help": "announcements.bybit.com/article",
    "coinbase_blog": "www.coinbase.com/blog",
    "coinbase_assets": "assets.coinbase.com",
    "coinbase_market_updates": "www.coinbase.com/blog/tagged/market-updates",
    "okx_help": "www.okx.com/help/section/announcements-delistings",
}


def wayback():
    out = {}
    for name, pat in WAYBACK.items():
        url = ("http://web.archive.org/cdx/search/cdx?output=json&matchType=prefix&filter=statuscode:200&collapse=timestamp:8"
               f"&limit=4000&fl=timestamp,original,mimetype&from=2024&url={quote(pat)}")
        d = get(url, timeout=90)
        rows = d[1:] if isinstance(d, list) and len(d) > 1 else []
        info = {"snapshots": len(rows), "error": d.get("_error") if isinstance(d, dict) else None}
        if rows:
            info["first"], info["last"] = rows[0][0], rows[-1][0]
            info["months"] = len({r[0][:6] for r in rows})
            info["sample_urls"] = sorted({r[1] for r in rows})[:6]
            mid = rows[len(rows) // 2]
            body = get(f"http://web.archive.org/web/{mid[0]}id_/{mid[1]}", timeout=60, raw=True)
            info["sample_fetch"] = {"ts": mid[0], "url": mid[1], "head": body[:700]}
        out[name] = info
        print("wayback", name, {k: v for k, v in info.items() if k != "sample_fetch"}, flush=True)
    return out


MIRRORS = {
    "bybit_bytick": "https://api.bytick.com/v5/announcements/index?locale=en-US&type=delistings&limit=3&page=1",
    "bybit_direct": "https://api.bybit.com/v5/announcements/index?locale=en-US&type=delistings&limit=3&page=1",
    "upbit_direct": "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=3&category=trade",
    "upbit_jina": "https://r.jina.ai/https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=3&category=trade",
    "bithumb_jina": "https://r.jina.ai/https://feed.bithumb.com/notice",
    "bybit_jina": "https://r.jina.ai/https://api.bybit.com/v5/announcements/index?locale=en-US&type=delistings&limit=3&page=1",
    "coinbase_jina": "https://r.jina.ai/https://www.coinbase.com/blog/landing",
    "bithumb_api": "https://api.bithumb.com/public/ticker/BTC_KRW",
    "coinbase_exchange": "https://api.exchange.coinbase.com/products",
}


def mirrors():
    out = {}
    for k, u in MIRRORS.items():
        body = get(u, timeout=40, tries=2, raw=True)
        out[k] = body[:300]
        print("mirror", k, body[:120].replace("\n", " "), flush=True)
    return out


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    res = {}
    for name, fn in (("binance", lambda: binance_titles(out)), ("okx", okx_depth), ("wayback", wayback), ("mirrors", mirrors)):
        try:
            res[name] = fn()
        except Exception as e:  # noqa: BLE001
            res[name] = {"error": repr(e)[:200]}
        with open(os.path.join(out, f"{name}.json"), "w") as f:
            json.dump(res[name], f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
