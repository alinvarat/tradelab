"""Always-on news ingestion inside the Kuber pod (stdlib only): the fastest free feeds with no account, a websocket push
channel, and Claude Haiku timing. It only MEASURES and LOGS. Since protocol v4.19 (2026-11-27) the trader reads its append-only
day files and view() READ-ONLY through core/desk_feeds.py (this module and its row format are unchanged); until v4.18 it did not
feed the trader.

For every new item it records t_pub (the source's own time), t_seen (when this pod first held the item) and t_llm (when
the Haiku read of it came back), into DIR/news_ingest/YYYYMMDD.jsonl, and /api/news_latency ("ingest" key) shows the
median and p90 of t_seen - t_pub per source. The locked collector (research/studies/news_latency_fwd.py, branch
data/news-latency-fwd) is not touched; this runs beside it and its protocol/prompt are not reused or edited.

Sources (checked 2026-11-26, none needs an account or key):
  sec_8k        EDGAR getcurrent Atom, every 2 s (fair access is 10 req/s), declared User-Agent from TRADELAB_SEC_UA
  prnewswire    RSS, conditional GET (ETag / If-Modified-Since) every 3 s
  globenewswire RSS, conditional GET every 5 s
  businesswire  RSS, conditional GET every 5 s
  binance_*     public CMS announcement lists, every 8-20 s (429 seen at 3 s)
  okx_announcements  public REST, every 3 s
  eqn_ws        EquationNews (BWEnews-style crypto newswire) public websocket push, no key
  eqn_rest      the same newswire over REST with ETag, every 3 s (its docs allow 1 req/s)
For eqn_*, t_pub is the newswire's own timestamp (when it relayed the story), not the original source's time.
Request rate is about 2.5 req/s in total; errors back off exponentially (403/429 wait at least 60 s)."""
import base64
import gzip
import json
import os
import random
import shutil
import socket
import ssl
import struct
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from . import news_latency_fwd as nl
from . import news_publish

DIR = Path(os.environ.get("TRADELAB_NEWS_INGEST_DIR")
           or Path(os.environ.get("TRADELAB_COLLECT_DIR") or Path(__file__).resolve().parent.parent / "data/collect") / "news_ingest")
KEEP_DAYS = 14
MIN_FREE_BYTES = 200e6
WINDOW_S = 24 * 3600
MAX_ROWS_PER_SOURCE = 3000
BACKOFF_MAX_S = 300
BLOCKED_BACKOFF_S = 60
UA = "Mozilla/5.0 (X11; Linux x86_64) tradelab-research"
LLM_TIMEOUT_S = 40
LLM_QUEUE_MAX = 20
SEC_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&start=0&count=100&output=atom"
BN = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo=1&pageSize=20&catalogId="
OKX_ANN = "https://www.okx.com/api/v5/support/announcements"
EQN_REST = "https://api.eqn.news/public/v1/news?limit=20"
EQN_WS = "wss://api.eqn.news/public/ws"
GNW = "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/GlobeNewswire%20-%20News%20about%20Public%20Companies"

SYSTEM = ("You read one fresh news item and judge the likely direction of the single most affected tradable instrument over "
          "the next 5 minutes. Reply with ONLY a JSON object: {\"direction\": \"up\" | \"down\" | \"none\", \"confidence\": "
          "0-100, \"instrument\": \"TICKER or coin symbol, or null\"}. Use \"none\" when the item is not clearly market-moving.")

_lock = threading.RLock()


# ------------------------------------------------------------------ pure helpers (tested offline)
def percentile(xs, q):
    """Linear-interpolated percentile (q in 0..100) of a list; None when empty."""
    s = sorted(xs)
    if not s:
        return None
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * q / 100.0
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _r(x):
    return None if x is None else round(x, 2)


def lat_summary(rows):
    """rows: [(t_seen, lat_s, res)] -> median/p90 of seen-published over rows with second resolution. Minute-resolution
    timestamps (true time up to 59 s later) are counted but kept out of the statistics."""
    sec = [r[1] for r in rows if r[2] != "m"]
    return {"n": len(sec), "n_minute_res": len(rows) - len(sec), "median_s": _r(percentile(sec, 50)),
            "p90_s": _r(percentile(sec, 90)), "n_negative": sum(1 for x in sec if x < 0)}


