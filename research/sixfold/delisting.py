"""Run the pre-registered Bybit venue-transfer check described in delisting_protocol.md."""
import gzip
import json
import re
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from statistics import median
from urllib.parse import urlencode

from research.sixfold.spot import BASE_COST, STRESS_COST, ONE, run_month, path_for
from research.sixfold.spot_inputs import HERE, millis, download

API = "https://api.bytick.com"
SCOPE_START, SCOPE_END = date(2023, 1, 1), date(2025, 12, 31)
DISCOVERY = {"ALPACA", "PDA", "VIB", "WING", "BAKE", "HIFI", "SLF", "HYPER"}
PAIR = re.compile(r"(?<![\w/])([A-Z0-9]{2,24})\s*/\s*USDT\b")
TOKEN_LIST = re.compile(r"(?i:to delist)\s+((?:[A-Z0-9]{2,24}(?:\s*,\s*|\s+(?i:and)\s+|\s*&\s*))*"
                        r"[A-Z0-9]{2,24})(?=\s+(?i:on|spot)\b|$)")
NOT_SPOT = re.compile(r"perpetual|derivative|option|convert|lending|collateral|leveraged token|bybit card", re.I)
CACHE = HERE / "delisting_inputs.json.gz"


def fetch(path, **params):
    response = json.loads(download(API + path + "?" + urlencode(params)))
    if response["retCode"] != 0:
        raise ValueError(response["retMsg"])
    return response["result"]


