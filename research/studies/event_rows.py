"""Recompute per-event rows for L1 (listings), L1f/L1e (Binance delist short) and L1g (Alpha removal short) with the
existing study code, keep them as jsonl.gz (artifacts expire), and report mean, sd, s, events/month and x = N * s^2 per
component. Runs on GitHub Actions only (workflow event_book.yml, mode rows).

    python research/studies/event_rows.py <out_dir> [component,...]      components: l1, l1f, l1g

Output: <out_dir>/rows/<component>.jsonl.gz (one event per line, with the study's `ret` per horizon plus `path`: the
coin's 1-minute close divided by the entry close for minutes 1..240, None where a bar is missing) and
<out_dir>/summary.json. `net` is the study's abnormal (coin minus BTC) return after 0.6% round-trip cost; `net_stop` is
the coin-only return with a 25% stop on 1-minute closes for the shorts (fill at the stop plus 0.5% slip), after cost.
"""
import gzip
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

MONTHS = 34            # 2024-01-01 .. 2026-10-31
HOLD_MIN = 240
STOP = 0.25
STOP_SLIP = 0.005
COSTS = {"l1": 0.006, "l1f": 0.006 + 0.001, "l1g": 0.006 + 0.001}
SIDES = {"l1": 1, "l1f": -1, "l1g": -1}
STUDY_OF = {"l1": "l1_listings", "l1f": "l1e_binance_delist", "l1g": "l1g_alpha_remove"}


def stats(values: list, months: float = MONTHS) -> dict:
    """mean, sd, s = mean/sd, events per month and x = N * s^2 of per-event net returns."""
    n = len(values)
    if n < 2:
        return {"n": n}
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    s = m / sd if sd > 0 else 0.0
    per_month = n / months
    return {"n": n, "mean": round(m, 5), "sd": round(sd, 5), "s": round(s, 4), "per_month": round(per_month, 3),
            "x": round(per_month * s * s, 4), "hit": round(sum(1 for v in values if v > 0) / n, 3)}


def stop_net(path: list, side: int, cost: float, stop: float = STOP, slip: float = STOP_SLIP):
    """Coin-only return of a position held for the whole path (minute 240) or stopped at `stop` on a 1-minute close."""
    last = None
    for r in path:
        if r is None:
            continue
        last = r
        if side * (r - 1) <= -stop:
            return -stop - slip - cost
    return None if last is None else side * (last - 1) - cost


def with_path(row: dict, venue_bars, close_at) -> dict:
    v = row.get("price_venue") or "binance"
    got = venue_bars(v, row["symbol"], row["ts"])
    if not got:
        return {**row, "path": None}
    m1 = got[1]
    t0 = row["ts"] + 60
    p0 = close_at(m1, t0, 60)
    if not p0:
        return {**row, "path": None}
    path = []
    for k in range(1, HOLD_MIN + 1):
        p = close_at(m1, t0 + 60 * k, 60)
        path.append(round(p / p0, 5) if p else None)
    return {**row, "path": path}


def summarize(comp: str, rows: list) -> dict:
    side, cost = SIDES[comp], COSTS[comp]
    out = {"component": comp, "rows": len(rows)}
    by_split = {}
    for h in ("15m", "1h", "4h", "1d", "7d"):
        v = [r["ret"][h]["net"] for r in rows if h in r["ret"]]
        out[f"net_{h}"] = stats(v)
    v4 = [(r["split"], r["ret"]["4h"]["net"]) for r in rows if "4h" in r["ret"]]
    for sp in ("train", "validation", "test"):
        by_split[sp] = stats([v for s, v in v4 if s == sp])
    out["net_4h_by_split"] = by_split
    sn = [stop_net(r["path"], side, cost) for r in rows if r.get("path")]
    sn = [v for v in sn if v is not None]
    out["net_stop_4h"] = stats(sn)
    from core import event_book as eb
    out["sizing"] = eb.frozen_weight(sn, STOP)      # half-Kelly weight on the stop-adjusted 4h returns, loss cap 25%
    out["stopped_share"] = round(sum(1 for r in rows if r.get("path") and any(
        x is not None and side * (x - 1) <= -STOP for x in r["path"])) / max(1, len(rows)), 3)
    if rows:
        out["with_path"] = sum(1 for r in rows if r.get("path"))
    return out


def run_component(comp: str, out_dir: str) -> dict:
    from research.studies import run as R
    from core import screens as sc
    t0 = time.time()
    summ, rows = R.STUDIES[STUDY_OF[comp]]([])
    rows = [with_path(r, R._venue_bars, sc.close_at) for r in rows]
    os.makedirs(os.path.join(out_dir, "rows"), exist_ok=True)
    with gzip.open(os.path.join(out_dir, "rows", f"{comp}.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str, separators=(",", ":")) + "\n")
    res = summarize(comp, rows)
    res["study_summary_keys"] = {k: summ.get(k) for k in ("events", "rows", "skipped", "gaps", "by_venue")}
    res["seconds"] = round(time.time() - t0, 1)
    return res


def main():
    out_dir = sys.argv[1]
    comps = (sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else ["l1", "l1f", "l1g"])
    summary = {"run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "months": MONTHS, "components": {}}
    for c in comps:
        try:
            summary["components"][c] = run_component(c, out_dir)
        except Exception as e:  # noqa: BLE001  keep the other components
            summary["components"][c] = {"error": repr(e)[:300]}
        print(json.dumps(summary["components"][c], default=str), flush=True)
    xs = [v.get("net_4h", {}).get("x", 0) for v in summary["components"].values() if isinstance(v, dict)]
    summary["x_sum_4h_net"] = round(sum(xs), 4)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)


if __name__ == "__main__":
    main()
