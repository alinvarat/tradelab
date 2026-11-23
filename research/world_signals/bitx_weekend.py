"""Test whether a BTC weekend gain carries through the following BITX session."""
import gzip
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from core.data import get_json
from research.sixfold.spot_volume import INPUT as SPOT
from .vix_fear import END, HERE, months_in, summarize

INPUT = HERE / "bitx_weekend_inputs.json.gz"
RESULT = HERE / "bitx_weekend_results.json"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/BITX"


def acquire():
    raw = gzip.decompress(SPOT.read_bytes())
    btc = json.loads(raw)["markets"]["BTCUSDT"]
    start = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    stop = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())
    chart = get_json(f"{URL}?period1={start}&period2={stop}&interval=1d")["chart"]["result"][0]
    bars = chart["indicators"]["quote"][0]
    sessions = {}
    ny = ZoneInfo("America/New_York")
    for stamp, op, close in zip(chart["timestamp"], bars["open"], bars["close"]):
        d = datetime.fromtimestamp(stamp, ny).date()
        if d.weekday() or not op or not close or d.isoformat() > END:
            continue
        recent, earlier = ((d - timedelta(days=lag)).isoformat() for lag in (1, 3))
        assert recent in btc and earlier in btc
        sessions[d.isoformat()] = [op, close, btc[recent][3], btc[earlier][3]]
    packed = {"source": URL, "btc_snapshot_sha256": hashlib.sha256(raw).hexdigest(), "sessions": sessions}
    INPUT.write_bytes(gzip.compress(json.dumps(packed).encode(), mtime=0))


def evaluate(sessions, start, end, fee):
    chosen, other = defaultdict(list), defaultdict(list)
    events = []
    for day, (op, close, sunday, friday) in sorted(sessions.items()):
        if not start <= day <= end:
            continue
        q = (day[:4], (int(day[5:7]) - 1) // 3)
        growth = close / op * (1-fee) / (1+fee) - 1
        if sunday >= friday * 1.04:
            chosen[q].append(growth)
            events.append((day, growth))
        else:
            other[q].append(growth)
    output = summarize(events, months_in(start, end))
    output["ending_thb_after_fx"] = output["balance_thb"] * .995**2
    output["events"] = events
    rng = random.Random(70562)
    if all(len(other[q]) >= len(vals) for q, vals in chosen.items()):
        draws = [mean(x for q, vals in chosen.items() for x in rng.sample(other[q], len(vals)))
                 for _ in range(3000)]
        output["control_mean_net"] = mean(draws)
        output["p_control_ge"] = (1 + sum(x >= output["mean_net"] for x in draws)) / (len(draws) + 1)
    return output


def main():
    if not INPUT.exists():
        acquire()
    raw = gzip.decompress(INPUT.read_bytes())
    sessions = json.loads(raw)["sessions"]
    periods = (("2024", "2024-01-01", "2024-12-31"), ("later", "2025-01-01", END),
               ("continuous", "2024-01-01", END))
    output = {"input_sha256": hashlib.sha256(raw).hexdigest(), "usable_mondays": len(sessions),
              "periods": {p: {name: evaluate(sessions, start, end, fee)
                              for name, fee in (("base", .0025), ("stress", .005))}
                          for p, start, end in periods}}
    RESULT.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
