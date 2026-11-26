"""notice_fwd: forward paper ledger of exchange notices entered 5 seconds after the pod first saw them (Q2 of PLAN_20261127_fable.md).
Protocol: research/studies/protocol_notice_fwd_20261126.md (locked before any price of this study was read). Pure logic: no network here;
the runner (research/studies/notice_fwd.py) injects the OKX tape and reads the parts of branch data/news-ingest.

Input rows are the joined item rows of research/news_train/ingest_branch.py (source, key, title, t_pub, res, t_seen). A notice is a
listing, delisting, monitoring-tag or Korean-exchange notice that names a coin with an OKX USDT perpetual. One cluster = (class, coin)
within 7 days; its clock is the earliest t_seen among rows that were fast enough. Entry at t_seen + 5 s, three holds, primary 60 min."""
import hashlib
import math
import re
from statistics import median

from core import forced_flow as ff
from core import kr_listing as kl
from core import sequential as sq

ENTRY_DELAY_S = 5
MAX_LAT_S = 25                      # t_seen - t_pub above this cannot be entered inside 30 s of the stamp
SLOW_MIN_ITEMS = 20                 # a source is killed once it has this many second-resolution items and a median above MAX_LAT_S
HOLDS = (300, 3600, 14400)
PRIMARY_HOLD = 3600
SLIP = 0.0015                       # against us on the entry fill
REST_COST = 0.0025                  # fees 0.10% + exit slippage 0.15%; with SLIP the round trip is 0.40%
FUND = {300: 0.0, 3600: 0.0003, 14400: 0.001}    # assumed funding per hold, charged as a cost
DEDUPE_S = 7 * 86400
CONTROL_SHIFT_S = 86400             # no-notice control: the same coin, side and hold one day earlier
CLIP = 0.10                         # e-process unit clip (raw means are reported)
ALPHA = 0.05
MIN_N = 30                          # traded tape-entry clusters before any kill or found verdict
MIN_GROSS = 0.008                   # 2x the 0.40% round trip
MIN_X = 0.2
DEADLINE = "2027-02-06"
SETTLE_GRACE_S = 120
MAX_ATTEMPTS = 3
EXPIRE_S = 6 * 3600                 # a pending cluster whose exits cannot be filled this long after the last hold is dropped

_HANGUL = re.compile(r"[가-힣]")
_KR_VENUE = re.compile(r"upbit|bithumb|업비트|빗썸", re.I)
_SKIP = re.compile(r"alpha|tradfi|pre-?market|launchpool|margin|leverage|earn\b|loan|p2p|airdrop|competition|tournament|"
                   r"perp(?:etual)?\s+monitor|spot\s+monitor|\bupdate\b|simple earn|vip", re.I)
_LIST = re.compile(r"\b(?:will\s+list|to\s+list|lists|will\s+add|listing\s+of)\b", re.I)
_DELIST = re.compile(r"\bdelist(?:s|ing|ed)?\b", re.I)
_PAREN = re.compile(r"\(([A-Z0-9]{2,15})\)")


def _clean(title):
    return re.sub(r"-USD[TC]?(?:-SWAP)?\b", "", title or "")


def _after_delist(title):
    m = re.search(r"delist(?:s|ing|ed)?(?:\s+of)?\s+(.+)", title, re.I)
    if not m:
        return []
    seg = re.split(r"\s+on\s+\d|\s+(?:spot|perpetual|futures|margin|trading|contract|and\s+update)|\s+from\b|\s+-\s+\d", m.group(1), flags=re.I)[0]
    return ff._tokens(seg)


