"""Long Actions collectors for the two PENDING arms of the S1-S5 probes: S2 (3-day GeckoTerminal trending-list poll) and S4
(48 hourly Kalshi x Polymarket snapshots). Rules: RESULTS.md pre-registration + research/studies/protocol_s2s4_poll_20261127.md.

    python research/studies/s15_long.py s2_collect <dir> [minutes]     poll every 30 s, rows and polls appended to <dir>
    python research/studies/s15_long.py s4_collect <dir> [minutes]     one snapshot at minute :10 of every hour
    python research/studies/s15_long.py s2_eval|s4_eval <dir>          verdict from what is on disk -> <dir>/summary.json

Each run is bounded (default 330 minutes), flushes to the data branch every 30 minutes (S15_PUSH script) and queues its successor
(S15_CHAIN=1) until the window is complete. Counts only: no price after a signal is read. Public endpoints, no keys."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import s15, s15_eval   # noqa: E402
from research.studies import s15_probe as P   # noqa: E402

POLL_S = 30
S2_HOURS = 72
S4_SNAPS = 48
FLUSH_S = 1800


def log(*a):
    print(time.strftime("%H:%M:%S", time.gmtime()), *a, file=sys.stderr, flush=True)


def jload(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:  # noqa: BLE001
        return default


def append(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")


def lines(path):
    out = []
    try:
        for ln in Path(path).read_text().splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    except FileNotFoundError:
        pass
    return out


def push(d):
    cmd = os.environ.get("S15_PUSH")
    if cmd:
        r = subprocess.run(["bash", cmd, str(d), os.environ.get("S15_BRANCH", "")], capture_output=True, text=True)
        log("push", r.returncode, (r.stdout + r.stderr)[-200:])


def chain_next(mode):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo and os.environ.get("GH_TOKEN") and os.environ.get("S15_CHAIN") == "1":
        r = subprocess.run(["gh", "workflow", "run", "s2s4_poll.yml", "-R", repo, "--ref", "main", "-f", f"mode={mode}"],
                           capture_output=True, text=True)
        log("chain", r.returncode, (r.stdout + r.stderr)[-200:])


# ====================================================================== S2
def s2_poll():
    """-> (ids, info) or None; both pages must answer, one retry each (a half answer is a void poll)."""
    ids, info = [], {}
    for page in (1, 2):
        d = None
        for attempt in range(2):
            st, d = P.jreq(f"{P.GT}/networks/trending_pools?duration=1h&page={page}", headers=P.GT_H, tries=1, timeout=15)
            if isinstance(d, dict) and isinstance(d.get("data"), list):
                break
            d = None
            time.sleep(5)
        if d is None:
            return None
        for x in d["data"]:
            a = x.get("attributes") or {}
            pid = x.get("id")
            ids.append(pid)
            dex = (((x.get("relationships") or {}).get("dex") or {}).get("data") or {}).get("id")
            info[pid] = {"name": a.get("name"), "reserve": P.fnum(a.get("reserve_in_usd")), "dex": dex, "address": a.get("address")}
    return ids, info


def sells_check(pid, i, first_t):
    net = pid.split("_")[0]
    st, d = P.jreq(f"{P.GT}/networks/{net}/pools/{i['address']}/trades", headers=P.GT_H, tries=1, timeout=15)
    if not (isinstance(d, dict) and isinstance(d.get("data"), list)):
        return None, False
    tr = [{"kind": (x.get("attributes") or {}).get("kind"), "wallet": (x.get("attributes") or {}).get("tx_from_address"),
           "t": P.parse_ts((x.get("attributes") or {}).get("block_timestamp") or "")} for x in d["data"]]
    tr = [x for x in tr if x["t"]]
    oldest = min((x["t"] for x in tr), default=None)
    truncated = len(tr) >= 300 and oldest is not None and oldest > first_t - 3600     # the 300-trade page does not reach back one hour
    return s15.distinct_sellers(tr, first_t), truncated


def s2_collect(d, minutes=330):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    state = jload(d / "state.json", {})
    if state.get("done"):
        log("window already complete")
        return
    state.setdefault("started", time.time())
    seen = set(state.get("seen", []))
    last_ids = set(state.get("last_ids", []))
    last_t = state.get("last_t")
    first_poll = not seen
    queue = []
    end = time.time() + minutes * 60
    last_flush = time.time()
    reentries = state.get("reentries", 0)
    while time.time() < end:
        t = time.time()
        got = s2_poll()
        if got is None:
            append(d / "polls.jsonl", {"t": round(t), "ok": False})
        else:
            ids, info = got
            append(d / "polls.jsonl", {"t": round(t), "ok": True, "n": len(ids)})
            for pid in ids:
                if pid in seen:
                    if last_ids and pid not in last_ids:
                        reentries += 1
                    continue
                seen.add(pid)
                if first_poll:
                    continue                      # baseline: the first poll ever counts nobody
                i = info[pid]
                fee = s15.pool_fee(i["name"], i["dex"])
                rt = s15.cp_round_trip(i["reserve"], fee)
                row = {"id": pid, "name": i["name"], "dex": i["dex"], "reserve_usd": i["reserve"], "fee": fee, "round_trip": rt,
                       "first_t": round(t), "prev_t": round(last_t) if last_t else None,
                       "delay_s": (t - last_t) if last_t else None, "qualifies": rt is not None and rt <= 0.03,
                       "sellers": None, "truncated": False}
                append(d / "entrants.jsonl", row)
                if row["qualifies"]:
                    queue.append((row, i, t))
            first_poll = False
            last_ids, last_t = set(ids), t
        # at most 2 sells checks a cycle; an entrant unchecked after 10 minutes stays "not measured"
        for _ in range(2):
            while queue and time.time() - queue[0][2] > 600:
                queue.pop(0)
            if not queue:
                break
            row, i, ft = queue.pop(0)
            sellers, trunc = sells_check(row["id"], i, ft)
            append(d / "sells.jsonl", {"id": row["id"], "sellers": sellers, "truncated": trunc})
        state.update(seen=sorted(seen), last_ids=sorted(last_ids), last_t=last_t, reentries=reentries)
        if time.time() - last_flush > FLUSH_S:
            (d / "state.json").write_text(json.dumps(state))
            push(d)
            last_flush = time.time()
        if time.time() - state["started"] > S2_HOURS * 3600:
            state["done"] = True
            break
        time.sleep(max(0, POLL_S - (time.time() - t)))
    (d / "state.json").write_text(json.dumps(state))
    summ = s2_eval(d)
    push(d)
    if not state.get("done"):
        chain_next("s2_collect")


def s2_rows(d):
    seen_ids, rows = set(), []
    for r in lines(Path(d) / "entrants.jsonl"):      # a crash between flushes can write an entrant twice: keep the first
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            rows.append(r)
    sells = {}
    for s in lines(Path(d) / "sells.jsonl"):
        sells[s["id"]] = s
    for r in rows:
        s = sells.get(r["id"])
        if s:
            r["sellers"], r["truncated"] = s["sellers"], s["truncated"]
    return rows


def s2_eval(d):
    d = Path(d)
    state = jload(d / "state.json", {})
    out = s15_eval.s2_evaluate(s2_rows(d), lines(d / "polls.jsonl"), hours_required=0.0 if state.get("done") else S2_HOURS * 0.9)
    out["started"] = state.get("started")
    out["reentries_not_counted"] = state.get("reentries", 0)
    out["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (d / "summary.json").write_text(json.dumps(out, indent=1))
    log("s2", out["status"], {k: out[k] for k in ("covered_hours", "entrants", "qualifying", "median_delay_s", "sell_measured", "sell_no_exit")})
    return out


# ====================================================================== S4
SERIES = {}


def kalshi_fee_mult(m):
    """Fee multiplier of the market's series (None = unknown, the pair is excluded and counted)."""
    sk = (m.get("event_ticker") or "").split("-")[0]
    if not sk:
        return None
    if sk not in SERIES:
        st, d = P.jreq(f"{P.KALSHI}/series/{sk}", tries=1, timeout=15)
        s = (d or {}).get("series") if isinstance(d, dict) else None
        ft = (s or {}).get("fee_type") or ""
        if ft.startswith("quadratic"):
            SERIES[sk] = P.fnum((s or {}).get("fee_multiplier")) if (s or {}).get("fee_multiplier") is not None else 1.0
        elif ft in ("fee_free", "flat_zero"):
            SERIES[sk] = 0.0
        else:
            SERIES[sk] = None
    return SERIES[sk]


