"""Family 7: US small-cap intraday LONG events. Pure functions, standard library only, no network.

Pre-registered rules (locked before the first scan; see ops/lines/F7_smallcap_intraday.md):
  (a) gap-up opening-range breakout (ORB): premarket gap >= 20% / 40% vs the previous regular close, ORB window 5/15/30 min,
      long on the first 5-minute close above the ORB high, filled at the NEXT bar's open; exits: stop at ORB low + time
      exit 15:55 / 11:30 ET, or an 8% trailing stop + 15:55.
  (b) LULD halt resumption (Nasdaq trade-halt feed, forward only): after a LUDP pause whose run-up before the halt was >= 5%,
      buy the first 5-minute bar open after resumption, hold 15 min / 60 min, with or without an 8% hard stop.
  (c) catalyst-tagged gaps (8-K / press-release keywords, no LLM): gap >= 20%, ORB 15 min, by tag.
Point-in-time universe: prior close 1-20 USD, 20-session average dollar volume 0.5-50 MUSD from sessions BEFORE the event day,
premarket dollar volume >= 50k USD by 09:25 ET. A bar is [minute_of_day_ET, open, high, low, close, volume].
Costs: half-spread/slippage per side SLIP plus Webull regulatory fees (no commission); the 2x stress doubles the cost.
"""
import math
import random
from datetime import date as _date, datetime, timezone
from zoneinfo import ZoneInfo

from core import sweep_stats as ss

ET = ZoneInfo("America/New_York")
PRE_START, PM_CUT, REG_OPEN, REG_CLOSE = 240, 565, 570, 960     # minute of day ET; PM_CUT: bars starting before 09:25
ENTRY_LAST = 660                                               # entry bar must start by 11:00 ET
EOD_MIN = 955                                                  # exit at the close of the bar ending 15:55
SLIP = 0.005                                                   # per side, EST (small-cap spread + breakout slippage)
PX_LO, PX_HI = 1.0, 20.0
ADV_LO, ADV_HI, ADV_SPLIT = 0.5e6, 50e6, 5e6
PM_DV_MIN = 50_000.0
MIN_PRIOR_SESSIONS = 10
PICK_K = 3                                                     # at most 3 positions per day (account split in 3)
GAPS = (0.20, 0.40)
ORBS = (5, 15, 30)
BANDS = ("low", "high")
EXITS = {"stoporb_eod": {"stop": "orb_low", "time": EOD_MIN},
         "stoporb_1130": {"stop": "orb_low", "time": 690},
         "trail8_eod": {"trail": 0.08, "time": EOD_MIN}}
TAGS = ("contract", "fda", "earnings", "offering", "none")
HALT_RUNUP = 0.05
HALT_HOLDS = {"t15": 3, "t60": 12}                             # in 5-minute bars
SIZE = {"lev": 1, "k": PICK_K}
CFG = {"alpha": 0.05, "account_usd": 147.0,
       "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
       "pass": {"min_val_trades": 30, "min_test_trades": 20}}


def _ts(y, m, d):
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp()


BOUNDS = {"train": (_ts(2026, 9, 16), _ts(2027, 1, 1)),
          "validation": (_ts(2027, 1, 1), _ts(2027, 4, 1)),
          "test": (_ts(2027, 4, 1), _ts(2027, 7, 1))}


# ------------------------------------------------------------------ time and bars
_off_cache = {}


