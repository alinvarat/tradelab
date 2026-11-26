"""News-analyst training, round 2: pure logic (protocol_r2_20261126.md). No network, no clock, stdlib only.

Adds to round 1 (logic.py, which is reused for costs, bootstrap, Holm and the cell scorer):
stock labels from 1-hour bars (in-session filings included), a GDELT crypto headline corpus (parse, coin map, dedupe),
calibrated abstention (a threshold on the analyst's own expected move, fitted on train only), the version-selection rule with a
trade floor, and the forward-sealed trigger that counts decisions, never outcomes."""
import bisect
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from research.news_train import logic as L

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_r2_v2.json")
VERSIONS_PATH = os.path.join(HERE, "versions_r2.json")
NY = ZoneInfo("America/New_York")
LAB = "main"                      # label key (one entry convention per item in round 2)
HOLDS_R2 = {"stock": ("1h", "eod"), "crypto": ("5m", "1h", "1d")}


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


def holds(market):
    return HOLDS_R2[market]


def ny_date(ts):
    return datetime.fromtimestamp(ts, NY).strftime("%Y-%m-%d")


def utc_ts(acc):
    """SEC acceptanceDateTime ('2026-11-25T22:26:14.000Z') is UTC (checked against the Atom feed on 2026-11-26).
    Round 1 read it as New York time (accept_ts, locked there): that moved filings 4-5 h later, so round 2 does not use it."""
    s = acc.replace("Z", "")[:19]
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


# ------------------------------------------------------------------ splits
def split_r2(ts, P):
    """clean train / clean validation / buffer / sealed_hist (crypto only, 2026-08-01..2026-11-26) / fwd (2026-11-27 on).
    Anything before the clean window is None: round 2 does not use the contaminated years."""
    d = P["dates"]
    if ts < L.day_ts(d["clean_start"]):
        return None
    if ts < L.day_ts(d["clean_train_end"]):
        return "train"
    if ts < L.day_ts(d["dev_end"]):
        return "validation"
    if ts < L.day_ts(d["sealed_hist_from"]):
        return "buffer"
    if ts < L.day_ts(d["fwd_from"]):
        return "sealed_hist"
    return "fwd"


def assert_dev(ts, P):
    if ts >= L.day_ts(P["dates"]["dev_end"]):
        raise L.SealError(f"t_pub {ts} is at or after dev_end: not for development")


# ------------------------------------------------------------------ stock labels from 1-hour bars
def stock_label_1h(bars, t_ref, lag, P):
    """bars: Yahoo 1-hour regular-session bars [{t,o,h,l,c}] ascending (09:30 ET start, last bar 30 min).
    Entry = open of the first bar that starts at or after t_ref + lag + extra (rounded to the NEXT bar); a filing after the last
    bar starts, or before the first, enters at the next session open. Holds: '1h' = open to close of the entry bar (None for the
    half-hour last bar), 'eod' = entry open to the close of the entry session. Pre-entry fields are known at entry.
    -> (label or None, reason)."""
    e = P["entry"]
    te = t_ref + lag + e["extra_s"]
    ts = [b["t"] for b in bars]
    i = bisect.bisect_left(ts, te)
    if i >= len(bars):
        return None, "no_entry_bar"
    if bars[i]["t"] - te > 5 * 86400:
        return None, "gap_in_bars"
    b = bars[i]
    sess = ny_date(b["t"])
    j = i - 1
    while j >= 0 and ny_date(bars[j]["t"]) == sess:
        j -= 1
    if j < 0:
        return None, "no_prior_bar"
    prev_close = bars[j]["c"]
    k = i
    while k + 1 < len(bars) and ny_date(bars[k + 1]["t"]) == sess:
        k += 1
    in_session = i > 0 and ny_date(bars[i - 1]["t"]) == sess
    full = i < k                                    # a following bar exists in the session, so this bar is a full hour
    closes, d = [], None                            # last close of each earlier session, newest first (for the 5-session run-up)
    for m in range(j, -1, -1):
        dd = ny_date(bars[m]["t"])
        if dd != d:
            closes.append(bars[m]["c"])
            d = dd
        if len(closes) >= 6:
            break
    lab = {"entry_ts": b["t"], "p_in": b["o"], "in_session": in_session, "delay_s": b["t"] - t_ref,
           "gross": {"1h": (b["c"] / b["o"] - 1.0) if full else None, "eod": bars[k]["c"] / b["o"] - 1.0},
           "exit_ts": {"1h": b["t"] + 3600, "eod": bars[k]["t"] + 3600},
           "day_move": b["o"] / prev_close - 1.0,
           "pre_move": (b["o"] / bars[i - 1]["o"] - 1.0) if in_session else (b["o"] / prev_close - 1.0),
           "runup5": (closes[0] / closes[5] - 1.0) if len(closes) >= 6 else None}
    return lab, "ok"


