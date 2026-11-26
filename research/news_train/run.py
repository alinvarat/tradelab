"""News-analyst training loop: IO and orchestration (protocol.md). GitHub Actions only (workflow news_train.yml).

    python research/news_train/run.py build   <out> stock|crypto
    python research/news_train/run.py publish <parts_dir> <data_dir>        (merge build parts into the data layout)
    python research/news_train/run.py leak    <out>
    python research/news_train/run.py eval    <out> <data_dir> <version> <set> <shard> <shards> [deadline_min]
    python research/news_train/run.py merge   <parts_dir> <data_dir> <out>
    python research/news_train/run.py sealed  <out> <data_dir>

Data layout on branch data/news-train: dev_items.jsonl.gz, dev_labels.jsonl.gz, sealed_items.jsonl.gz,
calls/<version>.jsonl.gz, evals/<version>_<set>.json, sealed/result.json.
"""
import calendar
import glob
import gzip
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logic as L  # noqa: E402

P = L.load_params()
UA = {"User-Agent": "Mozilla/5.0 (TradeLab research)"}


def log(*a):
    print(*a, flush=True)


def wjsonl(path, rows, gz=True):
    op = gzip.open if gz else open
    with op(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n")


def rjsonl(path):
    if not os.path.exists(path):
        return []
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


# ================================================================== build: stock
def stock_items():
    from core import ai_news, keyperson as kp, news_backtest as nb, factory_us_pit as fu  # noqa: F401
    from research.studies import keyperson as kpr
    spells = kpr.load_spells()
    t_lo, t_hi = L.day_ts(P["dates"]["dev_start"]), L.day_ts(P["dates"]["sealed_stock_to"])
    day_lo = P["dates"]["dev_start"]
    tick = nb.sec_company_tickers()
    names = sorted(s for s, sp in spells.items() if any(b is None or b >= day_lo for a, b in sp))
    ciks = {s: tick[s] for s in names if s in tick}
    keep, _ = fu.one_per_issuer(ciks, {s: sum(1 for _ in spells[s]) for s in ciks})
    allowed = set(P["stock_items"])
    cand, stats = [], {"symbols": len(keep), "sec_failed": 0}

    def member(sym, day):
        return any(a <= day and (b is None or day < b) for a, b in spells.get(sym, []))

    for n, s in enumerate(sorted(keep)):
        try:
            filings, issuer = kp.sec_filings_docs(ciks[s], kpr.sec_get_json, since=day_lo)
        except Exception as e:  # noqa: BLE001
            stats["sec_failed"] += 1
            log("  sec failed", s, e)
            continue
        for x in filings:
            if x["form"] != "8-K" or not x["doc"] or not (t_lo <= x["ts"] < t_hi):
                continue
            sp = L.split_of(x["ts"], P)
            if sp not in ("train", "validation", "sealed"):
                continue
            if x["items"] and not (set(x["items"]) & allowed):
                continue
            if not member(s, fu.ny_date(x["ts"])):
                continue
            cand.append({"sym": s, "cik": ciks[s], "ts": x["ts"], "acc": x["accession"], "doc": x["doc"], "items": x["items"],
                         "split": sp, "issuer": issuer})
        if n % 100 == 0:
            log(f"  filings {n}/{len(keep)} candidates {len(cand)}")
    stats["candidates"] = {sp: sum(1 for c in cand if c["split"] == sp) for sp in ("train", "validation", "sealed")}
    pick = []
    for sp in ("train", "validation"):
        pool = sorted((c for c in cand if c["split"] == sp), key=lambda c: L.unit(f"{P['seed']}:{c['acc']}"))
        pick += pool[:P["sample"]["stock_" + sp]]
    pick += [c for c in cand if c["split"] == "sealed"]
    stats["picked"] = len(pick)
    return pick, stats


def filing_text(c):
    from core import keyperson as kp
    from research.studies import keyperson as kpr
    items = set(c["items"])
    body, kind = "", "main"
    if not items or items & {"2.02", "7.01", "8.01"}:
        try:
            idx = json.loads(kpr.sec_get_raw(f"https://www.sec.gov/Archives/edgar/data/{c['cik']}/{c['acc'].replace('-', '')}/index.json"))
            files = [f["name"] for f in idx["directory"]["item"]]
            ex = sorted(f for f in files if re.search(r"ex-?99", f, re.I) and re.search(r"\.(htm|html|txt)$", f, re.I))
            if ex:
                body = kp.html_to_text(kpr.sec_get_raw(kp.doc_url(c["cik"], c["acc"], ex[0])).decode("utf-8", "replace"))
                kind = "exhibit"
        except Exception as e:  # noqa: BLE001
            log("  index failed", c["acc"], e)
    if not body:
        body = kp.html_to_text(kpr.sec_get_raw(kp.doc_url(c["cik"], c["acc"], c["doc"])).decode("utf-8", "replace"))
        m = re.search(r"item\s*\d\.\d\d", body, re.I)
        body = body[m.start():] if m else body
    body = body[:P["text_chars"] + 500]
    text = L.scrub_dates(kp.redact(body, c["issuer"], c["sym"]))[:P["text_chars"]]
    return text, kind


def build_stock(out):
    from research.studies import keyperson as kpr
    pick, stats = stock_items()
    log("picked", stats)
    items, failed = [], 0
    for k, c in enumerate(pick):
        try:
            text, kind = filing_text(c)
        except Exception as e:  # noqa: BLE001
            failed += 1
            log("  text failed", c["acc"], e)
            continue
        if len(text) < 80:
            failed += 1
            continue
        items.append({"key": "sec:" + c["acc"], "market": "stock", "src": "sec_8k", "t_pub": c["ts"], "sym": c["sym"],
                      "split": c["split"], "items": c["items"], "text": text, "text_kind": kind})
        if k % 200 == 0:
            log(f"  text {k}/{len(pick)} ok {len(items)} failed {failed}")
    stats["text_failed"] = failed
    dev = [i for i in items if i["split"] in ("train", "validation")]
    sealed = [i for i in items if i["split"] == "sealed"]
    # labels for DEV items only
    p1, p2 = calendar.timegm((2017, 12, 1, 0, 0, 0)), calendar.timegm((2026, 8, 1, 0, 0, 0))
    bars_by, labels, drops = {}, [], {}
    for s in sorted({i["sym"] for i in dev}):
        b, _dv, _sp = kpr.yahoo(s, p1, p2)
        if b:
            bars_by[s] = b
    for it in dev:
        L.assert_dev(it["t_pub"], P)
        bars = bars_by.get(it["sym"])
        if not bars:
            drops["no_bars"] = drops.get("no_bars", 0) + 1
            continue
        lab, why = L.stock_label(bars, it["t_pub"], P["entry"]["lag_s"], P)
        if not lab:
            drops[why] = drops.get(why, 0) + 1
            continue
        labels.append({"key": it["key"], "labels": {"93": lab}})
    stats["label_drops"] = drops
    stats["dev_items"], stats["dev_labelled"], stats["sealed_items"] = len(dev), len(labels), len(sealed)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "stock_dev_items.jsonl.gz"), dev)
    wjsonl(os.path.join(out, "stock_dev_labels.jsonl.gz"), labels)
    wjsonl(os.path.join(out, "stock_sealed_items.jsonl.gz"), sealed)
    json.dump(stats, open(os.path.join(out, "stock_report.json"), "w"), indent=1, default=str)
    log(json.dumps(stats, default=str))


