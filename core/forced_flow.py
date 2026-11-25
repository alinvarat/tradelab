"""Forced-flow event families shaped like L1f (a short after an exchange notice that forces holders to sell). Pure functions, no
network. Spec: research/studies/protocol_forced_flow_20261125.md (locked before any price of this study was pulled).

Trades are dicts in the core.sweep_engine format (t, te, x, sym, side, gross, cost, fund, net, mfe, mae, reason) so that the
sweep gate (core.sweep_stats.gate) and the pass criteria (core.sweep_stats.evaluate / judge_family) apply unchanged.
"""
import json
import math
import re
from datetime import datetime, timezone

COST = 0.006                                    # round trip: taker fees 0.11% + slippage 0.2% per side (as the notice tape / event rows)
FUND = {3600: 0.001, 14400: 0.001, 86400: 0.003}   # funding/borrow assumed per hold (the book's 0.1% for 4 h)
STOP = 0.25
STOP_SLIP = 0.005
HOLDS = (3600, 14400, 86400)
DELAYS = (60, 300)
DEDUPE_S = 7 * 86400
OVERLAP_S = 7 * 86400
SEED = 20261125


def _t(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


START, END = _t(2024, 1, 1), _t(2026, 10, 29)
BOUNDS = {"train": (START, _t(2025, 7, 1)), "validation": (_t(2025, 7, 1), _t(2026, 3, 1)), "test": (_t(2026, 3, 1), END)}
MONTHS = (END - START) / 86400 / 30.4375
CFG = {"alpha": 0.05, "account_usd": 147.0,
       "gate": {"min_train_trades": 20, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
       "pass": {"min_val_trades": 12, "min_test_trades": 10}}
CFG_STRICT = {"alpha": 0.05, "account_usd": 147.0,       # the sweep's own trade counts, reported beside the event-family counts
              "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
              "pass": {"min_val_trades": 30, "min_test_trades": 20}}
SIZE = {"lev": 1, "k": 1}
CONTROL_COINS = ("ADA", "ALGO", "APT", "ARB", "ATOM", "AVAX", "AXS", "CHZ", "CRV", "DOGE", "DOT", "DYDX", "ENJ", "FIL", "GALA",
                 "INJ", "LDO", "LINK", "MANA", "NEAR", "OP", "SAND", "SNX", "UNI")
N_CONTROL = 5

_TICK = re.compile(r"^[A-Z0-9]{2,15}$")
_NOT_COIN = {"USDT", "USDC", "FDUSD", "BUSD", "BTC", "ETH", "BNB", "TRY", "EUR", "BRL", "KRW", "AND", "ON", "THE", "FOR", "TO",
             "USD", "UTC", "ALL", "NEW", "TAG", "SEED", "MONITORING", "REMOVE", "INCLUDE", "EXTEND"}


def rule_id(fam, hold, delay):
    return f"{fam}|h{hold // 3600}h|d{delay // 60}m"


def family_rules(fam):
    return [(rule_id(fam, h, d), h, d) for h in HOLDS for d in DELAYS]


# ---------------------------------------------------------------- parsers
def _tokens(text):
    out = []
    for tok in re.split(r"[,&\s]+|\band\b", text):
        tok = tok.strip(" .;:()")
        tok = re.sub(r"^(1000000|10000|1000)(?=[A-Z])", "", tok)
        if _TICK.match(tok) and re.search("[A-Z]", tok) and tok not in _NOT_COIN and tok not in out:
            out.append(tok)
    return out


def monitoring_symbols(title: str) -> list:
    """'Binance Will Extend the Monitoring Tag to Include A, B & C, and Remove ... on 2026-01-02' -> ['A', 'B', 'C']
    (coins that GET the tag; removals and seed-tag removals are not events). 'Extend the Monitoring Tag to GPS on ...' also works."""
    m = re.search(r"Extend the Monitoring Tag to (?:Include )?(.+)", title.strip())
    if not m:
        return []
    body = m.group(1)
    body = re.split(r",?\s*(?:and\s+)?Remove\b|\s+on\s+\d{4}-\d{2}-\d{2}", body)[0]
    return _tokens(body)


def fut_delist_symbols(title: str, body: str = "") -> list:
    """Coins of 'Binance Futures Will Delist ... Perpetual Contract(s)' notices: every <COIN>USDT contract named in the title and
    body. Titles that also update leverage/margin tiers ('Delist and Update ...') are skipped (the body mixes delisted and updated
    contracts); COIN-M and delivery contracts (with an underscore date) are not included."""
    if "Perpetual" not in title or re.search(r"\bUpdate\b", title):
        return []
    toks = re.findall(r"\b([A-Z0-9]{2,15})USDT\b(?!_)", title + " " + body)
    toks += re.findall(r"\b([A-Z0-9]{2,15})USDC\b(?!_)", title + " " + body)
    return _tokens(" ".join(toks))


def flatten_body(body) -> str:
    """Binance article body (a JSON tree {'node','child','text'}) -> plain text."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return body
    out = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("node") == "text":
                out.append(n.get("text", ""))
            for c in n.get("child") or []:
                walk(c)
        elif isinstance(n, list):
            for c in n:
                walk(c)
    walk(body)
    return " ".join(out)


def pair_removal_symbols(text: str) -> list:
    """Base coins of the removed */USDT spot pairs in a 'Notice of Removal of Spot Trading Pairs' body: 'At 2026-11-20 03:00
    (UTC): GAS/TRY, HBAR/BNB, ABC/USDT and DEF/USDT' -> ['ABC', 'DEF']. Only the USDT quote counts (the coin's main market)."""
    return _tokens(" ".join(re.findall(r"\b([A-Z0-9]{2,15})/USDT\b", text)))


def kr_class(title: str) -> str:
    """Upbit/Bithumb title (Korean or English) -> 'delist' | 'caution' | ''. Event-style 'termination' words are not matched; lifted,
    extended, cancelled or completed notices are not new forced sales; a title that mixes a caution designation and a delisting
    (or a designation and its lifting) is ambiguous and is not an event."""
    low = title.lower()
    if re.search(r"해제|해지|연장|취소|유예|재개|completed|cancel|extend|postpone|lifted|resum", low):
        return ""
    delist = bool(re.search(r"거래지원\s*종료|상장\s*폐지|market support termination|support termination|termination of (?:digital asset )?(?:market )?support|delist", low))
    caution = bool(re.search(r"유의\s*종목|투자\s*유의|investment warning|caution", low))
    if delist and caution:
        return ""
    return "delist" if delist else ("caution" if caution else "")


def kr_symbols(title: str) -> list:
    """Tickers in parentheses of a Korean exchange title: '싸이식(CYS) 거래지원 종료' -> ['CYS'] (also 'A(AAA), B(BBB)')."""
    out = []
    for grp in re.findall(r"\(([^()]*)\)", title):
        parts = [g for g in re.split(r"[,/\s]+", grp.strip()) if g]
        if parts and all(_TICK.match(g) for g in parts):
            out += parts
    return _tokens(" ".join(out))


def bybit_class_symbols(slug_title: str):
    """Bybit announcement title -> ('perp_delist' | 'delist', coins) or None. Coins come only from the words after 'Delisting of' /
    'to delist' / 'Delists'. Alpha, TradFi, pair-only, zone and swap/migration notices are skipped."""
    t = slug_title.strip()
    low = t.lower()
    if any(k in low for k in ("alpha", "tradfi", "pre-market", "innovation", "spot trading pair", "trading pairs", "leveraged", "margin",
                              "p2p", "launchpool", "in the uk", "monitoring", "swap to", "migration", "rebrand")):
        return None
    m = re.search(r"(?i)(?:delisting of|to delist|delists?)\s+(.+?)(?:\s+perpetual|\s+contracts?|\s+spot|\s+on\s+(?:bybit|\w{3}\s+\d)|$)", t)
    if not m:
        return None
    perp = bool(re.search(r"perpetual|contract", low))
    seg = re.sub(r"/USD[TC]\b", " ", m.group(1))
    toks = re.findall(r"\b([A-Z0-9]{2,15})USDT\b", seg) if perp else []
    coins = _tokens(" ".join(toks)) if toks else _tokens(seg)
    return ("perp_delist" if perp else "delist", coins) if coins else None


# ---------------------------------------------------------------- events
def dedupe(events):
    """One event per (family, coin) within 7 days: the first notice counts. Input in any order; output sorted by time."""
    seen, out = {}, []
    for e in sorted(events, key=lambda e: e["ts"]):
        k = (e["fam"], e["sym"])
        if k in seen and e["ts"] - seen[k] < DEDUPE_S:
            continue
        seen[k] = e["ts"]
        out.append(e)
    return out


def in_window(ts):
    return START <= ts < END


def overlaps_l1f(ev, l1f_events):
    """True when the same coin has an L1f notice (Binance 'Will Delist') within +-7 days of this event."""
    return any(l["sym"] == ev["sym"] and abs(l["ts"] - ev["ts"]) <= OVERLAP_S for l in l1f_events)


# ---------------------------------------------------------------- simulation
def short_trade(bars: dict, step: int, ts: float, delay: int, hold: int, stop: float = STOP):
    """One short on {bar open ts: (o, h, l, c)} bars of `step` seconds. Entry at the open of the first bar at or after ts + delay
    (at most 3 bars late), exit at the open of the bar `hold` seconds later (at most 3 bars late) or at the stop (25% above the
    entry on a bar high, fill at the stop plus 0.5% slippage). Returns dict(gross, mfe, mae, te, x, reason) or None."""
    t0 = int(math.ceil((ts + delay) / step) * step)
    e = next((t for t in range(t0, t0 + 3 * step, step) if t in bars), None)
    if e is None:
        return None
    entry = bars[e][0]
    x_t = next((t for t in range(e + hold, e + hold + 3 * step, step) if t in bars), None)
    if x_t is None or entry <= 0:
        return None
    hi, lo, reason, gross, end = entry, entry, "time", None, x_t
    for t in range(e, x_t, step):
        b = bars.get(t)
        if b is None:
            continue
        hi, lo = max(hi, b[1]), min(lo, b[2])
        if b[1] >= entry * (1 + stop):
            gross, reason, end = -(stop + STOP_SLIP), "stop", t + step
            break
    if gross is None:
        gross = -(bars[x_t][0] / entry - 1)
    return {"te": e, "x": end, "gross": gross, "mfe": max((entry - lo) / entry, 0.0), "mae": max((hi - entry) / entry, 0.0), "reason": reason}


def make_trade(sym, ts, sim, hold, ctrl_gross=None):
    """Sweep-format trade. net = gross - cost - fund (short). ctrl_net: the same for the control basket's mean gross."""
    cost, fund = COST, FUND[hold]
    t = {"sym": sym, "side": -1, "t": ts, "te": sim["te"], "x": sim["x"], "ep": 0.0, "xp": 0.0, "gross": sim["gross"], "cost": cost,
         "fund": fund, "net": sim["gross"] - cost - fund, "mfe": sim["mfe"], "mae": sim["mae"], "reason": sim["reason"]}
    if ctrl_gross is not None:
        t["ctrl_net"] = ctrl_gross - cost - fund
    return t


def pick_control(rng, exclude: str) -> list:
    """N_CONTROL coins drawn at random from CONTROL_COINS, never the event coin (one draw per event, shared by its rules)."""
    return rng.sample([c for c in CONTROL_COINS if c != exclude], N_CONTROL)


def control_gross(ctrl_bars: dict, picks: list, step: int, ts: float, delay: int, hold: int):
    """Mean gross of the same short on the drawn control coins that have bars. ctrl_bars {coin: bars dict}. None when fewer
    than 3 of them give a usable trade."""
    vals = []
    for c in picks:
        b = ctrl_bars.get(c)
        if not b:
            continue
        s = short_trade(b, step, ts, delay, hold)
        if s:
            vals.append(s["gross"])
    return sum(vals) / len(vals) if len(vals) >= 3 else None


# ---------------------------------------------------------------- statistics
def stats(values, months):
    n = len(values)
    if n < 2:
        return {"n": n}
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    s = m / sd if sd > 0 else 0.0
    return {"n": n, "mean": round(m, 5), "sd": round(sd, 5), "s": round(s, 4), "per_month": round(n / months, 3),
            "x": round(n / months * s * s, 4), "hit": round(sum(1 for v in values if v > 0) / n, 3)}


def daily(trades, a, b, key="net"):
    """One value per UTC day of [a, b): the sum of the trades' `key` signalled that day."""
    n = int((b - a) // 86400)
    out = [0.0] * n
    for t in trades:
        k = int((t["t"] - a) // 86400)
        if 0 <= k < n:
            out[k] += t[key]
    return out


def corr(x, y):
    n = len(x)
    if n < 3 or n != len(y):
        return None
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)
