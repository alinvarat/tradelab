"""Round 3 Track B probes: reachability and coverage only. Reads no price outcome and no Haiku reply (protocol_r3_20261126.md).
    probe_b.py <out>
Each probe records status, byte counts, a few title/timestamp samples and counts, never a return."""
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile

UA_BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "*/*"}
UA_SEC = {"User-Agent": os.environ.get("TRADELAB_SEC_UA") or "tradelab-research research@example.com"}


def get(url, headers=None, timeout=45):
    try:
        req = urllib.request.Request(url, headers=headers or UA_BROWSER)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:  # noqa: BLE001
        return str(e)[:80], b""


def brief(url, headers=None, n=300):
    st, body = get(url, headers)
    return {"url": url, "status": st, "bytes": len(body), "head": body[:n].decode("utf-8", "replace")}


CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
KO = re.compile(r"[가-힯]")
ZH = re.compile(r"[一-鿿]")
COINS_CJK = ["비트코인", "이더리움", "리플", "솔라나", "도지코인", "比特币", "比特幣", "以太坊", "狗狗币", "瑞波币", "索拉纳"]


def probe_gnw(rep):
    r = []
    for u in ("https://www.globenewswire.com/search/date/20260301", "https://www.globenewswire.com/en/search/date/20260301",
              "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies",
              "https://www.globenewswire.com/sitemap.xml", "https://www.globenewswire.com/sitemap/news.xml"):
        r.append(brief(u))
    # Wayback CDX: how many archived release pages exist per day (prefix = the date in the release URL)
    for day in ("2026/03/02", "2026/01/15", "2025/12/10"):
        for host in ("globenewswire.com/news-release/", "prnewswire.com/news-releases/"):
            u = f"https://web.archive.org/cdx/search/cdx?url={host}{day}/&matchType=prefix&output=json&limit=2000&fl=timestamp,original,statuscode&filter=statuscode:200"
            st, body = get(u, timeout=90)
            n = None
            if st == 200 and body:
                try:
                    n = len(json.loads(body)) - 1
                except Exception:  # noqa: BLE001
                    n = -1
            r.append({"cdx": host + day, "status": st, "rows": n})
    for u in ("https://www.prnewswire.com/news-releases/news-releases-list/?page=1&pagesize=100", "https://www.prnewswire.com/rss/news-releases-list.rss",
              "https://www.prnewswire.com/sitemap-news.xml", "https://www.prnewswire.com/sitemap.xml"):
        r.append(brief(u))
    rep["wires"] = r


def probe_gkg_translation(rep):
    out = {}
    for stamp in ("20260301120000", "20251215120000", "20260715120000"):
        u = f"https://data.gdeltproject.org/gdeltv2/{stamp}.translation.gkg.csv.zip"
        st, body = get(u, timeout=120)
        d = {"status": st, "bytes": len(body)}
        if st == 200 and body:
            try:
                txt = zipfile.ZipFile(io.BytesIO(body)).read(zipfile.ZipFile(io.BytesIO(body)).namelist()[0]).decode("utf-8", "replace")
                lines = txt.split("\n")
                titles = []
                for ln in lines:
                    f = ln.split("\t")
                    if len(f) >= 27:
                        m = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", f[26], re.S)
                        if m:
                            titles.append((f[3], m.group(1).strip(), f[25][:60] if len(f) > 25 else ""))
                d["rows"] = len(lines)
                d["titles"] = len(titles)
                d["title_has_cjk"] = sum(1 for t in titles if CJK.search(t[1]))
                d["title_has_korean"] = sum(1 for t in titles if KO.search(t[1]))
                d["title_has_chinese"] = sum(1 for t in titles if ZH.search(t[1]))
                d["cjk_coin_titles"] = [t[1][:120] for t in titles if any(c in t[1] for c in COINS_CJK)][:8]
                d["en_crypto_titles"] = sum(1 for t in titles if re.search(r"\b(bitcoin|ethereum|crypto)\b", t[1], re.I))
                d["sample"] = [list(t) for t in titles[:8]]
                d["translation_info_sample"] = [ln.split("\t")[25][:80] for ln in lines[:200] if len(ln.split("\t")) > 25 and ln.split("\t")[25]][:4]
            except Exception as e:  # noqa: BLE001
                d["error"] = str(e)[:120]
        out[stamp] = d
    rep["gkg_translation"] = out


RSS = ["https://www.blockmedia.co.kr/feed", "https://www.tokenpost.kr/rss", "https://www.coindeskkorea.com/rss/allArticle.xml",
       "https://cointelegraph.com/rss", "https://www.panewslab.com/rss.xml", "https://www.odaily.news/rss", "https://www.8btc.com/rss",
       "https://www.theblockbeats.info/rss", "https://cn.cointelegraph.com/rss"]


def probe_rss(rep):
    out = []
    for u in RSS:
        st, body = get(u)
        txt = body.decode("utf-8", "replace")
        items = re.findall(r"<item>.*?</item>", txt, re.S)
        dates = re.findall(r"<pubDate>(.*?)</pubDate>", txt)
        out.append({"url": u, "status": st, "bytes": len(body), "items": len(items), "first_pub": dates[:1], "last_pub": dates[-1:],
                    "cjk_titles": sum(1 for i in items if CJK.search(i))})
    rep["rss"] = out


def probe_sec(rep):
    out = {}
    for day, q in (("20260302", "QTR1"), ("20260115", "QTR1"), ("20251210", "QTR4"), ("20260715", "QTR3")):
        u = f"https://www.sec.gov/Archives/edgar/daily-index/{day[:4]}/{q}/form.{day}.idx"
        st, body = get(u, UA_SEC, 60)
        txt = body.decode("latin-1", "replace")
        n8k = len([ln for ln in txt.split("\n") if ln.startswith("8-K ")])
        out[day] = {"status": st, "bytes": len(body), "n_8k": n8k}
    rep["sec_daily_index"] = out


def probe_yahoo(rep):
    """Bar coverage on a fixed sample of micro/small-cap tickers (counts only, no returns)."""
    syms = ["AEHR", "CLSK", "GEVO", "IZEA", "KULR", "MVIS", "NVOS", "OPTT", "SNDL", "TOUR", "UAVS", "WKSP", "XELB", "ZVSA", "ACHV"]
    now = int(time.time())
    res = {}
    for s in syms:
        r = {}
        for itv, back in (("5m", 58), ("1h", 700)):
            u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?period1={now - back * 86400}&period2={now}&interval={itv}&includePrePost=true")
            st, body = get(u)
            n = None
            if st == 200:
                try:
                    j = json.loads(body)["chart"]["result"][0]
                    n = [len(j.get("timestamp") or []), (j["timestamp"][0] if j.get("timestamp") else None)]
                except Exception:  # noqa: BLE001
                    n = -1
            r[itv] = {"status": st, "bars_first_ts": n}
        res[s] = r
    rep["yahoo_coverage"] = res


def main(out):
    rep = {"utc": int(time.time())}
    for fn in (probe_gnw, probe_gkg_translation, probe_rss, probe_sec, probe_yahoo):
        try:
            fn(rep)
        except Exception as e:  # noqa: BLE001
            rep[fn.__name__ + "_error"] = str(e)[:200]
        print(fn.__name__, "done", flush=True)
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "probe_b.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:20000])


if __name__ == "__main__":
    main(sys.argv[1])
