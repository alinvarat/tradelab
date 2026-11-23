"""Event trader (v2 paper system): reacts to large single-stock moves with attached headlines, keeps a labelled
event dataset, and tests ONE pre-registered rule forward against a same-time random control.
Rules are locked in research/event_trader/protocol.md; do not tune them on data already seen. Simulated money only.

Flow every SCAN_S seconds: quote the 104 large caps -> detect shocks (|move vs previous close| >= UP_PCT with day
volume >= VOL_MIN x its 50-day average) -> log the event with headlines -> if it is an up-shock and the risk guards
allow, open a small paper long in the stock AND a control long in a random non-shock stock at the same moment ->
exit both after HOLD_S (or at the stop) -> record paired returns and price paths at +1h/+4h/+1d/+3d."""
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean

from . import data, news
from .engine import Account, Quote
from .universe import TICKERS

DATA = Path(__file__).resolve().parent.parent / "data"
STATE = DATA / "event_trader.json"
LOG = DATA / "event_trader_log.jsonl"
SCAN_S = int(os.environ.get("TRADELAB_EVENT_EVERY", "60"))
CAPITAL_THB = 5000.0
UP_PCT, VOL_MIN = 5.0, 0.5            # shock definition (locked)
SIZE, MAX_POS, STOP = 0.05, 3, 0.08   # 5% of equity per trade, 3 open at once, 8% stop (locked)
HOLD_S = 20 * 3600                    # exit after 20 hours (locked)
DAILY_HALT = 0.03                     # no new entries after losing 3% in one UTC day
STALE_S = 1800                        # ignore quotes older than 30 minutes
HORIZONS = (3600, 4 * 3600, 24 * 3600, 3 * 24 * 3600)
MIN_TRADES = 30                       # evaluation starts only after this many closed pairs


def _day(ts=None):
    return time.strftime("%Y-%m-%d", time.gmtime(ts or time.time()))


