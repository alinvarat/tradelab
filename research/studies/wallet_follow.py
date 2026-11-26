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
GAMMA_DIAG = []
T0 = time.time()
BUDGET_S = 150 * 60            # stop starting new work after 150 minutes

FRAME_DATES = [f"{y}-{m:02d}-01" for y in (2025, 2026) for m in range(1, 13) if (y, m) <= (2026, 10)]   # 22 windows
FRAME_PAGES = 5
MARKETS_PER_MONTH = 10
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


def month_windows():
    """(first day, first day of next month) of the 22 frame months."""
    out = []
    for day in FRAME_DATES:
        y, m = int(day[:4]), int(day[5:7])
        out.append((day, f"{y + (m == 12)}-{(m % 12) + 1:02d}-01"))
    return out


def sample_markets(a, b):
    """Resolved binary markets ending in [a, b) with volume >= 50,000 USD (one keyset page of up to 100), then the first
    MARKETS_PER_MONTH by sha256(seed + conditionId). The choice reads no outcome and no wallet."""
    st, d = get(f"{GAMMA}/markets/keyset?closed=true&limit=100&volume_num_min=50000&end_date_min={a}T00:00:00Z&end_date_max={b}T00:00:00Z")
    ms = (d.get("markets") if isinstance(d, dict) else None) or []
    ok = []
    for m in ms:
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
        except ValueError:
            continue
        if len(toks) == 2 and m.get("conditionId"):
            ok.append(m["conditionId"])
    return wc.sample_order(ok, "q1-wallet-probe-markets-20261127")[:MARKETS_PER_MONTH], len(ms), st


def build_frame(out):
    """Addendum 20261127: wallets with a trade >= 500 USD notional in MARKETS_PER_MONTH outcome-blind resolved markets of each of
    22 months, read from the condition feed (a three-year window; the bare feed holds only ~2 months and ignores start/end)."""
    frame, new_counts, per_window = {}, [], {}
    for (a, b) in month_windows():
        conds, n_listed, st0 = sample_markets(a, b)
        n_new, rows_n, pages_n, tmin, tmax = 0, 0, 0, None, None
        for c in conds:
            rows, pages, trunc, st = page_all(f"{DATA}/trades?condition={c}&limit=1000", FRAME_PAGES)
            rows_n += len(rows)
            pages_n += pages
            for r in rows:
                p = wc.parse_row(r)
                if not p:
                    continue
                tmin = p["t"] if tmin is None else min(tmin, p["t"])
                tmax = p["t"] if tmax is None else max(tmax, p["t"])
                if p["wallet"] and p["price"] * p["size"] >= FRAME_MIN_USD and p["wallet"] not in frame:
                    frame[p["wallet"]] = a
                    n_new += 1
        new_counts.append(n_new)
        per_window[a] = {"listed": n_listed, "status": st0, "markets": len(conds), "rows": rows_n, "pages": pages_n, "ts_min": tmin, "ts_max": tmax, "new_wallets": n_new}
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
        st, b = get(f"{GAMMA}/markets?closed=true&" + "&".join(f"condition_ids={c}" for c in chunk) + "&limit=100")
        GAMMA_DIAG.append({"asked": len(chunk), "status": st, "got": len(b) if isinstance(b, list) else None,
                           "closed": sum(1 for m in b if m.get("closed")) if isinstance(b, list) else None,
                           "with_closedTime": sum(1 for m in b if m.get("closedTime")) if isinstance(b, list) else None})
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
        "per_wallet": [{k: s[k] for k in ("n_rows", "earliest", "conds", "resolved", "big_positions", "two_sided", "pages", "truncated", "qualifies")} for s in summaries],
        "gamma_diag": {"chunks": len(GAMMA_DIAG), "asked": sum(g["asked"] for g in GAMMA_DIAG), "got": sum(g["got"] or 0 for g in GAMMA_DIAG),
                       "closed": sum(g["closed"] or 0 for g in GAMMA_DIAG), "with_closedTime": sum(g["with_closedTime"] or 0 for g in GAMMA_DIAG),
                       "bad_status": [g["status"] for g in GAMMA_DIAG if g["got"] is None][:5]},
    }
    out["verdict_polymarket"] = verdict
    mk = []
    for j in done[:20]:
        raw2, p2, t2, _ = page_all(f"{DATA}/trades?user={j['wallet']}&limit=1000&taker_only=false", 10)
        mk.append({"taker_only_rows": j["raw"] if not j["truncated"] else None, "all_rows": len(raw2), "truncated": t2})
    out["wallets"]["maker_check_first20"] = mk


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


def b64j(c):
    import base64
    try:
        return json.loads(base64.urlsafe_b64decode(c + "=" * (-len(c) % 4)))
    except Exception:  # noqa: BLE001
        return None


def b64e(o):
    import base64
    return base64.urlsafe_b64encode(json.dumps(o, separators=(",", ":")).encode()).decode().rstrip("=")


