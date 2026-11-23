"""Social-buzz monitor over a BROAD universe (every US-listed stock the Reddit-mention tracker sees, not 104 large caps).

Source: ApeWisdom (public Reddit/social mention counts with the value 24 h ago for each ticker). A buzz event is a
surge in mentions on a real, liquid US stock. Each event is recorded with a Yahoo quote, headlines and a random
liquidity-matched control stock, then scored at +1h / +1d / +3d against SPY. This is an event study first (many more
samples than trades); it decides nothing by itself. Rules and criterion are locked in research/buzz/protocol.md.
Read-only, simulated analysis only; no orders."""
import json
import os
import random
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean, median
from urllib.request import Request, urlopen

from . import data, news

DATA = Path(os.environ.get("TRADELAB_BUZZ_DIR") or Path(__file__).resolve().parent.parent / "research/buzz/data")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
APE = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/{}"
NASDAQ = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&download=true"
SCAN_S = int(os.environ.get("TRADELAB_BUZZ_EVERY", "120"))
MIN_MENTIONS, MIN_RATIO = 20, 3.0       # surge definition (locked)
MIN_PRICE, MIN_CAP, MIN_DOLLAR_VOL = 1.0, 50e6, 1e6   # liquidity filter (locked)
HORIZONS = (3600, 24 * 3600, 3 * 24 * 3600)
GRACE = 6 * 3600
MIN_EVENTS = 100                        # no conclusion before this many events with a +1d result


def get_json(url, timeout=40):
    with urlopen(Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read())


def fetch_mentions(fetch=get_json):
    """All tickers with their mention counts now and 24 h ago -> {ticker: {...}}."""
    first = fetch(APE.format(1))
    rows = list(first["results"])
    for page in range(2, int(first.get("pages", 1)) + 1):
        rows += fetch(APE.format(page))["results"]
    return {r["ticker"]: {"rank": r["rank"], "mentions": r["mentions"], "mentions_24h": r.get("mentions_24h_ago") or 0,
                          "rank_24h": r.get("rank_24h_ago"), "upvotes": r.get("upvotes", 0), "name": r.get("name", "")}
            for r in rows if r.get("ticker") and "." not in r["ticker"]}


def fetch_universe(fetch=get_json):
    """US-listed stocks with market cap, for the liquidity filter and for random controls."""
    out = {}
    for r in fetch(NASDAQ)["data"]["rows"]:
        try:
            cap = float(r["marketCap"] or 0)
        except ValueError:
            cap = 0.0
        out[r["symbol"].strip()] = {"cap": cap, "name": r["name"], "sector": r.get("sector", "")}
    return out


# Tickers that are ordinary English words: social trackers count the word, not the company (seen live: SO, YOU, AM, HR).
WORD_TICKERS = {"A", "I", "IT", "ALL", "ARE", "SO", "YOU", "AM", "HR", "ON", "FOR", "NOW", "OR", "CAN", "HAS", "BE", "BY", "GO",
                "LOVE", "REAL", "TRUE", "OPEN", "ONE", "TWO", "BIG", "NEW", "OLD", "BEST", "GOOD", "WELL", "FAST", "FREE",
                "PLAY", "LIFE", "WORK", "NEXT", "SEE", "HE", "HIS", "WE", "US", "AN", "AS", "AT", "DO", "IF", "IN", "IS",
                "ME", "MY", "NO", "OF", "UP", "KEY", "TOP", "LOW", "HOT", "FUN", "EAT", "RUN", "WAY", "LOT", "ANY", "MAN",
                "CAR", "AI", "CASH", "COST", "DAY", "EVER", "FIT", "FLY", "GOLD", "HOME", "LAND", "LINK", "LOOP", "MAIN",
                "MIND", "MOVE", "PEAK", "PLUS", "RARE", "RISE", "SAFE", "SAVE", "SEED", "SHIP", "SURE", "TEAM", "TREE", "UNIT",
                "VIEW", "WAVE", "WIN", "WOW", "YES", "NYT"}


def same_company(a: dict, b: dict) -> bool:
    """Share classes of one company (GOOG/GOOGL, BRK.A/B...) must never be each other's control."""
    first = lambda n: "".join(c for c in (n or "").lower().split(" ")[0] if c.isalnum())
    return bool(first(a.get("name")) and first(a.get("name")) == first(b.get("name")))


