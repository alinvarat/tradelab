"""Check a publication-day sell-off rebound in dated Bybit spot records."""
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date

from . import delisting
from .spot import BASE_COST, HERE, ONE, STRESS_COST
from .spot_volume import evaluate

FRESH = HERE / "delist_rebound_2026_inputs.json.gz"
OLD = delisting.CACHE


def inputs(path, fresh):
    if fresh and not path.exists():
        delisting.CACHE = path
        delisting.SCOPE_START = date(2026, 1, 1)
        delisting.SCOPE_END = date(2026, 10, 31)
        delisting.fresh_snapshot()
    raw = gzip.decompress(path.read_bytes())
    return hashlib.sha256(raw).hexdigest(), json.loads(raw)


def candidates(sources):
    select, pools, bars, counts = {}, defaultdict(list), defaultdict(dict), Counter()
    for snapshot in sources:
        for iso, url, symbols in snapshot["events"]:
            signal = date.fromisoformat(iso)
            entry = signal + ONE
            for base in symbols:
                counts[(signal.year, "announced")] += 1
                hist = snapshot["prices"][base]["bars"]
                previous, today = (hist.get(d.isoformat()) for d in (signal - ONE, signal))
                if not previous or not today:
                    counts[(signal.year, "missing_signal_history")] += 1
                    continue
                pools[entry].append(base)
                entry_bar = hist.get(entry.isoformat())
                if entry_bar:
                    bars[base][entry] = entry_bar
                else:
                    counts[(signal.year, "missing_entry")] += 1
                _, high, low, close = today
                ratio = close / previous[3]
                if ratio <= .8 and close >= (high + low) / 2:
                    rank = (ratio, base, url)
                    if entry not in select or rank < select[entry]:
                        select[entry] = rank
    choices = {d: (x[1], pools[d]) for d, x in select.items()}
    return choices, bars, {str(y): {k: v for (yr,k),v in counts.items() if yr == y} for y in range(2023,2027)}


def main():
    original, fresh = inputs(OLD, False), inputs(FRESH, True)
    choose, bars, coverage = candidates([original[1], fresh[1]])
    report = {"snapshot_sha256": [original[0], fresh[0]], "coverage": coverage, "periods": {}}
    for label, years in (("reference", (2023,2024)), ("holdout", (2025,)),
                         ("later", (2026,)), ("continuous", range(2023,2027))):
        months = [f"{y}-{m:02d}" for y in years for m in range(1, 11 if y == 2026 else 13)]
        outcomes = report["periods"][label] = {}
        for name, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
            row = outcomes[name] = evaluate(choose, bars, months, cost)
            row["6x_months"] = sum(x >= 6 for _, x in row["months"])
    (HERE / "delist_rebound_results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