def backoff_s(every, errors, status=0):
    """Seconds to wait after `errors` consecutive failures: exponential, capped, and long for a block (403/429)."""
    if errors <= 0:
        return every
    wait = min(BACKOFF_MAX_S, every * (2 ** min(errors, 8)))
    if status in (403, 429):
        wait = max(wait, BLOCKED_BACKOFF_S)
    return min(BACKOFF_MAX_S, wait)


def parse_eqn_rest(body):
    out = []
    for i in json.loads(body).get("items") or []:
        t_pub, res = nl.parse_ts(i.get("time"))
        out.append({"key": f"eqn:{i.get('no')}", "title": str(i.get("en") or i.get("zh") or "")[:300],
                    "link": i.get("url") or "", "t_pub": t_pub, "res": res, "coins": i.get("coins") or []})
    return out


def parse_eqn_frame(text):
    """One websocket frame -> item dict, or None for pong / non-JSON / a frame without a headline."""
    if not text or text.strip() == "pong":
        return None
    try:
        d = json.loads(text)
    except ValueError:
        return None
    if not isinstance(d, dict) or not d.get("news_title"):
        return None
    ts = d.get("timestamp")
    t_pub = float(ts) if isinstance(ts, (int, float)) else None
    return {"key": f"eqn:{d.get('url') or d['news_title']}|{ts}", "title": str(d["news_title"])[:300], "link": d.get("url") or "",
            "t_pub": t_pub, "res": "s" if t_pub else None, "coins": d.get("coins_included") or []}


def eligible_for_llm(source, market, it):
    """Cheap deterministic filter before a Haiku call, so the plan's capacity is spent on items that can matter."""
    if market == "crypto":
        return True
    if source == "sec_8k":
        its = it.get("items") or []
        return bool(set(its) & nl.MATERIAL_8K_ITEMS) if its else False
    return bool(nl.ticker_from_text(it.get("title"), it.get("desc")))


# ------------------------------------------------------------------ minimal websocket client (the image has no ws library)
class Ws:
    """RFC 6455 client over TLS: text frames, ping/pong, close, fragmentation. Not a general library."""

    def __init__(self, url, timeout=45, sock=None):
        self.url, self.timeout, self.sock, self.buf = url, timeout, sock, b""

    def open(self):
        u = urlparse(self.url)
        s = socket.create_connection((u.hostname, u.port or 443), 10)
        s = ssl.create_default_context().wrap_socket(s, server_hostname=u.hostname)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.hostname}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nUser-Agent: {UA}\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            d = s.recv(4096)
            if not d:
                raise EOFError("closed during handshake")
            buf += d
            if len(buf) > 16384:
                raise ValueError("handshake too long")
        head, _, self.buf = buf.partition(b"\r\n\r\n")
        line = head.split(b"\r\n")[0].decode(errors="replace")
        if " 101 " not in line + " ":
            raise ConnectionError("websocket handshake: " + line[:80])
        s.settimeout(self.timeout)
        self.sock = s

    def _read(self, n):
        while len(self.buf) < n:
            d = self.sock.recv(65536)
            if not d:
                raise EOFError("closed")
            self.buf += d
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    @staticmethod
    def frame(op, payload=b""):
        mask = os.urandom(4)
        n = len(payload)
        head = bytes([0x80 | op])
        head += bytes([0x80 | n]) if n < 126 else b"\xfe" + struct.pack(">H", n) if n < 65536 else b"\xff" + struct.pack(">Q", n)
        return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    def send_text(self, text):
        self.sock.sendall(self.frame(1, text.encode()))

    def recv_text(self):
        """Next complete text message (str). Answers ping, ignores pong, raises EOFError on close. The socket timeout
        raises socket.timeout, which the caller treats as a dead connection."""
        parts, started = b"", False
        while True:
            h = self._read(2)
            fin, op, n = h[0] & 0x80, h[0] & 15, h[1] & 127
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if n > 4_000_000:
                raise ValueError("frame too large")
            payload = self._read(n)
            if op == 8:
                raise EOFError("close frame")
            if op == 9:
                self.sock.sendall(self.frame(10, payload))
                continue
            if op == 10:
                continue
            if op in (1, 2):
                parts, started = payload, True
            elif op == 0 and started:
                parts += payload
            if fin and started:
                return parts.decode("utf-8", "replace")

    def close(self):
        try:
            self.sock.close()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ state
