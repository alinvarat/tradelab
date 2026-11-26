"""v4.19 data feeds for the bot (pod side, stdlib only): the fast news ingest log, the forward ledgers' public summaries and OKX
funding. Everything is read-only and cached: the scan loop never waits on the network (a background thread refreshes the
ledgers and funding; the ingest log is read from the local file). Pure block builders live in core/desk_rules.py.

The ingest module (core/news_ingest.py) is not changed: this reads its append-only day files and its in-memory view().
Ledger summaries are the public files on the data branches of the repo (public since 2026-11-25), fetched with no key."""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from . import desk_rules as dr
from . import news_ingest, notice_fwd

log = logging.getLogger("tradelab.feeds")
REPO = os.environ.get("TRADELAB_DATA_REPO") or "alinvarat/tradelab"
LEDGERS = {   # name: (branch, max age in seconds before it counts as stale)
    "event_book": ("data/event-book", 3 * 3600),
    "okx_funding_fwd": ("data/okx-fwd", 12 * 3600),
    "notice_fwd": ("data/notice-fwd", 3 * 3600),
}
LEDGER_EVERY_S = 600
FUNDING_EVERY_S = 300
OKX_FUNDING = "https://www.okx.com/api/v5/public/funding-rate?instId="
TAIL_BYTES = 400_000
UA = "tradelab-desk-feeds"


def _get(url, timeout=6):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read()


