"""News-analyst training round 2: IO and orchestration (protocol_r2_20261126.md). GitHub Actions only (workflow news_train_r2.yml).

    run_r2.py gdelt_probe  <out>
    run_r2.py gdelt_pull   <out> <start_day> <end_day>
    run_r2.py crypto_build <parts_dir> <out> <r1_data_dir>
    run_r2.py stock_build  <out> <shard> <shards> <r1_data_dir>
    run_r2.py publish      <parts_dir> <data_dir>
    run_r2.py eval         <out> <data_dir> <version> <set> <shard> <shards> [deadline_min]
    run_r2.py merge        <parts_dir> <data_dir> <out>
    run_r2.py select       <data_dir> <out>
    run_r2.py analyze      <data_dir> <out> <version>
    run_r2.py sealed_crypto <out> <data_dir>
    run_r2.py fwd          <out> <data_dir>

Data layout on branch data/news-train-r2: dev.jsonl.gz (items with labels), sealed_crypto_items.jsonl.gz, calls/<v>.jsonl.gz,
evals/<v>_<set>.json, calib.json, selection.json, sealed_r2/crypto_result.json, fwd/{items,calls}.jsonl.gz, fwd/bars*.json,
fwd/progress.json (counts only), fwd/result.json (written once).
"""
import glob
import gzip
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402

P = R.load_params()
UA = {"User-Agent": "Mozilla/5.0 (TradeLab research)"}


def log(*a):
    print(*a, flush=True)


def wjsonl(path, rows, gz=True):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with (gzip.open if gz else open)(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")


def rjsonl(path):
    if not os.path.exists(path):
        return []
    with (gzip.open if path.endswith(".gz") else open)(path, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def http(url, timeout=60, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                return None
            time.sleep(2 * (k + 1))


# ================================================================== GDELT
def pull_stamp(stamp):
    """-> (rows of coin headlines, bytes, parsed lines) of one GKG file, or None when unreachable."""
    raw = http(R.gkg_url(stamp))
    if raw is None:
        return None
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        txt = z.read(z.namelist()[0]).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    t = R.stamp_ts(stamp)
    rows, n = [], 0
    for line in txt.split("\n"):
        r = R.parse_gkg_line(line)
        if not r:
            continue
        n += 1
        coin = R.coin_of(r["title"], r["themes"], P)
        if coin and not R.is_spam(r["title"], r["domain"], P):
            rows.append({"t": t, "coin": coin, "title": r["title"], "domain": r["domain"], "url": r["url"]})
    return rows, len(raw), n


def days_between(a, b):
    out, t = [], L.day_ts(a)
    while t < L.day_ts(b):
        out.append(L.day_of(t))
        t += 86400
    return out


def gdelt_probe(out):
    t0 = time.time()
    stamps = R.gkg_stamps("2026-03-01", 1)
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(pull_stamp, stamps))
    ok = [r for r in res if r]
    rep = {"files": len(stamps), "ok": len(ok), "seconds": time.time() - t0, "bytes": sum(r[1] for r in ok),
           "parsed_lines": sum(r[2] for r in ok), "rows_all96": sum(len(r[0]) for r in ok)}
    s4 = [r for i, r in enumerate(res) if r and i % 4 == 0]
    rep["rows_stride4"] = sum(len(r[0]) for r in s4)
    allrows = [x for r in ok for x in r[0]]
    rep["unique_all96"] = len(R.dedupe_rows(allrows, P))
    rep["unique_stride4"] = len(R.dedupe_rows([x for r in s4 for x in r[0]], P))
    rep["by_coin"] = {}
    for x in R.dedupe_rows(allrows, P):
        rep["by_coin"][x["coin"]] = rep["by_coin"].get(x["coin"], 0) + 1
    rep["sample"] = [x["title"] for x in allrows[:15]]
    for tag, st in (("2025-12-01", "20251201120000"), ("2026-08-01", "20260801120000"), ("2026-11-24", "20261124120000")):
        r = pull_stamp(st)
        rep["reach_" + tag] = None if r is None else {"rows": len(r[0]), "bytes": r[1]}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "gdelt_probe.json"), "w"), indent=1)
    log(json.dumps(rep, indent=1))