def _new_stat():
    return {"polls": 0, "ok": 0, "not_modified": 0, "errors": 0, "consecutive_errors": 0, "last_status": None,
            "last_ok_ts": None, "last_error": None, "next_wait_s": None, "new_items": 0, "cold_items": 0}


STATE = {"started": None, "sources": {}, "llm": {"enabled": False, "calls": 0, "ok": 0, "failed": 0, "dropped": 0,
                                                 "reason": None, "last_error": None, "per_hour_cap": 0},
         "log_errors": 0, "log_paused_low_disk": False}
ROWS = {}        # source -> deque[(t_seen, lat_s, res)]
LLM_ROWS = {}    # source -> deque[(t_seen, llm_s)]  (t_llm - t_seen)
TOTAL_ROWS = {}  # source -> deque[(t_seen, t_llm - t_pub)]
SEEN = {}        # source -> {key: t}
_llm_times = deque()
_llm_queue = deque()


def reset():
    """Tests only."""
    with _lock:
        STATE.update(started=None, sources={}, log_errors=0, log_paused_low_disk=False)
        STATE["llm"] = {"enabled": False, "calls": 0, "ok": 0, "failed": 0, "dropped": 0, "reason": None, "last_error": None,
                        "per_hour_cap": 0}
        for d in (ROWS, LLM_ROWS, TOTAL_ROWS, SEEN):
            d.clear()
        _llm_times.clear()
        _llm_queue.clear()


def _stat(name):
    return STATE["sources"].setdefault(name, _new_stat())


def sources():
    """The poll list. SEC is left out (not guessed at) when no declared User-Agent is configured."""
    out = [
        {"name": "prnewswire", "kind": "rss", "url": "https://www.prnewswire.com/rss/news-releases-list.rss", "every": 3, "market": "stock"},
        {"name": "globenewswire", "kind": "rss", "url": GNW, "every": 5, "market": "stock"},
        {"name": "businesswire", "kind": "rss", "url": "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpRWA==", "every": 5, "market": "stock"},
        {"name": "binance_listings", "kind": "binance", "url": BN + "48", "every": 8, "market": "crypto"},
        {"name": "binance_news", "kind": "binance", "url": BN + "49", "every": 8, "market": "crypto"},
        {"name": "binance_delist", "kind": "binance", "url": BN + "161", "every": 20, "market": "crypto"},
        {"name": "okx_announcements", "kind": "okx", "url": OKX_ANN, "every": 3, "market": "crypto"},
        {"name": "eqn_rest", "kind": "eqn", "url": EQN_REST, "every": 3, "market": "crypto"},
    ]
    sec_ua = os.environ.get("TRADELAB_SEC_UA")
    if sec_ua:
        out.insert(0, {"name": "sec_8k", "kind": "sec", "url": SEC_URL, "every": 2, "market": "stock", "ua": sec_ua})
    else:
        _stat("sec_8k")["last_error"] = "disabled: TRADELAB_SEC_UA (declared User-Agent) is not set"
    return out


def parse(src, body):
    k = src["kind"]
    if k == "sec":
        return nl.parse_edgar_atom(body)
    if k == "rss":
        return nl.parse_rss(body, src["name"])
    if k == "binance":
        return nl.parse_binance(json.loads(body), src["name"])
    if k == "okx":
        return nl.parse_okx_announcements(json.loads(body), src["name"])
    if k == "eqn":
        return parse_eqn_rest(body)
    raise ValueError("unknown kind " + k)


