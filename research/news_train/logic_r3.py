"""News-analyst training, round 3, Track A (magnitude): pure logic (protocol_r3_20261126.md). No network, no clock, stdlib only.
Imports round 1/2 logic read-only (labels, analog index, costs, Holm); nothing here touches round 2 files or its data."""
import bisect
import hashlib
import json
import math
import os
import random
import re

from research.news_train import logic as L
from research.news_train import logic_r2 as R

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_r3.json")
VERSIONS_PATH = os.path.join(HERE, "versions_r3.json")


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


def versions_registry(path=VERSIONS_PATH):
    with open(path) as f:
        return json.load(f)


def check_version(v, root=HERE):
    p = os.path.join(root, v["prompt"])
    if L.sha256_file(p) != v["sha256"]:
        raise ValueError(f"prompt of version {v['id']} does not match its registered sha256")
    return p


def assert_allowed(ts, P):
    """Round 3 never reads an item at or after refuse_from (the round-2 forward scorer owns that period)."""
    if ts >= L.day_ts(P["dates"]["refuse_from"]):
        raise L.SealError(f"t_pub {ts} is at or after refuse_from: not for round 3")


def assert_dev(ts, P):
    if ts >= L.day_ts(P["dates"]["dev_end"]):
        raise L.SealError(f"t_pub {ts} is at or after dev_end: sealed material, not for development")


