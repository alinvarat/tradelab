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
from core import buzz, dvol_collect, event_trader, llm_trader, news_archive, news_latency, steward
from core import ai, analysis, autotrader, backtest, data, econ_calendar, hunter, news
from core.engine import Account, Quote
from core.storage import write_json_atomic

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui"
STATE = ROOT / "data" / "state.json"
HOST = os.environ.get("TRADELAB_HOST", "127.0.0.1")  # keep 127.0.0.1 behind a tunnel; the server has no login
PORT = int(os.environ.get("TRADELAB_PORT", "8770"))
STARTED = time.time()
THREADS: dict = {}   # name -> (target, args, thread) so a dead loop thread is restarted
RESTARTS: dict = {}

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
buzzmon: buzz.BuzzMonitor | None = None


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
        write_json_atomic(STATE, d)


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
        q = data.quote_fast(symbol, ttl=1.5)
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
            slow = time.time() - last_slow > 30
            held = set(acct.positions) | (set(auto.acct.positions) if auto else set()) | (set(hunt.acct.positions) if hunt else set())
            todo = crypto + [s for s in syms if not data.is_crypto(s) and (slow or s in held)]
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
        time.sleep(3)


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
                age = {"poller": (now - status["last_poll"], 300)}
                if auto:
                    age["auto_trader"] = (now - getattr(auto, "last_cycle", STARTED), 1800)
                if evt and evt.last_scan:
                    age["event_trader"] = (now - evt.last_scan, 600)
                if buzzmon:
                    age["buzz"] = (now - (buzzmon.last_scan or STARTED), 3 * buzz.SCAN_S + 300)
                if news_archive.STATUS:
                    age["news_archive"] = (now - news_archive.STATUS["ts"], 900)
                if llm and llm.last_scan:
                    age["llm_trader"] = (now - llm.last_scan, 1800)
                grace = now - STARTED < 180
                stale = sorted(k for k, (a, limit) in age.items() if a > limit)
                free_gb = shutil.disk_usage(ROOT).free / 1e9
                ok = grace or (not stale and free_gb > 0.2)
                return self._send(200 if ok else 503, {
                    "ok": ok, "uptime_s": round(now - STARTED), "stale": stale, "disk_free_gb": round(free_gb, 2),
                    "ages_s": {k: round(a) for k, (a, _) in age.items()}, "restarts": RESTARTS,
                    "last_poll_age_s": round(now - status["last_poll"]),
                    "auto_cycle_age_s": round(now - getattr(auto, "last_cycle", STARTED)) if auto else None,
                    "buzz": ({"last_scan_age_s": round(now - buzzmon.last_scan), "events": len(buzzmon.events), "error": buzzmon.last_error}
                             if buzzmon and buzzmon.last_scan else None),
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
                return self._send(200, {**news.market_news(), "archive": news_archive.STATUS,
                                        "latency": news_latency.evaluate()})
            if p == "news_latency":
                return self._send(200, news_latency.evaluate())
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
            if p == "llm_log":
                lines = llm_trader.read_log_tail(llm_trader.LOG)
                return self._send(200, llm_trader.build_cycles(lines, int(q.get("n", 40))))
            if p == "event_log":
                lines = llm_trader.read_log_tail(event_trader.LOG, 2500)
                rows = []
                for line in lines[::-1]:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r["kind"] in ("event", "pair", "error", "reset"):
                        rows.append(r)
                    if len(rows) >= int(q.get("n", 60)):
                        break
                return self._send(200, {"rows": rows})
            if p == "accounts":
                return self._send(200, accounts_summary())
            if p == "steward":
                return self._send(200, steward.LAST or {"note": "no review yet (first one runs about 5 minutes after start)"})
            if p == "dvol":
                files = sorted(f.name for f in dvol_collect.RAW.glob("*.json.gz")) if dvol_collect.RAW.exists() else []
                return self._send(200, {**dvol_collect.STATUS, "snapshots": files, "dir": str(dvol_collect.RAW.name),
                                        "window": "Mondays 2026-11-30..2027-02-22 09:00 and 09:05 UTC"})
            if p == "buzz":
                return self._send(200, buzzmon.view() if buzzmon else {"disabled": True})
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
                for src in [ROOT / "data" / n for n in ("state.json", "auto.json", "hunter.json", "event_trader.json", "llm_trader.json", "llm_trader_v4.json", "ai_log.jsonl")] + \
                        sorted((ROOT / "data").glob("history-*.jsonl"))[-2:] + [ROOT / "data" / "event_trader_log.jsonl", ROOT / "data" / "llm_trader_log.jsonl", ROOT / "data" / "llm_trader_log_v4.jsonl"]:
                    if src.exists():
                        shutil.copy2(src, target / src.name)
                for old in sorted((ROOT / "data" / "backups").iterdir())[:-keep]:
                    shutil.rmtree(old, ignore_errors=True)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        time.sleep(3600)


def ai_news_available():
    from core import ai_news
    return ai_news.openrouter_available() or ai_news.opencode_available()


def accounts_summary():
    """One row per simulated account/experiment so the UI can show them side by side in the same units."""
    rate = data.fx_to_usd("THB") or 0.03
    rows = []
    open_thb = lambda eq, start: data.thb_at_open(eq, start) if start else 0.0

    def add(key, name, tab, acct_, start_usd, status, note, ctrl=None):
        with lock:
            eq = acct_.equity()
            control_equity = ctrl.equity() if ctrl is not None else None
        rows.append({"key": key, "name": name, "tab": tab, "start_usd": start_usd, "equity_usd": eq,
                     "return_pct": (eq / start_usd - 1) * 100 if start_usd else None,
                     "equity_thb": eq / rate if key == "manual" else open_thb(eq, start_usd),
                     "start_thb": acct_.initial / rate if key == "manual" else 5000.0,
                     "positions": len(acct_.positions), "status": status, "note": note,
                     "control_usd": control_equity,
                     "control_thb": open_thb(control_equity, start_usd) if control_equity is not None else None})
    add("manual", "Manual sandbox", "portfolio", acct, acct.initial, "you place the orders", "Manual paper trading account")
    if auto:
        add("auto", "Auto trader (monthly momentum)", "auto", auto.acct, auto.capital_usd, "paused" if auto.paused else "running",
            ("all cash this month" if not auto.targets else "holding " + ", ".join(auto.targets)) + "; no leverage")
    if hunt:
        v = hunt.view()
        add("hunter", "Hunter (20x BTC/ETH/SOL)", "auto", hunt.acct, hunt.capital_usd,
            "ruined" if v["ruined"] else "running", "20x leverage by design; high risk")
    if evt:
        ev = evt.evaluate()
        add("event", "Event trader (rule)", "events", evt.acct, evt.capital_usd, "paused" if evt.paused else "running",
            f"{ev['closed_pairs']}/{ev['needed']} pairs vs random control; no leverage (1x)", ctrl=evt.ctrl)
    if llm:
        ev = llm.evaluate()
        add("llm", "DeepSeek trader (v4, whole market)", "llm", llm.acct, llm.capital_usd, "paused" if llm.paused else "running",
            f"{ev['closed_pairs']}/{ev['needed']} pairs; model picks 1-20x leverage", ctrl=llm.ctrl)
    extra = {"buzz_events": len(buzzmon.events) if buzzmon else None}
    return {"rows": rows, "thb_per_usd": 1 / rate, **extra}


def status_for_steward():
    now = time.time()
    s = {"uptime_h": round((now - STARTED) / 3600, 1), "poller_age_s": round(now - status["last_poll"]),
         "restarts": RESTARTS, "disk_free_gb": round(shutil.disk_usage(ROOT).free / 1e9, 2),
         "errors": {"event_trader": evt.last_error, "buzz": buzzmon.last_error if buzzmon else None,
                    "llm_trader": llm.last_error if llm else None, "dvol": dvol_collect.STATUS["last_error"]},
         "news_archive": news_archive.STATUS, "dvol_snapshots_taken": dvol_collect.STATUS["taken"][-6:],
         "experiments": {"event_trader": evt.evaluate() if evt else None,
                         "buzz_1d": buzzmon.evaluate() if buzzmon else None,
                         "llm_trader": llm.evaluate() if llm else "disabled (needs OPENROUTER_API_KEY or opencode)"}}
    return s


def start(name, target, *args):
    t = threading.Thread(target=target, args=args, daemon=True, name=name)
    THREADS[name] = (target, args, t)
    t.start()


def supervisor():
    """Restart any background loop whose thread has died (loops catch their own errors; this covers the rest)."""
    while True:
        time.sleep(60)
        for name, (target, args, t) in list(THREADS.items()):
            if not t.is_alive():
                RESTARTS[name] = RESTARTS.get(name, 0) + 1
                print(f"thread {name} died; restarting (#{RESTARTS[name]})", flush=True)
                start(name, target, *args)


def shutdown(signum, _frame):
    """SIGTERM/SIGINT: persist every account once, then exit (systemd restarts it when wanted)."""
    for name, fn in (("server", save), ("auto", getattr(auto, "save", None)), ("hunter", getattr(hunt, "save", None)),
                     ("events", getattr(evt, "save", None)), ("llm", getattr(llm, "save", None)), ("buzz", getattr(buzzmon, "save", None))):
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
    start("autotrader", autotrader.loop, auto)
    hunt = hunter.Hunter()
    start("hunter", hunter.loop, hunt)
    evt = event_trader.EventTrader()
    start("event_trader", event_trader.loop, evt)
    if os.environ.get("TRADELAB_BUZZ", "1") == "1":  # read-only analysis; on by default
        buzzmon = buzz.BuzzMonitor()
        start("buzz", buzz.loop, buzzmon)
    want_llm = os.environ.get("TRADELAB_LLM_TRADER")   # unset: start automatically when a provider is available
    if want_llm == "1" or (want_llm is None and (ai_news_available())):
        llm = llm_trader.LlmTrader()
        start("llm_trader", llm_trader.loop, llm)
    start("poller", poller)
    start("backup_loop", backup_loop)
    start("shock_warm_loop", shock_warm_loop)
    start("history_loop", history_loop)
    if os.environ.get("TRADELAB_NEWS_ARCHIVE") == "1":  # set in the container; the systemd collector uses its own copy
        start("news_archive", news_archive.loop)
    start("dvol", dvol_collect.loop)
    start("steward", steward.loop, status_for_steward)
    start("supervisor", supervisor)
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f"TradeLab on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
