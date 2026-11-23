"""Record public depth snapshots and replay a fixed spot sizing diagnostic."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time

from source_probe import capture

HERE = Path(__file__).parent
MARKETS = ("binance", "deribit")
STAKE = Decimal("147")


def request(market, url, tick):
    try:
        record = capture(url)
    except (OSError, ValueError) as exc:
        return {"market": market, "tick": tick, "error": str(exc),
                "received_utc": datetime.now(timezone.utc).isoformat()}
    return {"market": market, "tick": tick, **record}


def record(path, count, interval):
    source = json.loads((HERE / "source_probe.json").read_text())
    urls = {"binance": source["binance"]["url"], "deribit": source["deribit"]["book"]["url"]}
    started = time.monotonic()
    with path.open("x") as stream, ThreadPoolExecutor(2) as pool:
        stream.write(json.dumps({"kind": "header", "interval_seconds": interval, "ticks": count,
                                 "mode": "rest_snapshots", "urls": urls}) + "\n")
        for tick in range(count):
            gap = started + tick*interval - time.monotonic()
            if gap > 0:
                time.sleep(gap)
            jobs = [pool.submit(request, m, urls[m], tick) for m in MARKETS]
            for job in jobs:
                stream.write(json.dumps(job.result()) + "\n")
            stream.flush()


def sweep(levels, amount, by_quote=False):
    remaining = amount
    base = quote = Decimal(0)
    for p, q in levels:
        price, size = Decimal(str(p)), Decimal(str(q))
        if price <= 0 or size <= 0:
            continue
        take = min(size, remaining / price if by_quote else remaining)
        base += take
        quote += take * price
        remaining -= take * price if by_quote else take
        if remaining <= Decimal("1e-18"):
            return base, quote
    return None


def replay(path):
    with path.open() as stream:
        header = json.loads(next(stream))
        rows = [json.loads(line) for line in stream if line.strip()]
    by_market = {m: {} for m in MARKETS}
    for row in rows:
        market, tick = row["market"], row["tick"]
        assert tick not in by_market[market] and 0 <= tick < header["ticks"]
        by_market[market][tick] = row
    output = {"snapshot_only": True, "interval_seconds": header["interval_seconds"], "markets": {}}
    for market, series in by_market.items():
        def good(row):
            if "payload" not in row:
                return False
            raw = row["payload"].get("result",{}) if market == "deribit" else row["payload"]
            return bool(raw.get("bids") and raw.get("asks"))

        usable = {t: row for t, row in sorted(series.items()) if good(row)}
        stamp = [datetime.fromisoformat(row["received_utc"]) for row in usable.values()]
        gaps = [(b-a).total_seconds() for a,b in zip(stamp,stamp[1:])]
        output["markets"][market] = {"usable_ticks": len(usable), "missing_or_invalid_ticks":
            sorted(set(range(header["ticks"]))-set(usable)),
            "max_received_gap_seconds": max(gaps,default=None),
            "gaps_over_twice_interval": sum(g > 2*header["interval_seconds"] for g in gaps)}
        if market == "binance":
            fee = Decimal(".0035")
            hypothetical = []
            for tick, entry in usable.items():
                exit_ = usable.get(tick + 1)
                if not exit_:
                    continue
                fill_buy = sweep(entry["payload"]["asks"], STAKE/(1+fee), by_quote=True)
                fill_sell = sweep(exit_["payload"]["bids"], fill_buy[0]) if fill_buy else None
                hypothetical.append({"entry_tick": tick, "exit_tick": tick+1,
                    "round_trip_net_multiple": float(fill_sell[1]*(1-fee)/STAKE) if fill_sell else None})
            output["markets"][market]["sizing_diagnostic"] = hypothetical
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--capture", type=int)
    parser.add_argument("--interval", type=float, default=2)
    args = parser.parse_args()
    if args.capture is not None:
        if not 1 <= args.capture <= 600 or args.interval < 1:
            parser.error("capture requires 1–600 samples at intervals of at least one second")
        record(args.path,args.capture,args.interval)
    print(json.dumps(replay(args.path), indent=2))


if __name__ == "__main__":
    main()
