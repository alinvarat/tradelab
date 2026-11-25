"""Forced-flow families, stage A2 (still no prices): look at the structure and yield of archive snapshots (Wayback) for Bybit,
Upbit and Bithumb notices and at Binance article bodies. Workflow forced_flow.yml, mode probe2.

    python research/studies/forced_flow_probe2.py <out_dir>
"""
import gzip
import json
import os
import re
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}


def fetch(url, timeout=60, tries=3):
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                if b[:2] == b"\x1f\x8b":
                    b = gzip.decompress(b)
                return b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                return "ERR " + repr(e)[:150]
            time.sleep(2 * (k + 1))


def cdx(pattern, flt="", limit=20000, collapse="urlkey"):
    u = ("http://web.archive.org/cdx/search/cdx?output=json&matchType=prefix&filter=statuscode:200"
         f"&collapse={collapse}&limit={limit}&fl=timestamp,original&from=2024&url={quote(pattern)}" + (f"&filter={quote(flt)}" if flt else ""))
    t = fetch(u, timeout=120)
    try:
        d = json.loads(t)
    except Exception:  # noqa: BLE001
        return t[:200]
    return d[1:]


def strip(html):
    html = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def snap(ts, url):
    return fetch(f"http://web.archive.org/web/{ts}id_/{url}")


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    res = {}
    only = sys.argv[2] if len(sys.argv) > 2 else ""
    if only == "bybit":
        b = cdx("announcements.bybit.com/en/article/", "original:.*([Dd]elist|[Mm]onitoring|[Rr]emov|[Ss]uspend).*")
        b2 = cdx("announcements.bybit.com/article/", "original:.*([Dd]elist|[Mm]onitoring|[Rr]emov|[Ss]uspend).*")
        res["bybit"] = {"n_en": len(b) if isinstance(b, list) else b, "n_plain": len(b2) if isinstance(b2, list) else b2}
        allb = (b if isinstance(b, list) else []) + (b2 if isinstance(b2, list) else [])
        res["bybit"]["urls"] = [x for x in allb[:80]]
        res["bybit"]["samples"] = [(x[0], x[1], snap(x[0], x[1])[:200], strip(snap(x[0], x[1]))[:1200]) for x in allb[:: max(1, len(allb) // 4)][:4]]
        with open(os.path.join(out, "probe2.json"), "w") as f:
            json.dump(res, f, indent=1, ensure_ascii=False)
        return
    # Binance article body
    codes = ["1c44ea17a57943aa95752f7b7360bd69", "c498db770fa844e188bbad8cc5986674", "e56e5e6b33ad493c98a71189643ade4f"]
    res["binance_detail"] = {}
    for c in codes:
        t = fetch(f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={c}")
        res["binance_detail"][c] = t[:3500]
    # Bybit articles about delisting / monitoring
    b = cdx("announcements.bybit.com/en/article/", "original:.*([Dd]elist|[Mm]onitoring|[Rr]emov|[Ss]uspend).*")
    res["bybit"] = {"n": len(b) if isinstance(b, list) else b, "first": b[:5] if isinstance(b, list) else None,
                    "titles": [x[1].rsplit("/", 2)[-2][:100] for x in b[:60]] if isinstance(b, list) else None}
    if isinstance(b, list) and b:
        res["bybit"]["samples"] = [strip(snap(x[0], x[1]))[:900] for x in b[:: max(1, len(b) // 3)][:3]]
    print("bybit", res["bybit"].get("n"), flush=True)
    # Upbit
    u = cdx("api-manager.upbit.com/api/v1/announcements")
    res["upbit"] = {"n": len(u) if isinstance(u, list) else u, "urls": [x[1] for x in u[:40]] if isinstance(u, list) else None}
    if isinstance(u, list) and u:
        res["upbit"]["samples"] = [(x[0], x[1], snap(x[0], x[1])[:1200]) for x in u[:: max(1, len(u) // 4)][:4]]
    print("upbit", res["upbit"].get("n"), flush=True)
    # Upbit HTML notice pages
    up = cdx("upbit.com//service_center/notice", limit=3000)
    res["upbit_page"] = {"n": len(up) if isinstance(up, list) else up}
    if isinstance(up, list) and up:
        res["upbit_page"]["samples"] = [(x[0], x[1], strip(snap(x[0], x[1]))[:700]) for x in up[:: max(1, len(up) // 3)][:3]]
    # Bithumb
    h = cdx("feed.bithumb.com/notice/", limit=20000)
    res["bithumb"] = {"n": len(h) if isinstance(h, list) else h}
    if isinstance(h, list) and h:
        res["bithumb"]["samples"] = [(x[0], x[1], strip(snap(x[0], x[1]))[:900]) for x in h[:: max(1, len(h) // 4)][:4]]
    print("bithumb", res["bithumb"].get("n"), flush=True)
    with open(os.path.join(out, "probe2.json"), "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
