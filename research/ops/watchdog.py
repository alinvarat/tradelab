"""Health check for the research collectors. Writes status.json and sends a desktop notification on failure.
Read-only: it never starts trades and never edits collected data."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))  # repo root, for core.news
NEWS = ROOT / "news_archive" / "data"
DVOL = ROOT / "threefold_plan" / "dvol_forward" / "raw"
STATUS = Path(__file__).parent / "status.json"
TEST_START, TEST_END = datetime(2026, 11, 30, tzinfo=timezone.utc), datetime(2027, 2, 27, tzinfo=timezone.utc)


def newest_news(now):
    files = sorted(NEWS.glob("20*.jsonl"))
    for path in reversed(files):
        lines = path.read_text().splitlines()
        if lines:
            return datetime.fromisoformat(json.loads(lines[-1])["first_seen_utc"])
    return None


def check(now):
    problems = []
    last = newest_news(now)
    # a quiet feed can legitimately give no new headline for a while; alarm only after 3 hours
    if last is None or now - last > timedelta(hours=3):
        problems.append(f"news archive has no new headline since {last}")
    try:
        feeds = json.loads((NEWS / "feed_health.json").read_text())["feeds"]
        from core.news import LOW_FREQUENCY
        bad = [n for n, h in feeds.items() if n not in LOW_FREQUENCY and n != "Bybit delistings"
               and (h["error"] or (h["newest_age_h"] is not None and h["newest_age_h"] > 12))]
        if len(bad) >= 3:
            problems.append(f"{len(bad)} news feeds dead or stale: {', '.join(bad[:6])}")
    except FileNotFoundError:
        pass
    for unit in ("tradelab-news-archive.timer", "tradelab-dvol-collect.timer"):
        state = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True).stdout.strip()
        if state != "active":
            problems.append(f"{unit} is {state or 'unknown'}")
    try:
        port = os.environ.get("TRADELAB_PORT", "8770")
        health = json.loads(urlopen(f"http://127.0.0.1:{port}/healthz", timeout=10).read())
        if not health["ok"]:
            problems.append(f"TradeLab server unhealthy: {health}")
        elif health.get("auto_cycle_age_s") and health["auto_cycle_age_s"] > 3600:
            problems.append(f"auto trader has not completed a cycle for {health['auto_cycle_age_s']} s")
    except HTTPError as exc:
        if exc.code != 404:  # 404 = server started before /healthz existed; restart it to enable the check
            problems.append(f"TradeLab server error {exc.code}")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"TradeLab server not answering: {exc!r}")
    free_gb = shutil.disk_usage(ROOT).free / 1e9
    if free_gb < 1:
        problems.append(f"only {free_gb:.1f} GB disk free")
    if TEST_START <= now <= TEST_END and now.weekday() == 0 and now.hour >= 10:
        today = now.strftime("%Y%m%d")
        got = sorted(p.name for p in DVOL.glob(today + "T09*.json.gz"))
        if len(got) < 2:
            problems.append(f"DVOL forward test: {len(got)}/2 snapshots for {today} (week will be cash)")
    return problems, last


def main():
    now = datetime.now(timezone.utc)
    problems, last = check(now)
    previous = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    STATUS.write_text(json.dumps({"checked_utc": now.isoformat(), "ok": not problems, "problems": problems,
                                  "newest_news_utc": last.isoformat() if last else None}, indent=1) + "\n")
    if problems and previous.get("problems") != problems:  # notify once per distinct problem set
        subprocess.run(["notify-send", "-u", "critical", "TradeLab collector problem", "\n".join(problems)],
                       capture_output=True)
    print("OK" if not problems else "PROBLEMS: " + "; ".join(problems))


if __name__ == "__main__":
    main()
