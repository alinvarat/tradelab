"""Exchange-notice tape (family 1 of research/plans/PLAN_20261125_fable.md): classify exchange announcements, simulate
the locked grid on perp 1-minute paths, judge the family with Holm. Pure functions; no network.
Spec: research/studies/protocol_notice_tape_20261125.md (locked before the run)."""
import math
import re

CLASSES = ("listing", "delist", "perp_delist", "monitoring", "funding_interval")
# (class, side) cells: +1 long, -1 short. 8 types as pre-registered.
TYPES = (("listing", 1), ("listing", -1), ("delist", 1), ("delist", -1), ("perp_delist", 1), ("perp_delist", -1),
         ("monitoring", -1), ("funding_interval", -1))
HOLDS = {"1h": 3600, "4h": 14400, "24h": 86400, "72h": 259200}
DELAYS = {"1m": 60, "5m": 300, "15m": 900}
STOPS = (0.10, 0.25)
STOP_SLIP = 0.005
COST = 0.007                  # round trip: fees 0.11% + slippage 0.2% per side + 0.1% funding/borrow
MIN_N = 30                    # events needed for a cell to be able to pass
HOLM_ALPHA = 0.05

_TICK = re.compile(r"^[A-Z0-9]{2,12}$")
_STABLE = {"USDT", "USDC", "USD", "BTC", "ETH", "KRW", "EUR", "PERP", "SPOT", "AND", "THE", "FOR", "NEW", "ALL", "API",
           "KYC", "UTC", "OKX", "BYBIT", "KUCOIN", "BITGET", "ST", "ETF", "USDE"}
_VERB = re.compile(r"\b(?:delisting of|listing of|delist|delists|list|lists|listed|adds?|removes?|removal of|support|supports|"
                   r"monitoring tag (?:for|to|on)|tag (?:for|to|on))\s+(.+)", re.I)


def _clean(tokens) -> list:
    out = []
    for t in tokens:
        t = re.sub(r"^(1000000|10000|1000)(?=[A-Z])", "", t.strip())
        if _TICK.match(t) and re.search("[A-Z]", t) and t not in _STABLE and t not in out:
            out.append(t)
    return out


def title_symbols(title: str) -> list:
    """Tickers named in a notice title. Only upper-case tokens count, so 'Cow Protocol' never becomes a ticker.
    Sources, in order: pair names (XXXUSDT, XXX/USDT, XXX-USDT), a ticker list after a verb ('delist DORA, ICX and ELF
    spot ...'), and parenthesised tickers ('(JELLYJELLY)')."""
    toks = re.findall(r"\b([A-Z0-9]{2,12})(?:USDT|USDC)\b", title)
    toks += re.findall(r"\b([A-Z0-9]{2,12})[/-](?:USDT|USDC|USD)\b", title)
    for grp in re.findall(r"\(([^()]*)\)", title):
        parts = [g for g in re.split(r"[,\s/]+", grp.strip()) if g]
        if parts and all(_TICK.match(g) for g in parts):
            toks += parts
    m = _VERB.search(title)
    if m:
        for w in re.split(r"[\s,]+", m.group(1)):
            if w.lower() in ("and", "&", ""):
                continue
            if _TICK.match(w) and w not in _STABLE:
                toks.append(w)
            else:
                break
    return _clean(toks)


_SKIP = ("tradfi", "stock", "equity", "pre-market", "premarket", "pre-ipo", "etf", "index", "copy trading",
         "trading bot", "campaign", "airdrop", "earn", "loan", "convert", "launchpool", "launchpad", "giveaway",
         "competition", "reward", "margin", "delay", "postpone", "futures will list", "new listing:", "bot trading", "trading bot", "maintenance", "wallet", "deposit", "withdraw")


