"""Locked 8-K / Form 4 event study runner.

Rules are in protocol.md and were fixed before the first result: entry at the open of the first session that
starts at/after the SEC acceptance timestamp, hold 1/3/5 sessions, exit at the close, costs on both sides,
a random same-class control bought at the same time, splits by date. Prints gross and net.
"""
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from core import data, news_backtest as nb, universe   # noqa: E402


def fetch_bars(symbol, years="10y"):
    try:
        ch = data.chart(symbol, years, "1d")
        return ch["bars"]
    except Exception as e:                     # a missing symbol is a gap, not a crash
        print(f"  bars failed {symbol}: {e}", file=sys.stderr)
        return []


def run(symbols, since="2018-01-01", forms=("8-K",), horizons=nb.HORIZONS, limit=0):
    tick = nb.sec_company_tickers()
    print(f"SEC ticker map: {len(tick)} symbols; study set {len(symbols)}", file=sys.stderr)
    bars = {}
    for s in symbols:
        bars[s] = fetch_bars(s)
        print(f"  {s}: {len(bars[s])} bars", file=sys.stderr)
    pool = {s: b for s, b in bars.items() if len(b) > 30}
    rows = []
    for s in symbols:
        if s not in pool or s not in tick:
            continue
        try:
            filings = nb.sec_filings(tick[s], forms=forms, since=since)
        except Exception as e:
            print(f"  filings failed {s}: {e}", file=sys.stderr)
            continue
        print(f"  {s}: {len(filings)} filings", file=sys.stderr)
        for f in filings:
            for h in horizons:
                r = nb.event_return(pool[s], f["ts"], h)
                if not r:
                    continue
                rng = random.Random(f"{s}:{f['ts']}")
                ctrl = nb.pick_control(s, universe.asset_class(s), pool, rng)
                if not ctrl:
                    continue
                c = nb.event_return(pool[ctrl], f["ts"], h)
                if not c:
                    continue
                rows.append({"symbol": s, "control": ctrl, "form": f["form"], "accepted": f["accepted"],
                             "ts": f["ts"], "horizon": h, "split": nb.split_of(f["ts"]),
                             "gross": r["gross"], "ctrl_gross": c["gross"],
                             "asset_class": universe.asset_class(s)})
                if limit and len(rows) >= limit:
                    return rows
    return rows


def report(rows, top=5):
    """Table by horizon and split at 1x cost, the same at 2x cost, and the top/bottom symbol contributors."""
    out = {"n_rows": len(rows), "by_horizon": {}, "by_horizon_split": {}, "by_horizon_2x": {},
           "by_horizon_split_2x": {}, "contributors": {}}
    for h in sorted({r["horizon"] for r in rows}):
        sub = [r for r in rows if r["horizon"] == h]
        out["by_horizon"][h] = nb.summarize(sub)
        out["by_horizon_2x"][h] = nb.summarize(sub, cost_mult=2.0)
        for sp in ("train", "validation", "test"):
            s2 = [r for r in sub if r["split"] == sp]
            if s2:
                out["by_horizon_split"][f"{h}:{sp}"] = nb.summarize(s2)
                out["by_horizon_split_2x"][f"{h}:{sp}"] = nb.summarize(s2, cost_mult=2.0)
        con = sorted(nb.contributions(sub), key=lambda a: a["sum_diff"])
        out["contributors"][h] = {"worst": con[:top], "best": con[::-1][:top]}
    return out


def brief(res) -> str:
    """One line per horizon/split for a human; the JSON on stdout is the full record."""
    lines = [f"rows {res['n_rows']}"]
    for key, s in list(res["by_horizon"].items()) + list(res["by_horizon_split"].items()):
        if not s.get("n"):
            continue
        s2 = res["by_horizon_2x"].get(key) or res["by_horizon_split_2x"].get(key) or {}
        lines.append(f"H{key} n={s['n']} gross={s['mean_gross']:+.3%} net={s['mean_net']:+.3%} "
                     f"diff={s['mean_diff']:+.3%} p_diff={s['p_diff']:.2f} p_diff_block={s['p_diff_block']:.2f} "
                     f"net2x={s2.get('mean_net', float('nan')):+.3%} diff2x={s2.get('mean_diff', float('nan')):+.3%}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="", help="comma separated; empty = first 40 large caps")
    ap.add_argument("--since", default="2018-01-01")
    ap.add_argument("--forms", default="8-K", help="comma separated SEC form types")
    ap.add_argument("--horizons", default="1,3,5")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--from-file", default="", help="re-report the rows of an earlier results JSON; no network")
    ap.add_argument("--quiet", action="store_true", help="no human summary on stderr")
    a = ap.parse_args()
    if a.from_file:
        with open(a.from_file) as f:
            old = json.load(f)
        rows = old["rows"]
        res = report(rows)
        keep = {k: old["summary"].get(k) for k in ("symbols", "since", "forms", "horizons")}
        res.update(keep, source=os.path.basename(a.from_file))
    else:
        symbols = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or universe.STOCKS[:40]
        forms = tuple(x.strip() for x in a.forms.split(",") if x.strip())
        horizons = tuple(int(x) for x in a.horizons.split(",") if x.strip())
        t0 = time.time()
        rows = run(symbols, a.since, forms, horizons, a.limit)
        res = report(rows)
        res.update(seconds=round(time.time() - t0, 1), symbols=symbols, since=a.since,
                   forms=list(forms), horizons=list(horizons))
        out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    f"results_{time.strftime('%Y%m%d_%H%M')}.json")
        with open(out, "w") as f:
            json.dump({"summary": res, "rows": rows}, f, ensure_ascii=False)
        if not a.quiet:
            print(f"rows: {len(rows)} -> {out}", file=sys.stderr)
    print(json.dumps(res, ensure_ascii=False, indent=1))   # stdout is JSON only, safe to pipe
    if not a.quiet:
        print(brief(res), file=sys.stderr)


if __name__ == "__main__":
    main()
