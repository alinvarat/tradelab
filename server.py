"""TradeLab: multi-market paper-trading simulator with analysis, news, backtests and an AI analyst.
Run: python3 server.py  ->  http://127.0.0.1:8770   (simulated money only; no broker connection exists)."""
import json
import math
import os
import shutil
import signal
import sys
import threading
import time
import traceback
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.universe import TICKERS
from core import event_trader, llm_trader, news_archive
from core import ai, analysis, autotrader, backtest, data, econ_calendar, hunter, news
from core.engine import Account, Quote

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
STATE = ROOT / "data" / "state.json"
HOST = os.environ.get("TRADELAB_HOST", "127.0.0.1")  # keep 127.0.0.1 behind a tunnel; the server has no login
PORT = int(os.environ.get("TRADELAB_PORT", "8770"))
STARTED = time.time()

DEFAULT_WATCH = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "SPY", "QQQ",
                 "BTC-USD", "ETH-USD", "SOL-USD", "GC=F", "CL=F", "EURUSD=X", "USDJPY=X"]
OVERVIEW = {
    "Indices": [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow Jones"), ("^RUT", "Russell 2000"),
                ("^VIX", "VIX volatility"), ("^STOXX50E", "Euro Stoxx 50"), ("^FTSE", "FTSE 100"),
                ("^GDAXI", "DAX"), ("^N225", "Nikkei 225"), ("^HSI", "Hang Seng")],
    "Rates and FX": [("^TNX", "US 10Y yield"), ("^IRX", "US 13W bill"), ("DX-Y.NYB", "US dollar index"),
                     ("EURUSD=X", "EUR/USD"), ("GBPUSD=X", "GBP/USD"), ("USDJPY=X", "USD/JPY"), ("USDCNY=X", "USD/CNY")],
    "Commodities": [("GC=F", "Gold"), ("SI=F", "Silver"), ("CL=F", "WTI crude"), ("BZ=F", "Brent crude"),
                    ("NG=F", "Natural gas"), ("HG=F", "Copper")],
    "Crypto": [("BTC-USD", "Bitcoin"), ("ETH-USD", "Ether"), ("SOL-USD", "Solana"), ("XRP-USD", "XRP"),
               ("BNB-USD", "BNB")],
    "US sectors": [("XLK", "Technology"), ("XLF", "Financials"), ("XLE", "Energy"), ("XLV", "Health care"),
                   ("XLY", "Consumer discretionary"), ("XLP", "Consumer staples"), ("XLI", "Industrials"),
                   ("XLU", "Utilities"), ("XLB", "Materials"), ("XLRE", "Real estate"), ("XLC", "Communication")],
}
UNIVERSE = sorted(set(DEFAULT_WATCH + ["AVGO", "JPM", "V", "MA", "UNH", "XOM", "LLY", "COST", "NFLX", "AMD",
                                       "ORCL", "CRM", "ADBE", "INTC", "BA", "DIS", "WMT", "KO", "PEP", "IWM",
                                       "TLT", "SLV", "XRP-USD", "BNB-USD", "GBPUSD=X"]))

lock = threading.RLock()
pool = ThreadPoolExecutor(10)
state = {"watchlist": list(DEFAULT_WATCH), "alerts": [], "alert_log": []}
acct = Account()
quotes: dict = {}
status = {"last_poll": 0, "errors": {}}
auto: autotrader.AutoTrader | None = None
hunt: hunter.Hunter | None = None
evt: event_trader.EventTrader | None = None
llm: llm_trader.LlmTrader | None = None


def load():
    global acct
    if STATE.exists():
        try:
            d = json.loads(STATE.read_text())
        except ValueError:  # corrupt file: use the newest backup instead of crash-looping
            backups = sorted((ROOT / "data" / "backups").glob("*/state.json"))
            if not backups:
                raise
            print(f"state.json unreadable; restoring {backups[-1]}", flush=True)
            shutil.copy(STATE, STATE.with_suffix(".corrupt"))
            d = json.loads(backups[-1].read_text())
        acct = Account.from_dict(d["account"])
        state.update({k: d[k] for k in ("watchlist", "alerts", "alert_log") if k in d})


