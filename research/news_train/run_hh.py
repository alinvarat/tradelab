"""Historical holdout, Haiku 5.5 vs Sonnet 5.5 on non-S&P-500 8-Ks: IO and orchestration (protocol_hh_20261127.md). GitHub Actions only (news_train_hh.yml).

    run_hh.py build <out> <gate_json> <leak_sonnet> <leak_haiku> <r2_data> <scan_dir>   items, bars, labels, features, prompts. Prints COUNTS only.
    run_hh.py call  <out> <prep.jsonl.gz> <set> <shard> <shards> <cache_dir>            both models answer the same prompts of one shard (cached decisions skipped)
    run_hh.py merge <parts> <prep> <labels> <out> <r2_data> <cache_dir>                 counts gate on decisions first; outcomes are read only if it passes; one-shot

Locked files are imported, never edited. run_r2.sp_candidates / stock_item are NOT used (S&P 500 spells and 'a large US-listed company' are hard-coded there)."""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_cmp as C  # noqa: E402
from research.news_train import logic_hh as H  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402
from research.news_train import logic_r3 as T  # noqa: E402
from research.news_train import run_cmp as X  # noqa: E402

P = H.load_params()
P2 = R.load_params()
P3 = T.load_params()
MODELS = P["models"]
SETS = ("stock_w3", "stock_m1")
log, wjsonl, rjsonl, jdump, jload = X.log, X.wjsonl, X.rjsonl, X.jdump, X.jload
UA_YAHOO = {"User-Agent": "Mozilla/5.0 (TradeLab research)"}


# ================================================================== universe and candidates (SEC), no price anywhere
def universe():
    """{cik: ticker} of Nasdaq/NYSE issuers that were never in the S&P 500 and are not in core/universe.py. -> (universe, stats)."""
    from core import news_backtest as nb, universe as U
    from research.studies import keyperson as kpr
    spells = kpr.load_spells()
    tick = nb.sec_company_tickers()
    ex = kpr.sec_get_json("https://www.sec.gov/files/company_tickers_exchange.json")
    fields = ex["fields"]
    rows = [dict(zip(fields, r)) for r in ex["data"]]
    bad_t = {s.upper() for s in spells} | {s.upper() for s in U.STOCKS}
    bad_c = {tick[s] for s in bad_t if s in tick}
    uni, st = {}, {"exchange_rows": len(rows), "excluded_sp500_or_list": 0, "other_exchange": 0}
    for r in sorted(rows, key=lambda r: str(r["ticker"])):
        t, c = str(r["ticker"]).upper(), int(r["cik"])
        if not H.exchange_ok(r.get("exchange"), P):
            st["other_exchange"] += 1
            continue
        if t in bad_t or c in bad_c:
            st["excluded_sp500_or_list"] += 1
            continue
        uni.setdefault(c, t)                              # one ticker per issuer (share classes share the 8-Ks): the alphabetically first
    st["universe_issuers"] = len(uni)
    return uni, st


def issuer_candidates(cik, sym, t_lo, t_hi):
    """8-K filings of one issuer accepted in the window (true UTC time), with the SIC description. SEC 'recent' covers the window; no older pages."""
    from core import keyperson as kp
    from research.studies import keyperson as kpr
    d = kpr.sec_get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    sic = d.get("sicDescription") or "unknown"
    names = [d.get("name") or ""] + [x.get("name") or "" for x in (d.get("formerNames") or [])]
    since = L.day_of(t_lo - 86400)
    out = []
    for x in kp.parse_filing_docs((d.get("filings") or {}).get("recent") or {}, since):
        f = dict(x, ts=R.fix_ts(x["ts"]))
        if H.candidate_ok(f, P, t_lo, t_hi):
            out.append({"sym": sym, "cik": cik, "ts": f["ts"], "acc": f["accession"], "doc": f["doc"], "items": f["items"],
                        "issuer": [n for n in names if n], "sic": sic})
    return out


def all_candidates(uni, t_lo, t_hi):
    def one(kv):
        try:
            return issuer_candidates(kv[0], kv[1], t_lo, t_hi), 0
        except Exception as e:  # noqa: BLE001
            log("  sec failed", kv, str(e)[:100])
            return [], 1
    cand, failed = [], 0
    with ThreadPoolExecutor(3) as ex:
        for n, (c, f) in enumerate(ex.map(one, sorted(uni.items()))):
            cand += c
            failed += f
            if n % 500 == 0:
                log(f"  issuers {n}/{len(uni)} candidates {len(cand)} failed {failed}")
    return cand, failed


