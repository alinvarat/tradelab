"""News-analyst training round 3, Track A (magnitude): IO and orchestration (protocol_r3_20261126.md). GitHub Actions only (news_train_r3.yml).

    run_r3.py crypto_pool  <jul_parts> <rem_parts> <out> <r2_data>
    run_r3.py stock_pool   <out> <shard> <shards>
    run_r3.py dev_features <out> <r2_data>
    run_r3.py publish      <parts> <data_dir> <r2_data>
    run_r3.py eval         <out> <data_dir> <version> <set> <shard> <shards> [deadline_min]
    run_r3.py merge        <parts> <data_dir> <out>
    run_r3.py analyze      <data_dir> <out> <version>
    run_r3.py sealed       <out> <data_dir>

Reads round-2 data (a checkout of branch data/news-train-r2) read-only; writes only to its own data branch data/news-train-r3.
Layout there: dev3.jsonl.gz (round-2 train+validation items + labels + features), sealed3_items.jsonl.gz (no labels, no features),
calls/<v>.jsonl.gz, evals/<v>_<set>.json, selection.json, sealed_r3/result.json (written once).
"""
import glob
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402
from research.news_train import logic_r3 as T  # noqa: E402
from research.news_train import run_r2 as RR  # noqa: E402

P = T.load_params()
P2 = R.load_params()
log, wjsonl, rjsonl = RR.log, RR.wjsonl, RR.rjsonl


# ================================================================== sealed pools (items only: no bars, no labels, no features)
def crypto_pool(jul_parts, rem_parts, out, r2_data):
    """July 2026 rows (never used by any round) and the unpicked remainder of the round-2 sealed-period pool (2026-08-01..11-26)."""
    scored = {i["key"] for i in rjsonl(os.path.join(r2_data, "crypto_sealed_items.jsonl.gz"))}
    scored_titles = {R.norm_title(i["text_named"]) for i in rjsonl(os.path.join(r2_data, "crypto_sealed_items.jsonl.gz"))}
    d = P["dates"]
    stats, items = {}, []
    for tag, parts in (("jul", jul_parts), ("rem", rem_parts)):
        rows = []
        for p in sorted(glob.glob(os.path.join(parts, "rows_*.jsonl.gz"))):
            rows += rjsonl(p)
        rows = R.cap_per_coin_day(R.dedupe_rows(rows, P2), P2)
        stats[tag + "_pool"] = len(rows)
        lo = L.day_ts(d["sealed_from"] if tag == "jul" else d["sealed_crypto_rem_from"])
        hi = L.day_ts(d["sealed_crypto_jul_to"] if tag == "jul" else d["refuse_from"])
        rows = [r for r in rows if lo <= r["t"] < hi]
        mine = []
        for r in rows:
            key = f"gd:{r['coin']}:{r['t']}:{int(L.unit(r['title']) * 1e8)}"
            if tag == "rem" and (key in scored or R.norm_title(r["title"]) in scored_titles):
                stats["rem_excluded_r2_scored"] = stats.get("rem_excluded_r2_scored", 0) + 1
                continue
            mine.append((key, r))
        if tag == "jul":
            mine = sorted(mine, key=lambda kr: L.unit(f"{P['seed']}:{kr[0]}"))[:P["sample"]["sealed_crypto_jul"]]
        for key, r in mine:
            T.assert_allowed(r["t"], P)
            items.append({"key": key, "market": "crypto", "src": r["domain"], "cls": None, "t_pub": r["t"], "sym": r["coin"], "pool": tag,
                          "items": [], "text": R.redact_title(r["title"], r["coin"], P2), "text_named": r["title"],
                          "descr": "Instrument: a crypto token with a perpetual contract."})
        stats[tag + "_items"] = len(mine)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "crypto_sealed3_items.jsonl.gz"), items)
    json.dump(stats, open(os.path.join(out, "crypto_pool_report.json"), "w"), indent=1)
    log(json.dumps(stats))


