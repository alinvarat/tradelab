"""Score the locked DVOL forward test (protocol.md) from raw snapshots. Simulation only."""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import random
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).parent
RAW = HERE / "raw"
DELIVERY = HERE / "delivery_prices.json"
RESULT = HERE / "results.json"
WALLET = D("147")
MONDAYS = [date(2026, 11, 30) + timedelta(weeks=i) for i in range(13)]
COSTS = {"base": {"slot": 0, "markup": D("1"), "fx": D(".0025")},
         "high": {"slot": 5, "markup": D("1.15"), "fx": D(".005")}}
TAKER, SETTLE, CAP = D(".0003"), D(".00015"), D(".125")


def load_snapshots(folder=RAW):
    snaps = defaultdict(dict)
    for path in sorted(folder.glob("*.json.gz")):
        snap = json.loads(gzip.decompress(path.read_bytes()))
        t = datetime.fromisoformat(snap["started_utc"])
        for slot, lo in ((0, 0), (5, 5)):
            start = t.replace(hour=9, minute=lo, second=0, microsecond=0)
            done = datetime.fromisoformat(snap["finished_utc"])
            if start <= t and done <= t.replace(hour=9, minute=10, second=0, microsecond=0) \
                    and not snap["errors"] and t < start + timedelta(minutes=5):
                snaps[t.date()].setdefault(slot, snap)
    return snaps


def signal(snap):
    hourly = [r for r in snap["dvol_hourly"]["data"]
              if r[0] + 3600000 <= datetime.fromisoformat(snap["started_utc"]).timestamp() * 1000]
    day0 = datetime.fromisoformat(snap["started_utc"]).replace(hour=0, minute=0, second=0, microsecond=0)
    daily = [r[4] for r in snap["dvol_daily"]["data"] if r[0] < day0.timestamp() * 1000][-90:]
    if not hourly or len(daily) < 90:
        return None
    ordered = sorted(daily)
    k = (len(ordered) - 1) * 0.30
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    threshold = ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)
    return {"dvol_now": hourly[-1][4], "threshold": threshold, "trade": hourly[-1][4] <= threshold}


def pick(snap, side):
    spot = snap["index"]["index_price"]
    target = spot * (1.085 if side == "C" else 0.915)
    legs = [i for i in snap["instruments"] if i["option_type"] == ("call" if side == "C" else "put")]
    if not legs:
        return None
    far = (lambda i: i["strike"]) if side == "C" else (lambda i: -i["strike"])
    return min(legs, key=lambda i: (abs(i["strike"] - target), -far(i)))


def buy(snap, inst, budget, cost):
    book = snap["books"].get(inst["instrument_name"])
    if not book or not book["asks"]:
        return None
    step = D(str(inst["min_trade_amount"]))
    fx = D(str(snap["index"]["index_price"])) * (1 + cost["fx"])
    best = None
    n = 1
    while True:
        size, left, prem, fee = step * n, step * n, D(0), D(0)
        for price, qty in book["asks"]:
            take = min(left, D(str(qty)))
            p = D(str(price)) * cost["markup"]
            prem += take * p
            fee += take * min(TAKER, CAP * p)
            left -= take
            if not left:
                break
        if left or (prem + fee) * fx > budget:
            return best
        best = {"instrument": inst["instrument_name"], "size": size, "strike": D(str(inst["strike"])),
                "spent_usd": (prem + fee) * fx, "avg_price_btc": prem / size}
        n += 1


def settle(leg, side, s, cost):
    s = D(str(s))
    intrinsic = max(D(0), (s - leg["strike"]) if side == "C" else (leg["strike"] - s)) / s
    if intrinsic == 0:
        return D(0)
    fee = min(SETTLE, CAP * intrinsic)
    return (intrinsic - fee) * leg["size"] * s * (1 - cost["fx"])