def gdelt_pull(out, start, end):
    rows, failed, files, t0 = [], 0, 0, time.time()
    for day in days_between(start, end):
        with ThreadPoolExecutor(12) as ex:
            res = list(ex.map(pull_stamp, R.gkg_stamps(day, P["gdelt"]["stride"])))
        for r in res:
            files += 1
            if r is None:
                failed += 1
            else:
                rows += r[0]
        log(day, "rows", len(rows), "failed files", failed, f"{time.time() - t0:.0f}s")
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, f"rows_{start}_{end}.jsonl.gz"), rows)
    json.dump({"start": start, "end": end, "files": files, "failed": failed, "rows": len(rows)}, open(os.path.join(out, f"pull_{start}_{end}.json"), "w"))


# ================================================================== crypto build
def coin_bars(coin, t0, t1):
    """1-minute (open_ts, high, low, close) of COINUSDT: futures/um monthly files, then spot; the current month has daily files only."""
    from research.studies import binance_vision as bv
    for mk in ("futures/um", "spot"):
        rows, failed = bv.klines(coin + "USDT", t0, t1, "1m", market=mk)
        if rows:
            return [(r[0], r[2], r[3], r[4]) for r in rows], mk, failed
    return None, None, None


def crypto_build(parts, out, r1_data):
    rows = []
    for p in sorted(glob.glob(os.path.join(parts, "rows_*.jsonl.gz"))):
        rows += rjsonl(p)
    stats = {"raw_rows": len(rows)}
    rows = R.cap_per_coin_day(R.dedupe_rows(rows, P), P)
    stats["after_dedupe_cap"] = len(rows)
    by = {"train": [], "validation": [], "sealed_hist": []}
    for r in rows:
        sp = R.split_r2(r["t"], P)
        if sp in by:
            by[sp].append(r)
    stats["by_split_pool"] = {k: len(v) for k, v in by.items()}
    cap = {"train": P["sample"]["crypto_train"], "validation": P["sample"]["crypto_validation"], "sealed_hist": P["sample"]["crypto_sealed_hist"]}
    items = []
    for sp, rs in by.items():
        rs = sorted(rs, key=lambda r: L.unit(f"{P['seed']}:{r['coin']}:{r['t']}:{r['title'][:40]}"))[:cap[sp]]
        for r in rs:
            items.append({"key": f"gd:{r['coin']}:{r['t']}:{int(L.unit(r['title']) * 1e8)}", "market": "crypto", "src": r["domain"], "cls": None,
                          "t_pub": r["t"], "sym": r["coin"], "split": sp, "items": [], "text": R.redact_title(r["title"], r["coin"], P),
                          "text_named": r["title"], "descr": "Instrument: a crypto token with a perpetual contract."})
    stats["picked"] = {sp: sum(1 for i in items if i["split"] == sp) for sp in by}
    dev, sealed = [i for i in items if i["split"] != "sealed_hist"], [i for i in items if i["split"] == "sealed_hist"]
    t0, t1 = L.day_ts("2025-11-30"), L.day_ts(P["dates"]["dev_end"]) + 86400 * 2
    drops, labelled = {}, []
    for coin in sorted({i["sym"] for i in dev}):
        bars, src, failed = coin_bars(coin, t0, t1)
        mine = [i for i in dev if i["sym"] == coin]
        if not bars:
            drops["no_perp_or_spot_bars"] = drops.get("no_perp_or_spot_bars", 0) + len(mine)
            continue
        log(coin, "bars", len(bars), src, "failed", failed, "items", len(mine))
        for it in mine:
            R.assert_dev(it["t_pub"], P)
            lab = R.crypto_label_r2(bars, it["t_pub"], P)
            if not lab:
                drops["no_entry_bar"] = drops.get("no_entry_bar", 0) + 1
                continue
            labelled.append(dict(it, price_src=src, labels={R.LAB: lab}))
    stats["drops"], stats["dev_labelled"], stats["sealed_items"] = drops, len(labelled), len(sealed)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "crypto_dev.jsonl.gz"), labelled)
    wjsonl(os.path.join(out, "crypto_sealed_items.jsonl.gz"), sealed)
    json.dump(stats, open(os.path.join(out, "crypto_report.json"), "w"), indent=1)
    log(json.dumps(stats))


# ================================================================== stock (SEC 8-K listing, 1-hour labels)
def yahoo_intraday(sym, p1, p2, interval="1h", tries=4):
    from core import factory_us_pit as fu
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1={int(p1)}&period2={int(p2)}"
           f"&interval={interval}&includePrePost=false")
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                d = json.loads(r.read())["chart"]
            if d.get("error") or not d.get("result"):
                return []
            return fu.parse_chart(d["result"][0])[0]
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                log("  intraday failed", sym, interval, e)
                return []
            time.sleep(2 * (k + 1))


