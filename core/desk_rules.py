"""v4.19 desk rules (frozen per protocol tag), risk state and the compact input blocks for the bot. Pure functions: no network,
no file access, no model calls (core/desk_feeds.py does the I/O and core/llm_trader.py wires this in).

Why frozen: a gate that read live statistics would change the bot's behaviour with no review (AGENTS rule 5 and the owner's
rule that behaviour changes ship as a PR with a tag). The constants and the RULES table below are the v4.19 behaviour; the
weekly job (research/llm_trader/weekly.py) recomputes the same cells with shrinkage and proposes the next tag as a PR.
Live statistics only go to the model as labelled context.

Every rule here can only veto an entry, shrink its size/leverage/hold, or stop new entries. None enlarges a trade or flips
its side: the evidence (a few days, overlapping candidates, no costs) cannot support that, and LESSONS says LLM direction
calls on public news had no edge in three rounds."""
import time

from .event_book import BANK_MULT, HALT_MULT

TAG = "v4.19"
SHRINK_K = 20                  # shrinkage toward zero: mean * n / (n + K); a cell with n = K keeps half its mean
MIN_CELL_N = 10                # cells below this n are not shown to the model as evidence

# ---- per-trade and book limits (owner 2026-11-27: manage risk; no martingale, no averaging down)
RISK_PER_TRADE = 0.02          # loss at the stop <= 2% of equity (was 100%)
SIZE_CAP_PCT = 20.0            # margin per position, percent of equity (was 100)
LEV_CAP = 3.0                  # per-trade leverage (was 20)
MAX_POS = 3                    # open positions (was 100)
MAX_EXPOSURE = 1.5             # total notional / equity (was 20)
MAX_ENTRIES_DAY = 3            # new positions per UTC day: abstain more, costs and no measured text edge
MAX_HOLD_S = 4 * 3600          # default time exit for a new entry
FORCED_HOLD_S = 3600           # forced-flow entries: the primary 60 min hold of notice_fwd / L1f
REVIEW_MAX_MIN = 120
MIN_EXPECTED_MOVE_PCT = 0.4    # a stated expected move under 2 x the 0.2% round trip is not worth the cost (arithmetic, not a fit)
DAILY_LOSS_HALT = 0.03         # no new entries after losing 3% of equity in one UTC day
DD_HALF = 0.10                 # drawdown from the peak: half size
DD_HALT = 0.20                 # drawdown from the peak: no new entries for DD_COOLDOWN_S, then the peak resets
DD_COOLDOWN_S = 24 * 3600
COHORT_DAYS = 30               # bank at BANK_MULT x and halt at HALT_MULT x the cohort start, as in core/event_book.py
STREAK_HALF = 2                # two losing closed trades in a row: half size until a win
NEWS_TYPE_ABSTAIN = {"analyst"}

# Frozen evidence behind each rule. Measured on /api/llm_trader desk_stats at 2026-11-27 13:30 UTC (SPY-relative returns of
# every candidate the bot saw, +1 h and +1 d, no costs, overlapping candidates, about three days of data). A "hold" cell is
# the long return of a candidate the bot passed on, so a negative hold cell is evidence AGAINST buying, not about holding.
RULES = {
    "R1": {"text": "abstain on new entries when the newest headline is an analyst note",
           "evidence": "type:analyst/hold/1d n=13 mean -4.96% hit 0.00 (shrunk -1.95%); hit 0 on n=13 is a red flag for "
                       "small-n noise, so the rule only abstains"},
    "R2": {"text": "long entries get half size",
           "evidence": "long-side 1d cells are negative: other n=251 -1.16%, news n=154 -1.31%, mover n=208 -0.85%, shock n=22 "
                       "-1.34% (shrunk -1.07, -1.21, -0.77, -0.63); 1h long cells are +0.0 to +0.16% (n 31-297), below the "
                       "0.14% engine round trip"},
    "R3": {"text": "default time exit 4 h (forced-flow 1 h), review at most every 120 min",
           "evidence": "same cells as R2: 1d long history is negative, 1h is about flat; no cell exists for 2-24 h"},
    "R4": {"text": "short entries are NOT enlarged or favoured",
           "evidence": "mover/short/1d n=10 +1.85% (shrunk +0.62%), other/short/1d n=14 +1.59% (shrunk +0.93%), "
                       "news/short/1d n=4 +0.33%: too few, overlapping and untested against costs to size up"},
    "R5": {"text": "at most 3 new entries a UTC day, 3 open positions, loss at the stop <= 2% of equity, margin <= 20%, "
                   "leverage <= 3, total notional <= 1.5x equity",
           "evidence": "no measured text edge (research/news_train/PLAYBOOK.md rounds 1-3, LESSONS); the desk is 143.85 USD "
                       "against a random control 149.00 USD"},
    "R6": {"text": "no martingale, no averaging down: size never rises after a loss, an add is allowed only while the position "
                   "is in profit and never as a limit order",
           "evidence": "owner rule 2026-11-27"},
    "R7": {"text": "drawdown brake: -10% from peak half size, -20% no entries for 24 h; -3% in a UTC day no entries; "
                   "bank (flatten, no entries) at 3x and halt at 0.4x of the 30-day cohort start",
           "evidence": "same bank and halt levels as core/event_book.py (protocol_event_book_20261125.md)"},
    "R8": {"text": "a stated expected_move_pct under 0.4 vetoes the entry",
           "evidence": "2 x the 0.2% round trip; Haiku's size estimate is weak (sealed partial rho 0.145, 0.047 with the "
                       "filing-type flag; round 3), so it can only veto, never enlarge"},
}