def prior_keys(scan_dir):
    """Every 'sec:' item key in any jsonl.gz file of the restored earlier data branches (data/news-train, -r2, -r3, -r3b, -cmp, -hh)."""
    keys = set()
    for dp, _, fs in os.walk(scan_dir):
        for f in fs:
            if not f.endswith(".jsonl.gz") and not f.endswith(".jsonl"):
                continue
            try:
                for r in rjsonl(os.path.join(dp, f)):
                    k = r.get("key") if isinstance(r, dict) else None
                    if isinstance(k, str) and k.startswith("sec:"):
                        keys.add(k)
            except Exception:  # noqa: BLE001
                pass
    return keys


# ================================================================== Yahoo 1-hour bars (rate-limited; smallcap_intraday backs off 8 s x attempt on 429)
def yahoo_1h(sym, p1, p2):
    from core import factory_us_pit as fu
    y = P["yahoo"]
    ys = urllib.parse.quote(sym.replace(".", "-"))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ys}?period1={int(p1)}&period2={int(p2)}&interval=1h&includePrePost=false"
    for k in range(y["tries"]):
        code = None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA_YAHOO), timeout=30) as r:
                d = json.loads(r.read())["chart"]
            time.sleep(y["sleep_s"])
            if d.get("error") or not d.get("result"):
                return [], "no_result"
            return fu.parse_chart(d["result"][0])[0], "ok"
        except urllib.error.HTTPError as e:
            code = e.code
            if code == 404:
                return [], "http_404"
        except Exception:  # noqa: BLE001
            code = -1
        time.sleep(y["backoff_s"] * (k + 1) if code == 429 else 2 * (k + 1))
    return [], f"failed_{code}"


# ================================================================== build: items + labels + prompts; COUNTS only are printed
def leak_check(gate_path, leak_sonnet, leak_haiku, out):
    gate = json.load(open(gate_path))
    t_lo, _ = H.window_ts(P)
    ok = C.eligible(t_lo, gate["cutoff_month"])
    tabs = {}
    for name, path in (("sonnet", leak_sonnet), ("haiku", leak_haiku)):
        if path and path != "-" and os.path.exists(path):
            tabs[name] = [r for r in json.load(open(path))["table"] if r["month"] >= "2025-09"]
    rep = {"gate": gate, "window_from": P["window"]["from"], "first_eligible_day": gate["first_eligible_day"], "window_after_both_cutoffs": ok,
           "answered_by_month_after_2025_09": {k: {f"{r['asset']} {r['month']}": r["answered"] for r in v} for k, v in tabs.items()},
           "answered_any_month_from_first_eligible": {k: sum(r["answered"] for r in v if r["month"] >= gate["first_eligible_day"][:7]) for k, v in tabs.items()},
           "note": "Registered rule of protocol_cmp_20261126.md (run_cmp.leak_gate). The probe asks for S&P 500 and BTC closes of named days; an answer after the cutoff would mean memory."}
    jdump(os.path.join(out, "leak_check.json"), rep)
    if not ok:
        raise SystemExit(f"window starts {P['window']['from']} before the combined cutoff eligibility {gate['first_eligible_day']}: refusing")
    return rep


