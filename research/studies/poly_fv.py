"""Polymarket short-horizon crypto markets vs digital-option fair value (family poly_fv).
Runs on GitHub Actions only (never on the owner's computer). Pure logic will live in core/poly_fv.py.
`python research/studies/poly_fv.py probe` prints a data-availability report (JSON) and exits."""
import bisect
import json
import math
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"


def http(url, timeout=30):
    """(status, parsed json or text head). Never raises: a block or error is a probe result."""
    try:
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 tradelab-research", "Accept-Encoding": "gzip"}), timeout=timeout) as r:
            body, status = r.read(), r.status
            if body[:2] == b"\x1f\x8b":
                import gzip
                body = gzip.decompress(body)
    except Exception as e:  # noqa: BLE001
        head = ""
        try:
            head = e.read()[:200].decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        return getattr(e, "code", None) or type(e).__name__, head or str(e)[:160]
    try:
        return status, json.loads(body)
    except Exception:  # noqa: BLE001
        return status, body[:200].decode("utf-8", "replace")


def get(url, tries=4):
    for k in range(tries):
        st, body = http(url)
        if st == 200 and isinstance(body, (dict, list)):
            return body
        if st in (400, 404, 410):
            return None
        time.sleep(1.5 * (k + 1))
    return None


def _day(d):
    return d.strftime("%Y-%m-%d")


ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import poly_fv as pf   # noqa: E402

COINS = {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "solana": "SOLUSDT", "xrp": "XRPUSDT"}
FIRST_MONTH, LAST_MONTH = (2025, 8), (2026, 11)
UTC = timezone.utc


def _ts(y, m=1, d=1):
    return datetime(y, m, d, tzinfo=UTC).timestamp()


BOUNDS = {"train": (_ts(2025, 8), _ts(2026, 3)), "validation": (_ts(2026, 3), _ts(2026, 7)), "test": (_ts(2026, 7), _ts(2026, 12))}
FOLDS = [(_ts(2026, 3), _ts(2026, 5)), (_ts(2026, 5), _ts(2026, 7)), (_ts(2026, 7), _ts(2026, 9)), (_ts(2026, 9), _ts(2026, 12))]


def universe():
    out, (y, m) = [], FIRST_MONTH
    while (y, m) <= LAST_MONTH:
        out += [f"{y}-{m:02d}:{c}" for c in COINS]
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def iso_ts(s):
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00").replace(" ", "T")).timestamp()
    except Exception:  # noqa: BLE001
        return None


def list_events(coin, a, b, gaps):
    """Closed events of one coin whose end date is in [a, b) (unix s), by one-day windows with offset paging."""
    got, t = {}, a
    while t < b:
        d0, d1 = datetime.fromtimestamp(t, UTC), datetime.fromtimestamp(min(t + 86400, b), UTC)
        for off in range(0, 3000, 100):
            page = get(f"{GAMMA}/events?closed=true&tag_slug={coin}&limit=100&offset={off}&end_date_min={d0:%Y-%m-%dT%H:%M:%SZ}&end_date_max={d1:%Y-%m-%dT%H:%M:%SZ}")
            if not isinstance(page, list):
                gaps["event_page_failed"] = gaps.get("event_page_failed", 0) + 1
                break
            for e in page:
                got.setdefault(str(e.get("id")), e)
            if len(page) < 100:
                break
        t += 86400
    return list(got.values())


HOURLY = re.compile(r"^(%s)-up-or-down-.*-\d{1,2}(am|pm)-et$" % "|".join(COINS))
DAILY = re.compile(r"^(%s)-above-on-" % "|".join(COINS))
NUM = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)")


