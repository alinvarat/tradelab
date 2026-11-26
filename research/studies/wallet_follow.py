"""Q1 wallet-follow study: I/O. Pure logic in wallet_follow_core.py. Runs on GitHub Actions only (wallet_follow.yml).
Usage: python research/studies/wallet_follow.py probe <out_dir>
Probe protocol: research/studies/protocol_wallet_follow_probe_20261127.md (counts only: no P&L, no returns, no win rates)."""
import calendar
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wallet_follow_core as wc   # noqa: E402

DATA = "https://data-api.polymarket.com/v2"
GAMMA = "https://gamma-api.polymarket.com"
HL = "https://api.hyperliquid.xyz/info"
UA = {"User-Agent": "Mozilla/5.0 tradelab-research"}
STATS = {"calls": 0, "429": 0, "errors": 0, "sec": 0.0}
LOCK = threading.Lock()
T0 = time.time()
BUDGET_S = 150 * 60            # stop starting new work after 150 minutes

FRAME_DATES = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in range(1, 13) if (y, m) <= (2026, 10)]   # 22 windows
WINDOW_S = 3600
FRAME_PAGES = 3
FRAME_MIN_USD = 500.0
SAMPLE_WALLETS = 200
PAGE_CAP = 25
HOT_CAP_WALLETS = 8             # parallel workers


def get(url, tries=4, timeout=30, body=None):
    """(status, parsed json or text head). Retries 429/5xx with backoff; counts calls."""
    last = (None, "")
    for k in range(tries):
        t0 = time.time()
        try:
            req = Request(url, data=json.dumps(body).encode() if body is not None else None,
                          headers=dict(UA, **({"Content-Type": "application/json"} if body is not None else {})))
            with urlopen(req, timeout=timeout) as r:
                raw, st = r.read(), r.status
            with LOCK:
                STATS["calls"] += 1
                STATS["sec"] += time.time() - t0
            try:
                return st, json.loads(raw)
            except ValueError:
                return st, raw[:200].decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            head = ""
            try:
                head = e.read()[:200].decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                head = str(e)[:160]
            with LOCK:
                STATS["calls"] += 1
                STATS["sec"] += time.time() - t0
                if code == 429:
                    STATS["429"] += 1
                else:
                    STATS["errors"] += 1
            last = (code or type(e).__name__, head)
            if code in (400, 404, 410, 422):
                return last
            time.sleep(1.5 * (k + 1))
    return last


def shape(x, depth=0):
    if isinstance(x, dict):
        return {k: (shape(v, depth + 1) if depth < 2 else type(v).__name__) for k, v in list(x.items())[:16]}
    if isinstance(x, list):
        return {"len": len(x), "first": shape(x[0], depth + 1) if x and depth < 3 else None}
    return x if not isinstance(x, str) else x[:120]


def ts_of(day, hh=12):
    return int(calendar.timegm(time.strptime(day, "%Y-%m-%d"))) + hh * 3600


def rows_of(body):
    return (body.get("data") if isinstance(body, dict) else None) or []


def page_all(url, cap, extra=""):
    """Cursor-page a v2 route (newest first). Returns (rows, pages, truncated, last_status)."""
    rows, cur, pages, st = [], "", 0, None
    while pages < cap:
        st, d = get(url + extra + (f"&cursor={cur}" if cur else ""))
        if not isinstance(d, dict):
            return rows, pages, False, st
        rows += rows_of(d)
        pages += 1
        pg = d.get("pagination") or {}
        cur = pg.get("next_cursor") or ""
        if not (pg.get("has_more") and cur):
            return rows, pages, False, st
    return rows, pages, True, st


def endpoints(out):
    """Status and shape of every candidate route, one call each (counts only)."""
    now = int(time.time())
    probes = {
        "status": f"{DATA}/status",
        "trades_global_window": f"{DATA}/trades?{urlencode({'start': ts_of('2026-09-01'), 'end': ts_of('2026-09-01') + 600, 'limit': 5})}",
        "trades_global_recent": f"{DATA}/trades?limit=5",
        "leaderboard_shape_only": f"{DATA}/leaderboard?limit=3",
        "user_stats_shape_only": None, "positions_status_closed": None,
    }
    res = {}
    for k, u in probes.items():
        if u:
            st, b = get(u)
            res[k] = {"status": st, "shape": shape(b)}
    g = rows_of(get(probes["trades_global_recent"])[1])
    w = (g[0].get("proxy_wallet") if g else None)
    res["sample_row"] = g[0] if g else None
    if w:
        for k, u in {"user_trades": f"{DATA}/trades?user={w}&limit=3", "user_activity": f"{DATA}/activity?user={w}&limit=3",
                     "user_positions": f"{DATA}/positions?user={w}&limit=3", "user_positions_closed": f"{DATA}/positions?user={w}&status=closed&limit=3",
                     "user_snapshot_2025": f"{DATA}/positions/snapshot?user={w}&date=2025-06-01&limit=3",
                     "user_snapshot_2026": f"{DATA}/positions/snapshot?user={w}&date=2026-10-01&limit=3",
                     "user_pnl": f"{DATA}/user-pnl?user={w}&interval=all&fidelity=1d", "user_stats": f"{DATA}/user-stats?user={w}"}.items():
            st, b = get(u)
            res[k] = {"status": st, "shape": shape(b)}
    cond = (g[0].get("condition_id") or g[0].get("condition")) if g else None
    if cond:
        st, b = get(f"{DATA}/resolutions?condition={cond}")
        res["resolutions"] = {"status": st, "shape": shape(b)}
        st, b = get(f"{GAMMA}/markets?condition_ids={cond}&limit=5")
        res["gamma_by_condition"] = {"status": st, "n": len(b) if isinstance(b, list) else None,
                                     "keys": sorted(b[0].keys())[:60] if isinstance(b, list) and b else str(b)[:120]}
    out["endpoints"] = res


