"""Forward news-latency collector, pure logic (no network, no clock): feed parsers, the Haiku reply parser, price-path
metrics, the paper trade at t_llm + 5 s and the report. Protocol: research/studies/protocol_news_latency_fwd_20261126.md
(locked before the first collection). IO lives in research/studies/news_latency_fwd.py.

Times are epoch seconds (UTC). A bar is [start_s, open, high, low, close, volume]; bars are 1 minute."""
import hashlib
import json
import math
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

ATOM = "{http://www.w3.org/2005/Atom}"
ET_ZONE = ZoneInfo("America/New_York")
RTH_FIRST_MIN, RTH_LAST_MIN = 9 * 60 + 35, 15 * 60       # stock items are scored only when t_pub is inside [09:35, 15:00] ET
TICKER_RE = re.compile(r"\((?:NASDAQ|NYSE American|NYSE|NYSEAMERICAN|Nasdaq Global Market|Nasdaq|NYSE MKT)\s*:\s*([A-Z]{1,5})\)", re.I)
MATERIAL_8K_ITEMS = {"1.01", "1.02", "2.01", "2.02", "2.05", "3.01", "4.02", "5.02", "7.01", "8.01"}


# ------------------------------------------------------------------ timestamps and text
def parse_ts(s):
    """-> (epoch seconds, 's' | 'm') or (None, None). 'm' when the string has no seconds (the true time is up to 59 s later)."""
    if s is None:
        return None, None
    s = str(s).strip()
    if not s:
        return None, None
    if re.fullmatch(r"\d{10,13}(\.\d+)?", s):
        v = float(s)
        return (v / 1000.0 if v > 1e11 else v), "s"
    try:
        if re.search(r"\d{2}:\d{2}:\d{2}", s):
            res = "s"
        else:
            res = "m"
        if "T" in s and re.match(r"\d{4}-\d{2}-\d{2}T", s):
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp(), res
    except (ValueError, TypeError, IndexError):
        return None, None


def strip_html(s, limit=None):
    t = re.sub(r"<[^>]+>", " ", s or "")
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit] if limit else t


def ticker_from_text(*texts):
    for t in texts:
        m = TICKER_RE.search(t or "")
        if m:
            return m.group(1).upper()
    return None


def in_rth(t_pub):
    d = datetime.fromtimestamp(t_pub, ET_ZONE)
    if d.weekday() >= 5:
        return False
    m = d.hour * 60 + d.minute
    return RTH_FIRST_MIN <= m <= RTH_LAST_MIN


def day_utc(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")


# ------------------------------------------------------------------ feed parsers (each returns a list of item dicts)
def parse_edgar_atom(xml_bytes):
    """SEC getcurrent atom. -> [{key, title, link, t_pub, res, cik, company, items, form}]; one row per accession."""
    out, seen = [], set()
    root = ET.fromstring(xml_bytes)
    for e in root.findall(ATOM + "entry"):
        title = (e.findtext(ATOM + "title") or "").strip()
        link_el = e.find(ATOM + "link")
        link = link_el.get("href") if link_el is not None else ""
        eid = e.findtext(ATOM + "id") or ""
        m = re.search(r"accession-number=([\d-]+)", eid) or re.search(r"/(\d{10}-\d{2}-\d{6})", link or "")
        acc = m.group(1) if m else link
        t_pub, res = parse_ts(e.findtext(ATOM + "updated"))
        mt = re.match(r"([\w/\-.]+)\s+-\s+(.*?)\s+\((\d{10})\)", title)
        form, company, cik = (mt.group(1), mt.group(2), int(mt.group(3))) if mt else ("", title, None)
        summary = strip_html(e.findtext(ATOM + "summary") or "")
        items = sorted(set(re.findall(r"Item\s+(\d\.\d{2})", summary)))
        if not acc or (acc, cik) in seen:
            continue
        seen.add((acc, cik))
        out.append({"key": "sec:" + acc, "title": title, "link": link, "t_pub": t_pub, "res": res, "cik": cik,
                    "company": company, "items": items, "form": form, "summary": summary[:400]})
    return out


def parse_rss(xml_bytes, prefix):
    """RSS 2.0 / Atom-less feeds. -> [{key, title, link, t_pub, res, desc, raw_ts}]."""
    out = []
    root = ET.fromstring(xml_bytes)
    for it in root.iter("item"):
        title = strip_html(it.findtext("title") or "", 300)
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link or title).strip()
        raw = it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
        t_pub, res = parse_ts(raw)
        out.append({"key": f"{prefix}:{guid}", "title": title, "link": link, "t_pub": t_pub, "res": res,
                    "desc": strip_html(it.findtext("description") or "", 700), "raw_ts": raw})
    return out


