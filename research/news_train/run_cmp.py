"""Sonnet 5.5 versus Haiku 5.5 comparison: IO and orchestration (protocol_cmp_20261126.md). GitHub Actions only (news_train_cmp.yml).

    run_cmp.py leak_gate  <leak_json> <haiku_leak_json or -> <out>        cutoff of each model by the registered rule -> gate.json
    run_cmp.py hist_prep  <out> <gate_json> <r2_data> <r3_data>            sealed items + labels + rendered prompts (one copy, both models read it)
    run_cmp.py hist_call  <out> <prep.jsonl.gz> <set> <shard> <shards>     both models answer the same prompts of one shard
    run_cmp.py hist_merge <parts> <prep> <out> <r2_data> <r3_data>         DESCRIPTIVE paired comparison -> hist_result.json
    run_cmp.py fwd        <out> <state> <ingest_dir> <r2_dir>              scheduled forward arm (decisions now, outcomes once at the trigger)

The model is switched in-process (`core.ai_news.CLAUDE_MODEL`); core/ and the production bot are not touched and still default to Haiku.
Reads the round-2 and round-3 data branches read-only; writes only to its own branch data/news-train-cmp. Locked files are imported, never edited."""
import hashlib
import json
import os
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import ingest_branch as B  # noqa: E402
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_cmp as C  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402
from research.news_train import logic_r3 as T  # noqa: E402
from research.news_train import logic_wide as W  # noqa: E402
from research.news_train import run_r2 as RR  # noqa: E402

P = C.load_params()
P2 = R.load_params()
P3 = T.load_params()
PW = W.load_params()
MODELS = P["models"]
log, wjsonl, rjsonl = RR.log, RR.wjsonl, RR.rjsonl
SETS = {"crypto_w1": ("r2", "w1", "crypto"), "stock_w3": ("r2", "w3", "stock"), "stock_m1": ("r3", "m1", "stock")}


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def jload(path, default=None):
    return json.load(open(path)) if os.path.exists(path) else default


def jdump(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, sort_keys=True, default=str)


def version_of(set_name):
    fam, vid, market = SETS[set_name]
    reg = (R if fam == "r2" else T).versions_registry()["versions"]
    ver = next(v for v in reg if v["id"] == vid)
    path = (R if fam == "r2" else T).check_version(ver)          # sha256 of the prompt must equal the registry
    return ver, open(path).read(), market


def parser_for(set_name):
    fam, _, market = SETS[set_name]
    return (lambda t: R.parse_reply2(t, market)) if fam == "r2" else T.parse_reply3


# ================================================================== calling a model (same path as research/news_train: core.ai_news.chat -> claude CLI, Max plan)
def run_model(model_key, jobs, parse, parallel=None, stop_after=None, retries=None, chat=None):
    """jobs: [{key, system, user}] in order. Answers all of them with MODELS[model_key] unless `stop_after` consecutive calls return NO reply at all
    (a usage limit or an outage): then the rest is not called and `stopped` is True (the sample is capped, never retried in a loop).
    -> (results, stopped, spend). Each result carries the wall-clock seconds of its own call (`lat_s`, retries included)."""
    from core import ai_news
    c = P["call"]
    parallel = parallel or c["parallel"]
    stop_after = stop_after or c["stop_after_consecutive_empty"]
    retries = c["retries"] if retries is None else retries
    chat = chat or ai_news.chat
    ai_news.CLAUDE_MODEL = MODELS[model_key]               # read at call time by ai_news._chat_claude
    before = ai_news.spend()
    st = {"empty_run": 0, "stopped": False}
    lock = threading.Lock()

    def one(j):
        if st["stopped"]:
            return None
        t0 = time.time()
        txt, served = "", ""
        for k in range(1 + retries):
            txt, served = chat(j["system"], j["user"], timeout=c["timeout_s"])
            if txt or st["stopped"]:
                break
            time.sleep(3)
        lat = time.time() - t0
        with lock:
            st["empty_run"] = 0 if txt else st["empty_run"] + 1
            if st["empty_run"] >= stop_after:
                st["stopped"] = True
        return dict(parse(txt), key=j["key"], model=model_key, lat_s=round(lat, 2), served=str(served)[:80], reply=(txt or "")[:500], user_sha=j.get("user_sha"))

    with ThreadPoolExecutor(max(1, parallel)) as ex:
        res = [r for r in ex.map(one, jobs) if r]
    after = ai_news.spend()
    return res, st["stopped"], {k: round(after[k] - before.get(k, 0), 4) for k in after if isinstance(after[k], (int, float))}


# ================================================================== leak gate
def leak_gate(leak_json, haiku_json, out):
    rule = P["leak_rule"]
    sonnet = C.leak_cutoff(json.load(open(leak_json))["table"], rule)
    haiku = C.leak_cutoff(json.load(open(haiku_json))["table"], rule) if haiku_json and haiku_json != "-" else None
    both = C.combined_cutoff(sonnet, haiku)
    gate = {"rule": rule, "sonnet_cutoff_month": sonnet, "haiku_cutoff_month": haiku, "cutoff_month": both,
            "first_eligible_day": C.first_eligible_day(both),
            "note": "items with t_pub before first_eligible_day are excluded from every comparison (registered rule, protocol_cmp_20261126.md)"}
    jdump(os.path.join(out, "gate.json"), gate)
    log(json.dumps(gate))