def norm_market(m, ev, coin, kind, gaps):
    """Resolved binary gamma market -> dict for the rules, or None."""
    try:
        prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        toks = json.loads(m.get("clobTokenIds") or "[]")
        outs = json.loads(m.get("outcomes") or "[]")
    except (ValueError, TypeError):
        gaps["unparsed"] = gaps.get("unparsed", 0) + 1
        return None
    end = iso_ts(m.get("endDate") or "")
    if len(prices) != 2 or len(toks) != 2 or sorted(prices) != [0.0, 1.0] or not end or not m.get("conditionId"):
        gaps["not_resolved_binary"] = gaps.get("not_resolved_binary", 0) + 1
        return None
    if not outs or outs[0] not in ("Up", "Yes"):
        gaps["outcome_order"] = gaps.get("outcome_order", 0) + 1
        return None
    fr, fe = 0.0, 1.0
    if m.get("feesEnabled"):
        sch = m.get("feeSchedule") or {}
        if "rate" in sch:
            fr, fe = float(sch["rate"]), float(sch.get("exponent", 1))
        else:
            fr, fe = 0.25, 2.0                    # no schedule on a fee market: the 2025 crypto formula, counted
            gaps["fee_market_without_schedule"] = gaps.get("fee_market_without_schedule", 0) + 1
    strike = None
    if kind == "hourly":
        strike = ((ev.get("eventMetadata") or {}).get("priceToBeat"))
    else:
        mt = re.search(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)", m.get("question") or "")
        if mt:
            strike = float(mt.group(1).replace(",", ""))
    return {"id": str(m["id"]), "cond": m["conditionId"], "coin": coin, "kind": kind, "end": end, "yes_won": prices[0] == 1.0,
            "fee_rate": fr, "fee_exp": fe, "strike": float(strike) if strike else None, "question": (m.get("question") or "")[:90]}


def parse_trades(rows):
    seen, out = set(), []
    for r in rows or []:
        try:
            key = (r.get("transaction_hash"), r.get("token_id"), float(r["price"]), float(r["size"]))
            if key in seen:
                continue
            seen.add(key)
            out.append({"t": int(r["timestamp"]), "side": str(r["side"]).upper(), "idx": int(r["outcome_index"]),
                        "price": float(r["price"]), "size": float(r["size"])})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda x: (x["t"], x["idx"]))
    return out


def fetch_trades(cond, max_pages=30):
    """(trades, truncated_or_failed). Cursor pages, newest first."""
    rows, cur = [], ""
    for _ in range(max_pages):
        d = get(f"{DATA}/v2/trades?condition={cond}&limit=1000" + (f"&cursor={cur}" if cur else ""))
        if not isinstance(d, dict):
            return parse_trades(rows), True
        rows += d.get("data") or []
        pg = d.get("pagination") or {}
        cur = pg.get("next_cursor") or ""
        if not (pg.get("has_more") and cur):
            return parse_trades(rows), False
    return parse_trades(rows), True


def run_shard(item, workers=8):
    """item 'YYYY-MM:coin' -> (rows, gaps)."""
    from concurrent.futures import ThreadPoolExecutor
    from research.studies import binance_vision as bv
    ym, coin = item.split(":")
    y, mo = int(ym[:4]), int(ym[5:7])
    a = _ts(y, mo)
    b = _ts(y + (mo == 12), mo % 12 + 1)
    gaps = {}
    cur = datetime.now(UTC)
    period = "daily" if (cur.year, cur.month) == (y, mo) else "monthly"
    kl, failed = bv.klines(COINS[coin], a - 2 * 86400, min(b, time.time()) + 1, "1m", "spot", period)
    if failed:
        gaps["spot_files_failed"] = failed
    spot_t, spot_c = [r[0] for r in kl], [r[4] for r in kl]
    if len(kl) < 1000:
        gaps["spot_too_short"] = len(kl)
        return [], gaps
    evs = list_events(coin, a, b, gaps)
    mk = []
    for e in evs:
        slug = e.get("slug") or ""
        kind = "hourly" if HOURLY.match(slug) else "daily" if DAILY.match(slug) else None
        if not kind:
            continue
        for m in e.get("markets") or []:
            n = norm_market(m, e, coin, kind, gaps)
            if n and a <= n["end"] < b:
                mk.append(n)
    gaps["markets"] = len(mk)

    def one(m):
        tr, bad = fetch_trades(m["cond"])
        if bad and not (tr and tr[0]["t"] < m["end"] - 95 * 60):   # newest-first pages: a cut loses only early trades
            return None, "trades_truncated_or_failed"
        if not tr:
            return None, "no_trades"
        strike = m["strike"]
        if strike is None:
            if m["kind"] != "hourly":
                return None, "no_strike"
            i = bisect.bisect_left(spot_t, m["end"] - 3600)
            if i >= len(spot_t) or spot_t[i] != m["end"] - 3600:
                return None, "no_strike"
            strike = [r[1] for r in kl][i]          # Binance 1-minute open at the hour start
        if m["kind"] == "daily":
            mid = spot_c[min(bisect.bisect_left(spot_t, m["end"] - 3600), len(spot_c) - 1)]
            if abs(math.log(strike / mid)) > 0.5:
                return None, "strike_implausible"
        return pf.market_rows(m, tr, spot_t, spot_c, strike), None
    rows = []
    with ThreadPoolExecutor(workers) as ex:
        for r, why in ex.map(one, mk):
            if r is None:
                gaps[why] = gaps.get(why, 0) + 1
            elif not r:
                gaps["no_candidate_rows"] = gaps.get("no_candidate_rows", 0) + 1
            else:
                rows += r
    gaps["rows"] = len(rows)
    return rows, gaps