def sp_candidates(t_lo, t_hi, shard=0, shards=1):
    """S&P 500 members' 8-K filings with a stock_items code accepted in [t_lo, t_hi), true UTC acceptance time."""
    from core import news_backtest as nb, keyperson as kp, factory_us_pit as fu
    from research.studies import keyperson as kpr
    spells = kpr.load_spells()
    day_lo = L.day_of(t_lo)
    tick = nb.sec_company_tickers()
    names = sorted(s for s, sp in spells.items() if any(b is None or b >= day_lo for a, b in sp))
    ciks = {s: tick[s] for s in names if s in tick}
    keep, _ = fu.one_per_issuer(ciks, {s: sum(1 for _ in spells[s]) for s in ciks})
    allowed = set(P["stock_items"])
    cand, failed = [], 0
    for n, s in enumerate(sorted(keep)):
        if n % shards != shard:
            continue
        try:
            filings, issuer = kp.sec_filings_docs(ciks[s], kpr.sec_get_json, since=day_lo)
        except Exception as e:  # noqa: BLE001
            failed += 1
            log("  sec failed", s, e)
            continue
        try:
            sic = kpr.sec_get_json(f"https://data.sec.gov/submissions/CIK{ciks[s]:010d}.json").get("sicDescription") or "unknown"
        except Exception:  # noqa: BLE001
            sic = "unknown"
        for x in filings:
            ts = R.fix_ts(x["ts"])
            if x["form"] != "8-K" or not x["doc"] or not (t_lo <= ts < t_hi):
                continue
            if x["items"] and not (set(x["items"]) & allowed):
                continue
            if not any(a <= fu.ny_date(ts) and (b is None or fu.ny_date(ts) < b) for a, b in spells.get(s, [])):
                continue
            cand.append({"sym": s, "cik": ciks[s], "ts": ts, "acc": x["accession"], "doc": x["doc"], "items": x["items"], "issuer": issuer, "sic": sic})
        if n % 100 == 0:
            log(f"  filings {n}/{len(keep)} candidates {len(cand)} failed {failed}")
    return cand, failed


def stock_item(c, cache):
    from research.news_train import run as R1
    key = "sec:" + c["acc"]
    if key in cache:
        text, kind = cache[key]["text"], cache[key].get("text_kind", "main")
    else:
        text, kind, _ = R1.filing_text(c)
    if len(text) < 80:
        return None
    return {"key": key, "market": "stock", "src": "sec_8k", "t_pub": c["ts"], "sym": c["sym"], "items": c["items"], "text": text, "text_kind": kind,
            "descr": f"Issuer: a large US-listed company (sector: {c['sic']})."}


def r1_cache(r1_data):
    return {i["key"]: i for i in rjsonl(os.path.join(r1_data, "dev_items.jsonl.gz")) if i.get("market") == "stock"}, \
           {i["key"] for i in rjsonl(os.path.join(r1_data, "dev_items.jsonl.gz")) if i.get("market") == "stock" and i.get("split") in ("train", "validation")}


