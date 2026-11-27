"""Historical holdout, Haiku 5.5 vs Sonnet 5.5 on non-S&P-500 8-Ks (protocol_hh_20261127.md): pure logic. No network, no clock, stdlib only.
Everything else (prompts, parsers, labels, costs, calibrated abstention, cell scorer, partial rank correlation, paired helpers) is reused from the
locked logic.py, logic_r2.py, logic_r3.py and logic_cmp.py. The one new piece of statistics is an ANALYTIC day-clustered test: the 2,000-draw
bootstraps of the older rounds bottom out at 5e-4 and return p = 0 when no draw is <= 0, which could never be read against alpha_k = 2.6e-5."""
import json
import math
import os

from research.news_train import logic as L
from research.news_train import logic_cmp as C
from research.news_train import logic_r2 as R

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_hh.json")


A1_PATH = os.path.join(HERE, "params_hh_a1.json")


def load_params(path=PARAMS_PATH, addenda=(A1_PATH,)):
    """params_hh.json (hash-locked in the protocol) with the dated addenda's `override` sections applied on top; the base file is never edited."""
    with open(path) as f:
        p = json.load(f)
    for a in addenda:
        if a and os.path.exists(a):
            with open(a) as f:
                for section, vals in json.load(f)["override"].items():
                    p[section].update(vals)
    return p


# ------------------------------------------------------------------ statistics
def _betacf(a, b, x):
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return h


def betainc(a, b, x):
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(ln) * _betacf(a, b, x) / a
    return 1.0 - math.exp(ln) * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """P(T > t) for Student's t with df degrees of freedom."""
    x = df / (df + t * t)
    half = 0.5 * betainc(df / 2.0, 0.5, x)
    return half if t > 0 else 1.0 - half


def cluster_t(values, days):
    """Mean of `values` with a day-clustered (ratio estimator) standard error and the one-sided analytic p of 'mean > 0' from Student's t with
    (days - 1) degrees of freedom. p is None, never 0 or 1 by default, when the statistic is undefined (fewer than 5 days or zero variance)."""
    n = len(values)
    by = {}
    for v, d in zip(values, days):
        s = by.setdefault(d, [0.0, 0])
        s[0] += v
        s[1] += 1
    k = len(by)
    out = {"n": n, "days": k, "mean": None, "se": None, "t": None, "df": k - 1, "p": None}
    if not n:
        return out
    mean = sum(s for s, _ in by.values()) / n
    out["mean"] = mean
    if k < 5:
        return out
    var = sum((s - mean * c) ** 2 for s, c in by.values()) * (k / (k - 1.0)) / (n * n)
    if var <= 0:
        return out
    se = math.sqrt(var)
    out.update(se=se, t=mean / se, p=t_sf(mean / se, k - 1))
    return out


def holm(ps, m_total):
    """Holm step-down on {name: p}; a missing p counts as 1."""
    return L.holm_adjust({k: (1.0 if v is None else v) for k, v in ps.items()}, m_total)


def meets_bar(p_adj, alpha):
    """A bar is met only by an analytic adjusted p that exists, is above 0 and is <= alpha. A bootstrap 'p = 0' never reaches here."""
    return p_adj is not None and 0.0 < p_adj <= alpha


# ------------------------------------------------------------------ decisions only (no label): the sample-size gate
def sides(decs, theta, hold, min_conf=0):
    """{key: trade side} of one model from its decisions and the frozen theta alone: reads no label, no outcome."""
    return {k: L.trade_side(R.effective(v, theta, True), hold, min_conf) for k, v in decs.items() if v and v.get("ok")}