def probe():
    out = {"t": datetime.now(timezone.utc).isoformat()}
    if "--quick" in sys.argv:
        gaps = {}
        evs = list_events("bitcoin", _ts(2026, 10, 10), _ts(2026, 10, 11), gaps)
        pat = {}
        for e in evs:
            sl = re.sub(r"\d+", "N", e.get("slug") or "")
            kind = "hourly" if HOURLY.match(e.get("slug") or "") else "daily" if DAILY.match(e.get("slug") or "") else None
            x = pat.setdefault(sl, {"events": 0, "markets": 0, "kind": kind, "ex": None})
            x["events"] += 1
            x["markets"] += len(e.get("markets") or [])
            if x["ex"] is None and e.get("markets"):
                m0 = e["markets"][0]
                x["ex"] = [e.get("slug"), m0.get("question"), m0.get("groupItemTitle"), (e.get("eventMetadata") or {})]
        out["patterns"] = pat
        out["gaps"] = gaps
        return out
    st, ser = http(f"{GAMMA}/series?slug=bitcoin-up-or-down-hourly&limit=5")
    out["series_by_slug"] = [st, json.dumps(ser)[:1500]]
    sid = None
    if isinstance(ser, list) and ser:
        sid = ser[0].get("id")
        out["series_keys"] = sorted(ser[0].keys())
    for slug in ("btc-up-or-down-hourly", "bitcoin-up-or-down-hourly", "bitcoin-multi-strikes-weekly", "bitcoin-neg-risk-weekly", "btc-up-or-down-daily"):
        st, s2 = http(f"{GAMMA}/series?slug={slug}&limit=2")
        out["series_" + slug] = [st, (json.dumps([(x.get("id"), x.get("slug"), x.get("recurrence")) for x in s2]) if isinstance(s2, list) else s2)]
    # event queries in 1-day windows by month back, with several filters
    hist = {}
    sample = None
    d = datetime(2026, 11, 20, tzinfo=timezone.utc)
    while d > datetime(2024, 1, 1, tzinfo=timezone.utc):
        a, b = _day(d), _day(d + timedelta(days=1))
        row = {}
        for name, q in (("series", f"series_id={sid}&") if sid else ("none", ""), ("tag", "tag_slug=crypto&"), ("plain", "")):
            st, ev = http(f"{GAMMA}/events?{q}closed=true&limit=100&end_date_min={a}T00:00:00Z&end_date_max={b}T00:00:00Z")
            if isinstance(ev, list):
                ud = [e for e in ev if re.search(r"up or down", e.get("title", ""), re.I)]
                ab = [e for e in ev if re.search(r"\babove\b", e.get("title", ""), re.I)]
                row[name] = {"n": len(ev), "updown": len(ud), "above": len(ab), "ex": [e.get("slug") for e in (ud + ab)[:2]]}
                if ud and sample is None:
                    sample = ud[0]
            else:
                row[name] = [st, str(ev)[:100]]
        hist[a] = row
        d -= timedelta(days=60)
    out["history_by_date"] = hist
    if sample:
        out["sample_event"] = {k: (v if len(str(v)) < 200 else str(v)[:200]) for k, v in sample.items() if k not in ("markets", "tags")}
        out["sample_tags"] = [(t.get("slug"), t.get("label")) for t in sample.get("tags") or []]
        mk = (sample.get("markets") or [{}])[0]
        out["sample_market"] = {k: (v if len(str(v)) < 300 else str(v)[:300]) for k, v in mk.items()}
        toks = json.loads(mk.get("clobTokenIds") or "[]")
        cond = mk.get("conditionId")
        if toks:
            out["fee_rate"] = http(f"{CLOB}/fee-rate?token_id={toks[0]}")
        if cond:
            out["clob_market"] = http(f"{CLOB}/markets/{cond}")
            tr = http(f"{DATA}/v2/trades?condition={cond}&limit=1000")
            if isinstance(tr[1], dict):
                rows = tr[1].get("data") or []
                out["trades"] = {"n": len(rows), "first": rows[:2], "has_more": (tr[1].get("pagination") or {}).get("has_more")}
            else:
                out["trades"] = tr
            if toks:
                for fid in (1, 5, 60):
                    ph = http(f"{CLOB}/prices-history?market={toks[0]}&interval=max&fidelity={fid}")
                    h = (ph[1] or {}).get("history") if isinstance(ph[1], dict) else None
                    out[f"prices_history_fid{fid}"] = {"status": ph[0], "n": len(h) if h is not None else None, "first": h[:1] if h else None}
    # slug-constructed lookups (hourly and daily), to measure how far back they exist
    slugs = {}
    for ymd in ("2025-06-15", "2025-07-15", "2025-08-01", "2026-06-10"):
        dd = datetime.strptime(ymd, "%Y-%m-%d")
        mon = dd.strftime("%B").lower()
        for coin in ("bitcoin", "ethereum", "solana", "xrp"):
            for sl in (f"{coin}-up-or-down-{mon}-{dd.day}-3pm-et", f"{coin}-up-or-down-{mon}-{dd.day}-{dd.year}-3pm-et", f"{coin}-above-on-{mon}-{dd.day}", f"{coin}-above-on-{mon}-{dd.day}-{dd.year}"):
                st, e = http(f"{GAMMA}/events?slug={sl}")
                slugs[sl] = [st, len(e) if isinstance(e, list) else str(e)[:60]]
    out["slug_lookup"] = slugs
    return out