def stock_build(out, shard, shards, r1_data):
    cache, r1_keys = r1_cache(r1_data)
    t_lo, t_hi = L.day_ts(P["dates"]["clean_start"]), L.day_ts(P["dates"]["dev_end"])
    cand, failed = sp_candidates(t_lo, t_hi, shard, shards)
    stats = {"candidates": len(cand), "sec_failed": failed}
    by = {"train": [], "validation": []}
    for c in cand:
        sp = R.split_r2(c["ts"], P)
        if sp == "validation" and "sec:" + c["acc"] in r1_keys:
            stats["r1_scored_excluded"] = stats.get("r1_scored_excluded", 0) + 1       # validation = items no round-1 version scored
            continue
        if sp in by:
            by[sp].append(c)
    items, drops = [], {}
    for sp, cs in by.items():
        share = int(1.4 * P["sample"]["stock_" + sp] / shards) + 1
        for c in sorted(cs, key=lambda c: L.unit(f"{P['seed']}:{c['acc']}"))[:share]:
            try:
                it = stock_item(c, cache)
            except Exception as e:  # noqa: BLE001
                drops["text_failed"] = drops.get("text_failed", 0) + 1
                log("  text failed", c["acc"], e)
                continue
            if not it:
                drops["short_text"] = drops.get("short_text", 0) + 1
                continue
            it["split"] = sp
            it["sic"] = c["sic"]
            items.append(it)
    p1, p2 = L.day_ts("2025-11-10"), L.day_ts(P["dates"]["dev_end"]) + 6 * 86400
    bars_by, labelled = {}, []
    for it in items:
        R.assert_dev(it["t_pub"], P)
        if it["sym"] not in bars_by:
            bars_by[it["sym"]] = yahoo_intraday(it["sym"], p1, p2, "1h")
        bars = bars_by[it["sym"]]
        if not bars:
            drops["no_bars"] = drops.get("no_bars", 0) + 1
            continue
        lab, why = R.stock_label_1h(bars, it["t_pub"], P["entry"]["lag_s"], P)
        if not lab:
            drops[why] = drops.get(why, 0) + 1
            continue
        labelled.append(dict(it, labels={R.LAB: lab}))
    stats["items"], stats["labelled"], stats["drops"] = len(items), len(labelled), drops
    stats["in_session_share"] = (sum(1 for i in labelled if i["labels"][R.LAB]["in_session"]) / len(labelled)) if labelled else None
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, f"stock_dev_{shard}.jsonl.gz"), labelled)
    json.dump(stats, open(os.path.join(out, f"stock_report_{shard}.json"), "w"), indent=1)
    log(json.dumps(stats))


def publish(parts, data):
    os.makedirs(data, exist_ok=True)
    rows = []
    for p in sorted(glob.glob(os.path.join(parts, "stock_dev_*.jsonl.gz"))) + sorted(glob.glob(os.path.join(parts, "crypto_dev.jsonl.gz"))):
        rows += rjsonl(p)
    seen, out = set(), []
    for r in rows:
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        out.append(r)
    # global trim to the registered sample sizes, by sha order (stock shards over-select by 1.4x)
    final = []
    for mk in ("stock", "crypto"):
        for sp in ("train", "validation"):
            pool = sorted((r for r in out if r["market"] == mk and r["split"] == sp), key=lambda r: L.unit(f"{P['seed']}:{r['key']}"))
            final += pool[:P["sample"][f"{mk}_{sp}"]]
    for r in final:
        R.assert_dev(r["t_pub"], P)
    wjsonl(os.path.join(data, "dev.jsonl.gz"), final)
    for name in ("crypto_sealed_items.jsonl.gz",):
        if os.path.exists(os.path.join(parts, name)):
            wjsonl(os.path.join(data, name), rjsonl(os.path.join(parts, name)))
    rep = {"stock": [json.load(open(p)) for p in sorted(glob.glob(os.path.join(parts, "stock_report_*.json")))],
           "crypto": json.load(open(os.path.join(parts, "crypto_report.json"))) if os.path.exists(os.path.join(parts, "crypto_report.json")) else None,
           "final": {f"{mk}_{sp}": sum(1 for r in final if r["market"] == mk and r["split"] == sp) for mk in ("stock", "crypto") for sp in ("train", "validation")}}
    json.dump(rep, open(os.path.join(data, "build_report.json"), "w"), indent=1)
    log(json.dumps(rep["final"]))


def load_dev(data):
    return R_assert(rjsonl(os.path.join(data, "dev.jsonl.gz")))


def R_assert(rows):
    for r in rows:
        R.assert_dev(r["t_pub"], P)
    return rows


# ================================================================== eval
def load_calls(data, vid):
    return {r["key"]: r for r in rjsonl(os.path.join(data, "calls", f"{vid}.jsonl.gz"))}


def decide(it, version, system, index):
    from core import ai_news
    lab = it["labels"].get(R.LAB)
    analogs = index.query(it, it["t_pub"], P["analogs"]["k"]) if (index and version.get("analogs")) else None
    user = R.render_user2(it, lab, version, analogs, P)
    txt, served = "", ""
    for _ in range(3):
        txt, served = ai_news.chat(system, user, timeout=150)
        if txt:
            break
        time.sleep(3)
    pr = R.parse_reply2(txt, it["market"])
    return dict(pr, key=it["key"], version=version["id"], prompt_sha=version["sha256"], reply=txt[:700], served=served[:80])


