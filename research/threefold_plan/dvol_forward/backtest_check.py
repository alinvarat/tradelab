"""Retrospective sanity check of the locked DVOL strangle design on the 2025-01..2026-10 BTC weekly tape.
NOT validation: the rule is frozen unchanged (30th percentile of 90 daily closes, same 25%+25% sizing); weeks and
fills come from earlier studies. Entry price = first qualifying BUY print in the 2 h after Monday 09:00 UTC (stored as first_print) with
the earlier base (+15% premium markup, 0.25% FX) and stress (+35%, 0.5%) friction; minimum trade size is
ignored (optimistic). Also computes a perfect-hindsight ceiling for THIS structure."""
import gzip
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).parent
WEEKLY = HERE.parents[1] / "sixfold" / "options_weekly_inputs.json.gz"
DVOL_CACHE = HERE / "dvol_hourly_history.json.gz"
OUT = HERE / "backtest_check_results.json"
CASES = {"base": (0.15, 0.0025), "stress": (0.35, 0.005)}
CAP, TAKER = 0.125, 0.0003


def dvol_history():
    if DVOL_CACHE.exists():
        return json.loads(gzip.decompress(DVOL_CACHE.read_bytes()))
    rows, start = {}, int(datetime(2024, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp() * 1000)
    while start < end:
        stop = min(start + 40 * 86400000, end)
        req = Request("https://www.deribit.com/api/v2/public/get_volatility_index_data?" + urlencode(
            {"currency": "BTC", "resolution": "3600", "start_timestamp": start, "end_timestamp": stop}),
            headers={"User-Agent": "tradelab-research"})
        for r in json.loads(urlopen(req, timeout=30).read())["result"]["data"]:
            rows[str(r[0])] = r[4]
        start = stop
    DVOL_CACHE.write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
    return rows


def signal(hist, decision_ms):
    last_complete = decision_ms - 3600000
    now = hist.get(str(last_complete))
    day0 = decision_ms - decision_ms % 86400000
    closes = []
    for d in range(1, 91):  # daily close = last hourly close of that UTC day
        v = hist.get(str(day0 - d * 86400000 + 23 * 3600000))
        if v is not None:
            closes.append(v)
    if now is None or len(closes) < 80:
        return None
    o = sorted(closes)
    k = (len(o) - 1) * 0.30
    lo = int(k)
    thr = o[lo] + (o[min(lo + 1, len(o) - 1)] - o[lo]) * (k - lo)
    return {"dvol": now, "threshold": thr, "trade": now <= thr}


def leg_multiple(row, side, sales, markup, fx):
    spec = row["options"]["20" + side]["spec"]
    name = row["options"]["20" + side]["name"]
    if not spec:
        return None
    fill = row["options"]["20" + side]["first_print"]  # first qualifying BUY print within 2 h (earlier study)
    if fill:
        price = fill["price"] * (1 + markup)
        cost = price + min(TAKER, CAP * price)
        spot = row["official_settlement_usd"]
        k = spec["strike"]
        payoff = max(0.0, (spot - k) if side == "C" else (k - spot)) / spot
        payoff -= min(0.00015, CAP * payoff) if payoff else 0
        return (payoff * (1 - fx)) / (cost * (1 + fx))
    return None


def main():
    data = json.loads(gzip.decompress(WEEKLY.read_bytes()))["assets"]["BTC"]
    hist = dvol_history()
    out = {"weeks": len(data["rows"]), "cases": {}}
    for case, (markup, fx) in CASES.items():
        weeks = []
        for row in data["rows"]:
            c, p = (leg_multiple(row, s, data["sales"], markup, fx) for s in "CP")
            legs = [m for m in (c, p) if m is not None]
            mult = 1 - 0.25 * len(legs) + 0.25 * sum(legs) if legs else 1.0
            weeks.append({"entry": row["entry_day"], "month": row["month"], "mult": mult, "legs": len(legs),
                          "sig": signal(hist, row["chosen_at"])})

        def monthly(select):
            res = {}
            for w in weeks:
                m = res.setdefault(w["month"], 1.0)
                if select(w):
                    res[w["month"]] = m * w["mult"]
            return res
        rules = {"signal": lambda w: bool(w["sig"] and w["sig"]["trade"]), "every_week": lambda w: True,
                 "oracle_best_weeks": lambda w: w["mult"] > 1}
        case_out = {}
        for name, select in rules.items():
            mo = monthly(select)
            wallet = 1.0
            for w in weeks:
                if select(w):
                    wallet *= w["mult"]
            case_out[name] = {"weeks_traded": sum(select(w) for w in weeks), "months_ge_3x": sum(v >= 3 for v in mo.values()),
                              "best_month": max(mo.values()), "median_month": median(mo.values()),
                              "months_below_half": sum(v <= .5 for v in mo.values()),
                              "continuous_multiple": wallet}
        case_out["signal_weeks_with_data"] = sum(1 for w in weeks if w["sig"])
        case_out["weeks_without_dvol_signal"] = sum(1 for w in weeks if not w["sig"])
        case_out["mean_week_multiple"] = {"signal": sum(w["mult"] for w in weeks if w["sig"] and w["sig"]["trade"]) /
                                          max(1, sum(1 for w in weeks if w["sig"] and w["sig"]["trade"])),
                                          "other": sum(w["mult"] for w in weeks if w["sig"] and not w["sig"]["trade"]) /
                                          max(1, sum(1 for w in weeks if w["sig"] and not w["sig"]["trade"]))}
        case_out["best_week_multiples"] = sorted((round(w["mult"], 2) for w in weeks), reverse=True)[:6]
        out["cases"][case] = case_out
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
