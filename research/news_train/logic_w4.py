"""News analyst training, round 4 (protocol_w4_20261127.md): pure logic. No network, no clock, stdlib only.
Trains the next prompt / abstention rule on the OPENED historical holdout (data/news-train-hh) and routes at most one version to an unopened forward test.
Everything else (costs, calibrated abstention, the analytic day-clustered t, the random control, the sign test) is reused from the locked logic.py,
logic_r2.py, logic_hh.py and logic_cmp.py."""
import json
import math
import os
from datetime import datetime

from research.news_train import logic as L
from research.news_train import logic_cmp as C
from research.news_train import logic_hh as H
from research.news_train import logic_r2 as R

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_w4.json")
CODES = ("1.01", "1.02", "2.01", "2.02", "2.05", "2.06", "3.01", "4.02", "5.02", "7.01", "8.01")


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------------ split (mechanical, by UTC day, never by eye)
def val_days(days, frac):
    """The last ceil(D * frac) distinct days (sorted) are validation. D = number of distinct days."""
    ds = sorted(set(days))
    n = math.ceil(len(ds) * frac - 1e-9)
    return set(ds[-n:]) if n > 0 else set()


def split_rows(rows, P):
    """rows carry t_pub. -> (train, validation, validation_days). Day = UTC day of t_pub."""
    vd = val_days([L.day_of(r["t_pub"]) for r in rows], P["split"]["val_day_fraction"])
    tr = [r for r in rows if L.day_of(r["t_pub"]) not in vd]
    va = [r for r in rows if L.day_of(r["t_pub"]) in vd]
    return tr, va, sorted(vd)


def assert_train_only(rows, vd):
    """The error-analysis and fit jobs must never hold a validation row."""
    bad = [r["key"] for r in rows if L.day_of(r["t_pub"]) in set(vd)]
    if bad:
        raise ValueError(f"{len(bad)} validation rows in a train-only job (first {bad[0]})")


# ------------------------------------------------------------------ rules (deterministic restrictions on a cached decision)
def option_list(P):
    """The registered menu as [(kind, value)] in a fixed order. A rule is {kind: value}; one value per kind."""
    out = []
    for kind, vals in P["menu"].items():
        for v in vals:
            out.append((kind, v))
    return out


def apply_rule(rule, row, dec, P, hold="1h"):
    """-> trade side (+1, -1, 0) of one item under `rule`. dec is the model's cached reply (ok, d, exp, conf, flow). rule {} = the frozen w3 behaviour."""
    if not dec or not dec.get("ok"):
        return 0
    theta = rule.get("theta_pct", P["base_theta_pct"])
    side = L.trade_side(R.effective(dec, {hold: theta}, True), hold, rule.get("min_conf", 0))
    if not side:
        return 0
    lab = (row.get("labels") or {}).get(R.LAB) or {}
    if "side_only" in rule and (rule["side_only"] == "long") != (side > 0):
        return 0
    if "gap_rule" in rule:
        pre = lab.get("pre_move")
        if pre is not None and abs(pre) >= P["greedy"]["gap_threshold"]:
            with_gap = (pre > 0) == (side > 0)
            if (rule["gap_rule"] == "no_fade" and not with_gap) or (rule["gap_rule"] == "no_chase" and with_gap):
                return 0
    if rule.get("session") == "outside_only" and lab.get("in_session"):
        return 0
    if "excl_code" in rule and rule["excl_code"] in (row.get("items") or []):
        return 0
    if "min_price" in rule and (lab.get("p_in") or 0) < rule["min_price"]:
        return 0
    fl = (dec.get("flow") or "none")
    if rule.get("flow") == "flow_only" and fl == "none":
        return 0
    if rule.get("flow") == "no_flow" and fl != "none":
        return 0
    return side


def records(rows, decs, rule, P, P2, hold="1h"):
    """One record per item with a 1 h gross and a valid reply: side, net at 1x and 2x, random-direction expectation on the traded items, gross."""
    out = []
    for r in rows:
        lab = (r.get("labels") or {}).get(R.LAB) or {}
        g = (lab.get("gross") or {}).get(hold)
        d = decs.get(r["key"])
        if g is None or not d or not d.get("ok"):
            continue
        s = apply_rule(rule, r, d, P, hold)
        out.append({"key": r["key"], "day": L.day_of(r["t_pub"]), "side": s, "gross": g, "row": r, "dec": d,
                    "a": L.net_pnl(s, g, "stock", P2), "a2": L.net_pnl(s, g, "stock", P2, 2.0),
                    "rnd": L.random_expectation(g, "stock", P2) if s else 0.0, "rnd2": L.random_expectation(g, "stock", P2, 2.0) if s else 0.0})
    return out