# ------------------------------------------------------------------ rank statistics
def ranks(x):
    """Average ranks (1-based), ties share the mean rank."""
    n = len(x)
    order = sorted(range(n), key=lambda i: x[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        m = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = m
        i = j + 1
    return r


def pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((u - ma) ** 2 for u in a)
    sb = sum((v - mb) ** 2 for v in b)
    if sa <= 0 or sb <= 0:
        return None
    return sum((u - ma) * (v - mb) for u, v in zip(a, b)) / math.sqrt(sa * sb)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def residual(y, controls):
    """Residual of y after least squares on the control columns (with intercept)."""
    n = len(y)
    X = [[1.0] + [c[i] for c in controls] for i in range(n)]
    k = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    for a in range(k):
        A[a][a] += 1e-9
    bvec = [sum(X[i][a] * y[i] for i in range(n)) for a in range(k)]
    beta = _solve(A, bvec)
    if beta is None:
        return None
    return [y[i] - sum(beta[a] * X[i][a] for a in range(k)) for i in range(n)]


def partial_spearman(x, y, controls):
    """Spearman partial correlation of x and y given the control variables (rank-transformed, linear residuals)."""
    rc = [ranks(c) for c in controls]
    rx, ry = residual(ranks(x), rc), residual(ranks(y), rc)
    if rx is None or ry is None:
        return None
    return pearson(rx, ry)


def auc(score, label):
    """P(score of a positive > score of a negative), ties 0.5. None without both classes."""
    pos = sum(1 for v in label if v)
    neg = len(label) - pos
    if not pos or not neg:
        return None
    r = ranks(score)
    return (sum(r[i] for i in range(len(label)) if label[i]) - pos * (pos + 1) / 2.0) / (pos * neg)


def day_bootstrap(rows, stat, n, seed):
    """Resample whole UTC days of `rows` (each has 'day'); stat(rows) -> float or None. Point value, 95% interval and the one-sided
    p (share of resampled stats <= 0; None draws are skipped)."""
    pt = stat(rows)
    by = {}
    for r in rows:
        by.setdefault(r["day"], []).append(r)
    days = sorted(by)
    if pt is None or len(days) < 5:
        return {"n": len(rows), "days": len(days), "point": pt, "lo": None, "hi": None, "p": None}
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        s = []
        for _i in range(len(days)):
            s += by[days[rng.randrange(len(days))]]
        v = stat(s)
        if v is not None:
            vals.append(v)
    vals.sort()
    if not vals:
        return {"n": len(rows), "days": len(days), "point": pt, "lo": None, "hi": None, "p": None}
    m = len(vals)
    return {"n": len(rows), "days": len(days), "point": pt, "lo": vals[int(0.025 * m)], "hi": vals[min(m - 1, int(0.975 * m))],
            "p": sum(1 for v in vals if v <= 0) / float(m)}


# ------------------------------------------------------------------ features known at entry
def crypto_rv(bars, entry_ts, hours, min_minutes):
    """Root-mean-square 1-hour move scale from 1-minute closes of the `hours` before entry: sqrt(sum of squared 1-minute log returns / hours).
    bars: [(open_ts, high, low, close)] ascending. Only bars that ended at or before entry are used."""
    opens = [b[0] for b in bars]
    hi = bisect.bisect_right(opens, entry_ts - 60)
    lo = bisect.bisect_left(opens, entry_ts - hours * 3600)
    seg = bars[lo:hi]
    if len(seg) < min_minutes:
        return None
    s = 0.0
    for a, b in zip(seg, seg[1:]):
        if b[0] - a[0] > 120 or a[3] <= 0 or b[3] <= 0:
            continue
        s += math.log(b[3] / a[3]) ** 2
    return math.sqrt(s / hours)


def stock_rv(bars, entry_ts, nbars, min_bars):
    """Root-mean-square open-to-close return of the last `nbars` 1-hour bars that started before the entry bar. Bars: [{t,o,h,l,c}]."""
    ts = [b["t"] for b in bars]
    i = bisect.bisect_left(ts, entry_ts)            # first bar at or after entry; earlier bars are known
    seg = bars[max(0, i - nbars):i]
    if len(seg) < min_bars:
        return None
    return math.sqrt(sum(math.log(b["c"] / b["o"]) ** 2 for b in seg if b["o"] > 0 and b["c"] > 0) / len(seg))


def kw_score(text, P2):
    """Keyword baseline for MAGNITUDE: number of listed positive or negative keywords present (round-2 list, direction ignored)."""
    t = (text or "").lower()
    return sum(1 for w in P2["keyword"]["pos"] + P2["keyword"]["neg"] if re.search(r"\b" + re.escape(w) + r"\b", t))


def features(item, lab, rv, P2):
    """All baseline inputs of one item, each known at entry. pre = |move before entry| (stock: opening gap or move since the start of
    the hour; crypto: the hour before entry)."""
    mk = item["market"]
    pre = lab.get("pre_move") if mk == "stock" else lab.get("pre_1h")
    return {"rv": rv, "pre": abs(pre) if pre is not None else None, "kw": kw_score(item.get("text"), P2), "pre_signed": pre}


def target(lab, hold):
    g = (lab.get("gross") or {}).get(hold)
    return None if g is None else abs(g)


def big_threshold(market, P):
    return P["big_mult"] * P["cost_round_trip"][market]


# ------------------------------------------------------------------ replies
def parse_reply3(text):
    """-> {ok, abs1h (fraction, >= 0), p_big (0..1 or None), why}."""
    if not text:
        return {"ok": False}
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"ok": False}
    try:
        o = json.loads(m.group(0))
        a = float(o.get("abs1h"))
    except Exception:  # noqa: BLE001
        return {"ok": False}
    if not math.isfinite(a) or a < 0:
        return {"ok": False}
    try:
        p = float(o.get("p_big"))
        p = max(0.0, min(100.0, p)) / 100.0 if math.isfinite(p) else None
    except (TypeError, ValueError):
        p = None
    return {"ok": True, "abs1h": a / 100.0, "p_big": p, "why": str(o.get("why", ""))[:300]}


# ------------------------------------------------------------------ prompt
def render_user3(item, lab, feat, version, analogs=None, P=None):
    P = P or load_params()
    mk = item["market"]
    thr = 100 * big_threshold(mk, P)
    lines = [f"Item type: {'SEC 8-K filing or press release exhibit' if mk == 'stock' else 'crypto news headline'}. "
             f"Instrument market: {'US stock' if mk == 'stock' else 'crypto perpetual'}."]
    if item.get("items"):
        lines.append("8-K items: " + ", ".join(item["items"]))
    if mk == "crypto":
        lines.append(f"Source: {item.get('src') or 'news'}.")
    if version.get("uses_ctx"):
        lines.append(R.pre_block2(item, lab))
        lines.append(f"Typical size of this instrument's 1-hour moves in the preceding days (root-mean-square): "
                     f"{100 * feat['rv']:.2f}%." if feat.get("rv") is not None else "Typical hourly move: unknown.")
    lines.append(item.get("descr") or "")
    lines.append("Text:\n" + (item.get("text") or "")[:P["text_chars"]])
    if analogs:
        lines.append("Similar past items and the absolute 1-hour move that followed entry:")
        for k, d in enumerate(analogs, 1):
            it, lb = d["item"], d["lab"]
            g = (lb.get("gross") or {}).get(P["hold"])
            fr = (it.get("feat") or {}).get("rv")
            lines.append(f"{k}. {(it.get('text') or '')[:P['analogs']['text_chars']].strip()} | typical hourly move then "
                         f"{'n/a' if fr is None else f'{100 * fr:.2f}%'} | absolute move {'n/a' if g is None else f'{100 * abs(g):.2f}%'}")
    lines.append(f"Threshold for p_big: an absolute 1-hour move above {thr:.2f}%.")
    lines.append('Answer with one JSON object only: {"abs1h": ..., "p_big": ..., "why": "..."}.')
    return "\n".join(lines)


# ------------------------------------------------------------------ scoring
def make_rows(items, decs, P):
    """Scoring rows of one market's items: those with a label, a target, rv, pre and a valid reply."""
    out, excl = [], {"no_label": 0, "no_target": 0, "no_feat": 0, "no_reply": 0}
    for it in items:
        lab = (it.get("labels") or {}).get(R.LAB)
        if not lab:
            excl["no_label"] += 1
            continue
        y = target(lab, P["hold"])
        if y is None:
            excl["no_target"] += 1
            continue
        f = it.get("feat") or {}
        if f.get("rv") is None or f.get("pre") is None:
            excl["no_feat"] += 1
            continue
        d = decs.get(it["key"])
        if not d or not d.get("ok"):
            excl["no_reply"] += 1
            continue
        out.append({"key": it["key"], "day": L.day_of(it["t_pub"]), "y": y, "big": 1 if y > big_threshold(it["market"], P) else 0,
                    "h": d["abs1h"], "hp": d["p_big"] if d.get("p_big") is not None else 0.0, "rv": f["rv"], "pre": f["pre"], "kw": float(f["kw"]),
                    "earn": 1.0 if "2.02" in (it.get("items") or []) else 0.0})
    return out, excl


def rho(rows, k):
    return spearman([r[k] for r in rows], [r["y"] for r in rows]) if len(rows) >= 10 else None


def partial_h(rows):
    if len(rows) < 30:
        return None
    return partial_spearman([r["h"] for r in rows], [r["y"] for r in rows], [[r["rv"] for r in rows], [r["pre"] for r in rows]])


def diff_stat(a, b):
    def f(rows):
        x, y = rho(rows, a), rho(rows, b)
        return None if x is None or y is None else x - y
    return f


def point_stats(rows):
    """Descriptive and gating point estimates of one market and set."""
    if len(rows) < 30:
        return {"n": len(rows)}
    y = [r["y"] for r in rows]
    big = [r["big"] for r in rows]
    out = {"n": len(rows), "big_rate": sum(big) / len(big), "mean_abs": sum(y) / len(y)}
    for k in ("h", "hp", "rv", "pre", "kw"):
        out["rho_" + k] = rho(rows, k)
        out["auc_" + k] = auc([r[k] for r in rows], big)
    out["partial_h_given_rv_pre"] = partial_h(rows)
    if len({r["earn"] for r in rows}) > 1:                # descriptive (addendum 2026-11-26 a): also control for an 8-K item 2.02 (results) flag
        out["partial_h_given_rv_pre_earn"] = partial_spearman([r["h"] for r in rows], y, [[r["rv"] for r in rows], [r["pre"] for r in rows], [r["earn"] for r in rows]])
        out["share_earn"] = sum(r["earn"] for r in rows) / len(rows)
    out["partial_rv_given_h"] = partial_spearman([r["rv"] for r in rows], y, [[r["h"] for r in rows]])
    # filter view (descriptive): the top third by the analyst's size estimate versus the rest
    cut = sorted(r["h"] for r in rows)[int(len(rows) * 2 / 3)]
    top = [r for r in rows if r["h"] >= cut]
    rest = [r for r in rows if r["h"] < cut]
    if top and rest:
        out["top_third"] = {"n": len(top), "mean_abs": sum(r["y"] for r in top) / len(top), "big_rate": sum(r["big"] for r in top) / len(top),
                            "rest_mean_abs": sum(r["y"] for r in rest) / len(rest), "rest_big_rate": sum(r["big"] for r in rest) / len(rest)}
    return out


def gate_tests(rows, n_boot, seed):
    """The three registered tests (one-sided, day-clustered): T1 partial rho of the analyst's size given realized vol and the pre-entry
    move > 0; T2 rho(analyst) - rho(keyword) > 0; T3 rho(analyst) - rho(pre-entry move) > 0."""
    return {"T1_partial": day_bootstrap(rows, partial_h, n_boot, seed),
            "T2_vs_keyword": day_bootstrap(rows, diff_stat("h", "kw"), n_boot, seed + 1),
            "T3_vs_pre": day_bootstrap(rows, diff_stat("h", "pre"), n_boot, seed + 2)}


def select_lock(valid, P):
    """valid: {version: {market: {'n','reply_ok','partial'}}} -> {market: version or None}. Eligible: n >= select.min_valid_n, reply_ok >= min_reply_ok
    and partial >= min_partial_rho; then the highest partial; tie -> lower version number."""
    s = P["select"]
    lock = {}
    for mk in ("stock", "crypto"):
        best = None
        for vid in sorted(valid, key=lambda v: int(v[1:])):
            c = (valid[vid] or {}).get(mk) or {}
            if c.get("partial") is None or c.get("n", 0) < s["min_valid_n"] or c.get("reply_ok", 0) < s["min_reply_ok"] or c["partial"] < s["min_partial_rho"]:
                continue
            if best is None or c["partial"] > best[1]:
                best = (vid, c["partial"])
        lock[mk] = best[0] if best else None
    return lock


def verdict(tests, n, K, P, n_markets=2):
    """Done condition for one market of the sealed set: n >= done.min_n, all three tests Holm-adjusted p < alpha (family m = 3 x K x markets)
    with positive point estimates."""
    m_total = P["tests_per_version"] * K * n_markets
    ps = {k: (v["p"] if v.get("p") is not None else 1.0) for k, v in tests.items()}
    adj = L.holm_adjust(ps, m_total)
    ok = {k: adj[k] < P["bootstrap"]["alpha"] and (tests[k].get("point") or 0) > 0 for k in tests}
    if n < P["done"]["min_n"]:
        return {"holm_adjusted": adj, "m_total": m_total, "verdict": "unread (fewer than min_n)", "checks": ok}
    return {"holm_adjusted": adj, "m_total": m_total, "verdict": "done condition met" if all(ok.values()) else "not met", "checks": ok}
