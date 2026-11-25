"""Pure logic of the forward paper test of two crypto spike screens (no network, no clock; tested offline).

Lines (protocol: research/studies/protocol_fwd_crypto_spikes_20261125.md):
  L12B_F  short after a >= +8% hour (>= 6 points beyond BTC), entry next hour open, exit after 24 h.
  L8B_F   short after a >= +20% UTC day, entry next UTC open, exit after 1 day.
Event detection reuses core.screens.hourly_shock_rows / gainer_fade_rows unchanged. A perp must exist (OKX USDT swap with
a funding rate settled in the 24 h before entry, the same test L12b used on Binance). Every event is tracked to its exit
(`taken` False when the book is full) and each gets a same-time seeded random control; the ledger only books taken trades.
"""
import bisect
import hashlib
import random
import re

from core import screens as sc
from core import sequential

START_EQUITY = 147.0
STAKE = 0.10                        # share of ledger equity per taken trade
MAX_OPEN = 5                        # taken trades open at once, per line
MAX_EVENTS = 150                    # closed events (taken or not) at which the test stops
FEES = 0.004                        # round trip taker + slippage, same as the screens
HOUR, DAY = 3600, 86400
LINES = {"L12B_F": {"interval": "1h", "step": HOUR, "hold": DAY, "min_qv": sc.L12_MIN_QV, "cooldown": DAY},
         "L8B_F": {"interval": "1d", "step": DAY, "hold": DAY, "min_qv": sc.L8_MIN_QV, "cooldown": 7 * DAY}}
SKIP = ("USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI", "EUR", "TRY", "BRL", "AEUR", "USDE", "PAXG", "WBTC", "WBETH")


def eligible_symbol(sym: str) -> bool:
    """Spot symbol the screens consider: XXXUSDT, not stable/fiat/wrapped/leveraged (same skip list as L8)."""
    if not sym.endswith("USDT"):
        return False
    base = sym[:-4]
    return bool(base) and base not in SKIP and not re.search(r"(UP|DOWN|BULL|BEAR)$", base)


def okx_inst(sym: str) -> str:
    return f"{sym[:-4]}-USDT-SWAP"


def perp_live(funding: list, entry_ts: float) -> bool:
    """funding: [(settle_ts, rate)]. True when a rate settled in the 24 h before entry (L12b's definition)."""
    times = sorted(t for t, _ in funding)
    k = bisect.bisect_left(times, entry_ts - DAY)
    return k < len(times) and times[k] < entry_ts


def funding_paid(funding: list, start: float, end: float) -> float:
    """Funding a short receives for settlements with start <= t < end (positive rate: longs pay shorts)."""
    return sum(rate for t, rate in funding if start <= t < end)


def trade_return(entry: float, exit_: float, btc_entry: float, btc_exit: float, funding: float, fees: float = FEES) -> float:
    """Short, BTC-hedged, net: short gain (1 - exit/entry) - BTC short gain - fees + funding received."""
    return sc.short_gain(entry, exit_) - sc.short_gain(btc_entry, btc_exit) - fees + funding


# ------------------------------------------------------------------ detection
def detect_hourly(symbol: str, h1: list, btc: dict, funding: list, min_event_hour: float, last_event_ts: float = 0.0) -> list:
    """h1: hourly bars (open_ts, o, h, l, c, quote_vol) oldest first INCLUDING the open entry bar; btc: open_ts -> (o, c).
    Events whose shock hour H >= min_event_hour (H closed), not within 24 h of `last_event_ts`, with a live perp.
    The series is cut so the first hour evaluated is min_event_hour with its full 720 preceding hours."""
    start = min_event_hour - 720 * HOUR
    bars = [b for b in h1 if b[0] >= start]
    out = []
    for r in sc.hourly_shock_rows(symbol, bars, btc, -1):
        e_ts = r["ts"]
        if e_ts - HOUR < min_event_hour or e_ts - last_event_ts < LINES["L12B_F"]["cooldown"]:
            continue
        if not perp_live(funding, e_ts):
            continue
        out.append({"line": "L12B_F", "symbol": symbol, "entry_ts": e_ts, "move": r["move"]})
    return out


