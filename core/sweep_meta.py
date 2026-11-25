"""sweep meta-allocator (family meta1): choose WHICH kept trades to take, from per-trade rows of earlier screens. Pure functions.

A trade is {src, rule, t (entry ts), x (exit ts), net (per unit notional, after the screen's costs)}. Every feature of a trade is
computed from trades of the same rule that had already EXITED before this trade's entry (x <= t): nothing from the future, nothing from
the trade itself. Chronological splits fixed in the config; the scorer is fitted on train only; validation and test are only read.

  strategy A "trailing": take a trade while the mean net of the rule's last `window` closed trades is > 0 (its gross mean beats its cost)
  strategy B "decile":   pooled monotone-bin scorer. On train, the trailing means m of all trades are cut into equal-count bins, the bin
                         means of the next trade's net are made monotone (pool adjacent violators) and the top decile bin is taken, when
                         its monotone value is > 0.
Evidence: mean net of the selected trades per split against random subsets of the same size drawn from the scorable trades of the same
split (same pool), p = share of draws with mean >= the strategy's.
"""
import bisect
import random


def trailing_means(trades, window):
    """Adds m = mean net of the last `window` closed trades of the same rule (None when fewer exist). Returns the trades sorted by t."""
    by = {}
    for tr in trades:
        by.setdefault((tr["src"], tr["rule"]), []).append(tr)
    out = []
    for lst in by.values():
        closed = sorted(lst, key=lambda z: z["x"])
        xs = [z["x"] for z in closed]
        pre = [0.0]
        for z in closed:
            pre.append(pre[-1] + z["net"])
        for tr in lst:
            k = bisect.bisect_right(xs, tr["t"])           # trades that exited at or before the entry
            tr["m"] = (pre[k] - pre[k - window]) / window if k >= window else None
            out.append(tr)
    out.sort(key=lambda z: (z["t"], z["rule"]))
    return out


def pav_increasing(values, weights):
    """Isotonic (non-decreasing) fit by pool adjacent violators."""
    blocks = []
    for v, w in zip(values, weights):
        blocks.append([v * w, w, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            a = blocks.pop()
            blocks[-1][0] += a[0]
            blocks[-1][1] += a[1]
            blocks[-1][2] += a[2]
    out = []
    for s, w, n in blocks:
        out.extend([s / w] * n)
    return out


def fit_scorer(train, bins=10):
    """train: scorable trades (m not None). Returns {cut, top_value, bins: [{lo, n, mean, iso}]} or None when too few."""
    rows = sorted(((z["m"], z["net"]) for z in train))
    if len(rows) < bins * 5:
        return None
    size = len(rows) / bins
    groups = [rows[int(i * size):int((i + 1) * size)] for i in range(bins)]
    means = [sum(n for _, n in g) / len(g) for g in groups]
    iso = pav_increasing(means, [len(g) for g in groups])
    return {"cut": groups[-1][0][0], "top_value": iso[-1],
            "bins": [{"lo": g[0][0], "n": len(g), "mean": m, "iso": i} for g, m, i in zip(groups, means, iso)]}


def select(trades, strategy, scorer=None):
    if strategy == "trailing":
        return [z for z in trades if z["m"] is not None and z["m"] > 0]
    if scorer is None or scorer["top_value"] <= 0:
        return []
    return [z for z in trades if z["m"] is not None and z["m"] >= scorer["cut"]]


def split_of(t, bounds):
    for k, (a, b) in bounds.items():
        if a <= t < b:
            return k
    return None


def control_p(selected_nets, universe_nets, draws, rng):
    """Share of random same-size subsets of the universe whose mean is >= the selected mean."""
    n = len(selected_nets)
    if n == 0 or n > len(universe_nets):
        return 1.0
    obs = sum(selected_nets) / n
    hits = 0
    for _ in range(draws):
        if sum(rng.sample(universe_nets, n)) / n >= obs:
            hits += 1
    return (hits + 1) / (draws + 1)


def evaluate(trades, bounds, window=60, bins=10, draws=2000, seed=20261125, min_trades=30, alpha=0.05):
    """trades: one pool. Returns {strategy: {...}} with per-split numbers and the pass flag."""
    ts = trailing_means([dict(z) for z in trades], window)
    by_split = {k: [z for z in ts if split_of(z["t"], bounds) == k and z["m"] is not None] for k in bounds}
    scorer = fit_scorer(by_split["train"], bins)
    out = {}
    for strat in ("trailing", "decile"):
        res = {"scorer": scorer if strat == "decile" else None, "splits": {}}
        rng = random.Random(seed)
        for k in ("validation", "test"):
            uni = [z["net"] for z in by_split[k]]
            sel = [z["net"] for z in select(by_split[k], strat, scorer)]
            res["splits"][k] = {"scorable": len(uni), "n": len(sel), "mean": sum(sel) / len(sel) if sel else None,
                                "universe_mean": sum(uni) / len(uni) if uni else None,
                                "ctrl_p": control_p(sel, uni, draws, rng)}
        v, t = res["splits"]["validation"], res["splits"]["test"]
        res["criteria"] = {"val_n": v["n"] >= min_trades, "test_n": t["n"] >= min_trades,
                           "val_mean_pos": v["mean"] is not None and v["mean"] > 0, "test_mean_pos": t["mean"] is not None and t["mean"] > 0,
                           "val_beats_random": v["ctrl_p"] < alpha, "test_beats_random": t["ctrl_p"] < alpha}
        res["n_criteria"] = sum(res["criteria"].values())
        res["passed"] = all(res["criteria"].values())
        res["status"] = "ok" if v["scorable"] >= min_trades and t["scorable"] >= min_trades else "gate"
        out[strat] = res
    return out


# ------------------------------------------------------------------ adapters: kept rows -> trades
def sweep_trades(lines, study, rule_filter=None):
    """lines: parsed jsonl rows of a data/sweep-rows file (fields rule, t, x, net)."""
    out = []
    for r in lines:
        if rule_filter and rule_filter not in r["rule"]:
            continue
        out.append({"src": study, "rule": r["rule"], "t": r["t"], "x": r["x"], "net": r["net"]})
    return out


EVENT_HORIZONS = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "7d": 604800}


def event_trades(rows, name):
    """data/event-rows l1 / l1f / l1g rows: one rule per horizon, net already after the screen's cost and signed for the side."""
    out = []
    for r in rows:
        for h, sec in EVENT_HORIZONS.items():
            v = (r.get("ret") or {}).get(h)
            if v and v.get("net") is not None:
                out.append({"src": "event", "rule": f"{name}/{h}", "t": r["ts"], "x": r["ts"] + sec, "net": v["net"]})
    return out


def poly_trades(rows):
    """data/poly-fv-rows: one rule per (kind, offset, lookback); the side is the one the fair value says is under-priced
    (fair > market: buy YES, fair < market: buy NO); net is the row's per-dollar result of that side."""
    out = []
    for r in rows:
        if r.get("fair") is None or r.get("mkt") is None or r["fair"] == r["mkt"]:
            continue
        leg = r["yes"] if r["fair"] > r["mkt"] else r["no"]
        if not leg or leg.get("net") is None or leg.get("t") is None:
            continue
        out.append({"src": "poly", "rule": f"{r.get('kind')}/off{r.get('off')}/lb{r.get('lb')}", "t": leg["t"], "x": r["end"], "net": leg["net"]})
    return out