def classify_title(title: str) -> list:
    """[(class, [symbols])] for one announcement title; [] when it is not one of the five classes."""
    t = title.strip()
    low = t.lower()
    if any(k in low for k in _SKIP):
        return []
    syms = title_symbols(t)
    if not syms:
        return []
    perp = "perpetual" in low or "perp" in low or "futures" in low or "swap" in low or "contract" in low
    if any(k in low for k in ("monitoring tag", "monitor tag", "st tag", "risk tag", "monitoring label")):
        return [("monitoring", syms)]
    if "funding" in low and "interval" in low:
        return [("funding_interval", syms)]
    if re.search(r"\bdelist|\bremov(e|al)\b|\bcease|\bsuspend trading|\bdelisting\b", low):
        return [("perp_delist" if perp else "delist", syms)]
    if re.search(r"\blist(ing|ed|s)?\b|\bwill add\b|\badds\b|\bnew listing\b", low):
        if perp:                                    # a futures launch is not one of the five classes
            return []
        return [("listing", syms)]
    return []


# ---------------------------------------------------------------- simulation
def cell_return(path: list, side: int, hold_s: int, delay_s: int, stop: float, bench: list = None, step_s: int = 60,
                cost: float = COST):
    """Net abnormal return of one event in one cell. path = [(high, low, close)] of 1-minute perp bars from the notice
    minute (index 0 = bar containing the notice time); entry at the close of bar delay_s/step_s, exit at the close of
    bar (delay_s + hold_s)/step_s or at the stop. bench = [close] of BTC for the same bars (subtracted, so market beta
    is removed). Returns None when a needed bar is missing."""
    i0, i1 = delay_s // step_s, (delay_s + hold_s) // step_s
    if i1 >= len(path) or path[i0] is None or path[i1] is None:
        return None
    p0 = path[i0][2]
    if not p0:
        return None
    ret, stopped = None, False
    for k in range(i0 + 1, i1 + 1):
        b = path[k]
        if b is None:
            continue
        hi, lo = b[0], b[1]
        if (side > 0 and lo <= p0 * (1 - stop)) or (side < 0 and hi >= p0 * (1 + stop)):
            ret, stopped = -(stop + STOP_SLIP), True
            break
    if ret is None:
        ret = side * (path[i1][2] / p0 - 1)
    if bench and not stopped and bench[i0] and i1 < len(bench) and bench[i1]:
        ret -= side * (bench[i1] / bench[i0] - 1)
    return ret - cost


def stats(values: list, months: float) -> dict:
    n = len(values)
    if n < 2:
        return {"n": n}
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    s = m / sd if sd > 0 else 0.0
    return {"n": n, "mean": round(m, 5), "sd": round(sd, 5), "s": round(s, 4), "per_month": round(n / months, 3),
            "x": round(n / months * s * s, 4), "hit": round(sum(1 for v in values if v > 0) / n, 3)}


def holm(pvals: dict, alpha: float = HOLM_ALPHA) -> dict:
    """Holm step-down over the whole family: {cell: (adjusted_p, rejected)}. Cells without a p count as p = 1."""
    items = sorted(pvals.items(), key=lambda kv: (1.0 if kv[1] is None else kv[1]))
    m = len(items)
    out, running, stop = {}, 0.0, False
    for i, (k, p) in enumerate(items):
        p = 1.0 if p is None else p
        adj = min(1.0, max(running, (m - i) * p))
        running = adj
        out[k] = (round(adj, 5), (not stop) and adj < alpha)
        if adj >= alpha:
            stop = True
    return out


def trimmed_mean(values: list, drop: int) -> float:
    v = sorted(values)
    v = v[:-drop] if drop and len(v) > drop else v
    return sum(v) / len(v) if v else 0.0


def cell_verdict(values: list, halves: tuple, months: float, adj_p: float) -> dict:
    """Pass rule (locked): n >= MIN_N, Holm-adjusted p < 0.05, mean > 0 in both time halves, > 0 without the best 3
    events, and x = events/month * s^2 >= 0.2."""
    st = stats(values, months)
    if st.get("n", 0) < MIN_N:
        return {**st, "pass": False, "why": f"n < {MIN_N}"}
    h1, h2 = halves
    ok = (adj_p < HOLM_ALPHA and h1 and h2 and sum(h1) / len(h1) > 0 and sum(h2) / len(h2) > 0
          and trimmed_mean(values, 3) > 0 and st["x"] >= 0.2)
    return {**st, "adj_p": adj_p, "half1": round(sum(h1) / len(h1), 5) if h1 else None,
            "half2": round(sum(h2) / len(h2), 5) if h2 else None, "trim3": round(trimmed_mean(values, 3), 5),
            "pass": bool(ok)}