def stock_labelable(bars, t_ref, lag, P):
    """True when the entry bar and the following bars exist; reads no return (used by the forward trigger)."""
    lab, _ = stock_label_1h(bars, t_ref, lag, P)
    return lab is not None


# ------------------------------------------------------------------ GDELT crypto corpus
GKG_COLS = 27


def gkg_url(stamp):
    return f"https://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip"


def gkg_stamps(day, stride):
    """File stamps (YYYYMMDDHHMMSS, every 15 min) of one UTC day, keeping every `stride`-th (1 = all 96)."""
    out = []
    for n in range(96):
        if n % stride == 0:
            out.append(f"{day.replace('-', '')}{n // 4:02d}{(n % 4) * 15:02d}00")
    return out


def stamp_ts(stamp):
    return int(datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp())


def parse_gkg_line(line):
    f = line.rstrip("\n").split("\t")
    if len(f) < GKG_COLS:
        return None
    m = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", f[26], re.S)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    return {"date": f[1], "domain": f[3].lower(), "url": f[4], "themes": f[7] or "", "title": title}


def coin_of(title, themes, P):
    """One coin symbol when exactly one listed coin is named and the headline is crypto-context, else None."""
    g = P["gdelt"]
    t = (title or "").lower()
    t = re.sub(r"bitcoin\s+cash", "bchtoken", t)
    hits = set()
    for sym, names in g["coins"].items():
        for nm in names:
            if re.search(r"(?<![a-z0-9])" + re.escape(nm.lower()) + r"(?![a-z0-9])", t):
                hits.add(sym)
                break
    if re.search(r"bchtoken", t):
        hits.add("BCH")
    if len(hits) != 1:
        return None
    ctx = any(w in t for w in g["context_words"]) or any(w in (themes or "") for w in g["context_themes"])
    return next(iter(hits)) if ctx else None


def is_spam(title, domain, P):
    g = P["gdelt"]
    if any(domain == d or domain.endswith("." + d) for d in g["spam_domains"]):
        return True
    return any(re.search(rx, title, re.I) for rx in g["spam_title_regex"])


def norm_title(title):
    t = re.split(r"\s[-|–—]\s", title)[0]       # drop the site suffix
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def jaccard(a, b):
    a, b = set(a.split()), set(b.split())
    return len(a & b) / len(a | b) if a and b else 0.0


def dedupe_rows(rows, P):
    """rows: [{t, coin, title, domain}] -> one row per syndicated story: the earliest by (coin, normalised title), then any
    later row whose title word set has Jaccard >= params.gdelt.jaccard against a kept row of the same coin within the window."""
    g = P["gdelt"]
    out, recent = [], {}
    for r in sorted(rows, key=lambda r: (r["t"], r["url"] if "url" in r else "")):
        nt = norm_title(r["title"])
        if len(nt.split()) < g["min_words"]:
            continue
        keep = True
        for t0, n0 in recent.get(r["coin"], []):
            if r["t"] - t0 > g["dup_window_s"]:
                continue
            if nt == n0 or jaccard(nt, n0) >= g["jaccard"]:
                keep = False
                break
        if keep:
            out.append(r)
            recent.setdefault(r["coin"], []).append((r["t"], nt))
            recent[r["coin"]] = [x for x in recent[r["coin"]] if r["t"] - x[0] <= g["dup_window_s"]]
    return out


def cap_per_coin_day(rows, P):
    """At most params.gdelt.cap_per_coin_day rows per (coin, UTC day), chosen by sha order (no outcome is read)."""
    by = {}
    for r in rows:
        by.setdefault((r["coin"], L.day_of(r["t"])), []).append(r)
    out = []
    for k, v in by.items():
        v.sort(key=lambda r: L.unit(f"{P['seed']}:{r['coin']}:{r['t']}:{r['title'][:40]}"))
        out += v[:P["gdelt"]["cap_per_coin_day"]]
    return sorted(out, key=lambda r: (r["t"], r["coin"]))


def crypto_label_r2(bars, t_seen, P):
    """GDELT t_seen is the file stamp (when the row was available), so the entry is t_seen + extra, no further lag."""
    return L.crypto_label(bars, t_seen, P["entry"]["gdelt_lag_s"], P)