# ================================================================== build: crypto
def git_show(ref_path):
    r = subprocess.run(["git", "show", ref_path], capture_output=True)
    return r.stdout if r.returncode == 0 else b""


def notice_events():
    ev = []
    raw = git_show("origin/data/event-rows:tape/events.json")
    for e in json.loads(raw or b"[]"):
        ev.append({"sym": e["symbol"], "ts": e["ts"], "title": e["title"], "src": e["venue"], "cls": e.get("cls")})
    for ref, fam in (("origin/data/forced-flow:events/latest.json", "forced"), ("origin/data/kr-listing:events/latest.json", "kr")):
        d = json.loads(git_show(ref) or b"{}")
        for e in d.get("events", []):
            ev.append({"sym": e["sym"], "ts": e["ts"], "title": e["title"], "src": e.get("src") or fam, "cls": e.get("fam")})
    seen, out = set(), []
    for e in sorted(ev, key=lambda e: e["ts"]):
        k = (e["sym"], int(e["ts"] // 60), e["title"][:60])
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def build_crypto(out):
    from research.studies import event_tape as et
    events = notice_events()
    stats = {"events": len(events), "by_split": {}, "drops": {}}
    items, labels = [], []
    day = 86400

    def price(e):
        t0, t1 = int(e["ts"]) - 3700, int(e["ts"]) + P["entry"]["lag_s"] + max(P["holds"].values()) + 900
        for fn, name in ((et.okx_bars, "okx"), (et.vision_bars, "binance_um")):
            for cand in ((e["sym"],) if name == "okx" else (e["sym"], "1000" + e["sym"])):
                b = fn(cand, t0, t1)
                if b:
                    return [(x[0], x[1], x[2], x[3]) for x in b], name
        return None, None

    todo = []
    for e in events:
        sp = L.split_of(e["ts"], P)
        stats["by_split"][sp] = stats["by_split"].get(sp, 0) + 1
        if sp in ("train", "validation", "sealed"):
            todo.append((e, sp))
    for n, (e, sp) in enumerate(todo):
        it = {"key": f"ntc:{e['src']}:{e['sym']}:{int(e['ts'])}", "market": "crypto", "src": e["src"], "cls": e.get("cls"),
              "t_pub": e["ts"], "sym": e["sym"], "split": sp, "items": [], "text": L.redact_coin(e["title"], e["sym"])}
        if sp == "sealed":
            items.append(it)      # sealed: text only, never priced here
            continue
        L.assert_dev(it["t_pub"], P)
        try:
            bars, src = price(e)
        except Exception as ex:  # noqa: BLE001
            bars, src = None, None
            log("  price error", e["sym"], ex)
        if not bars:
            stats["drops"]["no_perp_or_bars"] = stats["drops"].get("no_perp_or_bars", 0) + 1
            continue
        labs = {}
        for lag in [P["entry"]["lag_s"]] + P["entry"]["lag_sens"]:
            lb = L.crypto_label(bars, e["ts"], lag, P)
            if lb:
                labs[str(lag)] = lb
        if str(P["entry"]["lag_s"]) not in labs:
            stats["drops"]["no_entry_bar"] = stats["drops"].get("no_entry_bar", 0) + 1
            continue
        it["price_src"] = src
        items.append(it)
        labels.append({"key": it["key"], "labels": labs})
        if n % 50 == 0:
            log(f"  crypto {n}/{len(todo)} priced {len(labels)}")
    dev = [i for i in items if i["split"] != "sealed"]
    sealed = [i for i in items if i["split"] == "sealed"]
    stats["dev_items"], stats["dev_labelled"], stats["sealed_items"] = len(dev), len(labels), len(sealed)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "crypto_dev_items.jsonl.gz"), dev)
    wjsonl(os.path.join(out, "crypto_dev_labels.jsonl.gz"), labels)
    wjsonl(os.path.join(out, "crypto_sealed_items.jsonl.gz"), sealed)
    json.dump(stats, open(os.path.join(out, "crypto_report.json"), "w"), indent=1, default=str)
    log(json.dumps(stats, default=str))
    _ = day


