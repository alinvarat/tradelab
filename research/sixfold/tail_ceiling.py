"""Test whether winning weather contracts have sufficient observed volume for the goal."""
import gzip
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
from collections import defaultdict

from .tail import CENT, MAX_ASK, NEW_YORK, ROOT, SNAPSHOT, STAKE, TAKER, boundary


def best_offers(days, slip):
    months = defaultdict(list)
    for iso, day in sorted(days.items()):
        entry_time = boundary(date.fromisoformat(iso))
        for row in day["candidates"]:
            if row["result"] != "yes" or not row["settlement_ts"]:
                continue
            signal, entry = (Decimal(row[x]) if row[x] is not None else 0 for x in ("ask_signal", "ask_entry"))
            if not (0 < signal <= MAX_ASK and 0 < entry <= MAX_ASK):
                continue
            settled = datetime.fromisoformat(row["settlement_ts"]).astimezone(NEW_YORK)
            if settled.isoformat()[:7] != iso[:7] or settled.timestamp() <= entry_time:
                continue
            price = entry + slip
            cost_unit = price + TAKER * price * (1 - price)
            theoretical = int(STAKE // cost_unit)
            for label, qty in (("unlimited", theoretical), ("volume_capped", min(theoretical, int(row["volume_entry"])))):
                while qty > 0:
                    fee = (qty * TAKER * price * (1-price)).quantize(CENT, rounding=ROUND_CEILING)
                    spend = qty * price + fee
                    if spend <= STAKE:
                        months[(iso[:7], label)].append({
                            "ticker": row["ticker"], "day": iso, "quoted": float(entry),
                            "capacity_proxy": row["volume_entry"], "count": qty, "fee": float(fee),
                            "multiple": float((STAKE-spend+qty)/STAKE),
                        })
                        break
                    qty -= 1
    return {label: {f"{y}-{m:02d}": max(months[(f"{y}-{m:02d}", label)],
                                        key=lambda x: x["multiple"], default=None)
                    for y in (2024, 2025) for m in range(1, 13)}
            for label in ("unlimited", "volume_capped")}


def main():
    raw = gzip.decompress(SNAPSHOT.read_bytes())
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "one_winning_trade_per_month_oracle": True,
              "cases": {k: best_offers(json.loads(raw)["days"], slip) for k, slip in
                        (("base", CENT), ("stress", 2 * CENT))}}
    (ROOT / "tail_ceiling_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