def delivery(day, fetch_page=None):
    """Friday delivery price for the week starting `day`. Pages back (the API caps a page at 100 days)
    and raises if the price cannot be found, so a week is never silently skipped."""
    cache = json.loads(DELIVERY.read_text()) if DELIVERY.exists() else {}
    key = (day + timedelta(days=4)).isoformat()
    offset = 0
    while key not in cache and offset <= 1000:
        if fetch_page:
            rows = fetch_page(offset)
        else:
            req = Request("https://www.deribit.com/api/v2/public/get_delivery_prices?" +
                          urlencode({"index_name": "btc_usd", "count": 100, "offset": offset}),
                          headers={"User-Agent": "tradelab-research"})
            rows = json.loads(urlopen(req, timeout=20).read())["result"]["data"]
        if not rows:
            break
        cache.update({r["date"]: r["delivery_price"] for r in rows})
        offset += 100
    if not fetch_page:
        DELIVERY.write_text(json.dumps(cache, indent=1, sort_keys=True))
    if key not in cache:
        raise RuntimeError(f"no delivery price for {key}")
    return cache[key]


def week(snap, equity, cost, s):
    trades, spent, back = [], D(0), D(0)
    for side in "CP":
        inst = pick(snap, side)
        leg = inst and buy(snap, inst, equity * D(".25"), cost)
        if not leg:
            trades.append({"side": side, "status": "skipped"})
            continue
        value = settle(leg, side, s, cost)
        spent += leg["spent_usd"]
        back += value
        trades.append({"side": side, **{k: str(v) for k, v in leg.items()}, "settle_usd": str(value)})
    return equity - spent + back, trades


def run(plan, weeks, cost_name, settlements):
    cost = COSTS[cost_name]
    equity, peak, dd = WALLET, WALLET, D(0)
    months, log = {}, []
    for day in MONDAYS:
        m = day.isoformat()[:7]
        months.setdefault(m, [equity, equity])
        snap = weeks.get(day, {}).get(cost["slot"])
        if day in plan and snap is not None and settlements.get(day):
            equity, trades = week(snap, equity, cost, settlements[day])
            log.append({"monday": day.isoformat(), "equity": str(equity), "trades": trades})
        months[m][1] = equity
        peak = max(peak, equity)
        dd = max(dd, 1 - equity / peak)
    multiples = {m: (str(e / s) if s else None, s >= WALLET) for m, (s, e) in months.items()}
    return {"ending_usd": equity, "drawdown": dd, "months": multiples, "log": log,
            "3x_months": sum(1 for m, (s, e) in months.items() if s and e / s >= 3),
            "funded_3x_months": sum(1 for m, (s, e) in months.items() if s >= WALLET and e / s >= 3)}


def main(folder=RAW):
    weeks = load_snapshots(folder)
    valid = [d for d in MONDAYS if 0 in weeks.get(d, {}) and (datetime.now(timezone.utc).date() > d + timedelta(days=4))]
    settlements = {d: delivery(d) for d in valid}
    signals = {d: signal(weeks[d][0]) for d in valid}
    chosen = [d for d in valid if signals[d] and signals[d]["trade"]]
    out = {"valid_weeks": [d.isoformat() for d in valid], "missing_weeks": [d.isoformat() for d in MONDAYS if d not in valid],
           "signals": {d.isoformat(): v for d, v in signals.items()}, "cases": {}}
    for cost in COSTS:
        sig = run(set(chosen), weeks, cost, settlements)
        allw = run(set(valid), weeks, cost, settlements)
        rng = random.Random(20261123)
        draws = [run(set(rng.sample(valid, len(chosen))), weeks, cost, settlements)["ending_usd"] for _ in range(1000)] if valid else []
        out["cases"][cost] = {"signal": sig, "unconditional": allw,
                              "random_share_ge_signal": (sum(x >= sig["ending_usd"] for x in draws) / len(draws)) if draws else None,
                              "random_median": str(sorted(draws)[len(draws) // 2]) if draws else None}
    RESULT.write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("valid weeks", len(valid), "signal weeks", len(chosen))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAW)