# ================================================================== historical prep (labels and prompts once)
def prep_row(set_name, it, lab, feat, user):
    return {"set": set_name, "key": it["key"], "day": L.day_of(it["t_pub"]), "market": it["market"], "t_pub": it["t_pub"], "sym": it.get("sym"),
            "items": it.get("items") or [], "text": it.get("text") or "", "labels": {R.LAB: lab}, "feat": feat, "user": user, "user_sha": sha(user)}


def hist_prep(out, gate_path, r2, r3):
    gate = json.load(open(gate_path))
    cut = gate["cutoff_month"]
    rep = {"gate": gate, "sets": {}}
    rows = []
    # ---- crypto: round-2 sealed GDELT items, w1 (labels exactly as round 2's sealed_crypto)
    ver, _, _ = version_of("crypto_w1")
    items = [i for i in rjsonl(os.path.join(r2, "crypto_sealed_items.jsonl.gz")) if R.split_r2(i["t_pub"], P2) == "sealed_hist"]
    elig = [i for i in items if C.eligible(i["t_pub"], cut)]
    t0, t1 = L.day_ts(P2["dates"]["sealed_hist_from"]) - 86400, L.day_ts(P2["dates"]["fwd_from"]) + 2 * 86400
    bars_by, n0, drops = {}, len(rows), {}
    for it in elig:
        if it["sym"] not in bars_by:
            bars_by[it["sym"]] = RR.coin_bars(it["sym"], t0, t1)[0]
        bars = bars_by[it["sym"]]
        lab = R.crypto_label_r2(bars, it["t_pub"], P2) if bars else None
        if not lab:
            drops["no_label"] = drops.get("no_label", 0) + 1
            continue
        rows.append(prep_row("crypto_w1", it, lab, None, R.render_user2(it, lab, ver, None, P2)))
    rep["sets"]["crypto_w1"] = {"items_in_file": len(items), "eligible_by_gate": len(elig), "prepared": len(rows) - n0, "drops": drops,
                                "registered_n": P["hist"]["crypto_registered_n"]}
    # ---- stock: round-3 sealed July 8-Ks (labels, rv and features exactly as round 3's sealed run); m1 and w3 on the same callable items
    mine = [i for i in rjsonl(os.path.join(r3, "sealed3_items.jsonl.gz")) if i["market"] == "stock"]
    for it in mine:
        T.assert_allowed(it["t_pub"], P3)
    elig = [i for i in mine if C.eligible(i["t_pub"], cut)]
    n0, drops = len(rows), {}
    if elig:
        p1, p2 = L.day_ts("2026-06-01"), L.day_ts(P3["dates"]["sealed_stock_to"]) + 6 * 86400
        syms = sorted({i["sym"] for i in elig})
        with ThreadPoolExecutor(6) as ex:
            sbars = dict(zip(syms, ex.map(lambda s: RR.yahoo_intraday(s, p1, p2, "1h"), syms)))
        ver_m1, _, _ = version_of("stock_m1")
        ver_w3, _, _ = version_of("stock_w3")
        index = L.AnalogIndex(RR.load_dev(r2), lag=R.LAB)
        for it in elig:
            bars = sbars.get(it["sym"]) or []
            if not bars:
                drops["no_bars"] = drops.get("no_bars", 0) + 1
                continue
            lab, why = R.stock_label_1h(bars, it["t_pub"], P2["entry"]["lag_s"], P2)
            if not lab:
                drops[why] = drops.get(why, 0) + 1
                continue
            rv = T.stock_rv(bars, lab["entry_ts"], P3["rv"]["stock_bars"], P3["rv"]["min_stock_bars"])
            feat = T.features(it, lab, rv, P2)
            if T.target(lab, P3["hold"]) is None or feat.get("rv") is None or feat.get("pre") is None:
                drops["not_callable"] = drops.get("not_callable", 0) + 1
                continue
            analogs = index.query(it, it["t_pub"], P2["analogs"]["k"])
            rows.append(prep_row("stock_m1", it, lab, feat, T.render_user3(it, lab, feat, ver_m1, None, P3)))
            rows.append(prep_row("stock_w3", it, lab, feat, R.render_user2(it, lab, ver_w3, analogs, P2)))
    rep["sets"]["stock"] = {"items_in_file": len(mine), "eligible_by_gate": len(elig), "callable": (len(rows) - n0) // 2, "drops": drops,
                            "registered_n": P["hist"]["stock_registered_n"]}
    wjsonl(os.path.join(out, "prep.jsonl.gz"), rows)
    jdump(os.path.join(out, "prep_report.json"), rep)
    log(json.dumps(rep, default=str))


# ================================================================== historical calls (both models, same prompts, one shard)
def hist_call(out, prep, set_name, shard, shards):
    _, system, _ = version_of(set_name)
    parse = parser_for(set_name)
    rows = sorted((r for r in rjsonl(prep) if r["set"] == set_name), key=lambda r: L.unit(f"{P['seed']}:{r['key']}"))[shard::shards]
    jobs = [{"key": r["key"], "system": system, "user": r["user"], "user_sha": r["user_sha"]} for r in rows]
    log(f"{set_name} shard {shard}/{shards}: {len(jobs)} items, models {list(MODELS.values())}")
    meta = {"set": set_name, "shard": shard, "items": len(jobs), "models": {}}
    allres = []
    for mk in ("haiku", "sonnet"):                              # Haiku first (cheap); Sonnet runs on the same jobs in the same order
        res, stopped, spend = run_model(mk, jobs, parse)
        bad = [r for r in res if not str(r["served"]).startswith("claude/" + MODELS[mk]) or "SERVED" in r["served"]]
        meta["models"][mk] = {"called": len(res), "ok": sum(1 for r in res if r.get("ok")), "stopped_early": stopped, "spend": spend,
                              "served_mismatch": len(bad), "first_served": res[0]["served"] if res else None}
        allres += res
        log(mk, json.dumps(meta["models"][mk]))
    wjsonl(os.path.join(out, f"dec_{set_name}_{shard}.jsonl"), allres, gz=False)
    jdump(os.path.join(out, f"meta_{set_name}_{shard}.json"), meta)