def arrays_of(recs):
    return {k: [x[k] for x in recs] for k in ("key", "day", "side", "gross", "a", "a2", "rnd", "rnd2")}


def summary(recs):
    """Headline numbers of one rule on one set (the H.vs_random block plus counts)."""
    arr = arrays_of(recs)
    v = H.vs_random(arr)
    tr = [x for x in recs if x["side"]]
    v["hit_rate"] = (sum(1 for x in tr if x["side"] * x["gross"] > 0) / len(tr)) if tr else None
    v["mean_dir_gross_per_trade"] = (sum(x["side"] * x["gross"] for x in tr) / len(tr)) if tr else None
    return v


def paired_vs(recs_c, recs_b):
    """Candidate minus baseline on the items both have, net per offered at 1x and 2x: analytic day-clustered one-sided t, exact sign test."""
    ib = {x["key"]: x for x in recs_b}
    pairs = [(x, ib[x["key"]]) for x in recs_c if x["key"] in ib]
    days = [c["day"] for c, _ in pairs]
    d1 = [c["a"] - b["a"] for c, b in pairs]
    d2 = [c["a2"] - b["a2"] for c, b in pairs]
    return {"n": len(pairs), "diff_1x": H.cluster_t(d1, days), "diff_2x": H.cluster_t(d2, days), "sign_1x": C.sign_test(d1),
            "discordant": sum(1 for c, b in pairs if c["side"] != b["side"])}


# ------------------------------------------------------------------ greedy rule fit on TRAIN only
def greedy_fit(train_rows, decs, P, P2):
    """Start from the frozen w3 rule {}; at each step add the single menu restriction with the largest paired gain (net per offered, day-clustered
    t >= greedy.min_paired_t, gain > 0, at least greedy.min_trades_train trades); stop when none qualifies or after greedy.max_steps.
    -> {rule, steps, evaluations, train}. `evaluations` counts every (step, option) scored: it is the train-side multiplicity."""
    g = P["greedy"]
    rule, steps, evals = {}, [], 0
    cur = records(train_rows, decs, rule, P, P2)
    opts = option_list(P)
    for _ in range(g["max_steps"]):
        best = None
        for kind, val in opts:
            if rule.get(kind) == val:
                continue
            cand = dict(rule, **{kind: val})
            rec = records(train_rows, decs, cand, P, P2)
            evals += 1
            if sum(1 for x in rec if x["side"]) < g["min_trades_train"]:
                continue
            d = paired_vs(rec, cur)["diff_1x"]
            if d["mean"] is None or d["t"] is None or d["mean"] <= 0 or d["t"] < g["min_paired_t"]:
                continue
            if best is None or d["mean"] > best[0]:
                best = (d["mean"], d["t"], kind, val, cand, rec)
        if not best:
            break
        _, t, kind, val, rule, cur = best
        steps.append({"add": [kind, val], "gain_per_offered": best[0], "t": t, "trades": sum(1 for x in cur if x["side"])})
    return {"rule": rule, "steps": steps, "evaluations": evals, "train": summary(cur)}


# ------------------------------------------------------------------ error analysis tables (TRAIN rows only)
def ny_bucket(ts):
    t = datetime.fromtimestamp(ts, R.NY)
    m = t.hour * 60 + t.minute
    if t.weekday() >= 5:
        return "weekend"
    return "pre_market" if m < 570 else ("session" if m < 960 else "after_close")


def _edges(x, edges, names):
    if x is None:
        return "n/a"
    for e, n in zip(edges, names):
        if x < e:
            return n
    return names[-1]


