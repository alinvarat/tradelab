"""Apply the fixed spot strategies to 30-day windows, counted separately from calendar months."""
import hashlib
import gzip
import json
from datetime import date

from research.sixfold.spot import (
    HERE, ONE, BASE_COST, calendar, choose, lookup_factory, run_month, weekly_candidates, weekly_slots,
)
from statistics import median


PERIODS = {
    "reference": (date(2021, 1, 1), date(2023, 12, 31)),
    "holdout": (date(2024, 1, 1), date(2025, 12, 31)),
    "later_2026": (date(2026, 1, 1), date(2026, 10, 31)),
}


def summarize(rows):
    hits = [
        {"start": first.isoformat(), "end": last.isoformat(), "target_trade": row["trades"][-1]}
        for first, last, row in rows if row["6x"]
    ]
    outcomes = [r[2]["multiple"] for r in rows]
    unique_targets = sorted({(r["target_trade"]["symbol"], r["target_trade"]["exit"]) for r in hits})
    return {"windows": len(rows), "hits_6x": len(hits), "hit_windows": hits,
            "unique_target_symbol_dates": unique_targets, "median_multiple": median(outcomes),
            "loss_50pct": sum(v <= 0.50 for v in outcomes), "loss_95pct": sum(v <= 0.05 for v in outcomes),
            "best_multiple": max(outcomes)}


def main():
    packed = (HERE / "spot_inputs.json.gz").read_bytes()
    snapshot = json.loads(gzip.decompress(packed))
    prices = {symbol: {date.fromisoformat(d): bar for d, bar in series.items()}
              for symbol, series in snapshot["markets"].items()}
    pools = weekly_candidates(prices)
    out = {"snapshot_sha256": hashlib.sha256(packed).hexdigest(), "horizon_days": 30, "rules": {}}
    for rule in ("continuation", "reversal"):
        out["rules"][rule] = {}
        for delay in (0, 1):
            lookup = lookup_factory(prices, BASE_COST, delay=delay)
            analysis = {}
            for name, (begin, finish) in PERIODS.items():
                rows = []
                for start in calendar(begin, finish - 29 * ONE):
                    if start.weekday() != 0:
                        continue
                    end = start + 29 * ONE
                    picks = [
                        (slot, choose(pools.get(slot[0], ()), rule))
                        for slot in weekly_slots(start, end)
                    ]
                    rows.append((start, end, run_month(start, end, picks, lookup, details=True)))
                analysis[name] = summarize(rows)
            out["rules"][rule][f"delay_{delay}"] = analysis
    (HERE / "spot_rolling_results.json").write_text(json.dumps(out, indent=2) + "\n")
    for rule, variants in out["rules"].items():
        for variant, parts in variants.items():
            for part, result in parts.items():
                print(rule, variant, part, {k: v for k, v in result.items() if k != "hit_windows"})


if __name__ == "__main__":
    main()
