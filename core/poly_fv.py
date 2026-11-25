"""Pure logic for poly_fv (Polymarket short-horizon crypto markets vs digital-option fair value). No network here;
fetchers are in research/studies/poly_fv.py. Rules are locked in research/studies/protocol_poly_fv.md.

A trade is {'t': unix s, 'side': 'BUY'|'SELL', 'idx': 0 (first outcome token) | 1, 'price': float, 'size': shares}.
Fill model = Thin B's: a buy fills at the first recorded BUY trade on the wanted token at least LATENCY_S after the
decision time, size x price >= MIN_FILL_USD, plus HAIRCUT; price-history points are never fills."""
import bisect
import itertools
import math
import statistics

MIN = 60
LATENCY_S = 300
MIN_FILL_USD = 10.0
HAIRCUT = 0.005
MAX_FILL = 0.985
FILL_WINDOW_S = 20 * MIN         # a fill must come within 20 minutes of the earliest allowed time
CLOSE_GUARD_S = 60               # no fill / exit later than this before the scheduled end
MAX_QUOTE_AGE_S = 30 * MIN       # the market price at decision time is the last trade, at most this old
MIN_FILL = 0.01

THRESHOLDS = (0.05, 0.08, 0.12)
OFFSETS_MIN = (60, 30, 10)
LOOKBACKS_MIN = (60, 240, 1440)
EXITS = ("hold", "fair")
RULES = [{"id": f"d{int(t * 100):02d}_o{o}_l{l}_{x}", "thr": t, "off": o, "lb": l, "exit": x}
         for t, o, l, x in itertools.product(THRESHOLDS, OFFSETS_MIN, LOOKBACKS_MIN, EXITS)]
N_RULES = len(RULES)

