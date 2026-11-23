"""Daily copy of the live account files to data/backups/YYYY-MM-DD/ (keeps 14 days). Local only, never committed."""
from datetime import date, timedelta
from pathlib import Path
import shutil

DATA = Path(__file__).resolve().parents[1] / "data"
KEEP = 14


def main():
    target = DATA / "backups" / date.today().isoformat()
    target.mkdir(parents=True, exist_ok=True)
    for name in ("state.json", "auto.json", "hunter.json", "ai_log.jsonl"):
        if (DATA / name).exists():
            shutil.copy2(DATA / name, target / name)
    for old in sorted((DATA / "backups").iterdir())[:-KEEP]:
        shutil.rmtree(old, ignore_errors=True)
    print("backed up to", target)


if __name__ == "__main__":
    main()