def publish(parts, data):
    os.makedirs(data, exist_ok=True)
    for kind in ("dev_items", "dev_labels", "sealed_items"):
        rows = []
        for m in ("stock", "crypto"):
            rows += rjsonl(os.path.join(parts, f"{m}_{kind}.jsonl.gz"))
        if kind != "sealed_items":
            L.check_dev_rows([r for r in rows if "t_pub" in r], P)
        wjsonl(os.path.join(data, f"{kind}.jsonl.gz"), rows)
    rep = {}
    for m in ("stock", "crypto"):
        p = os.path.join(parts, f"{m}_report.json")
        if os.path.exists(p):
            rep[m] = json.load(open(p))
    json.dump(rep, open(os.path.join(data, "build_report.json"), "w"), indent=1)
    log(json.dumps(rep, default=str)[:3000])


# ================================================================== dataset loading
def load_dev(data):
    items = L.check_dev_rows(rjsonl(os.path.join(data, "dev_items.jsonl.gz")), P)
    labs = {r["key"]: r["labels"] for r in rjsonl(os.path.join(data, "dev_labels.jsonl.gz"))}
    out = []
    for it in items:
        if it["key"] in labs:
            out.append(dict(it, labels=labs[it["key"]]))
    return out


# ================================================================== leak probe
def build_leak(out):
    from core import ai_news
    from core import factory_us_pit as fu
    p1, p2 = calendar.timegm((2023, 12, 1, 0, 0, 0)), calendar.timegm((2026, 12, 5, 0, 0, 0))
    truth, qs = {}, []
    for a in P["leak"]["assets"]:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(a)}?period1={p1}&period2={p2}&interval=1d")
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            res = json.loads(r.read())["chart"]["result"][0]
        bars, _, _ = fu.parse_chart(res)
        by = {fu.ny_date(b["t"]): b for b in bars}
        days = sorted(by)
        for d in L.leak_days(P["leak"]["first_month"], P["leak"]["last_month"], P["leak"]["days_per_month"], a, days):
            i = days.index(d)
            if i < 1:
                continue
            truth[(a, d)] = "up" if by[d]["c"] > by[days[i - 1]]["c"] else "down"
            qs.append((a, d))
    name = {"^GSPC": "the S&P 500 index", "BTC-USD": "Bitcoin (BTC-USD)"}
    system = "You answer factual questions about past market moves from memory only. Never guess."

    def ask(q):
        a, d = q
        u = (f"Did {name.get(a, a)} close higher or lower on {d} than on the previous trading day? Answer with exactly one word: "
             "up, down, or unknown. If you do not actually remember, answer unknown.")
        txt, served = ai_news.chat(system, u, timeout=90)
        return {"asset": a, "day": d, "truth": truth[q], "answer": L.parse_updown(txt), "raw": txt[:80], "served": served[:60]}

    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        rows = list(ex.map(ask, qs))
    by = {}
    for r in rows:
        b = by.setdefault((r["asset"], r["day"][:7]), {"n": 0, "answered": 0, "right": 0, "empty": 0})
        b["n"] += 1
        if r["answer"] is None:
            b["empty"] += 1
        elif r["answer"] in ("up", "down"):
            b["answered"] += 1
            b["right"] += r["answer"] == r["truth"]
    table = [{"asset": a, "month": m, **v, "answer_rate": v["answered"] / v["n"], "acc_answered": (v["right"] / v["answered"]) if v["answered"] else None}
             for (a, m), v in sorted(by.items())]
    os.makedirs(out, exist_ok=True)
    json.dump({"table": table, "spend": ai_news.spend()}, open(os.path.join(out, "leak.json"), "w"), indent=1, default=str)
    wjsonl(os.path.join(out, "leak_rows.jsonl.gz"), rows)
    for t in table:
        log(t)