class EventTrader:
    def __init__(self, state_path=STATE, log_path=LOG, rng_seed=None):
        self.state_path, self.log_path = Path(state_path), Path(log_path)
        self.lock = threading.RLock()
        self.rng = random.Random(rng_seed)
        self.pool = ThreadPoolExecutor(10)
        self.avg_vol: dict[str, tuple[float, float]] = {}
        self.last_scan, self.last_error = 0.0, None
        self.context: dict[str, dict] = {}
        self.paused = False
        if self.state_path.exists():
            d = json.loads(self.state_path.read_text())
            self.acct, self.ctrl = Account.from_dict(d["account"]), Account.from_dict(d["ctrl"])
            self.events, self.pairs = d["events"], d["pairs"]
            self.seen, self.day_start, self.capital_usd = set(d["seen"]), d["day_start"], d["capital_usd"]
            self.paused = d.get("paused", False)
        else:
            self.reset()

    # ---------- setup / persistence ----------
    def _new_account(self, usd):
        return Account(balance=usd, leverage=1, fee_rate=0.0005, slippage=0.0002, allow_short=False)

    def reset(self):
        self.capital_usd = round(CAPITAL_THB * data.fx_to_usd("THB"), 2)
        self.acct, self.ctrl = self._new_account(self.capital_usd), self._new_account(self.capital_usd)
        self.events, self.pairs, self.seen = [], [], set()
        self.day_start = {"day": _day(), "equity": self.capital_usd}
        self.paused = False
        self.record("reset", capital_usd=self.capital_usd)

    def record(self, kind, **fields):
        """Append-only audit log; never rewritten."""
        self.log_path.parent.mkdir(exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps({"ts": round(time.time(), 1), "kind": kind, **fields}, default=str) + "\n")

    def save(self):
        with self.lock:
            d = {"account": self.acct.to_dict(), "ctrl": self.ctrl.to_dict(), "events": self.events[-500:],
                 "pairs": self.pairs, "seen": sorted(self.seen)[-5000:], "day_start": self.day_start,
                 "capital_usd": self.capital_usd, "paused": self.paused}
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, default=str))
        tmp.replace(self.state_path)

    # ---------- detection ----------
    def avg50(self, sym):
        cached = self.avg_vol.get(sym)
        if cached and time.time() - cached[1] < 12 * 3600:
            return cached[0]
        bars = data.chart(sym, "6mo", "1d")["bars"]
        vols = [b["v"] for b in bars[-51:-1] if b.get("v")]
        avg = sum(vols) / len(vols) if len(vols) >= 30 else 0.0
        self.avg_vol[sym] = (avg, time.time())
        return avg

    def is_shock(self, q, now):
        """Return (ok, vol_ratio). Fresh quote, open market, big move, normal-or-higher volume so far today."""
        if not q or q.get("price") is None or not q.get("prev_close") or not q.get("open"):
            return False, None
        if now - (q.get("ts") or 0) > STALE_S or abs(q.get("change_pct") or 0) < UP_PCT:
            return False, None
        avg = self.avg50(q["symbol"])
        ratio = (q.get("volume") or 0) / avg if avg else None
        return (ratio is not None and ratio >= VOL_MIN), ratio

    def _quote(self, q, fx=1.0):
        return Quote(q["symbol"], q["bid"], q["ask"], q.get("ts") or time.time(), fx, bool(q.get("open")))

    def risk_ok(self, now):
        eq = self.acct.equity()
        if self.day_start["day"] != _day(now):
            self.day_start = {"day": _day(now), "equity": eq}
        if self.paused:
            return False, "paused"
        if eq < self.day_start["equity"] * (1 - DAILY_HALT):
            return False, "daily loss halt"
        if len(self.acct.positions) + sum(1 for o in self.acct.orders if o.status == "pending") >= MAX_POS:
            return False, "max positions"
        return True, ""

    def _buy(self, acct, q, now):
        usd = min(acct.equity() * SIZE, acct.free_margin() * 0.99)
        if usd < 1:
            return None
        o = acct.place(q["symbol"], 1, usd / q["ask"], "market", None, q["ask"] * (1 - STOP), None)
        acct.on_quote(self._quote(q))
        return {"order": o.status, "usd": round(usd, 2), "ask": q["ask"]}

    # ---------- main step ----------
    def scan(self, quotes=None):
        """One pass over the universe. `quotes` (symbol -> quote dict) may be injected for tests."""
        now = time.time()
        if quotes is None:
            def get(s):
                try:
                    return data.quote(s)
                except Exception:  # noqa: BLE001
                    return None
            quotes = {s: q for s, q in zip(TICKERS, self.pool.map(get, TICKERS)) if q}
            for extra in ("SPY", "^VIX"):  # market context only; never traded, never counted as shocks
                q = get(extra)
                if q:
                    self.context[extra] = q
        with self.lock:
            for s in set(self.acct.positions) | {o.symbol for o in self.acct.orders if o.status == "pending"}:
                if s in quotes:
                    self.acct.on_quote(self._quote(quotes[s]))
            for s in set(self.ctrl.positions) | {o.symbol for o in self.ctrl.orders if o.status == "pending"}:
                if s in quotes:
                    self.ctrl.on_quote(self._quote(quotes[s]))
            self._exits(now, quotes)
            self._outcomes(now, quotes)
            for s, q in quotes.items():
                key = f"{_day(now)}:{s}"
                if key in self.seen:
                    continue
                ok, ratio = self.is_shock(q, now)
                if ok:
                    self.seen.add(key)
                    self._new_event(q, ratio, quotes, now)
            self._book_trades()
            self.acct.snapshot_equity() if not self.acct.equity_curve or now - self.acct.equity_curve[-1][0] >= 900 else None
            self.last_scan = now

    def _new_event(self, q, ratio, quotes, now):
        try:
            heads = [{"title": x["title"], "source": x["source"], "sentiment": x["sentiment"]}
                     for x in news.symbol_news(q["symbol"], q.get("name") or "")["items"][:3]]
        except Exception:  # noqa: BLE001
            heads = []
        spy, vix = self.context.get("SPY"), self.context.get("^VIX")
        spy_move = round(spy["change_pct"], 2) if spy and spy.get("change_pct") is not None else None
        same_day = sum(1 for k in self.seen if k.startswith(_day(now)))
        ev = {"id": f"{_day(now)}-{q['symbol']}", "ts": now, "symbol": q["symbol"], "price": q["price"],
              "spy_price": spy["price"] if spy else None, "spy_move_pct": spy_move,
              "abnormal_move_pct": round(q["change_pct"] - spy_move, 2) if spy_move is not None else None,
              "vix": vix["price"] if vix else None, "shocks_today": same_day,
              "move_pct": round(q["change_pct"], 2), "vol_ratio": round(ratio, 2), "headlines": heads,
              "direction": "up" if q["change_pct"] > 0 else "down", "out": {}, "entry": None, "control": None}
        if ev["direction"] == "up":
            ok, why = self.risk_ok(now)
            if ok:
                ev["entry"] = self._buy(self.acct, q, now)
                pool = [s for s in quotes if s != q["symbol"] and abs(quotes[s].get("change_pct") or 0) < UP_PCT
                        and quotes[s].get("open") and now - (quotes[s].get("ts") or 0) <= STALE_S]
                if pool and ev["entry"]:
                    cs = self.rng.choice(sorted(pool))
                    ev["control"] = {"symbol": cs, **(self._buy(self.ctrl, quotes[cs], now) or {})}
            else:
                ev["skipped"] = why
        self.events.append(ev)
        self.record("event", **{k: v for k, v in ev.items() if k != "out"})

    def _exits(self, now, quotes):
        for acct in (self.acct, self.ctrl):
            for s, p in list(acct.positions.items()):
                if now - p.opened_ts >= HOLD_S and s in quotes and quotes[s].get("open"):
                    acct.close(s, reason="time exit")

    def _outcomes(self, now, quotes):
        for ev in self.events[-200:]:
            q = quotes.get(ev["symbol"])
            if not q or not q.get("price"):
                continue
            for h in HORIZONS:
                if str(h) not in ev["out"] and now - ev["ts"] >= h and now - ev["ts"] < h + 3 * SCAN_S + 3600:
                    ev["out"][str(h)] = round(q["price"] / ev["price"] - 1, 5)
                    spy = self.context.get("SPY")
                    rel = None
                    if spy and spy.get("price") and ev.get("spy_price"):
                        rel = round(ev["out"][str(h)] - (spy["price"] / ev["spy_price"] - 1), 5)
                        ev.setdefault("out_vs_spy", {})[str(h)] = rel
                    self.record("outcome", id=ev["id"], horizon_s=h, ret=ev["out"][str(h)], vs_spy=rel)

    def _book_trades(self):
        done = {p["id"] for p in self.pairs}
        for ev in self.events:
            if ev["id"] in done or not ev.get("entry") or not ev.get("control"):
                continue

            def closed(acct, sym):
                for t in acct.trades:
                    if t.symbol == sym and t.opened_ts >= ev["ts"] - 5:
                        return t.pnl / (t.qty * t.entry)
                return None
            a, c = closed(self.acct, ev["symbol"]), closed(self.ctrl, ev["control"]["symbol"])
            if a is not None and c is not None:
                self.pairs.append({"id": ev["id"], "s1": a, "ctrl": c})
                self.record("pair", id=ev["id"], s1=a, ctrl=c)

    # ---------- evaluation (locked criterion) ----------
    def evaluate(self):
        p = self.pairs
        out = {"closed_pairs": len(p), "needed": MIN_TRADES}
        if len(p) < MIN_TRADES:
            out["verdict"] = f"too early ({len(p)}/{MIN_TRADES} closed pairs): no conclusion allowed"
            return out
        diff = [x["s1"] - x["ctrl"] for x in p]
        rng = random.Random(20261123)
        boots = [mean(rng.choice(diff) for _ in diff) for _ in range(2000)]
        pval = sum(b <= 0 for b in boots) / len(boots)
        out |= {"mean_s1": mean(x["s1"] for x in p), "mean_ctrl": mean(x["ctrl"] for x in p),
                "mean_diff": mean(diff), "p_diff_le_0": pval}
        edge = out["mean_s1"] > 0 and out["mean_diff"] > 0 and pval < 0.10
        out["verdict"] = "edge candidate (needs a second locked window)" if edge else "no edge shown"
        return out

    def view(self):
        with self.lock:
            a = self.acct
            ups = [e for e in self.events if e["direction"] == "up"]
            hz = {str(h): [e["out"][str(h)] for e in ups if str(h) in e["out"]] for h in HORIZONS}
            return {"equity_usd": a.equity(), "equity_thb": a.equity() / data.fx_to_usd("THB"),
                    "control_equity_usd": self.ctrl.equity(), "capital_usd": self.capital_usd, "paused": self.paused,
                    "last_scan_age_s": round(time.time() - self.last_scan) if self.last_scan else None,
                    "scan_every_s": SCAN_S, "error": self.last_error,
                    "positions": [{"symbol": s, "qty": p.qty, "entry": p.entry,
                                   "mark": a.last[s].bid if s in a.last else None} for s, p in a.positions.items()],
                    "events": self.events[::-1][:40], "n_events": len(self.events), "n_up": len(ups),
                    "up_mean_move": {k: (mean(v) if v else None, len(v)) for k, v in hz.items()},
                    "evaluation": self.evaluate(),
                    "rules": {"shock": f"move >= {UP_PCT}% vs previous close, day volume >= {VOL_MIN}x 50-day average",
                              "trade": f"long {SIZE * 100:.0f}% of equity at first sight of an UP shock, hold {HOLD_S // 3600} h, "
                                       f"stop {STOP * 100:.0f}%, max {MAX_POS} open; control = random non-shock stock, same time and rules"}}


def loop(t: EventTrader, every=SCAN_S):
    while True:
        try:
            t.scan()
            t.save()
            t.last_error = None
        except Exception as e:  # noqa: BLE001
            t.last_error = str(e)[:200]
            t.record("error", message=t.last_error)
        time.sleep(every)