def build(out, gate_path, leak_sonnet, leak_haiku, r2, scan_dir):
    from research.news_train import run as R1
    os.makedirs(out, exist_ok=True)
    rep = {"counts_only": True, "params_sha256": L.sha256_file(H.PARAMS_PATH)}
    rep["leak"] = leak_check(gate_path, leak_sonnet, leak_haiku, out)
    t_lo, t_hi = H.window_ts(P)
    uni, ust = universe()
    rep["universe"] = ust
    cand, failed = all_candidates(uni, t_lo, t_hi)
    rep["candidates"] = {"filings_in_window_with_registered_code": len(cand), "issuers_with_one": len({c["cik"] for c in cand}), "sec_failed": failed}
    prior = prior_keys(scan_dir)
    hit = [c for c in cand if "sec:" + c["acc"] in prior]
    rep["prior_key_overlap"] = {"prior_keys_scanned": len(prior), "candidates_excluded": len(hit)}
    cand = [c for c in cand if "sec:" + c["acc"] not in prior]
    drawn = H.sample_candidates(cand, P)
    rep["drawn"] = {"items": len(drawn), "issuers": len({c["cik"] for c in drawn}), "per_month": _by_month(drawn)}
    # ---- bars, labels and features (no text yet). Nothing here is printed except counts.
    p1, p2 = t_lo - 40 * 86400, t_hi + 8 * 86400
    bars_by, bar_status = {}, {}
    for n, sym in enumerate(sorted({c["sym"] for c in drawn})):
        bars_by[sym], st = yahoo_1h(sym, p1, p2)
        bar_status[st] = bar_status.get(st, 0) + 1
        if n % 200 == 0:
            log(f"  bars {n} {bar_status}")
    rep["bars"] = {"symbols": len(bars_by), "status": bar_status}
    drops, ok = {}, []
    for c in sorted(drawn, key=lambda c: L.unit(f"{P['seed']}:sec:{c['acc']}")):
        bars = bars_by.get(c["sym"]) or []
        if not bars:
            drops["no_bars"] = drops.get("no_bars", 0) + 1
            continue
        lab, why = R.stock_label_1h(bars, c["ts"], P2["entry"]["lag_s"], P2)
        if not lab:
            drops[why] = drops.get(why, 0) + 1
            continue
        liq, why = H.liquidity(bars, lab["entry_ts"], lab["p_in"], P)
        if not liq:
            drops[why] = drops.get(why, 0) + 1
            continue
        rv = T.stock_rv(bars, lab["entry_ts"], P3["rv"]["stock_bars"], P3["rv"]["min_stock_bars"])
        it = {"key": "sec:" + c["acc"], "market": "stock", "src": "sec_8k", "t_pub": c["ts"], "sym": c["sym"], "items": c["items"], "cik": c["cik"],
              "descr": P["universe"]["descr"].format(sic=c["sic"]), "_c": c}
        feat = T.features(dict(it, text=""), lab, rv, P2)          # rv and pre are all the callable check needs; the keyword count is redone with the text
        if T.target(lab, P3["hold"]) is None or feat.get("rv") is None or feat.get("pre") is None:
            drops["not_callable"] = drops.get("not_callable", 0) + 1
            continue
        ok.append((it, lab, rv))
    rep["labelable"] = {"callable_before_text": len(ok), "drops": drops}
    # ---- text, in the registered sha order, until the cap
    cap = P["n"]["callable_cap"]
    final, tdrops = [], {}

    def text(entry):
        it, lab, rv = entry
        try:
            t, kind, _ = R1.filing_text(it["_c"])
        except Exception as e:  # noqa: BLE001
            return entry, None, "text_failed"
        return (entry, (t, kind), None) if len(t) >= 80 else (entry, None, "short_text")
    with ThreadPoolExecutor(3) as ex:
        for entry, tk, why in ex.map(text, ok[: int(cap * 1.25) + 1]):
            if why:
                tdrops[why] = tdrops.get(why, 0) + 1
                continue
            it, lab, rv = entry
            it = dict(it, text=tk[0], text_kind=tk[1])
            final.append((it, lab, T.features(it, lab, rv, P2)))
    keep = set(H.first_n_by_sha([e[0]["key"] for e in final], cap, P["seed"]))
    final = [e for e in final if e[0]["key"] in keep]
    rep["text"] = {"drops": tdrops}
    gate_c = P["n"]["callable_floor"]
    rep["callable"] = {"n": len(final), "floor": gate_c, "cap": cap, "go": len(final) >= gate_c, "issuers": len({e[0]["cik"] for e in final}),
                       "per_month": _by_month([e[0] for e in final], key="t_pub"), "in_session_share": (sum(1 for e in final if e[1]["in_session"]) / len(final)) if final else None}
    # ---- prompts (rendered once; both models read the same bytes) and the files
    ver_w3, _, _ = X.version_of("stock_w3")
    ver_m1, _, _ = X.version_of("stock_m1")
    index = L.AnalogIndex(X.RR.load_dev(r2), lag=R.LAB)
    prep, labels, idx = [], [], []
    for it, lab, feat in final:
        base = {k: it[k] for k in ("key", "market", "t_pub", "sym", "items")}
        analogs = index.query(it, it["t_pub"], P2["analogs"]["k"])
        uw = R.render_user2(it, lab, ver_w3, analogs, P2)
        um = T.render_user3(it, lab, feat, ver_m1, None, P3)
        for sn, u in (("stock_w3", uw), ("stock_m1", um)):
            prep.append(dict(base, set=sn, day=L.day_of(it["t_pub"]), user=u, user_sha=X.sha(u)))
        labels.append(dict(base, labels={R.LAB: lab}, feat=feat, text=it["text"], cik=it["cik"], day=L.day_of(it["t_pub"])))
        idx.append({"key": it["key"], "t_pub": it["t_pub"], "cik": it["cik"], "items": it["items"], "month": H.month_of(it["t_pub"])})
    wjsonl(os.path.join(out, "prep.jsonl.gz"), prep)               # prompts only: no label, no outcome (the call jobs download this)
    wjsonl(os.path.join(out, "labels", "labels.jsonl.gz"), labels)  # labels and text: read only by merge, after the counts gate
    wjsonl(os.path.join(out, "items_index.jsonl.gz"), idx)
    jdump(os.path.join(out, "build_report.json"), rep)
    log(json.dumps(rep, default=str))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"go={'1' if rep['callable']['go'] else '0'}\n")