# ------------------------------------------------------------------ logging
def _day(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y%m%d")


def log_row(row, now=None):
    now = now or time.time()
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(DIR).free < MIN_FREE_BYTES:
            STATE["log_paused_low_disk"] = True
            return
        STATE["log_paused_low_disk"] = False
        with open(DIR / f"{_day(now)}.jsonl", "a") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        STATE["log_errors"] += 1


def prune_logs(now=None, keep_days=KEEP_DAYS):
    cutoff = _day((now or time.time()) - keep_days * 86400)
    if DIR.exists():
        for f in DIR.glob("*.jsonl"):
            if f.stem < cutoff:
                try:
                    f.unlink()
                except OSError:
                    pass


def reload_window(now=None):
    """After a restart: rebuild the 24 h statistics from the log so the endpoint does not start empty."""
    now = now or time.time()
    if not DIR.exists():
        return
    for f in sorted(DIR.glob("*.jsonl"))[-2:]:
        try:
            lines = f.read_text().splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("t_seen") is None or now - r["t_seen"] > WINDOW_S:
                continue
            s = r.get("source")
            if r.get("event") == "item" and r.get("t_pub") is not None:
                ROWS.setdefault(s, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((r["t_seen"], r["t_seen"] - r["t_pub"], r.get("res")))
            elif r.get("event") == "llm" and r.get("llm_s") is not None:
                LLM_ROWS.setdefault(s, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((r["t_seen"], r["llm_s"]))
                if r.get("t_pub") is not None and r.get("t_llm") is not None:
                    TOTAL_ROWS.setdefault(s, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((r["t_seen"], r["t_llm"] - r["t_pub"]))


# ------------------------------------------------------------------ recording and Haiku timing
def record_item(src, it, t_seen, cold=False):
    """Count a first-seen item. Items already in the first fetch of a source are cold (their t_seen is not a latency)."""
    name = src["name"]
    with _lock:
        seen = SEEN.setdefault(name, {})
        if it["key"] in seen:
            return False
        seen[it["key"]] = t_seen
        if len(seen) > 1500:
            for k in sorted(seen, key=seen.get)[:500]:
                del seen[k]
        st = _stat(name)
        if cold:
            st["cold_items"] += 1
            return False
        st["new_items"] += 1
        lat = None if it.get("t_pub") is None else t_seen - it["t_pub"]
        if lat is not None:
            ROWS.setdefault(name, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((t_seen, lat, it.get("res")))
    row = {"event": "item", "source": name, "key": it["key"], "title": it.get("title", "")[:200], "t_pub": it.get("t_pub"),
           "res": it.get("res"), "t_seen": t_seen, "lat_s": None if lat is None else round(lat, 3)}
    log_row(row, t_seen)
    if lat is not None and llm_enabled() and eligible_for_llm(name, src["market"], it):
        enqueue_llm(src, it, t_seen)
    return True


def llm_enabled():
    from . import ai_news
    ok = ai_news.claude_ready()
    cap = int(os.environ.get("TRADELAB_NEWS_INGEST_LLM_PER_HOUR", "40"))
    STATE["llm"].update(enabled=ok and cap > 0, per_hour_cap=cap,
                        reason=None if ok and cap > 0 else "Claude not configured or cap 0 (log only)")
    return ok and cap > 0


def enqueue_llm(src, it, t_seen):
    now = time.time()
    with _lock:
        while _llm_times and now - _llm_times[0] > 3600:
            _llm_times.popleft()
        if len(_llm_times) >= STATE["llm"]["per_hour_cap"] or len(_llm_queue) >= LLM_QUEUE_MAX:
            STATE["llm"]["dropped"] += 1
            return False
        _llm_times.append(now)
        _llm_queue.append((src["name"], it, t_seen))
        return True


def llm_one(name, it, t_seen, chat=None, now=time.time):
    """Ask Haiku about one item; log t_llm. `chat` defaults to ai_news.chat (Claude Haiku 5.5 only)."""
    from . import ai_news
    chat = chat or ai_news.chat
    text, model = chat(SYSTEM, "SOURCE: %s\nHEADLINE: %s\n%s" % (name, it.get("title", ""), (it.get("desc") or it.get("summary") or "")[:600]),
                       timeout=LLM_TIMEOUT_S, model=ai_news.CLAUDE_MODEL)
    t_llm = now()
    parsed = nl.parse_haiku(text)
    with _lock:
        STATE["llm"]["calls"] += 1
        if parsed is None:
            STATE["llm"]["failed"] += 1
            STATE["llm"]["last_error"] = (model if not text else "unreadable reply")[:120]
        else:
            STATE["llm"]["ok"] += 1
            LLM_ROWS.setdefault(name, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((t_seen, t_llm - t_seen))
            if it.get("t_pub") is not None:
                TOTAL_ROWS.setdefault(name, deque(maxlen=MAX_ROWS_PER_SOURCE)).append((t_seen, t_llm - it["t_pub"]))
    row = {"event": "llm", "source": name, "key": it["key"], "t_pub": it.get("t_pub"), "t_seen": t_seen, "t_llm": t_llm,
           "llm_s": round(t_llm - t_seen, 3), "model": str(model)[:60], "parsed": parsed}
    log_row(row, t_llm)
    return row


def llm_worker():
    while True:
        job = None
        with _lock:
            if _llm_queue:
                job = _llm_queue.popleft()
        if job is None:
            time.sleep(0.5)
            continue
        try:
            llm_one(*job)
        except Exception as exc:  # noqa: BLE001
            STATE["llm"]["last_error"] = repr(exc)[:120]


# ------------------------------------------------------------------ polling and websocket loops
def fetch(url, headers, timeout=10):
    """-> (status, body, t_received, response headers). 304 is a normal answer; status 0 = network error."""
    h = {"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip", **headers}
    try:
        with urlopen(Request(url, headers=h), timeout=timeout) as r:
            body = r.read()
            t = time.time()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status, body, t, dict(r.headers)
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", 0) or 0, (f"{type(e).__name__}"[:60]).encode(), time.time(), {}


def poll_step(src, cond, fetch_fn=fetch):
    """One poll of one source. `cond` is that source's conditional-GET and first-fetch state. -> seconds to wait."""
    name, every = src["name"], src["every"]
    st = _stat(name)
    headers = {"User-Agent": src["ua"]} if src.get("ua") else {}
    if cond.get("etag"):
        headers["If-None-Match"] = cond["etag"]
    if cond.get("modified"):
        headers["If-Modified-Since"] = cond["modified"]
    status, body, t_rx, hdr = fetch_fn(src["url"], headers)
    st["polls"] += 1
    st["last_status"] = status
    if status == 304:
        st["not_modified"] += 1
        st["consecutive_errors"] = 0
        st["last_ok_ts"] = t_rx
        return every
    err = None
    if status == 200:
        try:
            items = parse(src, body)
        except Exception as exc:  # noqa: BLE001
            err = f"parse {type(exc).__name__}"
            items = []
    else:
        err = f"http {status}" if status else "network " + body.decode("utf-8", "replace")
    if err:
        st["errors"] += 1
        st["consecutive_errors"] += 1
        st["last_error"] = err
        wait = backoff_s(every, st["consecutive_errors"], status)
    else:
        st["ok"] += 1
        st["consecutive_errors"] = 0
        st["last_ok_ts"] = t_rx
        cond["etag"] = hdr.get("ETag") or hdr.get("Etag") or cond.get("etag")
        cond["modified"] = hdr.get("Last-Modified") or cond.get("modified")
        first = not cond.get("done")
        for it in items:
            record_item(src, it, t_rx, cold=first)
        cond["done"] = True
        wait = every
    st["next_wait_s"] = round(wait, 1)
    return wait


def poll_loop(src):
    cond = {}
    while True:
        try:
            wait = poll_step(src, cond)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            wait = BACKOFF_MAX_S / 5
        time.sleep(wait * random.uniform(0.9, 1.1))


def ws_loop(url=EQN_WS, connect=None):
    """Push channel with exponential-backoff reconnect (1, 2, 4 ... 30 s, plus jitter). Sends the text 'ping' every 25 s as
    the service's docs ask. Items that arrive in the first 3 s after (re)connect are not counted as push latency if their
    own timestamp is older (no replay is promised; the REST poll fills gaps)."""
    src = {"name": "eqn_ws", "market": "crypto"}
    errors = 0
    while True:
        st = _stat("eqn_ws")
        ws = (connect or Ws)(url) if connect else Ws(url)
        try:
            ws.open()
            st["polls"] += 1
            st["last_ok_ts"] = time.time()
            st["last_status"] = 101
            errors = 0
            last_ping = time.time()
            ws.sock.settimeout(10)
            while True:
                try:
                    text = ws.recv_text()
                except socket.timeout:
                    text = None
                now = time.time()
                if now - last_ping > 25:
                    ws.send_text("ping")
                    last_ping = now
                if text is None:
                    if now - st["last_ok_ts"] > 90:
                        raise TimeoutError("no frame or ping for 90 s")
                    continue
                st["last_ok_ts"] = now
                it = parse_eqn_frame(text)
                if it:
                    record_item(src, it, now)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            st["errors"] += 1
            st["consecutive_errors"] = errors
            st["last_error"] = f"{type(exc).__name__} {str(exc)[:60]}"
        finally:
            ws.close()
        wait = min(30, 2 ** min(errors, 5)) * random.uniform(1.0, 1.3)
        st["next_wait_s"] = round(wait, 1)
        time.sleep(wait)


# ------------------------------------------------------------------ view and loop
def view(now=None):
    now = now or time.time()
    out_sources, all_rows = {}, []
    with _lock:
        names = sorted(set(STATE["sources"]) | set(ROWS) | set(LLM_ROWS) | set(TOTAL_ROWS))
        for n in names:
            rows = [r for r in ROWS.get(n, ()) if now - r[0] <= WINDOW_S]
            llm = [r[1] for r in LLM_ROWS.get(n, ()) if now - r[0] <= WINDOW_S]
            tot = [r[1] for r in TOTAL_ROWS.get(n, ()) if now - r[0] <= WINDOW_S]
            all_rows += rows
            s = dict(STATE["sources"].get(n, {}))
            if s.get("last_ok_ts"):
                s["last_ok_age_s"] = round(now - s["last_ok_ts"], 1)
            out_sources[n] = {**s, "seen_minus_published": lat_summary(rows),
                              "llm_minus_seen": {"n": len(llm), "median_s": _r(percentile(llm, 50)), "p90_s": _r(percentile(llm, 90))},
                              "llm_minus_published": {"n": len(tot), "median_s": _r(percentile(tot, 50)), "p90_s": _r(percentile(tot, 90))}}
        return {"started": STATE["started"], "window_h": WINDOW_S // 3600, "sources": out_sources,
                "all_seen_minus_published": lat_summary(all_rows), "llm": dict(STATE["llm"]),
                "log": {"dir": str(DIR), "log_errors": STATE["log_errors"], "paused_low_disk": STATE["log_paused_low_disk"]},
                "publish": news_publish.view(),
                "note": "t_pub is the source's own time; for eqn_* it is the newswire's relay time. Items in a source's first "
                        "fetch are not counted. Minute-resolution timestamps are excluded from the statistics."}


def loop():
    STATE["started"] = time.time()
    reload_window()
    prune_logs()
    srcs = sources()
    llm_enabled()
    threads = {}

    def spawn(name, target, *args):
        t = threading.Thread(target=target, args=args, daemon=True, name="news_ingest_" + name)
        t.start()
        threads[name] = (t, target, args)

    spawn("llm", llm_worker)
    spawn("eqn_ws", ws_loop)
    spawn("publish", news_publish.loop)       # own thread; a no-op until TRADELAB_DATA_PUSH_TOKEN is set
    for s in srcs:
        spawn(s["name"], poll_loop, s)
        time.sleep(0.3)           # stagger the first requests
    last_prune = time.time()
    while True:
        time.sleep(30)
        for name, (t, target, args) in list(threads.items()):
            if not t.is_alive():
                spawn(name, target, *args)
        if time.time() - last_prune > 6 * 3600:
            last_prune = time.time()
            prune_logs()
        llm_enabled()
