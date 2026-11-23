"""Write reports/STATUS.md: one page both teammates can read (collectors, DVOL forward test progress, news archive)."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "STATUS.md"
RAW = ROOT / "research/threefold_plan/dvol_forward/raw"
NEWS = ROOT / "research/news_archive/data"
MONDAYS = [datetime(2026, 11, 30, tzinfo=timezone.utc) + timedelta(weeks=i) for i in range(13)]


def main():
    now = datetime.now(timezone.utc)
    ok = json.loads((ROOT / "research/ops/status.json").read_text()) if (ROOT / "research/ops/status.json").exists() else {}
    lines = [f"# TradeLab status (auto-generated {now:%Y-%m-%d %H:%M} UTC)", "",
             "Simulated money only. Machine that ran the collectors wrote this file; gaps = that machine was off.", "",
             "## Health", f"- Watchdog: {'OK' if ok.get('ok') else 'PROBLEMS: ' + '; '.join(ok.get('problems', ['no status yet']))} "
             f"(checked {ok.get('checked_utc', 'never')})", ""]
    lines += ["## DVOL forward test (locked protocol, 13 Mondays 2026-11-30 .. 2027-02-22)",
              "| Monday | snapshots 09:00 / 09:05 | status |", "|---|---|---|"]
    done = 0
    for m in MONDAYS:
        files = sorted(p.name for p in RAW.glob(m.strftime("%Y%m%d") + "T09*.json.gz"))
        n = len(files)
        if m > now:
            status = "upcoming"
        elif n >= 2:
            status, done = "complete", done + 1
        else:
            status = f"MISSED ({n}/2) - week counts as cash"
        lines.append(f"| {m:%Y-%m-%d} | {n}/2 | {status} |")
    lines += ["", f"Complete weeks: {done}/13. Evaluate after 2027-02-26 with `python3 research/threefold_plan/dvol_forward/evaluate.py`; "
              "rules are locked (see `protocol.md`). Earlier checks say the expected result is poor (see the plan report).", ""]
    files = sorted(NEWS.glob("*.jsonl"))
    total = sum(len(p.read_text().splitlines()) for p in files)
    lines += ["## News archive (first-seen timestamps, 60 s polling)",
              f"- Days: {len(files)}, headlines: {total}" + (f", first file {files[0].stem}, last {files[-1].stem}" if files else ""), ""]
    timers = subprocess.run(["systemctl", "--user", "list-timers", "tradelab-*", "--no-pager"], capture_output=True, text=True).stdout
    lines += ["## Timers on the collector machine", "```", timers.strip() or "none", "```", ""]
    OUT.write_text("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