def parse_binance(d, prefix):
    out = []
    for cat in ((d.get("data") or {}).get("catalogs") or []):
        for a in cat.get("articles") or []:
            rd = a.get("releaseDate")
            t_pub, res = parse_ts(rd)
            code = a.get("code") or a.get("id")
            out.append({"key": f"{prefix}:{code}", "title": str(a.get("title") or "")[:300], "t_pub": t_pub, "res": res,
                        "link": f"https://www.binance.com/en/support/announcement/{code}", "desc": "", "raw_ts": str(rd)})
    return out


def parse_okx_announcements(d, prefix):
    out = []
    for blk in d.get("data") or []:
        for a in blk.get("details") or []:
            t_pub, res = parse_ts(a.get("pTime"))
            out.append({"key": f"{prefix}:{a.get('url') or a.get('title')}", "title": str(a.get("title") or "")[:300],
                        "t_pub": t_pub, "res": res, "link": a.get("url") or "", "desc": str(a.get("annType") or ""),
                        "raw_ts": str(a.get("pTime"))})
    return out


def parse_okx_candles(d):
    """OKX candles answer (newest first) -> ascending bars."""
    out = []
    for r in d.get("data") or []:
        try:
            out.append([int(r[0]) / 1000.0, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
        except (ValueError, TypeError, IndexError):
            continue
    return sorted(out)


def parse_yahoo_chart(d):
    """Yahoo v8 chart answer -> (bars ascending, meta). Null bars are left out, never filled."""
    res = ((d.get("chart") or {}).get("result") or [None])[0]
    if not res:
        return [], {}
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    bars = []
    for i, t in enumerate(ts):
        try:
            o, h, lo, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        except (KeyError, IndexError, TypeError):
            continue
        if None in (o, h, lo, c):
            continue
        bars.append([float(t), float(o), float(h), float(lo), float(c), float(v or 0)])
    return sorted(bars), (res.get("meta") or {})


def okx_perp_bases(d):
    """Set of base coins with a live USDT-margined perp, from /public/instruments?instType=SWAP."""
    out = set()
    for r in d.get("data") or []:
        if r.get("state") == "live" and r.get("instId", "").endswith("-USDT-SWAP"):
            out.add(r["instId"].split("-")[0])
    return out


def cik_ticker_map(d):
    """company_tickers_exchange.json -> {cik: ticker} for US exchange listings with a plain 1-5 letter ticker."""
    out = {}
    fields = d.get("fields") or []
    try:
        ic, it, ie = fields.index("cik"), fields.index("ticker"), fields.index("exchange")
    except ValueError:
        return out
    for r in d.get("data") or []:
        if r[ie] in ("Nasdaq", "NYSE", "NYSE American", "Cboe") and re.fullmatch(r"[A-Z]{1,5}", r[it] or ""):
            out.setdefault(int(r[ic]), r[it])
    return out


# ------------------------------------------------------------------ the Haiku call
def parse_haiku(text):
    """-> {'direction': 'up'|'down'|'none', 'confidence': 0..100, 'instrument': str|None} or None when unreadable.
    An unreadable or empty reply is a logged failure, never 'neutral'."""
    m = re.search(r"\{.*?\}", text or "", re.S)
    if not m:
        return None
    try:
        o = json.loads(m.group(0))
    except ValueError:
        return None
    d = str(o.get("direction", "")).lower().strip()
    if d not in ("up", "down", "none"):
        return None
    try:
        c = max(0, min(100, int(round(float(o.get("confidence", 0))))))
    except (TypeError, ValueError):
        return None
    inst = o.get("instrument")
    inst = re.sub(r"[^A-Z0-9]", "", str(inst).upper())[:12] if inst else None
    return {"direction": d, "confidence": c, "instrument": inst or None}


def stock_candidate(item, cik_map):
    """(ticker or None, reason) for a stock-market item: EDGAR 8-K by CIK and material item; wires by '(NASDAQ: X)' text."""
    if item["source"].startswith("sec"):
        tk = cik_map.get(item.get("cik"))
        if not tk:
            return None, "no_ticker"
        its = item.get("items") or []
        if its and not (set(its) & MATERIAL_8K_ITEMS):
            return None, "immaterial_8k"
        return tk, ""
    tk = ticker_from_text(item.get("title"), item.get("desc"))
    return (tk, "") if tk else (None, "no_ticker")


# ------------------------------------------------------------------ path metrics
def close_before(bars, t, max_gap=300):
    """Close of the last bar that had ended by t (known data); None when it is more than max_gap seconds old."""
    best = None
    for b in bars:
        if b[0] + 60 <= t:
            best = b
        else:
            break
    if best is None or t - (best[0] + 60) > max_gap:
        return None
    return best[4]


def open_after(bars, t, max_gap=120):
    for b in bars:
        if b[0] >= t:
            return b[1] if b[0] - t <= max_gap else None
    return None


def pre_coverage(bars, t_pub):
    """Bars with volume in the 5 minutes before t_pub (causal liquidity screen), 0..5."""
    return sum(1 for b in bars if t_pub - 300 <= b[0] < t_pub and b[5] > 0)


def snapshot_price(snap, max_age):
    """Mid for the move fraction and the side price for a taker entry, or None when stale. snap: {t_req, price, price_t, bid, ask}."""
    if not snap or not snap.get("price"):
        return None
    pt = snap.get("price_t")
    if pt is not None and abs(snap["t_req"] - pt) > max_age:
        return None
    return snap


def evaluate_item(it, P):
    """One scored item -> metrics dict (always has 'excluded' = reason or ''). P = params dict."""
    r = {"key": it["key"], "source": it["source"], "market": it["market"], "instrument": it.get("instrument"),
         "day": day_utc(it["t_pub"]), "excluded": ""}
    llm = it.get("llm") or {}
    bars = it.get("bars") or []
    t_pub, t_llm = it["t_pub"], it.get("t_llm")
    if not bars:
        r["excluded"] = "no_bars"
        return r
    cov = pre_coverage(bars, t_pub)
    if it["market"] == "stock" and cov < P["min_pre_coverage"]:
        r["excluded"] = "thin_pre_window"
        return r
    p0 = close_before(bars, t_pub)
    p60 = close_before(bars, t_pub + 3600)
    if p0 is None or p60 is None:
        r["excluded"] = "no_ref_price"
        return r
    r["p0"], r["p60"], r["move"] = p0, p60, p60 / p0 - 1
    r["large"] = abs(r["move"]) >= P["large_move"]
    if t_llm is not None:
        r["t_llm"] = t_llm
        pb = close_before(bars, t_llm, 300)
        ps = snapshot_price(it.get("snap"), P["snap_max_age_s"])
        pm = None
        if ps:
            pm = (ps["bid"] + ps["ask"]) / 2 if ps.get("bid") and ps.get("ask") else ps["price"]
        pseen = close_before(bars, it["t_seen"], 300)
        if p60 != p0:
            r["f_snap"] = None if pm is None else (pm - p0) / (p60 - p0)
            r["f_bar"] = None if pb is None else (pb - p0) / (p60 - p0)
            r["f_seen"] = None if pseen is None else (pseen - p0) / (p60 - p0)
    d = {"up": 1, "down": -1}.get(llm.get("direction"), 0)
    r["dir"] = d
    r["conf"] = llm.get("confidence")
    if t_llm is None or d == 0 or (llm.get("confidence") or 0) < 0:
        r["trade"] = False
        return r
    if t_llm + 5 > t_pub + P["latest_entry_s"]:
        r["trade"] = False
        r["excluded_trade"] = "too_late"
        return r
    ps = snapshot_price(it.get("snap"), P["snap_max_age_s"])
    r["trade"] = True
    r["rand_dir"] = 1 if hashlib.sha256(it["key"].encode()).digest()[0] % 2 else -1
    cost = P["cost_rt"][it["market"]]
    r["cost"] = cost
    if ps is None:
        r["entry"] = None
    else:
        side_px = (ps.get("ask") if d > 0 else ps.get("bid")) or ps["price"]
        r["entry"] = side_px
    eb = open_after(bars, t_llm + 5)
    r["entry_bar"] = eb
    for name, e in (("", r["entry"]), ("_bar", eb)):
        if e:
            gross_up = p60 / e - 1
            r["gross" + name] = d * gross_up
            r["rand_gross" + name] = r["rand_dir"] * gross_up
    return r


# ------------------------------------------------------------------ statistics
def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def lat_stats(xs):
    return {"n": len(xs), "median": percentile(xs, 0.5), "p90": percentile(xs, 0.9)} if xs else {"n": 0}


def boot_ci(vals, days, n=2000, seed=20261126):
    """Mean and 95% interval resampling UTC days (clusters) with replacement."""
    if not vals:
        return None
    by = {}
    for v, d in zip(vals, days):
        by.setdefault(d, []).append(v)
    keys = sorted(by)
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        s = c = 0
        for _k in keys:
            g = by[keys[rng.randrange(len(keys))]]
            s += sum(g)
            c += len(g)
        means.append(s / c)
    means.sort()
    return {"mean": sum(vals) / len(vals), "lo": means[int(0.025 * n)], "hi": means[int(0.975 * n) - 1],
            "n": len(vals), "days": len(keys)}


def select_trades(evals, P, min_conf=None, gross_key="gross"):
    """Trades with a usable entry; one open trade per instrument (first by t_llm wins, later overlapping ones dropped)."""
    min_conf = P["min_conf"] if min_conf is None else min_conf
    rows = sorted((e for e in evals if e.get("trade") and e.get(gross_key) is not None and (e.get("conf") or 0) >= min_conf),
                  key=lambda e: e["t_llm"])
    kept, busy_until = [], {}
    for e in rows:
        k = (e["market"], e["instrument"])
        if k in busy_until and e["t_llm"] + 5 < busy_until[k]:
            continue
        busy_until[k] = e["t_exit"]
        kept.append(e)
    return kept


def pnl_block(trades, P, gross_key="gross", rand_key="rand_gross"):
    if not trades:
        return {"n": 0}
    out = {"n": len(trades)}
    days = [t["day"] for t in trades]
    for tag, mult in (("net", 1.0), ("net_2x", 2.0)):
        net = [t[gross_key] - mult * t["cost"] for t in trades]
        out[tag] = boot_ci(net, days)
    gross = [t[gross_key] for t in trades]
    out["gross_mean"] = sum(gross) / len(gross)
    out["hit_gross"] = sum(1 for g in gross if g > 0) / len(gross)
    out["hit_net"] = sum(1 for t in trades if t[gross_key] - t["cost"] > 0) / len(trades)
    rn = [t[rand_key] - t["cost"] for t in trades]
    out["random_net_mean"] = sum(rn) / len(rn)
    fl = [-t[gross_key] - t["cost"] for t in trades]
    out["flipped_net_mean"] = sum(fl) / len(fl)
    out["haiku_minus_random"] = boot_ci([a - b for a, b in zip([t[gross_key] - t["cost"] for t in trades], rn)], days)
    return out


def verdict(block, P):
    if block.get("n", 0) < P["min_trades"]:
        return f"unread (n {block.get('n', 0)} < {P['min_trades']})"
    days = block["net"]["days"]
    ok = (days >= P["min_days"] and block["net"]["lo"] > 0 and block["net_2x"]["mean"] > 0
          and block["haiku_minus_random"]["lo"] > 0)
    return "edge candidate (forward)" if ok else "no edge shown"


# ------------------------------------------------------------------ the report
def summarize(rows, P):
    """rows = final item rows (items.jsonl). Pure function of the rows and params."""
    live = [r for r in rows if not r.get("cold") and r.get("t_pub") and r.get("t_seen")]
    lat = {"seen_minus_pub": {}, "llm_minus_seen": {}, "llm_minus_pub": {}, "text_minus_seen": {}}
    by_src = {}
    for r in live:
        by_src.setdefault(r["source"], []).append(r)
    for src, rs in list(by_src.items()) + [("ALL", live)]:
        lat["seen_minus_pub"][src] = lat_stats([r["t_seen"] - r["t_pub"] for r in rs])
        lat["seen_minus_pub"][src]["res"] = sorted({r.get("res") for r in rs if r.get("res")})
        scored = [r for r in rs if r.get("t_llm") and r.get("llm")]
        lat["llm_minus_seen"][src] = lat_stats([r["t_llm"] - r["t_seen"] for r in scored])
        lat["llm_minus_pub"][src] = lat_stats([r["t_llm"] - r["t_pub"] for r in scored])
        txt = [r["t_text_ready"] - r["t_seen"] for r in rs if r.get("t_text_ready")]
        if txt:
            lat["text_minus_seen"][src] = lat_stats(txt)
    health = {"items_live": len(live), "cold": sum(1 for r in rows if r.get("cold")),
              "scored": sum(1 for r in live if r.get("llm")),
              "llm_failed": sum(1 for r in live if r.get("llm_err")),
              "skipped": {}}
    for r in live:
        s = r.get("status")
        if s and s != "scored":
            health["skipped"][s] = health["skipped"].get(s, 0) + 1
    evals = []
    for r in live:
        if r.get("llm") and r.get("bars") is not None and r["status"] == "scored":
            e = evaluate_item(r, P)
            if not e["excluded"]:
                e["t_exit"] = r["t_pub"] + 3600
                e["t_seen"] = r["t_seen"]
            evals.append(e)
    good = [e for e in evals if not e["excluded"]]
    health["evaluated"] = len(good)
    health["excluded"] = {}
    for e in evals:
        if e["excluded"]:
            health["excluded"][e["excluded"]] = health["excluded"].get(e["excluded"], 0) + 1
    out = {"latency_s": lat, "health": health, "fraction_of_move": {}, "pnl": {}, "verdict": {}}
    for mk in ("crypto", "stock", "ALL"):
        sub = [e for e in good if mk == "ALL" or e["market"] == mk]
        large = [e for e in sub if e["large"]]
        fr = {}
        for key in ("f_snap", "f_bar", "f_seen"):
            xs = [e[key] for e in large if e.get(key) is not None]
            fr[key] = {"n": len(xs), "median": percentile(xs, 0.5), "p25": percentile(xs, 0.25), "p75": percentile(xs, 0.75),
                       "share_ge_half": (sum(1 for x in xs if x >= 0.5) / len(xs)) if xs else None,
                       "share_ge_one": (sum(1 for x in xs if x >= 1.0) / len(xs)) if xs else None}
        fr["items_total"], fr["items_large"] = len(sub), len(large)
        out["fraction_of_move"][mk] = fr
        if mk == "ALL":
            continue
        tr = select_trades(sub, P)
        blk = pnl_block(tr, P)
        blk["confidence_ge_80"] = pnl_block(select_trades(sub, P, min_conf=80), P)
        blk["any_confidence"] = pnl_block(select_trades(sub, P, min_conf=0), P)
        blk["bar_entry"] = pnl_block(select_trades(sub, P, gross_key="gross_bar"), P, "gross_bar", "rand_gross_bar")
        blk["large_move_only"] = pnl_block([t for t in tr if t["large"]], P)
        out["pnl"][mk] = blk
        out["verdict"][mk] = verdict(blk, P)
    return out
