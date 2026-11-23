"""Run from TradeLab with python3 -m research.world_signals.fomc."""
import argparse
import hashlib
import io
import json
import math
import random
import re
from bisect import bisect_right
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from statistics import mean
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from core.data import get_json, http_get
from core.research import COST
from research.events import bars

OUT = Path(__file__).resolve().parent
URL = "https://www.frbsf.org/wp-content/uploads/USMPD.xlsx"
BASE_COST = 3 * COST
PERIODS = [(2010, 2020), (2021, 2025), (2021, 2022), (2023, 2025)]
SYMBOLS = ("SPY", "QQQ")
DRAWS = 10_000


def statement_rates(workbook):
    """Read the publicly documented Statements sheet, retaining missing ED4."""
    with ZipFile(io.BytesIO(workbook)) as archive:
        root = ET.fromstring(archive.read("xl/worksheets/sheet2.xml"))
    rows = []
    for row in root.findall(".//{*}row"):
        rows.append({
            re.match(r"[A-Z]+", cell.attrib["r"])[0]:
            cell.findtext(".//{*}t") if cell.attrib["t"] == "inlineStr" else cell.findtext("{*}v")
            for cell in row.findall("{*}c")
        })
    header = {label: column for column, label in rows[0].items()}
    return [
        [(date(1899, 12, 30) + timedelta(days=int(float(row[header["Date"]])))).isoformat(),
         float(value) if (value := row.get(header["ED4"])) is not None else None]
        for row in rows[1:] if row.get(header["Date"])
    ]


