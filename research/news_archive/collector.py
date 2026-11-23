"""Read-only news archiver: every run appends headlines never seen before to data/YYYY-MM-DD.jsonl,
stamped with the time THIS machine first saw them (first_seen_utc). Use that stamp, not the feed's pubDate,
for any backtest so no price after the headline leaks backwards. No orders, no keys, separate from the bot."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import news  # noqa: E402

DATA = Path(__file__).parent / "data"
BYBIT = "https://api.bytick.com/v5/announcements/index?locale=en-US&type=delistings&limit=20&page=1"


def key(source, title):
    return hashlib.sha1((source + "|" + "".join(title.lower().split())).encode()).hexdigest()[:16]


def seen_keys():
    keys = set()
    for p in DATA.glob("*.jsonl"):
        for line in p.read_text().splitlines():
            try:
                keys.add(json.loads(line)["key"])
            except (ValueError, KeyError):
                pass
    return keys


def bybit_items():
    from core import data
    try:
        rows = json.loads(data.http_get(BYBIT, ttl=0))["result"]["list"]
    except Exception:
        return []
    return [{"title": r["title"], "link": r["url"], "source": "Bybit delistings",
             "ts": int(r["publishTime"]) / 1000, "summary": "", "sentiment": 0.0} for r in rows]


def main():
    now = datetime.now(timezone.utc)
    items = []
    for source, url in news.GENERAL_FEEDS.items():
        items += news.parse_feed(url, source, ttl=0)
    items += bybit_items()
    DATA.mkdir(exist_ok=True)
    known = seen_keys()
    fresh = []
    for x in items:
        k = key(x["source"], x["title"])
        if k in known:
            continue
        known.add(k)
        fresh.append({"key": k, "first_seen_utc": now.isoformat(), "published_ts": x["ts"], "source": x["source"],
                      "title": x["title"], "link": x["link"], "summary": x["summary"], "sentiment": x["sentiment"]})
    if fresh:
        with (DATA / (now.strftime("%Y-%m-%d") + ".jsonl")).open("a") as f:
            f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in fresh)
    print(now.isoformat(), "fetched", len(items), "new", len(fresh))


if __name__ == "__main__":
    main()
