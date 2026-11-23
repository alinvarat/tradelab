"""CLI entry point: the implementation lives in core/dvol_collect.py (also run by the web app on Mondays 09:00/09:05 UTC)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from core import dvol_collect  # noqa: E402

if __name__ == "__main__":
    dvol_collect.main()
