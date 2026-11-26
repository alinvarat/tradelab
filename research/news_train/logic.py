"""News-analyst training loop: pure logic (protocol.md). No network, no clock, stdlib only.

Splits and the seal, achievable-entry labels, net P&L, baselines, paired day-clustered bootstrap, Holm, analog retrieval
with a strict "outcome closed before" rule, prompt rendering and reply parsing."""
import bisect
import hashlib
import json
import math
import os
import random
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params.json")
VERSIONS_PATH = os.path.join(HERE, "versions.json")
HOLDS = ("5m", "1h", "1d")


class SealError(Exception):
    """Raised whenever dev code would touch an item or label at or after the end of the dev period."""


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


def day_ts(day):
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def unit(s):
    """Deterministic float in [0, 1) from a string."""
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16) / float(16 ** 12)


# ------------------------------------------------------------------ splits and the seal
def split_of(ts, P):
    d = P["dates"]
    if ts < day_ts(d["dev_start"]):
        return None
    if ts < day_ts(d["train_end"]):
        return "train"
    if ts < day_ts(d["dev_end"]):
        return "validation"
    if ts < day_ts(d["sealed_from"]):
        return "buffer"
    if day_ts(d["burn_from"]) <= ts < day_ts(d["burn_to"]):
        return "burned"
    return "sealed"


def assert_dev(ts, P):
    """The dev loader's guard: anything at or after dev_end is refused."""
    if ts >= day_ts(P["dates"]["dev_end"]):
        raise SealError(f"t_pub {ts} is at or after dev_end {P['dates']['dev_end']}: sealed data is not for development")


def check_dev_rows(rows, P, key="t_pub"):
    for r in rows:
        assert_dev(r[key], P)
    return rows


# ------------------------------------------------------------------ costs and P&L
def net_pnl(side, gross, market, P, mult=1.0, sessions=1):
    """Net return of one trade: side +1 long, -1 short, 0 abstain; gross = long-side return of the hold."""
    if side == 0 or gross is None:
        return 0.0
    c = P["cost"]
    per_side = (c["stock_side"] if market == "stock" else c["crypto_rt"] / 2.0) * mult
    net = (1.0 + side * gross) * (1.0 - per_side) ** 2 - 1.0
    if market == "stock" and side < 0:
        net -= c["stock_short_borrow_session"] * mult * sessions
    return net


def random_expectation(gross, market, P, mult=1.0):
    """Exact expectation of a random direction: the mean of the long and the short net P&L."""
    return 0.5 * (net_pnl(1, gross, market, P, mult) + net_pnl(-1, gross, market, P, mult))


# ------------------------------------------------------------------ achievable-entry labels
def close_at(bars, t, stale_s):
    """bars: [(open_ts, high, low, close)] ascending, 1-minute. Close of the last bar that ended at or before t, or None if
    there is none or it ended more than stale_s before t."""
    opens = [b[0] for b in bars]
    i = bisect.bisect_right(opens, t - 60) - 1
    if i < 0:
        return None
    if t - (opens[i] + 60) > stale_s:
        return None
    return bars[i][3]


def crypto_label(bars, t_pub, lag, P):
    """Label of one crypto item at one lag: entry price, pre-entry moves, gross long return per hold."""
    e = P["entry"]
    te = t_pub + lag + e["extra_s"]
    p_in = close_at(bars, te, e["stale_s"])
    if not p_in:
        return None
    out = {"entry_ts": te, "p_in": p_in, "gross": {}, "exit_ts": {}}
    p_pub = close_at(bars, t_pub, e["stale_s"])
    p_h = close_at(bars, t_pub - 3600, e["stale_s"])
    out["pre_lag"] = (p_in / p_pub - 1.0) if p_pub else None
    out["pre_1h"] = (p_in / p_h - 1.0) if p_h else None
    for name, secs in P["holds"].items():
        p_out = close_at(bars, te + secs, e["stale_s"])
        out["gross"][name] = (p_out / p_in - 1.0) if p_out else None
        out["exit_ts"][name] = te + secs
    if all(v is None for v in out["gross"].values()):
        return None
    return out


def stock_label(bars, t_pub, lag, P):
    """bars: [{"t": session open ts, o, h, l, c}] daily, ascending. -> (label or None, reason)."""
    e = P["entry"]
    te = t_pub + lag + e["extra_s"]
    sess = e["session_s"]
    idx = None
    for k, b in enumerate(bars):
        if b["t"] <= te < b["t"] + sess:
            return None, "intraday_no_bars"
        if idx is None and b["t"] > te:
            idx = k
            break
    if idx is None:
        return None, "no_entry_session"
    if bars[idx]["t"] - te > 5 * 86400:
        return None, "gap_in_bars"
    if idx < 1:
        return None, "no_prior_bar"
    b, prev = bars[idx], bars[idx - 1]
    lab = {"entry_ts": b["t"], "p_in": b["o"], "gross": {"1d": b["c"] / b["o"] - 1.0}, "exit_ts": {"1d": b["t"] + sess},
           "gap": b["o"] / prev["c"] - 1.0, "runup5": (prev["c"] / bars[idx - 6]["c"] - 1.0) if idx >= 6 else None}
    return lab, "ok"


