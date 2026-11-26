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
