"""Pure logic for Q1 (follow point-in-time ranked public wallets). No network here; fetchers are in
research/studies/wallet_follow.py. Rules: research/studies/protocol_wallet_follow_probe_20261127.md (counts-only probe).
Kept under research/ (not core/) so a merge does not redeploy production. Standard library only."""
import hashlib
import statistics

MIN_POS_USD = 500.0            # a "position" counts when its buy cost is at least this
MIN_RESOLVED = 100             # kill-0: distinct resolved conditions per wallet
DEPTH_CUTOFF_TS = 1748217600   # 2025-05-26 00:00 UTC: 18 months before the probe date (2026-11-26)
MIN_WALLETS = 300
EXIT_FRAC = 0.95               # a position is "exited by the wallet" when it sold >= 95% of the shares bought
STANDALONE_MULT = 3.0
MONTH_DAYS = 30.0


def parse_row(r):
    """Data-API v2 trade/activity row -> dict or None. Keeps the condition id, token, side, price, size, time."""
    try:
        return {"t": int(r["timestamp"]), "side": str(r["side"]).upper(), "price": float(r["price"]), "size": float(r["size"]),
                "token": str(r.get("token_id") or r.get("asset") or ""), "cond": str(r.get("condition_id") or r.get("conditionId") or ""),
                "tx": str(r.get("transaction_hash") or ""), "idx": r.get("outcome_index"), "wallet": str(r.get("proxy_wallet") or "")}
    except (KeyError, TypeError, ValueError):
        return None


