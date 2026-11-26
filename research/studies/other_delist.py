"""Other exchanges' own spot delist notices (protocol_other_spot_delist_20261127.md). GitHub Actions only (workflow other_delist.yml).

    python research/studies/other_delist.py <out_dir> notices <frozen_events.json>   notice COUNTS only, no prices (feeds of KuCoin, Bitget, Gate, MEXC;
                                                                                     OKX and Bybit spot titles from the frozen forced-flow events)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import forced_flow as ff   # noqa: E402
from core import notice_tape as nt   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept": "application/json"}
NOT_EVENT = re.compile(r"extend|postpone|cancel|resum|complet|perpetual|futures|\bswap\b|contract|option|margin|leveraged|etf|\bbull\b|\bbear\b|"
                       r"\b\d+[LS]\b|\b[A-Z]+3[LS]\b", re.I)
ERR = {}


def get(url, tries=2, timeout=15, raw_gz=False):
    last = 0
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                if raw_gz and b[:2] == b"\x1f\x8b":
                    import gzip
                    b = gzip.decompress(b)
                return r.status, b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = getattr(e, "code", 0) or 0
            ERR[f"{last}{type(e).__name__}"] = ERR.get(f"{last}{type(e).__name__}", 0) + 1
            if last in (400, 403, 404, 451):
                break
            time.sleep(1 + k)
    return last, None


def jget(url, **kw):
    st, t = get(url, **kw)
    try:
        return st, json.loads(t) if t else None
    except ValueError:
        return st, None


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def spot_syms(title):
    """Coins of a spot delist title, or [] (perp/futures/margin/ETF/extend/cancel titles are not events)."""
    if NOT_EVENT.search(title):
        return []
    cls = nt.classify_title(title)
    return [s for c, syms in cls if c == "delist" for s in syms]


def kucoin_notices(out):
    ev, page, total = [], 1, 1
    while page <= min(total, 80):
        st, d = jget(f"https://api.kucoin.com/api/v3/announcements?currentPage={page}&pageSize=50&annType=delistings&lang=en_US&startTime=1704067200000")
        if not d or d.get("code") != "200000":
            out["kucoin_status"] = st
            break
        data = d["data"]
        total = int(data.get("totalPage") or 1)
        for a in data.get("items") or []:
            ev.append({"title": a.get("annTitle", ""), "ts": a["cTime"] / 1000})
        page += 1
        time.sleep(0.15)
    out["kucoin_pages"] = page - 1
    return ev


def bitget_notices(out):
    ev, seen = [], set()
    t = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 30, tzinfo=timezone.utc)
    samples = []
    while t < end:
        t2 = datetime(t.year + (t.month == 12), t.month % 12 + 1, 1, tzinfo=timezone.utc)
        st, d = jget("https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=symbol_delisting"
                     f"&startTime={int(t.timestamp() * 1000)}&endTime={int(t2.timestamp() * 1000)}")
        rows = (d or {}).get("data") or []
        if len(samples) < 2:
            samples.append({"status": st, "n": len(rows), "head": str(d)[:300]})
        for a in rows:
            k = a.get("annId") or a.get("annUrl") or a.get("annTitle")
            if k not in seen:
                seen.add(k)
                ev.append({"title": a.get("annTitle", ""), "ts": float(a["cTime"]) / 1000})
        t = t2
        time.sleep(0.15)
    out["bitget_samples"] = samples
    return ev


def candidates(out, name, urls):
    res = []
    for u in urls:
        st, t = get(u, tries=1)
        res.append({"url": u, "status": st, "head": (t or "")[:240].replace("\n", " ")})
    out[name + "_candidates"] = res


def mode_notices(out_dir, frozen):
    doc = json.load(open(frozen))
    out = {"built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    feeds = {}
    for e in doc["events"]:
        if e["fam"] == "okx_delist" and nt.classify_title(e["title"]) and nt.classify_title(e["title"])[0][0] == "delist" and not NOT_EVENT.search(e["title"]):
            feeds.setdefault("okx", []).append({"title": e["title"], "ts": e["ts"], "sym": e["sym"]})
        if e["fam"] == "bybit_delist":
            c = ff.bybit_class_symbols(e["title"])
            if c and c[0] == "delist" and e["sym"] in c[1] and not NOT_EVENT.search(e["title"]):
                feeds.setdefault("bybit", []).append({"title": e["title"], "ts": e["ts"], "sym": e["sym"]})
    for name, fn in (("kucoin", kucoin_notices), ("bitget", bitget_notices)):
        try:
            rows = fn(out)
        except Exception as x:  # noqa: BLE001
            out[name + "_error"] = repr(x)[:200]
            rows = []
        for r in rows:
            for s in spot_syms(r["title"]):
                feeds.setdefault(name, []).append({"title": r["title"], "ts": r["ts"], "sym": s})
        out[name + "_raw_notices"] = len(rows)
    candidates(out, "gate", ["https://www.gate.com/announcements/delisted", "https://www.gate.io/announcements/delisted",
                             "https://www.gate.com/apiw/v2/announcement/list?page=1&limit=20&type=delisted",
                             "https://api.gateio.ws/api/v4/spot/currencies"])
    candidates(out, "mexc", ["https://www.mexc.com/support/sections/15425930648857", "https://www.mexc.com/api/operation/announcement/list?page=1&size=20",
                             "https://www.mexc.com/help/announce/api/v1/list?page=1", "https://api.mexc.com/api/v3/exchangeInfo?symbol=BTCUSDT"])
    for k, rows in feeds.items():
        rows = [r for r in rows if ff.in_window(r["ts"])]
        feeds[k] = rows
        sp = {n: sum(1 for r in rows if a <= r["ts"] < b) for n, (a, b) in ff.BOUNDS.items()}
        out[k] = {"events": len(rows), "coins": len({r["sym"] for r in rows}), "splits": sp,
                  "first": day(min(r["ts"] for r in rows)) if rows else None, "last": day(max(r["ts"] for r in rows)) if rows else None,
                  "sample": [(r["sym"], day(r["ts"]), r["title"][:80]) for r in rows[:4]]}
    out["errors"] = dict(ERR)
    os.makedirs(out_dir, exist_ok=True)
    json.dump({"summary": out, "events": feeds}, open(os.path.join(out_dir, "notices.json"), "w"), ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000], flush=True)


def mode_reach(out_dir, notices_path):
    """Reach of the own-book price history (HEAD only, no prices): Bybit spot trade archive for each Bybit event; Bitget notice paging."""
    ev = json.load(open(notices_path))["events"].get("bybit", [])
    res = {"bybit_events": len(ev), "ok": 0, "missing": 0, "failed": 0, "samples": []}
    st0, idx = get("https://public.bybit.com/spot/", tries=2)
    res["bybit_spot_index_status"] = st0
    res["bybit_spot_index_symbols"] = len(re.findall(r'href="([A-Z0-9]+USDT)/"', idx or ""))
    for e in ev:
        g = time.gmtime(e["ts"])
        d = f"{g.tm_year}-{g.tm_mon:02d}-{g.tm_mday:02d}"
        u = f"https://public.bybit.com/spot/{e['sym']}USDT/{e['sym']}USDT_{d}.csv.gz"
        try:
            req = Request(u, headers=UA, method="HEAD")
            with urlopen(req, timeout=15) as r:
                c = r.status
        except Exception as x:  # noqa: BLE001
            c = getattr(x, "code", 0) or 0
        res["ok" if c == 200 else "missing" if c in (403, 404) else "failed"] += 1
        if len(res["samples"]) < 6:
            res["samples"].append((e["sym"], d, c))
    pages, seen, cur, first = [], set(), "", None
    for i in range(60):
        st, d = jget("https://api.bitget.com/api/v2/public/annoucements?language=en_US&annType=symbol_delisting" + (f"&cursor={cur}" if cur else ""))
        rows = (d or {}).get("data") or []
        new = [a for a in rows if a["annId"] not in seen]
        pages.append((st, len(rows), len(new)))
        if not new:
            break
        for a in new:
            seen.add(a["annId"])
            first = min(first or 1e18, float(a["cTime"]) / 1000)
        cur = new[-1]["annId"]
        time.sleep(0.15)
    res["bitget_pages"] = pages[:8]
    res["bitget_total"] = len(seen)
    res["bitget_oldest"] = day(first) if first else None
    print(json.dumps(res, indent=1), flush=True)
    json.dump(res, open(os.path.join(out_dir, "reach.json"), "w"))


def main():
    out_dir, mode = sys.argv[1], sys.argv[2]
    if mode == "notices":
        mode_notices(out_dir, sys.argv[3])
    elif mode == "price":
        os.makedirs(out_dir, exist_ok=True)
        from research.studies import other_delist_price as P
        P.run(out_dir, sys.argv[3], sys.argv[4])
    elif mode == "reach":
        os.makedirs(out_dir, exist_ok=True)
        mode_reach(out_dir, sys.argv[3])
    else:
        raise SystemExit("mode must be notices")


if __name__ == "__main__":
    main()
