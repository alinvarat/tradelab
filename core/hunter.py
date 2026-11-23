"""Hunter: paper account that chases the owner's 6x-a-month target with leveraged crypto trend following.
Evidence (research/hunter.py, test 2023-2026, intraday lows, funding and fees): at 20x, 6x months 9-11%,
ruin months 43-51%; at 10x, 6x 0-4%, ruin 9-19%. This is a measured gamble, kept beside the main auto trader
so results can be compared month by month. Simulated money only.

Rule: each coin long when its daily close > SMA50 and its 30-day return > 0 (completed daily bars), equal split,
leverage LEV. Funding 0.01% per 8h is charged daily on notional. If month equity reaches 6x the month-start
equity, everything is closed and the account waits for the next month. Engine stop-out closes positions when
equity falls under half of the used margin (exchange-style liquidation)."""
import json
import os
import threading
import time
from pathlib import Path

from . import data, indicators as ind
from .engine import Account, Quote

STATE = Path(__file__).resolve().parent.parent / "data" / "hunter.json"
COINS = ["BTC-USD", "ETH-USD", "SOL-USD"]
LEV, FAST, MOM, TARGET = 20.0, 50, 30, 6.0
FEE_PCT, FUND_DAY = 0.05, 0.0003
CAPITAL_THB = 5000.0


class Hunter:
    def __init__(self):
        self.lock = threading.RLock()
        self.log, self.months = [], []
        self.month, self.month_start, self.done_month, self.last_day = "", None, "", ""
        self.acct, self.capital_usd = None, None
        if STATE.exists():
            d = json.loads(STATE.read_text())
            self.acct = Account.from_dict(d["account"])
            for k in ("log", "months", "month", "month_start", "done_month", "last_day", "capital_usd"):
                setattr(self, k, d.get(k, getattr(self, k)))
        else:
            self.reset()

    def reset(self):
        rate = data.fx_to_usd("THB")
        self.capital_usd = round(CAPITAL_THB * rate, 2)
        self.acct = Account(balance=self.capital_usd, leverage=LEV, fee_rate=FEE_PCT / 100, slippage=0.0002,
                            stop_out_level=0.5, allow_short=False)
        self.log, self.months, self.month, self.month_start, self.done_month, self.last_day = [], [], "", None, "", ""
        self.note(f"Hunter opened with {CAPITAL_THB:,.0f} THB = {self.capital_usd:.2f} USD, leverage {LEV:.0f}x.")

    def note(self, t):
        self.log.append({"ts": time.time(), "text": t})

    def save(self):
        with self.lock:
            d = {"account": self.acct.to_dict(), "log": self.log[-500:], "months": self.months, "month": self.month,
                 "month_start": self.month_start, "done_month": self.done_month, "last_day": self.last_day,
                 "capital_usd": self.capital_usd}
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        tmp.replace(STATE)

    def on_quote(self, q: Quote):
        with self.lock:
            n = len(self.acct.trades)
            self.acct.on_quote(q)
            for t in self.acct.trades[n:]:
                self.note(f"{t.symbol}: closed ({t.reason}) {t.pnl:+.2f} USD.")

    def signal(self, sym):
        b = data.chart(sym, "1y", "1d")["bars"]
        done = b if b[-1]["t"] + 86400 <= time.time() else b[:-1]
        c = [x["c"] for x in done]
        sma = ind.sma(c, FAST)[-1]
        return bool(sma and c[-1] > sma and c[-1] / c[-1 - MOM] > 1)

    def cycle(self):
        with self.lock:
            for s in COINS:
                q = data.quote(s)
                self.on_quote(Quote(s, q["bid"], q["ask"], q["ts"] or time.time(), 1.0, True))
            eq = self.acct.equity()
            month, day = time.strftime("%Y-%m", time.gmtime()), time.strftime("%Y-%m-%d", time.gmtime())
            if month != self.month:
                if self.month_start:
                    mult = eq / self.month_start
                    self.months.append({"month": self.month, "multiple": mult, "start": self.month_start, "end": eq})
                    self.note(f"Month {self.month} ended at {mult:.2f}x of its start.")
                self.month, self.month_start = month, eq
            if day != self.last_day and self.acct.positions:  # daily funding on notional
                cost = sum(p.qty * self.acct.last[s].mid * FUND_DAY for s, p in self.acct.positions.items())
                self.acct.balance -= cost
                self.last_day = day
            elif day != self.last_day:
                self.last_day = day
            if eq < self.capital_usd * 0.05:
                if not any("ruined" in x["text"] for x in self.log[-3:]):
                    self.note("Account ruined (under 5% of start). Press Restart to try again.")
                return
            if self.month_start and eq >= TARGET * self.month_start and self.done_month != month:
                for s in list(self.acct.positions):
                    self.acct.close(s, reason="6x target hit")
                self.done_month = month
                self.note(f"6x target reached for {month}: equity {eq:.2f} USD. Flat until next month.")
                return
            if self.done_month == month:
                return
            want = [s for s in COINS if self.signal(s)]
            for s in list(self.acct.positions):
                if s not in want:
                    self.acct.close(s, reason="trend off")
                    self.note(f"{s}: trend off, closed.")
            missing = [s for s in want if s not in self.acct.positions]
            if missing:
                eq = self.acct.equity()
                for s in missing:
                    q = self.acct.last[s]
                    notional = eq * LEV / len(want)
                    o = self.acct.place(s, 1, notional / q.ask * 0.97)
                    self.note(f"{s}: trend on, long {notional:.0f} USD notional at {LEV:.0f}x - {o.status}{' ' + o.note if o.note else ''}.")

    def view(self):
        with self.lock:
            a = self.acct
            rate = data.fx_to_usd("THB")
            eq = a.equity()
            return {"equity_usd": eq, "equity_thb": eq / rate, "capital_thb": CAPITAL_THB, "lev": LEV,
                    "month_start": self.month_start, "month_multiple": eq / self.month_start if self.month_start else None,
                    "positions": [{"symbol": s, "qty": p.qty, "entry": p.entry, "mark": a.last[s].bid if s in a.last else None,
                                   "notional": p.qty * (a.last[s].bid if s in a.last else p.entry)} for s, p in a.positions.items()],
                    "months": self.months[::-1], "log": self.log[::-1][:60], "ruined": eq < self.capital_usd * 0.05,
                    "target_done": self.done_month == time.strftime("%Y-%m", time.gmtime())}


EVERY_S = int(os.environ.get("TRADELAB_HUNTER_EVERY", "15"))


def loop(h: Hunter, every=EVERY_S):
    while True:
        try:
            h.cycle()
            h.save()
        except Exception as e:  # noqa: BLE001
            h.note(f"cycle error: {e}")
        time.sleep(every)