def detect_daily(symbol: str, d1: list, btc: dict, funding: list, min_event_day: float, last_event_ts: float = 0.0) -> list:
    """d1: daily bars INCLUDING the open entry-day bar. Events whose shock day D >= min_event_day, not within 7 days of
    `last_event_ts`, with a live perp. First day evaluated is min_event_day with its 21 preceding bars."""
    start = min_event_day - 21 * DAY
    bars = [b for b in d1 if b[0] >= start]
    out = []
    for r in sc.gainer_fade_rows(symbol, bars, btc):
        e_ts = r["ts"]
        if e_ts - DAY < min_event_day or e_ts - last_event_ts < LINES["L8B_F"]["cooldown"]:
            continue
        if not perp_live(funding, e_ts):
            continue
        out.append({"line": "L8B_F", "symbol": symbol, "entry_ts": e_ts, "move": r["gain"]})
    return out


def control_order(line: str, entry_ts: float, event_symbol: str, pool: list) -> list:
    """Seeded shuffle of the eligible perp coins (event coin excluded): the first with data is the same-time control.
    The seed depends only on line, entry time and event coin, so a re-run picks the same one."""
    seed = int(hashlib.sha256(f"{line}|{int(entry_ts)}|{event_symbol}".encode()).hexdigest()[:16], 16)
    cands = sorted(s for s in set(pool) if s != event_symbol)
    random.Random(seed).shuffle(cands)
    return cands


def exit_bar_ts(line: str, entry_ts: float) -> float:
    """Open time of the bar whose close is the exit price (the last bar of the 24 h hold)."""
    return entry_ts + LINES[line]["hold"] - LINES[line]["step"]


# ------------------------------------------------------------------ ledger state machine
def new_state(now: float) -> dict:
    hour = now - now % HOUR
    day_ceil = now - now % DAY + (DAY if now % DAY else 0)
    # first shock bar is the hour (day) that opens at or after start_ts, so no bar that began before the protocol counts
    return {"version": 1, "start_ts": hour, "h_next": hour, "d_next": day_ceil, "gap_hours_missed": 0,
            "lines": {k: {"equity": START_EQUITY, "open": [], "closed": [], "last_event": {}, "skipped_cap": 0}
                      for k in LINES}}


def open_event(state: dict, ev: dict, entry_px: float, btc_entry: float, control: dict = None) -> dict:
    """Register an event as a position. Taken (stake > 0) when fewer than MAX_OPEN taken trades are open, else a shadow
    (stake 0) that is still tracked so evidence uses every signal. Returns the position, or None if it is a duplicate."""
    ln = state["lines"][ev["line"]]
    pid = f'{ev["line"]}|{ev["symbol"]}|{int(ev["entry_ts"])}'
    if any(p["id"] == pid for p in ln["open"] + ln["closed"]):
        return None
    taken = sum(1 for p in ln["open"] if p["stake"] > 0) < MAX_OPEN
    stake = round(ln["equity"] * STAKE, 4) if taken else 0.0
    if not taken:
        ln["skipped_cap"] += 1
    ln["last_event"][ev["symbol"]] = max(ev["entry_ts"], ln["last_event"].get(ev["symbol"], 0))
    pos = {"id": pid, "line": ev["line"], "symbol": ev["symbol"], "entry_ts": ev["entry_ts"], "entry_px": entry_px,
           "btc_entry": btc_entry, "stake": stake, "move": ev.get("move"), "control": control}
    ln["open"].append(pos)
    return pos


def due(pos: dict, now: float, grace: float = 60.0) -> bool:
    return now >= pos["entry_ts"] + LINES[pos["line"]]["hold"] + grace


def close_position(state: dict, pos: dict, exit_px: float, btc_exit: float, fund: float, now: float,
                   control_exit: dict = None, liquidated: bool = False) -> dict:
    """Close a position: net return, ledger equity (taken trades only), control result. control_exit:
    {"exit_px", "btc_exit", "funding"} for the control coin, or None (control unavailable)."""
    ln = state["lines"][pos["line"]]
    net = trade_return(pos["entry_px"], exit_px, pos["btc_entry"], btc_exit, fund)
    ctrl = None
    c = pos.get("control")
    if c and control_exit:
        ctrl = trade_return(c["entry_px"], control_exit["exit_px"], c["btc_entry"], control_exit["btc_exit"], control_exit["funding"])
    pnl = round(pos["stake"] * net, 4)
    ln["equity"] = round(ln["equity"] + pnl, 4)
    row = {**pos, "exit_px": exit_px, "btc_exit": btc_exit, "funding": fund, "net": net, "control_net": ctrl,
           "liquidated": liquidated, "pnl_usd": pnl, "ts": now, "equity_after": ln["equity"]}
    ln["open"] = [p for p in ln["open"] if p["id"] != pos["id"]]
    ln["closed"].append(row)
    return row