def tape_jump(cond, depth_pages, variant):
    """Does a cursor built from a page-1 cursor with ts changed seek the condition tape to that time? Returns a dict.
    Reference: walk `depth_pages` pages newest-first and take a row; target = that row's time + 120 s."""
    st, d = get(f"{DATA}/trades?condition={cond}&limit=1000")
    cur = (d.get("pagination") or {}).get("next_cursor") if isinstance(d, dict) else None
    if not cur:
        return {"err": "no cursor", "status": st}
    ref = b64j(cur)
    rows, c, pages = rows_of(d), cur, 1
    while pages < depth_pages and c:
        st, d = get(f"{DATA}/trades?condition={cond}&limit=1000&cursor={c}")
        if not isinstance(d, dict):
            break
        rows += rows_of(d)
        c = (d.get("pagination") or {}).get("next_cursor") if (d.get("pagination") or {}).get("has_more") else None
        pages += 1
    if len(rows) < 2000:
        return {"err": "tape too short", "rows": len(rows)}
    x = rows[len(rows) // 2]
    tx = int(x["timestamp"])
    params = dict(((ref or {}).get("data") or {}).get("params") or {})
    new = json.loads(json.dumps(ref))
    new["data"]["params"]["ts"] = tx + 120
    if variant == "sq_big":
        new["data"]["params"]["sq"] = "9223372036854775807"
    elif variant == "sq_zero_drop":
        new["data"]["params"].pop("sq", None)
    elif variant == "sq_str9":
        new["data"]["params"]["sq"] = "999999999999999999"
    st2, j = get(f"{DATA}/trades?condition={cond}&limit=50&cursor={b64e(new)}")
    jr = rows_of(j)
    jts = [int(r["timestamp"]) for r in jr] if jr else []
    return {"variant": variant, "ref_keys": sorted(params), "status": st2, "n": len(jr), "first_ts": jts[0] if jts else None, "last_ts": jts[-1] if jts else None,
            "target_ts": tx + 120, "row_ts": tx, "covers_row": bool(jts and min(jts) <= tx <= max(jts)),
            "first_within_300s_of_target": bool(jts and abs(jts[0] - (tx + 120)) <= 300), "err": None if jr else str(j)[:160]}


def probe2(d):
    """Outcome-free check (protocol addendum 3): can the market tape be sought to a past time (a 60 s delayed fill needs a trade
    after the wallet's), and what does /v2/prices-history serve for old windows."""
    os.makedirs(d, exist_ok=True)
    out = {"line": "wallet_follow_probe2"}
    conds = []
    for a, b in month_windows()[:20:3]:
        c, _, _ = sample_markets(a, b)
        conds += c[:2]
    res = []
    for c in conds[:12]:
        for v in ("same", "sq_big", "sq_zero_drop", "sq_str9"):
            res.append(dict(cond=c[:10], **tape_jump(c, 4, v)))
    out["tape_jump"] = res
    by = {}
    for r in res:
        k = r.get("variant") or "none"
        z = by.setdefault(k, {"tests": 0, "ok_status": 0, "covers_row": 0, "near_target": 0})
        z["tests"] += 1
        z["ok_status"] += r.get("status") == 200
        z["covers_row"] += bool(r.get("covers_row"))
        z["near_target"] += bool(r.get("first_within_300s_of_target"))
    out["tape_jump_summary"] = by
    ph = []
    for c in conds[:6]:
        st, g = get(f"{GAMMA}/markets?closed=true&condition_ids={c}&limit=1")
        if not (isinstance(g, list) and g):
            continue
        toks = json.loads(g[0].get("clobTokenIds") or "[]")
        ct = g[0].get("closedTime") or ""
        if not toks or not ct:
            continue
        from datetime import datetime
        t1 = int(datetime.fromisoformat(ct.replace("+00", "+00:00").replace(" ", "T")).timestamp()) - 5 * 86400
        for bs, extra in ((60, ""), (10800, ""), (60, "&limit=5")):
            st2, h = get(f"{DATA}/prices-history?token_id={toks[0]}&start={t1}&end={t1 + 86400}&bucket_seconds={bs}{extra}")
            pts = (h.get("data") if isinstance(h, dict) else None)
            n = len(pts.get("points") or pts.get("history") or []) if isinstance(pts, dict) else (len(pts) if isinstance(pts, list) else None)
            ph.append({"bucket": bs, "age_days_of_start": round((time.time() - t1) / 86400), "status": st2, "points": n, "shape": shape(h) if not isinstance(h, str) else h[:120]})
    out["prices_history"] = ph
    out["http"] = dict(STATS, elapsed_s=round(time.time() - T0))
    with open(os.path.join(d, "probe2.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:30000])


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
    if len(argv) < 3 or argv[1] not in ("probe", "probe2"):
        print(__doc__)
        return 2
    {"probe": probe, "probe2": probe2}[argv[1]](argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