def build_frame(out):
    """Wallets with a trade >= 500 USD notional in a one-hour window at 12:00 UTC on the 1st of 22 months (outcome-blind)."""
    frame, new_counts, per_window = {}, [], {}
    for day in FRAME_DATES:
        a = ts_of(day)
        rows, pages, trunc, st = page_all(f"{DATA}/trades?{urlencode({'start': a, 'end': a + WINDOW_S, 'limit': 1000})}", FRAME_PAGES)
        n_new = 0
        for r in rows:
            p = wc.parse_row(r)
            if p and p["wallet"] and p["price"] * p["size"] >= FRAME_MIN_USD and p["wallet"] not in frame:
                frame[p["wallet"]] = day
                n_new += 1
        new_counts.append(n_new)
        per_window[day] = {"rows": len(rows), "pages": pages, "truncated": trunc, "status": st, "new_wallets": n_new}
    out["frame"] = {"windows": per_window, "n": len(frame), "new_counts": new_counts, "saturation_last5_share": wc.saturation(new_counts)}
    return frame


def closed_map(conds, deadline):
    """condition -> close ts (resolved) or None, from gamma (batches of 50 condition ids)."""
    from datetime import datetime
    out, conds = {}, sorted(conds)
    for i in range(0, len(conds), 50):
        if time.time() > deadline:
            break
        chunk = conds[i:i + 50]
        st, b = get(f"{GAMMA}/markets?" + "&".join(f"condition_ids={c}" for c in chunk) + "&limit=100")
        if not isinstance(b, list):
            continue
        for m in b:
            c = m.get("conditionId")
            ct = m.get("closedTime")
            ts = None
            if ct and m.get("closed"):
                try:
                    ts = int(datetime.fromisoformat(ct.replace("+00", "+00:00").replace(" ", "T")).timestamp())
                except ValueError:
                    ts = None
            if c:
                out[c] = ts
    return out


def wallet_job(w, deadline):
    if time.time() > deadline:
        return {"wallet": w, "skipped": True}
    raw, pages, trunc, st = page_all(f"{DATA}/trades?user={w}&limit=1000", PAGE_CAP)
    rows = [p for p in (wc.parse_row(r) for r in raw) if p]
    rows, dups = wc.dedupe(rows)
    return {"wallet": w, "rows": rows, "pages": pages, "truncated": trunc, "dups": dups, "raw": len(raw), "status": st}