# ================================================================== historical merge (DESCRIPTIVE)
def decs_by_model(parts, set_name):
    d = {"haiku": {}, "sonnet": {}}
    for f in sorted(os.listdir(parts)):
        if f.startswith(f"dec_{set_name}_") and f.endswith(".jsonl"):
            for r in rjsonl(os.path.join(parts, f)):
                d[r["model"]][r["key"]] = r
    return d


def direction_block(rows, decs, stored, market, theta, nb, seed):
    """rows: prep rows of one direction set (same labels for both models); decs: {model: {key: reply}}; stored: Haiku's round-registered replies."""
    byk = {r["key"]: r for r in rows}
    both = [r for r in rows if decs["haiku"].get(r["key"], {}).get("ok") and decs["sonnet"].get(r["key"], {}).get("ok")]
    lab = {r["key"]: r["labels"][R.LAB] for r in both}
    th = (theta or {})
    out = {"n_set": len(rows), "n_paired": len(both),
           "called": {m: len(decs[m]) for m in decs}, "ok": {m: sum(1 for v in decs[m].values() if v.get("ok")) for m in decs}}
    cells = {}
    for m in ("haiku", "sonnet"):
        eff = {k: R.effective(v, th, True) for k, v in decs[m].items()}
        cells[m] = {h: L.score_cell(both, eff, market, h, P2, lag=R.LAB) for h in R.holds(market)}
    out["cells"] = cells
    prim = P["fwd"]["hold"]
    pr = C.pair_direction({r["key"]: byk[r["key"]] for r in both}, decs["haiku"], decs["sonnet"], lab, lab, market, prim, th, True, P2)
    out["paired_1h"] = dict(C.paired_summary([x["d"] for x in pr], [x["day"] for x in pr], nb, seed), discordant=C.discordant(pr),
                            both_abstain=sum(1 for x in pr if x["side_a"] == 0 and x["side_b"] == 0), n=len(pr),
                            mean_net_per_item={"haiku": sum(x["a"] for x in pr) / len(pr) if pr else None, "sonnet": sum(x["b"] for x in pr) / len(pr) if pr else None})
    out["latency"] = {m: C.latency_stats([v.get("lat_s") for v in decs[m].values()]) for m in decs}
    if stored:                                                       # reproduction check against the registered Haiku run
        eff_s = {k: R.effective(v, th, True) for k, v in stored.items()}
        same = [k for k in lab if k in stored and stored[k].get("ok")]
        out["haiku_rerun_vs_registered"] = {
            "items": len(same),
            "same_side_1h": (sum(1 for k in same if L.trade_side(R.effective(decs["haiku"][k], th, True), prim) == L.trade_side(eff_s[k], prim)) / len(same)) if same else None,
            "registered_cell_1h": L.score_cell(both, eff_s, market, prim, P2, lag=R.LAB)}
    return out


def magnitude_block(rows, decs, stored, nb, seed):
    both = [r for r in rows if decs["haiku"].get(r["key"], {}).get("ok") and decs["sonnet"].get(r["key"], {}).get("ok")]
    items = [dict(r, labels=r["labels"]) for r in both]
    res = {}
    rs = {}
    for m in ("haiku", "sonnet"):
        rs[m], excl = T.make_rows(items, decs[m], P3)
        res[m] = {"stats": T.point_stats(rs[m]), "excluded": excl}
    res["n_set"], res["n_paired"] = len(rows), len(both)
    res["paired_partial"] = C.paired_partial(rs["haiku"], rs["sonnet"], nb, seed)
    res["latency"] = {m: C.latency_stats([v.get("lat_s") for v in decs[m].values()]) for m in decs}
    if stored:
        rr, _ = T.make_rows(items, stored, P3)
        res["registered_haiku_stats"] = T.point_stats(rr)
        k = [r["key"] for r in rs["haiku"] if r["key"] in {x["key"] for x in rr}]
        a = {r["key"]: r["h"] for r in rs["haiku"]}
        b = {r["key"]: r["h"] for r in rr}
        res["haiku_rerun_vs_registered_rank_corr"] = T.spearman([a[x] for x in k], [b[x] for x in k]) if len(k) >= 10 else None
    return res


