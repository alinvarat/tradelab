"""Audit target events against independent-resolution Binance public minute archives."""
import csv
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from zipfile import ZipFile

from research.sixfold.spot_inputs import ARCHIVE, HERE, download

TARGET = 6
FILL_BUFFER = 0.0025


def aggregate_evidence(symbol, timestamp, target_price):
    start_ms = int(datetime.fromisoformat(timestamp).timestamp() * 1_000)
    params = urlencode({"symbol": symbol, "startTime": start_ms, "endTime": start_ms + 59_999,
                        "limit": 1000})
    url = f"https://data-api.binance.vision/api/v3/aggTrades?{params}"
    pages = [download(url)]
    records = json.loads(pages[0])
    trades = []
    while records:
        trades.extend(row for row in records if start_ms <= row["T"] < start_ms + 60_000)
        last = records[-1]
        if len(records) < 1000 or last["T"] >= start_ms + 60_000 or len(pages) >= 25:
            break
        params = urlencode({"symbol": symbol, "fromId": last["a"] + 1, "limit": 1000})
        pages.append(download(f"https://data-api.binance.vision/api/v3/aggTrades?{params}"))
        records = json.loads(pages[-1])
        if records and records[0]["a"] <= last["a"]:
            raise ValueError(f"non-advancing aggregate IDs: {symbol}")
    qualifying = [row for row in trades if not row["m"] and float(row["p"]) >= target_price]
    return {"url": url, "source_pages_sha256": [hashlib.sha256(page).hexdigest() for page in pages],
            "aggregates_in_target_minute": len(trades), "page_limit_reached": len(pages) >= 25,
            "buyer_taker_aggregates_at_or_above_target": len(qualifying),
            "buyer_taker_quote_volume_at_or_above_target": round(
                sum(float(row["p"]) * float(row["q"]) for row in qualifying), 8)}



def verify(job):
    rule, variant, month, cost, trade = job
    symbol = trade["symbol"]
    target_price = TARGET * trade["raw_entry"] * (1 + cost) / (
        trade["running_equity_before"] * (1 - cost)
    )
    first = None
    entry_quote = None
    source_archives = {}
    for archive_month in sorted({trade["entry"][:7], trade["exit"][:7]}):
        key = f"data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{archive_month}.zip"
        url = f"{ARCHIVE}/{quote(key)}"
        packed = download(url)
        source_archives[url] = hashlib.sha256(packed).hexdigest()
        with ZipFile(io.BytesIO(packed)) as archive:
            with archive.open(archive.namelist()[0]) as source:
                for row in csv.reader(io.TextIOWrapper(source, encoding="utf-8")):
                    if not row[0].isdigit():
                        continue
                    stamp = int(row[0])
                    timestamp = datetime.fromtimestamp(stamp / (1_000_000 if stamp >= 10**14 else 1_000),
                                                      timezone.utc).isoformat()
                    day = timestamp[:10]
                    if day == trade["entry"] and entry_quote is None:
                        entry_quote = (timestamp, float(row[1]), float(row[7]))
                    if trade["entry"] <= day <= trade["exit"] and float(row[2]) >= target_price * (1 + FILL_BUFFER):
                        first = (timestamp, float(row[2]), float(row[7]), int(row[8]))
                        break
        if first:
            break
    assert first and first[0][:10] == trade["exit"] and entry_quote, (job, first, entry_quote)
    assert entry_quote[1] == trade["raw_entry"], (job, entry_quote)
    return {"rule": rule, "variant": variant, "month": month, "symbol": symbol,
            "entry_minute": entry_quote, "target_minute": first,
            "target_price": target_price, "source_archives_sha256": source_archives,
            "aggregate_trade_evidence": aggregate_evidence(symbol, first[0], target_price)}


def main():
    results = json.loads((HERE / "spot_results.json").read_text())
    jobs = []
    for rule in ("continuation", "reversal"):
        for variant in ("base", "late"):
            for month in results["rules"][rule][variant]["monthly"]:
                for trade in month["trades"]:
                    if trade["reason"] == "target":
                        jobs.append((rule, variant, month["month"], results["cost_per_side"], trade))
    rolling = json.loads((HERE / "spot_rolling_results.json").read_text())
    seen = {(trade["symbol"], trade["exit"]) for *_, trade in jobs}
    for rule, variants in rolling["rules"].items():
        for variant, periods in variants.items():
            for part in periods.values():
                for item in reversed(part["hit_windows"]):
                    trade = item["target_trade"]
                    key = trade["symbol"], trade["exit"]
                    if key not in seen:
                        jobs.append((rule, f"rolling_{variant}", item["start"][:7], results["cost_per_side"], trade))
                        seen.add(key)
    with ThreadPoolExecutor() as pool:
        verified = list(pool.map(verify, jobs))
    report = {"note": "Candle crossings corroborate price feasibility, not order book fills.",
              "target_entries": verified}
    (HERE / "spot_target_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(verified, indent=2))


if __name__ == "__main__":
    main()
