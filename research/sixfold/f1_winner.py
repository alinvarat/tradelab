"""Run the predeclared pre-race Kalshi F1 qualifying-rank test."""
import csv
import gzip
import hashlib
import io
import json
import math
import random
import statistics
import unicodedata
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import urlopen

from .tail import API, ROOT, get

SERIES = "KXF1RACE"
SOURCE = "https://github.com/f1db/f1db/releases/download/v2026.21.0/f1db-csv.zip"
INPUT = ROOT / "f1_winner_inputs.json.gz"
RESULT = ROOT / "f1_winner_results.json"
START = 147
FX = .0025


def ts(value):
    return int(datetime.fromisoformat(value).timestamp())


def utc(value):
    return datetime.fromtimestamp(value, timezone.utc)


def name(value):
    return "".join(x for x in unicodedata.normalize("NFKD", value.lower()) if x.isalnum())


def sports():
    with urlopen(SOURCE, timeout=25) as resp:
        raw = resp.read()
    archive = zipfile.ZipFile(io.BytesIO(raw))

    def rows(key):
        return csv.DictReader(archive.read(f"f1db-{key}.csv").decode().splitlines())

    drivers = {x["id"]: [x["name"], x["fullName"], x["abbreviation"]] for x in rows("drivers")}
    winners = {x["raceId"]: x["driverId"] for x in rows("races-race-results")
               if x["positionNumber"] == "1"}
    qual = defaultdict(dict)
    for x in rows("races-qualifying-results"):
        if x["positionNumber"] in {"1", "2", "3", "4", "5"}:
            qual[x["raceId"]][int(x["positionNumber"])] = x["driverId"]
    fit = Counter()
    test = []
    for r in rows("races"):
        year, rid = int(r["year"]), r["id"]
        if year < 2014 or rid not in winners or len(qual[rid]) != 5:
            continue
        if year <= 2024:
            fit["total"] += 1
            for rank, driver in qual[rid].items():
                fit[str(rank)] += driver == winners[rid]
            continue
        if r["date"] > "2026-10-31":
            continue
        test.append({"date": r["date"], "race": r["officialName"],
                     "start": ts(r["date"] + "T" + r["time"] + "+00:00"),
                     "qual_start": ts(r["qualifyingDate"] + "T" + r["qualifyingTime"] + "+00:00"),
                     "qualifiers": qual[rid], "winner": winners[rid]})
    return fit, test, drivers, hashlib.sha256(raw).hexdigest()