def classify(source, title):
    """-> {'cls', 'side', 'coins'} or None. cls in listing, delist, monitor, kr_listing, kr_delist, kr_caution. side +1 long, -1 short.
    Price-alert bot lines ('Perp Monitor: X +6% in 10 seconds'), Alpha/TradFi/margin/P2P/event notices are not notices."""
    t = (title or "").strip()
    if not t:
        return None
    if _HANGUL.search(t) or _KR_VENUE.search(t):
        syms = kl.listing_symbols(t)
        if syms:
            return {"cls": "kr_listing", "side": 1, "coins": syms}
        k = ff.kr_class(t)
        syms = ff.kr_symbols(t) if k else []
        if k and syms:
            return {"cls": "kr_delist" if k == "delist" else "kr_caution", "side": -1, "coins": syms}
        return None
    if _SKIP.search(t):
        return None
    t = _clean(t)
    syms = ff.monitoring_symbols(t)
    if syms:
        return {"cls": "monitor", "side": -1, "coins": syms}
    if _DELIST.search(t):
        syms = ff.fut_delist_symbols(t) or _after_delist(t)
        return {"cls": "delist", "side": -1, "coins": syms} if syms else None
    if _LIST.search(t):
        syms = [s for s in _PAREN.findall(t) if s not in ff._NOT_COIN]
        if not syms:
            m = re.search(r"(?:will\s+list|to\s+list|lists|will\s+add)\s+(.+)", t, re.I)
            syms = ff._tokens(re.split(r"\s+on\s+|\s+with\s+|\s+for\s+|\s+via\s+", m.group(1))[0]) if m else []
        return {"cls": "listing", "side": 1, "coins": syms} if syms else None
    return None


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def pct(xs, q):
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1)))] if s else None


def latency_table(joined):
    """-> per source: items, items with second resolution, median / p90 of t_seen - t_pub over those, and the notice counts by class.
    Outcome-free: no price is read. `joined` is {(source, key): row}."""
    out = {}
    for (src, _), d in joined.items():
        b = out.setdefault(src, {"items": 0, "lat": [], "notices": {}, "notice_items": 0})
        b["items"] += 1
        if d.get("res") == "s" and _num(d.get("t_seen")) and _num(d.get("t_pub")):
            b["lat"].append(d["t_seen"] - d["t_pub"])
        c = classify(src, d.get("title"))
        if c:
            b["notice_items"] += 1
            b["notices"][c["cls"]] = b["notices"].get(c["cls"], 0) + 1
    res = {}
    for src, b in sorted(out.items()):
        lat = b["lat"]
        res[src] = {"items": b["items"], "items_s": len(lat), "median_lat_s": round(median(lat), 3) if lat else None,
                    "p90_lat_s": round(pct(lat, 0.9), 3) if lat else None,
                    "share_fast": round(sum(1 for x in lat if x <= MAX_LAT_S) / len(lat), 3) if lat else None,
                    "notice_items": b["notice_items"], "notices": dict(sorted(b["notices"].items())),
                    "slow": bool(len(lat) >= SLOW_MIN_ITEMS and median(lat) > MAX_LAT_S)}
    return res


def slow_sources(table, sticky=()):
    """Killed sources: sticky flags from earlier runs plus today's table (a flag is never lifted)."""
    return sorted(set(sticky) | {s for s, v in table.items() if v["slow"]})


def clusters(joined, slow=()):
    """Notice clusters in time order. Each row of a cluster is one (source, key) item; the cluster clock is the earliest t_seen among rows
    that are fast (res 's', 0 <= t_seen - t_pub <= MAX_LAT_S) and from a source not in `slow`. -> list of dicts."""
    by = {}
    for (src, key), d in joined.items():
        c = classify(src, d.get("title"))
        if not c or not _num(d.get("t_seen")):
            continue
        lat = d["t_seen"] - d["t_pub"] if _num(d.get("t_pub")) else None
        fast = d.get("res") == "s" and lat is not None and 0 <= lat <= MAX_LAT_S and src not in slow
        for coin in c["coins"]:
            by.setdefault((c["cls"], coin), []).append({"source": src, "key": key, "t_seen": d["t_seen"], "t_pub": d.get("t_pub"), "lat": lat,
                                                      "fast": fast, "side": c["side"], "title": (d.get("title") or "")[:160]})
    out = []
    for (cls, coin), rows in by.items():
        rows.sort(key=lambda r: r["t_seen"])
        group = [rows[0]]
        for r in rows[1:]:                           # a new cluster starts DEDUPE_S after the current one's first row
            if r["t_seen"] - group[0]["t_seen"] >= DEDUPE_S:
                out.append(_cluster(cls, coin, group))
                group = [r]
            else:
                group.append(r)
        out.append(_cluster(cls, coin, group))
    return sorted(out, key=lambda c: (c["t_seen"], c["id"]))


