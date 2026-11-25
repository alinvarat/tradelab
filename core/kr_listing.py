"""D2: Upbit / Bithumb KRW-market listing notice, long the global perp. Pure functions, no network. Spec:
research/studies/protocol_kr_listing_20261126.md (locked before any price of this study was pulled).

Trades are dicts in the core.sweep_engine format so core.sweep_stats.gate / evaluate / judge_family apply unchanged. net = gross - cost - fund
(a long; the reversed side, the placebo, is -gross - cost + fund as in the sweep gate)."""
import math
import re

from core import forced_flow as ff

FAM = "kr_listing"
COST = 0.006                         # round trip, as forced_flow
FUND = {900: 0.0005, 3600: 0.001, 14400: 0.001}   # assumed funding/borrow per hold (long: charged as a cost, conservative)
STOP = 0.25
STOP_SLIP = 0.005
HOLDS = (900, 3600, 14400)
DELAYS = (60, 300, 900)
DEDUPE_S = 30 * 86400
SEED = 20261126
START, END, BOUNDS, MONTHS = ff.START, ff.END, ff.BOUNDS, ff.MONTHS
CFG, CFG_STRICT, SIZE = ff.CFG, ff.CFG_STRICT, ff.SIZE
stats, daily, corr = ff.stats, ff.daily, ff.corr


def rule_id(hold, delay):
    return f"{FAM}|h{hold // 60}m|d{delay // 60}m"


def family_rules():
    return [(rule_id(h, d), h, d) for h in HOLDS for d in DELAYS]


_KRW = re.compile(r"원화|KRW", re.I)
_ADD = re.compile(r"마켓\s*추가|디지털\s*자산\s*추가|신규\s*거래\s*지원|신규\s*상장|신규\s*디지털|market\s*add|add(?:ed|ing)?\s+.*market|new\s+listing|support\s+for", re.I)
_NOT = re.compile(r"종료|폐지|유의|해제|해지|변경|연기|취소|유예|재개|중단|점검|이벤트|지급|입출금|출금|입금|상장\s*기념|"
                  r"delist|terminat|cancel|postpone|suspend|resum|event|airdrop|maintenance|warning|caution|lifted|change", re.I)


_NOTE = re.compile(r"\s*\([^()]*(?:안내|연기|변경|재개|오픈|출금|입금|정상화|지연|delay|notice|change|schedule|update)[^()]*\)\s*$", re.I)


def strip_notes(title: str) -> str:
    """Addendum 20261126: notices are edited after posting with a trailing note such as '(거래지원 개시 시점 연기 안내)'; the first capture can already
    carry it. Trailing parenthetical notes with schedule/withdrawal words are removed before the exclusion test; a note with cancel/terminate words is kept (and excludes)."""
    t = title or ""
    while True:
        m = _NOTE.search(t)
        if not m or _CANCEL.search(m.group(0)):
            return t
        t = t[:m.start()]


_CANCEL = re.compile(r"취소|종료|폐지|cancel|terminat", re.I)


def listing_title(title: str) -> bool:
    """True for a notice that opens a KRW (원화) market for a coin. BTC-only / USDT-only markets, events, caution, delist,
    change, postpone and cancel notices are not events."""
    if not title:
        return False
    t = strip_notes(title)
    if _NOT.search(t):
        return False
    return bool(_KRW.search(t) and _ADD.search(t))


def listing_symbols(title: str) -> list:
    return ff.kr_symbols(title) if listing_title(title) else []


def dedupe(events):
    """One event per coin within 30 days across both venues: the earliest notice counts (the later venue adds no new information)."""
    seen, out = {}, []
    for e in sorted(events, key=lambda e: e["ts"]):
        if e["sym"] in seen and e["ts"] - seen[e["sym"]] < DEDUPE_S:
            continue
        seen[e["sym"]] = e["ts"]
        out.append(e)
    return out


def long_trade(bars: dict, step: int, ts: float, delay: int, hold: int, stop: float = STOP):
    """One long on {bar open ts: (o, h, l, c)} bars of `step` seconds. Entry at the open of the first bar at or after ts + delay
    (at most 3 bars late), exit at the open of the bar `hold` seconds later (at most 3 bars late) or at the stop (25% below the
    entry on a bar low, fill at the stop minus 0.5%). Returns dict(gross, mfe, mae, te, x, reason) or None."""
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
        if b[2] <= entry * (1 - stop):
            gross, reason, end = -(stop + STOP_SLIP), "stop", t + step
            break
    if gross is None:
        gross = bars[x_t][0] / entry - 1
    return {"te": e, "x": end, "gross": gross, "mfe": max((hi - entry) / entry, 0.0), "mae": max((entry - lo) / entry, 0.0), "reason": reason}


def make_trade(sym, ts, sim, hold, ctrl_gross=None):
    cost, fund = COST, FUND[hold]
    t = {"sym": sym, "side": 1, "t": ts, "te": sim["te"], "x": sim["x"], "ep": 0.0, "xp": 0.0, "gross": sim["gross"], "cost": cost,
         "fund": fund, "net": sim["gross"] - cost - fund, "mfe": sim["mfe"], "mae": sim["mae"], "reason": sim["reason"]}
    if ctrl_gross is not None:
        t["ctrl_net"] = ctrl_gross - cost - fund
    return t


def control_gross(ctrl_bars: dict, picks: list, step: int, ts: float, delay: int, hold: int):
    """Mean gross of the same long on the drawn control coins (5-minute bars); None when fewer than 3 give a trade."""
    vals = []
    for c in picks:
        b = ctrl_bars.get(c)
        s = long_trade(b, step, ts, delay, hold) if b else None
        if s:
            vals.append(s["gross"])
    return sum(vals) / len(vals) if len(vals) >= 3 else None