def count_gate(dec_h, dec_s, theta, hold, P):
    """Counts that decide 'unread' before any outcome is read: items both models answered, trades per model, discordant pairs."""
    sh, ss = sides(dec_h, theta, hold), sides(dec_s, theta, hold)
    both = sorted(set(sh) & set(ss))
    disc = sum(1 for k in both if sh[k] != ss[k])
    n = P["n"]
    out = {"paired": len(both), "traded_haiku": sum(1 for k in both if sh[k]), "traded_sonnet": sum(1 for k in both if ss[k]), "discordant": disc}
    out["ok"] = {"paired": len(both) >= n["callable_floor"], "traded_haiku": out["traded_haiku"] >= n["min_traded"],
                 "traded_sonnet": out["traded_sonnet"] >= n["min_traded"], "discordant": disc >= n["min_discordant"]}
    return out


# ------------------------------------------------------------------ family arrays (labels needed)
def arrays(rows, decs, theta, hold, market, P2):
    """Per item with a label gross, a valid reply: day, side, net, random-direction expectation on the traded items (0 when abstaining), at 1x and 2x cost."""
    out = {"key": [], "day": [], "side": [], "a": [], "rnd": [], "a2": [], "rnd2": [], "gross": []}
    for r in rows:
        g = ((r.get("labels") or {}).get(R.LAB) or {}).get("gross", {}).get(hold)
        d = decs.get(r["key"])
        if g is None or not d or not d.get("ok"):
            continue
        s = L.trade_side(R.effective(d, theta, True), hold)
        out["key"].append(r["key"])
        out["day"].append(L.day_of(r["t_pub"]))
        out["side"].append(s)
        out["gross"].append(g)
        out["a"].append(L.net_pnl(s, g, market, P2))
        out["rnd"].append(L.random_expectation(g, market, P2) if s else 0.0)
        out["a2"].append(L.net_pnl(s, g, market, P2, 2.0))
        out["rnd2"].append(L.random_expectation(g, market, P2, 2.0) if s else 0.0)
    return out


def vs_random(arr):
    """H1 / H2 statistic: mean per offered item of (model net - random-direction net on the same trades), analytic day-clustered one-sided p."""
    d = [a - r for a, r in zip(arr["a"], arr["rnd"])]
    res = cluster_t(d, arr["day"])
    n_tr = sum(1 for s in arr["side"] if s)
    res["n_offered"], res["n_traded"] = len(arr["side"]), n_tr
    res["mean_per_trade"] = (sum(arr["a"]) / n_tr) if n_tr else None
    res["mean_per_trade_2x"] = (sum(arr["a2"]) / n_tr) if n_tr else None
    res["score_per_offered"] = (sum(arr["a"]) / len(arr["a"])) if arr["a"] else None
    d2 = [a - r for a, r in zip(arr["a2"], arr["rnd2"])]
    res["vs_random_2x"] = cluster_t(d2, arr["day"])
    return res


def paired(arr_h, arr_s):
    """H3 statistic: Sonnet minus Haiku net per offered item on the items both answered. Exact two-sided sign test on the non-zero differences is the
    registered p; the analytic day-clustered t is descriptive."""
    ih = {k: i for i, k in enumerate(arr_h["key"])}
    d, days, disc = [], [], 0
    for j, k in enumerate(arr_s["key"]):
        if k not in ih:
            continue
        i = ih[k]
        d.append(arr_s["a"][j] - arr_h["a"][i])
        days.append(arr_s["day"][j])
        disc += arr_s["side"][j] != arr_h["side"][i]
    res = {"sign": C.sign_test(d), "t_cluster": cluster_t(d, days), "n": len(d), "discordant": disc,
           "mean_diff": (sum(d) / len(d)) if d else None}
    return res


def family(h1, h2, h3, P):
    """Holm over the 3 registered tests (m = 3). p1, p2 one-sided analytic; p3 the exact two-sided sign test. Nomination bar alpha_k applies to H1 and H2 only."""
    ps = {"H1_haiku_vs_random": h1.get("p"), "H2_sonnet_vs_random": h2.get("p"), "H3_sonnet_minus_haiku": (h3.get("sign") or {}).get("p")}
    adj = holm(ps, len(P["family_tests"]))
    return {"p": ps, "holm_adjusted": adj, "m": len(P["family_tests"])}


