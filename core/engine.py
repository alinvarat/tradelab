"""Paper-trading account in USD. Fills at bid/ask, SL/TP, margin,
stop-out, with limit/stop orders, add/reduce/flip, partial close, FX conversion and a
closed-market rule: market orders wait for an open market instead of filling at a stale price.
No real orders exist anywhere in this code."""
from dataclasses import dataclass, field, asdict
import itertools
import math
import time


@dataclass
class Quote:
    symbol: str
    bid: float
    ask: float
    ts: float = field(default_factory=time.time)
    fx: float = 1.0          # USD per unit of the instrument's currency
    open: bool = True        # market open and price fresh

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class Position:
    symbol: str
    side: int
    qty: float
    entry: float
    sl: float | None = None
    tp: float | None = None
    opened_ts: float = 0.0
    fees: float = 0.0        # USD fees paid on the open part, not yet booked to a trade
    ref: str | None = None   # caller's reference (e.g. the LLM trader's pair id); copied to the trade on close
    financing: float = 0.0   # cost already deducted from the balance; booked into the trade's P&L at close
    leverage: float | None = None   # margin requirement of this position; None means the account's leverage


@dataclass
class Order:
    id: int
    symbol: str
    side: int                # +1 buy, -1 sell
    qty: float
    type: str = "market"     # market | limit | stop
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    status: str = "pending"  # pending | filled | cancelled | rejected
    created: float = field(default_factory=time.time)
    filled_ts: float | None = None
    fill_px: float | None = None
    note: str = ""
    ref: str | None = None
    leverage: float | None = None


@dataclass
class Trade:
    symbol: str
    side: int
    qty: float
    entry: float
    exit: float
    pnl: float               # USD, net of fees
    fees: float
    reason: str
    opened_ts: float
    closed_ts: float
    ref: str | None = None