def hist_merge(parts, prep, out, r2, r3):
    gate = jload(os.path.join(os.path.dirname(prep), "gate.json")) or {}
    prows = rjsonl(prep)
    nb, seed = P["fwd"]["bootstrap"]["n"], P["seed"]
    calib = jload(os.path.join(r2, "calib.json"), {})
    res = {"label": "DESCRIPTIVE: these sealed sets were already opened once for Haiku (round 2 crypto, round 3 stock); no gate, no verdict",
           "gate": gate, "prep_report": jload(os.path.join(os.path.dirname(prep), "prep_report.json")), "sets": {}, "meta": []}
    for f in sorted(os.listdir(parts)):
        if f.startswith("meta_") and f.endswith(".json"):
            res["meta"].append(json.load(open(os.path.join(parts, f))))
    stored_crypto = {r["key"]: r for r in rjsonl(os.path.join(r2, "sealed_r2", "crypto_calls.jsonl.gz"))}
    stored_m1 = {r["key"]: r for r in rjsonl(os.path.join(r3, "sealed_r3", "calls.jsonl.gz"))}
    for sn in SETS:
        rows = [r for r in prows if r["set"] == sn]
        if not rows:
            res["sets"][sn] = {"n_set": 0, "note": "no items after the leakage gate"}
            continue
        decs = decs_by_model(parts, sn)
        if sn == "crypto_w1":
            res["sets"][sn] = direction_block(rows, decs, stored_crypto, "crypto", (calib.get("w1") or {}).get("crypto"), nb, seed)
        elif sn == "stock_w3":
            res["sets"][sn] = direction_block(rows, decs, None, "stock", (calib.get("w3") or {}).get("stock"), nb, seed + 10)
        else:
            res["sets"][sn] = magnitude_block(rows, decs, stored_m1, nb, seed + 20)
    spend = {}
    for m in res["meta"]:
        for mk, v in m["models"].items():
            s = spend.setdefault(mk, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "notional_usd": 0.0, "stopped_early_shards": 0})
            for k in ("calls", "tokens_in", "tokens_out", "notional_usd"):
                s[k] += (v["spend"].get(k) or 0)
            s["stopped_early_shards"] += 1 if v["stopped_early"] else 0
    res["spend"] = spend
    jdump(os.path.join(out, "hist_result.json"), res)
    log(json.dumps({k: v for k, v in res.items() if k in ("spend",)}, default=str))


