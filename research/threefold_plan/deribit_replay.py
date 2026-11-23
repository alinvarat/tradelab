"""Reconstruct the book only when the Deribit update chain remains valid."""
from datetime import datetime
import json
from pathlib import Path
import sys


def replay(path, cutoff=None, include_levels=False):
    book = {"bids": {}, "asks": {}}
    last = None
    book_time = index_time = index = None
    closed = False
    gaps, invalid, snapshots, changes = [], 0, 0, 0
    with path.open() as source:
        for line in source:
            record = json.loads(line)
            stamp = datetime.fromisoformat(record["utc"])
            if cutoff is not None and stamp > cutoff:
                break
            if record["kind"] == "stop":
                closed = True
            if record["kind"] != "message" or record["data"].get("method") != "subscription":
                continue
            message = record["data"]["params"]
            row = message["data"]
            if message["channel"].startswith("ticker."):
                index = row.get("index_price")
                index_time = stamp
                continue
            if row["type"] == "snapshot":
                book = {"bids": {}, "asks": {}}
                snapshots += 1
            elif last is None or row.get("prev_change_id") != last:
                if last is not None:
                    gaps.append([last, row.get("prev_change_id"), row["change_id"]])
                invalid += 1
                last = None
                continue
            else:
                changes += 1
            for side in book:
                for action, price, size in row[side]:
                    if action == "delete":
                        book[side].pop(price, None)
                    elif action in ("new", "change"):
                        book[side][price] = size
                    else:
                        raise ValueError(action)
            last = row["change_id"]
            book_time = stamp
    result = {"snapshots": snapshots, "applied_changes": changes,
            "ignored_changes": invalid, "gaps": gaps, "last_valid_id": last,
            "best_bid": max(book["bids"], default=None) if last is not None else None,
            "best_ask": min(book["asks"], default=None) if last is not None else None}

    if include_levels:
        result.update({"levels": book if last is not None else None, "book_time": book_time,
                       "index_price": index, "index_time": index_time, "closed": closed})
    return result


if __name__ == "__main__":
    print(json.dumps(replay(Path(sys.argv[1])), indent=2))