def _cluster(cls, coin, rows):
    fast = [r for r in rows if r["fast"]]
    first = fast[0] if fast else rows[0]
    direct = [r for r in rows if not r["source"].startswith("eqn")]
    gap = None
    if first["source"].startswith("eqn") and direct and _num(first["t_pub"]) and _num(direct[0]["t_pub"]):
        gap = round(first["t_pub"] - direct[0]["t_pub"], 3)
    return {"id": f"{cls}|{coin}|{int(rows[0]['t_seen'])}", "cls": cls, "coin": coin, "side": rows[0]["side"], "eligible": bool(fast),
            "source": first["source"], "t_seen": first["t_seen"], "t_pub": first["t_pub"], "lat": first["lat"], "title": first["title"],
            "sources": sorted({r["source"] for r in rows}), "first_any": rows[0]["source"], "pub_gap_s": gap}


# ---------------------------------------------------------------- fills
def tape_fill(get_page, inst, t, window_s=30, max_pages=6):
    """First OKX print at or after second `t`. `get_page(inst, after_ms)` -> trades older than after_ms, newest first, as
    [{'ts': ms, 'px': float}]. Pages back from t + window_s; a result is returned only if the walk crossed below t (so the earliest print
    in [t, t + window_s] is known), else None. -> {'px', 'ts', 'src': 'tape'} or None."""
    t_ms = int(t * 1000)
    cursor = int((t + window_s) * 1000)
    got = []
    for _ in range(max_pages):
        page = get_page(inst, cursor) or []
        if not page:
            return _pick(got, t_ms) if got else None   # history ends: the earliest print on record is known
        got.extend(page)
        oldest = min(p["ts"] for p in page)
        if oldest < t_ms:
            return _pick(got, t_ms)
        cursor = oldest
    return None


def _pick(got, t_ms):
    ok = [p for p in got if p["ts"] >= t_ms]
    if not ok:
        return None
    p = min(ok, key=lambda p: p["ts"])
    return {"px": p["px"], "ts": p["ts"] / 1000, "src": "tape"}


def bar_fill(bars, t):
    """Fallback: open of the 1 m bar that starts at the first minute boundary at or after `t` (a delay of up to 60 s, so it is flagged
    src 'bar' and never counts as evidence). bars = {bar_ts_seconds: open}."""
    b = math.ceil(t / 60) * 60
    return {"px": bars[b], "ts": b, "src": "bar"} if b in bars else None


def fill(tape, bars_for, inst, t):
    """Tape first, bar fallback. `tape(inst, t)` and `bars_for(inst, t)` are injected by the runner."""
    f = tape(inst, t)
    if f:
        return f
    bars = bars_for(inst, t)
    return bar_fill(bars, t) if bars else None


# ---------------------------------------------------------------- trade arithmetic
def trade_net(side, entry_raw, exit_raw, hold, mult=1.0):
    """(gross, net) of one trade: the entry is filled SLIP against the side, REST_COST and the assumed funding are charged;
    `mult` scales every cost (2.0 = the 2x-cost check)."""
    efill = entry_raw * (1 + side * SLIP * mult)
    gross = side * (exit_raw / entry_raw - 1)
    net = side * (exit_raw / efill - 1) - mult * REST_COST - mult * FUND[hold]
    return gross, net


def control_side(cid, hold):
    """Random side of the control, fixed by a hash of the cluster id."""
    return 1 if hashlib.sha256(f"{cid}|{hold}".encode()).digest()[0] % 2 == 0 else -1