def polymarket(out):
    deadline = T0 + BUDGET_S
    frame = build_frame(out)
    order = wc.sample_order(list(frame))[:SAMPLE_WALLETS]
    with ThreadPoolExecutor(HOT_CAP_WALLETS) as ex:
        jobs = list(ex.map(lambda w: wallet_job(w, deadline), order))
    done = [j for j in jobs if not j.get("skipped")]
    conds = set()
    for j in done:
        cs = sorted({r["cond"] for r in j["rows"] if r["cond"]})
        j["cond_check"] = cs[:150]
        conds.update(cs[:150])
    cmap = closed_map(conds, deadline + 20 * 60)
    summaries = []
    for j in done:
        s = wc.wallet_summary(j["rows"], cmap)
        # resolved counts only cover the checked conditions (first 150): a lower bound, stated in the protocol
        s["resolved"] = sum(1 for c in j["cond_check"] if cmap.get(c))
        s["qualifies"] = bool(s["earliest"]) and s["earliest"] <= wc.DEPTH_CUTOFF_TS and s["resolved"] >= wc.MIN_RESOLVED
        s.update(pages=j["pages"], truncated=j["truncated"], dups=j["dups"], raw=j["raw"])
        summaries.append(s)
    holds = [h for s in summaries for h in s["holds"]]
    entries = [e for s in summaries for e in s["entries"]]
    nq = sum(1 for s in summaries if s["qualifies"])
    verdict = wc.probe_verdict(len(frame), len(summaries), nq, wc.med(holds), wc.med(entries), out["frame"]["saturation_last5_share"])
    raw_total = sum(s["raw"] for s in summaries)
    out["wallets"] = {
        "sampled": len(summaries), "skipped_deadline": len(jobs) - len(done), "qualifying": nq,
        "truncated_at_cap": sum(1 for s in summaries if s["truncated"]), "page_cap": PAGE_CAP,
        "depth_ok_earliest_before_cutoff": sum(1 for s in summaries if s["earliest"] and s["earliest"] <= wc.DEPTH_CUTOFF_TS),
        "resolved_ge_100": sum(1 for s in summaries if s["resolved"] >= wc.MIN_RESOLVED),
        "rows_total": raw_total, "dup_rows_total": sum(s["dups"] for s in summaries),
        "dup_share": (sum(s["dups"] for s in summaries) / raw_total) if raw_total else None,
        "pages_median": wc.med([s["pages"] for s in summaries]),
        "earliest_months_back_median": wc.med([(time.time() - s["earliest"]) / (30.44 * 86400) for s in summaries if s["earliest"]]),
        "conds_median": wc.med([s["conds"] for s in summaries]), "resolved_median": wc.med([s["resolved"] for s in summaries]),
        "two_sided_gt_half": sum(1 for s in summaries if s["two_sided"] > 0.5),
        "big_positions_total": sum(s["big_positions"] for s in summaries), "big_with_exit_total": sum(s["big_with_exit"] for s in summaries),
        "hold_days_median": wc.med(holds), "hold_days_p25_p75": [wc.quantile(holds, .25), wc.quantile(holds, .75)] if holds else None,
        "entry_price_median": wc.med(entries), "entry_price_p25_p75": [wc.quantile(entries, .25), wc.quantile(entries, .75)] if entries else None,
        "per_wallet": [{k: s[k] for k in ("n_rows", "earliest", "conds", "resolved", "big_positions", "two_sided", "pages", "truncated", "qualifies")} for s in summaries[:60]],
    }
    out["verdict_polymarket"] = verdict


def hyperliquid(out):
    """Reach of the public info API for point-in-time wallet history (counts only)."""
    res = {}
    st, lb = get("https://stats-data.hyperliquid.xyz/Mainnet/leaderboard", timeout=60)
    rows = lb.get("leaderboardRows") if isinstance(lb, dict) else None
    res["leaderboard"] = {"status": st, "rows": len(rows) if rows else None, "row_keys": sorted(rows[0].keys()) if rows else str(lb)[:160],
                          "note": "as-of-today list: carries survivorship; used here only to find wallets to measure history depth"}
    ws = [r["ethAddress"] for r in (rows or [])[:400] if r.get("ethAddress")]
    ws = wc.sample_order(ws, "q1-hl-probe-20261127")[:20]
    depth = []
    for w in ws:
        if time.time() > T0 + BUDGET_S + 25 * 60:
            break
        st, d = get(HL, body={"type": "userFillsByTime", "user": w, "startTime": int(ts_of("2025-01-01")) * 1000})
        fills = d if isinstance(d, list) else []
        st2, p = get(HL, body={"type": "portfolio", "user": w})
        pdepth = None
        if isinstance(p, list):
            pdepth = {k: len(v.get("accountValueHistory") or []) for k, v in p if isinstance(v, dict)}
        depth.append({"status": st, "fills": len(fills), "earliest": min((f.get("time") for f in fills), default=None) if fills else None,
                      "portfolio_status": st2, "portfolio_history_len": pdepth})
        time.sleep(0.3)
    res["wallet_depth"] = depth
    res["earliest_reached_before_2025_06"] = sum(1 for d in depth if d["earliest"] and d["earliest"] < ts_of("2025-06-01") * 1000)
    res["fills_at_cap"] = sum(1 for d in depth if d["fills"] >= 2000)
    st, rt = get(HL, body={"type": "recentTrades", "coin": "BTC"})
    res["recentTrades"] = {"status": st, "n": len(rt) if isinstance(rt, list) else None, "has_users": bool(isinstance(rt, list) and rt and rt[0].get("users"))}
    out["hyperliquid"] = res


def probe(d):
    os.makedirs(d, exist_ok=True)
    out = {"line": "wallet_follow_probe", "started": int(T0)}
    for name, fn in (("endpoints", endpoints), ("polymarket", polymarket), ("hyperliquid", hyperliquid)):
        try:
            fn(out)
        except Exception as e:  # noqa: BLE001
            out.setdefault("errors", {})[name] = f"{type(e).__name__}: {str(e)[:300]}"
        out["http"] = dict(STATS, elapsed_s=round(time.time() - T0))
        with open(os.path.join(d, "probe.json"), "w") as f:
            json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:60000])


def main(argv):
    if len(argv) < 3 or argv[1] != "probe":
        print(__doc__)
        return 2
    probe(argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
