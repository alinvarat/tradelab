"""Read-only news archiver. Every run it
1. fetches 19 feeds + Bybit delisting notices and appends headlines never seen before to data/YYYY-MM-DD.jsonl,
   stamped with `first_seen_utc` (when THIS machine first saw them) and linked `symbols` (core/entities.py);
2. records per-feed health in feed_health.json (items, newest age, error) so dead feeds are noticed;
3. for headlines that mention a large cap, stores the price (and SPY) at first sight in labels_open.json and,
   when +1h / +1d / +3d have passed, writes the realised and SPY-relative return to labels.jsonl.
That labelled news->return table is the dataset any future news model must be trained and judged on.
Backtests must use `first_seen_utc`, never the feed's `published_ts`. No orders, no keys."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import ai_news, data as market, entities, news  # noqa: E402

DATA = Path(__file__).parent / "data"
HEALTH = DATA / "feed_health.json"
OPEN = DATA / "labels_open.json"
LABELS = DATA / "labels.jsonl"
AI_SCORES = DATA / "ai_scores.jsonl"
AI_PER_RUN, AI_PER_DAY, AI_BATCH = 40, 600, 20  # cost caps for AI scoring (linked headlines only)
BYBIT = "https://api.bytick.com/v5/announcements/index?locale=en-US&type=delistings&limit=20&page=1"
HORIZONS = {"1h": 3600, "1d": 86400, "3d": 3 * 86400}
GRACE = 6 * 3600  # a horizon is only labelled if we got a price within this window after it (else dropped)


def key(source, title):
    return hashlib.sha1((source + "|" + "".join(title.lower().split())).encode()).hexdigest()[:16]


def seen_keys():
    keys = set()
    for p in DATA.glob("20*.jsonl"):
        for line in p.read_text().splitlines():
            try:
                keys.add(json.loads(line)["key"])
            except (ValueError, KeyError):
                pass
    return keys


def bybit_items():
    try:
        rows = json.loads(market.http_get(BYBIT, ttl=0))["result"]["list"]
    except Exception:
        return None
    return [{"title": r["title"], "link": r["url"], "source": "Bybit delistings", "ts": int(r["publishTime"]) / 1000,
             "summary": "", "sentiment": 0.0} for r in rows]


def fetch_all():
    """-> (items, health) where health[source] = {items, newest_age_h, error}."""
    def one(kv):
        name, url = kv
        try:
            it = news.parse_feed(url, name, ttl=0)
            newest = max((x["ts"] for x in it), default=0)
            return name, it, {"items": len(it), "newest_age_h": round((time.time() - newest) / 3600, 1) if newest else None,
                              "error": None if it else "no items"}
        except Exception as exc:  # noqa: BLE001
            return name, [], {"items": 0, "newest_age_h": None, "error": repr(exc)[:120]}
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(one, news.GENERAL_FEEDS.items()))
    items = [x for _, it, _ in results for x in it]
    health = {name: h for name, _, h in results}
    by = bybit_items()
    health["Bybit delistings"] = {"items": len(by or []), "newest_age_h": None, "error": None if by else "no items"}
    return items + (by or []), health


def spot(symbols):
    out = {}
    for s in symbols:
        try:
            q = market.quote(s)
            if q.get("price") and q.get("open"):  # a closed market gives a stale price; label from open-market prices only
                out[s] = q["price"]
        except Exception:  # noqa: BLE001
            pass
    return out


def open_labels(fresh, now, price_fn=spot):
    """Remember the price at first sight for new headlines that mention a large cap."""
    linked = [x for x in fresh if x["symbols"]]
    if not linked:
        return
    syms = sorted({s for x in linked for s in x["symbols"]} | {"SPY"})
    px = price_fn(syms)
    if "SPY" not in px:
        return
    pending = json.loads(OPEN.read_text()) if OPEN.exists() else {}
    for x in linked:
        got = {s: px[s] for s in x["symbols"] if s in px}
        if got:
            pending[x["key"]] = {"t0": now, "symbols": got, "spy0": px["SPY"], "title": x["title"][:140],
                                 "source": x["source"], "sentiment": x["sentiment"], "done": []}
    OPEN.write_text(json.dumps(pending))


def settle_labels(now, price_fn=spot):
    """Write labels for horizons that are due; drop entries that are complete or too late."""
    if not OPEN.exists():
        return 0
    pending = json.loads(OPEN.read_text())
    due = {k: v for k, v in pending.items()
           if any(h not in v["done"] and now - v["t0"] >= s for h, s in HORIZONS.items())}
    if not due:
        return 0
    px = price_fn(sorted({s for v in due.values() for s in v["symbols"]} | {"SPY"}))
    wrote = 0
    with LABELS.open("a") as f:
        for k, v in due.items():
            for h, secs in HORIZONS.items():
                age = now - v["t0"]
                if h in v["done"] or age < secs:
                    continue
                if age > secs + GRACE or "SPY" not in px:
                    v["done"].append(h)   # missed its window: leave it unlabelled rather than label a stale price
                    continue
                for s, p0 in v["symbols"].items():
                    if s in px:
                        ret, spy = px[s] / p0 - 1, px["SPY"] / v["spy0"] - 1
                        f.write(json.dumps({"key": k, "horizon": h, "symbol": s, "ret": round(ret, 5),
                                            "spy_ret": round(spy, 5), "abnormal": round(ret - spy, 5), "t0": v["t0"],
                                            "title": v["title"], "source": v["source"],
                                            "sentiment": v["sentiment"]}) + "\n")
                        wrote += 1
                v["done"].append(h)
    pending = {k: v for k, v in pending.items() if len(v["done"]) < len(HORIZONS) and now - v["t0"] < 4 * 86400}
    OPEN.write_text(json.dumps(pending))
    return wrote


def ai_score_new(fresh, today, providers=None):
    """Score new headlines that mention a large cap with every available model (`providers`: {model: fn}), within
    per-run and per-day caps for each model. Returns rows written."""
    providers = ai_news.providers() if providers is None else providers
    linked = [x for x in fresh if x["symbols"]][:AI_PER_RUN]
    wrote = 0
    for model, fn in providers.items():
        done_today = 0
        if AI_SCORES.exists():
            done_today = sum(1 for l in AI_SCORES.read_text().splitlines()[-6000:]
                             if f'"day": "{today}"' in l and f'"model": "{model}"' in l)
        todo = linked[:max(0, AI_PER_DAY - done_today)]
        for i in range(0, len(todo), AI_BATCH):
            batch = todo[i:i + AI_BATCH]
            scores = fn([{"id": x["key"], "title": x["title"], "summary": x["summary"], "symbols": x["symbols"]}
                         for x in batch])
            with AI_SCORES.open("a") as f:
                for x in batch:
                    s = scores.get(x["key"])
                    if s:
                        f.write(json.dumps({"key": x["key"], "day": today, "model": model, "symbols": x["symbols"],
                                            "lexicon": x["sentiment"], **s}) + "\n")
                        wrote += 1
    return wrote


def main():
    now_dt = datetime.now(timezone.utc)
    DATA.mkdir(exist_ok=True)
    items, health = fetch_all()
    known = seen_keys()
    fresh = []
    for x in items:
        k = key(x["source"], x["title"])
        if k in known:
            continue
        known.add(k)
        fresh.append({"key": k, "first_seen_utc": now_dt.isoformat(), "published_ts": x["ts"], "source": x["source"],
                      "title": x["title"], "link": x["link"], "summary": x["summary"], "sentiment": x["sentiment"],
                      "symbols": entities.link(x["title"] + " " + x["summary"])})
    if fresh:
        with (DATA / (now_dt.strftime("%Y-%m-%d") + ".jsonl")).open("a") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in fresh)
    HEALTH.write_text(json.dumps({"checked_utc": now_dt.isoformat(), "feeds": health}, indent=1))
    now = time.time()
    open_labels(fresh, now)
    wrote = settle_labels(now)
    scored = ai_score_new(fresh, now_dt.strftime("%Y-%m-%d"))
    print(now_dt.isoformat(), "fetched", len(items), "new", len(fresh), "linked", sum(bool(x["symbols"]) for x in fresh),
          "labels", wrote, "ai_scored", scored)


if __name__ == "__main__":
    main()