def us_market(symbol):
    """Recover exchange day before joining a US ETF to a New York event date."""
    p1 = int(datetime.fromisoformat("2009-01-01T00:00:00+00:00").timestamp())
    # bars() requests through current time. Read raw timestamps with a fixed cutoff
    # separately so the provider's actual exchange-date convention is checked.
    p2 = int(datetime.fromisoformat("2026-01-01T00:00:00+00:00").timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={p1}&period2={p2}&interval=1d"
    timestamps = get_json(url)["chart"]["result"][0]["timestamp"]
    ny = ZoneInfo("America/New_York")
    exchange_days = {datetime.fromtimestamp(t + 43200, ZoneInfo("UTC")).date().isoformat():
                     datetime.fromtimestamp(t, ny).date().isoformat() for t in timestamps}
    return [
        {"d": exchange_days[b["d"]], "o": b["o"], "c": b["c"]}
        for b in bars(symbol, "2009-01-01") if b["d"] in exchange_days
    ]


def stratum(day):
    d = date.fromisoformat(day)
    return d.year, (d.month - 1) // 3, d.weekday()


def study(symbol, market, statements, start, end):
    dates = [bar["d"] for bar in market]
    raw = {bar["d"]: bar["c"] / bar["o"] - 1 for bar in market}
    matched = defaultdict(list)
    all_event_entries = set()
    triggers = set()
    in_period = lambda day: start <= int(day[:4]) <= end
    relevant = [row for row in statements if in_period(row[0])]
    for event, rate in statements:
        idx = bisect_right(dates, event)
        if idx == len(dates):
            continue
        entry = dates[idx]
        all_event_entries.add(entry)
        if in_period(event) and in_period(entry) and rate is not None and round(rate, 8) <= -0.05:
            triggers.add(entry)
    for day, ret in raw.items():
        if in_period(day) and day not in all_event_entries:
            matched[stratum(day)].append(ret)

    trading_days = sorted(triggers)
    gross = [raw[day] for day in trading_days]
    net = [r - BASE_COST for r in gross]
    months = defaultdict(lambda: 1.0)
    month_peaks = defaultdict(lambda: 1.0)
    equity = peak = 1.0
    drawdown = 0.0
    for day, ret in zip(trading_days, net):
        equity *= 1 + ret
        peak = max(equity, peak)
        drawdown = min(drawdown, equity / peak - 1)
        months[day[:7]] *= 1 + ret
        month_peaks[day[:7]] = max(month_peaks[day[:7]], months[day[:7]])
    out = {
        "symbol": symbol, "period": [start, end], "n": len(net),
        "statement_count": len(relevant),
        "missing_ed4": sum(r is None for _, r in relevant),
        "trades_per_year": len(net) / (end - start + 1),
        "trade_close_max_drawdown_pct": drawdown * 100,
        "months_at_6x": sum(x >= 6 for x in month_peaks.values()),
        "calendar_months": 12 * (end - start + 1),
        "max_month_pct": (max([1.0, *months.values()]) - 1) * 100,
        "trades": [{"date": d, "gross_pct": r * 100} for d, r in zip(trading_days, gross)],
    }
    if not net:
        return out
    pool = [matched[stratum(day)] for day in trading_days]
    if not all(pool):
        raise ValueError(f"{symbol}: empty matched stratum")
    rng = random.Random(8770)
    baseline = [mean(rng.choice(p) - BASE_COST for p in pool) for _ in range(DRAWS)]
    observed = mean(net)
    out.update(
        net_mean_pct=observed * 100, stress_net_mean_pct=(mean(gross) - 3 * BASE_COST) * 100,
        win_pct=100 * sum(r > 0 for r in net) / len(net), worst_trade_pct=min(net) * 100,
        random_mean_pct=mean(baseline) * 100, edge_pct=(observed - mean(baseline)) * 100,
        p_random=(1 + sum(r >= observed for r in baseline)) / (1 + DRAWS),
    )
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="download a new snapshot")
    args = parser.parse_args()
    inputs = OUT / "fomc_inputs.json"
    if args.refresh or not inputs.exists():
        with ThreadPoolExecutor() as pool:
            market = dict(zip(SYMBOLS, pool.map(us_market, SYMBOLS)))
        book = http_get(URL)
        snapshot = {
            "source": URL, "market_session_date": "America/New_York", "xlsx_sha256": hashlib.sha256(book).hexdigest(),
            "statements": [row for row in statement_rates(book) if "2009" <= row[0] < "2026"],
            "markets": {s: [{k: b[k] for k in ("d", "o", "c")} for b in market[s] if b["d"] < "2026"]
                        for s in SYMBOLS},
        }
        if any(len(b) < 3700 for b in snapshot["markets"].values()) or len(snapshot["statements"]) < 100:
            raise ValueError("Incomplete market or statements snapshot")
        inputs.write_text(json.dumps(snapshot, separators=(",", ":")) + "\n")
    snapshot = json.loads(inputs.read_text())
    if snapshot.get("market_session_date") != "America/New_York":
        raise ValueError("Run --refresh to replace the old snapshot with exchange dates")
    rows = [study(s, snapshot["markets"][s], snapshot["statements"], a, b)
            for s in SYMBOLS for a, b in PERIODS]
    _, test, first, last, _, transfer, _, _ = rows
    gates = {
        "30_events": test["n"] >= 30,
        "positive_net": test.get("net_mean_pct", -math.inf) > 0,
        "random_adjusted": test.get("p_random", 1) <= 0.0125,
        "two_subperiods_positive_edge": all(r.get("edge_pct", -math.inf) > 0 for r in (first, last)),
        "stress_positive": test.get("stress_net_mean_pct", -math.inf) > 0,
        "transfer_positive": transfer.get("net_mean_pct", -math.inf) > 0,
    }
    result = {"primary_rules": 1, "fixed_transfer_assets": 1, "random_draws": DRAWS,
              "base_round_trip_pct": BASE_COST * 100, "stress_round_trip_pct": BASE_COST * 300,
              "gate": gates, "deploy": all(gates.values()), "rows": rows}
    (OUT / "fomc_results.json").write_text(json.dumps(result, indent=2) + "\n")
    for row in rows:
        print({k: round(v, 4) if isinstance(v, float) else v for k, v in row.items() if k != "trades"})
    print(gates)


if __name__ == "__main__":
    main()
