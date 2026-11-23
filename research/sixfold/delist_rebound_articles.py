"""Score the frozen rebound rule on 2026 spot pairs confirmed in full articles."""
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from .delist_rebound import candidates
from .delisting import DISCOVERY, price_history
from .spot import BASE_COST, HERE, STRESS_COST
from .spot_volume import evaluate

CATALOG = HERE / "delist_rebound_articles.json"
INPUT = HERE / "delist_rebound_articles_inputs.json.gz"
RESULT = HERE / "delist_rebound_articles_results.json"


def acquire():
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw)
    seen = set()
    events = []
    for row in catalog["accepted"]:
        symbols = sorted(set(row["symbols"]) - seen - DISCOVERY)
        events.append([row["day"], row["url"], symbols])
        seen.update(symbols)
    with ThreadPoolExecutor(6) as pool:
        histories = pool.map(price_history, ((d, s) for d, _, names in events for s in names))
        prices = {s: {"bars": bars, "error": error} for s, bars, error in histories}
    packed = {"catalog_sha256": hashlib.sha256(raw).hexdigest(), "events": events, "prices": prices}
    INPUT.write_bytes(gzip.compress(json.dumps(packed).encode(), mtime=0))


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    snapshot = json.loads(raw)
    choices, bars, coverage = candidates([snapshot])
    months = [f"2026-{m:02d}" for m in range(1,11)]
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "coverage": coverage["2026"],
              "catalog_articles": len(snapshot["events"]), "cases": {}}
    for label, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
        row = output["cases"][label] = evaluate(choices, bars, months, cost)
        row["6x_months"] = sum(value >= 6 for _, value in row["months"])
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
