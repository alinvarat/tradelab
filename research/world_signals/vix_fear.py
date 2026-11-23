"""Replay the frozen VIX9D crossover with actual next-session UVXY bars."""
import csv
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from statistics import mean
from math import prod
from concurrent.futures import ThreadPoolExecutor

from core.data import get_json, http_get

HERE = Path(__file__).resolve().parent
INPUT = HERE / "vix_fear_inputs.json.gz"
RESULT = HERE / "vix_fear_results.json"
URLS = {
    x: f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{x}_History.csv"
    for x in ("VIX", "VIX9D")
}
END = "2026-10-31"


def index(name):
    rows = csv.DictReader(http_get(URLS[name]).decode("utf-8-sig").splitlines())
    return {
        d: float(row["CLOSE"])
        for row in rows
        if "2018-12-01" <= (d := datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat()) <= END
    }


def etf_bars():
    start = int(datetime(2018, 12, 1, tzinfo=timezone.utc).timestamp())
    stop = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/UVXY?period1={start}&period2={stop}&interval=1d"
    chart = get_json(url)["chart"]["result"][0]
    quotes = chart["indicators"]["quote"][0]
    ny = ZoneInfo("America/New_York")
    return [
        {"d": datetime.fromtimestamp(t, ny).date().isoformat(), "o": o, "c": c, "v": v}
        for t, o, c, v in zip(chart["timestamp"], quotes["open"], quotes["close"], quotes["volume"])
        if o is not None and c is not None and v is not None
    ]


def acquire():
    with ThreadPoolExecutor(3) as pool:
        etf = pool.submit(etf_bars)
        indices = dict(zip(URLS, pool.map(index, URLS)))
        rows = [bar for bar in etf.result() if bar["d"] <= END]
    packed = json.dumps({"indices": indices, "bars": rows, "sources": [*URLS.values(),
                        "https://query1.finance.yahoo.com/v8/finance/chart/UVXY"]}).encode()
    INPUT.write_bytes(gzip.compress(packed, mtime=0))


def months_in(start, end):
    year, month = map(int, start[:7].split("-"))
    while (key := f"{year:04d}-{month:02d}") <= end[:7]:
        yield key
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def summarize(events, months):
    cash = peak = 5000.0
    drawdown = 0.0
    gains = dict.fromkeys(months, 1.0)
    for day, net in events:
        gains[day[:7]] *= 1 + net
        cash *= 1 + net
        peak = max(peak, cash)
        drawdown = max(drawdown, 1 - cash / peak)
    return {
        "balance_thb": cash, "mean_net": mean(net for _, net in events),
        "win_rate": mean(net > 0 for _, net in events),
        "worst_net": min(net for _, net in events),
        "drawdown_closes": drawdown, "months": gains,
        "3x_months": sum(x >= 3 for x in gains.values()),
        "6x_months": sum(x >= 6 for x in gains.values()),
    }


def study(rows, signals, start, end, friction, delay):
    months = list(months_in(start, end))
    available = defaultdict(list)
    chosen = defaultdict(list)
    actions = []
    for i, row in enumerate(rows):
        day = row["d"]
        if not start <= day <= end:
            continue
        net = row["c"] / row["o"] * (1 - friction) / (1 + friction) - 1
        if i - delay in signals:
            chosen[day[:7]].append(net)
            actions.append((day, net))
        else:
            available[day[:7]].append(net)
    observed = summarize(actions, months)
    observed["events"] = actions
    observed["session_count"] = sum(map(len, chosen.values())) + sum(map(len, available.values()))
    if any(len(available[m]) < len(values) for m, values in chosen.items()):
        observed["random"] = None
    else:
        rng = random.Random(32815)
        controls = []
        max_month = 1.0
        hits = dict.fromkeys((3, 6), 0)
        for _ in range(3000):
            draws = [rng.sample(available[m], len(values)) for m, values in chosen.items()]
            controls.append(mean(net for month in draws for net in month))
            multiples = [prod(1 + net for net in month) for month in draws]
            max_month = max(max_month, *multiples)
            for target in hits:
                hits[target] += sum(multiple >= target for multiple in multiples)
        observed["random"] = {
            "draws": len(controls), "mean_net": mean(controls), "max_month": max_month,
            "total_3x_months_across_draws": hits[3], "total_6x_months_across_draws": hits[6],
            "p_ge_observed": (1 + sum(x >= observed["mean_net"] for x in controls)) / (len(controls) + 1),
        }
    observed["balance_after_fx_thb"] = observed["balance_thb"] * .995 ** 2
    return observed


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    data = json.loads(raw)
    rows = data["bars"]
    days = [row["d"] for row in rows]
    assert days == sorted(set(days)) and days[0] <= "2018-12-03" and days[-1] >= "2026-10-30"
    overlap = set(data["indices"]["VIX"]) & set(data["indices"]["VIX9D"])
    assert set(days).issubset(data["indices"]["VIX"]), sorted(set(days) - set(data["indices"]["VIX"]))
    spread = {i: data["indices"]["VIX9D"][d] - data["indices"]["VIX"][d]
              for i, d in enumerate(days) if d in overlap}
    signals = {i for i, value in spread.items() if i - 1 in spread and value > 0 >= spread[i - 1]}
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "periods": {}}
    output["missing_index_sessions"] = sorted(set(days) - overlap)
    for label, start, end in (("comparison", "2019-01-01", "2022-12-31"),
                              ("holdout", "2023-01-01", END),
                              ("full_continuous", "2019-01-01", END)):
        output["periods"][label] = {
            name: study(rows, signals, start, end, friction, delay)
            for name, friction, delay in (("base", .0025, 1), ("cost_stress", .005, 1),
                                          ("delay_cost_stress", .005, 2))
        }
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