def is_surge(m):
    return m["mentions"] >= MIN_MENTIONS and m["mentions"] >= MIN_RATIO * max(m["mentions_24h"], 5)


def liquid(q):
    return bool(q and q.get("price") and q["price"] >= MIN_PRICE and (q.get("volume") or 0) * q["price"] >= MIN_DOLLAR_VOL
                and q.get("open") is not None)


def _day(ts=None):
    return time.strftime("%Y-%m-%d", time.gmtime(ts or time.time()))


class BuzzMonitor:
    def __init__(self, state_path=None, log_path=None, fetch=get_json, quote=None, headlines=None, rng_seed=None):
        self.state_path = Path(state_path or DATA / "buzz.json")
        self.log_path = Path(log_path or DATA / "buzz_log.jsonl")
        self.fetch = fetch
        self.quote = quote or data.quote
        self.headlines = headlines or self._headlines
        self.rng = random.Random(rng_seed)
        self.lock = threading.RLock()
        self.universe, self.universe_ts = {}, 0.0
        self.last_scan, self.last_error, self.last_top = 0.0, None, []
        self.events, self.seen = [], set()
        if self.state_path.exists():
            d = json.loads(self.state_path.read_text())
            self.events, self.seen = d["events"], set(d["seen"])

    # ---------- storage ----------
    def record(self, kind, **fields):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a") as f:
            f.write(json.dumps({"ts": round(time.time(), 1), "kind": kind, **fields}, default=str) + "\n")

    def save(self):
        with self.lock:
            d = {"events": self.events[-3000:], "seen": sorted(self.seen)[-20000:]}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, default=str))
        tmp.replace(self.state_path)

    @staticmethod
    def _headlines(sym, name):
        try:
            return [{"title": x["title"][:160], "source": x["source"], "lexicon": x["sentiment"]}
                    for x in news.symbol_news(sym, name)["items"][:3]]
        except Exception:  # noqa: BLE001
            return []

    # ---------- scan ----------
    def refresh_universe(self, now):
        if not self.universe or now - self.universe_ts > 24 * 3600:
            self.universe, self.universe_ts = fetch_universe(self.fetch), now

    def scan(self, now=None):
        now = now or time.time()
        self.refresh_universe(now)
        mentions = fetch_mentions(self.fetch)
        self.last_top = sorted(mentions.items(), key=lambda kv: kv[1]["rank"])[:15]
        spy = self.quote("SPY")
        with self.lock:
            fresh = [t for t, m in mentions.items() if is_surge(m) and t not in WORD_TICKERS and t in self.universe
                     and self.universe[t]["cap"] >= MIN_CAP and f"{_day(now)}:{t}" not in self.seen]
        for t in fresh[:30]:                      # bounded work per scan
            self._new_event(t, mentions[t], spy, now)
        self._outcomes(now, spy)
        self.last_scan = now

    def _new_event(self, t, m, spy, now):
        try:
            q = self.quote(t)
        except Exception:  # noqa: BLE001
            return
        with self.lock:
            self.seen.add(f"{_day(now)}:{t}")
        if not liquid(q):
            self.record("skipped", ticker=t, why="not liquid or no quote", mentions=m["mentions"])
            return
        cap = self.universe[t]["cap"]
        pool = [s for s, u in self.universe.items() if s != t and 0.5 * cap <= u["cap"] <= 2 * cap and s not in self.seen
                and not same_company(u, self.universe[t])]
        control = None
        if pool:
            for s in self.rng.sample(sorted(pool), min(5, len(pool))):       # first liquid random match of similar size
                try:
                    cq = self.quote(s)
                except Exception:  # noqa: BLE001
                    continue
                if liquid(cq):
                    control = {"symbol": s, "price": cq["price"]}
                    break
        ev = {"id": f"{_day(now)}-{t}", "ts": now, "ticker": t, "name": self.universe[t]["name"], "cap": cap,
              "mentions": m["mentions"], "mentions_24h": m["mentions_24h"], "rank": m["rank"], "rank_24h": m["rank_24h"],
              "upvotes": m["upvotes"], "price": q["price"], "move_pct": q.get("change_pct"),
              "volume": q.get("volume"), "market_open": bool(q.get("open")), "spy_price": spy.get("price"),
              "control": control, "headlines": self.headlines(t, self.universe[t]["name"]), "out": {}, "out_ctrl": {}}
        with self.lock:
            self.events.append(ev)
        self.record("event", **{k: v for k, v in ev.items() if k not in ("out", "out_ctrl")})

    def _outcomes(self, now, spy):
        if not spy.get("price"):
            return
        for ev in self.events[-600:]:
            for h in HORIZONS:
                age = now - ev["ts"]
                if str(h) in ev["out"] or not (h <= age < h + GRACE):
                    continue
                try:
                    q = self.quote(ev["ticker"])
                except Exception:  # noqa: BLE001
                    continue
                if not q.get("price") or not ev.get("spy_price") or not q.get("open"):   # closed market = stale price
                    continue
                market = spy["price"] / ev["spy_price"] - 1
                ev["out"][str(h)] = round(q["price"] / ev["price"] - 1 - market, 5)
                if ev["control"]:
                    try:
                        cq = self.quote(ev["control"]["symbol"])
                        if cq.get("price"):
                            ev["out_ctrl"][str(h)] = round(cq["price"] / ev["control"]["price"] - 1 - market, 5)
                    except Exception:  # noqa: BLE001
                        pass
                self.record("outcome", id=ev["id"], horizon_s=h, abnormal=ev["out"][str(h)],
                            control=ev["out_ctrl"].get(str(h)))

    # ---------- evaluation ----------
    def evaluate(self, horizon=24 * 3600):
        rows = [(e["out"][str(horizon)], e["out_ctrl"].get(str(horizon))) for e in self.events if str(horizon) in e["out"]]
        out = {"events": len(rows), "needed": MIN_EVENTS, "horizon_h": horizon // 3600}
        if rows:
            v = [r[0] for r in rows]
            out |= {"mean": mean(v), "median": median(v), "share_positive": sum(x > 0 for x in v) / len(v)}
        paired = [(a, c) for a, c in rows if c is not None]
        if paired:
            out["control_mean"] = mean(c for _, c in paired)
        if len(rows) < MIN_EVENTS:
            out["verdict"] = f"too early ({len(rows)}/{MIN_EVENTS} events with a +{horizon // 3600}h result): no conclusion allowed"
            return out
        diff = [a - c for a, c in paired]
        rng = random.Random(20261123)
        boots = sorted(mean(rng.choice(diff) for _ in diff) for _ in range(2000)) if diff else []
        out["diff_ci95"] = (boots[50], boots[1949]) if boots else None
        if boots and boots[50] > 0:
            out["verdict"] = "buzz events beat matched controls (needs a later window)"
        elif boots and boots[1949] < 0:
            out["verdict"] = "buzz events LAG matched controls (reversal after attention)"
        else:
            out["verdict"] = "no difference from matched controls shown"
        return out

    def view(self):
        with self.lock:
            return {"scan_every_s": SCAN_S, "last_scan_age_s": round(time.time() - self.last_scan) if self.last_scan else None,
                    "error": self.last_error, "n_events": len(self.events), "universe": len(self.universe),
                    "top_now": [{"ticker": t, **m} for t, m in self.last_top],
                    "events": self.events[::-1][:40],
                    "eval_1d": self.evaluate(24 * 3600), "eval_1h": self.evaluate(3600),
                    "rule": f"mentions >= {MIN_MENTIONS} and >= {MIN_RATIO}x the 24 h-ago count, US stock with market cap >= "
                            f"${MIN_CAP / 1e6:.0f}M, price >= ${MIN_PRICE:.0f}, dollar volume >= ${MIN_DOLLAR_VOL / 1e6:.0f}M"}


def loop(m: BuzzMonitor, every=SCAN_S):
    time.sleep(30)
    while True:
        try:
            m.scan()
            m.save()
            m.last_error = None
        except Exception as e:  # noqa: BLE001
            m.last_error = str(e)[:200]
            traceback.print_exc()
        time.sleep(every)