def s4_snapshot():
    now = time.time()
    km, pm, err = P.snapshot_s4(now + 600)
    if err:
        return {"t": round(now), "ok": False, "error": err}
    kf, pf = [], []
    for m in km:
        stp = m.get("strike_type", "") or ""
        strike = P.fnum(m.get("floor_strike")) if stp.startswith("greater") else P.fnum(m.get("cap_strike")) if stp.startswith("less") else None
        f = s15.features(m.get("title") or m.get("yes_sub_title") or "", strike, stp)
        if f:
            kf.append((m, f, P.iso(m.get("close_time"))))
    for m in pm:
        f = s15.features(m.get("question") or "")
        if f and f["level"] is not None:
            pf.append((m, f, P.iso(m.get("endDate"))))
    matched, near = [], 0
    for km_, kfe, kc in kf:
        for pm_, pfe, pc in pf:
            if not (kc and pc):
                continue
            if s15.pair_match(kfe, pfe, kc, pc):
                matched.append((km_, pm_, kfe))
            elif s15.pair_match(kfe, pfe, kc, pc, tol=24 * 3600):
                near += 1
    rows, alloc, fee_excl = [], [], 0
    for km_, pm_, f in matched[:120]:
        ks = s15.sources_of((km_.get("rules_primary") or "") + " " + (km_.get("rules_secondary") or ""))
        ps = s15.sources_of((pm_.get("description") or "") + " " + (pm_.get("resolutionSource") or ""))
        row = {"k": km_.get("ticker"), "p": pm_.get("slug") or pm_.get("id"), "cat": f["cat"],
               "mismatch": s15.source_mismatch(ks, ps), "k_sources": sorted(ks), "p_sources": sorted(ps)}
        mult = kalshi_fee_mult(km_)
        if mult is None or pm_.get("feesEnabled"):
            fee_excl += 1
            row["excluded"] = "fee not readable" if mult is None else "polymarket fee enabled"
            rows.append(row)
            continue
        ya, na = P.cents(km_, "yes_ask_dollars", "yes_ask"), P.cents(km_, "no_ask_dollars", "no_ask")
        try:
            toks = json.loads(pm_.get("clobTokenIds") or "[]")
        except ValueError:
            toks = []
        books = []
        for tk in toks[:2]:
            st, b = P.jreq(f"{P.CLOB}/book?token_id={tk}", tries=1, timeout=15)
            asks = sorted((P.fnum(x["price"]), P.fnum(x["size"])) for x in (b or {}).get("asks", [])) if isinstance(b, dict) else []
            books.append(asks[0] if asks else None)
        best = None
        if ya is not None and na is not None and len(books) == 2 and books[0] and books[1]:
            for ka, pp in ((ya, books[1][0]), (na, books[0][0])):
                if not ka or not pp:
                    continue
                n = 20.0 / (ka + pp)
                net = s15.lock_net(ka, pp, s15.kalshi_fee(n, ka, mult), 0.0, n)
                if best is None or net > best[0]:
                    best = (net, n * (ka + pp))
        if best:
            ct = P.iso(km_.get("close_time")) or now
            days = max((ct - now) / 86400.0, 0.25)
            row["lock_net_usd_20"], row["cost_usd"], row["days"] = best[0], best[1], days
            alloc.append({"net_usd": best[0], "cost_usd": best[1], "days": days})
        rows.append(row)
        time.sleep(0.3)
    return {"t": round(now), "ok": True, "kalshi_n": len(km), "poly_n": len(pm), "kalshi_classified": len(kf),
            "poly_classified": len(pf), "matched_n": len(matched), "near_miss_24h": near, "fee_excluded": fee_excl,
            "matched": rows, "alloc_yield": s15.allocate(alloc) if alloc else 0.0}