def make_rows(cl, entry, exits, ctrl):
    """Rows (one per hold with an exit) of a cluster. entry / exits[hold] are fills; ctrl = {hold: (entry_fill, exit_fill)} of the no-notice
    control (the same coin, side and hold one day earlier); a missing fill gives nn_net None."""
    rows = []
    for hold, ex in sorted(exits.items()):
        gross, net = trade_net(cl["side"], entry["px"], ex["px"], hold)
        net2 = trade_net(cl["side"], entry["px"], ex["px"], hold, mult=2.0)[1]
        cs = control_side(cl["id"], hold)
        cnet = trade_net(cs, entry["px"], ex["px"], hold)[1]
        nn = None
        c = ctrl.get(hold)
        if c and c[0] and c[1]:
            nn = trade_net(cl["side"], c[0]["px"], c[1]["px"], hold)[1]
        rows.append({"id": cl["id"], "cls": cl["cls"], "coin": cl["coin"], "side": cl["side"], "source": cl["source"], "hold": hold,
                     "t_entry": cl["t_seen"] + ENTRY_DELAY_S, "entry_px": entry["px"], "entry_src": entry["src"], "entry_ts": entry["ts"],
                     "exit_px": ex["px"], "exit_src": ex["src"], "lat": cl["lat"], "gross": gross, "net": net, "net_2x": net2,
                     "ctrl_side": cs, "ctrl_net": cnet, "nn_net": nn})
    return rows


def clip(x):
    return max(-CLIP, min(CLIP, x))


class Ledger:
    """Evidence = the 60-minute row of each tape-entry cluster, paired against the random-side control."""

    def __init__(self, state=None):
        self.ep = sq.EProcess(alpha=ALPHA, lo=CLIP, hi=CLIP, paired=True)
        for k in ("n", "sum", "sumsq", "log_up", "log_down", "decision", "decided_at"):
            if state and k in state:
                setattr(self.ep, k, state[k])

    def add(self, row):
        if row["hold"] == PRIMARY_HOLD and row["entry_src"] == "tape":
            self.ep.update(clip(row["net"]) - clip(row["ctrl_net"]))

    def dump(self):
        return {k: getattr(self.ep, k) for k in ("n", "sum", "sumsq", "log_up", "log_down", "decision", "decided_at")}


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def verdict(rows, ep_view, today=None):
    """The frozen verdict on the primary-hold tape-entry rows (today = 'YYYY-MM-DD' for the deadline). -> dict with n, means, x and
    verdict in underpowered (n < MIN_N before the deadline), continue, kill (with reasons), found, not_found (deadline passed, n < MIN_N)."""
    p = [r for r in rows if r["hold"] == PRIMARY_HOLD and r["entry_src"] == "tape"]
    n = len(p)
    late = bool(today and today > DEADLINE)
    out = {"n": n, "min_n": MIN_N, "deadline": DEADLINE}
    if not n:
        out["verdict"] = "not_found" if late else "underpowered"
        return out
    net = [r["net"] for r in p]
    m, g = _mean(net), _mean([r["gross"] for r in p])
    sd = math.sqrt(sum((v - m) ** 2 for v in net) / (n - 1)) if n > 1 else None
    ts = [r["t_entry"] for r in p]
    months = (max(ts) - min(ts)) / 86400 / 30.4375
    x = (n / months) * (m / sd) ** 2 if months > 0 and sd and m > 0 else (0.0 if sd else None)
    d_rand = _mean([r["net"] - r["ctrl_net"] for r in p])
    nn = [r["net"] - r["nn_net"] for r in p if r.get("nn_net") is not None]
    d_nn = _mean(nn)
    out.update({"mean_net": m, "mean_gross": g, "mean_net_2x": _mean([r["net_2x"] for r in p]), "diff_vs_random_side": d_rand,
                "diff_vs_no_notice": d_nn, "n_no_notice": len(nn), "x_cluster": x, "e": ep_view})
    reasons = []
    if n >= MIN_N:
        if m <= 0:
            reasons.append("mean net <= 0")
        if g < MIN_GROSS:
            reasons.append("mean gross < 0.8%")
        if d_rand <= 0:
            reasons.append("not above the random-side control")
        if d_nn is not None and d_nn <= 0:
            reasons.append("not above the no-notice control")
        if x is not None and x < MIN_X:
            reasons.append("cluster x < 0.2")
    out["reasons"] = reasons
    if n < MIN_N:
        out["verdict"] = "not_found" if late else "underpowered"
    elif reasons:
        out["verdict"] = "kill"
    elif ep_view.get("decision") == "edge" and out["mean_net_2x"] > 0:
        out["verdict"] = "found"
    else:
        out["verdict"] = "continue"
    return out


