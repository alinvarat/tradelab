"""Forced-flow event families (protocol_forced_flow_20261125.md): build announcement events, price them on perps, apply the sweep
stage-0 gate and the validation/test criteria with a reversed-side placebo and a random control. GitHub Actions only (workflow
forced_flow.yml, mode run).

    python research/studies/forced_flow.py <out_dir>

Writes <out_dir>/events.json, rows.jsonl.gz (one row per priced event with the per-rule gross/control numbers) and summary.json.
"""
import gzip
import html
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import forced_flow as ff   # noqa: E402
from core import notice_tape as nt   # noqa: E402
from core import screens as sc       # noqa: E402
from core import sweep_stats as ss   # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
FAMILIES = ("mon_tag", "fut_delist", "pair_rm", "okx_delist", "upbit_delist", "upbit_caution", "bithumb_delist", "bithumb_caution",
            "bybit_delist")
LOCK = threading.Lock()
LAST = [0.0]
FAILS = {}


def pace(gap):
    with LOCK:
        w = LAST[0] + gap - time.time()
        LAST[0] = max(time.time(), LAST[0] + gap)
    if w > 0:
        time.sleep(w)


def fetch(url, timeout=40, tries=4, raw=True, gap=0.0):
    for k in range(tries):
        try:
            if gap:
                pace(gap)
            with urlopen(Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
            if b[:2] == b"\x1f\x8b":
                b = gzip.decompress(b)
            t = b.decode("utf-8", "replace")
            return t if raw else json.loads(t)
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                return None
            time.sleep(2 * (k + 1))


# ---------------------------------------------------------------- Binance notices
def binance_catalog(cid, gaps):
    out, page = [], 1
    while page <= 120:
        d = fetch(f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={cid}&pageNo={page}&pageSize=50",
                  raw=False)
        arts = (((d or {}).get("data") or {}).get("catalogs") or [{}])[0].get("articles") or []
        if not arts:
            if d is None:
                gaps[f"binance:{cid}"] = f"failed at page {page}"
            break
        out += [{"title": a.get("title", ""), "ts": a["releaseDate"] / 1000, "code": a.get("code")} for a in arts]
        if min(a["releaseDate"] for a in arts) / 1000 < ff.START:
            break
        page += 1
    return out


def binance_body(code):
    d = fetch(f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={code}", raw=False)
    return ff.flatten_body((((d or {}).get("data") or {}).get("body"))) if d else None


def binance_events(gaps):
    arts = {}
    for cid in (161, 49, 93):
        for a in binance_catalog(cid, gaps):
            arts.setdefault(a["code"] or a["title"], a)
    arts = sorted(arts.values(), key=lambda a: a["ts"])
    ev, l1f = [], []
    pr = [a for a in arts if re.match(r"^(Updated )?Notice of Removal of Spot Trading Pair", a["title"].strip())]
    fd = [a for a in arts if a["title"].startswith("Binance Futures Will Delist") and "Perpetual" in a["title"]]
    with ThreadPoolExecutor(4) as ex:
        bodies = dict(zip([a["code"] for a in pr + fd], ex.map(lambda a: binance_body(a["code"]), pr + fd)))
    miss = 0
    for a in arts:
        t, ts = a["title"], a["ts"]
        for s in ff.monitoring_symbols(t):
            ev.append({"fam": "mon_tag", "sym": s, "ts": ts, "src": "binance", "title": t[:140]})
        for s in sc.binance_delist_symbols(t):
            l1f.append({"fam": "l1f_ref", "sym": s, "ts": ts, "src": "binance", "title": t[:140]})
    for a in fd:
        body = bodies.get(a["code"])
        miss += body is None
        for s in ff.fut_delist_symbols(a["title"], body or ""):
            ev.append({"fam": "fut_delist", "sym": s, "ts": a["ts"], "src": "binance", "title": a["title"][:140]})
    for a in pr:
        body = bodies.get(a["code"])
        miss += body is None
        for s in ff.pair_removal_symbols(body or ""):
            ev.append({"fam": "pair_rm", "sym": s, "ts": a["ts"], "src": "binance", "title": a["title"][:140]})
    if miss:
        gaps["binance_body_missing"] = miss
    return ev, l1f


# ---------------------------------------------------------------- OKX notices
def okx_events(gaps):
    from research.studies import event_tape as et
    out = []
    for g in et.okx_notices(gaps):
        for cls, syms in nt.classify_title(g["title"]):
            if cls in ("delist", "perp_delist"):
                out += [{"fam": "okx_delist", "sym": s, "ts": g["ts"], "src": "okx", "title": g["title"][:140]} for s in syms]
    return out


# ---------------------------------------------------------------- Wayback collectors (partial coverage, reported)
def cdx(pattern, extra="", limit=50000, collapse="urlkey"):
    u = ("http://web.archive.org/cdx/search/cdx?output=json&matchType=prefix&filter=statuscode:200"
         f"&collapse={collapse}&limit={limit}&fl=timestamp,original&from=2024&url={quote(pattern)}{extra}")
    t = fetch(u, timeout=180, tries=3)
    try:
        return json.loads(t)[1:]
    except Exception:  # noqa: BLE001
        return None


def snap(ts, url, tag=""):
    t = fetch(f"http://web.archive.org/web/{ts}id_/{url}", timeout=60, tries=3, gap=0.2)
    with LOCK:
        FAILS[tag] = FAILS.get(tag, 0) + (t is None)
    return t


def cap_ts(stamp):
    """Wayback capture stamp YYYYMMDDhhmmss -> epoch seconds (UTC)."""
    return datetime.strptime(stamp[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()


def kst(s):
    return datetime.fromisoformat(s).timestamp() if "T" in s else datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc).timestamp() - 9 * 3600


def upbit_events(gaps, stats):
    """Title and time come from the EARLIEST capture of each notice id (titles are edited later: '(Completed)'); an event whose
    posted time is after its capture time is dropped and counted."""
    first, ev = {}, []
    one = cdx("api-manager.upbit.com/api/v1/announcements/") or []
    lists = cdx("api-manager.upbit.com/api/v1/announcements?", "&filter=" + quote("original:.*per_page.*"), limit=6000, collapse="timestamp:8") or []
    stats["upbit_snapshots"] = {"single": len(one), "list": len(lists)}
    jobs = sorted([(a, b) for a, b in one if re.search(r"/announcements/\d+", b)] + lists[:4500])

    def work(j):
        t = snap(j[0], j[1], "upbit")
        try:
            d = json.loads(t)["data"]
        except Exception:  # noqa: BLE001
            return j[0], []
        return j[0], d.get("notices") or ([d] if d.get("title") else [])
    with ThreadPoolExecutor(6) as ex:
        for stamp, notes in ex.map(work, jobs):
            for n in notes:
                if n.get("id") not in first:
                    first[n.get("id")] = (stamp, n)
    stats["upbit_notices"] = len(first)
    late = 0
    for stamp, n in first.values():
        try:
            ts = kst(n.get("first_listed_at") or n["listed_at"])
        except Exception:  # noqa: BLE001
            continue
        if ts > cap_ts(stamp) + 60:
            late += 1
            continue
        cls = ff.kr_class(n.get("title", ""))
        if cls:
            ev += [{"fam": f"upbit_{cls}", "sym": s, "ts": ts, "src": "upbit", "title": n["title"][:140]} for s in ff.kr_symbols(n["title"])]
    stats["upbit_time_after_capture_dropped"] = late
    return ev


def bithumb_events(gaps, stats):
    rows = cdx("feed.bithumb.com/notice/") or []
    ids = {}
    for t, u in rows:
        m = re.search(r"/notice/(\d+)", u)
        if m and m.group(1) not in ids:
            ids[m.group(1)] = (t, u)
    stats["bithumb_notice_pages"] = len(ids)

    def work(j):
        t, u = j
        h = snap(t, u, "bithumb")
        if not h:
            return None
        txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", h))))
        m = re.search(r"^.*공지사항\s+(.+?)\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+공유하기", txt)   # greedy prefix: the LAST 공지사항 before the date
        return (m.group(1), m.group(2), t) if m else None
    ev, parsed, late = [], 0, 0
    stats["bithumb_samples"] = []
    with ThreadPoolExecutor(6) as ex:
        for got in ex.map(work, list(ids.values())):
            if not got:
                continue
            parsed += 1
            title, when, stamp = got
            if len(stats["bithumb_samples"]) < 8:
                stats["bithumb_samples"].append({"title": title[:120], "when": when})
            cls = ff.kr_class(title)
            if cls:
                ts = kst(when)
                if ts > cap_ts(stamp) + 60:
                    late += 1
                    continue
                ev += [{"fam": f"bithumb_{cls}", "sym": s, "ts": ts, "src": "bithumb", "title": title[:140]} for s in ff.kr_symbols(title)]
    stats["bithumb_parsed"] = parsed
    stats["bithumb_time_after_capture_dropped"] = late
    return ev


_DATE = re.compile(r'"(?:publishTime|publish_time|publishedAt|publishDate|datePublished|dateCreated|createdAt|createTime|date)"\s*:\s*"?'
                   r'(\d{13}|\d{10}|\d{4}-\d{2}-\d{2}[T ][0-9:.]+Z?)')


def bybit_events(gaps, stats):
    rows = (cdx("announcements.bybit.com/en/article/", "&filter=" + quote("original:.*[Dd]elist.*")) or []) + \
           (cdx("announcements.bybit.com/article/", "&filter=" + quote("original:.*[Dd]elist.*")) or [])
    uniq = {}
    for t, u in rows:
        m = re.search(r"-((?:blt|art)[0-9a-f]+)/?", u)
        if m and m.group(1) not in uniq:
            uniq[m.group(1)] = (t, u)
    stats["bybit_articles"] = len(uniq)
    stats["bybit_debug"] = []

    def work(j):
        t, u = j
        h = snap(t, u, "bybit")
        if not h:
            return None
        m = re.search(r"<title>(?:Bybit Announcement \| )?(.*?)</title>", h, re.S)
        title = html.unescape(m.group(1)).strip() if m else ""
        d = _DATE.search(h)
        return title, d.group(1) if d else None, h, t

    ev, dated = [], 0
    with ThreadPoolExecutor(6) as ex:
        for got in ex.map(work, list(uniq.values())):
            if not got:
                continue
            title, when, h, stamp = got
            if len(stats["bybit_debug"]) < 6:
                stats["bybit_debug"].append({"title": title[:100], "date": when, "html_dates": re.findall(r"20\d\d-\d\d-\d\d[T ]\d\d:\d\d", h)[:3]})
            cs = ff.bybit_class_symbols(title)
            if not cs or not when:
                continue
            dated += 1
            ts = float(when) / (1000 if len(when) == 13 else 1) if when.isdigit() else datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp()
            if ts > cap_ts(stamp) + 60:
                stats["bybit_time_after_capture_dropped"] = stats.get("bybit_time_after_capture_dropped", 0) + 1
                continue
            ev += [{"fam": "bybit_delist", "sym": s, "ts": ts, "src": "bybit", "title": title[:140]} for s in cs[1]]
    stats["bybit_dated"] = dated
    return ev


# ---------------------------------------------------------------- prices
def _um_month(sym, y, m, interval):
    got = bv.fetch("futures/um", "monthly", "klines", sym, (y, m), interval, bv.parse_kline)
    return None if got is None else {r[0]: (r[1], r[2], r[3], r[4]) for r in got}


@lru_cache(maxsize=24)
def um_rows_1m(sym, y, m):
    return _um_month(sym, y, m, "1m")


@lru_cache(maxsize=900)
def um_rows_5m(sym, y, m):
    return _um_month(sym, y, m, "5m")


def um_bars(sym, t0, t1, interval="1m"):
    """{bar open ts: (o, h, l, c)} of a Binance USDT-M contract over [t0, t1); {} when it has no file, None on a failed download."""
    out = {}
    for y, m in bv.months(t0, t1):
        d = (um_rows_1m if interval == "1m" else um_rows_5m)(sym, y, m)
        if d is None:
            return None
        out.update({t: v for t, v in d.items() if t0 <= t < t1})
    return out


def okx_bars(base, t0, t1):
    out, after = {}, int(t1 * 1000)
    for _ in range(40):
        pace(0.13)
        d = fetch(f"https://www.okx.com/api/v5/market/history-candles?instId={base}-USDT-SWAP&bar=1m&after={after}&limit=100", raw=False)
        if not d or d.get("code") != "0":
            return None if not d else {}
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


def perp_bars(sym, ts, span):
    """1-minute bars for [ts - 1 h, ts + span]: Binance USDT-M (sym, then the 1000 prefix), else OKX swap. Needs a bar before ts.
    Returns (bars, source) or (None, reason) with reason no_perp, price_fetch_failed."""
    t0, t1 = ts - 3600, ts + span
    failed = False
    for cand in (sym, "1000" + sym, "1000000" + sym):
        b = um_bars(cand + "USDT", t0, t1)
        if b is None:
            failed = True
        elif any(t < ts for t in b):
            return b, "binance_um" if cand == sym else "binance_um_prefixed"
    b = okx_bars(sym, t0, t1)
    if b is None:
        failed = True
    elif any(t < ts for t in b):
        return b, "okx"
    return None, "price_fetch_failed" if failed else "no_perp"


def process_symbol(sym, events):
    out = []
    span = max(ff.HOLDS) + max(ff.DELAYS) + 3 * 60 + 600
    for e in events:
        ts = e["ts"]
        bars, src = perp_bars(sym, ts, span)
        row = {**e, "price_src": src, "rules": {}, "dropped": []}
        if bars is None:
            out.append(row)
            continue
        rng = random.Random(f"{ff.SEED}:{e['fam']}:{sym}:{int(ts)}")
        picks = ff.pick_control(rng, sym)
        cb = {}
        for c in picks:
            b = um_bars(c + "USDT", ts - 3600, ts + span, "5m")
            if b:
                cb[c] = b
        for rid, h, d in ff.family_rules(e["fam"]):
            s = ff.short_trade(bars, 60, ts, d, h)
            if not s:
                row["dropped"].append(rid)          # no bar at the entry or the exit (for example the perp was delisted before the exit)
                continue
            cg = ff.control_gross(cb, picks, 300, ts, d, h)
            row["rules"][rid] = [round(s["gross"], 6), None if cg is None else round(cg, 6), round(s["mfe"], 5), round(s["mae"], 5),
                                 s["reason"], s["te"], s["x"]]
        out.append(row)
    return out


# ---------------------------------------------------------------- evaluation
def trades_of(rows, rid, fam, hold):
    out = []
    for r in rows:
        v = r["rules"].get(rid)
        if not v or r.get("overlap_l1f") and fam != "l1f_ref":
            continue
        sim = {"te": v[5], "x": v[6], "gross": v[0], "mfe": v[2], "mae": v[3], "reason": v[4]}
        tr = ff.make_trade(r["sym"], r["ts"], sim, hold, v[1])
        tr["nid"] = f"{r.get('src')}|{int(r['ts'])}|{r.get('title')}"
        out.append(tr)
    return sorted(out, key=lambda t: t["t"])


def notice_level(trades, months):
    """One observation per notice (mean net of its coins): a notice naming many coins is one risk unit in the book."""
    g = {}
    for t in trades:
        g.setdefault(t["nid"], []).append(t["net"])
    return ff.stats([sum(v) / len(v) for v in g.values()], months)


def ctrl_mean(trades):
    v = [t["ctrl_net"] for t in trades if t.get("ctrl_net") is not None]
    return ss.mean(v)


def evaluate_family(fam, rows, cfg=None):
    cfg = cfg or ff.CFG
    table, gate_rows = {}, []
    t0, t1 = ff.BOUNDS["train"]
    train_days = (t1 - t0) / 86400
    train_months = train_days / 30.4375
    for rid, h, d in ff.family_rules(fam):
        tr_all = trades_of(rows, rid, fam, h)
        tr = ss.in_split(tr_all, t0, t1)
        ok, info = ss.gate(tr, {"size": ff.SIZE}, cfg, train_days)
        cm = ctrl_mean(tr)
        nl = notice_level(tr, train_months) if tr else {"n": 0}
        info = dict(info, id=rid, control_mean_train=cm, notice_level_train=nl)
        if ok and cm is not None and (info["train_mean"] or 0) <= cm:
            ok, info["reason"] = False, "train net mean not above the random-control mean"
        if ok and (nl.get("x") or 0) < cfg["gate"]["min_x"]:
            ok, info["reason"] = False, f"notice-level x {nl.get('x')} < {cfg['gate']['min_x']}"
        table[rid] = {"gate": info, "stats_all": ff.stats([t["net"] for t in tr_all], ff.MONTHS),
                      "notice_level_all": notice_level(tr_all, ff.MONTHS) if tr_all else {"n": 0},
                      "stats_by_split": {k: ff.stats([t["net"] for t in ss.in_split(tr_all, *ff.BOUNDS[k])],
                                                     (ff.BOUNDS[k][1] - ff.BOUNDS[k][0]) / 86400 / 30.4375) for k in ff.BOUNDS},
                      "control_mean_all": ctrl_mean(tr_all), "placebo_mean_all": ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in tr_all]),
                      "ok": ok}
        if ok:
            r = {"id": rid, "gate": info, "status": "ok", **ss.evaluate(tr_all, {"size": ff.SIZE}, ff.BOUNDS)}
            va, te = ss.in_split(tr_all, *ff.BOUNDS["validation"]), ss.in_split(tr_all, *ff.BOUNDS["test"])
            cv, ct = ctrl_mean(va), ctrl_mean(te)
            r["extra_criteria"] = {"val_beats_control": (ss.mean([t["net"] for t in va]) or 0) > (cv if cv is not None else 9),
                                   "test_beats_control": (ss.mean([t["net"] for t in te]) or 0) > (ct if ct is not None else 9)}
            gate_rows.append(r)
    return table, gate_rows


def build_events(out_dir):
    gaps, stats = {}, {}
    events, l1f = binance_events(gaps)
    print("binance events", len(events), "l1f", len(l1f), flush=True)
    for name, fn in (("okx", lambda: okx_events(gaps)), ("upbit", lambda: upbit_events(gaps, stats)),
                     ("bithumb", lambda: bithumb_events(gaps, stats)), ("bybit", lambda: bybit_events(gaps, stats))):
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001
            gaps[name] = repr(e)[:200]
            got = []
        print(name, len(got), stats, flush=True)
        events += got
    stats["fetch_failures"] = dict(FAILS)
    events = ff.dedupe([e for e in events if ff.in_window(e["ts"])])
    l1f = ff.dedupe([e for e in l1f if ff.in_window(e["ts"])])
    for e in events:
        e["overlap_l1f"] = ff.overlaps_l1f(e, l1f)
    counts = {}
    for e in events:
        c = counts.setdefault(e["fam"], {"events": 0, "notices": set(), "overlap_l1f": 0, "train": 0, "validation": 0, "test": 0})
        c["events"] += 1
        c["notices"].add((e["src"], int(e["ts"]), e["title"]))
        c["overlap_l1f"] += e["overlap_l1f"]
        c[ff_split(e["ts"])] += 1
    for c in counts.values():
        c["notices"] = len(c["notices"])
    doc = {"events": events, "l1f": l1f, "gaps": gaps, "stats": stats, "counts": counts, "l1f_events": len(l1f),
           "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(out_dir, "events.json"), "w") as f:
        json.dump(doc, f, ensure_ascii=False)
    print(json.dumps({k: v for k, v in doc.items() if k not in ("events", "l1f")}, ensure_ascii=False, default=str)[:4000], flush=True)
    for fam in FAMILIES:
        print("SAMPLE", fam, [(e["sym"], time.strftime("%Y-%m-%d %H:%M", time.gmtime(e["ts"])), e["title"][:70]) for e in events if e["fam"] == fam][:4], flush=True)
    return doc


def ff_split(ts):
    for k, (a, b) in ff.BOUNDS.items():
        if a <= ts < b:
            return k
    return "test"


def main():
    out_dir = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "run"          # events: announcements only, no prices; run: price the frozen events
    frozen = sys.argv[3] if len(sys.argv) > 3 else ""
    os.makedirs(out_dir, exist_ok=True)
    if mode == "events":
        build_events(out_dir)
        return
    t_start = time.time()
    if frozen and os.path.exists(frozen):
        doc = json.load(open(frozen))
        events, l1f, gaps, stats = doc["events"], doc["l1f"], doc["gaps"], doc["stats"]
        with open(os.path.join(out_dir, "events.json"), "w") as f:
            json.dump(doc, f, ensure_ascii=False)
    else:
        doc = build_events(out_dir)
        events, l1f, gaps, stats = doc["events"], doc["l1f"], doc["gaps"], doc["stats"]
    print("events", len(events), "l1f", len(l1f), flush=True)

    allev = events + l1f
    by_sym = {}
    for e in allev:
        by_sym.setdefault(e["sym"], []).append(e)
    rows = []
    with ThreadPoolExecutor(6) as ex:
        for part in ex.map(lambda kv: process_symbol(*kv), sorted(by_sym.items())):
            rows += part
    print("rows", len(rows), "seconds", round(time.time() - t_start), flush=True)
    with gzip.open(os.path.join(out_dir, "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")

    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": round(ff.MONTHS, 2), "gaps": gaps, "archive_stats": stats,
               "event_counts": doc.get("counts"), "families": {}}
    ref_rows = [r for r in rows if r["fam"] == "l1f_ref"]
    ref_tr = trades_of(ref_rows, ff.rule_id("l1f_ref", 14400, 60), "l1f_ref", 14400)
    a, b = ff.START, ff.END
    ref_day = ff.daily(ref_tr, a, b)
    summary["l1f_ref_perp_priced"] = {"events": len(l1f), "priced_trades": len(ref_tr), **ff.stats([t["net"] for t in ref_tr], ff.MONTHS)}
    gate_all, gate_strict = [], []
    for fam in ("l1f_ref",) + FAMILIES:
        fr = [r for r in rows if r["fam"] == fam]
        cov = {"events": len(l1f) if fam == "l1f_ref" else sum(1 for e in events if e["fam"] == fam),
               "overlap_l1f": sum(1 for e in events if e["fam"] == fam and e["overlap_l1f"]),
               "priced_rows": sum(1 for r in fr if r["rules"]), "by_src": {}, "rows_with_dropped_rules": sum(1 for r in fr if r.get("dropped")),
               "dropped_rule_instances": sum(len(r.get("dropped") or []) for r in fr)}
        for r in fr:
            cov["by_src"][r["price_src"]] = cov["by_src"].get(r["price_src"], 0) + 1
        hl = ff.rule_id(fam, 14400, 60)
        htr = trades_of(fr, hl, fam, 14400)
        head = {"rule": hl, **ff.stats([t["net"] for t in htr], ff.MONTHS), "notice_level": notice_level(htr, ff.MONTHS) if htr else {"n": 0},
                "control_mean": ctrl_mean(htr), "placebo_mean": ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in htr]),
                "corr_daily_with_l1f": ff.corr(ff.daily(htr, a, b), ref_day) if fam != "l1f_ref" else 1.0, "x_with_l1f_added": None}
        if fam != "l1f_ref":
            head["x_with_l1f_added"] = round(ff.stats([t["net"] for t in sorted(htr + ref_tr, key=lambda t: t["t"])], ff.MONTHS).get("x", 0), 4)
        table, gate_rows = evaluate_family(fam, fr)
        _, strict_rows = evaluate_family(fam, fr, ff.CFG_STRICT)
        summary["families"][fam] = {"coverage": cov, "headline_4h_1m": head, "rules": table}
        if fam != "l1f_ref":                    # the reference is reported, not judged
            for r in gate_rows:
                r["family"] = fam
            for r in strict_rows:
                r["family"] = fam
            gate_all += gate_rows
            gate_strict += strict_rows
    summary["rules_tested"] = len(FAMILIES) * len(ff.HOLDS) * len(ff.DELAYS)
    for name, rows_, cfg in (("event_gate", gate_all, ff.CFG), ("sweep_strict_gate", gate_strict, ff.CFG_STRICT)):
        fam_info = ss.judge_family(rows_, cfg) if rows_ else {"holm_m": 0}
        summary[name] = {"stage0_survivors": len(rows_), "holm": fam_info, "passed": [r["id"] for r in rows_ if r.get("passed")],
                         "evaluated": [dict(ss.compact(r, r["family"]), criteria=r["criteria"]) for r in rows_]}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in summary.items() if k != "families"}, default=str)[:4000])
    for fam, v in summary["families"].items():
        print(fam, v["coverage"], v["headline_4h_1m"], flush=True)


if __name__ == "__main__":
    main()
