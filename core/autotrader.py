"""Paper auto-trader: dual-momentum portfolio that re-learns its settings and reviews its losing months.

Why this method: in research/run_research.py and research/robust.py (adjusted daily prices since 2004, 0.10% cost
per side), top-k dual momentum over 9 ETFs plus BTC was the strongest method on the unseen 2017-2026 test, stayed
ahead of SPY in 2022-2026, kept profits at triple costs and all neighbouring settings were profitable.
It still had losing years of -8% to -34%; nothing here guarantees profit.

Learning loop (daily):
 1. Walk-forward: 24 settings (lookback x top-k x SMA200 guard x inverse-volatility weights) run on all history.
    Settings are ranked on the train window (start to three years ago) only; the last three years validate.
 2. Mistake review: the chosen setting's losing months are examined. Each loss is attributed to the assets held
    and to the condition at the rebalance (asset below its 200-day average, asset in a volatility spike).
    Live losing months are added. If a condition explains losses, the matching fix (guard or inverse-vol) is tested
    and adopted only if it improves the train result. Every finding goes to the lessons log.
 3. The portfolio trades only if the chosen setting also made money in the validation years.
Rebalances once a month. Simulated money only; no broker connection exists."""
import json
import os
import threading
import time
from pathlib import Path

from . import data, research as R
from .engine import Account, Quote

STATE = Path(__file__).resolve().parent.parent / "data" / "auto.json"
UNIVERSE = ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "BTC-USD"]
NAMES = {"SPY": "US large caps", "QQQ": "Nasdaq 100", "EFA": "Developed ex-US", "EEM": "Emerging markets",
         "TLT": "Long Treasuries", "IEF": "7-10y Treasuries", "GLD": "Gold", "DBC": "Commodities",
         "VNQ": "US real estate", "BTC-USD": "Bitcoin"}
GRID = [{"lookback": lb, "top": k, "guard": g, "invvol": v}
        for lb in (63, 126, 252) for k in (2, 3) for g in (False, True) for v in (False, True)]
FEE_PCT, SLIP_PCT = 0.10, 0.05
CAPITAL_THB = 5000.0
VALID_YEARS = 3
RELEARN_S = 24 * 3600
EVERY_S = int(os.environ.get("TRADELAB_AUTO_EVERY", "15"))  # how often the trader checks quotes, orders and the drawdown guard
SNAPSHOT_S = 900  # equity-curve resolution (keeps the chart's 2000 points ~3 weeks long)
TOL = 0.05  # rebalance tolerance as a share of equity


def _label(p):
    return (f"top {p['top']} by {p['lookback']}-day return" + (", SMA200 guard" if p["guard"] else "")
            + (", inverse-volatility weights" if p["invvol"] else ", equal weights"))


