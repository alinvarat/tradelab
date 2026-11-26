"""Forward news-latency collector (protocol_news_latency_fwd_20261126.md). Runs on GitHub Actions only
(workflow news_latency_fwd.yml). Public data, no keys, no orders; the only secret is the Claude Code token, read by the CLI.

    python research/studies/news_latency_fwd.py probe <out_dir>            reachability + timestamp fields, no outcomes
    python research/studies/news_latency_fwd.py run <data_dir> <minutes>   poll loop; refuses unless the protocol hash matches
    python research/studies/news_latency_fwd.py summary <data_dir>         rewrite summary.json from items.jsonl

<data_dir> is a checkout of branch data/news-latency-fwd: state.json, items.jsonl (one final row per item, titles only), summary.json.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core import news_latency_fwd as nl   # noqa: E402

PROTO = ROOT / "research/studies/protocol_news_latency_fwd_20261126.md"
PARAMS = ROOT / "research/news_latency/fwd_params.json"
PROMPT = ROOT / "research/news_latency/fwd_prompt.txt"
SEC_UA = os.environ.get("TRADELAB_SEC_UA", "TradeLab paper research")
UA = "Mozilla/5.0 (X11; Linux x86_64) tradelab-research"
OKX = "https://www.okx.com/api/v5"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers_exchange.json"
EDGAR = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=100&output=atom"
BN = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=20&catalogId="

CANDIDATES = [
    {"name": "sec_8k", "kind": "sec_atom", "url": EDGAR, "market": "stock"},
    {"name": "binance_listings", "kind": "binance", "url": BN + "48", "market": "crypto"},
    {"name": "binance_news", "kind": "binance", "url": BN + "49", "market": "crypto"},
    {"name": "binance_delist", "kind": "binance", "url": BN + "161", "market": "crypto"},
    {"name": "okx_announcements", "kind": "okx_ann", "url": OKX + "/support/announcements", "market": "crypto"},
    {"name": "coindesk", "kind": "rss", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "market": "crypto"},
    {"name": "cointelegraph", "kind": "rss", "url": "https://cointelegraph.com/rss", "market": "crypto"},
    {"name": "decrypt", "kind": "rss", "url": "https://decrypt.co/feed", "market": "crypto"},
    {"name": "theblock", "kind": "rss", "url": "https://www.theblock.co/rss.xml", "market": "crypto"},
    {"name": "bitcoinmagazine", "kind": "rss", "url": "https://bitcoinmagazine.com/feed", "market": "crypto"},
    {"name": "cryptoslate", "kind": "rss", "url": "https://cryptoslate.com/feed/", "market": "crypto"},
    {"name": "prnewswire", "kind": "rss", "url": "https://www.prnewswire.com/rss/news-releases-list.rss", "market": "stock"},
    {"name": "prnewswire_fin", "kind": "rss", "url": "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss", "market": "stock"},
    {"name": "globenewswire", "kind": "rss", "url": "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies", "market": "stock"},
    {"name": "globenewswire_all", "kind": "rss", "url": "https://www.globenewswire.com/RssFeed/subjectcode/42-Earnings%20Releases%20And%20Operating%20Results/feedTitle/GlobeNewswire%20-%20Earnings%20Releases%20And%20Operating%20Results", "market": "stock"},
    {"name": "businesswire", "kind": "rss", "url": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpRWA==", "market": "stock"},
]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


def http(url, timeout=10, ua=UA):
    """-> (status, body bytes, t_received, headers) ; status 0 on a network error (body = error text)."""
    try:
        with urlopen(Request(url, headers={"User-Agent": ua, "Accept": "*/*"}), timeout=timeout) as r:
            body = r.read()
            return r.status, body, time.time(), dict(r.headers)
    except Exception as e:   # noqa: BLE001
        code = getattr(e, "code", 0)
        return code, f"{type(e).__name__} {e}"[:200].encode(), time.time(), {}


def fetch_json(url, timeout=10, ua=UA):
    st, body, _, _ = http(url, timeout, ua)
    if st != 200:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def parse_source(src, body):
    k = src["kind"]
    if k == "sec_atom":
        items = nl.parse_edgar_atom(body)
    elif k == "rss":
        items = nl.parse_rss(body, src["name"])
    elif k == "binance":
        items = nl.parse_binance(json.loads(body), src["name"])
    elif k == "okx_ann":
        items = nl.parse_okx_announcements(json.loads(body), src["name"])
    else:
        raise ValueError(k)
    for it in items:
        it["source"], it["market"] = src["name"], src["market"]
    return items


# ------------------------------------------------------------------ prices
def okx_bars(inst, t0, t1):
    """1-minute bars covering [t0, t1] from OKX (recent endpoint first, then history)."""
    for ep in ("candles", "history-candles"):
        d = fetch_json(f"{OKX}/market/{ep}?instId={inst}-USDT-SWAP&bar=1m&before={int(t0 * 1000) - 1}&after={int(t1 * 1000) + 1}&limit=100", 15)
        bars = nl.parse_okx_candles(d) if d else []
        if bars:
            return bars
    return []


def yahoo_bars(sym, t0, t1):
    d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym)}?interval=1m&period1={int(t0)}&period2={int(t1)}&includePrePost=true", 15)
    return nl.parse_yahoo_chart(d)[0] if d else []


def snapshot(market, inst):
    """Live price at the call: crypto OKX ticker (bid/ask/last), stocks Yahoo regularMarketPrice and its own time."""
    t_req = time.time()
    if market == "crypto":
        d = fetch_json(f"{OKX}/market/ticker?instId={inst}-USDT-SWAP", 8)
        r = ((d or {}).get("data") or [None])[0]
        if not r:
            return None
        return {"t_req": t_req, "t_resp": time.time(), "price": float(r["last"]), "price_t": int(r["ts"]) / 1000.0,
                "bid": float(r["bidPx"]), "ask": float(r["askPx"])}
    d = fetch_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(inst)}?interval=1m&period1={int(t_req) - 900}&period2={int(t_req) + 60}&includePrePost=true", 8)
    meta = nl.parse_yahoo_chart(d)[1] if d else {}
    if not meta.get("regularMarketPrice"):
        return None
    return {"t_req": t_req, "t_resp": time.time(), "price": float(meta["regularMarketPrice"]),
            "price_t": float(meta.get("regularMarketTime") or 0) or None, "bid": None, "ask": None}


def fetch_bars(it):
    t0, t1 = int((it["t_pub"] - 300) // 60 * 60), it["t_pub"] + 3660
    f = okx_bars if it["market"] == "crypto" else yahoo_bars
    return f(it["instrument"], t0, t1)


# ------------------------------------------------------------------ probe
def probe(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rep = {"t_probe": time.time(), "sources": {}, "prices": {}}
    for src in CANDIDATES:
        ua = SEC_UA if "sec.gov" in src["url"] else UA
        t = time.time()
        st, body, t_rx, hdr = http(src["url"], 15, ua)
        row = {"status": st, "bytes": len(body), "secs": round(t_rx - t, 2), "market": src["market"],
               "server_date": hdr.get("Date")}
        if st == 200:
            try:
                items = parse_source(src, body)
                row["parsed"] = len(items)
                row["items_with_ts"] = sum(1 for i in items if i["t_pub"])
                row["resolution"] = sorted({i["res"] for i in items if i["res"]})
                row["newest"] = [{"title": i["title"][:70], "raw_ts": i.get("raw_ts") or i.get("link", "")[-40:], "age_s": round(t_rx - i["t_pub"]) if i["t_pub"] else None}
                                 for i in sorted(items, key=lambda i: -(i["t_pub"] or 0))[:3]]
                if src["kind"] == "sec_atom" and items:
                    row["sample_items_field"] = items[0].get("items"), items[0].get("summary", "")[:160]
            except Exception as e:   # noqa: BLE001
                row["parse_error"] = f"{type(e).__name__} {e}"[:160]
        else:
            row["error"] = body[:120].decode("utf-8", "replace")
        rep["sources"][src["name"]] = row
        log(src["name"], row.get("status"), row.get("parsed"), row.get("resolution"))
    now = time.time()
    p = rep["prices"]
    d = fetch_json(OKX + "/public/instruments?instType=SWAP", 15)
    p["okx_swap_bases"] = len(nl.okx_perp_bases(d)) if d else 0
    b = okx_bars("BTC", now - 3900, now - 300)
    p["okx_btc_bars_65m"] = len(b)
    p["okx_btc_last_bar_age_s"] = round(now - b[-1][0]) if b else None
    p["okx_ticker"] = snapshot("crypto", "BTC")
    yb = yahoo_bars("AAPL", now - 3900, now)
    p["yahoo_aapl_bars_65m"] = len(yb)
    p["yahoo_aapl_last_bar_age_s"] = round(now - yb[-1][0]) if yb else None
    p["yahoo_snapshot"] = snapshot("stock", "AAPL")
    st, body, _, _ = http(SEC_TICKERS, 20, SEC_UA)
    p["sec_ticker_map"] = len(nl.cik_ticker_map(json.loads(body))) if st == 200 else f"HTTP {st}"
    st, _, t_rx, hdr = http("https://www.okx.com/api/v5/public/time", 8)
    p["clock_vs_okx_ms"] = None
    try:
        d = json.loads(_)
        p["clock_vs_okx_ms"] = round((t_rx - int(d["data"][0]["ts"]) / 1000.0) * 1000)
    except Exception:   # noqa: BLE001
        pass
    (out / "probe.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


# ------------------------------------------------------------------ run
def check_lock():
    want = PROTO.with_suffix(".sha256").read_text().strip()
    if hashlib.sha256(PROTO.read_bytes()).hexdigest() != want:
        sys.exit("protocol hash mismatch: refusing to collect")
    P = json.loads(PARAMS.read_text())
    for path in (PARAMS, PROMPT):
        if hashlib.sha256(path.read_bytes()).hexdigest() not in PROTO.read_text():
            sys.exit(f"{path.name} hash not in the locked protocol: refusing to collect")
    return P


def atomic_write(path, text):
    tmp = str(path) + ".tmp"
    Path(tmp).write_text(text)
    os.replace(tmp, path)


def publish(dd, msg):
    def git(*a):
        return subprocess.run(["git", "-C", str(dd), *a], capture_output=True, text=True)
    git("config", "user.name", "tradelab-research")
    git("config", "user.email", "tradelab-research@users.noreply.github.com")
    git("add", "-A")
    git("commit", "-qm", msg)
    for _ in range(3):
        if git("push", "-q", "origin", "HEAD:data/news-latency-fwd").returncode == 0:
            return True
        git("fetch", "-q", "origin", "data/news-latency-fwd")
        git("rebase", "-q", "origin/data/news-latency-fwd")
    log("publish failed")
    return False


class Collector:
    def __init__(self, dd, P):
        self.dd, self.P = Path(dd), P
        self.sf = self.dd / "state.json"
        st = json.loads(self.sf.read_text()) if self.sf.exists() else {}
        self.seen = st.get("seen", {})            # key -> t_seen
        self.pending = st.get("pending", {})      # key -> item awaiting its +60 min path
        self.calls = st.get("calls", {})          # "YYYY-MM-DD" -> {"stock": n, "crypto": n}
        self.first = {}                           # source -> True once its first poll of this run is done
        self.cik, self.perps, self.perps_t, self.cik_t = {}, set(), 0, 0
        self.system = PROMPT.read_text()
        self.polls = ThreadPoolExecutor(8)
        self.work = ThreadPoolExecutor(P["claude_parallel"] + 2)
        self.futs = []

    def save(self):
        atomic_write(self.sf, json.dumps({"seen": self.seen, "pending": self.pending, "calls": self.calls}))

    def final(self, it):
        it.pop("text", None)          # titles only on the data branch (AGENTS rule 9)
        it["desc"] = (it.get("desc") or "")[:160]
        it.pop("summary", None)
        with open(self.dd / "items.jsonl", "a") as f:
            f.write(json.dumps(it, separators=(",", ":")) + "\n")

    def refresh_refs(self):
        now = time.time()
        if now - self.perps_t > 1800:
            d = fetch_json(OKX + "/public/instruments?instType=SWAP", 15)
            if d:
                self.perps, self.perps_t = nl.okx_perp_bases(d), now
        if now - self.cik_t > 6 * 3600 or not self.cik:
            st, body, _, _ = http(SEC_TICKERS, 20, SEC_UA)
            if st == 200:
                self.cik, self.cik_t = nl.cik_ticker_map(json.loads(body)), now

    def poll(self, src):
        ua = SEC_UA if "sec.gov" in src["url"] else UA
        st, body, t_rx, _ = http(src["url"], 10, ua)
        if st != 200:
            return src, None, t_rx
        try:
            return src, parse_source(src, body), t_rx
        except Exception as e:   # noqa: BLE001
            log("parse", src["name"], type(e).__name__)
            return src, None, t_rx

    def intake(self, src, items, t_rx):
        cold = src["name"] not in self.first
        self.first[src["name"]] = True
        for it in items:
            if it["key"] in self.seen:
                continue
            self.seen[it["key"]] = t_rx
            it.update(t_seen=t_rx, cold=cold, poll_s=src["poll_s"])
            if cold or not it["t_pub"]:
                it["status"] = "cold_start" if cold else "bad_ts"
                self.final(it)
                continue
            self.route(it)

    def route(self, it):
        day = nl.day_utc(it["t_pub"])
        c = self.calls.setdefault(day, {"stock": 0, "crypto": 0})
        mk = it["market"]
        if mk == "stock":
            tk, why = nl.stock_candidate(it, self.cik)
            if not tk:
                it["status"] = why
            elif not nl.in_rth(it["t_pub"]):
                it["status"] = "outside_rth"
            else:
                it["instrument"] = tk
        if "status" not in it and c[mk] >= self.P["daily_cap"][mk]:
            it["status"] = "skipped_cap"
        if "status" in it:
            self.final(it)
            return
        c[mk] += 1
        it["status"] = "scored"
        self.futs.append(self.work.submit(self.process, it))

    def process(self, it):
        try:
            if it["source"].startswith("sec"):
                it["text"] = self.edgar_text(it)
            it["t_text_ready"] = time.time()
            from core import ai_news
            user = self.user_msg(it)
            it["t_llm_start"] = time.time()
            text, served = ai_news.chat(self.system, user, timeout=90)
            it["t_llm"] = time.time()
            it["model"] = served
            r = nl.parse_haiku(text)
            if r is None:
                it["llm_err"] = (served if not text else "unparseable")[:120]
            else:
                it["llm"] = r
                if it["market"] == "crypto":
                    base = r["instrument"]
                    if base in self.perps and r["direction"] != "none":
                        it["instrument"] = base
                    elif r["direction"] != "none":
                        it["status"] = "no_instrument"
                if r["direction"] != "none" and it.get("instrument") and it["status"] == "scored":
                    wait = it["t_llm"] + 5 - time.time()
                    if wait > 0:
                        time.sleep(wait)
                    it["snap"] = snapshot(it["market"], it["instrument"])
        except Exception as e:   # noqa: BLE001
            it["llm_err"] = f"{type(e).__name__}"
        return it

    def user_msg(self, it):
        if it["source"].startswith("sec"):
            return (f"Source: SEC EDGAR 8-K just filed\nCompany: {it['company']} (ticker {it['instrument']})\nItems: {', '.join(it.get('items') or []) or 'unknown'}\n"
                    f"Filing text (start):\n{it.get('text') or it.get('summary', '')}")
        if it["market"] == "stock":
            return f"Source: {it['source']} press release\nTraded ticker: {it['instrument']}\nTitle: {it['title']}\nSummary: {it.get('desc', '')}"
        return f"Source: {it['source']}\nTitle: {it['title']}\nSummary: {it.get('desc', '')}"

    def edgar_text(self, it):
        st, body, _, _ = http(it["link"], 10, SEC_UA)
        if st != 200:
            return ""
        import re
        links = re.findall(r'href="(/Archives/edgar/data/[^"]+\.htm)"', body.decode("utf-8", "replace"))
        links = [h for h in links if "-index" not in h]
        pick = next((h for h in links if re.search(r"ex-?99", h, re.I)), links[0] if links else None)
        if not pick:
            return ""
        time.sleep(0.15)
        st, body, _, _ = http("https://www.sec.gov" + pick, 10, SEC_UA)
        return nl.strip_html(body[:300000].decode("utf-8", "replace"), self.P["text_chars"]) if st == 200 else ""

    def collect_done(self):
        keep = []
        for f in self.futs:
            if not f.done():
                keep.append(f)
                continue
            it = f.result()
            if it["status"] == "scored" and it.get("instrument") and (it.get("llm") or {}).get("direction") in ("up", "down"):
                self.pending[it["key"]] = it
            else:
                self.final(it)
        self.futs = keep

    def settle(self, flush=False):
        now = time.time()
        for key, it in list(self.pending.items()):
            if now >= it["t_pub"] + 3600 + 120 or flush:
                it["bars"] = fetch_bars(it)
                self.final(it)
                del self.pending[key]

    def loop(self, minutes):
        end = time.time() + minutes * 60
        nxt = {s["name"]: 0 for s in self.P["sources"]}
        last_pub = time.time()
        pend = []
        while time.time() < end:
            self.refresh_refs()
            now = time.time()
            for s in self.P["sources"]:
                if now >= nxt[s["name"]]:
                    nxt[s["name"]] = now + s["poll_s"]
                    pend.append(self.polls.submit(self.poll, s))
            still = []
            for f in pend:
                if f.done():
                    src, items, t_rx = f.result()
                    if items is not None:
                        self.intake(src, items, t_rx)
                else:
                    still.append(f)
            pend = still
            self.collect_done()
            self.settle()
            self.save()
            if time.time() - last_pub > 1200:
                last_pub = time.time()
                publish(self.dd, f"news latency forward: {time.strftime('%FT%TZ', time.gmtime())}")
            time.sleep(1)
        for f in self.futs:
            f.result(timeout=120)
        self.collect_done()
        self.settle()


def summary(dd):
    dd = Path(dd)
    P = json.loads(PARAMS.read_text())
    rows = [json.loads(l) for l in open(dd / "items.jsonl")] if (dd / "items.jsonl").exists() else []
    out = nl.summarize(rows, P)
    out["items_total"] = len(rows)
    try:
        from core import ai_news
        out["llm_spend_this_process"] = ai_news.spend()
    except Exception:   # noqa: BLE001
        pass
    atomic_write(dd / "summary.json", json.dumps(out, indent=1, default=str))
    return out


def run(dd, minutes):
    P = check_lock()
    os.environ["TRADELAB_CLAUDE_PARALLEL"] = str(P["claude_parallel"])
    Path(dd).mkdir(parents=True, exist_ok=True)
    c = Collector(dd, P)
    try:
        c.loop(minutes)
    finally:
        c.save()
        summary(dd)
        publish(dd, f"news latency forward: end of run {time.strftime('%FT%TZ', time.gmtime())}")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "probe":
        probe(sys.argv[2])
    elif mode == "run":
        run(sys.argv[2], float(sys.argv[3]))
    elif mode == "summary":
        print(json.dumps(summary(sys.argv[2]), indent=1, default=str))