def dedupe(rows):
    """(unique rows, duplicate count). Key: transaction hash, token, side, price, size, time."""
    seen, out = set(), []
    for r in rows:
        k = (r["tx"], r["token"], r["side"], r["price"], r["size"], r["t"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out, len(rows) - len(out)


def positions(rows):
    """Group one wallet's rows into positions per (condition, token): buy cost, shares, avg entry price, first buy time,
    sold shares, last sell time. Outcome-free: no P&L."""
    pos = {}
    for r in sorted(rows, key=lambda x: x["t"]):
        k = (r["cond"], r["token"])
        p = pos.setdefault(k, {"cond": r["cond"], "token": r["token"], "cost": 0.0, "bought": 0.0, "sold": 0.0, "first_buy": None, "last_sell": None})
        if r["side"] == "BUY":
            p["cost"] += r["price"] * r["size"]
            p["bought"] += r["size"]
            if p["first_buy"] is None:
                p["first_buy"] = r["t"]
        elif r["side"] == "SELL":
            p["sold"] += r["size"]
            p["last_sell"] = r["t"]
    out = []
    for p in pos.values():
        if p["bought"] > 0:
            p["entry"] = p["cost"] / p["bought"]
            out.append(p)
    return out


def exit_time(p, closed_at):
    """The wallet's own exit when it sold >= 95% of what it bought, else the market's close time (None while unresolved)."""
    if p["sold"] >= EXIT_FRAC * p["bought"] and p["last_sell"] is not None:
        return p["last_sell"]
    return closed_at


def two_sided(rows):
    """Share of the wallet's conditions where it BOUGHT both tokens: a market-maker marker (counts only)."""
    toks = {}
    for r in rows:
        if r["side"] == "BUY":
            toks.setdefault(r["cond"], set()).add(r["token"])
    return (sum(1 for s in toks.values() if len(s) >= 2) / len(toks)) if toks else 0.0


def wallet_summary(rows, closed_map, cutoff_ts=DEPTH_CUTOFF_TS):
    """Counts for one wallet. closed_map: condition -> close timestamp (resolved) or None. Returns a dict, no P&L."""
    ps = positions(rows)
    conds = {r["cond"] for r in rows}
    resolved = sum(1 for c in conds if closed_map.get(c))
    big = [p for p in ps if p["cost"] >= MIN_POS_USD]
    holds, entries = [], []
    for p in big:
        ex = exit_time(p, closed_map.get(p["cond"]))
        if ex is not None and p["first_buy"] is not None and ex >= p["first_buy"]:
            holds.append((ex - p["first_buy"]) / 86400.0)
            entries.append(p["entry"])
    ts = [r["t"] for r in rows]
    return {"n_rows": len(rows), "earliest": min(ts) if ts else None, "latest": max(ts) if ts else None, "conds": len(conds),
            "resolved": resolved, "positions": len(ps), "big_positions": len(big), "big_with_exit": len(holds),
            "holds": holds, "entries": entries, "two_sided": two_sided(rows),
            "qualifies": bool(ts) and min(ts) <= cutoff_ts and resolved >= MIN_RESOLVED}


def ceiling_multiple(median_hold_days, median_entry):
    """All-win ceiling of one 147 USD stake that turns over every median hold: (1 / entry) ** (30 / hold) with entry = the
    median entry price plus 0.01 (the worse-of fill rule). None when an input is missing or non-positive."""
    if not median_hold_days or median_hold_days <= 0 or median_entry is None:
        return None
    px = min(0.99, median_entry + 0.01)
    return (1.0 / px) ** (MONTH_DAYS / median_hold_days)


def saturation(new_counts):
    """Share of new wallets contributed by the last 5 windows of the frame build (small = the frame saturates)."""
    total = sum(new_counts)
    return (sum(new_counts[-5:]) / total) if total else None


def probe_verdict(n_frame, n_sampled, n_qualify, med_hold, med_entry, sat):
    """Kill 0 (locked): estimated qualifying wallets = frame x qualifying share must be >= 300; the frame is a lower bound,
    so a miss kills only if the frame saturated (last 5 windows added < 20% of the wallets), else 'extend_frame'.
    Standalone ceiling < 3x: 'component_only' (it can still enter the book as a small component)."""
    q = (n_qualify / n_sampled) if n_sampled else 0.0
    est = n_frame * q
    ceil = ceiling_multiple(med_hold, med_entry)
    if est >= MIN_WALLETS:
        wal = "pass"
    elif sat is not None and sat < 0.20:
        wal = "kill"
    else:
        wal = "extend_frame"
    stand = "unknown" if ceil is None else ("standalone_ok" if ceil >= STANDALONE_MULT else "component_only")
    return {"est_qualifying_wallets": round(est, 1), "qualifying_share": round(q, 4), "wallets": wal, "ceiling_multiple": ceil, "standalone": stand}


def med(x):
    return statistics.median(x) if x else None


def sample_order(wallets, seed="q1-wallet-probe-20261127"):
    """Outcome-blind deterministic order: sha256(seed + wallet)."""
    return sorted(wallets, key=lambda w: hashlib.sha256((seed + w).encode()).hexdigest())


def quantile(x, q):
    s = sorted(x)
    return s[min(len(s) - 1, max(0, int(q * (len(s) - 1) + 0.5)))] if s else None


# ======================================================================== Q1 test protocol (protocol_wallet_follow_20261127.md)
import calendar   # noqa: E402
import math       # noqa: E402
import random     # noqa: E402
import time       # noqa: E402

DAY = 86400
RANK_DAYS = 180
MIN_CLOSED = 50                # eligible: closed positions in the ranking window
MIN_VOL_USD = 25000.0          # eligible: buy notional in the ranking window
MM_TWO_SIDED = 0.5             # excluded: bought both tokens in more than this share of the window's conditions
TOP_N = 50
BOTTOM_N = 50
RAND_N = 100
MIN_SIGNAL_USD = 500.0         # first BUY fill of a new position
PX_LO, PX_HI = 0.05, 0.95      # followed wallet's price band
DELAY_S = 60
FILL_WINDOW_S = 1800
SLIP = 0.01
EXIT_FALLBACK_SLIP = 0.02
FILL_MAX = 0.97
PERSIST_DAYS = 90
PERSIST_MIN_POS = 10
SEED = "q1-wallet-follow-20261127"


def ts_day(s):
    return int(calendar.timegm(time.strptime(s, "%Y-%m-%d")))


FOLLOW_MONTHS = [f"{y}-{m:02d}-01" for y, m in [(2025, k) for k in range(4, 13)] + [(2026, k) for k in range(1, 11)]]   # 19 months
BOUNDS = {"train": (ts_day("2025-04-01"), ts_day("2026-01-01")), "validation": (ts_day("2026-01-01"), ts_day("2026-06-01")),
          "test": (ts_day("2026-06-01"), ts_day("2026-11-01"))}


def month_end(day):
    y, m = int(day[:4]), int(day[5:7])
    return ts_day(f"{y + (m == 12)}-{(m % 12) + 1:02d}-01")


def split_of(t):
    for k, (a, b) in BOUNDS.items():
        if a <= t < b:
            return k
    return None


def full_positions(rows):
    """Positions of one wallet's de-duplicated rows with the fields the protocol needs. No P&L here."""
    pos = {}
    for r in sorted(rows, key=lambda x: (x["t"], x["tx"])):
        k = (r["cond"], r["token"])
        p = pos.get(k)
        if p is None:
            p = pos[k] = {"cond": r["cond"], "token": r["token"], "cost": 0.0, "bought": 0.0, "sold": 0.0, "proceeds": 0.0, "t0": None,
                          "px0": None, "usd0": None, "t1": None, "px1": None}
        if r["side"] == "BUY":
            if p["t0"] is None:
                p["t0"], p["px0"], p["usd0"] = r["t"], r["price"], r["price"] * r["size"]
            p["cost"] += r["price"] * r["size"]
            p["bought"] += r["size"]
        elif r["side"] == "SELL":
            p["sold"] += r["size"]
            p["proceeds"] += r["price"] * r["size"]
            p["t1"], p["px1"] = r["t"], r["price"]
    out = [p for p in pos.values() if p["bought"] > 0 and p["t0"] is not None]
    both = {}
    for p in out:
        both[p["cond"]] = both.get(p["cond"], 0) + 1
    for p in out:
        p["both"] = both[p["cond"]] >= 2
    return out


def realize(p, info):
    """(closed_t, pnl, how) of a position or None while open. info = {'closed_at', 'payout': {token: 0.0|1.0}} for the condition.
    The wallet's own exit counts when it sold >= 95% of the shares; else the market's resolution (payout exactly 0 or 1)."""
    if p["sold"] >= EXIT_FRAC * p["bought"] and p["t1"] is not None:
        return p["t1"], p["proceeds"] + (p["bought"] - p["sold"]) * p["px1"] - p["cost"], "exit"
    pay = (info or {}).get("payout") or {}
    ca = (info or {}).get("closed_at")
    v = pay.get(p["token"])
    if ca and v in (0.0, 1.0):
        return ca, p["proceeds"] + (p["bought"] - p["sold"]) * v - p["cost"], "resolved"
    return None


def closed_positions(wpos, infos):
    """[(position, closed_t, pnl, how)] for every closed position of one wallet."""
    out = []
    for p in wpos:
        r = realize(p, infos.get(p["cond"]))
        if r:
            out.append((p, r[0], r[1], r[2]))
    return out


def rank_at(wallets, D):
    """wallets: {w: [(p, closed_t, pnl, how)]}. Rank at ts D using only positions closed in [D - 180 d, D). Eligible: >= 50 closed
    positions, >= 25,000 USD bought, two-sided share <= 0.5. Returns [(w, score, n, vol, roi)] sorted by score descending, then wallet."""
    out = []
    a = D - RANK_DAYS * DAY
    for w, cl in wallets.items():
        win = [c for c in cl if a <= c[1] < D]
        if len(win) < MIN_CLOSED:
            continue
        vol = sum(c[0]["cost"] for c in win)
        if vol < MIN_VOL_USD:
            continue
        conds = {c[0]["cond"] for c in win}
        two = {c[0]["cond"] for c in win if c[0]["both"]}
        if len(two) / len(conds) > MM_TWO_SIDED:
            continue
        score = sum(c[2] for c in win)
        out.append((w, score, len(win), vol, score / vol))
    out.sort(key=lambda z: (-z[1], z[0]))
    return out


def pools(ranked, D_key):
    """top 50, bottom 50 and 100 random of the rest, by sha256(seed + month + wallet). None when fewer than 150 are eligible."""
    n = len(ranked)
    if n < TOP_N + RAND_N:
        return None
    top = [r[0] for r in ranked[:TOP_N]]
    rest = [r[0] for r in ranked[TOP_N:]]
    bottom = [r[0] for r in ranked[-BOTTOM_N:]] if n >= TOP_N + BOTTOM_N else []
    mid = [w for w in rest if w not in set(bottom)]
    rnd = sample_order(mid, SEED + D_key)[:RAND_N]
    return {"top": top, "bottom": bottom, "rand": rnd}


def signals(wpos, infos, a, b):
    """Entries of one wallet: a first BUY fill in [a, b) of >= 500 USD, price in [0.05, 0.95], on a non-fee market with a known
    outcome (the wallet's own exit or a resolution). Returns (entries, dropped counts)."""
    out, drop = [], {"small": 0, "band": 0, "fee": 0, "open": 0}
    for p in wpos:
        if not (a <= p["t0"] < b):
            continue
        if p["usd0"] < MIN_SIGNAL_USD:
            drop["small"] += 1
            continue
        if not (PX_LO <= p["px0"] <= PX_HI):
            drop["band"] += 1
            continue
        info = infos.get(p["cond"]) or {}
        if info.get("fee"):
            drop["fee"] += 1
            continue
        r = realize(p, info)
        if not r:
            drop["open"] += 1
            continue
        own_exit = r[2] == "exit"
        out.append({"cond": p["cond"], "token": p["token"], "t0": p["t0"], "pw": p["px0"], "own_exit": own_exit,
                    "t1": p["t1"] if own_exit else None, "pw1": p["px1"] if own_exit else None,
                    "payout": (info.get("payout") or {}).get(p["token"]), "closed_at": info.get("closed_at")})
    return out, drop


def first_fill(tape, token, side, t_min, t_max):
    """First tape row (taker fills, ascending time) of the token and side with t_min <= t <= t_max. Returns the row or None."""
    for r in tape:
        if r["t"] > t_max:
            return None
        if r["t"] >= t_min and r["token"] == token and r["side"] == side:
            return r
    return None


def price_entry(e, tape):
    """Locked fill rule. Entry: the first tape BUY of the token at least 60 s after the wallet's fill, within 30 min; fill price =
    the worse (higher) of that trade and the wallet's price + 0.01. None = no fill (no trade in the window, or fill above 0.97)."""
    r = first_fill(tape, e["token"], "BUY", e["t0"] + DELAY_S, e["t0"] + DELAY_S + FILL_WINDOW_S)
    if r is None:
        return None
    px = max(r["price"], e["pw"] + SLIP)
    return px if px <= FILL_MAX else None


def price_exit(e, tape):
    """Exit at the wallet's exit: the first tape SELL of the token >= 60 s after their last sell, within 30 min; price = the worse
    (lower) of that trade and their price - 0.01; no such trade: their price - 0.02. Returns (price, time)."""
    t = e["t1"] + DELAY_S
    r = first_fill(tape, e["token"], "SELL", t, t + FILL_WINDOW_S)
    px = min(r["price"], e["pw1"] - SLIP) if r is not None else e["pw1"] - EXIT_FALLBACK_SLIP
    return max(px, 0.001), (r["t"] if r is not None else t)


def make_trade(e, entry_px, tape):
    """One followed entry -> trade dict for core.sweep_stats (net, gross and cost per unit stake). None if it cannot be followed."""
    if e["own_exit"]:
        if e["t1"] < e["t0"] + DELAY_S:
            return None                                 # the wallet left before our delayed fill
        x_px, x_t = price_exit(e, tape)
        w_exit = e["pw1"]
    else:
        if e["payout"] not in (0.0, 1.0) or not e["closed_at"]:
            return None
        x_px, x_t, w_exit = e["payout"], e["closed_at"], e["payout"]
    gross = (w_exit - e["pw"]) / e["pw"]
    net = (x_px - entry_px) / entry_px
    return {"t": e["t0"] + DELAY_S, "x": max(x_t, e["t0"] + DELAY_S), "net": net, "gross": gross, "cost": max(gross - net, 0.0), "fund": 0.0,
            "mfe": (1 - entry_px) / entry_px, "mae": 1.0, "cond": e["cond"], "wallet": e.get("wallet"), "entry": entry_px, "own_exit": e["own_exit"]}


def cluster(trades):
    """Cluster = market: one trade per condition (members averaged; t = first fill, x = last exit)."""
    by = {}
    for t in trades:
        by.setdefault(t["cond"], []).append(t)
    out = []
    for c, ms in by.items():
        n = len(ms)
        out.append({"t": min(m["t"] for m in ms), "x": max(m["x"] for m in ms), "cond": c, "k": n,
                    **{k: sum(m[k] for m in ms) / n for k in ("net", "gross", "cost", "fund", "mfe", "mae", "entry")}})
    out.sort(key=lambda z: (z["t"], z["cond"]))
    return out


def moments(trades, months):
    """n, mean, sd, s = mean / sd, N per month and x = N * s * |s| (signed) of net returns; months = length of the window."""
    n = len(trades)
    nets = [t["net"] for t in trades]
    if n < 2:
        return {"n": n, "mean": nets[0] if n else None, "sd": None, "s": None, "N": n / months if months else None, "x": None}
    m = sum(nets) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in nets) / (n - 1))
    s = m / sd if sd > 0 else None
    N = n / months
    return {"n": n, "mean": m, "sd": sd, "s": s, "N": N, "x": (N * s * abs(s)) if s is not None else None}