def et_parts(ts):
    """(YYYY-MM-DD, minute of day) in New York for a UTC epoch second."""
    k = int(ts) // 3600
    off = _off_cache.get(k)
    if off is None:
        off = int(datetime.fromtimestamp(ts, ET).utcoffset().total_seconds())
        _off_cache[k] = off
    t = int(ts) + off
    d = _date.fromordinal(719163 + t // 86400)
    return d.isoformat(), (t % 86400) // 60


def ts_of(day, minute):
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, minute // 60, minute % 60, tzinfo=ET).timestamp()


def parse_chart(res):
    """Yahoo chart result (5m, includePrePost, events=split) -> ({date: {"pre": [bars], "reg": [bars]}}, [split dates])."""
    ts = res.get("timestamp") or []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    o_, h_, l_, c_, v_ = (q.get(k) or [] for k in ("open", "high", "low", "close", "volume"))
    days = {}
    for i, t in enumerate(ts):
        try:
            o, h, l, c = o_[i], h_[i], l_[i], c_[i]
        except IndexError:
            break
        if None in (o, h, l, c):
            continue
        v = (v_[i] if i < len(v_) else 0) or 0
        d, m = et_parts(t)
        if PRE_START <= m < REG_OPEN:
            days.setdefault(d, {"pre": [], "reg": []})["pre"].append([m, o, h, l, c, v])
        elif REG_OPEN <= m < REG_CLOSE:
            days.setdefault(d, {"pre": [], "reg": []})["reg"].append([m, o, h, l, c, v])
    splits = []
    for s in ((res.get("events") or {}).get("splits") or {}).values():
        try:
            splits.append(et_parts(s["date"])[0])
        except (KeyError, TypeError, ValueError):
            pass
    return days, sorted(splits)


def _dv(bars):
    return sum(b[4] * b[5] for b in bars)


def find_events(sym, days, splits, today, after_close, gap_min=0.20):
    """Gap events of one symbol. Point in time: previous close, 20-session average dollar volume and the premarket gap use only
    information available at 09:25 ET of the event day. A day counts only when complete (earlier than `today`, or `today`
    after the close). Days within 3 sessions of a split are skipped (a reverse split fakes a gap)."""
    dates = sorted(d for d, v in days.items() if v["reg"])
    out = []
    sp = [_date.fromisoformat(s) for s in splits]
    for k in range(1, len(dates)):
        d, pd_ = dates[k], dates[k - 1]
        if d > today or (d == today and not after_close):
            continue
        dd = _date.fromisoformat(d)
        if (dd - _date.fromisoformat(pd_)).days > 5:
            continue
        if any(-3 <= (dd - s).days <= 4 for s in sp):
            continue
        prev_close = days[pd_]["reg"][-1][4]
        if not (PX_LO <= prev_close <= PX_HI):
            continue
        pm = [b for b in days[d]["pre"] if b[0] < PM_CUT]
        reg = days[d]["reg"]
        if not pm or reg[0][0] != REG_OPEN:
            continue
        gap = pm[-1][4] / prev_close - 1.0
        if gap < gap_min:
            continue
        pm_dv = _dv(pm)
        if pm_dv < PM_DV_MIN:
            continue
        prior = [_dv(days[x]["reg"]) for x in dates[max(0, k - 20):k]]
        if len(prior) < MIN_PRIOR_SESSIONS:
            continue
        adv = sum(prior) / len(prior)
        if not (ADV_LO <= adv <= ADV_HI):
            continue
        out.append({"sym": sym, "date": d, "prev_date": pd_, "prev_close": prev_close, "pm_px": pm[-1][4], "gap": round(gap, 5),
                    "pm_dv": round(pm_dv, 0), "adv20": round(adv, 0), "open": reg[0][1], "reg": reg})
    return out


# ------------------------------------------------------------------ simulation
def fees_frac(px):
    """Webull US stock regulatory fees as a fraction of notional for a round trip: SEC 0.0000206 of sale proceeds, FINRA TAF
    0.000166 per share sold (EST), CAT 0.000003 per share on each side. No commission."""
    return 0.0000206 + (0.000166 + 2 * 0.000003) / px


def band_ok(adv, band):
    if band == "low":
        return ADV_LO <= adv < ADV_SPLIT
    if band == "high":
        return ADV_SPLIT <= adv <= ADV_HI
    return ADV_LO <= adv <= ADV_HI


def run_trade(bars, i, time_min=None, hold=None, stop_px=None, trail=None, hstop=None):
    """Long from the open of bars[i]. Stop (absolute `stop_px`, `hstop` fraction below entry, or `trail` fraction below the running
    high) is checked on each held bar BEFORE that bar's high updates the trail; a bar opening through the stop fills at its
    open. Time exit at the close of the first bar ending at/after `time_min`, or after `hold` bars. Returns raw (unslipped)
    prices and excursions."""
    ep = bars[i][1]
    hwm, lo, hi = ep, ep, ep
    xp, j_exit = bars[-1][4], len(bars) - 1
    for j in range(i, len(bars)):
        m, o, h, l, c, _ = bars[j]
        s = stop_px
        if hstop is not None:
            s = max(s or 0.0, ep * (1 - hstop))
        if trail is not None:
            s = max(s or 0.0, hwm * (1 - trail))
        if s is not None and s > 0 and l <= s:
            xp = o if (j > i and o <= s) else s
            lo = min(lo, xp)
            j_exit = j
            break
        lo, hi, hwm = min(lo, l), max(hi, h), max(hwm, h)
        if (time_min is not None and m + 5 >= time_min) or (hold is not None and j - i + 1 >= hold):
            xp, j_exit = c, j
            break
    return {"ep": ep, "xp": xp, "gross": xp / ep - 1.0, "mfe": hi / ep - 1.0, "mae": max(0.0, 1.0 - lo / ep), "j_exit": j_exit}


def _trade(sym, day, bars, i, run, rule_id, extra=None):
    cost = 2 * SLIP + fees_frac(run["ep"])
    t = {"t": ts_of(day, bars[i][0]), "x": ts_of(day, bars[run["j_exit"]][0] + 5), "side": 1, "sym": sym, "date": day,
         "rule": rule_id, "ep": run["ep"], "xp": run["xp"], "gross": run["gross"], "cost": cost, "fund": 0.0,
         "net": run["gross"] - cost, "mfe": run["mfe"], "mae": run["mae"], "ctrl_net": None}
    t.update(extra or {})
    return t


def _ctrl_rng(sym, day, tag):
    return random.Random(f"{sym}|{day}|{tag}")


def orb_signal(bars, orb):
    """(entry index, ORB low) for the first 5m close above the ORB high; entry is the NEXT bar, which must start by 11:00."""
    n_or = [b for b in bars if b[0] < REG_OPEN + orb]
    if not n_or or bars[0][0] != REG_OPEN:
        return None
    hi, lo = max(b[2] for b in n_or), min(b[3] for b in n_or)
    for j in range(len(n_or), len(bars) - 1):
        if bars[j][0] + 5 > ENTRY_LAST:
            break
        if bars[j][4] > hi and bars[j + 1][0] <= ENTRY_LAST:
            return j + 1, lo, len(n_or)
    return None


def orb_trade(ev, rule):
    """One ORB trade for an event (or None) with its paired control: same exit, entry at a random bar of the same day between
    the end of the ORB window and 11:00. The control exists whenever the day has a valid window, signal or not is irrelevant."""
    bars = ev["reg"]
    sig = orb_signal(bars, rule["orb"])
    if sig is None:
        return None
    i, orb_low, n_or = sig
    spec = EXITS[rule["exit"]]

    def go(idx):
        sp = orb_low if (spec.get("stop") == "orb_low" and orb_low < bars[idx][1]) else None
        return run_trade(bars, idx, time_min=spec["time"], stop_px=sp, trail=spec.get("trail"))
    run = go(i)
    cands = [k for k in range(n_or, len(bars)) if bars[k][0] <= ENTRY_LAST]
    ctrl = go(_ctrl_rng(ev["sym"], ev["date"], rule["id"]).choice(cands)) if cands else None
    t = _trade(ev["sym"], ev["date"], bars, i, run, rule["id"], {"gap": ev["gap"], "tag": ev.get("tag"), "adv20": ev["adv20"]})
    if ctrl:
        t["ctrl_net"] = ctrl["gross"] - (2 * SLIP + fees_frac(ctrl["ep"]))
    return t


# ------------------------------------------------------------------ rules
def build_rules():
    """The whole pre-registered family (ids are stable and unique)."""
    rules = []
    for g in GAPS:
        for o in ORBS:
            for e in EXITS:
                for b in BANDS:
                    rules.append({"id": f"a_gap{int(g * 100)}_orb{o}_{e}_{b}", "fam": "orb", "gap": g, "orb": o, "exit": e, "band": b, "tag": None})
    for tag in TAGS:
        for e in ("stoporb_eod", "trail8_eod"):
            rules.append({"id": f"c_{tag}_gap20_orb15_{e}", "fam": "orb", "gap": 0.20, "orb": 15, "exit": e, "band": "any", "tag": tag})
    for h in HALT_HOLDS:
        for s in ("nostop", "stop8"):
            rules.append({"id": f"b_halt_{h}_{s}", "fam": "halt", "hold": h, "stop": s})
    return rules


def pick_per_day(items, key, k=PICK_K):
    """At most k items per date, best `key` first (key uses information known before entry)."""
    by = {}
    for it in items:
        by.setdefault(it["date"], []).append(it)
    out = []
    for d in sorted(by):
        out += sorted(by[d], key=key, reverse=True)[:k]
    return out


def halt_event_trade(h, rule):
    """h: {"sym","date","halt_m","resume_m","code","reg": bars}. Long the first 5m bar open at/after resumption when price rose
    >= 5% in the 15 minutes before the halt."""
    if h.get("code") != "LUDP":
        return None
    bars = h["reg"]
    done = [k for k, b in enumerate(bars) if b[0] + 5 <= h["halt_m"]]
    if len(done) < 4:
        return None
    k = done[-1]
    ref = bars[done[-4]][4]
    if not (PX_LO <= bars[k][4] <= PX_HI) or bars[k][4] / ref - 1.0 < HALT_RUNUP:
        return None
    start = -(-h["resume_m"] // 5) * 5
    cand = [j for j, b in enumerate(bars) if b[0] >= start and b[0] <= 930]
    if not cand:
        return None
    i = cand[0]
    hold = HALT_HOLDS[rule["hold"]]
    hs = 0.08 if rule["stop"] == "stop8" else None
    run = run_trade(bars, i, hold=hold, hstop=hs)
    pool = [j for j in range(4, len(bars) - hold) if 585 <= bars[j][0] <= 930]
    t = _trade(h["sym"], h["date"], bars, i, run, rule["id"], {"gap": None, "tag": None, "adv20": None})
    if pool:
        c = run_trade(bars, _ctrl_rng(h["sym"], h["date"], rule["id"]).choice(pool), hold=hold, hstop=hs)
        t["ctrl_net"] = c["gross"] - (2 * SLIP + fees_frac(c["ep"]))
    return t


def trades_for_rules(events, halts, rules=None):
    """{rule id: [trade dicts]} over the archived events/halts. Events are filtered by the rule's gap, band and tag, then at most
    3 per day are taken by premarket dollar volume (known at 09:25)."""
    rules = rules or build_rules()
    out = {}
    for r in rules:
        ts = []
        if r["fam"] == "orb":
            el = [e for e in events if e["gap"] >= r["gap"] and band_ok(e["adv20"], r["band"])
                  and (r["tag"] is None or (e.get("tag") or "none") == r["tag"])]
            for e in pick_per_day(el, key=lambda z: z["pm_dv"]):
                t = orb_trade(e, r)
                if t:
                    ts.append(t)
        else:
            el = sorted(halts, key=lambda z: (z["date"], z["resume_m"]))
            seen = {}
            for h in el:
                if seen.get(h["date"], 0) >= PICK_K:
                    continue
                t = halt_event_trade(h, r)
                if t:
                    seen[h["date"]] = seen.get(h["date"], 0) + 1
                    ts.append(t)
        ts.sort(key=lambda z: z["t"])
        out[r["id"]] = ts
    return out


# ------------------------------------------------------------------ catalyst tags (no LLM)
KEYWORDS = (("offering", ("public offering", "registered direct", "private placement", "underwritten", "securities purchase agreement",
                          "at-the-market", "at the market offering", "pricing of", "priced its", "warrants to purchase", "equity line")),
            ("fda", ("fda", "food and drug", "clinical", "phase 1", "phase 2", "phase 3", "phase i", "topline", "510(k)",
                     "breakthrough designation", "orphan drug", "pdufa", "ind application", "trial")),
            ("earnings", ("results of operations", "quarter ended", "fiscal year ended", "financial results", "reports first quarter",
                          "reports second quarter", "reports third quarter", "reports fourth quarter")),
            ("contract", ("contract", "purchase order", "awarded", "partnership", "collaboration", "license agreement", "supply agreement",
                          "definitive agreement", "merger", "acquisition", "acquire", "strategic", "agreement with")))


def classify_text(text, items=()):
    """Tag from 8-K item numbers plus press-release/8-K text keywords. Priority offering > fda > earnings > contract."""
    t = (text or "").lower()
    hits = {name: sum(t.count(w) for w in words) for name, words in KEYWORDS}
    if "3.02" in items:
        hits["offering"] += 2
    if "2.02" in items:
        hits["earnings"] += 2
    for name, _ in KEYWORDS:
        if hits[name] >= 1:
            return name
    return "other" if (t or items) else "none"


# ------------------------------------------------------------------ halts feed
def parse_nasdaq_halts(xml):
    """Nasdaq trade-halt RSS -> [{"sym","halt_date","halt_time","code","resume_date","resume_trade","raw"}] (tolerant regex parse)."""
    import re
    out = []
    for blk in re.findall(r"<item>(.*?)</item>", xml or "", flags=re.S):
        f = {k.lower(): v.strip() for k, v in re.findall(r"<ndaq:(\w+)>(.*?)</ndaq:\1>", blk, flags=re.S)}
        sym = f.get("issuesymbol")
        if not sym:
            continue
        out.append({"sym": sym.upper(), "halt_date": f.get("haltdate", ""), "halt_time": f.get("halttime", ""),
                    "code": f.get("reasoncode", ""), "resume_date": f.get("resumptiondate", ""),
                    "resume_trade": f.get("resumptiontradetime", ""), "market": f.get("market", ""), "raw": f})
    return out


def hhmm(s):
    """'HH:MM:SS' -> minute of day, or None."""
    try:
        h, m = s.strip().split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def us_date(s):
    """'MM/DD/YYYY' -> 'YYYY-MM-DD' or None."""
    try:
        m, d, y = s.strip().split("/")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except (ValueError, AttributeError):
        return None


# ------------------------------------------------------------------ evaluation
def month_folds(trades):
    """Rolling calendar-month folds of the net mean (stability check): [{'month','n','mean','mean_2x'}]."""
    by = {}
    for t in trades:
        by.setdefault(t["date"][:7], []).append(t)
    return [{"month": m, "n": len(v), "mean": ss.mean([t["net"] for t in v]), "mean_2x": ss.mean([t["net"] - t["cost"] for t in v])}
            for m, v in sorted(by.items())]


def _ctrl_mean(trades):
    v = [t["ctrl_net"] for t in trades if t.get("ctrl_net") is not None]
    return ss.mean(v)


def evaluate_family(trades_by_rule, now, bounds=None):
    """Stage-0 gate on TRAIN only (x >= 0.2, vol-to-cost, placebo, all-win ceiling), then validation/test only once their window has
    closed (`now` past the split end). Holm over the gate survivors when all splits are closed. Returns a summary dict."""
    b = bounds or BOUNDS
    t0, t1 = b["train"]
    train_days = (min(now, t1) - t0) / 86400.0
    rows, dropped = [], []
    for rid, trades in trades_by_rule.items():
        tr = ss.in_split(trades, t0, t1)
        ok, info = ss.gate(tr, {"size": SIZE}, CFG, train_days)
        info = dict(info, id=rid, control_mean_train=_ctrl_mean(tr), folds_month=month_folds(tr))
        if not ok:
            dropped.append(info)
            continue
        row = {"id": rid, "gate": info, "status": "pending"}
        if now >= b["test"][1]:
            row.update(ss.evaluate(trades, {"size": SIZE}, b), status="ok")
            va = ss.in_split(trades, *b["validation"])
            row["extra_criteria"] = {"val_beats_control": (ss.mean([t["net"] for t in va]) or 0) > (_ctrl_mean(va) or 0)}
        elif now >= b["validation"][1]:
            row["validation"] = ss.split_metrics(trades, 1.0 / PICK_K, *b["validation"], with_p=True)
            row["status"] = "validation_only"
        rows.append(row)
    fam = None
    ev = [r for r in rows if r["status"] == "ok"]
    if ev:
        fam = ss.judge_family(rows, CFG)
    best = sorted(dropped + [r["gate"] for r in rows], key=lambda z: -(z.get("x") or -9))[:5]
    return {"n_rules": len(trades_by_rule), "gate_survivors": len(rows), "passed": [r["id"] for r in rows if r.get("passed")],
            "survivors": rows, "family": fam, "top_train_x": best,
            "dropped_reasons": _count([" ".join(d.get("reason", "?").split(" ")[:3]) for d in dropped]),
            "train_days": round(train_days, 1), "now": now}


def _count(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def trailing_stats(trades):
    """n, mean, sd, s = mean/sd and x = N*s^2 per 30 days for a trade list spanning its own date range (report helper)."""
    if len(trades) < 2:
        return {"n": len(trades)}
    nets = [t["net"] for t in trades]
    m, s = sum(nets) / len(nets), ss.sd(nets)
    days = max(1.0, (max(t["t"] for t in trades) - min(t["t"] for t in trades)) / 86400.0)
    sr = m / s if s else 0.0
    return {"n": len(trades), "mean": m, "sd": s, "x_per_month": len(trades) / days * 30 * sr * abs(sr)}
