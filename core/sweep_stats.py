"""sweep statistics: step-0 gate, split metrics, block bootstrap, 30-day compounded multiples, Holm, pass rule.

Pure functions, standard library only. Trades come from core.sweep_engine (dicts with t, x, net, cost, mfe, mae).
A trade belongs to the split of its signal timestamp t. Returns are per unit notional; a rule's weight per trade is
w = lev / k (k = max concurrent trades), so the account return of a trade is w * net.
"""
import math
import random

DAY = 86400
LIQ_LEFT = 0.05            # a trade whose adverse move times w reaches 1 - LIQ_LEFT is liquidated: 5% of equity is left
LIQ_AT = 1.0 - LIQ_LEFT


def quantile(sorted_x, q):
    if not sorted_x:
        return None
    return sorted_x[min(len(sorted_x) - 1, max(0, int(q * (len(sorted_x) - 1) + 0.5)))]


def mean(x):
    return sum(x) / len(x) if x else None


def in_split(trades, a, b):
    return [t for t in trades if a <= t["t"] < b]


def day_series(trades, w, a, b, net_key="net"):
    """One account return per UTC day of [a, b): the sum of w * net of the trades signalled that day (0 on idle days)."""
    n = int((b - a) // DAY)
    out = [0.0] * n
    for t in trades:
        if a <= t["t"] < b:
            k = int((t["t"] - a) // DAY)
            if 0 <= k < n:
                out[k] += w * (t[net_key] if net_key == "net" else t["net"] - t["cost"])
    return out


def block_p(v, block=20, n_boot=2000, seed=11):
    """One-sided p that the mean of the daily series is <= 0: moving-block bootstrap of the series centred under the null.
    Floor is 1 / (n_boot + 1). Returns 1.0 for a non-positive mean or a series shorter than two blocks."""
    m = len(v)
    if m < 2 * block:
        return 1.0
    m0 = sum(v) / m
    if m0 <= 0:
        return 1.0
    pre = [0.0]
    for x in v:
        pre.append(pre[-1] + (x - m0))
    sums = [pre[j + block] - pre[j] for j in range(m - block + 1)]
    nb = math.ceil(m / block)
    thr = m0 * nb * block
    rng = random.Random(seed)
    choices = rng.choices
    hits = 0
    for _ in range(n_boot):
        if sum(choices(sums, k=nb)) >= thr:
            hits += 1
    return (hits + 1) / (n_boot + 1)


def p_adaptive(v, coarse=2000, fine=300_000, cut=0.02):
    """Block p with 2,000 resamples; rerun with 300,000 (floor 3e-6) only when p <= cut, so Bonferroni/Holm bars of a few
    1e-4 are reachable without paying for the hopeless rules."""
    p = block_p(v, n_boot=coarse)
    if p <= cut:
        return block_p(v, n_boot=fine)
    return p


def holm(pvals, alpha=0.05):
    """pvals {id: p} -> {id: Holm-adjusted p} (monotone, capped at 1). Family size m = len(pvals)."""
    m = len(pvals)
    order = sorted(pvals, key=lambda k: pvals[k])
    adj, run = {}, 0.0
    for j, k in enumerate(order):
        run = max(run, min(1.0, (m - j) * pvals[k]))
        adj[k] = run
    return adj


def month_dist(trades, w, a, b, window=30):
    """Distribution of the compounded account multiple over every rolling `window`-day window inside [a, b) (a window starts
    each day): trades are compounded by exit day at factor 1 + w * net; a liquidated trade leaves 5%; a factor <= 0 is ruin."""
    nd = int((b - a) // DAY)
    if nd < window:
        return {"n": 0}
    logs, zeros = [0.0] * nd, [0] * nd
    for t in sorted((t for t in trades if a <= t["t"] < b), key=lambda z: z["x"]):
        k = int((t["x"] - a) // DAY)
        k = min(max(k, 0), nd - 1)
        f = LIQ_LEFT if w * t["mae"] >= LIQ_AT else 1 + w * t["net"]
        if f <= 1e-9 or zeros[k]:
            zeros[k] = 1
        else:
            logs[k] += math.log(f)
    pl, pz = [0.0], [0]
    for k in range(nd):
        pl.append(pl[-1] + logs[k])
        pz.append(pz[-1] + zeros[k])
    mult = []
    for s in range(nd - window + 1):
        mult.append(0.0 if pz[s + window] - pz[s] else math.exp(min(50.0, pl[s + window] - pl[s])))
    mult.sort()
    nw = len(mult)
    return {"n": nw, "median": quantile(mult, 0.5), "p10": quantile(mult, 0.1), "p90": quantile(mult, 0.9),
            "min": mult[0], "max": mult[-1], "share_3x": sum(1 for x in mult if x >= 3.0) / nw,
            "share_gt1": sum(1 for x in mult if x > 1.0) / nw}


def gate(train_trades, rule, cfg, train_days, median_price=None, min_notional_usd=0.0):
    """Step-0 gate on TRAIN data only (never looks at validation or test): enough trades, notional reachable with the
    account, and the all-win ceiling must allow a 3x month. Ceiling: every trade earns the 90th-percentile favourable
    excursion seen in train, times w, minus the round-trip cost; compounded over the trades per 30 days it must reach the
    target multiple. Returns (ok, info)."""
    g = cfg.get("gate", {})
    min_tr = int(g.get("min_train_trades", 30))
    target = float(g.get("target_multiple", 3.0))
    q = float(g.get("mfe_quantile", 0.9))
    acct = float(cfg.get("account_usd", 147.0))
    w = float(rule["size"]["lev"]) / int(rule["size"].get("k", 1))
    n = len(train_trades)
    tpm = n / (train_days / 30.0) if train_days > 0 else 0.0
    info = {"n_train": n, "tpm": round(tpm, 3), "w": w}
    if n < min_tr:
        return False, dict(info, reason=f"train trades {n} < {min_tr}")
    if min_notional_usd and w * acct < min_notional_usd:
        return False, dict(info, reason=f"min notional {min_notional_usd:.0f} USD > account*w {w * acct:.0f} USD")
    mfe = quantile(sorted(t["mfe"] for t in train_trades), q)
    cost = quantile(sorted(t["cost"] for t in train_trades), 0.5)
    best = w * (mfe - cost)
    info.update(mfe_q=round(mfe, 5), cost_med=round(cost, 5), best_trade=round(best, 5))
    if best <= 0:
        return False, dict(info, reason="all-win ceiling: best trade does not beat cost")
    ceil_mult = math.exp(min(50.0, tpm * math.log(1 + best)))
    info["ceiling_multiple"] = round(ceil_mult, 3)
    if ceil_mult < target:
        return False, dict(info, reason=f"all-win ceiling {ceil_mult:.2f}x < {target:g}x per month")
    return True, info


def split_metrics(trades, w, a, b, with_p=False):
    tr = in_split(trades, a, b)
    out = {"n": len(tr)}
    if not tr:
        return dict(out, mean=None, mean_2x=None, mean_day=None, win=None)
    nets = [t["net"] for t in tr]
    out.update(mean=mean(nets), mean_2x=mean([t["net"] - t["cost"] for t in tr]),
               win=sum(1 for x in nets if x > 0) / len(nets))
    ds = day_series(trades, w, a, b)
    out["mean_day"] = mean(ds)
    if with_p:
        out["p"] = p_adaptive(ds)
    else:
        out["p"] = block_p(ds)
    out["mult30"] = month_dist(trades, w, a, b)
    return out


def evaluate(trades, rule, bounds):
    """Metrics of a rule that passed the gate: train / validation / test (validation p is the significance test)."""
    w = float(rule["size"]["lev"]) / int(rule["size"].get("k", 1))
    return {"train": split_metrics(trades, w, *bounds["train"]),
            "validation": split_metrics(trades, w, *bounds["validation"], with_p=True),
            "test": split_metrics(trades, w, *bounds["test"])}


CRITERIA = ("val_net_positive", "test_net_positive", "val_2x_positive", "test_2x_positive", "enough_trades",
            "significant_holm")


def criteria(row, cfg):
    """Booleans of the pass rule for one evaluated row (row['validation'] etc.; row['p_adj'] set by the merge)."""
    pc = cfg.get("pass", {})
    v, t = row["validation"], row["test"]
    pos = lambda x: x is not None and x > 0   # noqa: E731
    return {"val_net_positive": pos(v["mean"]), "test_net_positive": pos(t["mean"]),
            "val_2x_positive": pos(v["mean_2x"]), "test_2x_positive": pos(t["mean_2x"]),
            "enough_trades": v["n"] >= int(pc.get("min_val_trades", 30)) and t["n"] >= int(pc.get("min_test_trades", 20)),
            "significant_holm": row.get("p_adj") is not None and row["p_adj"] < float(cfg.get("alpha", 0.05))}


def judge_family(rows, cfg):
    """Holm over the rules that passed the gate (the gate uses train only, so the family is fixed before validation).
    Mutates rows: p_adj, criteria, n_criteria, passed. Returns the family info."""
    ev = [r for r in rows if r["status"] == "ok"]
    alpha = float(cfg.get("alpha", 0.05))
    adj = holm({r["id"]: r["validation"]["p"] for r in ev}, alpha)
    for r in ev:
        r["p_adj"] = adj[r["id"]]
        r["criteria"] = criteria(r, cfg)
        r["n_criteria"] = sum(r["criteria"].values())
        r["passed"] = all(r["criteria"].values())
    m = len(ev)
    return {"holm_m": m, "bonferroni_bar": alpha / m if m else None, "alpha": alpha}


def closeness_key(r):
    """Smaller is closer to passing: more criteria met, then lower validation p, then higher validation mean."""
    return (-r["n_criteria"], r["validation"]["p"], -(r["validation"]["mean"] or -1.0))


def compact(r, family=None):
    """One leaderboard line for an evaluated row."""
    v, t = r["validation"], r["test"]
    return {"id": r["id"], "family": family, "n_criteria": r["n_criteria"], "passed": r["passed"], "lev": r.get("lev"),
            "val_n": v["n"], "val_mean": v["mean"], "val_mean_2x": v["mean_2x"], "val_p": v["p"], "p_adj": r["p_adj"],
            "test_n": t["n"], "test_mean": t["mean"], "test_mean_2x": t["mean_2x"],
            "val_mult30_median": (v.get("mult30") or {}).get("median"), "val_share_3x": (v.get("mult30") or {}).get("share_3x"),
            "test_mult30_median": (t.get("mult30") or {}).get("median"), "test_share_3x": (t.get("mult30") or {}).get("share_3x")}