STAGE0_X = 0.2
STAGE0_MIN_N = 30
ALPHA = 0.05


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def realised_sigma(closes, lookback_min):
    """Std of 1-minute log returns over the last `lookback_min` closes (closes ascending, one per minute)."""
    c = closes[-(lookback_min + 1):]
    if len(c) < max(20, lookback_min // 2):
        return None
    r = [math.log(b / a) for a, b in zip(c, c[1:]) if a > 0 and b > 0]
    if len(r) < 10:
        return None
    return max(statistics.pstdev(r), 1e-5)


def fair_yes(spot, strike, sigma_min, tau_min):
    """P(spot at end >= strike) for a driftless lognormal with per-minute vol sigma_min and tau_min minutes left."""
    if spot <= 0 or strike <= 0 or sigma_min is None:
        return None
    if tau_min <= 0:
        return 1.0 if spot >= strike else 0.0
    return phi(math.log(spot / strike) / (sigma_min * math.sqrt(tau_min)))


def fee_per_share(price, rate, exp):
    """Taker fee per share, Polymarket crypto formula rate x (p (1 - p)) ** exp; rate 0 = no fee."""
    if not rate:
        return 0.0
    return rate * (price * (1 - price)) ** exp


def yes_equiv(tr):
    return tr["price"] if tr["idx"] == 0 else 1 - tr["price"]


def last_yes_before(trades, t, max_age=MAX_QUOTE_AGE_S):
    ts = [x["t"] for x in trades]
    i = bisect.bisect_left(ts, t) - 1
    if i < 0 or t - trades[i]["t"] > max_age:
        return None
    return yes_equiv(trades[i])


def first_buy(trades, idx, t_from, t_to, min_usd=MIN_FILL_USD):
    ts = [x["t"] for x in trades]
    for i in range(bisect.bisect_left(ts, t_from), len(trades)):
        x = trades[i]
        if x["t"] > t_to:
            return None
        if x["idx"] == idx and x["side"] == "BUY" and x["size"] * x["price"] >= min_usd:
            return x
    return None


def sell_records(trades, idx, t_from, t_to, min_usd=MIN_FILL_USD):
    """Running-maximum SELL trades on token idx in [t_from, t_to]: [[t, price], ...] with strictly rising prices. The first
    sell at or above any level X is the first record with price >= X, so one short list serves every fair-value exit."""
    out, best = [], -1.0
    for x in trades:
        if x["t"] < t_from:
            continue
        if x["t"] > t_to:
            break
        if x["idx"] == idx and x["side"] == "SELL" and x["size"] * x["price"] >= min_usd and x["price"] > best:
            best = x["price"]
            out.append([x["t"], round(x["price"], 4)])
    return out


def bet_net(payoff, price, fee_rate, fee_exp):
    """Return on the stake of buying at fill `price` (+ haircut + taker fee) and receiving `payoff` per share."""
    cost = price + HAIRCUT + fee_per_share(price, fee_rate, fee_exp)
    return payoff / cost - 1


def exit_net(sell_price, buy_price, fee_rate, fee_exp):
    """Return of buying at buy_price and selling at sell_price (both with haircut and taker fee)."""
    cost = buy_price + HAIRCUT + fee_per_share(buy_price, fee_rate, fee_exp)
    proceeds = sell_price - HAIRCUT - fee_per_share(sell_price, fee_rate, fee_exp)
    return proceeds / cost - 1


def market_rows(m, trades, spot_t, spot_c, strike, offsets=OFFSETS_MIN, lookbacks=LOOKBACKS_MIN):
    """Per-bet candidate rows of one market. m: {'id','coin','kind','end','yes_won','fee_rate','fee_exp'};
    spot_t / spot_c: ascending minute-start timestamps and closes of the spot pair; strike: spot threshold (Yes = spot >= strike at end).
    One row per (offset, lookback) with a fair value and a market price; the fills are per offset and shared."""
    rows = []
    if not trades or strike is None:
        return rows
    end = m["end"]
    fr, fe = m.get("fee_rate", 0.0), m.get("fee_exp", 1.0)
    for off in offsets:
        t0 = end - off * MIN
        mkt = last_yes_before(trades, t0)
        if mkt is None:
            continue
        i = bisect.bisect_left(spot_t, t0 // 60 * 60) - 1       # last minute that is complete at t0
        if i < 0 or t0 - spot_t[i] > 3 * MIN:
            continue
        spot = spot_c[i]
        series = spot_c[max(0, i - max(lookbacks)):i + 1]
        t_lo, t_hi = t0 + LATENCY_S, min(t0 + LATENCY_S + FILL_WINDOW_S, end - CLOSE_GUARD_S)
        fills = {}
        for idx in (0, 1):
            f = first_buy(trades, idx, t_lo, t_hi)
            if f and MIN_FILL <= f["price"] <= MAX_FILL:
                payoff = 1.0 if (m["yes_won"] if idx == 0 else not m["yes_won"]) else 0.0
                fills[idx] = {"price": round(f["price"], 4), "t": f["t"], "net": bet_net(payoff, f["price"], fr, fe),
                              "payoff": payoff, "sells": sell_records(trades, idx, f["t"] + LATENCY_S, end - CLOSE_GUARD_S)}
        for lb in lookbacks:
            sig = realised_sigma(series, lb)
            fair = fair_yes(spot, strike, sig, off) if sig else None
            if fair is None:
                continue
            rows.append({"id": m["id"], "coin": m["coin"], "kind": m["kind"], "end": end, "off": off, "lb": lb,
                         "won": m["yes_won"], "fair": round(fair, 4), "mkt": round(mkt, 4), "spot": spot, "strike": strike,
                         "fee_rate": fr, "fee_exp": fe,
                         "yes": fills.get(0), "no": fills.get(1)})
    return rows


def apply_rule(rule, row):
    """(side idx, bet dict) or None. side 0 = buy token 0 (Yes/Up), 1 = buy token 1. The bet carries the net return of the
    rule's exit and the random-side control (mean of both sides' net returns at the same time, hold)."""
    if row["off"] != rule["off"] or row["lb"] != rule["lb"]:
        return None
    dev = row["fair"] - row["mkt"]
    if abs(dev) < rule["thr"]:
        return None
    idx = 0 if dev > 0 else 1
    f = row["yes"] if idx == 0 else row["no"]
    if not f:
        return None
    net, exited = f["net"], False
    if rule["exit"] == "fair":
        target = row["fair"] if idx == 0 else 1 - row["fair"]
        for t, p in f["sells"]:
            if p >= target:
                net, exited = exit_net(p, f["price"], row["fee_rate"], row["fee_exp"]), True
                break
    ctl = None
    if row["yes"] and row["no"]:
        ctl = 0.5 * (row["yes"]["net"] + row["no"]["net"])
    return idx, {"t": f["t"], "end": row["end"], "net": net, "exited": exited, "ctl": ctl, "id": row["id"], "coin": row["coin"]}


def day_of(ts):
    return int(ts // 86400)


def cluster_stats(values, days):
    """Mean, cluster-robust (UTC day) standard error and one-sided p (mean > 0, normal approximation)."""
    n = len(values)
    if n < 2:
        return {"n": n, "mean": values[0] if n else None, "se": None, "p": None}
    m = sum(values) / n
    by = {}
    for v, d in zip(values, days):
        by[d] = by.get(d, 0.0) + (v - m)
    se = math.sqrt(sum(s * s for s in by.values())) / n
    if se == 0:
        return {"n": n, "mean": m, "se": 0.0, "p": 0.0 if m > 0 else 1.0}
    return {"n": n, "mean": m, "se": se, "p": 1 - phi(m / se)}


def holm(ps):
    """Holm-Bonferroni adjusted p-values (None stays None; the family size counts every entry)."""
    k = len(ps)
    idx = sorted((i for i, p in enumerate(ps) if p is not None), key=lambda i: ps[i])
    out, run = [None] * k, 0.0
    for rank, i in enumerate(idx):
        run = max(run, min(1.0, (k - rank) * ps[i]))
        out[i] = run
    return out


def months_span(ts_list):
    if not ts_list:
        return 0.0
    return max((max(ts_list) - min(ts_list)) / (30.4375 * 86400), 1 / 30.4375)


def stage0_x(nets, ts):
    """Monthly x = bets per month x (mean / std)^2 (0 when the mean is not positive)."""
    n = len(nets)
    if n < 2:
        return 0.0
    m = sum(nets) / n
    sd = statistics.pstdev(nets)
    if m <= 0 or sd == 0:
        return 0.0
    return n / months_span(ts) * (m / sd) ** 2


def evaluate(rows, bounds, folds):
    """rows: all per-bet candidate rows (dedupe by (id, off, lb)). bounds {'train','validation','test': (a, b)} on `end`;
    folds: list of (a, b) rolling windows over validation+test. Returns the per-rule table and the family verdict."""
    seen, uniq = set(), []
    for r in rows:
        k = (r["id"], r["off"], r["lb"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    by_cfg = {}
    for r in uniq:
        by_cfg.setdefault((r["off"], r["lb"]), []).append(r)
    table = []
    for rule in RULES:
        bets = []
        for r in by_cfg.get((rule["off"], rule["lb"]), []):
            got = apply_rule(rule, r)
            if got:
                bets.append(got[1])
        entry = {"rule": rule["id"], "n_all": len(bets)}
        for sp, (a, b) in bounds.items():
            v = [x for x in bets if a <= x["end"] < b]
            nets = [x["net"] for x in v]
            paired = [x["net"] - x["ctl"] for x in v if x["ctl"] is not None]
            pdays = [day_of(x["end"]) for x in v if x["ctl"] is not None]
            st = cluster_stats(nets, [day_of(x["end"]) for x in v])
            pst = cluster_stats(paired, pdays)
            entry[sp] = {"n": len(v), "mean": st["mean"], "p_abs": st["p"], "n_ctl": len(paired), "edge_vs_ctl": pst["mean"],
                         "p_ctl": pst["p"], "x_month": stage0_x(nets, [x["end"] for x in v]) if sp == "train" else None}
        vt = [x for x in bets if bounds["validation"][0] <= x["end"] < bounds["test"][1]]
        entry["x_month_valtest"] = stage0_x([x["net"] for x in vt], [x["end"] for x in vt])
        entry["fold_means"] = []
        for a, b in folds:
            f = [x["net"] for x in bets if a <= x["end"] < b]
            entry["fold_means"].append(round(sum(f) / len(f), 5) if len(f) >= 5 else None)
        table.append(entry)
    hp = holm([e["validation"]["p_ctl"] for e in table])
    for e, h in zip(table, hp):
        e["holm_p_val"] = h
        tr, va, te = e["train"], e["validation"], e["test"]
        e["stage0"] = bool(tr["n"] >= STAGE0_MIN_N and (tr["x_month"] or 0) >= STAGE0_X)
        used = [m for m in e["fold_means"] if m is not None]
        e["folds_positive"] = f"{sum(1 for m in used if m > 0)}/{len(used)}"
        e["passed"] = bool(e["stage0"] and h is not None and h < ALPHA and (va["mean"] or 0) > 0 and (va["edge_vs_ctl"] or 0) > 0
                           and (te["mean"] or 0) > 0 and (te["edge_vs_ctl"] or 0) > 0 and used and sum(1 for m in used if m > 0) * 2 > len(used))
    return {"table": table, "n_rules": N_RULES, "n_stage0": sum(1 for e in table if e["stage0"]),
            "passed": [e["rule"] for e in table if e["passed"]]}
