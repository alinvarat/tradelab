"""P3 Polymarket liquidity-reward quoting probe, replay and forward paper tape (protocol_poly_rewards_20261126.md).
Runs on GitHub Actions only (workflow poly_rewards.yml). Public endpoints, no keys, no orders.

    python research/studies/poly_rewards.py probe   <out_dir>      shapes and reachability only
    python research/studies/poly_rewards.py measure <out_dir>      pools, competition, allocation, trade-history replay
    python research/studies/poly_rewards.py collect <tape_dir>     one ~58 min paper-tape run (5-minute snapshots)
    python research/studies/poly_rewards.py eval    <tape_dir>     tape verdict from the stored rows
"""
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import poly_rewards_core as rc   # noqa: E402
import poly_fv as pfs            # noqa: E402  (fetch helpers: http, get, parse_trades)
from core import poly_fv as pf   # noqa: E402

GAMMA, CLOB, DATA = pfs.GAMMA, pfs.CLOB, pfs.DATA
UA = {"User-Agent": "Mozilla/5.0 tradelab-research", "Content-Type": "application/json"}
SNAP_EVERY_S = 300
RUN_S = 58 * 60
PRELIM_N = 300


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def now():
    return int(time.time())


def post(url, body, timeout=30):
    try:
        with urlopen(Request(url, data=json.dumps(body).encode(), headers=UA, method="POST"), timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except Exception as e:   # noqa: BLE001
        return getattr(e, "code", None) or type(e).__name__, str(e)[:160]


def shape(x, depth=0):
    """Keys and types only (no values), for the probe."""
    if isinstance(x, dict):
        return {k: (shape(v, depth + 1) if depth < 2 else type(v).__name__) for k, v in x.items()}
    if isinstance(x, list):
        return [shape(x[0], depth + 1)] if x and depth < 2 else f"list[{len(x)}]"
    return type(x).__name__


# ---------- data ----------
def fetch_reward_markets(max_pages=80):
    """All /sampling-markets rows (cursor pages)."""
    rows, cur = [], ""
    for _ in range(max_pages):
        d = pfs.get(f"{CLOB}/sampling-markets" + (f"?next_cursor={cur}" if cur else ""))
        if not isinstance(d, dict):
            break
        rows += d.get("data") or []
        cur = d.get("next_cursor") or ""
        if not cur or cur == "LTE=":
            break
    return rows


def parse_reward_market(m):
    """{'cond', 'yes', 'no', 'pool', 'min_size', 'v'} or None. pool = sum of rewards_daily_rate; v in cents."""
    try:
        rw = m.get("rewards") or {}
        pool = sum(float(r.get("rewards_daily_rate") or 0) for r in rw.get("rates") or [])
        toks = m.get("tokens") or []
        if pool <= 0 or len(toks) != 2 or not m.get("accepting_orders", True) or m.get("closed"):
            return None
        return {"cond": m["condition_id"], "yes": toks[0]["token_id"], "no": toks[1]["token_id"], "pool": pool,
                "min_size": float(rw["min_size"]), "v": float(rw["max_spread"]), "q": (m.get("question") or "")[:70]}
    except (KeyError, TypeError, ValueError):
        return None


def fetch_books(tokens, workers=8):
    """{token: book}: POST /books in batches of 100, GET /book for what is missing."""
    out = {}
    tokens = list(tokens)
    for i in range(0, len(tokens), 100):
        st, d = post(f"{CLOB}/books", [{"token_id": t} for t in tokens[i:i + 100]])
        if st == 200 and isinstance(d, list):
            for b in d:
                if isinstance(b, dict) and b.get("asset_id"):
                    out[b["asset_id"]] = b
    miss = [t for t in tokens if t not in out]
    if miss:
        with ThreadPoolExecutor(workers) as ex:
            for t, b in zip(miss, ex.map(lambda t: pfs.get(f"{CLOB}/book?token_id={t}", tries=2), miss)):
                if isinstance(b, dict):
                    out[t] = b
    return out


def control_markets(exclude, n=rc.CONTROL_N):
    """Top 24h-volume gamma markets with an order book that are not reward markets."""
    d = pfs.get(f"{GAMMA}/markets?active=true&closed=false&order=volume24hr&ascending=false&limit=300") or []
    out = []
    for m in d if isinstance(d, list) else []:
        try:
            toks = json.loads(m.get("clobTokenIds") or "[]")
            if m["conditionId"] in exclude or len(toks) != 2 or not m.get("enableOrderBook", True):
                continue
            out.append({"cond": m["conditionId"], "yes": toks[0], "no": toks[1], "q": (m.get("question") or "")[:70]})
        except (KeyError, TypeError, ValueError):
            continue
        if len(out) >= n:
            break
    return out


def attach_books(markets):
    books = fetch_books([m["yes"] for m in markets])
    out = []
    for m in markets:
        b = books.get(m["yes"])
        if not b:
            continue
        mid, qc = rc.competition(b, m["v"])
        if mid is None:
            continue
        out.append(dict(m, mid=mid, qc=qc))
    return out


def prelim_rank(m):
    den = m["min_size"] * (1 - 2 * rc.PRIMARY_FRAC * m["v"] / 100)
    return m["pool"] / den if den > 0 else 0.0


# ---------- probe ----------
def probe(out_dir):
    out = {"t": datetime.now(timezone.utc).isoformat(), "endpoints": {}}
    E = out["endpoints"]

    def rec(name, st_body):
        st, body = st_body
        E[name] = {"status": st, "shape": shape(body) if isinstance(body, (dict, list)) else str(body)[:120]}
        return body
    gm = rec("gamma_markets", pfs.http(f"{GAMMA}/markets?active=true&closed=false&order=volume24hr&ascending=false&limit=3"))
    sm = rec("clob_sampling_markets", pfs.http(f"{CLOB}/sampling-markets"))
    rec("clob_rewards_markets_multi", pfs.http(f"{CLOB}/rewards/markets/multi?page_size=3"))
    rec("clob_rewards_markets_current", pfs.http(f"{CLOB}/rewards/markets/current"))
    rec("clob_simplified_markets", pfs.http(f"{CLOB}/simplified-markets"))
    rows = (sm.get("data") if isinstance(sm, dict) else None) or []
    parsed = [x for x in (parse_reward_market(r) for r in rows) if x]
    out["sampling_page"] = {"rows": len(rows), "with_pool": len(parsed), "next_cursor_present": bool(isinstance(sm, dict) and sm.get("next_cursor"))}
    if rows:
        out["sampling_first_keys"] = sorted(rows[0].keys())
        out["sampling_first_rewards_shape"] = shape(rows[0].get("rewards"))
    if parsed:
        p = parsed[0]
        rec("clob_book_get", pfs.http(f"{CLOB}/book?token_id={p['yes']}"))
        rec("clob_books_post", post(f"{CLOB}/books", [{"token_id": p["yes"]}, {"token_id": p["no"]}]))
        rec("data_v2_trades", pfs.http(f"{DATA}/v2/trades?condition={p['cond']}&limit=5"))
        rec("data_trades_market", pfs.http(f"{DATA}/trades?market={p['cond']}&limit=5"))
        rec("clob_market", pfs.http(f"{CLOB}/markets/{p['cond']}"))
    if isinstance(gm, list) and gm:
        out["gamma_reward_like_keys"] = sorted(k for k in gm[0] if "eward" in k)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "probe.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


# ---------- measure ----------
def fetch_trades(cond, max_pages=10):
    tr, trunc = pfs.fetch_trades(cond, max_pages)
    return tr, trunc


def mid_from_trades(trades):
    ts = [x["t"] for x in trades]

    def mid_at(T):
        return pf.last_yes_before(trades, T)
    return mid_at, ts


def measure(out_dir):
    out_p = Path(out_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    rep = {"t": datetime.now(timezone.utc).isoformat(), "budget": rc.BUDGET}
    rows = fetch_reward_markets()
    mk = [x for x in (parse_reward_market(r) for r in rows) if x]
    rep["sampling_rows"] = len(rows)
    rep["reward_markets"] = len(mk)
    pools = sorted(m["pool"] for m in mk)
    rep["pool_total_usd_day"] = sum(pools)
    rep["pool_quantiles"] = {q: pools[int(q * (len(pools) - 1))] for q in (0.5, 0.9, 0.99)} if pools else {}
    mk.sort(key=prelim_rank, reverse=True)
    mkb = attach_books(mk[:PRELIM_N])
    rep["with_book"] = len(mkb)
    shapes = []
    allocs = {}
    for frac in rc.OFFSET_FRACS:
        for mode in ("two", "single"):
            k, gross, spent = rc.allocate(mkb, frac, mode)
            nq = sum(1 for m in mkb if rc.qualifies(m, frac, mode))
            shapes.append({"frac": frac, "mode": mode, "n_qualifying": nq, "n_alloc": len(k), "spent": round(spent, 2),
                           "gross_usd_day": round(gross, 4), "gross_pct": gross / rc.BUDGET,
                           "after_min_payout_pct": rc.after_min_payout(gross) / rc.BUDGET})
            allocs[(frac, mode)] = k
    rep["shapes"] = shapes
    rep["decision"] = rc.decide(shapes)
    rep["top_markets"] = [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items() if k not in ("yes", "no")}
                          for m in mkb[:15]]
    best = max(shapes, key=lambda s: s["gross_pct"])
    rep["best_shape"] = {"frac": best["frac"], "mode": best["mode"]}
    log("decision", rep["decision"], "best", rep["best_shape"], best["gross_pct"])
    if rep["decision"] != "kill_complete":
        rep["replay"] = replay(mkb, allocs, rc.PRIMARY_FRAC, "two", best)
    (out_p / "summary.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k != "top_markets"}, indent=1, default=str))


def replay(mkb, allocs, frac, mode, best):
    """Trade-history replay of the primary shape (and the best-gross shape): constant today's pool and competition."""
    res = {}
    by = {m["cond"]: m for m in mkb}
    shapes = {("primary", frac, mode): allocs[(frac, mode)]}
    shapes[("best", best["frac"], best["mode"])] = allocs[(best["frac"], best["mode"])]
    need = {c for k in shapes.values() for c in k}
    with ThreadPoolExecutor(6) as ex:
        trades = dict(zip(need, ex.map(lambda c: fetch_trades(c), sorted(need))))
    ctrl = control_markets({m["cond"] for m in mkb})
    med_v = sorted(m["v"] for m in mkb)[len(mkb) // 2]
    med_ms = sorted(m["min_size"] for m in mkb)[len(mkb) // 2]
    with ThreadPoolExecutor(6) as ex:
        ctrades = dict(zip([c["cond"] for c in ctrl], ex.map(lambda c: fetch_trades(c["cond"]), ctrl)))
    cbooks = attach_books([dict(c, pool=0.0, v=med_v, min_size=med_ms) for c in ctrl])
    for (name, fr, md), k in shapes.items():
        for tag, mark_s, hc, zero in (("base", rc.MARK_S, rc.HAIRCUT, False), ("mark_1h", rc.MARK_S_SHORT, rc.HAIRCUT, False),
                                      ("haircut_x2", rc.MARK_S, 2 * rc.HAIRCUT, False), ("zero_reward", rc.MARK_S, rc.HAIRCUT, True)):
            per, cap, cover = {}, 0.0, []
            for c, units in k.items():
                m, (tr, trunc) = by[c], trades[c]
                if len(tr) < 20:
                    continue
                t0, t1 = tr[0]["t"], tr[-1]["t"]
                q = rc.our_q(units, m["min_size"], m["v"], fr * m["v"], m["mid"], md)
                share = q / (q + m["qc"]) if q + m["qc"] > 0 else 0.0
                mid_at, _ = mid_from_trades(tr)
                per[c] = rc.simulate_market(tr, t0, t1, m["v"], fr, units, m["min_size"], lambda T, s=share: s, mid_at,
                                            0.0 if zero else m["pool"], mark_s=mark_s, haircut=hc)
                cap += units * rc.unit_cost(m["mid"], m["min_size"], fr * m["v"], md)
                cover.append([c[:10], len(tr), round((t1 - t0) / 86400, 2), trunc])
            if per and cap > 0:
                res[f"{name}|{tag}"] = dict(rc.summarise(per, cap), capital=round(cap, 2), markets=len(per),
                                            monthly_linear=None, coverage=cover[:10] if tag == "base" else None)
                s = res[f"{name}|{tag}"]
                if s["net_mean"] is not None:
                    s["monthly_linear"] = 30 * s["net_mean"]
    # no-reward matched control: one unit each, fill-only per USD
    per, cap = {}, 0.0
    for m in cbooks:
        tr, trunc = ctrades[m["cond"]]
        if len(tr) < 20:
            continue
        mid_at, _ = mid_from_trades(tr)
        per[m["cond"]] = rc.simulate_market(tr, tr[0]["t"], tr[-1]["t"], m["v"], frac, 1, m["min_size"], lambda T: 0.0, mid_at, 0.0)
        cap += rc.unit_cost(m["mid"], m["min_size"], frac * m["v"], mode)
    if per and cap > 0:
        res["control_no_reward"] = dict(rc.summarise(per, cap), capital=round(cap, 2), markets=len(per))
    res["assumptions"] = "today's pool and competition held constant; mid proxy = last trade <= 30 min old; no historical book"
    return res


# ---------- forward tape ----------
def write_gz(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def read_gz_dir(d):
    rows = []
    for p in sorted(Path(d).glob("*.jsonl.gz")):
        with gzip.open(p, "rt") as f:
            rows += [json.loads(x) for x in f if x.strip()]
    return rows


def pick_tracked():
    rows = fetch_reward_markets()
    mk = [x for x in (parse_reward_market(r) for r in rows) if x]
    mk.sort(key=prelim_rank, reverse=True)
    mkb = attach_books(mk[:PRELIM_N])
    mkb.sort(key=prelim_rank, reverse=True)
    rew = [dict(m, group="reward") for m in mkb[:rc.TRACK_N]]
    med_v = sorted(m["v"] for m in rew)[len(rew) // 2]
    med_ms = sorted(m["min_size"] for m in rew)[len(rew) // 2]
    ctl = [dict(c, pool=0.0, v=med_v, min_size=med_ms, group="control")
           for c in control_markets({m["cond"] for m in mk})]
    return rew + ctl


def collect(tape_dir):
    d = Path(tape_dir)
    (d / "snaps").mkdir(parents=True, exist_ok=True)
    (d / "trades").mkdir(parents=True, exist_ok=True)
    meta = json.loads((d / "markets.json").read_text()) if (d / "markets.json").exists() else {}
    state = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else {}
    tracked = pick_tracked()
    if len(tracked) < 20:
        log("too few markets", len(tracked))
        return
    for m in tracked:
        e = meta.setdefault(m["cond"], {"first_seen": now()})
        e.update({k: m[k] for k in ("yes", "no", "pool", "min_size", "v", "group", "q")}, last_seen=now())
    (d / "markets.json").write_text(json.dumps(meta))
    snaps, tr_rows = [], []
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    end = time.time() + RUN_S
    by = {m["cond"]: m for m in tracked}
    nxt = time.time()
    while True:
        books = fetch_books([m["yes"] for m in tracked])
        t = now()
        for m in tracked:
            b = books.get(m["yes"])
            if not b:
                continue
            bb, ba, bids, asks = rc.top_of_book(b)
            mid = rc.mid_of(bb, ba)
            if mid is None:
                continue
            q1, q2 = rc.band_q(bids, asks, mid, m["v"])
            snaps.append([t, m["cond"], bb, ba, round(q1, 2), round(q2, 2)])

        def new_trades(c):
            st = state.get(c) or {"t": 0, "keys": []}
            got, cur = [], ""
            for _ in range(5):
                x = pfs.get(f"{DATA}/v2/trades?condition={c}&limit=500" + (f"&cursor={cur}" if cur else ""))
                if not isinstance(x, dict):
                    break
                rows = x.get("data") or []
                got += rows
                pg = x.get("pagination") or {}
                cur = pg.get("next_cursor") or ""
                if not rows or not pg.get("has_more") or min(int(r["timestamp"]) for r in rows) <= st["t"]:
                    break
            return c, st, pfs.parse_trades(got)
        with ThreadPoolExecutor(8) as ex:
            for c, st, trs in ex.map(new_trades, list(by)):
                keys = set(st["keys"])
                last, lk = st["t"], set(st["keys"])
                for x in trs:
                    k = f"{x['t']}|{x['idx']}|{x['side']}|{x['price']}|{x['size']}"
                    if x["t"] < st["t"] or (x["t"] == st["t"] and k in keys):
                        continue
                    tr_rows.append([x["t"], c, x["idx"], x["side"], x["price"], x["size"]])
                    if x["t"] > last:
                        last, lk = x["t"], set()
                    if x["t"] == last:
                        lk.add(k)
                state[c] = {"t": last, "keys": sorted(lk)[:50]}
        nxt += SNAP_EVERY_S
        if time.time() + SNAP_EVERY_S > end:
            break
        time.sleep(max(0, nxt - time.time()))
    write_gz(d / "snaps" / f"{run}.jsonl.gz", snaps)
    write_gz(d / "trades" / f"{run}.jsonl.gz", tr_rows)
    (d / "state.json").write_text(json.dumps(state))
    log("run", run, "snaps", len(snaps), "trades", len(tr_rows))
    evaluate(tape_dir)


# ---------- tape evaluation ----------
def evaluate(tape_dir):
    d = Path(tape_dir)
    if not (d / "markets.json").exists():
        return
    meta = json.loads((d / "markets.json").read_text())
    snaps = read_gz_dir(d / "snaps")
    trades = read_gz_dir(d / "trades")
    import bisect
    sn, tr = {}, {}
    for t, c, bb, ba, q1, q2 in snaps:
        sn.setdefault(c, []).append((t, bb, ba, q1, q2))
    for t, c, idx, side, p, s in trades:
        tr.setdefault(c, []).append({"t": t, "idx": idx, "side": side, "price": p, "size": s})
    res = {}
    for group in ("reward", "control"):
        for tag, mark_s, hc, zero in (("base", rc.MARK_S, rc.HAIRCUT, False), ("haircut_x2", rc.MARK_S, 2 * rc.HAIRCUT, False),
                                      ("zero_reward", rc.MARK_S, rc.HAIRCUT, True)):
            if group == "control" and tag != "base":
                continue
            per, cap = {}, 0.0
            for c, m in meta.items():
                if m["group"] != group or c not in sn or len(sn[c]) < 12:
                    continue
                s = sorted(sn[c])
                st = [x[0] for x in s]
                trs = sorted(tr.get(c, []), key=lambda x: x["t"])

                def mid_at(T, s=s, st=st):
                    i = bisect.bisect_right(st, T) - 1
                    if i < 0 or T - st[i] > 1200 or s[i][1] is None or s[i][2] is None:
                        return None
                    return (s[i][1] + s[i][2]) / 2

                def share_at(T, s=s, st=st, m=m):
                    i = bisect.bisect_right(st, T) - 1
                    if i < 0:
                        return 0.0
                    mid = (s[i][1] + s[i][2]) / 2
                    q = rc.score(m["v"], rc.PRIMARY_FRAC * m["v"]) * m["min_size"]
                    qc = rc.qmin(s[i][3], s[i][4], mid)
                    return q / (q + qc) if q + qc > 0 else 0.0
                per[c] = rc.simulate_market(trs, st[0], st[-1], m["v"], rc.PRIMARY_FRAC, 1, m["min_size"], share_at, mid_at,
                                            0.0 if (zero or group == "control") else m["pool"], mark_s=mark_s, haircut=hc)
                mid0 = (s[0][1] + s[0][2]) / 2
                cap += rc.unit_cost(mid0, m["min_size"], rc.PRIMARY_FRAC * m["v"], "two")
            if per and cap > 0:
                res[f"{group}|{tag}"] = dict(rc.summarise(per, cap), capital=round(cap, 2), markets=len(per))
                res[f"{group}|{tag}"]["_series"] = rc.combine(per, cap)
    out = {"t": datetime.now(timezone.utc).isoformat(), "snaps": len(snaps), "trades": len(trades)}
    base, ctl = res.get("reward|base"), res.get("control|base")
    if base:
        days = base["days"]
        out["days"] = days
        verdict = "collecting"
        if base["net_mean"] is not None and days >= rc.KILL_TAPE_DAYS:
            r = res.get("reward|zero_reward")
            if base["net_mean"] <= 0 or (r and base["reward_mean"] < -(r["fill_mean"] or 0)):
                verdict = "killed"
        if verdict == "collecting" and days >= rc.MIN_TAPE_DAYS_VERDICT and ctl:
            ds, a, b = base["_series"][0], base["_series"][1], res["control|base"]["_series"]
            fa = dict(zip(ds, [x + y for x, y in zip(base["_series"][1], base["_series"][2])]))
            fb = dict(zip(b[0], [x + y for x, y in zip(b[1], b[2])]))
            common = sorted(set(fa) & set(fb))
            st = pf.cluster_stats([fa[x] - fb[x] for x in common], common)
            out["vs_control"] = st
            x2 = res.get("reward|haircut_x2")
            if st["p"] is not None and st["p"] < rc.ALPHA_TAPE and x2 and x2["net_mean"] > 0:
                verdict = "found"
            else:
                verdict = "not_found"
        out["verdict"] = verdict
    for v in res.values():
        v.pop("_series", None)
    out["results"] = res
    (d / "summary.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    {"probe": probe, "measure": measure, "collect": collect, "eval": evaluate}[argv[1]](argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