def run_eval(out, data, vid, which, shard, shards, deadline_min=300):
    from core import ai_news
    version = next(v for v in R.versions_registry()["versions"] if v["id"] == vid)
    system = open(R.check_version(version)).read()
    dev = load_dev(data)
    index = L.AnalogIndex(dev, lag=R.LAB) if version.get("analogs") else None
    target = sorted((i for i in dev if i["split"] == which), key=lambda i: i["key"])[shard::shards]
    cache = load_calls(data, vid)
    todo = [i for i in target if not (i["key"] in cache and cache[i["key"]].get("prompt_sha") == version["sha256"] and cache[i["key"]].get("ok"))]
    log(f"{vid} {which} shard {shard}/{shards}: target {len(target)} to call {len(todo)}")
    t_end = time.time() + deadline_min * 60
    res = []

    def one(it):
        return None if time.time() > t_end else decide(it, version, system, index)

    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        for k, r in enumerate(ex.map(one, todo)):
            if r:
                res.append(r)
            if k % 50 == 0:
                log(f"  {k + 1}/{len(todo)} failed {sum(1 for x in res if not x['ok'])} spend {ai_news.spend()}")
    done = {r["key"] for r in res}
    wjsonl(os.path.join(out, f"part_{vid}_{which}_{shard}.jsonl"), res + [cache[i["key"]] for i in target if i["key"] in cache and i["key"] not in done], gz=False)
    json.dump(ai_news.spend(), open(os.path.join(out, f"spend_{vid}_{which}_{shard}.json"), "w"))


def merge(parts, data, out):
    dev = load_dev(data)
    reg = {v["id"]: v for v in R.versions_registry()["versions"]}
    by_v = {}
    for p in glob.glob(os.path.join(parts, "part_*.jsonl")):
        vid = os.path.basename(p).split("_")[1]
        for r in rjsonl(p):
            by_v.setdefault(vid, {})[r["key"]] = r
    calib = json.load(open(os.path.join(data, "calib.json"))) if os.path.exists(os.path.join(data, "calib.json")) else {}
    os.makedirs(os.path.join(out, "calls"), exist_ok=True)
    os.makedirs(os.path.join(out, "evals"), exist_ok=True)
    for vid, calls in by_v.items():
        old = load_calls(data, vid)
        old.update(calls)
        wjsonl(os.path.join(out, "calls", f"{vid}.jsonl.gz"), list(old.values()))
        ver = reg[vid]
        decs = {k: v for k, v in old.items() if v.get("prompt_sha") == ver["sha256"]}
        train = [i for i in dev if i["split"] == "train"]
        if ver.get("calib"):                                 # theta is fitted on TRAIN only and applied unchanged to validation
            th = {mk: {h: R.fit_theta(train, decs, mk, h, P) for h in R.holds(mk)} for mk in ("stock", "crypto")}
            if sum(1 for i in train if i["key"] in decs) > 0:
                calib[vid] = th
        theta = calib.get(vid)
        for which in ("train", "validation"):
            rows = [i for i in dev if i["split"] == which]
            res = {"version": vid, "set": which, "sha256": ver["sha256"], "theta": theta,
                   "failed_replies": sum(1 for i in rows if i["key"] in decs and not decs[i["key"]].get("ok")),
                   "missing_replies": sum(1 for i in rows if i["key"] not in decs),
                   "cells": R.score_set(rows, decs, ver, theta, P)}
            json.dump(res, open(os.path.join(out, "evals", f"{vid}_{which}.json"), "w"), indent=1, default=str)
            for c in res["cells"]:
                log(vid, which, c["market"], c["hold"], "offered", c["n_offered"], "traded", c["n_traded"], "score", c.get("score_per_offered"),
                    "per trade", c.get("mean_per_trade"), "p_rnd", (c.get("vs_random") or {}).get("p"), "p_kw", (c.get("vs_keyword") or {}).get("p"))
    json.dump(calib, open(os.path.join(out, "calib.json"), "w"), indent=1)


def select(data, out):
    """Selection rule of the round-2 addendum, on clean validation only."""
    cells = {}
    for p in glob.glob(os.path.join(data, "evals", "*_validation.json")):
        e = json.load(open(p))
        cells[e["version"]] = {mk: next((c for c in e["cells"] if c["market"] == mk and c["hold"] == P["primary"][mk]), None) for mk in ("stock", "crypto")}
    lock = R.select_lock(cells, P)
    rep = {"lock": lock, "k_versions": len(R.versions_registry()["versions"]),
           "validation_primary": {v: {mk: ({k: (c or {}).get(k) for k in ("n_offered", "n_traded", "score_per_offered", "mean_per_trade")}) for mk, c in d.items()} for v, d in cells.items()}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "selection.json"), "w"), indent=1)
    log(json.dumps(rep, indent=1))