def s4_collect(d, minutes=330):
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    state = jload(d / "state.json", {})
    if state.get("done"):
        log("window already complete")
        return
    snaps = lines(d / "snaps.jsonl")
    state.setdefault("started", time.time())
    end = time.time() + minutes * 60
    last_flush = time.time()
    while time.time() < end:
        okn = sum(1 for s in snaps if s.get("ok"))
        due = (not snaps) or (time.time() - snaps[-1]["t"] >= 3500 and time.gmtime().tm_min >= 10)
        if due:
            try:
                s = s4_snapshot()
            except Exception as e:  # noqa: BLE001  a crashed snapshot is a logged void, not a silent hole
                s = {"t": round(time.time()), "ok": False, "error": repr(e)[:200]}
            snaps.append(s)
            append(d / "snaps.jsonl", s)
            log("s4 snapshot", {k: s.get(k) for k in ("ok", "kalshi_n", "poly_n", "matched_n", "near_miss_24h", "alloc_yield", "error")})
            if sum(1 for x in snaps if x.get("ok")) >= S4_SNAPS:
                state["done"] = True
                break
        if time.time() - last_flush > FLUSH_S:
            (d / "state.json").write_text(json.dumps(state))
            push(d)
            last_flush = time.time()
        time.sleep(30)
    (d / "state.json").write_text(json.dumps(state))
    s4_eval(d)
    push(d)
    if not state.get("done"):
        chain_next("s4_collect")


def s4_eval(d):
    d = Path(d)
    allsn = lines(d / "snaps.jsonl")
    snaps = [s for s in allsn if s.get("ok")]
    out = s15_eval.s4_evaluate(snaps)
    out["failed_snapshots"] = len(allsn) - len(snaps)
    out["near_miss_24h_max"] = max((s.get("near_miss_24h", 0) for s in snaps), default=0)
    out["classified_median"] = {"kalshi": P.med([s.get("kalshi_classified") for s in snaps]), "polymarket": P.med([s.get("poly_classified") for s in snaps])}
    out["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (d / "summary.json").write_text(json.dumps(out, indent=1))
    log("s4", out["status"], {k: out[k] for k in ("snapshots", "distinct_pairs", "pairs_per_day", "mean_alloc_yield_per_day")})
    return out


if __name__ == "__main__":
    mode, dd = sys.argv[1], sys.argv[2]
    mins = int(sys.argv[3]) if len(sys.argv) > 3 else 330
    {"s2_collect": lambda: s2_collect(dd, mins), "s4_collect": lambda: s4_collect(dd, mins),
     "s2_eval": lambda: s2_eval(dd), "s4_eval": lambda: s4_eval(dd)}[mode]()