def archives():
    events = defaultdict(list)
    for history in (True, False):
        cursor = None
        while True:
            params = {"series_ticker": SERIES, "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            page = get(API, "/historical/markets" if history else "/markets", **params)
            for market in page["markets"]:
                events[market["event_ticker"]].append((history, market))
            cursor = page["cursor"]
            if not cursor:
                break
    return events


def parse_unsuffixed(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value / 100
    # Historical endpoint now returns decimal-dollar strings even here.
    parsed = float(value)
    if not 0 <= parsed <= 1:
        raise ValueError(f"Unexpected candle price: {value}")
    return parsed


def offer(job):
    time, history, market = job
    ticker = market["ticker"]
    path = (f"/historical/markets/{ticker}/candlesticks" if history else
            f"/series/{SERIES}/markets/{ticker}/candlesticks")
    data = get(API, path, start_ts=time-3600, end_ts=time+3600, period_interval=60)
    candles = {x["end_period_ts"]: x for x in (data or {}).get("candlesticks", [])}
    a, b = candles.get(time, {}), candles.get(time + 3600, {})

    def field(row, key, name):
        value = row.get(key, {}).get(name + "_dollars")
        if value is None:
            cents = row.get(key, {}).get(name)
            return parse_unsuffixed(cents)
        return float(value)

    return {"ticker": ticker, "signal": field(a, "yes_ask", "close"),
            "entry": field(b, "yes_ask", "open"),
            "volume_prior": float(a.get("volume_fp", a.get("volume", 0))),
            "volume_entry": float(b.get("volume_fp", b.get("volume", 0)))}


def acquire():
    fit, races, drivers, sha = sports()
    events = archives()
    with ThreadPoolExecutor(max_workers=7) as pool:
        pending = {}
        for race in races:
            race["decision"] = stamp = race["start"] // 3600 * 3600 - 7200
            race["offers"] = []
            matched = [rows for rows in events.values()
                       if any(m.get("settlement_ts") and 0 < ts(m["close_time"]) - race["start"] < 18*3600
                              and m.get("result") == "yes" for _, m in rows)]
            if len(matched) != 1 or stamp - race["qual_start"] < 10800:
                race["status"] = "no_unique_active_event" if len(matched) != 1 else "early_qualifying"
                continue
            markets = matched[0]
            winner_names = set(map(name, drivers[race["winner"]]))
            if not any(name(m["yes_sub_title"]) in winner_names and m["result"] == "yes" for _, m in markets):
                race["status"] = "winner_mismatch"
                continue
            race["status"] = "matched"
            race["event"] = markets[0][1]["event_ticker"]
            for rank, driver in race["qualifiers"].items():
                names = set(map(name, drivers[driver]))
                items = [(history, m) for history, m in markets
                         if name(m["yes_sub_title"]) in names and m.get("result") in ("yes", "no")
                         and m.get("settlement_ts") and ts(m["open_time"]) <= stamp - 3600]
                if len(items) != 1:
                    continue
                history, m = items[0]
                record = {"rank": rank, "yes": m["result"] == "yes", "settle": ts(m["settlement_ts"])}
                race["offers"].append(record)
                pending[pool.submit(offer, (stamp, history, m))] = record
        print(f"{len(races)} races, {len(pending)} contracts to query", flush=True)
        for i, (future, record) in enumerate(pending.items(), 1):
            record.update(future.result())
            if i % 25 == 0:
                print(f"{i}/{len(pending)} quote requests", flush=True)
    packed = json.dumps({"fit": dict(fit), "races": races, "sport_snapshot_sha256": sha})
    INPUT.write_bytes(gzip.compress(packed.encode(), mtime=0))


def unit(ask, slip):
    price = ask + slip
    return price + .07 * price * (1-price)


def trade_price(row, slip, balance):
    price = row["entry"] + slip
    count = min(math.floor(balance * .5 / unit(row["entry"], slip)), math.floor(row["volume_entry"]))
    while count:
        amount = count * price + math.ceil(.07 * count * price * (1-price) * 100 - 1e-10) / 100
        if amount <= balance * .5:
            return count, amount
        count -= 1
    return 0, 0


def menus(race, fit):
    choices = []
    candidates = []
    for row in race["offers"]:
        ask, entry = row["signal"], row["entry"]
        if not ask or row["volume_prior"] <= 0 or ask > .32:
            continue
        prob = fit[str(row["rank"])] / fit["total"]
        row = row | {"signal_edge": prob - unit(ask, .01)}
        candidates.append(row)
        if entry and entry <= .32 and row["volume_entry"] >= 1:
            choices.append(row | {"entry_edge": prob - unit(entry, .01)})
    best = max(candidates, key=lambda row: (row["signal_edge"], -row["rank"]), default=None)
    selected = next((r for r in choices if best and r["rank"] == best["rank"]
                     and r["signal_edge"] >= .03 and r["entry_edge"] >= .03), None)
    return selected, choices


def trial(months, slip, path, rng=None, details=False):
    cash, active, equity_peak, drawdown = START*(1-FX), None, START, 0
    results = []
    last_end = START
    for year, month, pairs in months:
        next_month = (month % 12) + 1
        boundary = int(datetime(year + (month == 12), next_month, 1, tzinfo=timezone.utc).timestamp())
        if not path:
            cash, active, last_end = START*(1-FX), None, START
        trades = []
        for race, (selected, choices) in pairs:
            if active and active[0] <= race["decision"]:
                cash += active[1]
                active = None
            if active:
                continue
            if rng:
                selected = rng.choice(choices) if choices else None
            if not selected:
                continue
            count, spend = trade_price(selected, slip, cash)
            if not count:
                continue
            cash -= spend
            active = selected["settle"], count if selected["yes"] else 0
            trades.append({"ticker": selected["ticker"], "units": count, "spend": spend,
                           "payout": active[1], "settle": active[0]})
        if active and active[0] < boundary:
            cash += active[1]
            active = None
        end = cash*(1-FX)
        equity_peak = max(equity_peak, end)
        drawdown = max(drawdown, 1 - end/equity_peak)
        results.append({"month": f"{year}-{month:02}", "start": last_end, "end": end,
                        "multiple": end/last_end if last_end else None, "trades": trades})
        last_end = end
    summary = {"end": last_end, "drawdown_month_end": drawdown}
    for target in (3, 6):
        summary[f"hits_{target}x"] = sum((r["multiple"] or 0) >= target for r in results)
        summary[f"funded_hits_{target}x"] = sum((r["multiple"] or 0) >= target and r["start"] >= START for r in results)
    summary["half_loss_months"] = sum(r["multiple"] is not None and r["multiple"] <= .5 for r in results)
    executed = [t for r in results for t in r["trades"]]
    summary["trades"] = len(executed)
    summary["wins"] = sum(t["payout"] > 0 for t in executed)
    summary["mean_trade_net"] = statistics.mean((t["payout"]-t["spend"])/t["spend"] for t in executed) if executed else None
    return summary | ({"months": results} if details else {})


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    snapshot = json.loads(raw)
    grouped = defaultdict(list)
    for race in snapshot["races"]:
        grouped[race["date"][:7]].append((race, menus(race, snapshot["fit"])))
    result = {"input_sha256": hashlib.sha256(raw).hexdigest(), "fit": snapshot["fit"],
              "race_audit": [{k: v for k, v in r.items() if k != "offers"} |
                             {"queried": len(r["offers"]), "quotes": sum(o["entry"] is not None for o in r["offers"]),
                              "executable_benchmark": len(menus(r, snapshot["fit"])[1]),
                              "signal_selected": (menus(r, snapshot["fit"])[0] or {}).get("ticker")}
                             for r in snapshot["races"]], "outcomes": {}}
    for label, years in (("2025", (2025,)), ("2026", (2026,)), ("continuous", (2025, 2026))):
        months = [(y, m, grouped[f"{y}-{m:02}"]) for y in years for m in range(1, 13 if y == 2025 else 11)]
        for cost, slip in (("base", .01), ("stress", .02)):
            for path in (True, False):
                actual = trial(months, slip, path, details=True)
                rng = random.Random(549)
                controls = [trial(months, slip, path, rng) for _ in range(1000)]
                actual["control"] = {f"p_ge_{k}": (1+sum(x[k] >= actual[k] for x in controls))/1001
                                     for k in ("hits_3x", "hits_6x")}
                if path:
                    actual["control"]["p_ge_end"] = (1+sum(x["end"] >= actual["end"] for x in controls))/1001
                key = f"{label}_{cost}_{'path' if path else 'reset'}"
                result["outcomes"][key] = actual
    RESULT.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