def analyze(data, out, vid):
    """Error analysis on TRAIN only: outcome groups with and without the analyst."""
    dev = [i for i in load_dev(data) if i["split"] == "train"]
    decs = load_calls(data, vid)
    calib = json.load(open(os.path.join(data, "calib.json"))) if os.path.exists(os.path.join(data, "calib.json")) else {}
    ver = next(v for v in R.versions_registry()["versions"] if v["id"] == vid)
    th = calib.get(vid)
    groups = {}
    for it in dev:
        mk = it["market"]
        lab = it["labels"][R.LAB]
        dec = R.effective(decs.get(it["key"]), (th or {}).get(mk), ver.get("calib"))
        for h in R.holds(mk):
            g = lab["gross"].get(h)
            if g is None:
                continue
            side = L.trade_side(dec, h)
            for gname in (R.item_group(it), "flow:" + str((decs.get(it["key"]) or {}).get("flow") or "-"),
                          "pre:" + ("big" if abs(lab.get("pre_move") if mk == "stock" else (lab.get("pre_1h") or 0)) > 0.01 else "small")
                          if mk == "stock" or lab.get("pre_1h") is not None else "pre:na"):
                s = groups.setdefault((mk, h, gname), {"n": 0, "gross": 0.0, "traded": 0, "net": 0.0, "wrong_conf70": 0})
                s["n"] += 1
                s["gross"] += g
                if side:
                    s["traded"] += 1
                    s["net"] += L.net_pnl(side, g, mk, P)
                    if side * g < 0 and (dec.get("conf") or 0) >= 70:
                        s["wrong_conf70"] += 1
    rows = [{"market": k[0], "hold": k[1], "group": k[2], "n": v["n"], "mean_gross": v["gross"] / v["n"], "traded": v["traded"],
             "net_sum": v["net"], "net_per_trade": (v["net"] / v["traded"]) if v["traded"] else None, "wrong_conf70": v["wrong_conf70"]}
            for k, v in sorted(groups.items()) if v["n"] >= 15]
    os.makedirs(out, exist_ok=True)
    json.dump(rows, open(os.path.join(out, f"analysis_{vid}.json"), "w"), indent=1)
    for r in rows:
        log(r)


# ================================================================== sealed crypto (GDELT 2026-08-01..2026-11-26), one shot
def score_sealed(rows, decs, ver, theta, k_family, extra_family=0):
    res = {"cells": R.score_set(rows, decs, ver, theta, P)}
    m_total = P["done"]["baselines"] * (k_family + extra_family)
    res["m_total"] = m_total
    return res, m_total


def done_checks(cell, m_total):
    if not cell.get("vs_random"):
        return {}, "unread (no cell)"
    ps = {"random": cell["vs_random"]["p"], "keyword": cell["vs_keyword"]["p"], "abstain": cell["vs_abstain"]["p"]}
    adj = L.holm_adjust(ps, m_total)
    chk = {"traded_ge_min": cell["n_traded"] >= P["done"]["min_traded"], "mean_per_trade_positive": (cell.get("mean_per_trade") or 0) > 0,
           "beats_random_holm": adj["random"] < P["bootstrap"]["alpha"] and cell["vs_random"]["mean"] > 0,
           "beats_keyword_holm": adj["keyword"] < P["bootstrap"]["alpha"] and cell["vs_keyword"]["mean"] > 0,
           "positive_at_2x": (cell.get("mean_per_trade_2x") or 0) > 0}
    verdict = "unread (fewer than min traded)" if not chk["traded_ge_min"] else ("done condition met" if all(chk.values()) else "not met")
    return {"holm_adjusted": adj, "checks": chk}, verdict


def decide_all(rows, ver, system, index, parallel_label=""):
    from core import ai_news
    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        return list(ex.map(lambda it: decide(it, ver, system, index), rows))


