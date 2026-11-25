"""Forward paper ledger fundwin_okx_fwd (protocol_fundwin_okx_fwd_20261125.md). Runs on GitHub Actions only (workflow
fundwin_okx.yml, dispatched by keeper.yml about 30 minutes before each 8-hour settlement). Public OKX data, no keys, no orders.

    python research/studies/fundwin_okx_forward.py forward <state_dir>
    python research/studies/fundwin_okx_forward.py probe <out_dir>

forward: waits for T-15 / T-5 / T-1 minutes of the next 00:00 / 08:00 / 16:00 UTC settlement, reads OKX's predicted funding
rates (public/funding-rate instId=ANY) and the swap tickers, opens the paper trades of the six cohorts, closes them at T+1 minute,
reads the settled rates and appends <state_dir>/trades.jsonl, <state_dir>/preds.jsonl and rewrites state.json / summary.json.
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import okx_fund_fwd as of   # noqa: E402

OKX = "https://www.okx.com/api/v5"
UA = {"User-Agent": "Mozilla/5.0 tradelab-research", "Accept": "application/json"}
MAX_WAIT_S = 40 * 60


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(path, tries=3, timeout=20):
    last = None
    for k in range(tries):
        try:
            with urlopen(Request(OKX + path, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:   # noqa: BLE001
            last = e
            time.sleep(1 + k)
    log(f"GET {path.split('?')[0]} failed: {type(last).__name__} {last}")
    return None


def read_rates_and_books():
    """(rates, books): both requests at the same moment."""
    with ThreadPoolExecutor(2) as ex:
        fr = ex.submit(get, "/public/funding-rate?instId=ANY")
        tk = ex.submit(get, "/market/tickers?instType=SWAP")
        return of.parse_rates(fr.result()), of.parse_books(tk.result())


def realized(inst, T):
    time.sleep(0.22)                                   # 10 requests / 2 s
    return of.parse_realized(get(f"/public/funding-rate-history?instId={inst}&limit=5"), T)


def wait_until(t):
    d = t - time.time()
    if d > 0:
        time.sleep(d)


def forward(state_dir):
    sd = Path(state_dir)
    sd.mkdir(parents=True, exist_ok=True)
    state = json.loads((sd / "state.json").read_text()) if (sd / "state.json").exists() else {}
    ledger = of.Ledger(state.get("cohorts"))
    meta = state.setdefault("meta", {"settlements": 0, "missed": 0, "late_cohorts": 0, "no_rates": 0, "done": []})
    now = time.time()
    T = of.next_settlement(now, min_lead=60)
    if T - now > MAX_WAIT_S:
        log(f"next settlement {T} is {T - now:.0f}s away: nothing to do")
        meta["missed"] += 1
        return finish(sd, state, ledger, [], [])
    if T in meta["done"]:
        log("settlement already done")
        return finish(sd, state, ledger, [], [])
    open_trades, pred_rows = {}, []
    for minutes in of.ENTRY_MINUTES:
        at = T - minutes * 60
        if time.time() > at + 20:
            meta["late_cohorts"] += 1
            log(f"cohort -{minutes} missed (late by {time.time() - at:.0f}s)")
            continue
        wait_until(at)
        rates, books = read_rates_and_books()
        if not rates or not books:
            meta["no_rates"] += 1
            log(f"-{minutes}: no rates/books")
            continue
        for inst, (r, ft) in rates.items():
            if ft == T:
                pred_rows.append({"T": T, "inst": inst, "minutes": minutes, "pred": r})
        for cid, m, thr in of.COHORTS:
            if m == minutes:
                open_trades[cid] = of.entries(rates, books, T, thr)
                log(f"-{minutes} thr {thr}: {len(open_trades[cid])} trades of {sum(1 for _, (_, ft) in rates.items() if ft == T)} swaps settling at T")
    wait_until(T + 60)
    _, exit_books = read_rates_and_books()
    insts = sorted({e["inst"] for es in open_trades.values() for e in es} | {r["inst"] for r in pred_rows if abs(r["pred"]) >= 0.0005})
    wait_until(T + 100)
    settled = {}
    for inst in insts:
        v = realized(inst, T)
        if v is not None:
            settled[inst] = v
    log(f"settled rates: {len(settled)} of {len(insts)} instruments")
    trades = []
    for cid, es in open_trades.items():
        unit = []
        for e in es:
            if e["inst"] in exit_books and e["inst"] in settled:
                unit.append(of.settle_trade(e, exit_books[e["inst"]], settled[e["inst"]], T, cid))
        trades.extend(unit)
        ledger.add_unit(cid, unit)
    for r in pred_rows:
        r["settled"] = settled.get(r["inst"])
    meta["settlements"] += 1
    meta["done"] = (meta["done"] + [T])[-50:]
    return finish(sd, state, ledger, trades, [r for r in pred_rows if r["inst"] in settled])


def finish(sd, state, ledger, trades, pred_rows):
    state["cohorts"] = ledger.dump()
    (sd / "state.json").write_text(json.dumps(state))
    with open(sd / "trades.jsonl", "a") as f:
        for t in trades:
            f.write(json.dumps(t, separators=(",", ":")) + "\n")
    with open(sd / "preds.jsonl", "a") as f:
        for r in pred_rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    rows = []
    if (sd / "preds.jsonl").exists():
        rows = [json.loads(x) for x in (sd / "preds.jsonl").read_text().splitlines() if x.strip()]
    summary = {"updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "meta": {k: v for k, v in state["meta"].items() if k != "done"},
               "cohorts": ledger.verdicts(), "tracking": of.tracking(rows)}
    (sd / "summary.json").write_text(json.dumps(summary, indent=1))
    log(json.dumps(summary["cohorts"])[:1500])
    return summary


def probe(out_dir):
    """One look at the three endpoints the ledger needs: what OKX answers from a GitHub runner."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fr, tk = get("/public/funding-rate?instId=ANY"), get("/market/tickers?instType=SWAP")
    rates, books = of.parse_rates(fr), of.parse_books(tk)
    hist = get("/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=3")
    when = {}
    for _, ft in rates.values():
        when[ft] = when.get(ft, 0) + 1
    big = sorted(((abs(r), i, r) for i, (r, _) in rates.items()), reverse=True)[:10]
    res = {"funding_any_code": (fr or {}).get("code"), "n_rates": len(rates), "n_books": len(books),
           "funding_time_counts": {str(k): v for k, v in sorted(when.items())}, "top_rates": [(i, r) for _, i, r in big],
           "sample_raw": ((fr or {}).get("data") or [None])[0], "history_raw": (hist or {}).get("data"),
           "next_settlement": of.next_settlement(time.time()), "now": int(time.time())}
    (out / "probe.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("forward", "probe"):
        sys.exit("usage: fundwin_okx_forward.py forward|probe <dir>")
    (forward if sys.argv[1] == "forward" else probe)(sys.argv[2])