# ---------------------------------------------------------------- one forward step
def step(state, cls_list, now, perps, tape, bars_for):
    """Advance the ledger once. -> (state, new_rows, new_notices); state is mutated.
    state: seen {cluster id: status}, pending {id: {cluster, inst, entry, attempts, done}}, meta counters.
    A cluster is entered once: eligible, its coin has an OKX USDT perp, and t_seen + 5 s + grace has passed. Exits and the no-notice
    control are filled for every hold whose exit time + SETTLE_GRACE_S has passed."""
    seen, pend = state.setdefault("seen", {}), state.setdefault("pending", {})
    meta = state.setdefault("meta", {})
    for k in ("no_perp", "too_slow", "no_entry", "bar_entry", "entered", "settled_rows", "expired"):
        meta.setdefault(k, 0)
    new_rows, notices = [], []
    for cl in cls_list:
        if cl["id"] in seen:
            continue
        inst = f"{cl['coin']}-USDT-SWAP"
        if not cl["eligible"]:
            status = "too_slow"
        elif inst not in perps:
            status = "no_perp"
        elif now < cl["t_seen"] + ENTRY_DELAY_S + SETTLE_GRACE_S:
            continue                                   # too early to look the print up; the next run takes it
        else:
            status = "pending"
            pend[cl["id"]] = {"cluster": cl, "inst": inst, "entry": None, "attempts": 0, "done": []}
        seen[cl["id"]] = status
        if status in ("too_slow", "no_perp"):
            meta[status] += 1
        notices.append({**{k: cl[k] for k in ("id", "cls", "coin", "side", "source", "sources", "first_any", "t_seen", "t_pub", "lat",
                                              "pub_gap_s", "title")}, "status": status})
    for cid, p in list(pend.items()):
        cl, inst = p["cluster"], p["inst"]
        t_entry = cl["t_seen"] + ENTRY_DELAY_S
        if p["entry"] is None:
            f = fill(tape, bars_for, inst, t_entry)
            if not f:
                p["attempts"] += 1
                if p["attempts"] >= MAX_ATTEMPTS:
                    seen[cid] = "no_entry"
                    meta["no_entry"] += 1
                    del pend[cid]
                continue
            p["entry"] = f
            meta["entered"] += 1
            meta["bar_entry"] += 1 if f["src"] == "bar" else 0
            seen[cid] = "entered"
        exits, ctrl = {}, {}
        for h in (h for h in HOLDS if h not in p["done"] and now >= t_entry + h + SETTLE_GRACE_S):
            ex = fill(tape, bars_for, inst, t_entry + h)
            if ex:
                exits[h] = ex
                ctrl[h] = (fill(tape, bars_for, inst, t_entry - CONTROL_SHIFT_S), fill(tape, bars_for, inst, t_entry - CONTROL_SHIFT_S + h))
        rows = make_rows(cl, p["entry"], exits, ctrl)
        p["done"] += [r["hold"] for r in rows]
        new_rows += rows
        meta["settled_rows"] += len(rows)
        if len(p["done"]) == len(HOLDS):
            seen[cid] = "settled"
            del pend[cid]
        elif now > t_entry + max(HOLDS) + EXPIRE_S:
            seen[cid] = "expired"
            meta["expired"] += 1
            del pend[cid]
    return state, new_rows, notices
