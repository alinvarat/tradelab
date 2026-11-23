"""Verify whether two manually confirmed Bybit articles can be joined to candles."""
import gzip
import json
from datetime import datetime, timezone

from .delisting import price_history
from .delist_rebound import FRESH, HERE

KNOWN = {"art0d9083316016": ["HFT"], "art6d24cb99655a": ["L3", "VIC"]}


def main():
    snapshot = json.loads(gzip.decompress(FRESH.read_bytes()))
    output = {}
    for url, announcement in snapshot["archive"].items():
        article = next((x for x in KNOWN if x in url), None)
        if not article:
            continue
        day = datetime.fromtimestamp(announcement["publishTime"] / 1000, timezone.utc).date().isoformat()
        output[url] = {"published": day, "prices": {}}
        for symbol in KNOWN[article]:
            _, bars, error = price_history((day, symbol))
            output[url]["prices"][symbol] = {"bars": bars, "error": error}
    (HERE / "delist_rebound_article_probe.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
