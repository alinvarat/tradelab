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
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 tradelab-research"}), timeout=timeout) as r:
            body, status = r.read(), r.status
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
    # A: closed crypto events ending in a one-day window, by month back to 2024
    days = []
    d = datetime(2026, 11, 20, tzinfo=timezone.utc)
    while d > datetime(2024, 1, 1, tzinfo=timezone.utc):
        days.append(d)
        d -= timedelta(days=60)
    hist = {}
    sample = None
    for d in days:
        a, b = _day(d), _day(d + timedelta(days=1))
        ev = get(f"{GAMMA}/events?closed=true&tag_slug=crypto&limit=500&end_date_min={a}T00:00:00Z&end_date_max={b}T00:00:00Z")
        if not isinstance(ev, list):
            hist[a] = "fail"
            continue
        updown = [e for e in ev if re.search(r"up or down", e.get("title", ""), re.I)]
        above = [e for e in ev if re.search(r"above|reach|hit", e.get("title", ""), re.I)]
        hist[a] = {"events": len(ev), "updown": len(updown), "above_like": len(above),
                   "titles": [e.get("title") for e in ev[:6]], "slugs": [e.get("slug") for e in (updown + above)[:3]]}
        if updown and sample is None:
            sample = updown[0]
    out["history_by_date"] = hist
    if sample:
        out["sample_event_keys"] = sorted(sample.keys())
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
    # B: other discovery routes
    out["series_probe"] = {}
    for q in ("bitcoin up or down", "ethereum above", "solana up or down"):
        st, body = http(f"{GAMMA}/public-search?q={q.replace(' ', '%20')}&limit_per_type=5&events_status=closed")
        out["series_probe"][q] = (st, [(e.get("slug"), e.get("endDate"), (e.get("series") or [{}])[0].get("slug") if e.get("series") else None) for e in (body.get("events") or [])][:6] if isinstance(body, dict) else body)
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["probe"]:
        print(json.dumps(probe(), indent=1, default=str)[:60000])
