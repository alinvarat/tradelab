"""D3 + D4 (protocol_d3d4_20261126.md). GitHub Actions only (workflow d3d4.yml). Modes:

    python research/studies/d3d4.py <out> events <frozen forced-flow events.json>
        stage A, NO returns: fresh Binance catalog titles (tag removals), D4 events, D3 point-in-time signals from daily perp klines, hazard table, kill 1
    python research/studies/d3d4.py <out> run <frozen d3d4 events dir> <forced-flow rows.jsonl.gz>
        prices the frozen signals / events once, stage-0 gate, Holm, placebo, matched / random control, correlation with L1f
"""
import gzip
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import forced_flow as ff   # noqa: E402
from core import kr_listing as kl    # noqa: E402
from core import sweep_stats as ss   # noqa: E402
from research.studies import binance_vision as bv   # noqa: E402
from research.studies import d3d4_core as dc        # noqa: E402

DAY, HOUR = dc.DAY, dc.HOUR
T_FEAT0 = ff._t(2023, 10, 1)
TRAIN_DAYS = (dc.BOUNDS["train"][1] - dc.BOUNDS["train"][0]) / DAY


def months_of(a, b):
    return (b - a) / DAY / 30.4375


def dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, default=str)


def dump_gz(path, obj):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))


# ================================================================ stage A (events)
def catalog_titles(gaps):
    from research.studies import forced_flow as sf
    arts = {}
    for cid in (161, 49, 93):
        for a in sf.binance_catalog(cid, gaps):
            arts.setdefault(a["code"] or a["title"], a)
    return sorted(arts.values(), key=lambda a: a["ts"])