def verdict(fam, h1, h2, h3, gate, P):
    """-> {'nomination': {...}, 'comparison': str}. Rule H: history only nominates; the words are 'nominated' / 'not nominated', never 'found'."""
    nom = {}
    for name, h in (("H1_haiku_vs_random", h1), ("H2_sonnet_vs_random", h2)):
        ok = (meets_bar(fam["holm_adjusted"][name], P["alpha_k"]) and (h.get("mean") or 0) > 0 and (h.get("mean_per_trade") or 0) > 0
              and (h.get("mean_per_trade_2x") or 0) > 0 and (h.get("n_traded") or 0) >= P["n"]["min_traded"])
        nom[name] = "nominated for a forward ledger" if ok else "not nominated"
    if not (gate["ok"]["paired"] and gate["ok"]["traded_haiku"] and gate["ok"]["traded_sonnet"]):
        cmp_ = "unread (below the registered counts)"
    elif not gate["ok"]["discordant"]:
        cmp_ = "underpowered (fewer than the registered discordant pairs)"
    else:
        adj = fam["holm_adjusted"]["H3_sonnet_minus_haiku"]
        md = h3.get("mean_diff") or 0
        cmp_ = "Sonnet better" if adj < P["alpha_within"] and md > 0 else ("Haiku better" if adj < P["alpha_within"] and md < 0 else "no difference detected")
    return {"nomination": nom, "comparison": cmp_}


# ------------------------------------------------------------------ universe and sample
def exchange_ok(exchange, P):
    return (exchange or "") in P["universe"]["exchanges"]


def window_ts(P):
    return L.day_ts(P["window"]["from"]), L.day_ts(P["window"]["to"])


def month_of(ts):
    return L.day_of(ts)[:7]


def candidate_ok(f, P, t_lo, t_hi):
    """f: a filing {form, ts (UTC, already fixed), doc, items}. Form 8-K only, in the window, a registered item code (an empty item list passes, as in round 2)."""
    u = P["universe"]
    if f["form"] != u["form"] or not f["doc"] or not (t_lo <= f["ts"] < t_hi):
        return False
    return (not f["items"]) or bool(set(f["items"]) & set(u["stock_items"]))


def sample_candidates(cands, P):
    """Deterministic, outcome-free: sha order inside each issuer, at most per_issuer_cap per issuer, then the first candidates_drawn by sha order overall."""
    u = P["universe"]
    seed = P["seed"]
    by = {}
    for c in cands:
        by.setdefault(c["cik"], []).append(c)
    kept = []
    for rows in by.values():
        kept += sorted(rows, key=lambda c: L.unit(f"{seed}:sec:{c['acc']}"))[:u["per_issuer_cap"]]
    return sorted(kept, key=lambda c: L.unit(f"{seed}:sec:{c['acc']}"))[:u["candidates_drawn"]]


def liquidity(bars, entry_ts, p_in, P):
    """From bars BEFORE entry only plus the entry price: price floor and mean dollar volume of the previous sessions. -> (ok, reason)."""
    c = P["liquidity"]
    if p_in < c["min_price"]:
        return False, "price_below_floor"
    sess = {}
    for b in bars:
        if b["t"] >= entry_ts:
            break
        sess.setdefault(R.ny_date(b["t"]), 0.0)
        sess[R.ny_date(b["t"])] += b["c"] * (b.get("v") or 0)
    days = sorted(sess)[-c["prior_sessions"]:]
    if len(days) < c["min_prior_sessions"]:
        return False, "too_few_prior_sessions"
    if sum(sess[d] for d in days) / len(days) < c["min_dollar_volume_day"]:
        return False, "dollar_volume_below_floor"
    return True, "ok"


def first_n_by_sha(keys, n, seed):
    """The registered prefix: the first n keys in sha order (a usage-limit stop leaves an unbiased prefix of the same order)."""
    return sorted(keys, key=lambda k: L.unit(f"{seed}:{k}"))[:n]
