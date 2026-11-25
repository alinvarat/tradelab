"""Family 5 runner (Actions only): fetch | events | sim | merge. See core/fxgold_tick.py and protocol_fxgold_tick_20261125.md.
  fetch SYM YEAR OUT          Dukascopy 1m bid/ask candles of one symbol-year -> OUT/SYM_YEAR.gz (+ .json status)
  events SYM EVENTS.csv OUT   per-second bid/ask from ticks around each calendar release -> OUT/events_SYM.json.gz
  sim SYM DATA OUT            all pre-registered rules on one symbol: cells_SYM.json, rows_SYM.jsonl.gz
  merge DIR                   stage-0 survivors: evaluation, Holm, criteria -> summary.json"""
import csv
import glob
import gzip
import json
import os
import sys
import time

from core import fxgold_data as fd
from core import fxgold_tick as ft
from core import sweep_stats as ss

R6 = ("gross", "cost", "net", "mfe", "mae")


def do_fetch(sym, chunk, start, end, out):
    from datetime import date
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    n = fd.fetch_range(sym, date.fromisoformat(start), date.fromisoformat(end), f"{out}/{sym}_{chunk}.gz", workers=3)
    n["sec"] = round(time.time() - t0, 1)
    json.dump(n, open(f"{out}/{sym}_{chunk}.json", "w"))
    fd.log(sym, chunk, n)
    if n["fail"]:
        raise SystemExit(f"{n['fail']} days failed: not cached, rerun fetches this chunk again")


