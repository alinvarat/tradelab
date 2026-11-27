"""Sonnet 5.5 versus Haiku 5.5 on news analysis: pure logic (protocol_cmp_20261126.md). No network, no clock, stdlib only.
Everything else (prompts, parsers, labels, costs, calibrated abstention, the cell scorer, the partial rank correlation) is reused from the locked
logic.py, logic_r2.py and logic_r3.py."""
import json
import math
import os
import re
from statistics import median

from research.news_train import logic as L
from research.news_train import logic_r2 as R
from research.news_train import logic_r3 as T

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_cmp.json")


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


# ------------------------------------------------------------------ memory probe and the cutoff gate
def leak_cutoff(table, rule):
    """table: rows of run.py's leak.json ({asset, month 'YYYY-MM', answered, acc_answered}). A month is known when at least
    rule.min_answered of its questions were answered with accuracy >= rule.min_acc on either asset. -> last known month or None."""
    known = [r["month"] for r in table
             if r.get("answered", 0) >= rule["min_answered"] and (r.get("acc_answered") or 0) >= rule["min_acc"]]
    return max(known) if known else None


def first_eligible_day(cutoff_month):
    """First day of the month after the cutoff month ('YYYY-MM-DD'); None cutoff means no memory found: everything is eligible."""
    if not cutoff_month:
        return "1970-01-01"
    y, m = int(cutoff_month[:4]), int(cutoff_month[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}-01"


def eligible(t_pub, cutoff_month):
    return t_pub >= L.day_ts(first_eligible_day(cutoff_month))


def combined_cutoff(*cutoffs):
    """The later of the models' cutoffs: only items after both can be compared."""
    c = [x for x in cutoffs if x]
    return max(c) if c else None


# ------------------------------------------------------------------ paired statistics
def sign_test(diffs):
    """Exact two-sided sign test on the non-zero differences (ties are dropped and counted). -> {n_nonzero, pos, neg, ties, p}."""
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    n = pos + neg
    out = {"n_nonzero": n, "pos": pos, "neg": neg, "ties": len(diffs) - n}
    if n == 0:
        out["p"] = None
        return out
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    out["p"] = min(1.0, 2.0 * tail / float(2 ** n))
    return out


def two_sided(p_le_zero):
    """Two-sided p from the share of resampled statistics at or below zero."""
    return None if p_le_zero is None else min(1.0, 2.0 * min(p_le_zero, 1.0 - p_le_zero))


def paired_summary(diffs, days, n_boot, seed):
    """Mean paired difference (second model minus first), day-clustered bootstrap interval and two-sided p, plus the sign test."""
    b = L.cluster_bootstrap(diffs, days, n_boot, seed)
    return {"n": b["n"], "days": b.get("days"), "mean_diff": b["mean"], "lo": b["lo"], "hi": b["hi"], "p_boot_two_sided": two_sided(b["p"]),
            "sign": sign_test(diffs)}


def pair_direction(items, dec_a, dec_b, lab_a, lab_b, market, hold, theta, calib, P):
    """Paired net P&L of two models on the same items. items: {key: {day, ...}}; dec_x: {key: reply}; lab_x: {key: label with gross};
    theta: {hold: pct} frozen from the Haiku-fitted calibration; entry may differ by model (lab_a / lab_b are the models' own labels).
    -> [{key, day, side_a, side_b, a, b, d}] for items both models answered and both labels have a gross for the hold."""
    out = []
    for k in sorted(items):
        da, db = dec_a.get(k), dec_b.get(k)
        la, lb = lab_a.get(k), lab_b.get(k)
        if not da or not db or not da.get("ok") or not db.get("ok") or not la or not lb:
            continue
        ga, gb = (la.get("gross") or {}).get(hold), (lb.get("gross") or {}).get(hold)
        if ga is None or gb is None:
            continue
        sa = L.trade_side(R.effective(da, theta, calib), hold)
        sb = L.trade_side(R.effective(db, theta, calib), hold)
        a, b = L.net_pnl(sa, ga, market, P), L.net_pnl(sb, gb, market, P)
        out.append({"key": k, "day": items[k]["day"], "side_a": sa, "side_b": sb, "a": a, "b": b, "d": b - a})
    return out


def discordant(rows):
    """Pairs whose trade side differs (one trades and the other abstains, or opposite sides)."""
    return sum(1 for r in rows if r["side_a"] != r["side_b"])


def latency_stats(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    if not xs:
        return {"n": 0}
    return {"n": len(xs), "median_s": round(median(xs), 2), "p90_s": round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 2),
            "mean_s": round(sum(xs) / len(xs), 2)}


def paired_partial(rows_a, rows_b, n_boot, seed):
    """Magnitude: partial Spearman of the size estimate given realized volatility and the pre-entry move, model B minus model A, on the
    items both answered; day-clustered bootstrap (resamples days, recomputes both partials). rows_x are logic_r3.make_rows rows."""
    ib = {r["key"]: r for r in rows_b}
    merged = [{"key": r["key"], "day": r["day"], "y": r["y"], "rv": r["rv"], "pre": r["pre"], "ha": r["h"], "hb": ib[r["key"]]["h"]}
              for r in rows_a if r["key"] in ib]

    def part(rows, k):
        if len(rows) < 30:
            return None
        return T.partial_spearman([r[k] for r in rows], [r["y"] for r in rows], [[r["rv"] for r in rows], [r["pre"] for r in rows]])

    def stat(rows):
        a, b = part(rows, "ha"), part(rows, "hb")
        return None if a is None or b is None else b - a

    res = T.day_bootstrap(merged, stat, n_boot, seed)
    res["a"], res["b"] = part(merged, "ha"), part(merged, "hb")
    res["p_two_sided"] = two_sided(res.get("p"))
    return res


# ------------------------------------------------------------------ forward bookkeeping
def project(n_now, n_target, first_ts, now_ts):
    """Linear projection of when a count reaches its target, from the rate since the first item. Counts only. -> dict or None."""
    if not n_now or now_ts <= first_ts:
        return None
    rate = n_now / ((now_ts - first_ts) / 86400.0)
    if n_now >= n_target:
        return {"rate_per_day": round(rate, 2), "days_left": 0, "date": None}
    left = (n_target - n_now) / rate
    return {"rate_per_day": round(rate, 2), "days_left": round(left, 1), "date": L.day_of(now_ts + left * 86400)}


def fire_reason(paired, disc, now_ts, P):
    """Pre-registered trigger on counts: paired >= min_paired and discordant >= min_discordant, or the hard-stop date (underpowered)."""
    f = P["fwd"]
    if paired >= f["min_paired"] and disc >= f["min_discordant"]:
        return "min_n"
    if now_ts >= L.day_ts(f["hard_stop_utc"]):
        return "hard_stop_underpowered"
    return None


def crypto_pre_label(bars, t_seen, P2):
    """Pre-entry fields known at the item's t_seen (no outcome): move from availability to entry and over the hour before.
    Names match logic.crypto_label so render_user2 reads them unchanged. None when there is no entry price yet."""
    e = P2["entry"]
    te = t_seen + e["extra_s"]
    p_in = L.close_at(bars, te, e["stale_s"])
    if not p_in:
        return None
    p_pub = L.close_at(bars, t_seen, e["stale_s"])
    p_h = L.close_at(bars, t_seen - 3600, e["stale_s"])
    return {"entry_ts": te, "p_in": p_in, "pre_lag": (p_in / p_pub - 1.0) if p_pub else None, "pre_1h": (p_in / p_h - 1.0) if p_h else None,
            "gross": {}, "exit_ts": {}}


def crypto_own_label(bars, t_seen, llm_s, P2):
    """Label for one model's own entry: t_seen + that model's measured call time + the 5 s order delay (logic.crypto_label with lag = llm_s)."""
    return L.crypto_label(bars, t_seen, llm_s, P2)


def title_to_item(source, key, title, t_seen, coin, P2):
    """Forward crypto item from one ingest-log row: redacted title, the pod source as the source label."""
    return {"key": f"ing:{source}:{key}", "market": "crypto", "src": source, "t_pub": t_seen, "t_seen": t_seen, "sym": coin, "items": [],
            "text": redact_symbol(R.redact_title(title, coin, P2), coin), "text_named": title, "descr": "Instrument: a crypto token with a perpetual contract."}


JUNK_RX = (r"^\s*(rt\s+)?@\w+", r"https?://", r"\bt\.co/", r"^\s*\W*\s*$")


def is_junk(title):
    """Social and junk filter registered in protocol_cmp_addendum_20261126.md (written after reading title samples of the first ingest part,
    before any outcome): tweets that start with a handle or RT, any item with a link, and empty titles."""
    t = title or ""
    return any(re.search(rx, t, re.I) for rx in JUNK_RX)


# ------------------------------------------------------------------ widened forward crypto universe (protocol_cmp_addendum2_20261126.md)
NOT_COINS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USD", "EUR", "GBP", "KRW", "TRY", "BRL", "UTC", "ETF", "API", "FAQ", "VIP", "P2P", "KYC", "AMA",
             "UK", "US", "EU", "UAE", "ID", "TBA", "NFT", "DEFI", "CEO", "IPO", "SEC", "FED", "CPI", "PM", "AM"}