def shrink(mean, n, k=SHRINK_K):
    """Shrink a cell mean toward zero by n / (n + k)."""
    return mean * n / (n + k) if n > 0 else 0.0


def desk_source(why) -> str:
    w = (why or "").lower()
    return ("forced" if "forced-flow" in w else "news" if "headline" in w else "shock" if "shock" in w
            else "buzz" if "buzz" in w else "pre-open" if "pre-open" in w else "mover")


def shrunk_cells(stats: dict, min_n: int = MIN_CELL_N, limit: int = 14) -> list:
    """Compact, labelled cells for the prompt: 'other/hold/1d n=251 raw -1.16% shrunk -1.07% hit 0.43', largest |shrunk| first.
    A hold cell is the long return of a candidate the bot passed on (a negative number argues against buying it)."""
    rows = []
    for k, v in (stats or {}).items():
        n = v.get("n", 0)
        if n >= min_n:
            rows.append((abs(shrink(v["mean_pct"], n)), k, n, v["mean_pct"], v.get("hit")))
    rows.sort(reverse=True)
    return [f"{k} n={n} raw {m:+.2f}% shrunk {shrink(m, n):+.2f}% hit {h}" for _, k, n, m, h in rows[:limit]]


def rules_view() -> list:
    return [f"{k}: {v['text']} [{v['evidence']}]" for k, v in RULES.items()]