def sealed_crypto(out, data):
    from core import ai_news
    if os.path.exists(os.path.join(data, "sealed_r2", "crypto_result.json")):
        raise SystemExit("crypto sealed set already opened: refusing a second run")
    lock = json.load(open(os.path.join(R.HERE, "LOCK_R2.json")))["crypto"]
    ver = next(v for v in R.versions_registry()["versions"] if v["id"] == lock["version"])
    assert ver["sha256"] == lock["prompt_sha256"], "LOCK_R2.json does not match the registry"
    system = open(R.check_version(ver)).read()
    theta = (json.load(open(os.path.join(data, "calib.json"))).get(ver["id"]) if ver.get("calib") else None)
    dev = load_dev(data)
    index = L.AnalogIndex(dev, lag=R.LAB) if ver.get("analogs") else None
    items = [i for i in rjsonl(os.path.join(data, "crypto_sealed_items.jsonl.gz")) if R.split_r2(i["t_pub"], P) == "sealed_hist"]
    t0, t1 = L.day_ts(P["dates"]["sealed_hist_from"]) - 86400, L.day_ts(P["dates"]["fwd_from"]) + 2 * 86400
    bars_by, rows, drops = {}, [], {}
    for it in items:
        if it["sym"] not in bars_by:
            bars_by[it["sym"]] = coin_bars(it["sym"], t0, t1)[0]
        bars = bars_by[it["sym"]]
        lab = R.crypto_label_r2(bars, it["t_pub"], P) if bars else None
        if not lab:
            drops["no_label"] = drops.get("no_label", 0) + 1
            continue
        rows.append(dict(it, labels={R.LAB: lab}))
    log("sealed crypto labelled", len(rows), drops)
    calls = decide_all(rows, ver, system, index)
    decs = {c["key"]: c for c in calls}
    k = len(R.versions_registry()["versions"])
    res, m_total = score_sealed(rows, decs, ver, theta, k)
    prim = next(c for c in res["cells"] if c["market"] == "crypto" and c["hold"] == P["primary"]["crypto"])
    extra, verdict = done_checks(prim, m_total)
    res.update(extra, version=ver["id"], k_versions=k, drops=drops, verdict=verdict, theta=theta, spend=ai_news.spend(),
               failed_replies=sum(1 for c in calls if not c["ok"]))
    os.makedirs(os.path.join(out, "sealed_r2"), exist_ok=True)
    json.dump(res, open(os.path.join(out, "sealed_r2", "crypto_result.json"), "w"), indent=1, default=str)
    wjsonl(os.path.join(out, "sealed_r2", "crypto_calls.jsonl.gz"), calls)
    log(json.dumps({k2: v for k2, v in res.items() if k2 != "cells"}, default=str))


# ================================================================== forward stock set (scheduled; decisions now, outcomes once)
def merge_bars(old, new):
    d = {b["t"]: b for b in old}
    d.update({b["t"]: b for b in new})
    return [d[t] for t in sorted(d)]


