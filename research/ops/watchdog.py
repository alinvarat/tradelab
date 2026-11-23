"""Health check for the research collectors. Writes status.json and sends a desktop notification on failure.
Read-only: it never starts trades and never edits collected data."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / "news_archive" / "data"
DVOL = ROOT / "threefold_plan" / "dvol_forward" / "raw"
STATUS = Path(__file__).parent / "status.json"
TEST_START, TEST_END = datetime(2026, 11, 30, tzinfo=timezone.utc), datetime(2027, 2, 27, tzinfo=timezone.utc)


def newest_news(now):
    files = sorted(NEWS.glob("*.jsonl"))
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
    for unit in ("tradelab-news-archive.timer", "tradelab-dvol-collect.timer"):
        state = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True).stdout.strip()
        if state != "active":
            problems.append(f"{unit} is {state or 'unknown'}")
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