def _iso(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def tail_rows(path, max_bytes=TAIL_BYTES):
    p = Path(path)
    if not p.exists():
        return []
    size = p.stat().st_size
    with p.open("rb") as f:
        f.seek(max(0, size - max_bytes))
        raw = f.read()
    lines = raw.decode("utf-8", "replace").splitlines()
    if size > max_bytes and lines:
        lines = lines[1:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def classify_rows(rows):
    """Item rows of the ingest log -> rows with the forced-flow class when notice_fwd.classify recognises a notice."""
    out = []
    for r in rows:
        if r.get("event") != "item" or not r.get("t_seen"):
            continue
        try:
            c = notice_fwd.classify(r.get("source") or "", r.get("title") or "")
        except Exception:  # noqa: BLE001
            c = None
        out.append({"source": r["source"], "key": r.get("key"), "title": r.get("title") or "", "t_pub": r.get("t_pub"),
                    "t_seen": r["t_seen"], "lat_s": r.get("lat_s"), "cls": c["cls"] if c else None,
                    "side": c["side"] if c else None, "coins": c["coins"] if c else []})
    return out


def compact_ledger(name, summary):
    """A short, labelled view of one ledger summary.json and its timestamp (None when the file has none)."""
    if name == "event_book":
        return {"ts": _iso(summary.get("run_utc")), "view": {k: summary.get(k) for k in ("events_seen", "open", "closed", "components")}}
    if name == "okx_funding_fwd":
        co = summary.get("cohorts") or {}
        nets = [c.get("mean_net_2x") for c in co.values() if c.get("mean_net_2x") is not None]
        return {"ts": _iso(summary.get("updated_utc")),
                "view": {"settlements": (summary.get("meta") or {}).get("settlements"), "cohorts": len(co),
                         "mean_net_2x_range": [round(min(nets), 4), round(max(nets), 4)] if nets else None,
                         "max_e_edge": max((c.get("e_value_edge") or 0 for c in co.values()), default=None),
                         "decisions": sorted({c.get("verdict") for c in co.values()})}}
    if name == "notice_fwd":
        v = summary.get("verdict") or {}
        return {"ts": _iso(summary.get("updated_utc")),
                "view": {"verdict": v.get("verdict"), "n": v.get("n"), "mean_net": v.get("mean_net"),
                         "clusters": summary.get("clusters"), "pending": summary.get("pending")}}
    return {"ts": None, "view": {}}


class Feeds:
    def __init__(self, ingest_dir=None, fetch=_get, universe=None):
        self.dir = Path(ingest_dir or news_ingest.DIR)
        self.fetch = fetch
        self.universe = set(universe or ())
        self.ledgers: dict = {}
        self.funding: dict = {}
        self.errors: dict = {}
        self._stop = False

    # ---- background refresh (never called from the scan loop)
    def refresh_ledgers(self):
        for name, (branch, _) in LEDGERS.items():
            try:
                summary = json.loads(self.fetch(f"https://raw.githubusercontent.com/{REPO}/{branch}/summary.json"))
                self.ledgers[name] = {**compact_ledger(name, summary), "fetched": time.time()}
                self.errors.pop(name, None)
            except Exception as e:  # noqa: BLE001 a missing branch (404) is a normal "not started" state
                self.errors[name] = str(e)[:80]

    def refresh_funding(self):
        for sym in sorted(s for s in self.universe if s.endswith("-USD")):
            inst = sym.replace("-USD", "-USDT-SWAP")
            try:
                d = json.loads(self.fetch(OKX_FUNDING + inst))["data"][0]
                cur, nxt, t = float(d["fundingRate"]), d.get("nextFundingRate"), float(d["fundingTime"]) / 1000
                self.funding[sym] = {"rate_pct": round(cur * 100, 4), "predicted_pct": round(float(nxt) * 100, 4) if nxt not in (None, "") else None,
                                     "settles_in_min": round((t - time.time()) / 60), "ts": time.time()}
            except Exception as e:  # noqa: BLE001
                self.errors["funding:" + sym] = str(e)[:80]

    def run(self):
        last_l = last_f = 0.0
        while not self._stop:
            now = time.time()
            if now - last_l >= LEDGER_EVERY_S:
                last_l = now
                self.refresh_ledgers()
            if now - last_f >= FUNDING_EVERY_S:
                last_f = now
                self.refresh_funding()
            time.sleep(15)

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="desk_feeds").start()

    # ---- reads used by the scan loop (local only)
    def ingest_items(self, now):
        rows = []
        for t in (now - 86400, now):
            rows += tail_rows(self.dir / f"{news_ingest._day(t)}.jsonl")
        return classify_rows(rows)

    def source_health(self):
        try:
            v = news_ingest.view()
        except Exception:  # noqa: BLE001
            return {}
        return {n: {"last_ok_age_s": s.get("last_ok_age_s"), "median_s": (s.get("seen_minus_published") or {}).get("median_s"),
                    "n": (s.get("seen_minus_published") or {}).get("n")} for n, s in v.get("sources", {}).items()}

    def forced_candidates(self, now, window_s=900):
        """Forced-flow notices (delist, monitoring tag, listing) seen in the last window that name a coin the bot can trade.
        Small perps are not in the bot's universe (11 large coins): those are covered by the notice_fwd ledger only."""
        out = {}
        for r in self.ingest_items(now):
            if not r["cls"] or now - r["t_seen"] > window_s:
                continue
            for c in r["coins"]:
                sym = f"{c}-USD"
                if sym in self.universe and sym not in out:
                    out[sym] = {"cls": r["cls"], "side": r["side"], "title": r["title"][:110], "key": f"{r['source']}|{r['key']}",
                                "age_s": round(now - r["t_seen"]), "lat_s": r["lat_s"], "src": r["source"]}
        return out

    def block(self, now):
        """The data_feeds context block: fast news, flow base rates, ledgers and freshness. Small by construction."""
        health = self.source_health()
        led = {n: {"ts": v.get("ts"), "max_age_s": LEDGERS[n][1]} for n, v in self.ledgers.items()}
        for n in LEDGERS:
            led.setdefault(n, {"ts": None, "max_age_s": LEDGERS[n][1]})
        fh = dr.feed_health(health, led, now)
        fast = dr.fast_news_block(self.ingest_items(now), now, health)
        return {"fast_news": fast,
                "flow_base_rates": {"evidence": "in-sample on the screens that chose the hold; forward books confirm",
                                    "rates": dr.FLOW_BASE_RATES, "recent": dr.FLOW_RECENT_OOS,
                                    "reachable": "only coins in your universe can be traded; small perps are not"},
                "forward_ledgers": {n: {"age_s": None if v.get("ts") is None else round(now - v["ts"]), **v.get("view", {})}
                                    for n, v in self.ledgers.items()} | {n: {"status": "not available: " + self.errors.get(n, "no data yet")}
                                                                          for n in LEDGERS if n not in self.ledgers},
                "freshness": {"stale": fh["stale"], "note": "a stale feed is NOT evidence of quiet: treat its data as missing"}}, fh

    def candidate_context(self, sym):
        f = self.funding.get(sym)
        return {"funding_okx": {k: f[k] for k in ("rate_pct", "predicted_pct", "settles_in_min")} | {"age_s": round(time.time() - f["ts"])}} if f else {}