def save():
    with lock:
        d = {"account": acct.to_dict(), **state}
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(STATE)


def num(v, name, lo=None, hi=None):
    """Parse a finite number from request JSON or raise ValueError (-> HTTP 400)."""
    x = float(v)
    if not math.isfinite(x) or (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError(f"{name} must be a finite number" + (f" in [{lo}, {hi}]" if lo is not None else ""))
    return x


def to_quote(q: dict) -> Quote:
    return Quote(q["symbol"], q["bid"], q["ask"], q["ts"] or time.time(), data.fx_to_usd(q["currency"]), q["open"])


def refresh(symbol: str) -> dict | None:
    try:
        q = data.quote(symbol)
        if q.get("price") is None:
            return None
        q["fx"] = data.fx_to_usd(q["currency"])
        status["errors"].pop(symbol, None)
    except Exception as e:  # noqa: BLE001
        status["errors"][symbol] = str(e)[:200]
        return None
    with lock:
        quotes[symbol] = q
        acct.on_quote(to_quote(q))
        check_alerts(q)
    if auto and (symbol in auto.acct.positions or any(o.symbol == symbol and o.status == "pending" for o in auto.acct.orders)):
        auto.on_quote(to_quote(q))
    if hunt and (symbol in hunt.acct.positions or any(o.symbol == symbol and o.status == "pending" for o in hunt.acct.orders)):
        hunt.on_quote(to_quote(q))
    return q


def check_alerts(q):
    for a in state["alerts"]:
        if a["symbol"] != q["symbol"] or a.get("hit"):
            continue
        if (a["op"] == "above" and q["price"] >= a["price"]) or (a["op"] == "below" and q["price"] <= a["price"]):
            a["hit"] = time.time()
            state["alert_log"].insert(0, {"ts": a["hit"], "symbol": a["symbol"],
                                          "text": f"{a['symbol']} {a['op']} {a['price']} (now {q['price']:.4g})"})
            del state["alert_log"][100:]


def tracked() -> list:
    with lock:
        s = set(state["watchlist"]) | set(acct.positions) | {o.symbol for o in acct.orders if o.status == "pending"}
        s |= {a["symbol"] for a in state["alerts"] if not a.get("hit")}
    if auto:
        s |= set(auto.acct.positions) | {o.symbol for o in auto.acct.orders if o.status == "pending"}
    if hunt:
        s |= set(hunt.acct.positions) | {o.symbol for o in hunt.acct.orders if o.status == "pending"}
    return sorted(s)


def poller():
    last_slow, last_save = 0.0, 0.0
    while True:
        try:
            syms = tracked()
            crypto = [s for s in syms if data.is_crypto(s)]
            slow = time.time() - last_slow > 60
            todo = crypto + ([s for s in syms if not data.is_crypto(s)] if slow else [])
            list(pool.map(refresh, todo))
            if slow:
                last_slow = time.time()
                with lock:
                    acct.snapshot_equity()
            status["last_poll"] = time.time()
            if time.time() - last_save > 30:
                save()
                last_save = time.time()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(5)


def overview():
    def one(item):
        sym, name = item
        try:
            ch = data.chart(sym, "1mo", "1d")
            m, bars = ch["meta"], ch["bars"]
            px, prev = m.get("regularMarketPrice"), m.get("previousClose") or m.get("chartPreviousClose")
            if len(bars) >= 2 and bars[-1]["c"]:
                prev = bars[-2]["c"]
            return {"symbol": sym, "name": name, "price": px, "change_pct": (px / prev - 1) * 100 if prev else None,
                    "month_pct": (px / bars[0]["c"] - 1) * 100 if bars else None,
                    "spark": [round(b["c"], 6) for b in bars]}
        except Exception as e:  # noqa: BLE001
            return {"symbol": sym, "name": name, "error": str(e)[:120]}
    out = {g: list(pool.map(one, items)) for g, items in OVERVIEW.items()}
    return {"groups": out, "fear_greed": data.fear_greed()}


def screener(universe):
    def one(sym):
        try:
            a = analysis.analyze(sym)
            return {"symbol": sym, "name": a["name"], "price": a["price"], "currency": a["currency"],
                    "score": a["score"], "rating": a["rating"], "rsi": a["momentum"]["rsi"],
                    "adx": a["trend"]["adx"], "atr_pct": a["volatility"]["atr_pct"],
                    "perf_1m": a["performance"]["1m"], "perf_3m": a["performance"]["3m"], "perf_1y": a["performance"]["1y"],
                    "above_sma200": (a["price"] > a["trend"]["sma200"]) if a["trend"]["sma200"] else None,
                    "events": [e["event"] for e in a["events"][-2:]]}
        except Exception as e:  # noqa: BLE001
            return {"symbol": sym, "error": str(e)[:120]}
    return list(pool.map(one, universe))


_shock_cache = {"ts": 0, "rows": None}


def shocks():
    """Large US stocks that gapped >= 3% at the latest open on >= 1.5x their 50-day volume, with headlines."""
    if _shock_cache["rows"] is not None and time.time() - _shock_cache["ts"] < 1800:
        return _shock_cache["rows"]

    def one(sym):
        try:
            b = data.chart(sym, "6mo", "1d")["bars"]
            if len(b) < 52:
                return None
            for i in (len(b) - 1, len(b) - 2):
                avgv = sum(x["v"] for x in b[i - 50:i]) / 50
                gap = b[i]["o"] / b[i - 1]["c"] - 1
                if abs(gap) >= 0.03 and avgv and b[i]["v"] >= 1.5 * avgv:
                    return {"symbol": sym, "t": b[i]["t"], "gap": gap * 100, "day": (b[i]["c"] / b[i]["o"] - 1) * 100,
                            "vmult": b[i]["v"] / avgv, "since": (b[-1]["c"] / b[i]["c"] - 1) * 100}
        except Exception:  # noqa: BLE001
            return None
        return None
    rows = [r for r in pool.map(one, TICKERS) if r]
    for r in rows:
        try:
            r["news"] = news.symbol_news(r["symbol"])["items"][:3]
        except Exception:  # noqa: BLE001
            r["news"] = []
    rows.sort(key=lambda r: r["gap"])
    _shock_cache.update(ts=time.time(), rows=rows)
    return rows


def account_view():
    with lock:
        pos = []
        for s, p in acct.positions.items():
            q = acct.last.get(s)
            mark = (q.bid if p.side > 0 else q.ask) if q else p.entry
            fx = q.fx if q else 1
            pos.append({"symbol": s, "side": p.side, "qty": p.qty, "entry": p.entry, "mark": mark, "sl": p.sl, "tp": p.tp,
                        "value_usd": mark * p.qty * fx, "pnl_usd": (mark - p.entry) * p.qty * p.side * fx,
                        "pnl_pct": (mark / p.entry - 1) * 100 * p.side, "opened_ts": p.opened_ts,
                        "currency": quotes.get(s, {}).get("currency", "USD"), "market_open": q.open if q else None})
        st = acct.stats()
        eq = st["equity"]
        alloc = {}
        for p in pos:
            t = quotes.get(p["symbol"], {}).get("type", "OTHER")
            alloc[t] = alloc.get(t, 0) + abs(p["value_usd"])
        return {"stats": st, "settings": acct.settings(), "positions": pos,
                "orders": [vars(o) for o in reversed(acct.orders[-200:])],
                "trades": [vars(t) for t in reversed(acct.trades[-300:])],
                "equity_curve": acct.equity_curve[-3000:] + [(time.time(), round(eq, 2))],
                "allocation": alloc, "cash_usd": acct.balance}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/healthz":
                now = time.time()
                ok = now - status["last_poll"] < 300 or now - STARTED < 120
                return self._send(200 if ok else 503, {
                    "ok": ok, "uptime_s": round(now - STARTED), "last_poll_age_s": round(now - status["last_poll"]),
                    "auto_cycle_age_s": round(now - getattr(auto, "last_cycle", STARTED)) if auto else None,
                    "news_archive": ({**news_archive.STATUS, "age_s": round(now - news_archive.STATUS["ts"])}
                                     if news_archive.STATUS else None),
                    "llm_trader": ({"last_scan_age_s": round(now - llm.last_scan), "error": llm.last_error}
                                   if llm and llm.last_scan else None)})
            if not u.path.startswith("/api/"):
                return self._static(u.path)
            p = u.path[5:]
            if p == "quotes":
                syms = state["watchlist"]
                missing = [s for s in syms if s not in quotes]
                list(pool.map(refresh, missing))
                with lock:
                    return self._send(200, {"watchlist": syms, "quotes": [quotes.get(s) for s in syms],
                                            "last_poll": status["last_poll"], "errors": status["errors"]})
            if p == "quote":
                return self._send(200, refresh(q["symbol"]) or {"error": "no quote"})
            if p == "chart":
                ch = data.chart(q["symbol"], q.get("range", "1y"), q.get("interval"))
                return self._send(200, {**ch, "ind": analysis.series(ch["bars"])})
            if p == "analysis":
                a = analysis.analyze(q["symbol"])
                a["profile"] = data.profile(q["symbol"])
                return self._send(200, a)
            if p == "news":
                if q.get("symbol"):
                    return self._send(200, news.symbol_news(q["symbol"], q.get("name", "")))
                return self._send(200, news.market_news())
            if p == "search":
                if not q.get("q", "").strip():
                    return self._send(200, [])
                return self._send(200, data.search(q["q"]))
            if p == "overview":
                return self._send(200, overview())
            if p == "account":
                return self._send(200, account_view())
            if p == "calendar":
                return self._send(200, econ_calendar.events())
            if p == "screener":
                uni = state["watchlist"] if q.get("list") == "watchlist" else UNIVERSE
                return self._send(200, screener(uni))
            if p == "shocks":
                return self._send(200, shocks())
            if p == "alerts":
                return self._send(200, {"alerts": state["alerts"], "log": state["alert_log"]})
            if p == "auto":
                return self._send(200, auto.view())
            if p == "hunter":
                return self._send(200, hunt.view())
            if p == "events":
                return self._send(200, evt.view())
            if p == "llm_trader":
                return self._send(200, llm.view() if llm else {"disabled": True})
            if p == "strategies":
                return self._send(200, backtest.STRATEGIES)
            return self._send(404, {"error": "not found"})
        except KeyError as e:
            self._send(400, {"error": f"missing {e}"})
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):  # the data provider does not know this symbol/request
                self._send(404, {"error": "unknown symbol or no data"})
            else:
                self._send(502, {"error": str(e)[:300]})
        except Exception as e:  # noqa: BLE001
            self._send(502, {"error": str(e)[:300]})

    def do_POST(self):
        global acct
        u = urlparse(self.path)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            b = json.loads(self.rfile.read(n) or b"{}")
            p = u.path[5:]
            f = lambda k: num(b[k], k, 0) if b.get(k) not in (None, "") else None  # noqa: E731
            if p == "order":
                sym = b["symbol"].strip().upper()
                if sym.endswith(".BK"):
                    return self._send(400, {"error": "this simulator covers global markets only"})
                if not refresh(sym):
                    return self._send(400, {"error": f"no quote for {sym}"})
                if int(b["side"]) not in (1, -1):
                    raise ValueError("side must be 1 (buy) or -1 (sell)")
                with lock:
                    o = acct.place(sym, int(b["side"]), num(b["qty"], "qty", 0, 1e9), b.get("type", "market"), f("price"),
                                   f("sl"), f("tp"))
                save()
                return self._send(200, vars(o))
            if p == "cancel":
                with lock:
                    ok = acct.cancel(int(b["id"]))
                save()
                return self._send(200, {"ok": ok})
            if p == "close":
                refresh(b["symbol"])
                with lock:
                    t, err = acct.close(b["symbol"], f("qty"))
                save()
                return self._send(400 if err else 200, {"error": err} if err else vars(t))
            if p == "modify":
                with lock:
                    ok = acct.modify(b["symbol"], f("sl"), f("tp"))
                save()
                return self._send(200, {"ok": ok})
            if p == "reset":
                with lock:
                    acct = Account(balance=num(b.get("balance", 100000), "balance", 1, 1e12),
                                   leverage=num(b.get("leverage", 1), "leverage", 1, 100),
                                   fee_rate=num(b.get("fee_pct", 0.05), "fee_pct", 0, 100) / 100,
                                   min_fee=num(b.get("min_fee", 0), "min_fee", 0, 1e6),
                                   slippage=num(b.get("slippage_pct", 0.02), "slippage_pct", 0, 100) / 100,
                                   allow_short=bool(b.get("allow_short", True)))
                    for s, qd in quotes.items():
                        acct.on_quote(to_quote(qd))
                save()
                return self._send(200, {"ok": True})
            if p == "watchlist":
                with lock:
                    sym = b["symbol"].strip().upper()
                    if b.get("action") == "remove":
                        state["watchlist"] = [s for s in state["watchlist"] if s != sym]
                    elif sym not in state["watchlist"]:
                        if sym.endswith(".BK"):
                            return self._send(400, {"error": "global markets only"})
                        if not refresh(sym):
                            return self._send(400, {"error": f"unknown symbol {sym}"})
                        state["watchlist"].append(sym)
                save()
                return self._send(200, {"watchlist": state["watchlist"]})
            if p == "alerts":
                with lock:
                    if b.get("action") == "remove":
                        state["alerts"] = [a for a in state["alerts"] if a["id"] != b["id"]]
                    else:
                        state["alerts"].append({"id": int(time.time() * 1000), "symbol": b["symbol"].upper(),
                                                "op": b["op"], "price": num(b["price"], "price", 0), "created": time.time()})
                save()
                return self._send(200, {"alerts": state["alerts"]})
            if p == "backtest":
                num(b.get("capital", 10000), "capital", 1, 1e12)
                return self._send(200, backtest.run(
                    b["symbol"], b.get("strategy", "sma_cross"), b.get("params") or {}, b.get("range", "5y"),
                    b.get("interval", "1d"), float(b.get("capital", 10000)), float(b.get("fee_pct", 0.05)),
                    float(b.get("slip_pct", 0.02)), float(b.get("position_pct", 100)), float(b.get("stop_atr", 0)),
                    bool(b.get("allow_short", False))))
            if p == "auto":
                act = b.get("action")
                if act == "pause":
                    auto.paused = True
                elif act == "resume":
                    auto.paused = False
                    threading.Thread(target=auto.cycle, daemon=True).start()
                elif act == "learn":
                    auto.model["ts"] = 0
                    threading.Thread(target=auto.cycle, daemon=True).start()
                elif act == "reset":
                    with auto.lock:
                        auto.reset()
                    threading.Thread(target=auto.cycle, daemon=True).start()
                auto.save()
                return self._send(200, {"ok": True})
            if p == "hunter":
                if b.get("action") == "reset":
                    with hunt.lock:
                        hunt.reset()
                    hunt.save()
                    threading.Thread(target=hunt.cycle, daemon=True).start()
                return self._send(200, {"ok": True})
            if p == "events":
                act = b.get("action")
                with evt.lock:
                    if act == "pause":
                        evt.paused = True
                    elif act == "resume":
                        evt.paused = False
                evt.save()
                return self._send(200, {"ok": True, "paused": evt.paused})
            if p == "ai":
                sym = b["symbol"]
                a = analysis.analyze(sym)
                return self._send(200, ai.analyst(sym, a, news.symbol_news(sym, a.get("name") or ""), b.get("question", "")))
            return self._send(404, {"error": "not found"})
        except KeyError as e:
            self._send(400, {"error": f"missing {e}"})
        except (ValueError, TypeError) as e:
            self._send(400, {"error": f"invalid input: {str(e)[:200]}"})
        except Exception as e:  # noqa: BLE001
            self._send(502, {"error": str(e)[:300]})

    def _static(self, path):
        path = "/index.html" if path in ("", "/") else path
        f = (UI / path.lstrip("/")).resolve()
        if UI not in f.parents or not f.is_file():
            return self._send(404, {"error": "not found"})
        ct = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css",
              ".svg": "image/svg+xml"}.get(f.suffix, "application/octet-stream")
        self._send(200, f.read_bytes(), ct)