def available_holds(market):
    return ("1d",) if market == "stock" else HOLDS


# ------------------------------------------------------------------ keyword baseline
def keyword_side(text, P):
    t = (text or "").lower()
    pos = sum(1 for w in P["keyword"]["pos"] if re.search(r"\b" + re.escape(w) + r"\b", t))
    neg = sum(1 for w in P["keyword"]["neg"] if re.search(r"\b" + re.escape(w) + r"\b", t))
    return 1 if pos > neg else (-1 if neg > pos else 0)


# ------------------------------------------------------------------ statistics
def day_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def cluster_bootstrap(values, days, n, seed):
    """Mean of `values`, 95% interval and the one-sided p (share of resampled means <= 0), resampling whole UTC days."""
    if not values:
        return {"n": 0, "mean": None, "lo": None, "hi": None, "p": None}
    by = {}
    for v, d in zip(values, days):
        s = by.setdefault(d, [0.0, 0])
        s[0] += v
        s[1] += 1
    tot = list(by.values())
    k = len(tot)
    mean = sum(s for s, _ in tot) / sum(c for _, c in tot)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        ss = cs = 0
        for _i in range(k):
            s, c = tot[rng.randrange(k)]
            ss += s
            cs += c
        means.append(ss / cs)
    means.sort()
    p = sum(1 for m in means if m <= 0) / float(n)
    return {"n": len(values), "days": k, "mean": mean, "lo": means[int(0.025 * n)], "hi": means[min(n - 1, int(0.975 * n))], "p": p}


def holm_adjust(pvals, m_total):
    """Holm step-down adjusted p-values for the tested hypotheses, with m_total hypotheses in the family and the untested
    ones counted as p = 1 (they sort last). pvals: {name: p}."""
    order = sorted(pvals, key=lambda k: pvals[k])
    out, run = {}, 0.0
    for rank, name in enumerate(order):
        adj = min(1.0, (m_total - rank) * pvals[name])
        run = max(run, adj)
        out[name] = run
    return out


# ------------------------------------------------------------------ scoring one version on one set
def trade_side(dec, hold, min_conf=0):
    if not dec or not dec.get("ok"):
        return 0
    if (dec.get("conf") or 0) < min_conf:
        return 0
    return {"long": 1, "short": -1}.get((dec.get("d") or {}).get(hold), 0)


def score_cell(rows, decisions, market, hold, P, lag="93"):
    """rows: items with labels ({"key","t_pub","market","text","labels":{lag: label}}); decisions: {key: {"ok","d","conf"}}.
    -> metrics for one market and hold. Items without a label, a gross for this hold, or a valid reply are excluded and counted."""
    cfg = P["bootstrap"]
    arrays = {k: [] for k in ("days", "a", "a2", "rnd", "rnd2", "kw", "kw2", "long_all", "long_tr", "short_tr")}
    excl = {"no_label": 0, "no_gross": 0, "no_reply": 0}
    traded = hits = 0
    for r in rows:
        if r["market"] != market:
            continue
        lab = (r.get("labels") or {}).get(lag)
        if not lab:
            excl["no_label"] += 1
            continue
        g = lab["gross"].get(hold)
        if g is None:
            excl["no_gross"] += 1
            continue
        dec = decisions.get(r["key"])
        if not dec or not dec.get("ok"):
            excl["no_reply"] += 1
            continue
        side = trade_side(dec, hold, P["min_conf"])
        ks = keyword_side(r.get("text") or "", P)
        a = arrays
        a["days"].append(day_of(r["t_pub"]))
        a["a"].append(net_pnl(side, g, market, P))
        a["a2"].append(net_pnl(side, g, market, P, 2.0))
        a["rnd"].append(random_expectation(g, market, P) if side else 0.0)
        a["rnd2"].append(random_expectation(g, market, P, 2.0) if side else 0.0)
        a["kw"].append(net_pnl(ks, g, market, P))
        a["kw2"].append(net_pnl(ks, g, market, P, 2.0))
        a["long_all"].append(net_pnl(1, g, market, P))
        a["long_tr"].append(net_pnl(1, g, market, P) if side else 0.0)
        a["short_tr"].append(net_pnl(-1, g, market, P) if side else 0.0)
        if side:
            traded += 1
            hits += (side * g) > 0
    n = len(arrays["days"])
    out = {"market": market, "hold": hold, "lag": lag, "n_offered": n, "n_traded": traded, "excluded": excl,
           "hit_rate": (hits / traded) if traded else None}
    if not n:
        return out
    d = arrays["days"]
    seed = P["seed"]
    nb = cfg["n"]

    def diff(x, y):
        return [u - v for u, v in zip(arrays[x], arrays[y])]

    out["score_per_offered"] = sum(arrays["a"]) / n
    out["mean_per_trade"] = (sum(arrays["a"]) / traded) if traded else None
    out["mean_per_trade_2x"] = (sum(arrays["a2"]) / traded) if traded else None
    out["vs_abstain"] = cluster_bootstrap(arrays["a"], d, nb, seed)
    out["vs_random"] = cluster_bootstrap(diff("a", "rnd"), d, nb, seed + 1)
    out["vs_keyword"] = cluster_bootstrap(diff("a", "kw"), d, nb, seed + 2)
    out["vs_random_2x"] = cluster_bootstrap(diff("a2", "rnd2"), d, nb, seed + 3)
    out["baselines"] = {"abstain": 0.0, "random_per_offered": sum(arrays["rnd"]) / n, "keyword_per_offered": sum(arrays["kw"]) / n,
                        "keyword_traded": sum(1 for r in rows if r["market"] == market and keyword_side(r.get("text") or "", P)),
                        "long_all_per_offered": sum(arrays["long_all"]) / n,
                        "long_on_traded_per_offered": sum(arrays["long_tr"]) / n,
                        "short_on_traded_per_offered": sum(arrays["short_tr"]) / n}
    return out