class AutoTrader:
    def __init__(self):
        self.lock = threading.RLock()
        self.cycle_lock = threading.Lock()
        self.model: dict = {}
        self.grid: list = []
        self.lessons: list = []
        self.log: list = []
        self.months: list = []          # live monthly results
        self.rebalanced: str = ""       # YYYY-MM of the last completed rebalance
        self.targets: dict = {}
        self.entry_tags: dict = {}
        self.month_start_eq = None
        self.month_hold: dict = {}
        self.paused = False
        self.learning = False
        self.capital_usd = None
        self.acct = None
        self.load()

    # ---------- persistence ----------
    KEYS = ("model", "grid", "lessons", "log", "months", "rebalanced", "targets", "entry_tags", "month_start_eq",
            "month_hold", "paused", "capital_usd")

    def load(self):
        if STATE.exists():
            d = json.loads(STATE.read_text())
            if d.get("version") == 2:
                self.acct = Account.from_dict(d["account"])
                for k in self.KEYS:
                    if k in d:
                        setattr(self, k, d[k])
                return
        self.reset()

    def save(self):
        with self.lock:
            d = {"version": 2, "account": self.acct.to_dict(), **{k: getattr(self, k) for k in self.KEYS}}
            d["lessons"], d["log"] = self.lessons[-400:], self.log[-600:]
        tmp = STATE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, default=str))
        tmp.replace(STATE)

    def reset(self):
        rate = data.fx_to_usd("THB")
        self.capital_usd = round(CAPITAL_THB * rate, 2)
        self.acct = Account(balance=self.capital_usd, leverage=1, fee_rate=FEE_PCT / 100, slippage=SLIP_PCT / 100,
                            allow_short=False)
        self.model, self.grid, self.lessons, self.log, self.months = {}, [], [], [], []
        self.rebalanced, self.targets, self.entry_tags, self.month_start_eq, self.month_hold = "", {}, {}, None, {}
        self.paused = False
        self.note(f"Account opened with {CAPITAL_THB:,.0f} THB = {self.capital_usd:,.2f} USD at {rate:.5f}.")

    def note(self, text, lesson=False):
        (self.lessons if lesson else self.log).append({"ts": time.time(), "text": text})

    # ---------- learning ----------
    def learn(self):
        self.learning = True
        try:
            days, px = R.panel(UNIVERSE + ["SHY"], "2004-01-01")
            a = next(i for i, d in enumerate(days) if d >= "2006-01-01")
            cut = f"{int(days[-1][:4]) - VALID_YEARS}{days[-1][4:]}"
            split = max(i for i, d in enumerate(days) if d <= cut)
            end = len(days) - 1
            spy_curve, _ = R.run(days, px, R.make_rule("buy_hold", days, px, UNIVERSE, {"asset": "SPY"}))
            spy_val = R.stats(days, spy_curve, split, end)
            cost = (FEE_PCT + SLIP_PCT) / 100
            rows = []
            for p in GRID:
                curve, _ = R.run(days, px, R.make_rule("dual_mom", days, px, UNIVERSE, p), cost=cost)
                rows.append({"p": p, "train": R.stats(days, curve, a, split), "valid": R.stats(days, curve, split, end)})
            rows.sort(key=lambda r: -r["train"]["sharpe"])
            base = max((r for r in rows if not r["p"]["guard"] and not r["p"]["invvol"]), key=lambda r: r["train"]["sharpe"])
            chosen = self.review(days, px, a, split, base, rows)
            live = chosen["valid"]["cagr"] > 0
            self.grid = [{"label": _label(r["p"]), "p": r["p"], "train": r["train"], "valid": r["valid"]} for r in rows]
            prev = self.model.get("p")
            self.model = {"p": chosen["p"], "label": _label(chosen["p"]), "train": chosen["train"],
                          "valid": chosen["valid"], "spy_valid": spy_val, "status": "live" if live else "cash",
                          "ts": time.time(), "train_span": f"{days[a]} to {days[split]}",
                          "valid_span": f"{days[split]} to {days[end]}", "settings_tested": len(GRID)}
            if prev != chosen["p"]:
                self.note(f"Model set to {_label(chosen['p'])}: train {chosen['train']['cagr']:+.1f}%/year, validation "
                          f"{chosen['valid']['cagr']:+.1f}%/year with max drawdown {chosen['valid']['mdd']:.0f}% "
                          f"(SPY {spy_val['cagr']:+.1f}%/year, drawdown {spy_val['mdd']:.0f}%). "
                          + ("Trading it." if live else "Not trading: it lost money in the validation years."), True)
        except Exception as e:  # noqa: BLE001
            self.note(f"Learning failed: {e}")
        finally:
            self.learning = False

    def review(self, days, px, a, split, base, rows):
        """Attribute losing months to holdings and conditions; adopt a fix only if it improves the train result."""
        p = base["p"]
        me = sorted(R.month_ends(days))
        tally = {"below_sma200": [0, 0.0], "vol_spike": [0, 0.0]}
        by_asset = {}
        smas = {s: R._sma_none(px[s], 200) for s in UNIVERSE}
        for j in range(1, len(me)):
            i0, i1 = me[j - 1], me[j]
            if i0 < a or i1 > split:
                continue
            w = R.dual_weights(px, UNIVERSE, i0, p["lookback"], p["top"])
            for s, wt in w.items():
                r = px[s][i1] / px[s][i0] - 1
                if r >= 0:
                    continue
                loss = wt * r * 100
                by_asset[s] = by_asset.get(s, 0) + loss
                for t in self.conditions(px, s, i0, smas):
                    tally[t][0] += 1
                    tally[t][1] += loss
        for m in self.months:  # live losing months count too
            if m["ret"] < 0:
                for t in m.get("tags", []):
                    if t in tally:
                        tally[t][0] += 1
                        tally[t][1] += m["ret"]
        worst = sorted(by_asset.items(), key=lambda kv: kv[1])[:3]
        if worst:
            self.note("Mistake review: in the train years the biggest losses came from holding "
                      + ", ".join(f"{s} ({NAMES[s]}, {v:+.0f} weighted % points)" for s, v in worst) + ".", True)
        chosen = base
        fixes = {"below_sma200": "guard", "vol_spike": "invvol"}
        for cond, (n, loss) in sorted(tally.items(), key=lambda kv: kv[1][1]):
            if n < 3:
                continue
            key = fixes[cond]
            trial_p = dict(chosen["p"], **{key: True})
            trial = next(r for r in rows if r["p"] == trial_p)
            better = trial["train"]["sharpe"] > chosen["train"]["sharpe"]
            what = "the asset was below its 200-day average" if cond == "below_sma200" else "the asset was in a volatility spike"
            fix = "skip assets below their 200-day average" if key == "guard" else "weight by inverse volatility"
            self.note(f"Mistake review: {n} losing holdings started when {what} ({loss:+.0f} weighted % points). "
                      f"Tested '{fix}': train Sharpe {chosen['train']['sharpe']:.2f} to {trial['train']['sharpe']:.2f}, "
                      f"validation {chosen['valid']['cagr']:+.1f} to {trial['valid']['cagr']:+.1f}%/year, drawdown "
                      f"{chosen['valid']['mdd']:.0f}% to {trial['valid']['mdd']:.0f}%. "
                      + ("Adopted." if better else "Rejected: it did not improve the train result."), True)
            if better:
                chosen = trial
        same = [r for r in rows if r["p"]["guard"] == chosen["p"]["guard"] and r["p"]["invvol"] == chosen["p"]["invvol"]]
        return max(same, key=lambda r: r["train"]["sharpe"])

    @staticmethod
    def conditions(px, s, i, smas):
        tags = []
        sma = smas[s][i]
        if sma is not None and px[s][i] < sma:
            tags.append("below_sma200")
        rr = [px[s][k] / px[s][k - 1] - 1 for k in range(max(1, i - 20), i + 1) if px[s][k - 1] and px[s][k]]
        rl = [px[s][k] / px[s][k - 1] - 1 for k in range(max(1, i - 252), i + 1) if px[s][k - 1] and px[s][k]]
        if len(rl) > 60 and R._std(rr) > 1.5 * R._std(rl):
            tags.append("vol_spike")
        return tags

    # ---------- trading ----------
    def quote(self, sym):
        q = data.quote(sym)
        fx = data.fx_to_usd(q["currency"])
        self.on_quote(Quote(sym, q["bid"], q["ask"], q["ts"] or time.time(), fx, q["open"]))

    def on_quote(self, q: Quote):
        with self.lock:
            before = len(self.acct.trades)
            self.acct.on_quote(q)
            for t in self.acct.trades[before:]:
                self.note(f"{t.symbol}: sold {t.qty:.6g} at {t.exit:.4f}, result {t.pnl:+.2f} USD ({t.reason}).")

    def cycle(self):
        if not self.cycle_lock.acquire(blocking=False):
            return
        try:
            if self.paused:
                return
            if not self.model or time.time() - self.model.get("ts", 0) > RELEARN_S:
                self.learn()
                self.save()
            for s in UNIVERSE:
                try:
                    self.quote(s)
                except Exception as e:  # noqa: BLE001
                    self.note(f"{s}: no quote ({e}).")
            with self.lock:
                eq = self.acct.equity()
                if eq < self.acct.peak_equity * 0.70:
                    self.paused = True
                    self.note(f"Paused: equity {eq:.2f} USD is more than 30% below its peak. Review before resuming.", True)
                    return
            self.rebalance()
            with self.lock:
                curve = self.acct.equity_curve
                if not curve or time.time() - curve[-1][0] >= SNAPSHOT_S:
                    self.acct.snapshot_equity()
        finally:
            self.cycle_lock.release()
            self.save()

    def rebalance(self, month=None):
        if not self.model:
            return  # never trade before a successful learning pass
        month = month or time.strftime("%Y-%m", time.gmtime())
        if self.rebalanced != month:  # only now is the long price history needed
            days, px = R.panel(UNIVERSE + ["SHY"], "2004-01-01")
            today = time.strftime("%Y-%m-%d", time.gmtime())
            last = len(days) - 1 if days[-1] < today else len(days) - 2   # last completed session
            for o in self.acct.orders:
                if o.status == "pending":
                    self.acct.cancel(o.id)
            self.close_month()
            if self.model.get("status") == "live":
                p = self.model["p"]
                smas = {s: R._sma_none(px[s], 200) for s in UNIVERSE}
                self.targets = R.dual_weights(px, UNIVERSE, last, p["lookback"], p["top"], p["guard"], p["invvol"], smas)
                self.entry_tags = {s: self.conditions(px, s, last, smas) for s in self.targets}
            else:
                self.targets, self.entry_tags = {}, {}
            self.month_hold = dict(self.targets)
            self.month_start_eq = self.acct.equity()
            tgt = ", ".join(f"{s} {w * 100:.0f}%" for s, w in self.targets.items()) or "all cash"
            self.note(f"Rebalance for {month} using closes of {days[last]}: target {tgt}.")
            self.rebalanced = month
        self.trade_to_targets()

    def close_month(self):
        if self.month_start_eq is None:
            return
        eq = self.acct.equity()
        ret = (eq / self.month_start_eq - 1) * 100
        tags = sorted({t for s in self.month_hold for t in self.entry_tags.get(s, [])})
        self.months.append({"month": self.rebalanced, "ret": ret, "hold": self.month_hold, "tags": tags,
                            "start": self.month_start_eq, "end": eq})
        self.note(f"Month {self.rebalanced} closed at {ret:+.2f}% (held {', '.join(self.month_hold) or 'cash'}).")
        if ret < 0:
            self.note(f"Losing month {self.rebalanced} ({ret:+.2f}%): conditions at entry {tags or 'none flagged'}; "
                      "counted in the next mistake review.", True)

    def trade_to_targets(self):
        with self.lock:
            eq = self.acct.equity()
            pend = {o.symbol for o in self.acct.orders if o.status == "pending"}
            cur = {}
            for s, p in self.acct.positions.items():
                q = self.acct.last.get(s)
                cur[s] = p.qty * (q.bid if q else p.entry) * (q.fx if q else 1)
            for s in sorted(set(cur)):  # sells first
                if s in pend:
                    continue
                diff = self.targets.get(s, 0) * eq - cur[s]
                if s in self.targets and diff >= -TOL * eq:
                    continue
                q = self.acct.last[s]
                qty = None if s not in self.targets else min(self.acct.positions[s].qty, -diff / (q.bid * q.fx))
                _, err = self.acct.close(s, qty, reason="rebalance")
                if err:
                    o = self.acct.place(s, -1, qty or self.acct.positions[s].qty)
                    self.note(f"{s}: sell queued ({o.note or o.status}).")
            for s, w in sorted(self.targets.items()):
                if s in pend:
                    continue
                diff = w * eq - cur.get(s, 0)
                q = self.acct.last.get(s)
                if diff <= TOL * eq or not q:
                    continue
                usd = min(diff, self.acct.free_margin() * 0.995 / (1 + FEE_PCT / 100))
                if usd < 1:
                    continue
                o = self.acct.place(s, 1, usd / (q.ask * q.fx))
                self.note(f"{s}: buy {usd:.2f} USD toward a {w * 100:.0f}% target - {o.status}"
                          f"{' (' + o.note + ')' if o.note else ''}.")

    # ---------- view ----------
    def view(self):
        with self.lock:
            a = self.acct
            rate = data.fx_to_usd("THB")
            eq = a.equity()
            pos = []
            for s, p in a.positions.items():
                q = a.last.get(s)
                mark = q.bid if q else p.entry
                val = mark * p.qty * (q.fx if q else 1)
                pos.append({"symbol": s, "name": NAMES.get(s, s), "qty": p.qty, "entry": p.entry, "mark": mark,
                            "value_usd": val, "weight": val / eq * 100 if eq else 0,
                            "pnl_usd": (mark - p.entry) * p.qty * (q.fx if q else 1)})
            return {"stats": a.stats(), "equity_thb": eq / rate if rate else None, "capital_thb": CAPITAL_THB,
                    "capital_usd": self.capital_usd, "positions": pos, "model": self.model, "grid": self.grid[:12],
                    "targets": [{"symbol": s, "name": NAMES.get(s, s), "weight": w * 100, "tags": self.entry_tags.get(s, [])}
                                for s, w in self.targets.items()],
                    "lessons": self.lessons[::-1][:100], "log": self.log[::-1][:100], "months": self.months[::-1],
                    "trades": [vars(t) for t in a.trades[::-1][:100]], "orders": [vars(o) for o in a.orders[::-1][:30]],
                    "paused": self.paused, "learning": self.learning, "check_every_s": EVERY_S, "equity_curve": a.equity_curve[-2000:],
                    "rebalanced": self.rebalanced, "universe": [{"symbol": s, "name": NAMES[s]} for s in UNIVERSE],
                    "costs": {"fee_pct": FEE_PCT, "slippage_pct": SLIP_PCT}}


def loop(at: AutoTrader, every=EVERY_S):
    while True:
        try:
            at.cycle()
        except Exception as e:  # noqa: BLE001
            at.note(f"cycle error: {e}")
        at.last_cycle = time.time()
        time.sleep(every)