def dims(P):
    """{dimension: fn(rec) -> label or [labels]}; every input is known before the entry, except `month` / `weekday` of t_pub (also known)."""
    def lab(x):
        return (x["row"].get("labels") or {}).get(R.LAB) or {}

    def exp1h(x):
        return abs(((x["dec"].get("exp") or {}).get("1h")) or 0.0)

    def align(x):
        pre = lab(x).get("pre_move")
        s = x["side"] or (1 if ((x["dec"].get("exp") or {}).get("1h") or 0) > 0 else -1)
        if pre is None or abs(pre) < P["greedy"]["gap_threshold"]:
            return "small_gap"
        return "with_gap" if (pre > 0) == (s > 0) else "against_gap"

    return {
        "has_code": lambda x: [c for c in (x["row"].get("items") or []) if c in CODES] or ["none_listed"],
        "n_codes": lambda x: str(min(len(x["row"].get("items") or []), 5)),
        "side": lambda x: {1: "long", -1: "short", 0: "none"}[x["side"]],
        "abs_exp_1h": lambda x: _edges(exp1h(x), (0.25, 0.5, 1, 2, 4), ("<0.25", "0.25-0.5", "0.5-1", "1-2", "2-4", ">=4")),
        "conf": lambda x: _edges(x["dec"].get("conf"), (25, 40, 55, 70), ("<25", "25-39", "40-54", "55-69", ">=70")),
        "flow": lambda x: x["dec"].get("flow") or "none",
        "in_session": lambda x: str(bool(lab(x).get("in_session"))),
        "ny_time": lambda x: ny_bucket(x["row"]["t_pub"]),
        "pre_move": lambda x: _edges(lab(x).get("pre_move"), (-0.05, -0.02, -0.005, 0.005, 0.02, 0.05), ("<-5%", "-5..-2%", "-2..-0.5%", "+-0.5%", "0.5..2%", "2..5%", ">=5%")),
        "gap_align": align,
        "runup5": lambda x: _edges(lab(x).get("runup5"), (-0.05, 0.0, 0.05), ("<-5%", "-5..0%", "0..5%", ">=5%")),
        "rv": lambda x: _edges((x["row"].get("feat") or {}).get("rv"), (0.005, 0.01, 0.02), ("<0.5%", "0.5-1%", "1-2%", ">=2%")),
        "price": lambda x: _edges(lab(x).get("p_in"), (10, 20, 50), ("<10", "10-20", "20-50", ">=50")),
        "kw": lambda x: str(min(int((x["row"].get("feat") or {}).get("kw") or 0), 3)),
        "month": lambda x: L.day_of(x["row"]["t_pub"])[:7],
        "weekday": lambda x: str(datetime.strptime(L.day_of(x["row"]["t_pub"]), "%Y-%m-%d").weekday()),
        "text_len": lambda x: _edges(len(x["row"].get("text") or ""), (1500, 3000, 6000), ("<1.5k", "1.5-3k", "3-6k", ">=6k")),
        "delay": lambda x: _edges(lab(x).get("delay_s"), (900, 3600, 14400), ("<15m", "15-60m", "1-4h", ">=4h")),
    }


def group_table(recs, fn, min_n):
    """Per label: offered, traded, net per offered / per trade, random per offered, gap to random, hit rate, mean directional gross, total net, share of all losses."""
    groups = {}
    for x in recs:
        labs = fn(x)
        for lb in (labs if isinstance(labs, list) else [labs]):
            groups.setdefault(lb, []).append(x)
    total_loss = sum(-x["a"] for x in recs if x["a"] < 0) or 1.0
    out = {}
    for lb, xs in sorted(groups.items()):
        tr = [x for x in xs if x["side"]]
        if len(xs) < min_n and len(tr) < 5:
            continue
        out[lb] = {"offered": len(xs), "traded": len(tr),
                   "net_per_offered": sum(x["a"] for x in xs) / len(xs), "random_per_offered": sum(x["rnd"] for x in xs) / len(xs),
                   "net_per_trade": (sum(x["a"] for x in tr) / len(tr)) if tr else None,
                   "net_per_trade_2x": (sum(x["a2"] for x in tr) / len(tr)) if tr else None,
                   "hit_rate": (sum(1 for x in tr if x["side"] * x["gross"] > 0) / len(tr)) if tr else None,
                   "mean_dir_gross_per_trade": (sum(x["side"] * x["gross"] for x in tr) / len(tr)) if tr else None,
                   "total_net": sum(x["a"] for x in xs), "loss_share": sum(-x["a"] for x in xs if x["a"] < 0) / total_loss}
    return out


def theta_conf_sweep(rows, decs, P, P2):
    a = P["analysis"]
    out = []
    for th in a["theta_grid_pct"]:
        for mc in a["conf_grid"]:
            recs = records(rows, decs, {"theta_pct": th, "min_conf": mc}, P, P2)
            tr = [x for x in recs if x["side"]]
            n = len(recs) or 1
            out.append({"theta_pct": th, "min_conf": mc, "offered": len(recs), "traded": len(tr), "net_per_offered": sum(x["a"] for x in recs) / n,
                        "net_per_offered_2x": sum(x["a2"] for x in recs) / n, "random_per_offered": sum(x["rnd"] for x in recs) / n,
                        "net_per_trade": (sum(x["a"] for x in tr) / len(tr)) if tr else None})
    return out


