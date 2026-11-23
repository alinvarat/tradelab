"""Trace winning NYC temperature quotes through the frozen daily selection gates."""
import gzip
import hashlib
import json
from collections import Counter
from decimal import Decimal

from .tail import MAX_ASK, ROOT, SNAPSHOT
from .tail_daily import prepare


def stage(row, day, picks):
    signal, entry = (Decimal(row[k]) if row[k] is not None else None
                     for k in ("ask_signal", "ask_entry"))
    if signal is None or entry is None:
        return "missing_quote"
    if not (0 < signal <= MAX_ASK and 0 < entry <= MAX_ASK):
        return "outside_cheap_quote_cap"
    if row["volume_signal"] <= 0:
        return "no_prior_volume"
    if row["volume_entry"] < 1:
        return "no_entry_volume"
    if day not in picks:
        return "no_daily_pick"
    return "picked" if picks[day] == row["ticker"] else "another_contract_picked"


def main():
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    days = json.loads(raw)["days"]
    picks = {day: row["ticker"] for month in prepare(days).values() for day, _, row, _ in month}
    output = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "periods": {}}
    for year in ("2024", "2025"):
        counts = {label: Counter() for label in ("winning", "losing", "other")}
        rows = []
        for day, record in days.items():
            if not day.startswith(year):
                continue
            for row in record["candidates"]:
                label = {"yes": "winning", "no": "losing"}.get(row["result"], "other")
                reason = stage(row, day, picks)
                counts[label][reason] += 1
                if label == "winning" and reason in ("no_prior_volume", "no_entry_volume",
                                                     "no_daily_pick", "another_contract_picked", "picked"):
                    rows.append({"day": day, "ticker": row["ticker"], "reason": reason,
                                 "p": row["probability"], "ask_signal": row["ask_signal"],
                                 "ask_entry": row["ask_entry"], "prior_volume": row["volume_signal"],
                                 "entry_volume": row["volume_entry"], "selected": picks.get(day)})
        output["periods"][year] = {"counts": counts, "quoted_affordable_winners": rows}
    (ROOT / "tail_attrition_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
