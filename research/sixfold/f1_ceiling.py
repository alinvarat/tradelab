"""Find the hindsight maximum under archived F1 menu and timing constraints."""
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product

from .f1_winner import FX, INPUT, START, menus, trade_price
from .spot import HERE


def optimize(year, month, races, slip):
    end = int(datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc).timestamp())
    menus_by_race = [[None, *(o for o in offers if o["yes"] and o["settle"] < end)]
                     for _, offers in races]
    best = {"ending": START * (1 - FX)**2, "trades": []}
    for sequence in product(*menus_by_race):
        cash, settlement, receipts = START * (1 - FX), 0, 0
        taken = []
        for ((race, _), choice) in zip(races, sequence):
            if choice is None or race["decision"] < settlement:
                continue
            cash += receipts
            receipts = 0
            units, expense = trade_price(choice, slip, cash)
            if units:
                cash -= expense
                receipts = units
                settlement = choice["settle"]
                taken.append({"ticker": choice["ticker"], "units": units, "spend": expense, "settle": settlement})
        value = (cash + receipts) * (1 - FX)
        if value > best["ending"]:
            best = {"ending": value, "trades": taken}
    best["multiple"] = best["ending"] / START
    return best


def main():
    raw = gzip.decompress(INPUT.read_bytes())
    snapshot = json.loads(raw)
    horses = defaultdict(list)
    for race in sorted(snapshot["races"], key=lambda r: r["decision"]):
        decided = datetime.fromtimestamp(race["decision"], timezone.utc)
        _, available = menus(race, snapshot["fit"])
        horses[(decided.year, decided.month)].append((race, available))
    result = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "hindsight_only": True, "cases": {}}
    for label, slip in (("base", .01), ("stress", .02)):
        result["cases"][label] = {
            f"{year}-{month:02d}": optimize(year, month, horses[(year, month)], slip)
            for year, n in ((2025, 12), (2026, 10)) for month in range(1, n+1)
        }
    (HERE / "f1_ceiling_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
