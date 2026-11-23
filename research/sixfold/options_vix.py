"""Use VIX direction before Monday as a fixed direction signal for BTC options."""
import gzip
import hashlib
import json
import random
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from .options import WALLET
from .options_fetch import HERE
from .options_weekly import SNAPSHOT, month_run, reached
from ..world_signals.vix_fear import INPUT as VIX


def rules(rows, vix):
    dates = sorted(vix)

    def observed(anchor):
        i = bisect_right(dates, anchor.isoformat()) - 1
        if i < 0 or (anchor - date.fromisoformat(dates[i])).days > 2:
            return None
        return vix[dates[i]]

    result = defaultdict(list)
    for row in rows:
        day = date.fromisoformat(row["entry_day"])
        now = observed(day - timedelta(days=3))
        prev = observed(day - timedelta(days=10))
        if now is None or prev is None or now == prev:
            continue
        result[row["month"]].append((row, "P" if now > prev else "C"))
    return result


def run(plan, months, tape, target, cost, rng=None, detail=False):
    cash = peak = WALLET
    path = []
    hits = funded = 0
    dd = 0.
    for month in months:
        before = cash
        entries = plan[month]
        sides = [rng.choice("CP") if rng else side for _, side in entries]
        cash, records = month_run([row for row, _ in entries], tape, target, cost, before,
                                  sides=sides, detail=True, budget_fraction=.5)
        hit = reached(cash, before * target) if before else False
        hits += hit
        funded += hit and before >= WALLET
        peak = max(peak, cash)
        dd = max(dd, 1-cash/peak)
        if detail:
            path.append({"month": month, "start": before, "end": cash, "orders": records})
    return {"end": cash, "hits": hits, "funded_hits": funded, "drawdown_month_end": dd} | (
        {"months": path} if detail else {})


def main():
    weekly_raw, vix_raw = [gzip.decompress(p.read_bytes()) for p in (SNAPSHOT, VIX)]
    btc = json.loads(weekly_raw)["assets"]["BTC"]
    vix = json.loads(vix_raw)["indices"]["VIX"]
    plan = rules(btc["rows"], vix)
    months = [f"{y}-{m:02d}" for y,n in ((2025,12),(2026,10)) for m in range(1,n+1)]
    data = {"weekly_sha256": hashlib.sha256(weekly_raw).hexdigest(),
            "vix_sha256": hashlib.sha256(vix_raw).hexdigest(), "eligible_weeks": sum(map(len,plan.values())),
            "periods": {}}
    for label, period in (("2025",months[:12]), ("2026",months[12:]), ("continuous",months)):
        sub = data["periods"][label] = {}
        for target in (3,6):
            for name, cost in (("base",(.15,.05)),("stress",(.35,.15))):
                x = sub[f"{target}x_{name}"] = run(plan, period, btc["sales"], target, cost, detail=True)
                rng = random.Random(28143)
                draws = [run(plan, period, btc["sales"], target, cost, rng)["end"] for _ in range(500)]
                x["random_median_end"] = median(draws)
                x["random_fraction_ge"] = sum(d >= x["end"] for d in draws)/len(draws)
    (HERE / "options_vix_results.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
