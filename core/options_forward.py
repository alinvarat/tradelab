"""Pure pieces of the forward options test (research/studies/protocol_llm_options_forward.md).

The runner (research/studies/options_forward.py) does the network work on GitHub Actions; everything that decides
a contract, a session count, a return or an account path lives here and is tested offline.
"""
import calendar
import html
import random
import re
import time

from . import news_backtest as nb

MIN_DAYS = 7          # nearest expiry at least this many calendar days away
OTM = 0.05            # call strike >= spot*1.05, put strike <= spot*0.95
HOLD_SESSIONS = 5
FEE = 0.65            # USD per contract per side
STAKE = 0.20          # share of equity per new trade
START_USD = 147.0
MIN_TRADES = 150


def parse_current_atom(text: str) -> list:
    """SEC 'getcurrent' Atom feed -> [{'accession','cik','items','updated'}] (updated = UTC seconds)."""
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", text, re.S):
        acc = re.search(r"accession-number=([0-9-]+)", entry)
        cik = re.search(r"\((\d{4,10})\)\s*\(", entry)
        upd = re.search(r"<updated>([^<]+)</updated>", entry)
        if not (acc and cik and upd):
            continue
        summary = html.unescape(re.search(r"<summary[^>]*>(.*?)</summary>", entry, re.S).group(1)) \
            if "<summary" in entry else ""
        items = re.findall(r"Item (\d+\.\d+)", summary)
        link = re.search(r'href="([^"]+-index\.htm)"', entry)
        out.append({"accession": acc.group(1), "cik": int(cik.group(1)), "items": items,
                    "updated": iso_to_ts(upd.group(1)), "index_url": link.group(1) if link else None})
    return out


def iso_to_ts(s: str) -> int:
    """'2026-11-23T17:29:14-05:00' -> UTC seconds."""
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([+-]\d{2}):?(\d{2})?", s.strip())
    if not m:
        raise ValueError(s)
    base = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S"))
    sign = 1 if m.group(2)[0] == "+" else -1
    offset = sign * (abs(int(m.group(2))) * 3600 + int(m.group(3) or 0) * 60)
    return base - offset


def choose_expiry(expiries: list, now_ts: int, min_days: int = MIN_DAYS):
    """Nearest expiry (UTC seconds) at least min_days calendar days after now."""
    ok = sorted(e for e in expiries if e >= now_ts + min_days * 86400)
    return ok[0] if ok else None


def pick_contract(chain: dict, spot: float, direction: str, otm: float = OTM):
    """chain: {'calls': [...], 'puts': [...]} (Yahoo shape). Long -> lowest call strike >= spot*(1+otm);
    short -> highest put strike <= spot*(1-otm). None when no strike qualifies."""
    if direction == "long":
        c = [x for x in chain.get("calls", []) if x.get("strike", 0) >= spot * (1 + otm)]
        return min(c, key=lambda x: x["strike"]) if c else None
    if direction == "short":
        p = [x for x in chain.get("puts", []) if x.get("strike", 1e18) <= spot * (1 - otm)]
        return max(p, key=lambda x: x["strike"]) if p else None
    return None


def opposite(direction: str) -> str:
    return {"long": "short", "short": "long"}.get(direction, "skip")


def random_direction(symbol: str, accession: str) -> str:
    return random.Random(f"dir:{symbol}:{accession}").choice(("long", "short"))


def intrinsic(direction: str, strike: float, spot: float) -> float:
    return max(0.0, spot - strike) if direction == "long" else max(0.0, strike - spot)


def trade_return(entry_ask: float, exit_bid: float, fee: float = FEE, haircut: float = 0.0) -> float:
    """One contract: pay ask*100 + fee, receive bid*100*(1-haircut) - fee."""
    cost = entry_ask * 100 + fee
    got = max(0.0, (exit_bid or 0.0) * 100 * (1 - haircut) - fee)
    return got / cost - 1


def sessions_after(session_dates: list, entry_date: str) -> int:
    return sum(1 for d in session_dates if d > entry_date)


def simulate_account(trades: list, start: float = START_USD, stake: float = STAKE, whole_contracts: bool = True):
    """trades: closed, each {'entry_ts','exit_ts','entry_ask','exit_bid'}. Events in time order; each entry stakes
    stake*equity (capped at cash). whole_contracts: buy floor(stake/(ask*100+fee)) contracts, skip if 0."""
    events = sorted([(t["entry_ts"], 0, i) for i, t in enumerate(trades)] +
                    [(t["exit_ts"], 1, i) for i, t in enumerate(trades)])
    cash, held, count, curve, taken, unaffordable = start, {}, {}, [], 0, 0
    for ts, kind, i in events:
        t = trades[i]
        unit = t["entry_ask"] * 100 + FEE
        if kind == 0:
            equity = cash + sum(held.values())
            budget = min(cash, stake * equity)
            n = int(budget // unit) if whole_contracts else budget / unit
            if n <= 0:
                unaffordable += 1
                continue
            cash -= n * unit
            held[i] = n * unit
            count[i] = n
            taken += 1
        elif i in held:
            n = count[i]
            cash += max(0.0, (t["exit_bid"] or 0.0) * 100 - FEE) * n
            held.pop(i)
            curve.append((ts, cash + sum(held.values())))
    months = {}
    for ts, eq in curve:
        months[time.strftime("%Y-%m", time.gmtime(ts))] = eq
    return {"end_equity_usd": cash + sum(held.values()), "taken": taken, "unaffordable": unaffordable,
            "month_end_equity": months, "curve": curve}


def verdict(closed: list) -> dict:
    """Protocol verdict on closed trades: {'symbol','ts','ret','ctrl_ret','ret_haircut'}."""
    import random as _r
    n = len(closed)
    if n < MIN_TRADES:
        return {"verdict": f"collecting ({n}/{MIN_TRADES} closed trades)", "n": n}
    keys = [nb.cluster_key(t) for t in closed]
    rng = _r.Random(20261124)
    ret = [t["ret"] for t in closed]
    diff = [t["ret"] - t["ctrl_ret"] for t in closed]
    hair = [t["ret_haircut"] for t in closed]
    out = {"n": n, "mean_ret": sum(ret) / n, "mean_diff": sum(diff) / n, "mean_ret_haircut": sum(hair) / n,
           "p_ret_block": nb.block_bootstrap_p(ret, keys, rng), "p_diff_block": nb.block_bootstrap_p(diff, keys, rng)}
    ok = (out["mean_ret"] > 0 and out["p_ret_block"] < 0.05 and out["mean_diff"] > 0 and out["p_diff_block"] < 0.05
          and out["mean_ret_haircut"] > 0)
    out["verdict"] = "edge" if ok else "no edge shown"
    return out
