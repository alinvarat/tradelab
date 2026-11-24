"""Link headline text to tickers in the large-cap universe (names, key products/people, unambiguous tickers)."""
import json
import re
from pathlib import Path

ALIASES: dict[str, list[str]] = json.loads((Path(__file__).parent / "entities.json").read_text())
# Tickers that are ordinary words or too short: only a company-name match counts for these.
AMBIGUOUS = {s for s in ALIASES if len(s.replace("-", "")) <= 2} | {"ALL", "NOW", "CAT", "GE", "GM", "KO", "KR", "DE", "CI", "EL", "LOW", "DG"}
# Company names that are also ordinary words: they link only when capitalised and not used as the ordinary word
# ("target hikes", "price target", "visa rules", "apple orchard" are not the companies). Added 2026-11-24 after
# "Zscaler receives multiple target hikes ..." was linked to Target (TGT).
COMMON_WORD_NAMES = {"Target", "Visa", "Oracle", "Apple", "Amazon"}
_NOT_COMPANY_AFTER = (r"(?!\s+(?:price|prices|hike|hikes|raise|raises|raised|cut|cuts|date|dates|audience|rate|rates|"
                      r"range|level|levels|zone|market|markets|rules|rule|application|applications|holders?|"
                      r"rainforest|basin|river|orchard|juice|of\b))")
_NOT_COMPANY_BEFORE = r"(?<!price )(?<!profit )(?<!sales )(?<!revenue )(?<!earnings )(?<!inflation )(?<!student )"
_PATTERNS: dict[str, re.Pattern] = {}
_STRICT: dict[str, re.Pattern] = {}
for sym, names in ALIASES.items():
    parts = [re.escape(n) for n in names if len(n) >= 4 and n not in COMMON_WORD_NAMES]
    _PATTERNS[sym] = re.compile(r"(?<![\w])(" + "|".join(parts) + r")(?![\w])", re.I) if parts else None
    strict = [re.escape(n) for n in names if n in COMMON_WORD_NAMES]
    if strict:   # case-sensitive, with the ordinary-word contexts excluded
        _STRICT[sym] = re.compile(_NOT_COMPANY_BEFORE + r"(?<![\w])(" + "|".join(strict) + r")(?![\w])" + _NOT_COMPANY_AFTER)


def link(text: str, limit: int = 4) -> list[str]:
    """Symbols mentioned in `text`, in order of the first mention (company name, product/person alias or ticker)."""
    hits = []
    for sym, pat in _PATTERNS.items():
        pos = None
        if pat:
            m = pat.search(text)
            pos = m.start() if m else None
        if pos is None and sym in _STRICT:
            m = _STRICT[sym].search(text)
            pos = m.start() if m else None
        if pos is None and sym not in AMBIGUOUS:
            m = re.search(r"(?<![\w$])\$?" + re.escape(sym) + r"(?![\w])", text)  # uppercase ticker as written
            pos = m.start() if m else None
        if pos is not None:
            hits.append((pos, sym))
    return [s for _, s in sorted(hits)][:limit]