_SYM = r"[A-Z][A-Z0-9]{1,9}"
COIN_RX = (r"(?<![A-Za-z0-9])(" + _SYM + r")\s*/\s*USDT(?![A-Za-z0-9])", r"(?<![A-Za-z0-9])(" + _SYM + r")USDT(?![A-Za-z0-9])",
           r"\((" + _SYM + r")\)")


def coin_from_title(title):
    """Exactly one coin symbol named as XXXUSDT, XXX/USDT or (XXX) in an exchange or newswire title, else None (two different symbols are ambiguous).
    Whether a Binance or OKX market exists at t_seen is checked later, when the bars are fetched (no bars: the item is skipped)."""
    hits = set()
    for rx in COIN_RX:
        for m in re.finditer(rx, title or ""):
            sym = m.group(1)
            if sym not in NOT_COINS:
                hits.add(sym)
    return next(iter(hits)) if len(hits) == 1 else None


def redact_symbol(text, coin):
    """Also hide the symbol in its USDT forms (the locked redact_title only handles the bare symbol and the 20 names)."""
    t = re.sub(r"(?<![A-Za-z0-9])" + re.escape(coin) + r"\s*/?\s*USDT(?![A-Za-z0-9])", "[COIN]/USDT", text, flags=re.I)
    return re.sub(r"\(" + re.escape(coin) + r"\)", "([COIN])", t)