# ================================================================== eval (one shard)
def load_calls(data, version):
    return {r["key"]: r for r in rjsonl(os.path.join(data, "calls", f"{version}.jsonl.gz"))}


def build_analog_pool(dev):
    return L.AnalogIndex(dev)


def decide(it, version, system, index, P_):
    lab = it["labels"].get(str(P_["entry"]["lag_s"]))
    analogs = index.query(it, it["t_pub"], P_["analogs"]["k"]) if (index and version.get("analogs")) else None
    user = L.render_user(it, lab, version, analogs, P_)
    from core import ai_news
    txt, served = "", ""
    for _ in range(3):
        txt, served = ai_news.chat(system, user, timeout=150)
        if txt:
            break
        time.sleep(3)
    parsed = L.parse_reply(txt, it["market"])
    return {"key": it["key"], "version": version["id"], "prompt_sha": version["sha256"], "ok": parsed["ok"], "d": parsed.get("d"),
            "conf": parsed.get("conf"), "why": parsed.get("why"), "reply": txt[:600], "served": served[:80]}


def run_eval(out, data, vid, which, shard, shards, deadline_min=300):
    from core import ai_news
    version = next(v for v in L.versions_registry()["versions"] if v["id"] == vid)
    system = open(L.check_version(version)).read()
    dev = load_dev(data)
    index = build_analog_pool(dev) if version.get("analogs") else None
    target = sorted((i for i in dev if i["split"] == which), key=lambda i: i["key"])[shard::shards]
    cache = load_calls(data, vid)
    todo = [i for i in target if not (i["key"] in cache and cache[i["key"]].get("prompt_sha") == version["sha256"] and cache[i["key"]].get("ok"))]
    log(f"{vid} {which} shard {shard}/{shards}: target {len(target)} cached {len(target) - len(todo)} to call {len(todo)}")
    t_end = time.time() + deadline_min * 60
    res = []

    def one(it):
        if time.time() > t_end:
            return None
        return decide(it, version, system, index, P)

    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        for k, r in enumerate(ex.map(one, todo)):
            if r:
                res.append(r)
            if k % 50 == 0:
                log(f"  {k + 1}/{len(todo)} failed {sum(1 for x in res if not x['ok'])} spend {ai_news.spend()}")
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, f"part_{vid}_{which}_{shard}.jsonl"), res + [cache[i["key"]] for i in target if i["key"] in cache and i not in todo], gz=False)
    json.dump(ai_news.spend(), open(os.path.join(out, f"spend_{vid}_{which}_{shard}.json"), "w"))