def fwd(out, data):
    from core import ai_news
    now = int(time.time())
    fd = os.path.join(data, "fwd")
    os.makedirs(fd, exist_ok=True)
    t_lo = L.day_ts(P["dates"]["fwd_from"])
    items = rjsonl(os.path.join(fd, "items.jsonl.gz"))
    have = {i["key"] for i in items}
    cand, failed = sp_candidates(t_lo, now)
    new = []
    for c in cand:
        if "sec:" + c["acc"] in have:
            continue
        try:
            it = stock_item(c, {})
        except Exception as e:  # noqa: BLE001
            log("  text failed", c["acc"], e)
            continue
        if it:
            it["split"] = "fwd"
            new.append(it)
    items += new
    log("fwd candidates", len(cand), "new items", len(new), "total", len(items), "sec failed", failed)
    bars1h = json.load(open(os.path.join(fd, "bars1h.json"))) if os.path.exists(os.path.join(fd, "bars1h.json")) else {}
    bars5m = json.load(open(os.path.join(fd, "bars5m.json"))) if os.path.exists(os.path.join(fd, "bars5m.json")) else {}
    for sym in sorted({i["sym"] for i in items}):          # snapshot before the 5-minute window (about 60 days) rolls off
        bars1h[sym] = merge_bars(bars1h.get(sym, []), yahoo_intraday(sym, t_lo - 10 * 86400, now + 86400, "1h"))
        bars5m[sym] = merge_bars(bars5m.get(sym, []), yahoo_intraday(sym, max(t_lo - 86400, now - 58 * 86400), now + 86400, "5m"))
    lockf = json.load(open(os.path.join(R.HERE, "LOCK_R2.json"))).get("stock") if os.path.exists(os.path.join(R.HERE, "LOCK_R2.json")) else None
    calls = {r["key"]: r for r in rjsonl(os.path.join(fd, "calls.jsonl.gz"))}
    prog = {"utc": now, "items": len(items), "locked": bool(lockf)}
    result_exists = os.path.exists(os.path.join(fd, "result.json"))
    if lockf and not result_exists:
        ver = next(v for v in R.versions_registry()["versions"] if v["id"] == lockf["version"])
        assert ver["sha256"] == lockf["prompt_sha256"], "LOCK_R2.json does not match the registry"
        system = open(R.check_version(ver)).read()
        theta = (json.load(open(os.path.join(data, "calib.json"))).get(ver["id"], {}).get("stock") if ver.get("calib") else None)
        dev = load_dev(data)
        index = L.AnalogIndex(dev, lag=R.LAB) if ver.get("analogs") else None
        todo = [i for i in items if i["key"] not in calls]
        # an item needs a label dict only for the analog-free renderer's pre-entry block: built from bars known at entry
        ready = []
        for it in todo:
            lab, _ = R.stock_label_1h(bars1h.get(it["sym"]) or [], it["t_pub"], P["entry"]["lag_s"], P)
            if lab:                                          # only the pre-entry fields are shown, never gross
                ready.append(dict(it, labels={R.LAB: lab}))
        for c in decide_all(ready, ver, system, index):
            calls[c["key"]] = c
        trig = R.fwd_trigger(items, calls, bars1h, now, P, ver, {"1h": (theta or {}).get("1h"), "eod": (theta or {}).get("eod")})
        prog.update(trig, version=ver["id"], decisions=len(calls))
        if trig["fire"]:
            rows = []
            for it in items:
                lab, _ = R.stock_label_1h(bars1h.get(it["sym"]) or [], it["t_pub"], P["entry"]["lag_s"], P)
                if lab and lab["exit_ts"]["eod"] <= now:
                    rows.append(dict(it, labels={R.LAB: lab}))
            res, m_total = score_sealed(rows, calls, ver, {"stock": theta}, len(R.versions_registry()["versions"]), P["done"]["r1_family_stock"])
            prim = next(c for c in res["cells"] if c["market"] == "stock" and c["hold"] == P["primary"]["stock"])
            extra, verdict = done_checks(prim, m_total)
            res.update(extra, version=ver["id"], verdict=verdict, items_scored=len(rows), opened_utc=now, spend=ai_news.spend())
            os.makedirs(os.path.join(out, "fwd"), exist_ok=True)
            json.dump(res, open(os.path.join(out, "fwd", "result.json"), "w"), indent=1, default=str)
            prog["fired"] = True
    os.makedirs(os.path.join(out, "fwd"), exist_ok=True)
    wjsonl(os.path.join(out, "fwd", "items.jsonl.gz"), items)
    wjsonl(os.path.join(out, "fwd", "calls.jsonl.gz"), list(calls.values()))
    json.dump(bars1h, open(os.path.join(out, "fwd", "bars1h.json"), "w"))
    json.dump(bars5m, open(os.path.join(out, "fwd", "bars5m.json"), "w"))
    json.dump(prog, open(os.path.join(out, "fwd", "progress.json"), "w"), indent=1)
    log(json.dumps(prog))


def main():
    a = sys.argv
    mode = a[1]
    if mode == "gdelt_probe":
        gdelt_probe(a[2])
    elif mode == "gdelt_pull":
        gdelt_pull(a[2], a[3], a[4])
    elif mode == "crypto_build":
        crypto_build(a[2], a[3], a[4])
    elif mode == "stock_build":
        stock_build(a[2], int(a[3]), int(a[4]), a[5])
    elif mode == "publish":
        publish(a[2], a[3])
    elif mode == "eval":
        run_eval(a[2], a[3], a[4], a[5], int(a[6]), int(a[7]), int(a[8]) if len(a) > 8 else 300)
    elif mode == "merge":
        merge(a[2], a[3], a[4])
    elif mode == "select":
        select(a[2], a[3])
    elif mode == "analyze":
        analyze(a[2], a[3], a[4])
    elif mode == "sealed_crypto":
        sealed_crypto(a[2], a[3])
    elif mode == "fwd":
        fwd(a[2], a[3])
    else:
        raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
