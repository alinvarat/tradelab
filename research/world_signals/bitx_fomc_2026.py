"""Evaluate next-session BITX performance after a dovish rate surprise."""
import gzip
import hashlib
import json
import random
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from core.data import get_json, http_get
from .bitx_weekend import URL
from .fomc import URL as FED_WORKBOOK, statement_rates, stratum
from .vix_fear import HERE, months_in, summarize

INPUT = HERE / "bitx_fomc_2026_inputs.json.gz"
RESULT = HERE / "bitx_fomc_2026_results.json"
START = "2026-01-01"
END = "2026-10-31"


def acquire():
    statement_raw = http_get(FED_WORKBOOK)
    stamps = [int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())
              for d in (START, "2026-11-01")]
    chart = get_json(f"{URL}?period1={stamps[0]}&period2={stamps[1]}&interval=1d")["chart"]["result"][0]
    quotes = chart["indicators"]["quote"][0]
    ny = ZoneInfo("America/New_York")
    bars = {}
    for ts, o, c in zip(chart["timestamp"], quotes["open"], quotes["close"]):
        day = datetime.fromtimestamp(ts, ny).date().isoformat()
        if START <= day <= END and o and c:
            bars[day] = [o, c]
    snapshot = {"statements": statement_rates(statement_raw), "bars": bars,
                "source": URL, "statement_source": FED_WORKBOOK, "statement_sha256": hashlib.sha256(statement_raw).hexdigest()}
    INPUT.write_bytes(gzip.compress(json.dumps(snapshot).encode(), mtime=0))


def score(sessions, mapping, start, end, fee):
    controls, choices, events = defaultdict(list), defaultdict(list), []
    for day, (o, c) in sorted(sessions.items()):
        if not start <= day <= end:
            continue
        ret = c / o * (1 - fee) / (1 + fee) - 1
        group = stratum(day)
        if day not in mapping:
            controls[group].append(ret)
        elif mapping[day][1] is not None and round(mapping[day][1], 10) <= -.05:
            choices[group].append(ret)
            events.append((day, ret))
    if not events:
        return {"events": [], "months": dict.fromkeys(months_in(start, end), 1),
                "3x_months": 0, "6x_months": 0, "ending_thb": 5000}
    output = summarize(events, months_in(start, end))
    output.update({"events": events, "ending_thb": output["balance_thb"] * .995**2})
    if all(len(controls[k]) >= len(vals) for k, vals in choices.items()):
        rng = random.Random(96471)
        draws = [mean(x for k, vals in choices.items() for x in rng.sample(controls[k], len(vals)))
                 for _ in range(3000)]
        output["random_net"] = mean(draws)
        output["p_random_ge"] = (1 + sum(x >= output["mean_net"] for x in draws)) / (len(draws) + 1)
    return output


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    snapshot = json.loads(raw)
    bars = snapshot["bars"]
    days = sorted(bars)
    mapping = {}
    for statement, surprise in snapshot["statements"]:
        if START <= statement <= END and (i := bisect_right(days, statement)) < len(days):
            mapping[days[i]] = [statement, surprise]
    output = {"snapshot_sha256": hashlib.sha256(raw).hexdigest(), "mapping": mapping, "periods": {}}
    for label, start, end in (("holdout_2026", START, END),):
        output["periods"][label] = {cost: score(bars, mapping, start, end, fee)
                                     for cost, fee in (("base", .0025), ("stress", .005))}
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
