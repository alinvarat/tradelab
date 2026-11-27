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
  binance_*_fast  the same lists, but each request goes to a different CloudFront cache key (parameter order) and is made just
                when that key's ~120 s cache entry expires (see binance_variants / cache_expiry); 12 keys -> staleness ~10 s
                instead of 0-120 s (measured 2026-11-26: Age header climbs to ~120 then RefreshHit; the control's median 64 s
                is that cache, not the poll interval). About 0.1 request/s per catalog. LLM off for these (duplicates).
  okx_announcements  public REST, every 3 s (not cached by a CDN: DYNAMIC / no-store)
  okx_ann_my, okx_ann_listings, okx_help_latest, okx_help_listings  candidate faster OKX paths raced against okx_announcements:
                the EU-catalogue host, the per-type list, and the help-center section pages (server-rendered list with ETag).
                All use the same t_pub as the control (API pTime == help-page updatedAt) and the same key (slug), so rows pair
                one-to-one on key. LLM off for these.
  eqn_ws        EquationNews (BWEnews-style crypto newswire) public websocket push, no key
  eqn_rest      the same newswire over REST with ETag, every 3 s (its docs allow 1 req/s)
For eqn_*, t_pub is the newswire's own timestamp (when it relayed the story), not the original source's time.
Request rate is about 2.5 req/s in total; errors back off exponentially (403/429 wait at least 60 s)."""
import base64
import gzip
import itertools
import json
import os
import random
import re
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
# Experiment sources raced against the controls: logged and measured, never shown to the bot (core.desk_feeds skips them, so
# the bot's inputs are unchanged and the same article is not listed up to eight times).
CANDIDATE_SOURCES = frozenset({"binance_listings_fast", "binance_news_fast", "binance_delist_fast", "okx_ann_my", "okx_ann_listings",
                               "okx_help_latest", "okx_help_listings", "binance_listings_apex", "binance_news_apex",
                               "binance_delist_apex", "binance_news_cat"})
BN_TTL_S = 120          # CloudFront TTL measured on 2026-11-26 (Age climbs to ~120, then RefreshHit)
BN_KEYS = 12            # cache keys per catalog; 120 / 12 = one expiry about every 10 s
BN_MIN_GAP_S = 2.0      # never more than one request per 2 s per catalog
OKX_HELP = "https://www.okx.com/help/section/"
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


BN_PARAMS = ("type", "pageNo", "pageSize", "catalogId")
BN_CMS = "https://www.binance.com/bapi/"
BN_PATH = {"list": BN_CMS + "composite/v1/public/cms/article/list/query",          # the control's endpoint
           "apex": BN_CMS + "apex/v1/public/apex/cms/article/list/query",          # same answer, different gateway path
           "cat": BN_CMS + "composite/v1/public/cms/article/catalog/list/query"}   # id/code/title only (no releaseDate)


def binance_variants(catalog_id, k=BN_KEYS, page_size=10, variant="list"):
    """k distinct URLs for one catalog that return the same list but are different CloudFront cache keys. The server accepts
    the four parameters in any order (all 24 permutations checked, 200); an unknown extra parameter is a 400. The odd-indexed
    permutations are used so the control URL (permutation 0) is never reused. Deterministic."""
    if variant == "cat":     # 3 parameters x page sizes 5 and 10 = 12 distinct cache keys
        out = []
        for ps in (5, 10):
            vals = {"catalogId": str(catalog_id), "pageNo": "1", "pageSize": str(ps)}
            out += [BN_PATH["cat"] + "?" + "&".join(f"{p}={vals[p]}" for p in perm) for perm in itertools.permutations(vals)]
        return out[:k]
    vals = {"type": "1", "pageNo": "1", "pageSize": str(page_size), "catalogId": str(catalog_id)}
    perms = list(itertools.permutations(BN_PARAMS))[1::2][:k]
    return [BN_PATH[variant] + "?" + "&".join(f"{p}={vals[p]}" for p in perm) for perm in perms]


def parse_binance_cat(d, prefix):
    """catalog/list/query answer: id, code, title only. t_pub is None here; the analysis joins on the key to the control's
    releaseDate (same prefix:code key)."""
    out = []
    for a in (d.get("data") or {}).get("articles") or []:
        code = a.get("code") or a.get("id")
        out.append({"key": f"{prefix}:{code}", "title": str(a.get("title") or "")[:300], "t_pub": None, "res": None,
                    "link": f"https://www.binance.com/en/support/announcement/{code}", "desc": ""})
    return out


def _hget(hdr, name):
    low = name.lower()
    for k, v in (hdr or {}).items():
        if k.lower() == low:
            return v
    return None


def cache_expiry(hdr, t_rx, ttl=BN_TTL_S):
    """When the CDN entry that answered this request will expire (epoch s). Age gives the entry's age; a Miss/RefreshHit has
    no Age header and was filled now. A Hit without Age (unexpected) is rechecked after half a TTL."""
    age = _hget(hdr, "Age")
    try:
        return t_rx - float(age) + ttl
    except (TypeError, ValueError):
        pass
    if "hit" in (_hget(hdr, "X-Cache") or "").lower().replace("refreshhit", ""):
        return t_rx + ttl / 2
    return t_rx + ttl


def next_variant(keys, now, last_fetch=None, min_gap=BN_MIN_GAP_S, margin=1.0):
    """keys: {url: expiry_epoch}. -> (url, seconds to wait): the key that expires first, fetched `margin` s after expiry, and
    never sooner than `min_gap` after the previous request."""
    url = min(keys, key=lambda u: (keys[u], u))
    wait = max(0.0, keys[url] + margin - now)
    if last_fetch is not None:
        wait = max(wait, last_fetch + min_gap - now)
    return url, wait


def okx_key(url_or_slug):
    """Canonical pairing key for an OKX article: the slug, whatever host or locale the list came from."""
    slug = str(url_or_slug or "").split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return "okx_announcements:https://www.okx.com/help/" + slug


def parse_okx_norm(body, name=None):
    """OKX announcements REST answer with slug-based keys (so regional hosts pair with the control)."""
    out = nl.parse_okx_announcements(json.loads(body), "okx_announcements")
    for it in out:
        it["key"] = okx_key(it["link"] or it["key"])
    return out


_HELP_ITEM = re.compile(r'"slug":"([^"]+)","title":"((?:[^"\\]|\\.)*)","publishTime":(\d+),"updatedAt":(\d+),"sectionSlug":"([^"]+)"')


def parse_okx_help(body):
    """OKX help-center section page (server-rendered, window.__INIT_STATE__ ... parseData("<json string>")) -> items. t_pub is
    updatedAt (equal to the REST API's pTime to the second, so it pairs with okx_announcements); publishTime (often a scheduled
    hour mark) is kept in `extra`. Structured parse first, regex over the escaped text as a fallback."""
    text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else body
    rows = []
    for m in re.finditer(r'parseData\("((?:[^"\\]|\\.)*)"\)', text):
        try:
            d = json.loads(json.loads('"' + m.group(1) + '"'))
            lst = d["appContext"]["initialProps"]["sectionData"]["articleList"]["list"]
        except (ValueError, KeyError, TypeError):
            continue
        rows = [(a.get("slug"), a.get("title"), a.get("publishTime"), a.get("updatedAt"), a.get("sectionSlug")) for a in lst]
        break
    if not rows:
        flat = text.replace('\\"', '"')
        rows = [(g[0], g[1], g[2], g[3], g[4]) for g in _HELP_ITEM.findall(flat)]
    out = []
    for slug, title, pub, upd, sect in rows:
        if not slug or not upd:
            continue
        try:
            title = json.loads('"' + title + '"') if "\\u" in str(title) else str(title)
        except ValueError:
            title = str(title)
        out.append({"key": okx_key(slug), "title": title[:300], "t_pub": int(upd) / 1000.0, "res": "s",
                    "link": "https://www.okx.com/help/" + slug, "desc": sect, "extra": {"publish_time": int(pub) / 1000.0 if pub else None}})
    return out


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
        # candidate faster paths, raced against the controls above; same keys, same t_pub, no LLM (duplicates)
        {"name": "binance_listings_fast", "kind": "binance_multi", "catalog": 48, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "binance_news_fast", "kind": "binance_multi", "catalog": 49, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "binance_delist_fast", "kind": "binance_multi", "catalog": 161, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        # same lists through another gateway path / endpoint, to find out whether the 60 s that remains on a cache Miss is
        # in the shared composite backend; keys pair with the controls through `prefix`
        {"name": "binance_listings_apex", "kind": "binance_multi", "variant": "apex", "prefix": "binance_listings", "catalog": 48, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "binance_news_apex", "kind": "binance_multi", "variant": "apex", "prefix": "binance_news", "catalog": 49, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "binance_delist_apex", "kind": "binance_multi", "variant": "apex", "prefix": "binance_delist", "catalog": 161, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "binance_news_cat", "kind": "binance_multi", "variant": "cat", "prefix": "binance_news", "catalog": 49, "every": BN_MIN_GAP_S, "market": "crypto", "llm": False, "trace": True},
        {"name": "okx_ann_my", "kind": "okx_norm", "url": "https://my.okx.com/api/v5/support/announcements", "every": 3, "market": "crypto", "llm": False},
        {"name": "okx_ann_listings", "kind": "okx_norm", "url": OKX_ANN + "?annType=announcements-new-listings", "every": 3, "market": "crypto", "llm": False},
        {"name": "okx_help_latest", "kind": "okx_help", "url": OKX_HELP + "announcements-latest-announcements", "every": 2.5, "market": "crypto", "llm": False},
        {"name": "okx_help_listings", "kind": "okx_help", "url": OKX_HELP + "announcements-new-listings", "every": 3, "market": "crypto", "llm": False},
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
    if k == "okx_norm":
        return parse_okx_norm(body)
    if k == "okx_help":
        return parse_okx_help(body)
    if k == "binance_multi":
        prefix = src.get("prefix") or src["name"].replace("_fast", "")
        if src.get("variant") == "cat":
            return parse_binance_cat(json.loads(body), prefix)
        return nl.parse_binance(json.loads(body), prefix)
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
    if it.get("via"):
        row["via"] = it["via"]
    if it.get("extra"):
        row.update(it["extra"])
    log_row(row, t_seen)
    if lat is not None and src.get("llm", True) and llm_enabled() and eligible_for_llm(name, src["market"], it):
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


def cache_trace(hdr):
    """Compact CDN state of an answer for the log row, e.g. 'Hit:104' (X-Cache and Age), so every rare event shows where
    its delay came from."""
    xc = (_hget(hdr, "X-Cache") or _hget(hdr, "CF-Cache-Status") or "").split(" ")[0]
    age = _hget(hdr, "Age")
    return (xc + (":" + str(age) if age is not None else "")) or None


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
        cond["last_hdr"] = hdr
        via = cache_trace(hdr) if src.get("trace") else None
        for it in items:
            if via:
                it["via"] = via
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


def multi_step(src, state, now=time.time, fetch_fn=fetch):
    """One tick of a cache-key-rotating poll (binance_*_fast). state: {"keys": {url: expiry}, "conds": {url: cond}, "last": t}.
    Fetches the key whose cache entry expires first, when it expires. -> seconds until the next tick. 429/403 pause the whole
    catalog (poll_step's backoff); other errors retry that key after the backoff."""
    if "keys" not in state:
        urls = binance_variants(src["catalog"], variant=src.get("variant", "list"))
        t = now()
        # first pass: one request per TTL/k seconds, so the entries that this fills (Miss = filled now) expire evenly spread
        # over the TTL; later requests keep that phase because each is made at its own entry's expiry
        gap = BN_TTL_S / max(1, len(urls))
        state.update(keys={u: t + i * gap - 1.0 for i, u in enumerate(urls)}, conds={u: {} for u in urls}, last=None)
    url, wait = next_variant(state["keys"], now(), state["last"])
    if wait > 0:
        return min(wait, 1.0)
    cond = state["conds"][url]
    cond.pop("etag", None)
    cond.pop("modified", None)
    st = _stat(src["name"])
    errors_before = st["errors"]
    w = poll_step({**src, "url": url}, cond, fetch_fn)
    t = now()
    state["last"] = t
    if st["errors"] != errors_before:
        for u in state["keys"]:             # a failure (429/403 above all) pauses the whole catalog, not just this key
            state["keys"][u] = max(state["keys"][u], t + w)
        return min(w, 1.0)
    state["keys"][url] = cache_expiry(cond.get("last_hdr"), t)
    return 0.0


def multi_loop(src):
    state = {}
    while True:
        try:
            wait = multi_step(src, state)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            wait = BACKOFF_MAX_S / 5
        time.sleep(max(0.05, wait) * (random.uniform(0.9, 1.1) if wait > 1.5 else 1.0))


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


HEALTH_EVERY_S = 600


def health_row(now):
    """A log row (no source/key, so every reader of the item rows skips it) with each source's poll counters, so a quiet
    source can be told apart from a broken one from the data branch alone."""
    with _lock:
        return {"event": "health", "t_seen": now, "sources": {n: {k: s.get(k) for k in ("polls", "ok", "errors", "last_status", "last_error", "new_items", "cold_items")}
                                                              for n, s in STATE["sources"].items()}}


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
        spawn(s["name"], multi_loop if s["kind"] == "binance_multi" else poll_loop, s)
        time.sleep(0.3)           # stagger the first requests
    last_prune = time.time()
    last_health = 0.0
    while True:
        time.sleep(30)
        if time.time() - last_health > HEALTH_EVERY_S:
            last_health = time.time()
            log_row(health_row(last_health), last_health)
        for name, (t, target, args) in list(threads.items()):
            if not t.is_alive():
                spawn(name, target, *args)
        if time.time() - last_prune > 6 * 3600:
            last_prune = time.time()
            prune_logs()
        llm_enabled()