def versions_registry(path=VERSIONS_PATH):
    with open(path) as f:
        return json.load(f)


def check_version(v, root=HERE):
    """A version may be called only when its prompt file matches the registered sha256."""
    path = os.path.join(root, v["prompt"])
    if sha256_file(path) != v["sha256"]:
        raise ValueError(f"prompt of version {v['id']} does not match its registered sha256")
    return path


# ------------------------------------------------------------------ redaction
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE_PATTERNS = [(re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[DATE]"),
                  (re.compile(r"\b(?:%s)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b" % _MONTHS, re.I), "[DATE]"),
                  (re.compile(r"\b\d{1,2}\s+(?:%s)\s+\d{4}\b" % _MONTHS, re.I), "[DATE]"),
                  (re.compile(r"\b(?:%s)\s+\d{4}\b" % _MONTHS, re.I), "[DATE]"),
                  (re.compile(r"\b(?:19|20)\d{2}\b"), "[YEAR]")]


def scrub_dates(text):
    for rx, rep in _DATE_PATTERNS:
        text = rx.sub(rep, text)
    return text


def redact_coin(title, symbol):
    """Crypto notice title: the symbol and the 'Name (SYM)' pattern become [COIN]; dates are scrubbed."""
    s = title or ""
    if symbol:
        s = re.sub(r"[\w .'\-]{1,40}\(\s*" + re.escape(symbol) + r"\s*\)", "[COIN]", s)
        s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(symbol) + r"(?![A-Za-z0-9])", "[COIN]", s)
    return scrub_dates(s)


# ------------------------------------------------------------------ analog retrieval
_STOP = set("the and for with that this from will has have are was were its their into per not all new inc corp company".split())


def tokens(item):
    text = (item.get("text") or "").lower()
    words = [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", text) if w not in _STOP][:120]
    toks = set(words)
    toks.update("item:" + x for x in item.get("items") or [])
    if item.get("cls"):
        toks.add("cls:" + item["cls"])
    toks.add("src:" + str(item.get("src") or item.get("market")))
    return toks


def closed_ts(item, lab):
    """When the longest hold of this item's outcome is known (its exit time)."""
    ex = (lab or {}).get("exit_ts") or {}
    return max(ex.values()) if ex else None


class AnalogIndex:
    """Pool of (item, label) pairs for retrieval. query() returns the k most similar pool items of the same market whose
    outcome was CLOSED strictly before `before_ts` (the scored item's t_pub); the scored item itself is never returned."""

    def __init__(self, pool, lag="93"):
        self.lag = lag
        self.docs = []
        df = {}
        for it in pool:
            lab = (it.get("labels") or {}).get(lag)
            ct = closed_ts(it, lab)
            if not lab or ct is None:
                continue
            tk = tokens(it)
            self.docs.append({"item": it, "lab": lab, "closed": ct, "tok": tk})
            for t in tk:
                df[t] = df.get(t, 0) + 1
        n = max(1, len(self.docs))
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}
        for d in self.docs:
            d["norm"] = math.sqrt(sum(self.idf[t] ** 2 for t in d["tok"])) or 1.0
        self.inv = {}
        for i, d in enumerate(self.docs):
            for t in d["tok"]:
                self.inv.setdefault(t, []).append(i)

    def query(self, item, before_ts, k):
        tk = tokens(item)
        qn = math.sqrt(sum(self.idf.get(t, 0.0) ** 2 for t in tk)) or 1.0
        sc = {}
        for t in tk:
            w = self.idf.get(t)
            if not w:
                continue
            for i in self.inv.get(t, ()):
                sc[i] = sc.get(i, 0.0) + w * w
        out = []
        for i, s in sc.items():
            d = self.docs[i]
            if d["closed"] >= before_ts or d["item"]["key"] == item["key"] or d["item"]["market"] != item["market"]:
                continue
            out.append((s / (qn * d["norm"]), d["item"]["key"], d))
        out.sort(key=lambda x: (-x[0], x[1]))
        return [d for _, _, d in out[:k]]


