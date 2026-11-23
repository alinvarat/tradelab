"""CLI entry point kept for the systemd timer: the implementation lives in core/news_archive.py.
This module IS that module (same object), so `import research.news_archive.collector as c; c.DATA = ...` still works."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import news_archive  # noqa: E402

if __name__ == "__main__":
    news_archive.main()
else:
    sys.modules[__name__] = news_archive
