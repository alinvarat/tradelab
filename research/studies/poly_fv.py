"""Polymarket short-horizon crypto markets vs digital-option fair value (family poly_fv).
Runs on GitHub Actions only (never on the owner's computer). Pure logic will live in core/poly_fv.py.
`python research/studies/poly_fv.py probe` prints a data-availability report (JSON) and exits."""
import json
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


def probe():
    out = {"t": datetime.now(timezone.utc).isoformat()}
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


if __name__ == "__main__":
    if sys.argv[1:2] == ["probe"]:
        print(json.dumps(probe(), indent=1, default=str)[:60000])