# ------------------------------------------------------------------ prompt rendering and reply parsing
def pct(x):
    return "n/a" if x is None else f"{100 * x:+.2f}%"


def pre_block(item, lab):
    if item["market"] == "stock":
        return (f"Already priced before your entry: opening gap versus the previous close {pct(lab.get('gap'))}; "
                f"previous 5-session run-up {pct(lab.get('runup5'))}.")
    return (f"Already priced before your entry: move from publication to entry {pct(lab.get('pre_lag'))}; "
            f"move over the hour before publication {pct(lab.get('pre_1h'))}.")


def outcome_block(item, lab):
    holds = available_holds(item["market"])
    return ", ".join(f"{h} {pct((lab.get('gross') or {}).get(h))}" for h in holds)


def render_user(item, lab, version, analogs=None, P=None):
    """User message for one item. `lab` is the label at the primary lag; only its pre-entry fields are shown, never gross."""
    P = P or load_params()
    holds = available_holds(item["market"])
    lines = []
    kind = "SEC 8-K filing" if item["market"] == "stock" else "exchange notice"
    lines.append(f"Item type: {kind}. Instrument market: {'US stock' if item['market'] == 'stock' else 'crypto perpetual'}.")
    if item.get("items"):
        lines.append("8-K items: " + ", ".join(item["items"]))
    if item.get("src") and item["market"] == "crypto":
        lines.append(f"Source: {item['src']}.")
    if version.get("uses_pre") and lab:
        lines.append(pre_block(item, lab))
    lines.append("Text:\n" + (item.get("text") or "")[:P["text_chars"]])
    if analogs:
        lines.append("Similar past items and what happened after entry (net of nothing, long-side moves):")
        for k, d in enumerate(analogs, 1):
            it, lb = d["item"], d["lab"]
            pre = pre_block(it, lb) if version.get("uses_pre") else ""
            lines.append(f"{k}. {(it.get('text') or '')[:P['analogs']['text_chars']].strip()} | {pre} | outcome: {outcome_block(it, lb)}")
    lines.append("Answer with one JSON object only: {" + ", ".join(f'"{h}": "long|short|none"' for h in holds) +
                 ', "conf": 0-100, "why": "one short sentence"}. Use "none" when you have no edge; abstaining is a normal answer.')
    return "\n".join(lines)


def parse_reply(text, market):
    """-> {"ok": bool, "d": {hold: long|short|none}, "conf": int, "why": str}. ok is False for an empty or unusable reply."""
    if not text:
        return {"ok": False}
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"ok": False}
    try:
        o = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {"ok": False}
    if not isinstance(o, dict):
        return {"ok": False}
    d = {}
    for h in available_holds(market):
        v = str(o.get(h, "")).strip().lower()
        if v not in ("long", "short", "none"):
            return {"ok": False}
        d[h] = v
    try:
        conf = int(max(0, min(100, float(o.get("conf", 0)))))
    except Exception:  # noqa: BLE001
        conf = 0
    return {"ok": True, "d": d, "conf": conf, "why": str(o.get("why", ""))[:300]}


# ------------------------------------------------------------------ leakage probe
def leak_days(first_month, last_month, per_month, seed_key, valid_days):
    """Deterministic sample of `per_month` trading days per month from valid_days (sorted 'YYYY-MM-DD')."""
    by = {}
    for d in valid_days:
        by.setdefault(d[:7], []).append(d)
    out = []
    for mth in sorted(by):
        if first_month <= mth <= last_month:
            days = sorted(by[mth], key=lambda d: unit(f"{seed_key}:{d}"))
            out += sorted(days[:per_month])
    return out


def parse_updown(text):
    t = (text or "").strip().lower()
    for w in ("up", "down", "unknown"):
        if re.match(r"^\W*" + w + r"\b", t):
            return w
    m = re.search(r"\b(up|down|unknown)\b", t)
    return m.group(1) if m else None