# ================================================================== forward arm
def spot_1m(coin, t0, t1):
    """1-minute spot bars [(open_ts, high, low, close)] of COINUSDT from data-api.binance.vision (the daily Vision files lag a day, so the
    forward arm reads the REST endpoint; spot, not the perpetual, for every forward label of both models)."""
    out, t = [], int(t0)
    while t < t1:
        raw = RR.http(f"https://data-api.binance.vision/api/v3/klines?symbol={urllib.parse.quote(coin)}USDT&interval=1m&startTime={t * 1000}&endTime={int(t1) * 1000}&limit=1000", timeout=30)
        if not raw:
            break
        rows = json.loads(raw)
        if not rows:
            break
        out += [(r[0] // 1000, float(r[2]), float(r[3]), float(r[4])) for r in rows]
        t = rows[-1][0] // 1000 + 60
        if len(rows) < 1000:
            break
    return out


def okx_1m(coin, t0, t1, pages=40):
    """1-minute OKX bars of COIN-USDT, newest page first (history-candles, 100 rows a page), returned ascending as [(open_ts, high, low, close)]."""
    out, after = {}, int(t1) * 1000
    for _ in range(pages):
        raw = RR.http(f"https://www.okx.com/api/v5/market/history-candles?instId={urllib.parse.quote(coin)}-USDT&bar=1m&after={after}&limit=100", timeout=30)
        if not raw:
            break
        rows = (json.loads(raw).get("data") or [])
        if not rows:
            break
        for r in rows:
            out[int(r[0]) // 1000] = (int(r[0]) // 1000, float(r[2]), float(r[3]), float(r[4]))
        oldest = min(int(r[0]) for r in rows)
        if oldest // 1000 <= t0:
            break
        after = oldest
    return [out[k] for k in sorted(out) if t0 <= k <= t1]


def bars_any(coin, t0, t1):
    """Priceable market at t_seen: Binance spot first, then OKX spot. [] when neither lists the coin (the item is then skipped, never imputed)."""
    return spot_1m(coin, t0, t1) or okx_1m(coin, t0, t1)


def fwd_crypto_candidates(joined, start):
    rows = []
    for (src, key), d in joined.items():
        t = d.get("t_seen")
        if src in P["fwd"]["crypto_sources"] and isinstance(t, (int, float)) and not isinstance(t, bool) and t >= start and d.get("title") and not C.is_junk(d["title"]):
            coin = C.coin_from_title(d["title"]) or R.coin_of(d["title"], "", P2)     # addendum 2: exchange symbol first, locked 20-coin map as before
            if coin:
                rows.append({"t": t, "coin": coin, "title": d["title"], "domain": src, "url": key})
    return R.dedupe_rows(rows, P2)


def capped_keys(items, keys):
    """Per (coin, UTC day) at most fwd.cap_per_coin_day of `keys`, by sha order (the round-2 rule); decision-independent."""
    rows = [{"t": items[k]["t_seen"], "coin": items[k]["sym"], "title": items[k]["text_named"], "key": k} for k in keys]
    cap = dict(P2, gdelt=dict(P2["gdelt"], cap_per_coin_day=P["fwd"]["cap_per_coin_day"]))
    return {r["key"] for r in R.cap_per_coin_day(rows, cap)}


def load_dec(path):
    return {(r["model"], r["head"], r["key"]): r for r in rjsonl(path)}


def need_call(decs, model, head, key):
    d = decs.get((model, head, key))
    return not (d and d.get("ok")) and (d or {}).get("attempts", 0) < P["fwd"]["max_attempts"]


def decide_heads(items_by_head, decs, system_of, parse_of, run=run_model):
    """items_by_head: {head: [(key, user)]}. Calls each model on what it still lacks (Haiku first); records attempts and call time.
    Never re-decides an answered item. -> {model: stopped_early}."""
    stopped = {}
    for mk in ("haiku", "sonnet"):
        for head, lst in items_by_head.items():
            jobs = [{"key": k, "system": system_of[head], "user": u, "user_sha": sha(u)} for k, u in lst if need_call(decs, mk, head, k)]
            if not jobs or stopped.get(mk):
                continue
            res, st, _ = run(mk, jobs, parse_of[head])
            stopped[mk] = stopped.get(mk, False) or st
            for r in res:
                old = decs.get((mk, head, r["key"])) or {}
                decs[(mk, head, r["key"])] = dict(r, head=head, attempts=old.get("attempts", 0) + 1)
    return stopped


def wide_universe():
    """-> ({cik: [tickers]}, S&P 500 spells). Network: the SEC ticker map and the round-1 membership list."""
    from core import news_backtest as nb
    from research.studies import keyperson as kpr
    by = {}
    for sym, cik in nb.sec_company_tickers().items():
        by.setdefault(cik, []).append(sym)
    return by, kpr.load_spells()


def wide_check(r, tickers_of, spells, p, filings_fn=None, get_json=None, item_fn=None):
    """One pod 8-K row -> (stock item or None, reason). Not an S&P 500 member on the filing's New York date (that universe is round 2's),
    a stock_items code or none listed, text of at least 80 characters. The item has the round-2 item shape; only `descr` differs."""
    from core import keyperson as kp
    from research.studies import keyperson as kpr
    filings_fn, get_json, item_fn = filings_fn or kp.sec_filings_docs, get_json or kpr.sec_get_json, item_fn or RR.stock_item
    tk = tickers_of.get(r["cik"])
    if not tk:
        return None, "no_ticker"
    if W.in_spell(spells, tk, R.ny_date(r["t_pub"])):
        return None, "sp500"
    filings, issuer = filings_fn(r["cik"], get_json, since=L.day_of(r["t_pub"] - 86400))
    x = next((f for f in filings if f.get("accession") == r["acc"]), None)
    if not x or x["form"] != p["form"] or not x["doc"]:
        return None, "no_filing"
    if x["items"] and not (set(x["items"]) & set(P2["stock_items"])):
        return None, "item_filtered"
    try:
        sic = get_json(f"https://data.sec.gov/submissions/CIK{r['cik']:010d}.json").get("sicDescription") or "unknown"
    except Exception:  # noqa: BLE001
        sic = "unknown"
    c = {"sym": W.pick_ticker(tk), "cik": r["cik"], "ts": R.fix_ts(x["ts"]), "acc": r["acc"], "doc": x["doc"], "items": x["items"], "issuer": issuer, "sic": sic}
    it = item_fn(c, {})
    if not it:
        return None, "short_text"
    it.update(arm=p["arm"], split="fwd", descr=p["descr"].format(sic=sic))
    return it, "ok"



def wide_step(joined, start, now, wstate, witems, universe_fn=None, check_fn=None):
    """Select every closed, not yet selected UTC day of the wide arm once (logic_wide.select_day). Mutates wstate and witems. -> counts."""
    pl = W.pool(joined, start, PW)
    by = {}
    for r in pl:
        by.setdefault(r["day"], []).append(r)
    due = [d for d in sorted(by) if d not in wstate["days"] and W.day_ready(d, now, PW)]
    info = {"pod_sec_8k_rows": len(pl), "days_due": len(due)}
    if not due:
        return info
    try:
        tickers_of, spells = (universe_fn or wide_universe)()
    except Exception as e:  # noqa: BLE001
        info["blocker"] = f"universe load failed: {e}"
        return info
    chk = check_fn or wide_check
    for d in due:
        its, st = W.select_day(by[d], PW, lambda r: chk(r, tickers_of, spells, PW))
        if st["errors"] >= max(3, st["examined"] // 4):             # SEC trouble, not a real selection: tried again next run
            info.setdefault("retry_days", []).append(d)
            continue
        for it in its:
            witems[it["key"]] = it
        wstate["days"][d] = st
    return info


def fwd(out, state, ingest, r2, now=None, bars_fn=bars_any, run=run_model, universe_fn=None, check_fn=None, intraday_fn=None):
    now = int(now or time.time())
    fdir = os.path.join(state, "fwd")
    start = L.day_ts(P["fwd"]["start_utc"])
    items = {r["key"]: r for r in rjsonl(os.path.join(fdir, "items.jsonl.gz"))}
    decs = load_dec(os.path.join(fdir, "dec.jsonl.gz"))
    joined = B.join(B.load_rows(ingest)) if os.path.isdir(ingest) else {}
    prog = {"utc": now, "ingest_rows": len(joined), "locked_models": MODELS}
    if not joined:
        prog["blocker"] = "branch data/news-ingest is absent or empty (the pod publishes only after the owner sets TRADELAB_DATA_PUSH_TOKEN)"
    ver_w1, sys_w1, _ = version_of("crypto_w1")
    ver_w3, sys_w3, _ = version_of("stock_w3")
    ver_m1, sys_m1, _ = version_of("stock_m1")
    system_of = {"w1": sys_w1, "w3": sys_w3, "m1": sys_m1}
    parse_of = {"w1": parser_for("crypto_w1"), "w3": parser_for("stock_w3"), "m1": parser_for("stock_m1")}
    todo = {"w1": [], "w3": [], "m1": []}
    # ---- crypto: new ingest items -> prompt from prices known at t_seen
    cand = fwd_crypto_candidates(joined, start)
    ready = [c for c in cand if c["t"] + P2["entry"]["extra_s"] + P["fwd"]["ready_after_s"] <= now]
    fresh = [c for c in ready if f"ing:{c['domain']}:{c['url']}" not in items]
    bars_by = {}
    for c in fresh:
        coin = c["coin"]
        if coin not in bars_by:
            lo = min(x["t"] for x in fresh if x["coin"] == coin) - 7200
            bars_by[coin] = bars_fn(coin, lo, now + 60)
        it = C.title_to_item(c["domain"], c["url"], c["title"], c["t"], coin, P2)
        pre = C.crypto_pre_label(bars_by[coin], c["t"], P2) if bars_by[coin] else None
        if not pre:
            if now - c["t"] > 3 * 3600:                               # no Binance/OKX market after 3 h: skipped for good (counted, never imputed)
                items[it["key"]] = {"key": it["key"], "market": "skip", "sym": coin, "t_seen": c["t"], "why": "no_market"}
            continue                                                  # otherwise retried in the next run
        it["pre"] = pre
        it["user"] = R.render_user2(it, pre, ver_w1, None, P2)
        items[it["key"]] = it
    for k, it in items.items():
        if it["market"] == "crypto":
            todo["w1"].append((k, it["user"]))
    # ---- stock: round-2 forward items that the pod also saw (real t_seen), prompts from bars known at entry
    s_items = rjsonl(os.path.join(r2, "fwd", "items.jsonl.gz"))
    s_bars = jload(os.path.join(r2, "fwd", "bars1h.json"), {})
    # ---- stock-wide arm (addendum 3): selected from pod rows once per closed day; its own raw items and bars, never written to data/news-train-r2
    wstate = jload(os.path.join(fdir, "wide_state.json"), {"days": {}})
    witems = {r["key"]: r for r in rjsonl(os.path.join(fdir, "wide_items.jsonl.gz"))}
    wbars = jload(os.path.join(fdir, "wide_bars1h.json"), {})
    winfo = wide_step(joined, start, now, wstate, witems, universe_fn, check_fn)
    need = {}
    for k, w in witems.items():
        row = items.get(k)
        if row and row["market"] == "skip":
            continue
        if row is None or now < row["pre"]["entry_ts"] + PW["settle_s"]:
            need[w["sym"]] = min(need.get(w["sym"], w["t_pub"]), w["t_pub"])
    for sym in sorted(need):
        wbars[sym] = RR.merge_bars(wbars.get(sym, []), (intraday_fn or RR.yahoo_intraday)(sym, need[sym] - 10 * 86400, now + 86400, "1h"))
    index = None
    n_stock_pod = 0
    n_wide_pod = 0
    work = [(it, s_bars, "sp500") for it in s_items] + [(w, wbars, "wide") for w in witems.values()]
    for it, bars_of, arm in work:
        tm = B.timing_for(it["key"], joined)
        if not tm:
            continue
        if arm == "wide":
            n_wide_pod += 1
        else:
            n_stock_pod += 1
        if it["key"] in items:
            continue
        lag = max(0.0, tm["t_seen"] - it["t_pub"])
        bars = bars_of.get(it["sym"]) or []
        lab, _ = R.stock_label_1h(bars, it["t_pub"], lag, P2)
        if not lab:
            if arm == "wide" and now - it["t_pub"] > PW["bars_give_up_s"]:           # no entry bar after 5 days: skipped for good, counted, never imputed
                items[it["key"]] = {"key": it["key"], "market": "skip", "arm": arm, "sym": it["sym"], "t_seen": tm["t_seen"], "why": "no_bars"}
            continue
        pre = {k: lab[k] for k in ("entry_ts", "in_session", "delay_s", "pre_move", "day_move", "runup5")}   # known at entry; gross is never stored
        rv = T.stock_rv(bars, lab["entry_ts"], P3["rv"]["stock_bars"], P3["rv"]["min_stock_bars"])
        feat = T.features(it, pre, rv, P2)
        if index is None:
            index = L.AnalogIndex(RR.load_dev(r2), lag=R.LAB)
        analogs = index.query(it, it["t_pub"], P2["analogs"]["k"])
        row = {k: it[k] for k in ("key", "market", "sym", "t_pub", "items", "text", "descr") if k in it}
        row.update(t_seen=tm["t_seen"], lag_s=lag, pre=pre, feat=feat, src="sec_8k", arm=arm,
                   user_w3=R.render_user2(it, pre, ver_w3, analogs, P2), user_m1=T.render_user3(it, pre, feat, ver_m1, None, P3))
        items[it["key"]] = row
    for k, it in items.items():
        if it["market"] == "stock":
            todo["w3"].append((k, it["user_w3"]))
            todo["m1"].append((k, it["user_m1"]))
    # ---- decisions (identical prompt bytes for both models; a decision is made once and never changed)
    stopped = decide_heads(todo, decs, system_of, parse_of, run)
    prog.update(skipped_no_market=sum(1 for i in items.values() if i["market"] == "skip" and i.get("arm") != "wide"), items=len(items), crypto_items=sum(1 for i in items.values() if i["market"] == "crypto"),
                stock_items=sum(1 for i in items.values() if i["market"] == "stock" and i.get("arm") != "wide"), stock_items_with_pod_row=n_stock_pod,
                stopped_early=stopped, capped_by_usage_limit=any(stopped.values()))
    # ---- counts only: paired, settled, discordant (no outcome is read before the trigger)
    cal = jload(os.path.join(r2, "calib.json"), {})
    th_c = (cal.get("w1") or {}).get("crypto") or {}
    prim = P["fwd"]["hold"]
    crypto = {k: it for k, it in items.items() if it["market"] == "crypto"}
    both_ok = [k for k in crypto if decs.get(("haiku", "w1", k), {}).get("ok") and decs.get(("sonnet", "w1", k), {}).get("ok")]
    settled = [k for k in both_ok if now >= crypto[k]["t_seen"] + max(decs[("haiku", "w1", k)]["lat_s"], decs[("sonnet", "w1", k)]["lat_s"]) + 5 + 3600 + 120]
    keep = capped_keys(crypto, settled)
    side = lambda m, k: L.trade_side(R.effective(decs[(m, "w1", k)], th_c, True), prim)      # noqa: E731
    disc = sum(1 for k in keep if side("haiku", k) != side("sonnet", k))
    first = min((it["t_seen"] for it in crypto.values()), default=now)
    reason = C.fire_reason(len(keep), disc, now, P)
    prog["crypto"] = {"both_answered": len(both_ok), "paired_settled_capped": len(keep), "discordant": disc,
                      "min_paired": P["fwd"]["min_paired"], "min_discordant": P["fwd"]["min_discordant"],
                      "projection_paired": C.project(len(keep), P["fwd"]["min_paired"], first, now),
                      "projection_discordant": C.project(disc, P["fwd"]["min_discordant"], first, now), "fire": reason}
    os.makedirs(os.path.join(out, "fwd"), exist_ok=True)
    if reason and not os.path.exists(os.path.join(fdir, "result_crypto.json")):
        res = fwd_score_crypto(crypto, decs, keep, th_c, now, bars_fn)
        res["fired_by"] = reason
        jdump(os.path.join(out, "fwd", "result_crypto.json"), res)
        prog["crypto"]["fired_now"] = True
    # stock: scoring stays closed until round 2's own forward trigger has fired (its one-shot must not be steered by these labels)
    r2_open = os.path.exists(os.path.join(r2, "fwd", "result.json"))
    st_both = [k for k, it in items.items() if it["market"] == "stock" and it.get("arm") != "wide" and all(decs.get((m, h, k), {}).get("ok") for m in MODELS for h in ("w3", "m1"))]
    prog["stock"] = {"both_answered_w3_m1": len(st_both), "round2_forward_result_exists": r2_open, "scoring_open": r2_open,
                     "min_magnitude_n": P["fwd"]["min_stock_magnitude_n"],
                     "projection": C.project(len(st_both), P["fwd"]["min_stock_magnitude_n"], min((items[k]["t_seen"] for k in st_both), default=now), now)}
    if r2_open and len(st_both) >= P["fwd"]["min_stock_magnitude_n"] and not os.path.exists(os.path.join(fdir, "result_stock.json")):
        res = fwd_score_stock({k: items[k] for k in st_both}, decs, s_bars, cal, now)
        jdump(os.path.join(out, "fwd", "result_stock.json"), res)
        prog["stock"]["fired_now"] = True
    # ---- stock-wide arm: counts, then its own one-shot (the universe excludes S&P 500 members, so round 2's forward set and trigger are untouched)
    w_rows = {k: it for k, it in items.items() if it["market"] == "stock" and it.get("arm") == "wide"}
    w_both = [k for k, it in w_rows.items() if all(decs.get((m, h, k), {}).get("ok") for m in MODELS for h in ("w3", "m1"))]
    w_settled = [k for k in w_both if now >= w_rows[k]["pre"]["entry_ts"] + PW["settle_s"]]
    first_w = min((w_rows[k]["t_seen"] for k in w_both), default=now)
    prog["stock_wide"] = dict(winfo, days_selected=len(wstate["days"]), admitted=len(witems), rows_built=len(w_rows), with_pod_row=n_wide_pod,
                              skipped_no_bars=sum(1 for i in items.values() if i["market"] == "skip" and i.get("arm") == "wide"),
                              both_answered_w3_m1=len(w_both), settled=len(w_settled), min_n=PW["min_n"],
                              projection=C.project(len(w_settled), PW["min_n"], first_w, now), per_day=wstate["days"])
    if (len(w_settled) >= PW["min_n"] or now >= L.day_ts(PW["hard_stop_utc"])) and w_settled and not os.path.exists(os.path.join(fdir, "result_stock_wide.json")):
        res = fwd_score_stock({k: w_rows[k] for k in w_settled}, decs, wbars, cal, now,
                              label="stock-wide forward arm (addendum 3, non-S&P 500 8-Ks): magnitude m1 (headline) and direction w3 (descriptive); selected before any outcome")
        res["n_settled"] = len(w_settled)
        res["underpowered"] = len(w_settled) < PW["min_n"]
        jdump(os.path.join(out, "fwd", "result_stock_wide.json"), res)
        prog["stock_wide"]["fired_now"] = True
    jdump(os.path.join(out, "fwd", "wide_state.json"), wstate)
    wjsonl(os.path.join(out, "fwd", "wide_items.jsonl.gz"), list(witems.values()))
    jdump(os.path.join(out, "fwd", "wide_bars1h.json"), wbars)
    wjsonl(os.path.join(out, "fwd", "items.jsonl.gz"), list(items.values()))
    wjsonl(os.path.join(out, "fwd", "dec.jsonl.gz"), list(decs.values()))
    jdump(os.path.join(out, "fwd", "progress.json"), prog)
    log(json.dumps(prog, default=str))


def fwd_score_crypto(crypto, decs, keep, th_c, now, bars_fn):
    """One shot. Each model enters at its own t_llm: t_seen + its measured call time + 5 s; the 1-hour gross comes from spot 1-minute bars."""
    keep = sorted(keep)
    labs = {"haiku": {}, "sonnet": {}}
    by = {}
    for k in keep:
        by.setdefault(crypto[k]["sym"], []).append(k)
    for coin, ks in by.items():
        bars = bars_fn(coin, min(crypto[k]["t_seen"] for k in ks) - 7200, now + 60)
        for k in ks:
            for m in labs:
                labs[m][k] = C.crypto_own_label(bars, crypto[k]["t_seen"], decs[(m, "w1", k)]["lat_s"], P2)
    dh = {k: decs[("haiku", "w1", k)] for k in keep}
    ds = {k: decs[("sonnet", "w1", k)] for k in keep}
    items = {k: dict(day=L.day_of(crypto[k]["t_seen"])) for k in keep}
    prim = P["fwd"]["hold"]
    pr = C.pair_direction(items, dh, ds, labs["haiku"], labs["sonnet"], "crypto", prim, th_c, True, P2)
    nb, seed = P["fwd"]["bootstrap"]["n"], P["seed"]
    res = {"label": "PRIMARY forward comparison, crypto w1 at 1 h, paired Sonnet minus Haiku net P&L per offered item (abstain = 0)",
           "paired": dict(C.paired_summary([x["d"] for x in pr], [x["day"] for x in pr], nb, seed + 30), discordant=C.discordant(pr), n=len(pr),
                          both_abstain=sum(1 for x in pr if x["side_a"] == 0 and x["side_b"] == 0),
                          mean_net_per_item={"haiku": sum(x["a"] for x in pr) / len(pr) if pr else None, "sonnet": sum(x["b"] for x in pr) / len(pr) if pr else None}),
           "latency_call_s": {m: C.latency_stats([decs[(m, "w1", k)]["lat_s"] for k in keep]) for m in labs},
           "entry_delay_note": "each model's entry is t_seen + its own measured call time + 5 s", "opened_utc": now}
    d = res["paired"]
    res["verdict"] = ("underpowered" if d["n"] < P["fwd"]["min_paired"] or d["discordant"] < P["fwd"]["min_discordant"] else
                      ("sonnet better" if d["mean_diff"] > 0 and d["lo"] > 0 and (d["sign"]["p"] or 1) < P["fwd"]["bootstrap"]["alpha"] else
                       "sonnet worse" if d["mean_diff"] < 0 and d["hi"] < 0 and (d["sign"]["p"] or 1) < P["fwd"]["bootstrap"]["alpha"] else "no difference detected"))
    return res


def fwd_score_stock(sitems, decs, s_bars, cal, now, label="stock forward: magnitude m1 (headline) and direction w3 (descriptive); round-2 forward result existed before scoring"):
    """One shot, opened only after round 2's forward result exists. Magnitude (m1) is the stock headline; direction (w3) is descriptive."""
    prim = P["fwd"]["hold"]
    labs = {m: {} for m in MODELS}
    for k, it in sitems.items():
        bars = s_bars.get(it["sym"]) or []
        for m in MODELS:
            lab, _ = R.stock_label_1h(bars, it["t_pub"], it["lag_s"] + decs[(m, "w3", k)]["lat_s"], P2)
            if lab:
                labs[m][k] = lab
    rows = {}
    for m in MODELS:
        its = [dict(sitems[k], labels={R.LAB: labs[m][k]}) for k in sitems if k in labs[m]]
        rows[m], _ = T.make_rows(its, {k: decs[(m, "m1", k)] for k in sitems}, P3)
    nb, seed = P["fwd"]["bootstrap"]["n"], P["seed"]
    th = (cal.get("w3") or {}).get("stock")
    items = {k: dict(day=L.day_of(sitems[k]["t_pub"])) for k in sitems}
    pr = C.pair_direction(items, {k: decs[("haiku", "w3", k)] for k in sitems}, {k: decs[("sonnet", "w3", k)] for k in sitems}, labs["haiku"], labs["sonnet"],
                          "stock", prim, th, True, P2)
    return {"label": label,
            "magnitude_partial": C.paired_partial(rows["haiku"], rows["sonnet"], nb, seed + 40),
            "direction_w3": dict(C.paired_summary([x["d"] for x in pr], [x["day"] for x in pr], nb, seed + 41), discordant=C.discordant(pr), n=len(pr)),
            "latency_call_s": {m: C.latency_stats([decs[(m, "m1", k)]["lat_s"] for k in sitems]) for m in MODELS}, "opened_utc": now}


def main():
    a = sys.argv
    mode = a[1]
    if mode == "leak_gate":
        leak_gate(a[2], a[3], a[4])
    elif mode == "hist_prep":
        hist_prep(a[2], a[3], a[4], a[5])
    elif mode == "hist_call":
        hist_call(a[2], a[3], a[4], int(a[5]), int(a[6]))
    elif mode == "hist_merge":
        hist_merge(a[2], a[3], a[4], a[5], a[6])
    elif mode == "fwd":
        fwd(a[2], a[3], a[4], a[5])
    else:
        raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