def _by_month(rows, key="ts"):
    out = {}
    for r in rows:
        m = H.month_of(r[key])
        out[m] = out.get(m, 0) + 1
    return dict(sorted(out.items()))


# ================================================================== calls (both models, same prompts, decisions cached)
def load_cache(cache):
    d = {}
    for dp, _, fs in os.walk(cache or "/nonexistent"):
        for f in fs:
            if f.startswith("dec_") and (f.endswith(".jsonl") or f.endswith(".jsonl.gz")):
                for r in rjsonl(os.path.join(dp, f)):
                    d[(r["set"], r["model"], r["key"])] = r
    return d


def call(out, prep, set_name, shard, shards, cache):
    _, system, _ = X.version_of(set_name)
    parse = X.parser_for(set_name)
    rows = [r for r in rjsonl(prep) if r["set"] == set_name]
    rows = sorted(rows, key=lambda r: L.unit(f"{P['seed']}:{r['key']}"))[shard::shards]
    have = load_cache(cache)
    meta = {"set": set_name, "shard": shard, "items": len(rows), "models": {}}
    allres = []
    for mk in ("haiku", "sonnet"):
        todo = [r for r in rows if not have.get((set_name, mk, r["key"]), {}).get("ok")]
        jobs = [{"key": r["key"], "system": system, "user": r["user"], "user_sha": r["user_sha"]} for r in todo]
        res, stopped, spend = X.run_model(mk, jobs, parse, parallel=P["call"]["parallel"], stop_after=P["call"]["stop_after_consecutive_empty"], retries=P["call"]["retries"])
        bad = [r for r in res if not str(r["served"]).startswith("claude/" + MODELS[mk]) or "SERVED" in r["served"]]
        meta["models"][mk] = {"cached": len(rows) - len(todo), "called": len(res), "ok": sum(1 for r in res if r.get("ok")), "stopped_early": stopped, "spend": spend,
                              "served_mismatch": len(bad), "first_served": res[0]["served"] if res else None}
        allres += [dict(r, set=set_name) for r in res]
        log(mk, json.dumps(meta["models"][mk]))
    wjsonl(os.path.join(out, f"dec_{set_name}_{shard}.jsonl"), allres, gz=False)
    jdump(os.path.join(out, f"meta_{set_name}_{shard}.json"), meta)


# ================================================================== merge: counts gate first, outcomes only if it passes, one shot
def decisions(parts, cache):
    d = {s: {"haiku": {}, "sonnet": {}} for s in SETS}
    for src in (cache, parts):
        for (s, m, k), r in load_cache(src).items():
            if s in d and (r.get("ok") or k not in d[s][m]):
                d[s][m][k] = r
    return d