class Account:
    def __init__(self, balance=100_000.0, leverage=1.0, fee_rate=0.0005, min_fee=0.0, slippage=0.0002,
                 stop_out_level=0.5, allow_short=True):
        self.initial = self.balance = float(balance)
        self.leverage, self.fee_rate, self.min_fee = float(leverage), float(fee_rate), float(min_fee)
        self.slippage, self.stop_out_level, self.allow_short = float(slippage), stop_out_level, allow_short
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trades: list[Trade] = []
        self.last: dict[str, Quote] = {}
        self.peak_equity, self.max_drawdown = self.balance, 0.0
        self.equity_curve: list[tuple[float, float]] = []
        self._ids = itertools.count(1)

    # ---- valuation -------------------------------------------------------
    def _fx(self, sym):
        q = self.last.get(sym)
        return q.fx if q else 1.0

    def unrealized(self, sym=None) -> float:
        tot = 0.0
        for s, p in self.positions.items():
            if sym and s != sym:
                continue
            q = self.last.get(s)
            if q:
                px = q.bid if p.side > 0 else q.ask
                tot += (px - p.entry) * p.qty * p.side * q.fx
        return tot

    def equity(self) -> float:
        return self.balance + self.unrealized()

    def used_margin(self) -> float:
        return sum(p.entry * p.qty * self._fx(s) / (p.leverage or self.leverage) for s, p in self.positions.items())

    def free_margin(self) -> float:
        return self.equity() - self.used_margin()

    def _fee(self, notional_usd):
        return max(notional_usd * self.fee_rate, self.min_fee) if notional_usd > 0 else 0.0

    # ---- orders ----------------------------------------------------------
    def place(self, symbol, side, qty, type="market", price=None, sl=None, tp=None, ref=None, leverage=None) -> Order:
        o = Order(next(self._ids), symbol, 1 if side > 0 else -1, float(qty), type, price, sl, tp, ref=ref, leverage=leverage)
        finite = all(v is None or math.isfinite(v) for v in (qty, price, sl, tp))
        if not finite or qty <= 0 or type not in ("market", "limit", "stop") or (type != "market" and not price):
            o.status, o.note = "rejected", "invalid quantity, type or price"
        self.orders.append(o)
        if o.status == "pending":
            q = self.last.get(symbol)
            if q:
                self._try_fill(o, q)
            elif type == "market":
                o.note = "waiting for a quote"
        return o

    def cancel(self, oid) -> bool:
        for o in self.orders:
            if o.id == oid and o.status == "pending":
                o.status = "cancelled"
                return True
        return False

    def _try_fill(self, o: Order, q: Quote):
        if not q.open:
            o.note = "market closed: fills at the next open quote"
            return
        if o.type == "market":
            px = q.ask if o.side > 0 else q.bid
        elif o.type == "limit":
            if o.side > 0 and q.ask <= o.price:
                px = min(q.ask, o.price)
            elif o.side < 0 and q.bid >= o.price:
                px = max(q.bid, o.price)
            else:
                return
        else:  # stop
            if o.side > 0 and q.ask >= o.price:
                px = q.ask
            elif o.side < 0 and q.bid <= o.price:
                px = q.bid
            else:
                return
        px *= (1 + o.side * self.slippage) if o.type != "limit" else 1
        err = self._execute(o.symbol, o.side, o.qty, px, q, o.sl, o.tp, ref=o.ref, leverage=o.leverage)
        if err:
            o.status, o.note = "rejected", err
        else:
            o.status, o.fill_px, o.filled_ts, o.note = "filled", px, q.ts, ""

    def _execute(self, sym, side, qty, px, q: Quote, sl=None, tp=None, reason="order", ref=None, leverage=None):
        p = self.positions.get(sym)
        fx = q.fx
        if p and p.side != side:  # reduce, close or flip
            close_qty = min(qty, p.qty)
            self._close_part(sym, close_qty, px, q, reason if reason != "order" else "manual")
            qty -= close_qty
            if qty <= 1e-12:
                return None
            p = None
        if side < 0 and not p and not self.allow_short:
            return "short selling is disabled"
        eff_lev = leverage or (p.leverage if p else None) or self.leverage
        need = px * qty * fx / eff_lev
        fee = self._fee(px * qty * fx)
        if need + fee > self.free_margin() + 1e-9:
            return f"insufficient buying power (need {need + fee:,.2f} USD, free {self.free_margin():,.2f})"
        self.balance -= fee
        if p:  # add to same side
            tot = p.qty + qty
            old_lev = p.leverage or self.leverage
            old_margin = p.entry * p.qty / old_lev
            p.entry = (p.entry * p.qty + px * qty) / tot
            p.qty, p.fees = tot, p.fees + fee
            if leverage is not None:          # effective leverage = total notional / total committed margin
                p.leverage = (p.entry * tot) / (old_margin + px * qty / leverage)
            if sl is not None:
                p.sl = sl
            if tp is not None:
                p.tp = tp
        else:
            self.positions[sym] = Position(sym, side, qty, px, sl, tp, q.ts, fee, ref, leverage=leverage)
        return None

    def _close_part(self, sym, qty, px, q: Quote, reason):
        p = self.positions[sym]
        qty = min(qty, p.qty)
        gross = (px - p.entry) * qty * p.side * q.fx
        fee = self._fee(px * qty * q.fx)
        share = qty / p.qty
        open_fee = p.fees * share
        fin = p.financing * share
        p.financing -= fin
        self.balance += gross - fee
        t = Trade(sym, p.side, qty, p.entry, px, gross - fee - open_fee - fin, fee + open_fee, reason, p.opened_ts, q.ts, p.ref)
        self.trades.append(t)
        p.qty -= qty
        p.fees -= open_fee
        if p.qty <= 1e-12:
            del self.positions[sym]
        return t

    def close(self, sym, qty=None, reason="manual"):
        p, q = self.positions.get(sym), self.last.get(sym)
        if not p or not q:
            return None, "no position or no quote"
        if not q.open:
            return None, "market closed"
        base = q.bid if p.side > 0 else q.ask
        px = base * (1 - p.side * self.slippage)
        return self._close_part(sym, qty or p.qty, px, q, reason), None

    def modify(self, sym, sl=None, tp=None):
        p = self.positions.get(sym)
        if not p:
            return False
        p.sl, p.tp = sl, tp
        return True

    # ---- market updates ----------------------------------------------------
    def on_quote(self, q: Quote) -> list[Trade]:
        self.last[q.symbol] = q
        closed = []
        for o in [o for o in self.orders if o.status == "pending" and o.symbol == q.symbol]:
            self._try_fill(o, q)
        p = self.positions.get(q.symbol)
        if p and q.open:
            px = q.bid if p.side > 0 else q.ask
            if p.sl is not None and ((p.side > 0 and px <= p.sl) or (p.side < 0 and px >= p.sl)):
                closed.append(self.close(q.symbol, reason="stop loss")[0])
            elif p.tp is not None and ((p.side > 0 and px >= p.tp) or (p.side < 0 and px <= p.tp)):
                closed.append(self.close(q.symbol, reason="take profit")[0])
        used = self.used_margin()
        if used > 0 and self.leverage > 1 and self.equity() / used < self.stop_out_level:
            for s in list(self.positions):
                if self.last[s].open:
                    closed.append(self.close(s, reason="stop out")[0])
        eq = self.equity()
        self.peak_equity = max(self.peak_equity, eq)
        self.max_drawdown = max(self.max_drawdown, (self.peak_equity - eq) / self.peak_equity)
        return [t for t in closed if t]

    def snapshot_equity(self, ts=None):
        self.equity_curve.append((ts or time.time(), round(self.equity(), 2)))
        if len(self.equity_curve) > 20000:
            self.equity_curve = self.equity_curve[::2]

    # ---- reporting / persistence -------------------------------------------
    def stats(self) -> dict:
        n = len(self.trades)
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [-t.pnl for t in self.trades if t.pnl <= 0]
        eq = self.equity()
        return {"equity": eq, "balance": self.balance, "unrealized": self.unrealized(),
                "realized": sum(t.pnl for t in self.trades), "fees": sum(t.fees for t in self.trades),
                "used_margin": self.used_margin(), "free_margin": self.free_margin(),
                "return_pct": (eq / self.initial - 1) * 100, "trades": n,
                "win_rate": len(wins) / n * 100 if n else None,
                "avg_win": sum(wins) / len(wins) if wins else None,
                "avg_loss": -sum(losses) / len(losses) if losses else None,
                "profit_factor": sum(wins) / sum(losses) if losses and sum(losses) else None,
                "max_drawdown_pct": self.max_drawdown * 100}

    def settings(self):
        return {"initial": self.initial, "leverage": self.leverage, "fee_rate": self.fee_rate,
                "min_fee": self.min_fee, "slippage": self.slippage, "allow_short": self.allow_short}

    def to_dict(self):
        return {"settings": self.settings(), "balance": self.balance, "peak": self.peak_equity,
                "max_dd": self.max_drawdown, "positions": [asdict(p) for p in self.positions.values()],
                "orders": [asdict(o) for o in self.orders[-500:]], "trades": [asdict(t) for t in self.trades],
                "equity_curve": self.equity_curve, "last": {k: asdict(v) for k, v in self.last.items()}}

    @classmethod
    def from_dict(cls, d):
        s = d["settings"]
        a = cls(balance=s["initial"], leverage=s["leverage"], fee_rate=s["fee_rate"], min_fee=s["min_fee"],
                slippage=s["slippage"], allow_short=s["allow_short"])
        a.balance, a.peak_equity, a.max_drawdown = d["balance"], d["peak"], d["max_dd"]
        a.positions = {p["symbol"]: Position(**p) for p in d["positions"]}
        a.orders = [Order(**o) for o in d["orders"]]
        a.trades = [Trade(**t) for t in d["trades"]]
        a.equity_curve = [tuple(x) for x in d.get("equity_curve", [])]
        a.last = {k: Quote(**v) for k, v in d.get("last", {}).items()}
        a._ids = itertools.count(max([o.id for o in a.orders], default=0) + 1)
        return a
