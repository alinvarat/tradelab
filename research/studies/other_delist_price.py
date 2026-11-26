"""Price other exchanges' own-spot delist shorts under protocol_other_spot_delist_20261127.md (one rule: 4 h, 60 s, 25% stop, 0.6% + 0.1%
borrow). Called by other_delist.py mode price. Own-book 1-minute bars: Bybit spot trade archive (bars built from trades), KuCoin spot candles,
OKX spot candles. Control = the same coin on the same exchange 24 h earlier."""
import gzip
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from core import forced_flow as ff
from core import sweep_stats as ss
from research.studies import forced_flow as FF
from research.studies import other_delist as OD

HOLD, DELAY = 14400, 60
STABLES = {"USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "IDRT", "VAI", "UST", "USTC", "EURT", "PYUSD", "USDE"}


def bars_bybit_spot(sym, t0, t1):
    out, day = {}, int(t0) - int(t0) % 86400
    while day < t1:
        g = time.gmtime(day)
        st, t = OD.get(f"https://public.bybit.com/spot/{sym}USDT/{sym}USDT_{g.tm_year}-{g.tm_mon:02d}-{g.tm_mday:02d}.csv.gz", tries=2, raw_gz=True)
        if t is None:
            if st in (403, 404):
                day += 86400
                continue
            return None
        lines = t.splitlines()
        head = lines[0].lower().split(",") if lines else []
        it, ip = (head.index("timestamp") if "timestamp" in head else 1), (head.index("price") if "price" in head else 2)
        for ln in lines[1:]:
            f = ln.split(",")
            try:
                ts, px = float(f[it]), float(f[ip])
            except (ValueError, IndexError):
                continue
            ts = ts / 1000 if ts > 1e11 else ts
            m = int(ts // 60 * 60)
            if not t0 <= m < t1:
                continue
            o = out.get(m)
            if o is None:
                out[m] = [px, px, px, px, ts]
            else:
                o[1], o[2] = max(o[1], px), min(o[2], px)
                if ts >= o[4]:
                    o[3], o[4] = px, ts
        day += 86400
    return {m: tuple(v[:4]) for m, v in out.items()}


def bars_kucoin_spot(sym, t0, t1):
    out, t = {}, int(t0)
    while t < t1:
        te = min(int(t1), t + 1400 * 60)
        st, d = OD.jget(f"https://api.kucoin.com/api/v1/market/candles?type=1min&symbol={sym}-USDT&startAt={t}&endAt={te}")
        if d is None:
            return {} if st in (400, 404) else None
        for k in d.get("data") or []:
            out[int(k[0])] = (float(k[1]), float(k[3]), float(k[4]), float(k[2]))      # time, open, close, high, low
        t = te
        time.sleep(0.12)
    return {m: v for m, v in out.items() if t0 <= m < t1}


def bars_okx_spot(sym, t0, t1):
    out, after = {}, int(t1 * 1000)
    for _ in range(40):
        time.sleep(0.12)
        st, d = OD.jget(f"https://www.okx.com/api/v5/market/history-candles?instId={sym}-USDT&bar=1m&after={after}&limit=100")
        if d is None:
            return None
        rows = d.get("data") or []
        if d.get("code") != "0" or not rows:
            break
        for k in rows:
            out[int(k[0]) // 1000] = (float(k[1]), float(k[2]), float(k[3]), float(k[4]))
        oldest = min(int(k[0]) for k in rows)
        if oldest / 1000 <= t0:
            break
        after = oldest
    return {m: v for m, v in out.items() if t0 <= m < t1}


FETCH = {"bybit": bars_bybit_spot, "kucoin": bars_kucoin_spot, "okx": bars_okx_spot}


def price_event(ex, e):
    ts, sym = e["ts"], e["sym"]
    span = HOLD + DELAY + 900
    bars = FETCH[ex](sym, ts - 3600, ts + span)
    row = {"fam": "os_" + ex, "ex": ex, "sym": sym, "ts": ts, "src": ex, "title": e["title"][:100], "overlap_l1f": False, "rules": {}}
    if not bars:
        row["status"] = "failed" if bars is None else "no_bars"
        return row
    if not any(t < ts for t in bars):
        row["status"] = "no_bar_before_notice"
        return row
    s = ff.short_trade(bars, 60, ts, DELAY, HOLD)
    if not s:
        row["status"] = "no_entry_or_exit_bar"
        return row
    cb = FETCH[ex](sym, ts - 3600 - 86400, ts + span - 86400)
    cs = ff.short_trade({t + 86400: v for t, v in cb.items()}, 60, ts, DELAY, HOLD) if cb else None
    row["status"] = "priced"
    row["rules"][ff.rule_id(row["fam"], HOLD, DELAY)] = [round(s["gross"], 6), None if not cs else round(cs["gross"], 6), round(s["mfe"], 5),
                                                         round(s["mae"], 5), s["reason"], s["te"], s["x"]]
    return row


def summarize(fam, rows):
    rid = ff.rule_id(fam, HOLD, DELAY)
    sub = [dict(r, fam=fam, rules={rid: list(r["rules"].values())[0]}) for r in rows if r["rules"]]
    res = {"fam": fam, "events_priced": len(sub)}
    tr = FF.trades_of(sub, rid, fam, HOLD)
    if not tr:
        return res, []
    res["all"] = ff.stats([t["net"] for t in tr], ff.MONTHS)
    res["notice_level_all"] = FF.notice_level(tr, ff.MONTHS)
    res["by_split"] = {k: ff.stats([t["net"] for t in ss.in_split(tr, *ff.BOUNDS[k])], (b - a) / 86400 / 30.4375) for k, (a, b) in ff.BOUNDS.items()}
    res["control_mean"] = FF.ctrl_mean(tr)
    res["placebo_mean"] = ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in tr])
    res["mean_2x_cost"] = ss.mean([t["net"] - t["cost"] - t["fund"] for t in tr])
    res["stopped"] = sum(1 for t in tr if t["reason"] == "stop")
    table, gate_rows = FF.evaluate_family(fam, sub)
    res["stage0"] = {"ok": table[rid]["ok"], "gate": table[rid]["gate"]}
    for r in gate_rows:
        r["family"] = fam
    return res, gate_rows


def run(out_dir, notices_path, frozen_path):
    t_start = time.time()
    feeds = json.load(open(notices_path))["events"]
    l1f = json.load(open(frozen_path))["l1f"]
    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "coverage": {}, "tests": {}}
    jobs = []
    for ex in ("bybit", "kucoin", "okx"):
        evs = ff.dedupe([{"fam": "os_" + ex, "sym": r["sym"], "ts": r["ts"], "title": r["title"]} for r in feeds.get(ex, [])])
        cov = {"events": len(evs), "stable": 0, "overlap_l1f": 0}
        for e in evs:
            if e["sym"] in STABLES:
                cov["stable"] += 1
            elif ff.overlaps_l1f(e, l1f):
                cov["overlap_l1f"] += 1
            else:
                jobs.append((ex, e))
        summary["coverage"][ex] = cov
    print("jobs", len(jobs), flush=True)

    def safe(j):
        try:
            r = price_event(*j)
        except Exception as x:  # noqa: BLE001
            r = {"fam": "os_" + j[0], "ex": j[0], "sym": j[1]["sym"], "ts": j[1]["ts"], "rules": {}, "status": "error:" + type(x).__name__}
        print("priced", j[0], r["sym"], r["status"], flush=True)
        return r
    with ThreadPoolExecutor(4) as ex_:
        rows = list(ex_.map(safe, jobs))
    with gzip.open(os.path.join(out_dir, "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    all_gate = []
    for ex in ("bybit", "kucoin", "okx"):
        er = [r for r in rows if r["ex"] == ex]
        c = summary["coverage"][ex]
        for st in {r["status"] for r in er}:
            c["rows_" + st] = sum(1 for r in er if r["status"] == st)
        res, g = summarize("os_" + ex, er)
        summary["tests"][ex] = res
        all_gate += g
    res, g = summarize("os_pool", [r for r in rows])
    summary["tests"]["pool"] = res
    all_gate += g
    summary["rules_tested"] = 4                                        # bybit, kucoin, okx, pool (gate, mexc, bitget: no reachable feed)
    fam_info = ss.judge_family(all_gate, ff.CFG) if all_gate else {"holm_m": 0}
    summary["event_gate"] = {"stage0_survivors": len(all_gate), "holm": fam_info, "passed": [r["id"] for r in all_gate if r.get("passed")],
                             "evaluated": [dict(ss.compact(r, r["family"]), criteria=r["criteria"]) for r in all_gate]}
    summary["seconds"] = round(time.time() - t_start)
    summary["errors"] = dict(OD.ERR)
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w"), indent=1, default=str)
    for k, v in summary["tests"].items():
        print(k, json.dumps({a: v.get(a) for a in ("events_priced", "all", "by_split", "control_mean", "placebo_mean", "mean_2x_cost")}, default=str))
        print("   stage0", v.get("stage0", {}).get("ok"), v.get("stage0", {}).get("gate", {}).get("reason"), flush=True)