# ------------------------------------------------------------------ risk state
def _utc_day(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def new_risk_state(eq, now):
    return {"tag": TAG, "since": now, "peak": eq, "cohort_ts": now, "cohort_eq": eq, "day": _utc_day(now), "day_eq": eq,
            "cool_until": 0.0, "banked": False, "halted": False, "streak": 0, "last_loss": False, "last_size_pct": None,
            "entries_day": _utc_day(now), "entries_n": 0}


def risk_status(rs: dict, eq: float, now: float) -> dict:
    """Update the state for this equity reading and return {allow, mult, reasons, ...}. Idempotent within a reading."""
    if now - rs["cohort_ts"] >= COHORT_DAYS * 86400:      # a new cohort: bank or halt flags end, the base is today's equity
        rs.update(cohort_ts=now, cohort_eq=eq, banked=False, halted=False, peak=eq, cool_until=0.0)
    if rs["day"] != _utc_day(now):
        rs.update(day=_utc_day(now), day_eq=eq)
    rs["peak"] = max(rs["peak"], eq)
    if eq >= BANK_MULT * rs["cohort_eq"]:
        rs["banked"] = True
    if eq <= HALT_MULT * rs["cohort_eq"]:
        rs["halted"] = True
    dd = 1.0 - eq / rs["peak"] if rs["peak"] > 0 else 0.0
    if rs["cool_until"] and now >= rs["cool_until"]:      # cooldown over: the peak resets, so the brake cannot lock forever
        rs.update(cool_until=0.0, peak=eq)
        dd = 0.0
    if not rs["cool_until"] and dd >= DD_HALT:
        rs["cool_until"] = now + DD_COOLDOWN_S
    reasons, mult, allow = [], 1.0, True
    if rs["banked"]:
        allow = False
        reasons.append(f"banked: equity >= {BANK_MULT:g}x the cohort start (no entries until the cohort ends)")
    if rs["halted"]:
        allow = False
        reasons.append(f"halted: equity <= {HALT_MULT:g}x the cohort start (no entries until the cohort ends)")
    if rs["cool_until"]:
        allow = False
        reasons.append(f"drawdown {dd:.0%} from the peak: no new entries until the 24 h cooldown ends")
    if eq <= rs["day_eq"] * (1 - DAILY_LOSS_HALT):
        allow = False
        reasons.append(f"lost {DAILY_LOSS_HALT:.0%} today: no new entries until the next UTC day")
    if dd >= DD_HALF:
        mult *= 0.5
        reasons.append(f"drawdown {dd:.0%} from the peak: half size")
    if rs["streak"] >= STREAK_HALF:
        mult *= 0.5
        reasons.append(f"{rs['streak']} losing trades in a row: half size until a win")
    return {"allow": allow, "mult": mult, "reasons": reasons, "drawdown_pct": round(dd * 100, 2),
            "cohort_x": round(eq / rs["cohort_eq"], 3) if rs["cohort_eq"] else None, "banked": rs["banked"],
            "halted": rs["halted"]}


def risk_trade_closed(rs: dict, pnl: float):
    """Feed one closed model trade (P&L in account currency) into the loss streak."""
    if pnl < 0:
        rs["streak"] += 1
        rs["last_loss"] = True
    else:
        rs["streak"], rs["last_loss"] = 0, False


def note_entry(rs: dict, size_pct: float, now: float):
    if rs["entries_day"] != _utc_day(now):
        rs.update(entries_day=_utc_day(now), entries_n=0)
    rs["entries_n"] += 1
    rs["last_size_pct"] = size_pct


def entries_today(rs: dict, now: float) -> int:
    return rs["entries_n"] if rs["entries_day"] == _utc_day(now) else 0


# ------------------------------------------------------------------ the gate
def gate(d: dict, *, news_type, forced: bool, rs: dict, eq: float, now: float, n_open: int, extra_entries: int = 0,
         is_add: bool = False) -> dict:
    """Apply the frozen v4.19 rules to one buy/short decision. Returns {veto, rules, size_pct, leverage, max_hold_s,
    review_in_min, notes}. `veto` is a string (rule id and reason) or None. Never raises a size or leverage."""
    out = {"veto": None, "rules": [], "notes": [], "size_pct": d["size_pct"], "leverage": d["leverage"],
           "max_hold_s": FORCED_HOLD_S if forced else MAX_HOLD_S,
           "review_in_min": min(int(d.get("review_in_min") or REVIEW_MAX_MIN), REVIEW_MAX_MIN)}
    st = risk_status(rs, eq, now)
    if not st["allow"]:
        out["veto"] = "R7 " + "; ".join(r for r in st["reasons"] if "half size" not in r)
        return out
    if news_type in NEWS_TYPE_ABSTAIN and not forced:
        out["veto"] = f"R1 news type {news_type!r}: abstain"
        return out
    em = d.get("expected_move_pct")
    if em is not None and em < MIN_EXPECTED_MOVE_PCT:
        out["veto"] = f"R8 expected move {em:g}% is under {MIN_EXPECTED_MOVE_PCT:g}%"
        return out
    if not is_add and n_open >= MAX_POS:
        out["veto"] = f"R5 {n_open} positions open (max {MAX_POS})"
        return out
    if not is_add and entries_today(rs, now) + extra_entries >= MAX_ENTRIES_DAY:
        out["veto"] = f"R5 {MAX_ENTRIES_DAY} entries already today"
        return out
    size = float(d["size_pct"]) * st["mult"]
    if st["mult"] < 1:
        out["rules"].append("R7")
        out["notes"] += [r for r in st["reasons"] if "half size" in r]
    if d["action"] == "buy" and not forced:
        size *= 0.5
        out["rules"].append("R2")
    if rs.get("last_loss") and rs.get("last_size_pct"):
        if size > rs["last_size_pct"]:
            size = rs["last_size_pct"]                    # no martingale: never larger than the size that just lost
            out["rules"].append("R6")
    if size > SIZE_CAP_PCT:
        size = SIZE_CAP_PCT
        out["rules"].append("R5")
    lev = min(float(d["leverage"]), LEV_CAP)
    if lev < d["leverage"]:
        out["rules"].append("R5")
    out["rules"].append("R3")                         # every accepted entry carries the time exit
    out.update(size_pct=round(size, 4), leverage=lev)
    out["rules"] = sorted(set(out["rules"]))
    return out


def may_add(side: int, entry: float, mark: float) -> bool:
    """Adding to a position is allowed only while it is in profit (no averaging down)."""
    return side * (mark / entry - 1.0) > 0 if entry else False


# ------------------------------------------------------------------ input blocks (pure builders)
EVIDENCE_FAST_NEWS = ("context only: an LLM reading public news for direction had no edge in three rounds (research/"
                      "news_train/PLAYBOOK.md); speed helps only where flow is forced")
# Base rates of the forced-flow families, from research/studies/RESULTS.md (frozen 2026-11-25 events; in-sample on the screens
# that picked the 4 h hold, so only forward books confirm). Short = the coin is expected to fall.
FLOW_BASE_RATES = [
    "L1f binance delist short 4h: n=105 +14.5% spot-priced (in-sample); perp-reachable subset +4.7% (train -3.3, validation "
    "+13.9, test +6.4), about 1.9 events a month",
    "fut_delist short 4h: n=59 +6.2% (train n only 6), about 1.7 a month",
    "mon_tag (monitoring tag) short 4h: n=89 +2.7%, positive in every split but small",
    "bybit_delist short 4h n=74 -1.1% and okx_delist n=17 -0.5%: negative; Korean notices do not move the global perp",
]
FLOW_RECENT_OOS = ("NEGATIVE out of sample: the delisting short lost 1.8% per trade over 48 trades at 1 d (sealed Aug-Nov 2026, "
                   "news_train v4, PLAYBOOK rule 1): a regime, not a law")


def fast_news_block(rows: list, now: float, source_health: dict, max_items: int = 6, window_s: int = 1800) -> dict:
    """rows: classified fast-ingest items [{source, title, t_pub, t_seen, lat_s, cls, coins}], newest last.
    source_health: {source: {"last_ok_age_s", "median_s", "n"}} from news_ingest.view()."""
    fresh = [r for r in rows if now - r["t_seen"] <= window_s]
    fresh.sort(key=lambda r: r["t_seen"], reverse=True)
    items = [{"src": r["source"], "t_pub": r.get("t_pub"), "age_s": round(now - r["t_seen"]), "latency_s": r.get("lat_s"),
              "title": (r.get("title") or "")[:110], **({"flow": r["cls"], "coins": r["coins"][:4]} if r.get("cls") else {})}
             for r in fresh[:max_items]]
    return {"evidence": EVIDENCE_FAST_NEWS, "window_min": window_s // 60, "items": items,
            "source_latency_median_s": {s: h.get("median_s") for s, h in source_health.items() if h.get("median_s") is not None}}


def feed_health(source_health: dict, ledgers: dict, now: float, max_source_age_s: float = 300.0) -> dict:
    """Which inputs are stale. A source is stale when its last successful poll is older than max_source_age_s (or never);
    a ledger when its newest update is older than its own limit. Returns {name: {"age_s", "stale"}} plus a 'stale' list."""
    out, stale = {}, []
    for s, h in sorted(source_health.items()):
        age = h.get("last_ok_age_s")
        bad = age is None or age > max_source_age_s
        out[s] = {"age_s": age, "stale": bad}
        if bad:
            stale.append(s)
    for name, led in sorted(ledgers.items()):
        age = None if led.get("ts") is None else round(now - led["ts"])
        bad = age is None or age > led.get("max_age_s", 6 * 3600)
        out["ledger:" + name] = {"age_s": age, "stale": bad}
        if bad:
            stale.append("ledger:" + name)
    return {"feeds": out, "stale": stale}