# ------------------------------------------------------------------ replies, calibration, decisions
def parse_reply2(text, market):
    """-> {ok, d{hold: long|short|none}, exp{hold: float % or None}, flow, conf, why}. exp and flow are optional (w0 has neither)."""
    if not text:
        return {"ok": False}
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"ok": False}
    try:
        o = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return {"ok": False}
    if not isinstance(o, dict) or not isinstance(o.get("d"), dict):
        return {"ok": False}
    d, ex = {}, {}
    ev = o.get("exp") if isinstance(o.get("exp"), dict) else {}
    for h in holds(market):
        v = str(o["d"].get(h, "")).strip().lower()
        if v not in ("long", "short", "none"):
            return {"ok": False}
        d[h] = v
        try:
            x = float(ev.get(h))
            ex[h] = x if math.isfinite(x) else None
        except (TypeError, ValueError):
            ex[h] = None
    try:
        conf = int(max(0, min(100, float(o.get("conf", 0)))))
    except Exception:  # noqa: BLE001
        conf = 0
    return {"ok": True, "d": d, "exp": ex, "flow": str(o.get("flow", "")).strip().lower()[:20], "conf": conf,
            "why": str(o.get("why", ""))[:300]}


def effective(dec, theta, calib):
    """Decision after calibrated abstention. theta: {hold: pct or None (never trade)}. Without calibration the model's own d stands.
    With it a hold trades only if the direction agrees with the sign of the analyst's expected move and |exp| >= theta (in %)."""
    if not dec or not dec.get("ok"):
        return dec
    if not calib:
        return dec
    d = {}
    for h, v in dec["d"].items():
        x = (dec.get("exp") or {}).get(h)
        th = (theta or {}).get(h)
        ok = (v != "none" and x is not None and th is not None and abs(x) >= th and (x > 0) == (v == "long"))
        d[h] = v if ok else "none"
    return dict(dec, d=d)


def fit_theta(rows, decs, market, hold, P):
    """Threshold on |expected move| (percent) that maximises the mean net P&L per offered item on TRAIN, subject to a trade floor.
    -> pct or None (no grid value gives enough trades: never trade this hold)."""
    best, best_s = None, None
    floor = P["select"]["theta_min_trades"][market]
    for th in P["select"]["theta_grid_pct"]:
        tot = n = tr = 0
        for r in rows:
            if r["market"] != market:
                continue
            lab = (r.get("labels") or {}).get(LAB)
            g = (lab or {}).get("gross", {}).get(hold)
            dec = decs.get(r["key"])
            if g is None or not dec or not dec.get("ok"):
                continue
            n += 1
            eff = effective(dec, {hold: th}, True)
            side = L.trade_side(eff, hold)
            if side:
                tr += 1
                tot += L.net_pnl(side, g, market, P)
        if n and tr >= floor:
            s = tot / n
            if best_s is None or s > best_s:
                best, best_s = th, s
    return best


def score_set(rows, decs, version, calib_theta, P):
    """Every (market, hold) cell of one version on one set; calib_theta: {market: {hold: pct}} (train fit) or None."""
    out = []
    for market in ("stock", "crypto"):
        th = (calib_theta or {}).get(market, {})
        eff = {k: effective(v, th, version.get("calib")) for k, v in decs.items()}
        for h in holds(market):
            out.append(L.score_cell(rows, eff, market, h, P, lag=LAB))
    return out


def select_lock(valid_cells, P):
    """valid_cells: {version_id: {market: cell of the primary hold on clean validation}} -> {market: version id or None}.
    Eligible = at least select.min_traded_val[market] traded items; then highest score_per_offered; tie -> lower version number."""
    lock = {}
    for market in ("stock", "crypto"):
        floor = P["select"]["min_traded_val"][market]
        best = None
        for vid in sorted(valid_cells, key=lambda v: int(v[1:])):
            c = (valid_cells[vid] or {}).get(market) or {}
            if c.get("n_traded", 0) < floor or c.get("score_per_offered") is None:
                continue
            if best is None or c["score_per_offered"] > best[1]:
                best = (vid, c["score_per_offered"])
        lock[market] = best[0] if best else None
    return lock


# ------------------------------------------------------------------ forward trigger (decisions only)
def fwd_trigger(items, decs, bars_by, now_ts, P, version, theta):
    """Counts for the forward stock set without reading any outcome: items settled (entry bar exists and the session has closed),
    the analyst's non-abstain decisions on the primary hold among them. Fire when traded >= done.min_traded."""
    prim = P["primary"]["stock"]
    settled = traded = 0
    for it in items:
        lab, _ = stock_label_1h(bars_by.get(it["sym"]) or [], it["t_pub"], P["entry"]["lag_s"], P)
        if not lab or lab["exit_ts"]["eod"] > now_ts or lab["gross"].get(prim) is None:
            continue
        dec = decs.get(it["key"])
        if not dec or not dec.get("ok"):
            continue
        settled += 1
        if L.trade_side(effective(dec, theta, version.get("calib")), prim):
            traded += 1
    return {"settled": settled, "traded": traded, "fire": traded >= P["done"]["min_traded"]}


