"""US macro event calendar from data/events.csv (FOMC, CPI, NFP; dates taken from the
BLS and Federal Reserve schedule pages listed per row; verify against the source before relying on them)."""
import csv
import datetime as dt
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "events.csv"
DESC = {"FOMC": "Fed interest-rate decision", "CPI": "US consumer price inflation", "NFP": "US non-farm payrolls (jobs)"}


def events(days_back=30, days_ahead=120) -> list:
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    with CSV.open() as f:
        for r in csv.DictReader(f):
            t = dt.datetime.strptime(r["utc_datetime"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
            if now - dt.timedelta(days=days_back) <= t <= now + dt.timedelta(days=days_ahead):
                out.append({"ts": t.timestamp(), "event": r["event"], "desc": DESC.get(r["event"], ""),
                            "source": r["source_url"], "impact": "High"})
    return out