def stock_pool(out, shard, shards):
    """S&P 500 8-Ks accepted in July 2026 (true UTC time), text as in round 2; no label, no bars read."""
    d = P["dates"]
    t_lo, t_hi = L.day_ts(d["sealed_from"]), L.day_ts(d["sealed_stock_to"])
    cand, failed = RR.sp_candidates(t_lo, t_hi, shard, shards)
    items, drops = [], {}
    for c in sorted(cand, key=lambda c: L.unit(f"{P['seed']}:{c['acc']}"))[:int(1.4 * P["sample"]["sealed_stock"] / shards) + 1]:
        T.assert_allowed(c["ts"], P)
        try:
            it = RR.stock_item(c, {})
        except Exception as e:  # noqa: BLE001
            drops["text_failed"] = drops.get("text_failed", 0) + 1
            log("  text failed", c["acc"], e)
            continue
        if not it:
            drops["short_text"] = drops.get("short_text", 0) + 1
            continue
        it["sic"] = c["sic"]
        items.append(it)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, f"stock_sealed3_{shard}.jsonl.gz"), items)
    json.dump({"candidates": len(cand), "sec_failed": failed, "items": len(items), "drops": drops}, open(os.path.join(out, f"stock_pool_report_{shard}.json"), "w"))


# ================================================================== development features (round-2 train + validation items)
def dev_features(out, r2_data):
    dev = rjsonl(os.path.join(r2_data, "dev.jsonl.gz"))
    for it in dev:
        T.assert_dev(it["t_pub"], P)
    p1, p2 = L.day_ts("2025-11-10"), L.day_ts(P["dates"]["dev_end"]) + 6 * 86400
    syms = sorted({i["sym"] for i in dev if i["market"] == "stock"})
    with ThreadPoolExecutor(6) as ex:
        sbars = dict(zip(syms, ex.map(lambda s: RR.yahoo_intraday(s, p1, p2, "1h"), syms)))
    cbars = {}
    for coin in sorted({i["sym"] for i in dev if i["market"] == "crypto"}):
        b, src, failed = RR.coin_bars(coin, L.day_ts("2025-11-29"), L.day_ts(P["dates"]["dev_end"]) + 2 * 86400)
        cbars[coin] = b
        log(coin, "bars", len(b or []), src, "failed", failed)
    res, drops = [], {}
    for it in dev:
        lab = (it.get("labels") or {}).get(R.LAB)
        if not lab:
            drops["no_label"] = drops.get("no_label", 0) + 1
            continue
        if it["market"] == "stock":
            rv = T.stock_rv(sbars.get(it["sym"]) or [], lab["entry_ts"], P["rv"]["stock_bars"], P["rv"]["min_stock_bars"])
        else:
            rv = T.crypto_rv(cbars.get(it["sym"]) or [], lab["entry_ts"], P["rv"]["crypto_hours"], P["rv"]["min_crypto_minutes"])
        f = T.features(it, lab, rv, P2)
        if rv is None:
            drops["no_rv_" + it["market"]] = drops.get("no_rv_" + it["market"], 0) + 1
        res.append(dict(it, feat=f))
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "dev3.jsonl.gz"), res)
    rep = {"items": len(res), "drops": drops, "by": {f"{m}_{s}": sum(1 for r in res if r["market"] == m and r["split"] == s) for m in ("stock", "crypto") for s in ("train", "validation")},
           "with_rv": {m: sum(1 for r in res if r["market"] == m and r["feat"]["rv"] is not None) for m in ("stock", "crypto")}}
    json.dump(rep, open(os.path.join(out, "dev3_report.json"), "w"), indent=1)
    log(json.dumps(rep))


def publish(parts, data, r2_data):
    os.makedirs(data, exist_ok=True)
    dev3 = os.path.join(parts, "dev3.jsonl.gz")
    wjsonl(os.path.join(data, "dev3.jsonl.gz"), rjsonl(dev3))
    stock = []
    for p in sorted(glob.glob(os.path.join(parts, "stock_sealed3_*.jsonl.gz"))):
        stock += rjsonl(p)
    seen, st = set(), []
    for r in sorted(stock, key=lambda r: L.unit(f"{P['seed']}:{r['key']}")):
        if r["key"] not in seen:
            seen.add(r["key"])
            st.append(r)
    st = st[:P["sample"]["sealed_stock"]]
    cr = rjsonl(os.path.join(parts, "crypto_sealed3_items.jsonl.gz")) if os.path.exists(os.path.join(parts, "crypto_sealed3_items.jsonl.gz")) else []
    r2keys = {i["key"] for i in rjsonl(os.path.join(r2_data, "dev.jsonl.gz"))}
    assert not ({i["key"] for i in st + cr} & r2keys), "sealed item overlaps a round-2 development item"
    for r in st + cr:
        T.assert_allowed(r["t_pub"], P)
        assert r["t_pub"] >= L.day_ts(P["dates"]["sealed_from"]), "sealed item before sealed_from"
    wjsonl(os.path.join(data, "sealed3_items.jsonl.gz"), st + cr)
    rep = {"sealed_stock": len(st), "sealed_crypto": len(cr), "sealed_crypto_by_pool": {k: sum(1 for r in cr if r["pool"] == k) for k in ("jul", "rem")}}
    json.dump(rep, open(os.path.join(data, "build_report3.json"), "w"), indent=1)
    log(json.dumps(rep))