def loss_concentration(recs):
    tr = sorted((x for x in recs if x["side"]), key=lambda x: x["a"])
    loss = sum(-x["a"] for x in tr if x["a"] < 0) or 1.0
    gain = sum(x["a"] for x in tr if x["a"] > 0) or 1.0
    k5 = max(1, len(tr) // 20)
    return {"traded": len(tr), "total_loss": sum(-x["a"] for x in tr if x["a"] < 0), "total_gain": sum(x["a"] for x in tr if x["a"] > 0),
            "worst_5pct_loss_share": sum(-x["a"] for x in tr[:k5] if x["a"] < 0) / loss, "best_5pct_gain_share": sum(x["a"] for x in tr[::-1][:k5] if x["a"] > 0) / gain,
            "worst_10": [{"key": x["key"], "net": x["a"], "side": x["side"], "gross": x["gross"], "items": x["row"].get("items"),
                          "exp_1h": (x["dec"].get("exp") or {}).get("1h")} for x in tr[:10]]}


def analysis(train_rows, decs, P, P2):
    """Everything the error analysis reports, TRAIN rows only: the frozen w3 behaviour (rule {}), the same tables for the direction of the
    analyst at theta 0 (every item with a direction and an agreeing sign: where does the direction carry anything), the theta x conf grid, loss concentration."""
    mn = P["analysis"]["min_group_n"]
    base = records(train_rows, decs, {}, P, P2)
    all_dir = records(train_rows, decs, {"theta_pct": 0}, P, P2)
    ds = dims(P)
    return {"n_train_rows": len(train_rows), "baseline_w3": summary(base),
            "baseline_all_directions_theta0": summary(all_dir),
            "tables_w3_trades": {k: group_table(base, f, mn) for k, f in ds.items()},
            "tables_all_directions": {k: group_table(all_dir, f, mn) for k, f in ds.items() if k in ("abs_exp_1h", "conf", "flow", "has_code", "gap_align", "in_session", "ny_time", "price", "rv", "side")},
            "theta_conf_sweep": theta_conf_sweep(train_rows, decs, P, P2), "loss_concentration": loss_concentration(base)}


# ------------------------------------------------------------------ validation (one shot) and routing
def evaluate(val_rows, decs_of, cands, P, P2):
    """cands: [{id, dec: 'w3'|'w4', rule}] frozen before this call. decs_of: {'w3': {key: dec}, 'w4': {key: dec}}. The baseline is w3 with rule {}.
    Items are the validation items that have every needed reply. -> {baseline, candidates: {id: {...}}, holm}."""
    keys = None
    for src in {"w3"} | {c["dec"] for c in cands}:
        ok = {k for k, d in decs_of[src].items() if d and d.get("ok")}
        keys = ok if keys is None else keys & ok
    rows = [r for r in val_rows if r["key"] in keys]
    base = records(rows, decs_of["w3"], {}, P, P2)
    res = {"n_items": len(base), "baseline_w3": summary(base), "candidates": {}}
    ps = {}
    for c in cands:
        rec = records(rows, decs_of[c["dec"]], c["rule"], P, P2)
        pv = paired_vs(rec, base)
        res["candidates"][c["id"]] = {"def": c, "summary": summary(rec), "paired_vs_w3": pv}
        ps[c["id"]] = pv["diff_2x"]["p"]
    res["holm_adjusted_p_diff_2x"] = H.holm(ps, P["validation"]["holm_m"]) if ps else {}
    return res


def route(res, P):
    """The registered routing rule. Not evidence of an edge: it only chooses what the forward arm scores. -> (id or None, reasons per candidate)."""
    ok, why = [], {}
    for cid, c in res["candidates"].items():
        s, pv = c["summary"], c["paired_vs_w3"]
        d1, d2 = pv["diff_1x"]["mean"], pv["diff_2x"]["mean"]
        checks = {"diff_1x_positive": d1 is not None and d1 > 0, "diff_2x_positive": d2 is not None and d2 > 0,
                  "net_per_trade_2x_positive": (s.get("mean_per_trade_2x") or 0) > 0, "trades_floor": (s.get("n_traded") or 0) >= P["validation"]["min_trades"]}
        why[cid] = checks
        if all(checks.values()):
            ok.append((d2, cid))
    return (max(ok)[1] if ok else None), why
