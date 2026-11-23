"""Trace eligible funded 3x months to their unique public Deribit sale prints."""
import json
import hashlib

from .options import WALLET
from .options_fetch import HERE, trade_range
from .options_weekly import reached

SOURCES = {
    "vix": (("periods","2026","3x_base","months"), "orders"),
    "agreement": (("cases","2026","3x_base","agreement","months"), "trades"),
    "budget": (("assets","BTC","2026","3x_base_0.5_cap","continuous"), "weeks"),
}
CHECK = HERE / "options_hit_overlap_trade_checks.json"
RESULT = HERE / "options_hit_overlap_results.json"


def main():
    checks = json.loads(CHECK.read_text()) if CHECK.exists() else {}
    output = {"source_sha256": {}, "funded_months": [], "unique_sales": {}}
    for label, (keys, orders) in SOURCES.items():
        raw = (HERE / f"options_{label}_results.json").read_bytes()
        rows = json.loads(raw)
        for key in keys:
            rows = rows[key]
        output["source_sha256"][label] = hashlib.sha256(raw).hexdigest()
        for row in rows:
            start = row.get("start", row.get("starting"))
            end = row.get("end", row.get("ending"))
            if start < WALLET or not reached(end, 3 * start):
                continue
            sales = []
            for step in row[orders]:
                if step.get("modeled_exit") != "early":
                    continue
                model = step["sale_print"]
                ticket = model["trade_id"]
                if ticket not in checks:
                    response = trade_range(step["instrument"], model["timestamp"], model["timestamp"])
                    checks[ticket] = response["trades"]
                actual = next(p for p in checks[ticket] if p["trade_id"] == ticket)
                assert actual["amount"] >= step["contract_units"] and actual["direction"] == "sell"
                assert actual["price"] == model["price"] and actual["timestamp"] == model["timestamp"]
                sales.append(ticket)
                output["unique_sales"][ticket] = {"instrument": step["instrument"], "price": actual["price"],
                    "observed_size": actual["amount"], "simulated_size": step["contract_units"],
                    "timestamp": actual["timestamp"]}
            output["funded_months"].append({"rule": label, "month": row["month"], "start": start,
                                             "end": end, "sale_ids": sales})
    CHECK.write_text(json.dumps(checks, indent=2) + "\n")
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