def announcements():
    def page(n):
        return fetch("/v5/announcements/index", locale="en-US", type="delistings", limit=20, page=n)
    first = page(1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        later = list(pool.map(page, range(2, (first["total"] + 19) // 20 + 1)))
    return {row["url"]: row for p in [first, *later] for row in p["list"]}


def catalog(archive):
    dated = []
    counts = {"missing_publish_time": 0, "excluded_type": 0, "unresolved_titles": 0,
              "unresolved_explicit_count": 0, "archive_rows": len(archive)}
    for url, raw in archive.items():
        title = raw["title"]
        if not raw.get("publishTime"):
            counts["missing_publish_time"] += 1
            continue
        day = datetime.fromtimestamp(raw["publishTime"] / 1_000, timezone.utc).date()
        if not SCOPE_START <= day <= SCOPE_END:
            continue
        if NOT_SPOT.search(title):
            counts["excluded_type"] += 1
            continue
        symbols = PAIR.findall(title + "\n" + raw["description"])
        if not symbols and (match := TOKEN_LIST.search(title)):
            symbols = re.findall(r"[A-Z0-9]{2,24}", match[1])
        if not symbols:
            counts["unresolved_titles"] += 1
            if re.search(r"\d+\s+(?:token|pair)s?\b|\d+\s+token\(s\)", title, re.I):
                counts["unresolved_explicit_count"] += 1
            continue
        dated.append((day, url, set(symbols) - DISCOVERY - {"USDT", "USDC", "SPOT"}))
    seen = set()
    out = []
    for day, url, pairs in sorted(dated):
        if candidates := sorted(pairs - seen):
            out.append((day.isoformat(), url, candidates))
        seen.update(pairs)
    return out, counts


def price_history(event_and_symbol):
    day, symbol = event_and_symbol
    publish = date.fromisoformat(day)
    params = {"category": "spot", "symbol": symbol + "USDT", "interval": "D", "limit": 40,
              "start": millis(publish - 15 * ONE), "end": millis(publish + 9 * ONE) - 1}
    try:
        series = fetch("/v5/market/kline", **params)["list"]
    except Exception as exc:
        return symbol, {}, str(exc)
    bars = {}
    for stamp, o, h, low, close, qty, turnover in series:
        t = datetime.fromtimestamp(int(stamp) / 1000, timezone.utc)
        assert t.hour == t.minute == 0, t
        if float(qty) > 0 and float(turnover) > 0:
            bars[t.date().isoformat()] = [float(o), float(h), float(low), float(close)]
    return symbol, bars, None if bars else "empty kline response"


def fresh_snapshot():
    archive = announcements()
    events, catalog_counts = catalog(archive)
    flat = [(day, symbol) for day, _, symbols in events for symbol in symbols]
    with ThreadPoolExecutor(max_workers=8) as pool:
        acquisition = dict((symbol, {"bars": hist, "error": err})
                           for symbol, hist, err in pool.map(price_history, flat))
    snapshot = {"archive": archive, "events": events, "catalog_counts": catalog_counts, "prices": acquisition}
    CACHE.write_bytes(gzip.compress(json.dumps(snapshot).encode(), mtime=0))
    return snapshot


def evaluate(snapshot, cost):
    outcomes = []
    first_by_month = {}
    for day, url, candidates in snapshot["events"]:
        publication = date.fromisoformat(day)
        entry = publication + ONE
        end = min(entry + 6 * ONE, date(entry.year, entry.month, monthrange(entry.year, entry.month)[1]))
        symbol_outcomes = []
        for symbol in candidates:
            data = snapshot["prices"][symbol]
            bars = {date.fromisoformat(d): c for d, c in data["bars"].items()}
            if not any(d < publication for d in bars):
                symbol_outcomes.append({"symbol": symbol, "entry_available": False,
                                        "reason": data["error"] or "no pre-publication trade"})
                continue
            if entry not in bars:
                symbol_outcomes.append({"symbol": symbol, "entry_available": False, "reason": "no next UTC open"})
                continue
            def account(start, stop):
                slot = (start, stop, False)
                result = run_month(start, stop, [(slot, symbol)],
                                   lambda _slot, _symbol: path_for(bars, start, stop, False, cost), details=True)
                return result["multiple"], result["trades"]
            multiple, trades = account(entry, end)
            control_entry, control_end = entry - 14 * ONE, end - 14 * ONE
            control = (account(control_entry, control_end)[0]
                       if all(control_entry + n * ONE in bars for n in range((control_end-control_entry).days+1))
                       else None)
            symbol_outcomes.append({"symbol": symbol, "entry_available": True, "multiple": multiple,
                                    "control_multiple": control, "trades": trades})
        active = [r for r in symbol_outcomes if r["entry_available"]]
        outcomes.append({"day": day, "entry": entry.isoformat(), "url": url, "symbols": symbol_outcomes})
        if active and entry <= SCOPE_END:
            # Retain the allocation to unfilled symbols as cash and never shift it after seeing prices.
            multiple = sum(r.get("multiple", 1.0) for r in symbol_outcomes) / len(symbol_outcomes)
            first_by_month.setdefault(entry.isoformat()[:7], {"multiple": multiple, "url": url})
    return outcomes, first_by_month


def report(out, traded, year):
    months = [traded.get(f"{year}-{m:02}", {}).get("multiple", 1.0) for m in range(1, 13)]
    events = [e for e in out if e["day"].startswith(str(year))]
    pairs = [r for e in events for r in e["symbols"]]
    n = sum(r["entry_available"] for r in pairs)
    complete_controls = [r for r in pairs if r.get("control_multiple") is not None]
    return {"parsed_announcements": len(events), "announcements_with_entry": sum(any(r["entry_available"] for r in e["symbols"]) for e in events),
            "parsed_pairs": len(pairs), "pairs_with_entry": n,
            "first_entry_months": sum(k.startswith(str(year)) for k in traded),
            "6x_months": sum(m >= 6 for m in months), "half_loss_months": sum(m <= .50 for m in months),
            "median_multiple": median(months), "best_multiple": max(months), "worst_multiple": min(months),
            "control_pairs": len(complete_controls)}


def main():
    snapshot = json.loads(gzip.decompress(CACHE.read_bytes())) if CACHE.exists() else fresh_snapshot()
    result = {"catalog_counts": snapshot["catalog_counts"], "venues": ["Bybit"], "variants": {}}
    for label, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
        outcomes, traded = evaluate(snapshot, cost)
        years = {y: report(outcomes, traded, y) for y in range(2023, 2026)}
        holdout = years[2025]
        coverage = holdout["pairs_with_entry"] / max(1, holdout["parsed_pairs"])
        result["variants"][label] = {"years": years, "coverage_pass": holdout["announcements_with_entry"] >= 10
                                     and coverage >= 0.80, "first_entry_months": traded, "outcomes": outcomes}
    (HERE / "delisting_results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["catalog_counts"])
    for k, r in result["variants"].items():
        print(k, r["years"], r["coverage_pass"])


if __name__ == "__main__":
    main()