# ================================================================== eval
def load_dev3(data):
    rows = rjsonl(os.path.join(data, "dev3.jsonl.gz"))
    for r in rows:
        T.assert_dev(r["t_pub"], P)
    return rows


def load_calls(data, vid):
    return {r["key"]: r for r in rjsonl(os.path.join(data, "calls", f"{vid}.jsonl.gz"))}


def callable_item(it):
    lab = (it.get("labels") or {}).get(R.LAB) or {}
    f = it.get("feat") or {}
    return T.target(lab, P["hold"]) is not None and f.get("rv") is not None and f.get("pre") is not None


def decide(it, version, system, index):
    from core import ai_news
    lab = it["labels"][R.LAB]
    analogs = index.query(it, it["t_pub"], P["analogs"]["k"]) if (index and version.get("analogs")) else None
    user = T.render_user3(it, lab, it["feat"], version, analogs, P)
    txt, served = "", ""
    for _ in range(3):
        txt, served = ai_news.chat(system, user, timeout=150)
        if txt:
            break
        time.sleep(3)
    return dict(T.parse_reply3(txt), key=it["key"], version=version["id"], prompt_sha=version["sha256"], reply=txt[:500], served=served[:80])


def run_eval(out, data, vid, which, shard, shards, deadline_min=300):
    from core import ai_news
    version = next(v for v in T.versions_registry()["versions"] if v["id"] == vid)
    system = open(T.check_version(version)).read()
    dev = load_dev3(data)
    index = L.AnalogIndex(dev, lag=R.LAB) if version.get("analogs") else None
    target = sorted((i for i in dev if i["split"] == which and callable_item(i)), key=lambda i: i["key"])[shard::shards]
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
    dev = load_dev3(data)
    reg = {v["id"]: v for v in T.versions_registry()["versions"]}
    by_v = {}
    for p in glob.glob(os.path.join(parts, "part_*.jsonl")):
        vid = os.path.basename(p).split("_")[1]
        for r in rjsonl(p):
            by_v.setdefault(vid, {})[r["key"]] = r
    os.makedirs(os.path.join(out, "calls"), exist_ok=True)
    os.makedirs(os.path.join(out, "evals"), exist_ok=True)
    for vid, calls in by_v.items():
        old = load_calls(data, vid)
        old.update(calls)
        wjsonl(os.path.join(out, "calls", f"{vid}.jsonl.gz"), list(old.values()))
    # evaluate every version that has cached calls (previous + new)
    valid = {}
    for p in sorted(glob.glob(os.path.join(out, "calls", "*.jsonl.gz")) + [x for x in glob.glob(os.path.join(data, "calls", "*.jsonl.gz")) if not os.path.exists(os.path.join(out, "calls", os.path.basename(x)))]):
        vid = os.path.basename(p).split(".")[0]
        if vid not in reg:
            continue
        decs = {k: v for k, v in {r["key"]: r for r in rjsonl(p)}.items() if v.get("prompt_sha") == reg[vid]["sha256"]}
        for which in ("train", "validation"):
            res = {"version": vid, "set": which, "sha256": reg[vid]["sha256"], "markets": {}}
            for mk in ("stock", "crypto"):
                items = [i for i in dev if i["split"] == which and i["market"] == mk and callable_item(i)]
                called = [i for i in items if i["key"] in decs]
                rows, excl = T.make_rows(items, decs, P)
                m = {"callable": len(items), "called": len(called), "reply_ok": (sum(1 for i in called if decs[i["key"]].get("ok")) / len(called)) if called else 0.0,
                     "excluded": excl, "stats": T.point_stats(rows)}
                if which == "validation" and len(rows) >= 30:
                    m["tests"] = T.gate_tests(rows, P["bootstrap"]["n_dev"], P["seed"])
                res["markets"][mk] = m
                if which == "validation":
                    valid.setdefault(vid, {})[mk] = {"n": m["stats"].get("n", 0), "reply_ok": m["reply_ok"], "partial": m["stats"].get("partial_h_given_rv_pre")}
                s = m["stats"]
                log(vid, which, mk, "n", s.get("n"), "rho_h", s.get("rho_h"), "rho_rv", s.get("rho_rv"), "rho_pre", s.get("rho_pre"), "rho_kw", s.get("rho_kw"),
                    "partial", s.get("partial_h_given_rv_pre"), "auc_h", s.get("auc_h"), "auc_rv", s.get("auc_rv"))
            json.dump(res, open(os.path.join(out, "evals", f"{vid}_{which}.json"), "w"), indent=1, default=str)
    lock = T.select_lock(valid, P)
    json.dump({"lock": lock, "validation": valid, "k_versions": len(reg), "rule": "protocol_r3 selection rule on clean validation"},
              open(os.path.join(out, "selection.json"), "w"), indent=1)
    log("SELECTION", json.dumps({"lock": lock, "validation": valid}))


