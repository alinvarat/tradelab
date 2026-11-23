"""Diagnose a delayed reversal on the known Bybit delisting calendar."""
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from .delist_rebound_articles import INPUT
from .spot import BASE_COST, HERE, STRESS_COST

# Confirmed removal dates in the corresponding Bybit article text.
STOP = {
    "bltdbc6fb605a3bb8c6": "2026-05-19",
    "art81c9cb138ade": "2026-07-16",
    "artc357601e1303": "2026-07-23",
    "art406557a5a84a": "2026-08-04",
    "art29ea635c889e": "2026-08-25",
    "art2489b2a8c89e": "2026-08-27",
    "art74f3fc794bf8": "2026-09-04",
    "art6d24cb99655a": "2026-09-17",
    "art1a1071a0dd4e": "2026-09-24",
    "art1b7b7449b6c5": "2026-10-08",
    "art0d9083316016": "2026-10-28",
}


def run(data, cost):
    factor = (1 - cost) / (1 + cost)
    trades = defaultdict(list)
    for published, url, names in data["events"]:
        stop = date.fromisoformat(next(value for key, value in STOP.items() if key in url))
        day = date.fromisoformat(published) + timedelta(days=3)
        if day >= stop:
            continue
        control = (day - timedelta(days=7)).isoformat()
        for symbol in names:
            bars = data["prices"][symbol]["bars"]
            sample = bars.get(day.isoformat())
            prior = bars.get(control)
            trades[day.isoformat()].append({
                "symbol": symbol, "url": url, "removal": stop.isoformat(),
                "net_multiple": sample[3] / sample[0] * factor if sample else None,
                "control_multiple": prior[3] / prior[0] * factor if prior and sample else None,
            })
    balance, peak, drawdown = 5000., 5000., 0.
    months = dict.fromkeys((f"2026-{m:02d}" for m in range(1, 11)), 1.)
    pairs = []
    for day, batch in sorted(trades.items()):
        growth = mean(1 if x["net_multiple"] is None else x["net_multiple"] for x in batch)
        months[day[:7]] *= growth
        balance *= growth
        peak = max(balance, peak)
        drawdown = max(drawdown, 1 - balance / peak)
        pairs.extend((x["net_multiple"], x["control_multiple"]) for x in batch if x["control_multiple"] is not None)
    return {"ending_thb": balance, "months": months, "3x_months": sum(x >= 3 for x in months.values()),
            "6x_months": sum(x >= 6 for x in months.values()), "drawdown_day_closes": drawdown,
            "eligible_dates": len(trades), "trades": trades, "paired_control_count": len(pairs),
            "paired_mean_actual": mean(x - 1 for x, _ in pairs) if pairs else None,
            "paired_mean_control": mean(x - 1 for _, x in pairs) if pairs else None}


def main():
    raw = gzip.decompress(INPUT.read_bytes())
    data = json.loads(raw)
    result = {"input_sha256": hashlib.sha256(raw).hexdigest(),
              "cases": {k: run(data, fee) for k, fee in (("base", BASE_COST), ("stress", STRESS_COST))}}
    (HERE / "delist_delayed_results.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
