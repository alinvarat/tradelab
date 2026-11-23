"""Synchronize buffered Binance depth updates and reject gaps."""
from datetime import datetime
import json
from decimal import Decimal
from pathlib import Path
import sys


def replay(path, cutoff=None, include_levels=False):
    buffered = []
    book = None
    last = None
    received = None
    closed = False
    stats = {"snapshots": 0, "applied": 0, "stale": 0, "gaps": [], "ignored_after_gap": 0}

    def apply(row):
        nonlocal last
        if last is None:
            stats["ignored_after_gap"] += 1
            return
        if row["u"] <= last:
            stats["stale"] += 1
            return
        if not row["U"] <= last + 1 <= row["u"]:
            stats["gaps"].append([last, row["U"], row["u"]])
            last = None
            return
        for index, side in enumerate(("b", "a")):
            for price, size in row[side]:
                price, size = Decimal(price), Decimal(size)
                if size:
                    book[index][price] = size
                else:
                    book[index].pop(price, None)
        last = row["u"]
        stats["applied"] += 1

    with path.open() as stream:
        for line in stream:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["utc"])
            if cutoff is not None and timestamp > cutoff:
                break
            row = record["data"]
            if record["kind"] == "snapshot":
                book = [{Decimal(p): Decimal(q) for p,q in row[k]} for k in ("bids","asks")]
                last = row["lastUpdateId"]
                stats["snapshots"] += 1
                for event in buffered:
                    apply(event)
                buffered.clear()
                received = timestamp
            elif record["kind"] == "diff":
                if book is None:
                    buffered.append(row)
                else:
                    prior = last
                    apply(row)
                    if last is not None and last != prior:
                        received = timestamp
            elif record["kind"] == "stop":
                closed = True
    stats["last_valid_id"] = last
    stats["best_bid"] = str(max(book[0])) if last is not None and book[0] else None
    stats["best_ask"] = str(min(book[1])) if last is not None and book[1] else None
    if include_levels:
        stats["received"] = received
        stats["closed"] = closed
        stats["levels"] = [sorted(book[0].items(), reverse=True), sorted(book[1].items())] if last is not None else None
    return stats


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1])), indent=2))