def merge(parts, prep, labels_path, out, r2, cache):
    if os.path.exists(os.path.join(cache or "/nonexistent", "hh", "result.json")):
        raise SystemExit("result.json exists on data/news-train-hh: the one-shot read was already done; refusing")
    os.makedirs(out, exist_ok=True)
    calib = jload(os.path.join(r2, "calib.json"), {})
    theta = (calib.get("w3") or {}).get("stock") or {}
    hold = P["hold"]
    D = decisions(parts, os.path.join(cache or "/nonexistent", "hh"))
    gate = H.count_gate(D["stock_w3"]["haiku"], D["stock_w3"]["sonnet"], theta, hold, P)
    meta = [json.load(open(os.path.join(parts, f))) for f in sorted(os.listdir(parts)) if f.startswith("meta_")]
    spend = {}
    for m in meta:
        for mk, v in m["models"].items():
            s = spend.setdefault(mk, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "notional_usd": 0.0, "stopped_early_shards": 0, "served_mismatch": 0})
            for k in ("calls", "tokens_in", "tokens_out", "notional_usd"):
                s[k] += (v["spend"].get(k) or 0)
            s["stopped_early_shards"] += 1 if v["stopped_early"] else 0
            s["served_mismatch"] += v["served_mismatch"]
    res = {"protocol": "protocol_hh_20261127.md", "k": P["k"], "alpha_k": P["alpha_k"], "theta_frozen_w3_stock": theta, "count_gate": gate, "spend": spend,
           "capped_by_usage_limit": any(v["stopped_early_shards"] for v in spend.values())}
    wjsonl(os.path.join(out, "decisions.jsonl.gz"), [r for s in SETS for m in D[s] for r in D[s][m].values()])
    must = gate["ok"]["paired"] and gate["ok"]["traded_haiku"] and gate["ok"]["traded_sonnet"]
    if not must:
        res["verdict"] = {"comparison": "unread (below the registered counts; no outcome was read)", "nomination": {}}
        jdump(os.path.join(out, "unread.json"), res)
        log(json.dumps(res, default=str))
        return
    labs = {r["key"]: r for r in rjsonl(labels_path)}
    rows = [dict(r, set="stock_w3") for r in labs.values()]
    nb, seed = P["bootstrap"]["n"], P["seed"]
    arr = {m: H.arrays(rows, D["stock_w3"][m], theta, hold, "stock", P2) for m in ("haiku", "sonnet")}
    h1, h2 = H.vs_random(arr["haiku"]), H.vs_random(arr["sonnet"])
    h3 = H.paired(arr["haiku"], arr["sonnet"])
    fam = H.family(h1, h2, h3, P)
    res["family"] = dict(fam, H1_haiku_vs_random=h1, H2_sonnet_vs_random=h2, H3_sonnet_minus_haiku=h3)
    res["verdict"] = H.verdict(fam, h1, h2, h3, gate, P)
    # ---- descriptive, not in the family: registered cells (bootstrap intervals), eod, 2x cost, keyword baseline, magnitude head, months, latency
    res["descriptive"] = {"w3_cells": X.direction_block(rows, D["stock_w3"], None, "stock", theta, nb, seed),
                          "m1": X.magnitude_block([dict(r) for r in rows], D["stock_m1"], None, nb, seed + 20),
                          "per_month": _per_month(rows, D["stock_w3"], theta, hold)}
    res["integrity"] = integrity(labs, arr, meta)
    jdump(os.path.join(out, "result.json"), res)
    log(json.dumps({k: v for k, v in res.items() if k in ("count_gate", "verdict", "spend", "integrity")}, default=str))
    log(json.dumps({k: res["family"][k] for k in ("p", "holm_adjusted")}))


def _per_month(rows, decs, theta, hold):
    out = {}
    for mo in sorted({H.month_of(r["t_pub"]) for r in rows}):
        sub = [r for r in rows if H.month_of(r["t_pub"]) == mo]
        a = {m: H.arrays(sub, decs[m], theta, hold, "stock", P2) for m in ("haiku", "sonnet")}
        out[mo] = {m: {"offered": len(a[m]["side"]), "traded": sum(1 for s in a[m]["side"] if s),
                       "score_per_offered": (sum(a[m]["a"]) / len(a[m]["a"])) if a[m]["a"] else None,
                       "random_per_offered": (sum(a[m]["rnd"]) / len(a[m]["rnd"])) if a[m]["rnd"] else None} for m in a}
    return out


def integrity(labs, arr, meta):
    """RUNBOOK 4.1 numbers: rows, unique rows, per-split counts, losing events, round counts, duplicates."""
    keys = list(labs)
    per = {}
    for r in labs.values():
        per[H.month_of(r["t_pub"])] = per.get(H.month_of(r["t_pub"]), 0) + 1
    out = {"rows": len(keys), "unique_keys": len(set(keys)), "unique_issuers": len({r["cik"] for r in labs.values()}), "per_split_month": dict(sorted(per.items())),
           "round_row_count": len(keys) in (100, 200, 250, 280, 300, 320, 360, 500, 1000, 2000, 3000), "served_mismatch": sum(v["served_mismatch"] for m in meta for v in m["models"].values())}
    for m, a in arr.items():
        tr = [x for x, s in zip(a["a"], a["side"]) if s]
        out[m] = {"traded": len(tr), "losing_trades": sum(1 for x in tr if x < 0), "winning_trades": sum(1 for x in tr if x > 0)}
    return out


def main():
    a = sys.argv
    if a[1] == "build":
        build(*a[2:8])
    elif a[1] == "call":
        call(a[2], a[3], a[4], int(a[5]), int(a[6]), a[7])
    elif a[1] == "merge":
        merge(*a[2:8])
    else:
        raise SystemExit("modes: build | call | merge")


if __name__ == "__main__":
    main()
