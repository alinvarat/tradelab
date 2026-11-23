"""Audit pre_removal.py: source prices, removal time, notice timing and the random-control bias.

Does not change pre_removal_results.json. Fetches public Bybit data once into
pre_removal_audit_inputs.json.gz, then recomputes from that file.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import product
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

from research.sixfold.delist_delayed import STOP
from research.sixfold.delisting import fetch
from research.threefold_plan.pre_removal import CATALOG, INPUT, HOUR, opportunities, replay

HERE = Path(__file__).parent
AUDIT_INPUT = HERE / "pre_removal_audit_inputs.json.gz"
AUDIT_RESULT = HERE / "pre_removal_audit_results.json"
COSTS = (("base", .0035), ("higher", .01))
POSITION_USDT = 147.0


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def jobs():
    out = []
    for notice in json.loads(CATALOG.read_bytes())["accepted"]:
        key = next(k for k in STOP if k in notice["url"])
        removal = int(datetime.fromisoformat(STOP[key]).replace(hour=8, tzinfo=timezone.utc).timestamp() * 1000)
        out += [(s, removal - 24 * HOUR, removal, key) for s in notice["symbols"]]
    return sorted(out)


def grab(job):
    symbol, entry, removal, _ = job
    hourly = fetch("/v5/market/kline", category="spot", symbol=symbol + "USDT", interval="60",
                   limit=60, start=entry - 13 * HOUR, end=removal + 12 * HOUR)["list"]
    quarter = fetch("/v5/market/kline", category="spot", symbol=symbol + "USDT", interval="15",
                    limit=200, start=entry - 12 * HOUR, end=entry + 12 * HOUR - 1)["list"]
    return symbol, hourly, quarter


def acquire():
    with ThreadPoolExecutor(6) as workers:
        rows = list(workers.map(grab, jobs()))
    notices = {}
    for page in range(1, 10):
        listing = fetch("/v5/announcements/index", locale="en-US", type="delistings", limit=20, page=page)["list"]
        for item in listing:
            for key in STOP:
                if key in item["url"]:
                    notices[key] = {"url": item["url"], "publishTime": item["publishTime"]}
        if not listing:
            break
    AUDIT_INPUT.write_bytes(gzip.compress(json.dumps({"fetched_utc": datetime.now(timezone.utc).isoformat(),
                                                      "rows": rows, "notices": notices}).encode(), mtime=0))


def raw_bars(rows):
    return {int(r[0]): {"open": float(r[1]), "high": float(r[2]), "close": float(r[4]), "volume": float(r[5]),
                        "turnover": float(r[6])} for r in rows}


def exit_price(bars, entry):
    """Close of the last traded hourly bar inside the 12-hour hold (no trade = price unchanged)."""
    if entry not in bars or bars[entry]["volume"] <= 0:
        return None
    last = None
    for i in range(12):
        bar = bars.get(entry + i * HOUR)
        if bar and bar["volume"] > 0:
            last = bar["close"]
    return last / bars[entry]["open"]


def wallet(choices, fee, unverified):
    """Continuous 5,000 THB wallet for one fixed choice per event; unverified: 'loss' or 'carry'."""
    equity = 5000.
    for gross, carry in choices:
        if gross is None:                      # no entry bar: stay in cash
            continue
        if gross == 0:                         # missing held hour in the original model
            if unverified == "loss":
                return 0.
            gross = carry
        equity *= gross * (1 - fee) / (1 + fee)
    return equity


def oracle(fresh, meta):
    """Perfect hindsight upper bound: buy the best pair at the fixed entry open, sell at its best
    traded-bar HIGH before removal (or within 12 h). Full wallet, one pair per event."""
    events = {}
    for symbol, (entry, removal, _) in meta.items():
        bars = fresh[symbol][0]
        if entry not in bars or bars[entry]["volume"] <= 0:
            continue
        for window, end in (("to_removal", removal), ("hold_12h", entry + 12 * HOUR)):
            traded = [(bars[t]["high"], t) for t in range(entry, end, HOUR) if t in bars and bars[t]["volume"] > 0]
            high, at = max(traded)
            events.setdefault(window, {}).setdefault(utc(entry), []).append(
                {"symbol": symbol, "gross_at_high": high / bars[entry]["open"], "high_utc": utc(at),
                 "turnover_usdt_entry_to_high": sum(bars[t]["turnover"] for t in range(entry, at + 1, HOUR) if t in bars),
                 "high_bar_turnover_usdt": bars[at]["turnover"]})
    out = {"months_with_any_event": sorted({d[:7] for d in events["to_removal"]}), "months_total": 10}
    for window, by_time in events.items():
        best = {d: max(v, key=lambda x: x["gross_at_high"]) for d, v in sorted(by_time.items())}
        result = {"best_per_event": best}
        for label, fee in COSTS:
            months = dict.fromkeys((f"2026-{m:02}" for m in range(1, 11)), 1.)
            for d, x in best.items():
                months[d[:7]] *= max(1., x["gross_at_high"] * (1 - fee) / (1 + fee))
            result[label] = {"monthly": months, "3x_months": sum(v >= 3 for v in months.values())}
        out[window] = result
    return out


def main():
    if not AUDIT_INPUT.exists():
        acquire()
    audit_raw = gzip.decompress(AUDIT_INPUT.read_bytes())
    audit = json.loads(audit_raw)
    original_raw = gzip.decompress(INPUT.read_bytes())
    original = json.loads(original_raw)["rows"]
    fresh = {symbol: (raw_bars(h), raw_bars(q)) for symbol, h, q in audit["rows"]}
    meta = {s: (e, r, k) for s, e, r, k in jobs()}
    out = {"original_input_sha256": hashlib.sha256(original_raw).hexdigest(),
           "audit_input_sha256": hashlib.sha256(audit_raw).hexdigest(),
           "audit_fetched_utc": audit["fetched_utc"]}

    # 1. stored bars vs refetched source bars
    mismatch, zero_volume_gaps, absent_gaps = [], 0, 0
    for symbol, entry, stored, _ in original:
        hourly = fresh[symbol][0]
        for ts, (op, cl) in stored.items():
            bar = hourly.get(int(ts))
            if not bar or bar["open"] != op or bar["close"] != cl:
                mismatch.append([symbol, utc(int(ts))])
        for i in range(-12, 12):
            ts = entry + i * HOUR
            if str(ts) not in stored:
                if ts in hourly and hourly[ts]["volume"] == 0:
                    zero_volume_gaps += 1
                elif ts not in hourly:
                    absent_gaps += 1
    out["source_match"] = {"stored_bars": sum(len(x[2]) for x in original), "mismatched_bars": mismatch,
                           "missing_hours_that_are_zero_volume_bars": zero_volume_gaps,
                           "missing_hours_absent_from_api": absent_gaps}

    # 2. removal time: last hourly bar with trades around the assumed 08:00 UTC stop
    last_trade = {}
    for symbol, (hourly, _) in fresh.items():
        entry, removal, _ = meta[symbol]
        traded = [ts for ts, b in hourly.items() if b["volume"] > 0 and ts >= removal - 24 * HOUR]
        last_trade[symbol] = (max(traded) - removal) // HOUR if traded else None
    out["removal_check"] = {"assumed": "08:00 UTC on STOP day",
                            "last_traded_hour_offset_vs_removal": last_trade,
                            "pairs_last_trade_in_07_utc_bar": sum(v == -1 for v in last_trade.values()),
                            "pairs_trading_at_or_after_removal": {k: v for k, v in last_trade.items()
                                                                   if v is not None and v >= 0}}

    # 3. notice publish time vs entry
    timing = {}
    for symbol, (entry, removal, key) in meta.items():
        pub = int(audit["notices"][key]["publishTime"])
        timing[key] = {"publish_utc": utc(pub), "entry_utc": utc(entry), "removal_utc": utc(removal),
                       "hours_notice_to_entry": (entry - pub) / HOUR}
    out["notice_timing"] = timing

    # 4. NEON: 15-minute aggregation and size vs traded USDT
    hourly, quarter = fresh["NEON"]
    entry = meta["NEON"][0]
    agg = []
    for i in range(-12, 12):
        ts = entry + i * HOUR
        q = [quarter.get(ts + j * 900000) for j in range(4)]
        if all(q) and ts in hourly:
            agg.append(abs(q[0]["open"] - hourly[ts]["open"]) < 1e-12 and abs(q[3]["close"] - hourly[ts]["close"]) < 1e-12)
    out["neon"] = {
        "signal_open_utc": utc(entry - 12 * HOUR), "signal_open": hourly[entry - 12 * HOUR]["open"],
        "signal_close_utc": utc(entry - HOUR + 3599999), "signal_close": hourly[entry - HOUR]["close"],
        "signal_return": hourly[entry - HOUR]["close"] / hourly[entry - 12 * HOUR]["open"] - 1,
        "entry_open": hourly[entry]["open"], "exit_close": hourly[entry + 11 * HOUR]["close"],
        "hourly_equals_15m_aggregate": f"{sum(agg)}/{len(agg)}",
        "entry_hour_turnover_usdt": hourly[entry]["turnover"],
        "exit_hour_turnover_usdt": hourly[entry + 11 * HOUR]["turnover"],
        "position_share_of_entry_hour_turnover": POSITION_USDT / hourly[entry]["turnover"],
        "note": "turnover is quote-volume in USDT from the kline; no order-book depth at the entry time",
    }

    # 5. random control: exact enumeration instead of 1,000 draws with dropped paths
    dates, _ = opportunities(original)
    events = []
    for stamp, menu in sorted(dates.items()):
        if not any(x[0] >= .05 for x in menu):
            continue
        opts = []
        for strength, symbol, gross in menu:
            opts.append((gross, exit_price(fresh[symbol][0], stamp)))
        events.append((utc(stamp), [m[1] for m in menu], opts))
    out["random_events"] = [{"entry_utc": d, "menu": names,
                             "unverified": [n for n, (g, _) in zip(names, o) if g == 0]} for d, names, o in events]
    total = 1
    for _, _, opts in events:
        total *= len(opts)
    for label, fee in COSTS:
        model = replay(dates, fee)["ending_thb"]
        case = {"strategy_ending_thb": model, "combinations": total}
        paths = list(product(*[o for _, _, o in events]))
        unverified = sum(any(g == 0 for g, _ in p) for p in paths)
        case["share_paths_with_missing_hold_hour"] = unverified / total
        for mode in ("drop", "carry", "loss"):
            values = [wallet(p, fee, mode) for p in paths
                      if mode != "drop" or not any(g == 0 for g, _ in p)]
            case[mode] = {"paths": len(values), "median_thb": median(values),
                          "share_at_or_above_strategy": sum(v >= model for v in values) / len(values)}
        out[label] = case
    out["oracle_ceiling"] = oracle(fresh, meta)
    AUDIT_RESULT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