def history_loop(every=300):
    """Append-only long-term record (data/history-YYYY-MM.jsonl): both bot equities and SPY every 5 minutes."""
    time.sleep(30)
    while True:
        try:
            if auto and hunt:
                with auto.lock:
                    auto_eq = auto.acct.equity()
                with hunt.lock:
                    hunt_eq = hunt.acct.equity()
                spy = (quotes.get("SPY") or {}).get("price")
                path = ROOT / "data" / ("history-" + time.strftime("%Y-%m", time.gmtime()) + ".jsonl")
                with path.open("a") as f:
                    f.write(json.dumps({"ts": round(time.time()), "auto_usd": round(auto_eq, 4),
                                        "hunter_usd": round(hunt_eq, 4), "spy": spy}) + "\n")
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(every)


def shock_warm_loop():
    """Keep the news-shock scan cached so the button answers instantly instead of taking ~8 s."""
    time.sleep(20)
    while True:
        try:
            shocks()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(1700)  # cache lifetime is 1800 s


def backup_loop(keep=14):
    """Once a day copy the account files to data/backups/YYYY-MM-DD/ (inside the data volume; keeps `keep` days)."""
    while True:
        try:
            target = ROOT / "data" / "backups" / time.strftime("%Y-%m-%d", time.gmtime())
            if not target.exists():
                target.mkdir(parents=True)
                for src in [ROOT / "data" / n for n in ("state.json", "auto.json", "hunter.json", "event_trader.json", "llm_trader.json", "ai_log.jsonl")] + \
                        sorted((ROOT / "data").glob("history-*.jsonl"))[-2:] + [ROOT / "data" / "event_trader_log.jsonl", ROOT / "data" / "llm_trader_log.jsonl"]:
                    if src.exists():
                        shutil.copy2(src, target / src.name)
                for old in sorted((ROOT / "data" / "backups").iterdir())[:-keep]:
                    shutil.rmtree(old, ignore_errors=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(3600)


def shutdown(signum, _frame):
    """SIGTERM/SIGINT: persist every account once, then exit (systemd restarts it when wanted)."""
    for name, fn in (("server", save), ("auto", getattr(auto, "save", None)), ("hunter", getattr(hunt, "save", None)),
                     ("events", getattr(evt, "save", None)), ("llm", getattr(llm, "save", None))):
        try:
            if fn:
                fn()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
    print(f"saved state on signal {signum}", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    load()
    auto = autotrader.AutoTrader()
    threading.Thread(target=autotrader.loop, args=(auto,), daemon=True).start()
    hunt = hunter.Hunter()
    threading.Thread(target=hunter.loop, args=(hunt,), daemon=True).start()
    evt = event_trader.EventTrader()
    threading.Thread(target=event_trader.loop, args=(evt,), daemon=True).start()
    if os.environ.get("TRADELAB_LLM_TRADER") == "1":  # needs opencode or OPENROUTER_API_KEY; off by default
        llm = llm_trader.LlmTrader()
        threading.Thread(target=llm_trader.loop, args=(llm,), daemon=True).start()
    threading.Thread(target=poller, daemon=True).start()
    threading.Thread(target=backup_loop, daemon=True).start()
    threading.Thread(target=shock_warm_loop, daemon=True).start()
    threading.Thread(target=history_loop, daemon=True).start()
    if os.environ.get("TRADELAB_NEWS_ARCHIVE") == "1":  # set in the container; the systemd collector uses its own copy
        threading.Thread(target=news_archive.loop, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f"TradeLab on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