# ------------------------------------------------------------------ prompt rendering
def pre_block2(item, lab):
    if item["market"] == "stock":
        if lab.get("in_session"):
            return (f"Already priced before your entry: this filing came during the trading session; you can only enter at the next hourly bar open, "
                    f"{lab.get('delay_s', 0) / 60:.0f} minutes after publication. Move of the stock from the start of that hour to your entry "
                    f"{L.pct(lab.get('pre_move'))}; move since the previous close {L.pct(lab.get('day_move'))}; previous 5-session run-up {L.pct(lab.get('runup5'))}.")
        return (f"Already priced before your entry: the filing came outside the session; you enter at the next session open. Opening gap "
                f"versus the previous close {L.pct(lab.get('pre_move'))}; previous 5-session run-up {L.pct(lab.get('runup5'))}.")
    return (f"Already priced before your entry: move from the headline's availability to entry {L.pct(lab.get('pre_lag'))}; "
            f"move over the hour before {L.pct(lab.get('pre_1h'))}.")


def outcome_block2(item, lab):
    return ", ".join(f"{h} {L.pct((lab.get('gross') or {}).get(h))}" for h in holds(item["market"]))


def render_user2(item, lab, version, analogs=None, P=None):
    P = P or load_params()
    mk = item["market"]
    hs = holds(mk)
    lines = [f"Item type: {'SEC 8-K filing or press release exhibit' if mk == 'stock' else 'crypto news headline'}. "
             f"Instrument market: {'US stock' if mk == 'stock' else 'crypto perpetual'}."]
    if item.get("items"):
        lines.append("8-K items: " + ", ".join(item["items"]))
    if mk == "crypto":
        lines.append(f"Source: {item.get('src') or 'news'}.")
    if version.get("uses_pre") and lab:
        lines.append(pre_block2(item, lab))
    lines.append(item.get("descr") or "")
    lines.append("Text:\n" + (item.get("text") or "")[:P["text_chars"]])
    if analogs:
        lines.append("Similar past items and what happened after entry (long-side moves, before costs):")
        for k, d in enumerate(analogs, 1):
            it, lb = d["item"], d["lab"]
            pre = pre_block2(it, lb) if version.get("uses_pre") else ""
            lines.append(f"{k}. {(it.get('text') or '')[:P['analogs']['text_chars']].strip()} | {pre} | outcome: {outcome_block2(it, lb)}")
    want_exp = version.get("calib")
    shape = '"d": {' + ", ".join(f'"{h}": "long|short|none"' for h in hs) + "}"
    if want_exp:
        shape += ", \"exp\": {" + ", ".join(f'"{h}": signed expected move in percent' for h in hs) + "}"
    if version.get("flow"):
        shape += ', "flow": "forced_sell|forced_buy|index|none"'
    lines.append("Answer with one JSON object only: {" + shape + ', "conf": 0-100, "why": "one short sentence"}.')
    return "\n".join(lines)


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def versions_registry(path=VERSIONS_PATH):
    with open(path) as f:
        return json.load(f)


def check_version(v, root=HERE):
    p = os.path.join(root, v["prompt"])
    if sha256_file(p) != v["sha256"]:
        raise ValueError(f"prompt of version {v['id']} does not match its registered sha256")
    return p


# ------------------------------------------------------------------ helpers added for the runner
def fix_ts(ts_et_read):
    """Round 1's accept_ts reads the UTC digits of acceptanceDateTime as New York time; recover the true UTC epoch from it
    (the wall-clock digits are the UTC clock). Exact except inside the one repeated hour at the autumn DST change."""
    dt = datetime.fromtimestamp(ts_et_read, NY).replace(tzinfo=None)
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def redact_title(title, coin, P):
    s = title or ""
    for nm in P["gdelt"]["coins"].get(coin, []) + [coin]:
        s = re.sub(r"(?<![A-Za-z0-9])" + re.escape(nm) + r"(?![A-Za-z0-9])", "[COIN]", s, flags=re.I)
    return L.scrub_dates(s)


def item_group(it):
    """Coarse class used only by the error analysis (train)."""
    t = (it.get("text") or "").lower()
    if it["market"] == "stock":
        its = it.get("items") or []
        return "8-K " + (its[0] if its else "none")
    for name, rx in (("etf", r"\betf\b"), ("hack", r"hack|exploit|stolen|breach"), ("regulation", r"sec\b|regulat|ban|law|court|lawsuit|bill|senate"),
                     ("listing", r"list|delist"), ("price_move", r"surge|plunge|rall|crash|drop|jump|soar|slump|price|falls|rises"),
                     ("adoption", r"adopt|partner|launch|integrat|accept")):
        if re.search(rx, t):
            return name
    return "other"