def do_events(sym, evcsv, year, out):
    from concurrent.futures import ThreadPoolExecutor
    os.makedirs(out, exist_ok=True)
    evs = [r for r in csv.DictReader(open(evcsv))]
    from datetime import datetime, timezone
    items = [(int(datetime.strptime(r["utc_datetime"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp()), r["event"]) for r in evs]
    items = [x for x in items if datetime.fromtimestamp(x[0], timezone.utc).year == int(year) and x[0] < ft.BOUNDS["test"][1]]

    def one(x):
        sec, st = fd.fetch_ticks_window(sym, x[0], 120, 1200)
        return {"ts": x[0], "name": x[1], "status": st, "sec": sec or []}
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(one, items))
    cnt = {}
    for r in res:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    fd.log(sym, "events", len(items), cnt)
    with gzip.open(f"{out}/events_{sym}_{year}.json.gz", "wt") as f:
        json.dump(res, f)


def cid(rid, sym):
    return f"{rid}|{sym}"


def slim(t):
    d = {k: (round(v, 7) if k in R6 else v) for k, v in t.items() if k not in ("fund", "pe", "sp_in", "rule", "sym")}
    d["pe"] = t["pe"]
    d["sp"] = round(t["sp_in"], 6)
    return d


def do_sim(sym, data, out):
    os.makedirs(out, exist_ok=True)
    D = fd.load_bars(glob.glob(f"{data}/{sym}_*.gz"), sym)
    fd.log(sym, "bars", len(D["ts"]), "dropped", D["bad"])
    if len(D["ts"]) < (250_000 if os.environ.get("FXGOLD_PILOT") else 1_500_000):
        raise SystemExit(f"{sym}: only {len(D['ts'])} bars, data not complete")
    events = []
    for ep in sorted(glob.glob(f"{data}/events_{sym}_*.json.gz")):
        events += [e for e in json.load(gzip.open(ep, "rt")) if e["status"] == "ok"]
    sig = {}
    for e in events:
        j = ft.ix(D, e["ts"] - 60)
        sg = ft._sigma1(D, j)
        if sg:
            sig[e["ts"]] = sg
    cells, rows = {}, gzip.open(f"{out}/rows_{sym}.jsonl.gz", "wt")
    for rid, spec in ft.build_rules().items():
        if sym not in spec["syms"]:
            continue
        t0 = time.time()
        if spec["fam"] == "C":
            mode, th, hold = spec["args"]
            mk = lambda seed: ft.macro_trades(events, sym, rid, mode, th, hold, sig) if seed is None else \
                _flip(ft.macro_trades(events, sym, rid, mode, th, hold, sig), seed)
        else:
            mk = lambda seed: ft.trades_for(D, sym, rid, spec, seed)
        trades = mk(None)
        ok, info = ft.gate_cell(sym, trades)
        cell = {"rule": rid, "sym": sym, "fam": spec["fam"], "gate_ok": ok, "n_all": len(trades), "gate": info}
        if ok:
            ctrl = []
            for s in range(ft.N_CTRL):
                ct = mk(1000 + s)
                ctrl.append({"val": ft.mean_net(ct, *ft.BOUNDS["validation"]), "test": ft.mean_net(ct, *ft.BOUNDS["test"])})
            cell["ctrl"] = ctrl
        cells[cid(rid, sym)] = cell
        rows.write(json.dumps({"cell": cid(rid, sym), "trades": [slim(t) for t in trades]}) + "\n")
        fd.log(sym, rid, len(trades), ok, info.get("reason", "ok"), round(time.time() - t0, 1))
    rows.close()
    json.dump(cells, open(f"{out}/cells_{sym}.json", "w"))


def _flip(trades, seed):
    """Macro control: same releases, random side. Re-simulate with the side flipped at random is not possible from net alone, so the
    control re-runs the entry with random sign using the stored quotes: here we use the exact mirror when the draw is -1 (stop distance differs
    little) -- implemented by reversing gross and keeping cost."""
    import random
    rng = random.Random(seed)
    out = []
    for t in trades:
        if rng.random() < 0.5:
            t = dict(t, gross=-t["gross"], net=-t["gross"] - t["cost"])
        out.append(t)
    return out


def do_merge(d):
    cells, rows = {}, {}
    for p in glob.glob(f"{d}/cells_*.json"):
        cells.update(json.load(open(p)))
    for p in glob.glob(f"{d}/rows_*.jsonl.gz"):
        for line in gzip.open(p, "rt"):
            o = json.loads(line)
            if cells[o["cell"]]["gate_ok"]:
                rows[o["cell"]] = o["trades"]
    ev = []
    gate_fail = {}
    for c, cell in cells.items():
        if not cell["gate_ok"]:
            r = cell["gate"].get("reason", "?").split(" ")[0:3]
            key = " ".join(r)
            gate_fail[key] = gate_fail.get(key, 0) + 1
            continue
        tr = rows[c]
        rule = {"size": ft.rule_size(cell["sym"])}
        e = ss.evaluate(tr, rule, ft.BOUNDS)
        va = cell["ctrl"]
        e.update(id=c, status="ok", gate=cell["gate"], lev=ft.LEV[cell["sym"]], family="fxgold_tick")
        cv = max((x["val"] or -1) for x in va)
        e["ctrl_val_max"] = cv
        e["extra_criteria"] = {"val_beats_control": (e["validation"]["mean"] or -1) > cv}
        ev.append(e)
    fam = ss.judge_family(ev, ft.CFG)
    ev.sort(key=ss.closeness_key)
    top = [ss.compact(r, "fxgold_tick") for r in ev[:15]]
    best_x = sorted(((r["gate"]["x"], r["id"]) for r in ev), reverse=True)[:5]
    byfam = {}
    for cell in cells.values():
        k = cell["fam"]
        byfam.setdefault(k, {"cells": 0, "gate_ok": 0})
        byfam[k]["cells"] += 1
        byfam[k]["gate_ok"] += 1 if cell["gate_ok"] else 0
    # best gate-failed cells by x (informational)
    near = sorted(((c["gate"].get("x", -9), k, c["gate"].get("reason", "")) for k, c in cells.items()), reverse=True)[:8]
    summ = {"cells": len(cells), "gate_ok": len(ev), "passed": sum(1 for r in ev if r["passed"]), "family": fam,
            "gate_fail_reasons": gate_fail, "by_family": byfam, "top": top, "best_x_survivors": best_x, "best_x_all": near,
            "bounds": ft.BOUNDS}
    json.dump(summ, open(f"{d}/summary.json", "w"), indent=1, default=str)
    json.dump({k: {kk: vv for kk, vv in v.items()} for k, v in cells.items()}, open(f"{d}/cells_all.json", "w"))
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    if os.environ.get("FXGOLD_PILOT"):
        ft.use_pilot()
    m = sys.argv[1]
    {"fetch": do_fetch, "events": do_events, "sim": do_sim, "merge": do_merge}[m](*sys.argv[2:])