def merge(parts, data, out):
    """Collate shard parts into calls/<version>.jsonl.gz and score every (version, set)."""
    from core import ai_news  # noqa: F401
    dev = load_dev(data)
    by_v = {}
    for p in glob.glob(os.path.join(parts, "part_*.jsonl")):
        vid = os.path.basename(p).split("_")[1]
        for r in rjsonl(p):
            by_v.setdefault(vid, {})[r["key"]] = r
    os.makedirs(os.path.join(out, "calls"), exist_ok=True)
    os.makedirs(os.path.join(out, "evals"), exist_ok=True)
    reg = {v["id"]: v for v in L.versions_registry()["versions"]}
    for vid, calls in by_v.items():
        old = load_calls(data, vid)
        old.update(calls)
        wjsonl(os.path.join(out, "calls", f"{vid}.jsonl.gz"), list(old.values()))
        for which in ("train", "validation"):
            rows = [i for i in dev if i["split"] == which]
            decs = {k: v for k, v in old.items() if prompt_ok(v, reg.get(vid))}
            res = {"version": vid, "set": which, "sha256": reg[vid]["sha256"], "cells": [],
                   "failed_replies": sum(1 for i in rows if i["key"] in old and not old[i["key"]].get("ok")),
                   "missing_replies": sum(1 for i in rows if i["key"] not in old)}
            for market in ("stock", "crypto"):
                for h in L.available_holds(market):
                    res["cells"].append(L.score_cell(rows, decs, market, h, P))
                if market == "crypto":
                    for lag in [str(x) for x in P["entry"]["lag_sens"]]:
                        res["cells"].append(L.score_cell(rows, decs, market, "1h", P, lag=lag))
            json.dump(res, open(os.path.join(out, "evals", f"{vid}_{which}.json"), "w"), indent=1, default=str)
            for c in res["cells"]:
                if c["lag"] == "93":
                    log(vid, which, c["market"], c["hold"], "offered", c["n_offered"], "traded", c["n_traded"], "score", c.get("score_per_offered"),
                        "per trade", c.get("mean_per_trade"), "p_rnd", (c.get("vs_random") or {}).get("p"), "p_kw", (c.get("vs_keyword") or {}).get("p"))


def prompt_ok(call, version):
    return bool(version) and call.get("prompt_sha") == version["sha256"]