def capped_x(trades, months, concurrent=20):
    """x with N capped by capital turns: `concurrent` equal stakes (1/20 of equity each), each turned over every median hold:
    N_cap = concurrent * 30 / median hold days. Returns (x_capped, N_cap, median hold days)."""
    holds = [(t["x"] - t["t"]) / DAY for t in trades]
    mh = statistics.median(holds) if holds else None
    mo = moments(trades, months)
    if mo["s"] is None or not mh:
        return None, None, mh
    ncap = concurrent * 30.0 / max(mh, 1e-6)
    return min(mo["N"], ncap) * mo["s"] * abs(mo["s"]), ncap, mh


def top_share(trades, frac=0.01):
    """Share of total net profit that comes from the best 1% of clusters (at least 1). None when the total is <= 0."""
    nets = sorted((t["net"] for t in trades), reverse=True)
    tot = sum(nets)
    if tot <= 0 or not nets:
        return None
    k = max(1, int(math.ceil(frac * len(nets))))
    return sum(nets[:k]) / tot


def spearman(xs, ys):
    """Spearman rank correlation (average ranks for ties); None below 3 points or without variance."""
    n = len(xs)
    if n < 3:
        return None

    def rk(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0 + 1
            i = j + 1
        return r
    a, b = rk(xs), rk(ys)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def persistence(wallets, D, data_end):
    """Test 1 at ranking date D (no copy rule, no costs): rank on the trailing window (score), read each wallet's forward realised ROI
    on positions first bought in [D, D + 90 d) that are closed by data_end (>= 10 such positions). Returns a dict."""
    ranked = rank_at(wallets, D)
    fwd = {}
    for w, score, *_ in ranked:
        cl = [c for c in wallets[w] if D <= c[0]["t0"] < D + PERSIST_DAYS * DAY and c[1] <= data_end]
        if len(cl) >= PERSIST_MIN_POS:
            vol = sum(c[0]["cost"] for c in cl)
            if vol > 0:
                fwd[w] = sum(c[2] for c in cl) / vol
    sc = {r[0]: r[1] for r in ranked}
    ws = sorted(fwd)
    rho = spearman([sc[w] for w in ws], [fwd[w] for w in ws])
    top = [fwd[r[0]] for r in ranked[:TOP_N] if r[0] in fwd]
    allv = list(fwd.values())
    return {"eligible": len(ranked), "with_forward": len(fwd), "rho": rho, "top_n": len(top),
            "top_median": statistics.median(top) if top else None, "all_median": statistics.median(allv) if allv else None}


def persistence_verdict(rows):
    """Kill if the mean rank correlation over the train ranking dates is <= 0, or the top 50's median forward ROI does not beat the
    median wallet's on average. rows = persistence() dicts of the train dates."""
    rhos = [r["rho"] for r in rows if r["rho"] is not None]
    gaps = [r["top_median"] - r["all_median"] for r in rows if r["top_median"] is not None and r["all_median"] is not None]
    mr = sum(rhos) / len(rhos) if rhos else None
    mg = sum(gaps) / len(gaps) if gaps else None
    return {"dates": len(rows), "mean_rho": mr, "mean_top_minus_median": mg, "kill": (mr is None or mr <= 0 or mg is None or mg <= 0)}


def permutation_p(by_month, n_perm=2000, seed=11):
    """One-sided p that the top wallets' mean net beats the random wallets' under label permutation within each month.
    by_month = {month: {wallet: [net, ...]}} with 'top' wallets marked by by_month[m]['_top'] (a set). Statistic: mean net of all
    top entries minus mean net of all random entries, pooled over months."""
    def stat(assign):
        a, b = [], []
        for m, d in by_month.items():
            for w, nets in d["wallets"].items():
                (a if assign[m][w] else b).extend(nets)
        return (sum(a) / len(a) - sum(b) / len(b)) if a and b else None
    obs_assign = {m: {w: (w in d["top"]) for w in d["wallets"]} for m, d in by_month.items()}
    obs = stat(obs_assign)
    if obs is None:
        return None, None
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        asg = {}
        for m, d in by_month.items():
            ws = sorted(d["wallets"])
            k = len(d["top"])
            pick = set(rng.sample(ws, k)) if 0 < k < len(ws) else set(d["top"])
            asg[m] = {w: (w in pick) for w in ws}
        v = stat(asg)
        if v is not None and v >= obs:
            hits += 1
    return obs, (hits + 1) / (n_perm + 1)