def main(argv):
    import argparse
    import gzip
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "plan", "shard", "merge"])
    ap.add_argument("--shards", type=int, default=64)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--dir", default="out")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "probe":
        print(json.dumps(probe(), indent=1, default=str)[:60000])
    elif a.cmd == "plan":
        print(json.dumps(list(range(len(universe())))))
    elif a.cmd == "shard":
        item = universe()[a.shard]
        t0 = time.time()
        rows, gaps = run_shard(item)
        os.makedirs(a.dir, exist_ok=True)
        with gzip.open(f"{a.dir}/rows_{a.shard:03d}.jsonl.gz", "wt") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":")) + "\n")
        json.dump({"item": item, "gaps": gaps, "seconds": round(time.time() - t0)}, open(f"{a.dir}/gaps_{a.shard:03d}.json", "w"))
        print(item, len(rows), gaps)
    else:
        import glob
        rows, gaps = [], {}
        parts = sorted(glob.glob(f"{a.dir}/rows_*.jsonl.gz"))
        for f in parts:
            with gzip.open(f, "rt") as fh:
                rows += [json.loads(x) for x in fh if x.strip()]
        for f in sorted(glob.glob(f"{a.dir}/gaps_*.json")):
            g = json.load(open(f))
            gaps[g["item"]] = g["gaps"]
        res = pf.evaluate(rows, BOUNDS, FOLDS)
        cal = {}
        for r in rows:
            if r["off"] == 10 and r["lb"] == 60 and (r["fair"] > 0.9 or r["fair"] < 0.1):
                k = f"{r['kind']}:{'hi' if r['fair'] > 0.9 else 'lo'}"
                c = cal.setdefault(k, [0, 0])
                c[0] += 1
                c[1] += 1 if r.get("won") else 0
        res["calibration_yes_rate"] = {k: [v[0], round(v[1] / v[0], 3)] for k, v in cal.items()}
        res["parts"] = len(parts)
        res["expected_parts"] = len(universe())
        res["rows"] = len(rows)
        res["gaps"] = gaps
        json.dump(res, open(f"{a.dir}/summary.json", "w"))
        tab = sorted(res["table"], key=lambda e: -(e["validation"]["mean"] or -9))
        print(json.dumps({k: v for k, v in res.items() if k not in ("table", "gaps")}))
        for e in tab[:12]:
            print(json.dumps(e)[:600])


if __name__ == "__main__":
    main(sys.argv[1:])