# ================================================================== sealed (one shot)
def run_sealed(out, data):
    from core import ai_news
    from research.studies import keyperson as kpr
    lock = json.load(open(os.path.join(L.HERE, "LOCK.json")))
    if os.path.exists(os.path.join(data, "sealed", "result.json")):
        raise SystemExit("sealed set already opened: refusing a second run")
    reg = L.versions_registry()
    version = next(v for v in reg["versions"] if v["id"] == lock["version"])
    assert version["sha256"] == lock["prompt_sha256"], "LOCK.json does not match the registry"
    system = open(L.check_version(version)).read()
    dev = load_dev(data)
    index = build_analog_pool(dev) if version.get("analogs") else None     # pool frozen: dev items only
    items = rjsonl(os.path.join(data, "sealed_items.jsonl.gz"))
    items = [i for i in items if L.split_of(i["t_pub"], P) == "sealed"]
    # sealed labels, computed only now
    p1, p2 = calendar.timegm((2026, 7, 1, 0, 0, 0)), calendar.timegm((2026, 12, 31, 0, 0, 0))
    bars_by, rows, drops = {}, [], {}
    from research.studies import event_tape as et
    for it in items:
        if it["market"] == "stock":
            if it["sym"] not in bars_by:
                bars_by[it["sym"]] = kpr.yahoo(it["sym"], p1, p2)[0]
            lab, why = L.stock_label(bars_by[it["sym"]] or [], it["t_pub"], P["entry"]["lag_s"], P)
        else:
            t0, t1 = int(it["t_pub"]) - 3700, int(it["t_pub"]) + P["entry"]["lag_s"] + 86400 + 900
            bars = None
            for fn, cands in ((et.okx_bars, [it["sym"]]), (et.vision_bars, [it["sym"], "1000" + it["sym"]])):
                for c in cands:
                    b = fn(c, t0, t1)
                    if b:
                        bars = [(x[0], x[1], x[2], x[3]) for x in b]
                        break
                if bars:
                    break
            lab, why = (L.crypto_label(bars, it["t_pub"], P["entry"]["lag_s"], P), "no_label") if bars else (None, "no_perp")
        if not lab:
            drops[why] = drops.get(why, 0) + 1
            continue
        rows.append(dict(it, labels={"93": lab}))
    log("sealed labelled", len(rows), "drops", drops)

    def one(it):
        return decide(it, version, system, index, P)

    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        calls = list(ex.map(one, rows))
    decs = {c["key"]: c for c in calls}
    k_versions = len(reg["versions"])
    m_total = P["done"]["baselines"] * k_versions
    result = {"version": lock["version"], "k_versions": k_versions, "m_total": m_total, "drops": drops, "cells": [],
              "failed_replies": sum(1 for c in calls if not c["ok"]), "spend": ai_news.spend()}
    for market in ("stock", "crypto"):
        for h in L.available_holds(market):
            result["cells"].append(L.score_cell(rows, decs, market, h, P))
    prim = next(c for c in result["cells"] if c["market"] == "stock" and c["hold"] == "1d")
    ps = {}
    if prim.get("vs_random"):
        ps = {"random": prim["vs_random"]["p"], "keyword": prim["vs_keyword"]["p"], "abstain": prim["vs_abstain"]["p"]}
        result["holm_adjusted"] = L.holm_adjust(ps, m_total)
        adj = result["holm_adjusted"]
        result["done_checks"] = {
            "traded_ge_100": prim["n_traded"] >= P["done"]["min_traded"],
            "mean_per_trade_positive": (prim.get("mean_per_trade") or 0) > 0,
            "beats_random_holm": adj["random"] < P["bootstrap"]["alpha"] and prim["vs_random"]["mean"] > 0,
            "beats_keyword_holm": adj["keyword"] < P["bootstrap"]["alpha"] and prim["vs_keyword"]["mean"] > 0,
            "positive_at_2x": (prim.get("mean_per_trade_2x") or 0) > 0}
        result["verdict"] = ("unread (fewer than 100 traded)" if not result["done_checks"]["traded_ge_100"] else
                             "done condition met" if all(result["done_checks"].values()) else "not met")
    os.makedirs(os.path.join(out, "sealed"), exist_ok=True)
    json.dump(result, open(os.path.join(out, "sealed", "result.json"), "w"), indent=1, default=str)
    wjsonl(os.path.join(out, "sealed", "calls.jsonl.gz"), calls)
    log(json.dumps({k: v for k, v in result.items() if k != "cells"}, default=str))


def main():
    a = sys.argv
    mode = a[1]
    if mode == "build":
        (build_stock if a[3] == "stock" else build_crypto)(a[2])
    elif mode == "publish":
        publish(a[2], a[3])
    elif mode == "leak":
        build_leak(a[2])
    elif mode == "eval":
        run_eval(a[2], a[3], a[4], a[5], int(a[6]), int(a[7]), int(a[8]) if len(a) > 8 else 300)
    elif mode == "merge":
        merge(a[2], a[3], a[4])
    elif mode == "sealed":
        run_sealed(a[2], a[3])
    else:
        raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
