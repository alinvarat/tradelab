"""Family 7 collector and screen (US small-cap intraday long events). Runs on GitHub Actions only, never on the owner's machine.

    python research/studies/smallcap_intraday.py scan   <state_dir>    # archive new gap events + halts, recompute rows, gate
    python research/studies/smallcap_intraday.py halts  <state_dir>    # archive the halt feeds only
    python research/studies/smallcap_intraday.py report <state_dir>    # recompute rows/summary from the archive (no network)

State files in <state_dir> (the data branch data/smallcap-intraday-rows): events.jsonl.gz (one gap event with its regular-session
5m bars per line), halts.jsonl.gz (Nasdaq/NYSE halt items + that day's 5m bars), rows.jsonl.gz (per-trade rows of every rule),
summary.json. No LLM is called (catalyst tags are keyword rules), so there is nothing to log in reports/COSTS.md.
"""
import gzip
import json
import os
import random
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core import smallcap_intraday as si   # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) tradelab-research", "Accept": "*/*"}
SEC_UA = os.environ.get("TRADELAB_SEC_UA", "TradeLab paper research")
MAX_SECONDS = 100 * 60
WORKERS = 6


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url, headers=None, timeout=30, tries=3):
    for k in range(tries):
        try:
            with urlopen(Request(url, headers=headers or UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code in (404, 422):
                return None
            time.sleep(1.5 * (k + 1) if code != 429 else 8 * (k + 1))
    return None


def read_jsonl(path):
    try:
        with gzip.open(path, "rt") as f:
            return [json.loads(x) for x in f if x.strip()]
    except OSError:
        return []


def write_jsonl(path, rows):
    with gzip.open(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def chart(sym):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
           "?range=60d&interval=5m&includePrePost=true&events=split")
    body = get(url, tries=3)
    if not body:
        return None
    try:
        res = json.loads(body)["chart"]["result"][0]
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    return si.parse_chart(res)


def universe():
    body = get("https://www.sec.gov/files/company_tickers_exchange.json", {"User-Agent": SEC_UA})
    d = json.loads(body)
    rows = [r for r in d["data"] if r[3] in ("Nasdaq", "NYSE", "NYSE American", "Cboe") and r[2] and re.fullmatch(r"[A-Z]{1,5}", r[2])]
    return {r[2]: int(r[0]) for r in rows}


# ------------------------------------------------------------------ catalyst tags
def sec_text(url, limit=60000):
    body = get(url, {"User-Agent": SEC_UA, "Accept-Encoding": "identity"})
    time.sleep(0.12)
    if not body:
        return ""
    t = re.sub(r"<[^>]+>", " ", body[:200000].decode("utf-8", "replace"))
    return re.sub(r"\s+", " ", t)[:limit]


def tag_event(ev, cik):
    """Tag one event from SEC 8-Ks accepted between 16:00 ET of the previous session and 09:25 ET of the event day."""
    from core import news_backtest as nb
    try:
        lo = si.ts_of(ev["prev_date"], 960)
        hi = si.ts_of(ev["date"], 565)
        fl = [f for f in nb.sec_filings(cik, forms=("8-K", "8-K/A"), since=ev["prev_date"]) if lo <= f["ts"] < hi]
    except Exception as e:  # noqa: BLE001
        return {"tag": "none", "tag_err": f"{type(e).__name__}"}
    if not fl:
        return {"tag": "none", "items": []}
    text, items = "", []
    for f in fl[:3]:
        items += f["items"]
        base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{f['accession'].replace('-', '')}/"
        idx = get(base + "index.json", {"User-Agent": SEC_UA, "Accept-Encoding": "identity"})
        time.sleep(0.12)
        names = []
        try:
            names = [x["name"] for x in json.loads(idx)["directory"]["item"]] if idx else []
        except (ValueError, KeyError, TypeError):
            pass
        ex = [n for n in names if re.search(r"ex-?99", n, re.I) and n.lower().endswith((".htm", ".html", ".txt"))][:1]
        for n in ex + [f["doc"]]:
            if n:
                text += " " + sec_text(base + n)
    return {"tag": si.classify_text(text, items), "items": sorted(set(items))}


# ------------------------------------------------------------------ halts
def collect_halts(state):
    path = os.path.join(state, "halts.jsonl.gz")
    old = read_jsonl(path)
    seen = {(h["sym"], h["halt_date"], h["halt_time"]) for h in old}
    new = []
    body = get("https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts")
    for h in si.parse_nasdaq_halts(body.decode("utf-8", "replace") if body else ""):
        key = (h["sym"], h["halt_date"], h["halt_time"])
        if key not in seen:
            seen.add(key)
            h.update(src="nasdaq", date=si.us_date(h["halt_date"]), halt_m=si.hhmm(h["halt_time"]), resume_m=si.hhmm(h["resume_trade"]), reg=None)
            new.append(h)
    body = get("https://www.nyse.com/api/trade-halts/current")
    try:
        for h in (json.loads(body)["results"]["tradeHalts"] if body else []):
            key = (h.get("symbol"), h.get("formatedHaltDate"), h.get("formatedHaltTime"))
            if key not in seen and h.get("symbol"):
                seen.add(key)
                new.append({"sym": h["symbol"], "halt_date": h.get("formatedHaltDate"), "halt_time": h.get("formatedHaltTime"), "code": h.get("reason", ""),
                            "src": "nyse", "date": h.get("formatedHaltDate"), "halt_m": si.hhmm(h.get("formatedHaltTime") or ""), "resume_m": None, "reg": None, "raw": h})
    except (ValueError, KeyError, TypeError):
        pass
    log(f"halts: {len(old)} archived, {len(new)} new")
    return old + new


def attach_halt_bars(halts, today, after_close):
    """5m regular bars of the halt day for Nasdaq LUDP halts that have a resumption time (needs a completed day)."""
    todo = [h for h in halts if h.get("reg") is None and h["src"] == "nasdaq" and h.get("code") == "LUDP" and h.get("date") and h.get("resume_m")
            and (h["date"] < today or (h["date"] == today and after_close))]
    syms = sorted({h["sym"] for h in todo})
    log(f"halt bars to fetch: {len(syms)} symbols")
    with ThreadPoolExecutor(WORKERS) as ex:
        got = dict(zip(syms, ex.map(chart, syms)))
    for h in todo:
        c = got.get(h["sym"])
        if c and h["date"] in c[0] and c[0][h["date"]]["reg"]:
            h["reg"] = c[0][h["date"]]["reg"]
    return halts


# ------------------------------------------------------------------ scan
def scan_events(state, deadline):
    path = os.path.join(state, "events.jsonl.gz")
    old = read_jsonl(path)
    have = {(e["sym"], e["date"]) for e in old}
    uni = universe()
    syms = sorted(uni)
    random.Random(int(time.time()) // 86400).shuffle(syms)       # a timed-out scan covers a different part each day
    today, m = si.et_parts(time.time())
    after_close = m >= 975
    new, stats = [], {"funnel": {}, "symbols": len(syms), "fetched": 0, "failed": 0, "timeout": False}

    def one(sym):
        if time.time() > deadline:
            stats["timeout"] = True
            return []
        c = chart(sym)
        if c is None:
            stats["failed"] += 1
            return []
        stats["fetched"] += 1
        return si.find_events(sym, c[0], c[1], today, after_close, funnel=stats["funnel"])
    with ThreadPoolExecutor(WORKERS) as ex:
        for evs in ex.map(one, syms):
            for e in evs:
                if (e["sym"], e["date"]) not in have:
                    have.add((e["sym"], e["date"]))
                    new.append(e)
    log(f"events: {len(old)} archived, {len(new)} new, {stats}")
    for e in new:
        e.update(tag_event(e, uni.get(e["sym"], 0)) if uni.get(e["sym"]) else {"tag": "none"})
    write_jsonl(path, old + new)
    return old + new, stats


def report(state, events=None, halts=None, extra=None):
    events = events if events is not None else read_jsonl(os.path.join(state, "events.jsonl.gz"))
    halts = halts if halts is not None else read_jsonl(os.path.join(state, "halts.jsonl.gz"))
    hl = [dict(h, resume_m=h["resume_m"]) for h in halts if h.get("reg") and h.get("resume_m") and h.get("halt_m")]
    tbr = si.trades_for_rules(events, hl)
    rows = [t for ts in tbr.values() for t in ts]
    write_jsonl(os.path.join(state, "rows.jsonl.gz"), rows)
    ev = si.evaluate_family(tbr, time.time())
    per_rule = {rid: si.trailing_stats(ts) for rid, ts in tbr.items()}
    days = sorted({e["date"] for e in events})
    summ = {"asof": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), "events": len(events), "event_days": [days[0], days[-1]] if days else None,
            "events_by_gap": {"20": sum(1 for e in events if e["gap"] >= 0.2), "40": sum(1 for e in events if e["gap"] >= 0.4)},
            "tags": {t: sum(1 for e in events if (e.get("tag") or "none") == t) for t in si.TAGS + ("other",)},
            "halts_archived": len(halts), "halts_with_bars": len(hl), "trade_rows": len(rows), "per_rule": per_rule, "eval": ev}
    if extra:
        summ["scan"] = extra
    with open(os.path.join(state, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1, default=str)
    brief = {"funnel": (extra or {}).get("funnel")}
    brief.update({k: summ[k] for k in ("events", "event_days", "events_by_gap", "tags", "halts_archived", "halts_with_bars", "trade_rows")})
    brief.update(rules=ev["n_rules"], gate_survivors=ev["gate_survivors"], passed=ev["passed"], dropped_reasons=ev["dropped_reasons"],
                 top_train_x=[{k: d.get(k) for k in ("id", "n_train", "train_mean", "x", "vol_cost", "reason")} for d in ev["top_train_x"]])
    print(json.dumps(brief, indent=1, default=str))


def main():
    mode, state = sys.argv[1], sys.argv[2]
    os.makedirs(state, exist_ok=True)
    if mode == "report":
        return report(state)
    t0 = time.time()
    today, m = si.et_parts(t0)
    halts = collect_halts(state)
    if mode == "halts":
        write_jsonl(os.path.join(state, "halts.jsonl.gz"), halts)
        return
    events, stats = scan_events(state, t0 + MAX_SECONDS)
    halts = attach_halt_bars(halts, today, m >= 975)
    write_jsonl(os.path.join(state, "halts.jsonl.gz"), halts)
    report(state, events, halts, stats)


if __name__ == "__main__":
    main()
