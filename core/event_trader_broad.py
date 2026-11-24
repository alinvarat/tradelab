"""Broad rule trader (protocol research/event_trader/protocol_broad.md, locked 2026-11-24). No AI.

The same universe and per-class shock thresholds the DeepSeek trader sees (217 stocks, ETFs, commodity futures, FX and
crypto). Rule: at the first sight of a shock, trade WITH the move (up -> long, down -> short) at 3x leverage with 10% of
equity as margin, stop 5% against the entry, exit after 20 hours (at the first quote of an open market). A random
non-shock asset of the same class gets the same side, size and rules at the same moment (control)."""
import time
from pathlib import Path

from . import data
from .engine import Account
from .event_trader import EventTrader, _day
from .universe import ALL, SHOCK_PCT, asset_class

DATA = Path(__file__).resolve().parent.parent / "data"
STATE = DATA / "event_trader_broad.json"
LOG = DATA / "event_trader_broad_log.jsonl"
PROTOCOL = "broad-v1"
LEVERAGE, MARGIN, STOP, MAX_POS, HOLD_S = 3.0, 0.10, 0.05, 5, 20 * 3600
VOL_MIN, STALE_S = 0.5, 1800
VOLUME_CLASSES = ("stock", "etf")       # volume confirmation only where exchange volume is meaningful
SCAN_S = 30


class BroadEventTrader(EventTrader):
    def __init__(self, state_path=STATE, log_path=LOG, rng_seed=None):
        super().__init__(state_path, log_path, rng_seed)
        self.tickers = list(ALL)

    def _new_account(self, usd):
        return Account(balance=usd, leverage=LEVERAGE, fee_rate=0.0005, slippage=0.0002, allow_short=True)

    def risk_ok(self, now):
        if self.paused:
            return False, "paused"
        if len(self.acct.positions) + sum(1 for o in self.acct.orders if o.status == "pending") >= MAX_POS:
            return False, "max positions"
        return True, ""

    def is_shock(self, q, now):
        if not q or q.get("price") is None or not q.get("prev_close") or not q.get("open"):
            return False, None
        cls = asset_class(q["symbol"])
        if now - (q.get("ts") or 0) > STALE_S or abs(q.get("change_pct") or 0) < SHOCK_PCT[cls]:
            return False, None
        if cls not in VOLUME_CLASSES:
            return True, None
        avg = self.avg50(q["symbol"])
        ratio = (q.get("volume") or 0) / avg if avg else None
        return (ratio is not None and ratio >= VOL_MIN), ratio

    def _open(self, acct, q, side):
        margin = min(acct.equity() * MARGIN, acct.free_margin() * 0.99)
        if margin < 1:
            return None
        px = q["ask"] if side > 0 else q["bid"]
        stop = px * (1 - STOP) if side > 0 else px * (1 + STOP)
        o = acct.place(q["symbol"], side, margin * LEVERAGE / px, "market", None, stop, None)
        acct.on_quote(self._quote(q))
        return {"order": o.status, "margin_usd": round(margin, 2), "notional_usd": round(margin * LEVERAGE, 2),
                "side": "long" if side > 0 else "short", "px": px}

    def _new_event(self, q, ratio, quotes, now):
        side = 1 if q["change_pct"] > 0 else -1
        cls = asset_class(q["symbol"])
        ev = {"id": f"{_day(now)}-{q['symbol']}", "ts": now, "symbol": q["symbol"], "class": cls, "price": q["price"],
              "move_pct": round(q["change_pct"], 2), "vol_ratio": round(ratio, 2) if ratio else None,
              "direction": "up" if side > 0 else "down", "protocol": PROTOCOL, "out": {}, "entry": None, "control": None}
        ok, why = self.risk_ok(now)
        if ok:
            ev["entry"] = self._open(self.acct, q, side)
            pool = [s for s, x in quotes.items() if s != q["symbol"] and asset_class(s) == cls and x.get("open")
                    and abs(x.get("change_pct") or 0) < SHOCK_PCT[cls] and now - (x.get("ts") or 0) <= STALE_S]
            if pool and ev["entry"]:
                cs = self.rng.choice(sorted(pool))
                ev["control"] = {"symbol": cs, **(self._open(self.ctrl, quotes[cs], side) or {})}
        else:
            ev["skipped"] = why
        self.events.append(ev)
        self.record("event", **{k: v for k, v in ev.items() if k != "out"})

    def _exits(self, now, quotes):
        for acct in (self.acct, self.ctrl):
            for s, p in list(acct.positions.items()):
                if now - p.opened_ts >= HOLD_S and s in quotes and quotes[s].get("open"):
                    acct.close(s, reason="time exit")

    def _book_trades(self):
        done = {p["id"] for p in self.pairs}
        for ev in self.events:
            if ev["id"] in done or not ev.get("entry") or not ev.get("control"):
                continue

            def closed(acct, sym):
                for t in acct.trades:
                    if t.symbol == sym and t.opened_ts >= ev["ts"] - 5:
                        return t.pnl / (t.qty * t.entry) * LEVERAGE       # return on margin
                return None
            a, c = closed(self.acct, ev["symbol"]), closed(self.ctrl, ev["control"]["symbol"])
            if a is not None and c is not None:
                self.pairs.append({"id": ev["id"], "s1": a, "ctrl": c, "booked_ts": time.time()})
                self.record("pair", id=ev["id"], s1=a, ctrl=c)

    def _position_view(self, s, p):
        last = self.acct.last.get(s)
        mark = (last.bid if p.side > 0 else last.ask) if last else p.entry
        ev = next((x for x in reversed(self.events) if x["symbol"] == s and x.get("entry")), None)
        why = f"first sight of a {ev['move_pct']:+.1f}% move ({ev['class']})" if ev else ""
        return {"symbol": s, "side": "long" if p.side > 0 else "short", "qty": p.qty, "entry": p.entry, "mark": mark,
                "pnl_pct": (mark / p.entry - 1) * 100 * p.side,
                "notional_usd": p.qty * mark, "stop": p.sl, "opened_ts": p.opened_ts, "exit_at": p.opened_ts + HOLD_S,
                "why": why, "control": None}

    def view(self):
        v = super().view()
        v["protocol"] = PROTOCOL
        v["scan_every_s"] = SCAN_S
        v["universe_size"] = len(self.tickers)
        v["rules"] = {"shock": "first sight of a move vs previous close >= the class threshold (stock 5%, ETF 3%, "
                               "commodity 2%, FX 1%, crypto 5%); stocks and ETFs also need day volume >= 0.5x the 50-day average",
                      "trade": f"trade with the move (up long, down short), {MARGIN * 100:.0f}% of equity as margin at "
                               f"{LEVERAGE:.0f}x, stop {STOP * 100:.0f}% against entry, exit after {HOLD_S // 3600} h, "
                               f"max {MAX_POS} open; control = random non-shock asset of the same class, same side and rules"}
        return v


def loop(t: BroadEventTrader, every=SCAN_S):
    while True:
        try:
            t.scan()
            t.save()
            t.last_error = None
        except Exception as e:  # noqa: BLE001
            t.last_error = str(e)[:200]
            t.record("error", message=t.last_error)
        time.sleep(every)