def analyze(data, out, vid):
    """Error analysis on TRAIN only: where the analyst's size estimate tracks realized size, and where it does not."""
    dev = [i for i in load_dev3(data) if i["split"] == "train" and callable_item(i)]
    decs = load_calls(data, vid)
    rows_all = []
    for mk in ("stock", "crypto"):
        items = [i for i in dev if i["market"] == mk]
        rows, _ = T.make_rows(items, decs, P)
        by_key = {i["key"]: i for i in items}
        for r in rows:
            it = by_key[r["key"]]
            r.update(market=mk, group=R.item_group(it), in_session=bool((it["labels"][R.LAB] or {}).get("in_session")), coin=it["sym"] if mk == "crypto" else "-",
                     hour=int(time.strftime("%H", time.gmtime(it["t_pub"]))))
        rows_all += rows
    out_rows = []
    for mk in ("stock", "crypto"):
        rs = [r for r in rows_all if r["market"] == mk]
        if len(rs) < 60:
            continue
        rvc = sorted(r["rv"] for r in rs)
        t1, t2 = rvc[len(rvc) // 3], rvc[2 * len(rvc) // 3]
        for r in rs:
            r["rv_tercile"] = "rv_low" if r["rv"] < t1 else ("rv_mid" if r["rv"] < t2 else "rv_high")
            r["pre_class"] = "pre_big" if r["pre"] > r["rv"] else "pre_small"
        groups = {}
        for r in rs:
            for g in ("all", r["group"], r["rv_tercile"], r["pre_class"], "in_session" if r["in_session"] else "out_session",
                      ("coin:" + r["coin"]) if mk == "crypto" else "coin:-"):
                groups.setdefault(g, []).append(r)
        for g, gr in sorted(groups.items()):
            if len(gr) < 30:
                continue
            out_rows.append({"market": mk, "group": g, "n": len(gr), "rho_h": T.rho(gr, "h"), "rho_rv": T.rho(gr, "rv"), "partial_h": T.partial_h(gr),
                             "mean_abs": sum(r["y"] for r in gr) / len(gr), "mean_h": sum(r["h"] for r in gr) / len(gr),
                             "big_rate": sum(r["big"] for r in gr) / len(gr), "mean_p_big": sum(r["hp"] for r in gr) / len(gr)})
    os.makedirs(out, exist_ok=True)
    json.dump(out_rows, open(os.path.join(out, f"analysis_{vid}.json"), "w"), indent=1)
    for r in out_rows:
        log(r)


# ================================================================== sealed (one shot)
def sealed(out, data):
    from core import ai_news
    if os.path.exists(os.path.join(data, "sealed_r3", "result.json")):
        raise SystemExit("round-3 sealed set already opened: refusing a second run")
    lockf = json.load(open(os.path.join(T.HERE, "LOCK_R3.json")))
    reg = {v["id"]: v for v in T.versions_registry()["versions"]}
    dev = load_dev3(data)
    items = rjsonl(os.path.join(data, "sealed3_items.jsonl.gz"))
    for it in items:
        T.assert_allowed(it["t_pub"], P)
    K = len(reg)
    result = {"markets": {}, "k_versions": K, "spend": None}
    allcalls = []
    for mk in ("stock", "crypto"):
        lk = lockf.get(mk) or {}
        if not lk.get("version"):
            result["markets"][mk] = {"verdict": "no candidate (sealed set not opened for this market)"}
            continue
        ver = reg[lk["version"]]
        assert ver["sha256"] == lk["prompt_sha256"], "LOCK_R3.json does not match the registry"
        system = open(T.check_version(ver)).read()
        index = L.AnalogIndex(dev, lag=R.LAB) if ver.get("analogs") else None
        mine = [i for i in items if i["market"] == mk]
        rows_items, drops = [], {}
        if mk == "stock":
            p1, p2 = L.day_ts("2026-06-01"), L.day_ts(P["dates"]["sealed_stock_to"]) + 6 * 86400
            syms = sorted({i["sym"] for i in mine})
            with ThreadPoolExecutor(6) as ex:
                bars_by = dict(zip(syms, ex.map(lambda s: RR.yahoo_intraday(s, p1, p2, "1h"), syms)))
        else:
            bars_by = {}
            t0, t1 = L.day_ts("2026-06-29"), L.day_ts(P["dates"]["refuse_from"]) + 2 * 86400
            for coin in sorted({i["sym"] for i in mine}):
                bars_by[coin] = RR.coin_bars(coin, t0, t1)[0]
        for it in mine:
            bars = bars_by.get(it["sym"]) or []
            if not bars:
                drops["no_bars"] = drops.get("no_bars", 0) + 1
                continue
            if mk == "stock":
                lab, why = R.stock_label_1h(bars, it["t_pub"], P2["entry"]["lag_s"], P2)
            else:
                lab, why = R.crypto_label_r2(bars, it["t_pub"], P2), "no_entry_bar"
            if not lab:
                drops[why] = drops.get(why, 0) + 1
                continue
            rv = (T.stock_rv(bars, lab["entry_ts"], P["rv"]["stock_bars"], P["rv"]["min_stock_bars"]) if mk == "stock"
                  else T.crypto_rv(bars, lab["entry_ts"], P["rv"]["crypto_hours"], P["rv"]["min_crypto_minutes"]))
            rows_items.append(dict(it, labels={R.LAB: lab}, feat=T.features(it, lab, rv, P2)))
        todo = [i for i in rows_items if callable_item(i)]
        log("sealed", mk, "items", len(mine), "labelled", len(rows_items), "callable", len(todo), drops)
        with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
            calls = list(ex.map(lambda it: decide(it, ver, system, index), todo))
        allcalls += calls
        decs = {c["key"]: c for c in calls}
        rows, excl = T.make_rows(rows_items, decs, P)
        tests = T.gate_tests(rows, P["bootstrap"]["n_sealed"], P["seed"] + 100)
        v = T.verdict(tests, len(rows), K, P)
        result["markets"][mk] = dict(v, version=ver["id"], n=len(rows), excluded=excl, drops=drops, stats=T.point_stats(rows), tests=tests,
                                     failed_replies=sum(1 for c in calls if not c["ok"]))
        # by pool (crypto): July versus the August-November remainder, descriptive
        if mk == "crypto":
            for pool in ("jul", "rem"):
                keys = {i["key"] for i in rows_items if i.get("pool") == pool}
                sub = [r for r in rows if r["key"] in keys]
                result["markets"][mk]["pool_" + pool] = T.point_stats(sub)
    result["spend"] = ai_news.spend()
    os.makedirs(os.path.join(out, "sealed_r3"), exist_ok=True)
    json.dump(result, open(os.path.join(out, "sealed_r3", "result.json"), "w"), indent=1, default=str)
    wjsonl(os.path.join(out, "sealed_r3", "calls.jsonl.gz"), allcalls)
    log(json.dumps({k: (v if k != "markets" else {m: {kk: vv for kk, vv in d.items() if kk in ("verdict", "n", "holm_adjusted", "version")} for m, d in v.items()}) for k, v in result.items()}, default=str))


def main():
    a = sys.argv
    mode = a[1]
    if mode == "crypto_pool":
        crypto_pool(a[2], a[3], a[4], a[5])
    elif mode == "stock_pool":
        stock_pool(a[2], int(a[3]), int(a[4]))
    elif mode == "dev_features":
        dev_features(a[2], a[3])
    elif mode == "publish":
        publish(a[2], a[3], a[4])
    elif mode == "eval":
        run_eval(a[2], a[3], a[4], a[5], int(a[6]), int(a[7]), int(a[8]) if len(a) > 8 else 300)
    elif mode == "merge":
        merge(a[2], a[3], a[4])
    elif mode == "analyze":
        analyze(a[2], a[3], a[4])
    elif mode == "sealed":
        sealed(a[2], a[3])
    else:
        raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