def evidence(closed: list, max_events: int = MAX_EVENTS) -> dict:
    """Sequential evidence per protocol: core.sequential.paired_daily over closed events (every event counts, taken or
    not), one unit per UTC exit day. Verdict: `edge` only when both the model and the model-minus-control e-process
    reach 20; `no edge` when either negative side reaches 20; at max_events without either: `inconclusive at max`."""
    rows = [{"ts": r["ts"], "model": r["net"], "control": r.get("control_net")} for r in closed]
    res = sequential.paired_daily(rows, start=0, before=float("inf"))
    m, p = res["model"], res["paired"]
    if m["decision"] == "edge" and p["decision"] == "edge":
        verdict = "edge (forward test of an inconclusive screen, not a pass of the screen)"
    elif m["decision"].startswith("no edge") or p["decision"].startswith("no edge"):
        verdict = "no edge"
    elif len(closed) >= max_events:
        verdict = "inconclusive at max"
    else:
        verdict = "continue"
    return {"n_closed": len(closed), "max_events": max_events, "verdict": verdict, "model": m, "paired": p}


def line_active(state: dict, line: str) -> bool:
    """A line keeps opening events only while its verdict is `continue` (open trades still close after a stop)."""
    return evidence(state["lines"][line]["closed"])["verdict"] == "continue"


def drawdown(state: dict, line: str) -> float:
    """Worst peak-to-trough fall of the line's realized equity, as a fraction of the peak (0 when none)."""
    peak, worst = START_EQUITY, 0.0
    for r in state["lines"][line]["closed"]:
        peak = max(peak, r["equity_after"])
        worst = max(worst, 1 - r["equity_after"] / peak)
    return round(worst, 4)


def line_summary(state: dict, line: str) -> dict:
    ln = state["lines"][line]
    c = ln["closed"]
    nets = [r["net"] for r in c]
    ctrl = [r["control_net"] for r in c if r.get("control_net") is not None]
    taken = [r for r in c if r["stake"] > 0]
    return {"equity_usd": ln["equity"], "start_usd": START_EQUITY, "open": len(ln["open"]),
            "open_taken": sum(1 for p in ln["open"] if p["stake"] > 0), "closed": len(c), "closed_taken": len(taken),
            "skipped_cap": ln["skipped_cap"], "worst_drawdown": drawdown(state, line),
            "liquidated": sum(1 for r in c if r.get("liquidated")),
            "funding_usd_taken": round(sum(r["stake"] * r["funding"] for r in taken), 4),
            "mean_funding": round(sum(r["funding"] for r in c) / len(c), 5) if c else None,
            "equity_double_cost_usd": round(START_EQUITY + sum(r["pnl_usd"] - r["stake"] * FEES for r in taken), 4),
            "mean_net_double_cost": round(sum(nets) / len(nets) - FEES, 5) if nets else None,
            "mean_net": round(sum(nets) / len(nets), 5) if nets else None,
            "mean_control": round(sum(ctrl) / len(ctrl), 5) if ctrl else None,
            "hit_rate": round(sum(1 for x in nets if x > 0) / len(nets), 3) if nets else None,
            "worst_net": round(min(nets), 4) if nets else None,
            "evidence": evidence(c)}


# ------------------------------------------------------------------ parsers (pure)
def parse_klines(rows: list, now: float = None, closed_only: bool = False) -> list:
    """Binance kline rows -> [(open_ts_s, o, h, l, c, quote_volume)]; closed_only drops a bar still open at `now`."""
    out = []
    for r in rows:
        t = int(r[0]) / 1000
        if closed_only and now is not None and int(r[6]) / 1000 >= now:
            continue
        out.append((t, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])))
    return out


def parse_okx_funding(payload: dict) -> list:
    """OKX funding-rate-history -> [(settle_ts_s, rate)] oldest first (realizedRate when present, else fundingRate)."""
    out = []
    for r in payload.get("data") or []:
        rate = r.get("realizedRate") or r.get("fundingRate")
        if rate in (None, ""):
            continue
        out.append((int(r["fundingTime"]) / 1000, float(rate)))
    return sorted(out)


def parse_okx_live_swaps(payload: dict) -> set:
    return {x["instId"] for x in payload.get("data") or [] if x.get("state") == "live" and x.get("instId", "").endswith("-USDT-SWAP")}