def perp_daily(sym):
    out, failed = {}, 0
    for y, m in bv.months(T_FEAT0, ff.END):
        rows = bv.fetch("futures/um", "monthly", "klines", sym, (y, m), "1d", bv.parse_kline)
        if rows is None:
            failed += 1
            continue
        for r in rows:
            out[int(r[0] // DAY)] = (r[4], r[7])
    return sym, out, failed


def stage_a(out_dir, frozen_path):
    t0 = time.time()
    fz = json.load(open(frozen_path))
    adds = [e for e in fz["events"] if e["fam"] == "mon_tag"]
    fut = [e for e in fz["events"] if e["fam"] == "fut_delist"]
    l1f = list(fz["l1f"])
    gaps = {}
    arts = catalog_titles(gaps)
    removals = ff.dedupe([{"fam": "tag_rm", "sym": s, "ts": a["ts"], "src": "binance", "title": a["title"]}
                          for a in arts for s in dc.monitoring_removed(a["title"]) if ff.in_window(a["ts"])])
    from core import screens as sc
    fresh_adds = ff.dedupe([{"fam": "mon_tag", "sym": s, "ts": a["ts"]} for a in arts for s in ff.monitoring_symbols(a["title"]) if ff.in_window(a["ts"])])
    fresh_l1f = ff.dedupe([{"fam": "l1f_ref", "sym": s, "ts": a["ts"]} for a in arts for s in sc.binance_delist_symbols(a["title"]) if ff.in_window(a["ts"])])
    tag_titles = [{"ts": a["ts"], "title": a["title"]} for a in arts if "monitoring tag" in a["title"].lower()]
    cross = {"catalog_articles": len(arts), "adds_frozen": len(adds), "adds_fresh": len(fresh_adds), "l1f_frozen": len(l1f), "l1f_fresh": len(fresh_l1f),
             "removal_notices": len({e["ts"] for e in removals}), "removal_coins": len(removals), "tag_titles": len(tag_titles)}
    print("catalog", cross, gaps, flush=True)
    d4 = dc.d4_events(adds, removals, l1f, fut)
    d4c = dc.d4_counts(d4)
    print("d4 counts", d4c, flush=True)
    ends = l1f + fut
    nidx = dc.notice_index(ends)
    book = dc.tag_book(adds, removals, ends)

    syms = [x for x in bv.list_symbols("futures/um", "USDT", "klines", "monthly") if dc.base_of(x)]
    print("perp symbols", len(syms), flush=True)
    dbars, failed = {}, {}
    with ThreadPoolExecutor(12) as ex:
        for sym, bars, nf in ex.map(perp_daily, syms):
            if bars:
                dbars[sym] = bars
            if nf:
                failed[sym] = nf
    print("daily bars", len(dbars), "symbols with failed months", len(failed), "seconds", round(time.time() - t0), flush=True)
    days = [d for d in range(int(dc.FIRST_SIGNAL // DAY), int(dc.LAST_SIGNAL // DAY))]
    rows, pool = dc.build_signals(dbars, days, book, nidx)
    print("signals", len(rows), "pool days", len(pool), flush=True)
    haz = {k: dc.hazard_table(rows, nidx, a, b) for k, (a, b) in dc.BOUNDS.items()}
    killed, ok = dc.kill1_d3(haz["train"])
    ncal = dc.notice_calendar(ends)
    leads = dc.tag_leads(adds, nidx)
    stage = {"hazard": haz, "kill1_d3": {"killed": killed, "judged_sets_pass": ok, "rule": "train hazard per coin-day >= 10% on >= 20 coin-days"},
             "d4": d4c, "calendar_l1f_fut": ncal, "tag_leads": leads, "crosscheck": cross, "failed_month_symbols": len(failed),
             "perp_symbols": len(syms), "perp_with_daily": len(dbars), "gaps": gaps, "seconds": round(time.time() - t0),
             "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    dump(os.path.join(out_dir, "stagea.json"), stage)
    dump(os.path.join(out_dir, "events.json"), {"adds": adds, "removals": removals, "l1f": l1f, "fut": fut, "d4_events": d4, "d4_counts": d4c,
                                                 "tag_titles": tag_titles, "crosscheck": cross, "built_utc": stage["built_utc"]})
    dump_gz(os.path.join(out_dir, "signals.json.gz"), {"rows": rows, "pool": pool})
    print(json.dumps(stage, default=str)[:6000], flush=True)


# ================================================================ pricing helpers
class Ctx:
    """Lazy monthly files of one perp (hourly klines, 1-minute klines, funding); one per worker task."""

    def __init__(self, perp):
        self.perp, self.h, self.m1, self.f, self.fund_missing = perp, {}, {}, {}, 0

    def _month(self, store, kind, interval, y, m, parse):
        if (y, m) not in store:
            r = bv.fetch("futures/um", "monthly", kind, self.perp, (y, m), interval, parse)
            if interval == "1m" and len(store) >= 2:
                store.clear()
            store[(y, m)] = r if kind == "fundingRate" else (None if r is None else {x[0]: (x[1], x[2], x[3], x[4]) for x in r})
        return store[(y, m)]

    def bars(self, t0, t1, interval="1h"):
        store = self.h if interval == "1h" else self.m1
        out = {}
        for y, m in bv.months(t0, t1):
            d = self._month(store, "klines", interval, y, m, bv.parse_kline)
            if d is None:
                return None
            out.update({t: v for t, v in d.items() if t0 <= t < t1})
        return out

    def rates(self, t0, t1):
        out = []
        for y, m in bv.months(t0, t1):
            r = self._month(self.f, "fundingRate", None, y, m, bv.parse_funding)
            if r is None:
                self.fund_missing += 1
                continue
            out += r
        return out


def price_one(ctx, e0, hold, nidx):
    """One short entered at e0 (UTC 01:00 of the signal day). Returns dict(sim, income, notice, m1, fund_missing) or a string reason for a dropped trade."""
    nt = dc.first_notice_after(nidx, dc.base_of(ctx.perp), e0)
    nt = nt if nt is not None and nt + 60 < e0 + hold + 3 * HOUR else None
    bars = ctx.bars(e0, e0 + hold + 6 * HOUR)
    if bars is None:
        return "price_fetch_failed"
    if not bars:
        return "no_bars"
    b1 = None
    if nt is not None:
        b1 = ctx.bars(int(nt) + 60, int(nt) + 60 + 400, "1m")
    sim = dc.short_hourly(bars, e0, hold, nt, b1 or None)
    if not sim:
        return "no_entry_or_exit_bar"
    fm0 = ctx.fund_missing
    income = dc.fund_income(ctx.rates(sim["te"] - 1, sim["x"] + 1), sim["te"], sim["x"])
    return {"sim": sim, "income": income, "notice": nt is not None and sim["reason"] == "notice", "m1": bool(b1), "fund_missing": ctx.fund_missing > fm0}


def d3_worker(args):
    perp, days_by_set, nidx = args
    ctx, cache, out, drops = Ctx(perp), {}, {}, {}
    for rid, s, h in dc.d3_rules():
        last, res = -1, []
        for d in days_by_set.get(s, []):
            e0 = d + HOUR
            if e0 < last:
                continue
            key = (e0, h)
            if key not in cache:
                cache[key] = price_one(ctx, e0, h, nidx)
            r = cache[key]
            if isinstance(r, str):
                drops[r] = drops.get(r, 0) + 1
                continue
            res.append((d, r))
            last = r["sim"]["x"]
        out[rid] = res
    return perp, out, drops


def control_worker(args):
    perp, jobs, nidx = args
    ctx, out = Ctx(perp), {}
    for d, h in jobs:
        r = price_one(ctx, d + HOUR, h, nidx)
        out[(d, h)] = None if isinstance(r, str) else r["sim"]["gross"] + r["income"]
    return perp, out


# ================================================================ evaluation (shared)
def split_stats(trades, key="net"):
    return {k: ff.stats([t[key] for t in ss.in_split(trades, *dc.BOUNDS[k])], months_of(*dc.BOUNDS[k])) for k in dc.BOUNDS}


def describe(rid, coin_tr, clus):
    """Report block of one rule: stats by split at cluster and coin level, gross / placebo / control means, cost sensitivity."""
    def by(tr, f):
        return {k: dc.mean_of([f(t) for t in ss.in_split(tr, *dc.BOUNDS[k])]) for k in dc.BOUNDS}
    return {"id": rid, "cluster_stats_by_split": split_stats(clus), "coin_stats_by_split": split_stats(coin_tr),
            "cluster_stats_all": ff.stats([t["net"] for t in clus], dc.MONTHS), "coin_stats_all": ff.stats([t["net"] for t in coin_tr], dc.MONTHS),
            "gross_mean_by_split": by(clus, lambda t: t["gross"]),
            "placebo_mean_by_split": by(clus, lambda t: -t["gross"] - t["cost"] + t["fund"]),
            "control_mean_by_split": {k: dc.ctrl_mean(ss.in_split(clus, *dc.BOUNDS[k])) for k in dc.BOUNDS},
            "mean_2x_cost_all": dc.mean_of([t["net"] - t["cost"] for t in clus]),
            "mean_at_014pct_cost_all": dc.mean_of([t["net"] + t["cost"] - 0.0014 for t in clus]),
            "reasons": {r: sum(1 for t in coin_tr if t["reason"] == r) for r in sorted({t["reason"] for t in coin_tr})}}


def evaluate(items, cfg, l1f_tr):
    """items [(rid, coin_trades, cluster_trades, judged)] -> (table, gate_rows). Stage 0 on the train clusters (gate + train mean above the control mean), then
    sweep evaluate for the survivors; non-judged rules are described only."""
    table, gate_rows = {}, []
    t0, t1 = dc.BOUNDS["train"]
    a, b = dc.START, dc.END
    l1f_day, l1f_wk = dc.exit_series(l1f_tr, a, b), dc.exit_series(l1f_tr, a, b, True)
    for rid, coin_tr, clus, judged in items:
        tr = ss.in_split(clus, t0, t1)
        d = describe(rid, coin_tr, clus)
        d["judged"] = judged
        d["corr_l1f_exit_day"] = ff.corr(dc.exit_series(clus, a, b), l1f_day)
        d["corr_l1f_exit_week"] = ff.corr(dc.exit_series(clus, a, b, True), l1f_wk)
        ok = False
        if judged:
            ok, info = ss.gate(tr, {"size": dc.SIZE}, cfg, TRAIN_DAYS)
            cm = dc.ctrl_mean(tr)
            info = dict(info, id=rid, control_mean_train=cm)
            if ok and cm is not None and (info["train_mean"] or 0) <= cm:
                ok, info["reason"] = False, "train net mean not above the matched/random-control mean"
            d["gate"] = info
        d["ok"] = ok
        table[rid] = d
        if ok:
            r = {"id": rid, "gate": d["gate"], "status": "ok", **ss.evaluate(clus, {"size": dc.SIZE}, dc.BOUNDS)}
            va, te = ss.in_split(clus, *dc.BOUNDS["validation"]), ss.in_split(clus, *dc.BOUNDS["test"])
            cv, ct = dc.ctrl_mean(va), dc.ctrl_mean(te)
            r["extra_criteria"] = {"val_beats_control": (dc.mean_of([t["net"] for t in va]) or 0) > (cv if cv is not None else 9),
                                   "test_beats_control": (dc.mean_of([t["net"] for t in te]) or 0) > (ct if ct is not None else 9)}
            gate_rows.append(r)
    return table, gate_rows


def judge(table, gate_rows, strict_rows, cfg, strict_cfg, label, killed):
    out = {}
    for name, rows_, c in (("event_gate", gate_rows, cfg), ("sweep_strict_gate", strict_rows, strict_cfg)):
        for r in rows_:
            r["family"] = label
        info = ss.judge_family(rows_, c) if rows_ else {"holm_m": 0}
        passed = [] if killed else [r["id"] for r in rows_ if r.get("passed")]
        out[name] = {"stage0_survivors": len(rows_), "holm": info, "passed": passed, "passed_if_not_killed": [r["id"] for r in rows_ if r.get("passed")],
                     "evaluated": [dict(ss.compact(r, label), criteria=r["criteria"], extra=r.get("extra_criteria")) for r in rows_]}
    return out


def closest(table, gate_rows):
    """Rule closest to passing: most criteria met among stage-0 survivors, else the judged rule with the highest train x."""
    if gate_rows:
        r = sorted(gate_rows, key=ss.closeness_key)[0]
        return {"id": r["id"], "n_criteria": r["n_criteria"], "of": len(r["criteria"])}
    j = [(v["gate"].get("x", -9), k) for k, v in table.items() if v.get("judged") and "gate" in v]
    return {"id": max(j)[1], "train_x": max(j)[0], "stage0": "dropped at the gate"} if j else None


# ================================================================ D3 run
def run_d3(out_dir, fz, sig, stage, l1f_tr):
    t0 = time.time()
    rows, pool = sig["rows"], sig["pool"]
    ends = fz["l1f"] + fz["fut"]
    nidx = dc.notice_index(ends)
    by_sym = {}
    for r in rows:
        for s in dc.SETS:
            if dc.in_set(s, r["tag"], r["low"], r["fall"]):
                by_sym.setdefault(r["sym"], {}).setdefault(s, []).append(r["d"])
    jobs = [(p, {s: sorted(v) for s, v in d.items()}, nidx) for p, d in by_sym.items()]
    res, drops = {}, {}
    with ThreadPoolExecutor(8) as ex:
        for perp, out, dr in ex.map(d3_worker, jobs):
            res[perp] = out
            for k, v in dr.items():
                drops[k] = drops.get(k, 0) + v
    print("d3 priced symbols", len(res), "drops", drops, "seconds", round(time.time() - t0), flush=True)
    # matched control: per (day, hold) five perps of that day's pool (lowvol, not tagged, not falling)
    need, picks = {}, {}
    for perp, out in res.items():
        for rid, s, h in dc.d3_rules():
            if s in dc.JUDGED_SETS:
                for d, _ in out.get(rid, []):
                    need[(d, h)] = 1
    for (d, h) in need:
        p = sorted(pool.get(str(int(d)), []))
        picks[(d, h)] = random.Random(f"{dc.SEED}:d3:{int(d)}").sample(p, min(ff.N_CONTROL, len(p))) if p else []
    cjobs = {}
    for (d, h), ps in picks.items():
        for c in ps:
            cjobs.setdefault(c, []).append((d, h))
    cres = {}
    with ThreadPoolExecutor(8) as ex:
        for perp, out in ex.map(control_worker, [(c, sorted(set(j)), nidx) for c, j in cjobs.items()]):
            cres[perp] = out
    print("d3 control symbols", len(cres), "seconds", round(time.time() - t0), flush=True)

    def ctrl_total(d, h):
        v = [cres[c][(d, h)] for c in picks.get((d, h), []) if cres.get(c, {}).get((d, h)) is not None]
        return sum(v) / len(v) if len(v) >= 3 else None
    items, extra, tr_dump = [], {}, []
    for rid, s, h in dc.d3_rules():
        coin_tr = []
        for perp, out in res.items():
            for d, r in out.get(rid, []):
                tr = dc.make_short(dc.base_of(perp), d + HOUR, r["sim"], r["income"], ctrl_total(d, h) if s in dc.JUDGED_SETS else None)
                tr.update(day=d, perp=perp, notice=r["notice"], m1=r["m1"], fund_missing=r["fund_missing"])
                coin_tr.append(tr)
        coin_tr.sort(key=lambda t: (t["t"], t["sym"]))
        clus = dc.cluster(coin_tr, lambda t: t["day"])
        d = {"coin_trades": len(coin_tr), "through_notice": sum(1 for t in coin_tr if t["notice"]),
             "through_notice_mean": dc.mean_of([t["net"] for t in coin_tr if t["notice"]]), "not_through_mean": dc.mean_of([t["net"] for t in coin_tr if not t["notice"]]),
             "m1_fallbacks": sum(1 for t in coin_tr if t["notice"] and not t["m1"]), "fund_missing": sum(1 for t in coin_tr if t["fund_missing"]),
             "funding_income_mean": dc.mean_of([-t["fund"] for t in coin_tr])}
        items.append((rid, coin_tr, clus, s in dc.JUDGED_SETS))
        extra[rid] = d
        tr_dump += [[rid, t["perp"], t["day"], round(t["gross"], 6), round(-t["fund"], 6), t["x"], t["reason"], t.get("ctrl_net")] for t in coin_tr]
    table, gate_rows = evaluate(items, dc.CFG, l1f_tr)
    _, strict_rows = evaluate(items, dc.CFG_STRICT, l1f_tr)
    for rid in table:
        table[rid].update(extra[rid])
    killed = stage["kill1_d3"]["killed"]
    judged = judge(table, gate_rows, strict_rows, dc.CFG, dc.CFG_STRICT, "d3", killed)
    summary = {"killed_stage_a": killed, "rules_tested": len(items), "rules_judged": sum(1 for i in items if i[3]), "drops": drops, "table": table,
               "closest": closest(table, gate_rows), **judged}
    with gzip.open(os.path.join(out_dir, "d3_trades.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in tr_dump:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return summary


# ================================================================ D4 run
def _spot_month(sym, y, m, interval):
    got = bv.fetch("spot", "monthly", "klines", sym, (y, m), interval, bv.parse_kline)
    return None if got is None else {r[0]: (r[1], r[2], r[3], r[4]) for r in got}


@lru_cache(maxsize=16)
def spot_rows_1m(sym, y, m):
    return _spot_month(sym, y, m, "1m")


@lru_cache(maxsize=900)
def spot_rows_5m(sym, y, m):
    return _spot_month(sym, y, m, "5m")


def spot_bars(sym, t0, t1, interval="1m"):
    out = {}
    for y, m in bv.months(t0, t1):
        d = (spot_rows_1m if interval == "1m" else spot_rows_5m)(sym, y, m)
        if d is None:
            return None
        out.update({t: v for t, v in d.items() if t0 <= t < t1})
    return out


def spot_event_bars(sym, ts, span):
    t0, t1 = ts - 3600, ts + span
    failed = False
    for cand in (sym, "1000" + sym):
        b = spot_bars(cand + "USDT", t0, t1)
        if b is None:
            failed = True
        elif any(t < ts for t in b):
            return b, "spot"
    return None, "price_fetch_failed" if failed else "no_spot"


def process_event(e):
    sym, ts = e["sym"], e["ts"]
    span = max(dc.HOLDS_D4) + max(dc.DELAYS_D4) + 3 * 60 + 600
    bars, src = spot_event_bars(sym, ts, span)
    row = {**e, "price_src": src, "rules": {}, "dropped": []}
    if bars is None:
        return row
    picks = ff.pick_control(random.Random(f"{dc.SEED}:d4:{sym}:{int(ts)}"), sym)
    cb = {}
    for c in picks:
        b = spot_bars(c + "USDT", ts - 3600, ts + span, "5m")
        if b:
            cb[c] = b
    for rid, fam, h, d in dc.d4_rules():
        if fam != e["fam"]:
            continue
        s = kl.long_trade(bars, 60, ts, d, h)
        if not s:
            row["dropped"].append(rid)
            continue
        cg = kl.control_gross(cb, picks, 300, ts, d, h)
        row["rules"][rid] = [round(s["gross"], 6), None if cg is None else round(cg, 6), round(s["mfe"], 5), round(s["mae"], 5), s["reason"], s["te"], s["x"]]
    return row


def run_d4(out_dir, fz, l1f_tr):
    t0 = time.time()
    events = fz["d4_events"]
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(process_event, events))
    print("d4 rows", len(rows), "priced", sum(1 for r in rows if r["rules"]), "seconds", round(time.time() - t0), flush=True)
    with gzip.open(os.path.join(out_dir, "d4_rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    cov = {"events": len(events), "priced_rows": sum(1 for r in rows if r["rules"]), "by_src": {}, "dropped_rule_instances": sum(len(r["dropped"]) for r in rows)}
    for r in rows:
        cov["by_src"][r["price_src"]] = cov["by_src"].get(r["price_src"], 0) + 1
    items = []
    for rid, fam, h, d in dc.d4_rules():
        coin_tr = []
        for r in rows:
            v = r["rules"].get(rid)
            if v:
                tr = dc.make_long(r["sym"], r["ts"], {"te": v[5], "x": v[6], "gross": v[0], "mfe": v[2], "mae": v[3], "reason": v[4]}, v[1])
                tr["nid"] = r["nid"]
                coin_tr.append(tr)
        coin_tr.sort(key=lambda t: t["t"])
        items.append((rid, coin_tr, dc.cluster(coin_tr, lambda t: t["nid"]), True))
    table, gate_rows = evaluate(items, dc.CFG, l1f_tr)
    _, strict_rows = evaluate(items, dc.CFG_STRICT, l1f_tr)
    killed = dc.d4_counts(events)["killed"]
    judged = judge(table, gate_rows, strict_rows, dc.CFG, dc.CFG_STRICT, "d4", killed)
    return {"killed_stage_a": killed, "coverage": cov, "counts": dc.d4_counts(events), "rules_tested": len(items), "table": table,
            "closest": closest(table, gate_rows), **judged}


def main():
    out_dir, mode = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "events":
        stage_a(out_dir, sys.argv[3])
        return
    ddir, rows_path = sys.argv[3], sys.argv[4]
    fz = json.load(open(os.path.join(ddir, "events.json")))
    sig = json.load(gzip.open(os.path.join(ddir, "signals.json.gz"), "rt", encoding="utf-8"))
    stage = json.load(open(os.path.join(ddir, "stagea.json")))
    ffrows = [json.loads(line) for line in gzip.open(rows_path, "rt", encoding="utf-8")]
    l1f_tr = dc.l1f_exit_trades(ffrows)
    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": round(dc.MONTHS, 2), "l1f_trades": len(l1f_tr), "stage_a": {
        "hazard_train": stage["hazard"]["train"], "kill1_d3": stage["kill1_d3"], "d4": stage["d4"]}}
    summary["d3"] = run_d3(out_dir, fz, sig, stage, l1f_tr)
    dump(os.path.join(out_dir, "summary_d3.json"), summary)
    summary["d4"] = run_d4(out_dir, fz, l1f_tr)
    dump(os.path.join(out_dir, "summary.json"), summary)
    for lab in ("d3", "d4"):
        s = summary[lab]
        print(lab, "killed", s["killed_stage_a"], "tested", s["rules_tested"], "closest", s["closest"], "passed", s["event_gate"]["passed"], flush=True)
        for rid, v in s["table"].items():
            print(rid, "ok", v["ok"], (v.get("gate") or {}).get("reason"), "train", v["cluster_stats_by_split"]["train"], "val", v["cluster_stats_by_split"]["validation"],
                  "test", v["cluster_stats_by_split"]["test"], "corr", v["corr_l1f_exit_day"], flush=True)


if __name__ == "__main__":
    main()
