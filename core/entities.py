"""Link headline text to tickers in the large-cap universe (names, key products/people, unambiguous tickers)."""
import json
import re
from pathlib import Path

ALIASES: dict[str, list[str]] = json.loads((Path(__file__).parent / "entities.json").read_text())
# Tickers that are ordinary words or too short: only a company-name match counts for these.
AMBIGUOUS = {s for s in ALIASES if len(s.replace("-", "")) <= 2} | {"ALL", "NOW", "CAT", "GE", "GM", "KO", "KR", "DE", "CI", "EL", "LOW", "DG"}
_PATTERNS: dict[str, re.Pattern] = {}
for sym, names in ALIASES.items():
    parts = [re.escape(n) for n in names if len(n) >= 4]
    _PATTERNS[sym] = re.compile(r"(?<![\w])(" + "|".join(parts) + r")(?![\w])", re.I) if parts else None


def link(text: str, limit: int = 4) -> list[str]:
    """Symbols mentioned in `text`, in order of the first mention (company name, product/person alias or ticker)."""
    hits = []
    for sym, pat in _PATTERNS.items():
        pos = None
        if pat:
            m = pat.search(text)
            pos = m.start() if m else None
        if pos is None and sym not in AMBIGUOUS:
            m = re.search(r"(?<![\w$])\$?" + re.escape(sym) + r"(?![\w])", text)  # uppercase ticker as written
            pos = m.start() if m else None
        if pos is not None:
            hits.append((pos, sym))
    return [s for _, s in sorted(hits)][:limit]
