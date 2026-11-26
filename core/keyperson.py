"""Key-person events (CEO / founder / chair change in an 8-K Item 5.02) on a point-in-time S&P 500. Pure functions, no network.
Spec: research/studies/protocol_keyperson_20261126.md (locked before any price of this study was pulled).

Trades are dicts in the core.sweep_engine format (t, te, x, sym, side, gross, cost, fund, net, mfe, mae, reason) so the sweep gate
(core.sweep_stats.gate) and pass criteria (evaluate / judge_family) apply unchanged. Daily bars: entry at the open of the first
session whose 09:30 ET open is after the SEC acceptance time, exit at the open `hold` sessions later.
"""
import bisect
import hashlib
import html
import json
import os
import random
import re

from core import factory_us_pit as fu
from core import sweep_stats as ss
from core.forced_flow import corr, stats   # noqa: F401  (re-exported: same n/mean/sd/s/N/x arithmetic as the other event studies)

SEED = 20261126
PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "studies", "keyperson_prompt.txt")
with open(PROMPT_PATH, "rb") as _f:
    _raw = _f.read()
SYSTEM = _raw.decode("utf-8")
PROMPT_SHA256 = hashlib.sha256(_raw).hexdigest()

BOUNDS_DAYS = {"train": ("2017-01-01", "2020-01-01"), "validation": ("2020-01-01", "2023-01-01"), "test": ("2023-01-01", "2026-10-01")}
BOUNDS = {k: (fu.bound_ts(a), fu.bound_ts(b)) for k, (a, b) in BOUNDS_DAYS.items()}
START, END = BOUNDS["train"][0], BOUNDS["test"][1]
POST_CUTOFF_DAY = "2026-01-01"      # reported slice: filings the model cannot have memorised if its training data ends before 2026
POST_CUTOFF_TS = fu.bound_ts(POST_CUTOFF_DAY)


def split_of(ts):
    for k, (a, b) in BOUNDS.items():
        if a <= ts < b:
            return k
    return None


def months_of(split):
    a, b = BOUNDS[split]
    return (b - a) / 86400 / 30.4375


MONTHS = (END - START) / 86400 / 30.4375
HOLDS = (1, 5, 20)
BASES = ("raw", "adj")
CLASSES = ("abrupt", "planned", "return", "interim")
JUDGED = (("abrupt", -1), ("return", 1))        # the owner's two directions; every other class/side is descriptive
COST_LONG = 0.0010            # round trip, fractional shares of S&P 500 names, 0.05% a side at the open
COST_SHORT = 0.0020           # round trip, stock CFD spread on an event day (assumption, labelled in the protocol)
SHORT_FIN_YEAR = 0.05         # CFD financing / borrow, charged per session held
SPY_LEG = 0.0004              # round trip on the SPY leg of the market-adjusted basis
DEDUPE_DAYS = 30
CTRL_N = 5
CTRL_EXCL = 21                # control sessions stay more than this many sessions from any of the ticker's own 5.02 filings
CTRL_MIN = 3
SIZE = {"lev": 1, "k": 1}
CFG = {"alpha": 0.05, "account_usd": 147.0,
       "gate": {"min_train_trades": 20, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
       "pass": {"min_val_trades": 12, "min_test_trades": 10}}
CFG_STRICT = {"alpha": 0.05, "account_usd": 147.0,
              "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9, "min_vol_cost": 10, "min_x": 0.2},
              "pass": {"min_val_trades": 30, "min_test_trades": 20}}


# ---------------------------------------------------------------- filing text
def html_to_text(raw: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


_ITEM502 = re.compile(r"item\s*5\.02", re.I)
_NEXT_ITEM = re.compile(r"item\s*(5\.0[3-9]|[6-9]\.\d\d)|\bsignatures?\b", re.I)


def item_502_section(text: str, cap: int = 6000) -> str:
    """The Item 5.02 part of an 8-K main document: from the first 'Item 5.02' to the next other item or the signature, at most
    `cap` characters. '' when the text has no Item 5.02 heading."""
    m = _ITEM502.search(text)
    if not m:
        return ""
    rest = text[m.start():]
    nxt = _NEXT_ITEM.search(rest, 20)
    sec = rest[:nxt.start()] if nxt else rest
    return sec[:cap].strip()


PREFILTER = re.compile(r"chief\s+executive|\bCEO\b|\bfounders?\b|co-founders?|\bchair(?:man|woman|person)?\b|principal\s+executive\s+officer",
                       re.I)


def passes_prefilter(section: str) -> bool:
    """Locked deterministic pre-filter (decided before any label or price): the section names a CEO, founder or chair."""
    return bool(section) and bool(PREFILTER.search(section))


_SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|holdings?|group|the|n\.?v\.?|s\.?a\.?)\b\.?", re.I)
_STOP = set("""Chief Executive Officer Officers President Vice Chairman Chairwoman Chair Chairperson Board Directors Director Company Committee
Compensation Audit Inc Corp Corporation Securities Exchange Commission Act Item Certain Departure Election Appointment Compensatory
Arrangements Principal Financial Operating Senior General Counsel Secretary Treasurer Agreement Employment Separation Plan Annual
Meeting Shareholders Stockholders United States New York Delaware January February March April May June July August September October
November December Monday Tuesday Wednesday Thursday Friday Saturday Sunday Effective Immediately Interim Acting Founder Co-Founder
Nominating Governance Lead Independent Executive Section Form Report Registrant Current Date Earliest Event Reported Commission
File Number Identification Address Telephone Washington Nasdaq NYSE Stock Market Common Class Series Preferred Rule Regulation""".split())
_NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?){1,2}\b")
_HONOR = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.?\s+([A-Z][a-z]+)")


def redact(section: str, company_names=(), ticker: str = "") -> str:
    """Replace the issuer name, the ticker and person names with [COMPANY] / [PERSON] so the model cannot use what it remembers
    about the firm or the people. Heuristic (capitalised word runs without corporate title words); the protocol states it."""
    s = section
    for name in sorted({n for n in company_names if n}, key=len, reverse=True):
        core_name = _SUFFIX.sub(" ", name)
        core_name = re.sub(r"\s+", " ", re.sub(r"[^\w&\s-]", " ", core_name)).strip()
        for cand in {core_name, " ".join(core_name.split()[:2])}:
            if len(cand) >= 4:
                s = re.sub(r"\b" + re.escape(cand).replace(r"\ ", r"\s+") + r"\b", "[COMPANY]", s, flags=re.I)
    if ticker:
        s = re.sub(r"\b" + re.escape(ticker) + r"\b", "[COMPANY]", s)
    seen = set()

    def person(m):
        words = [w.rstrip(".") for w in re.split(r"\s+", m.group(0))]
        if any(w in _STOP for w in words):
            return m.group(0)
        seen.update(w for w in words if len(w) > 2)
        return "[PERSON]"

    s = _NAME.sub(person, s)
    s = _HONOR.sub(lambda m: (seen.add(m.group(1)), "[PERSON]")[1], s)
    for w in sorted(seen, key=len, reverse=True):
        s = re.sub(r"\b" + re.escape(w) + r"\b", "[PERSON]", s)
    return s


# ---------------------------------------------------------------- labels
FLAGS = ("immediate", "terminated", "misconduct", "planned", "interim", "returning")
ROLES = ("ceo", "founder", "chair", "none")
ACTIONS = ("departure", "appointment", "both", "none")


def parse_label(reply: str):
    """Model reply -> flags dict, or None for an unusable reply (counted as a failure, never as a class)."""
    m = re.search(r"\{.*\}", reply or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    if d.get("role") not in ROLES or d.get("action") not in ACTIONS:
        return None
    out = {"role": d["role"], "action": d["action"]}
    for k in FLAGS:
        v = d.get(k)
        if not isinstance(v, bool):
            return None
        out[k] = v
    if out["role"] == "none" or out["action"] == "none":
        out.update({k: False for k in FLAGS})
        out["role"] = out["action"] = "none"
    return out


def derive_class(f: dict) -> str:
    """Locked precedence over the flags (the order of the owner's list): abrupt > return > planned > interim > other.
    abrupt needs a departure; return needs an appointment; interim only when nothing above applies."""
    if not f or f.get("role") == "none" or f.get("action") == "none":
        return "other"
    dep = f["action"] in ("departure", "both")
    app = f["action"] in ("appointment", "both")
    if dep and (f["immediate"] or f["terminated"] or f["misconduct"]):
        return "abrupt"
    if app and f["returning"]:
        return "return"
    if dep and f["planned"]:
        return "planned"
    if f["interim"]:
        return "interim"
    return "other"


def user_message(section: str) -> str:
    return "ITEM 5.02 TEXT:\n" + section


def label_filing(section: str, chat) -> tuple:
    """One filing -> (flags or None, model_or_reason, raw reply). chat(system, user) -> (text, served); one retry on an empty reply."""
    text = served = ""
    for _ in range(2):
        text, served = chat(SYSTEM, user_message(section))
        if text:
            break
    return parse_label(text), served, (text or "")[:600]


# ---------------------------------------------------------------- SEC filings with their main document
def parse_filing_docs(cols: dict, since: str = "2016-09-01") -> list:
    fl = cols.get("form") or []
    n = len(fl)
    out = []
    for form, acc, fdate, items, accno, doc in zip(fl, cols.get("acceptanceDateTime") or [""] * n, cols.get("filingDate") or [""] * n,
                                                   cols.get("items") or [""] * n, cols.get("accessionNumber") or [""] * n,
                                                   cols.get("primaryDocument") or [""] * n):
        if form not in ("8-K", "8-K/A") or not acc or (fdate or "") < since:
            continue
        out.append({"form": form, "date": fdate, "ts": fu.accept_ts(acc), "accession": accno, "doc": doc,
                    "items": [x.strip() for x in (items or "").split(",") if x.strip()]})
    return out


def sec_filings_docs(cik: int, get_json, since: str = "2016-09-01") -> tuple:
    """-> (8-K and 8-K/A filings with item list and primary document, [issuer names]). get_json raises on failure."""
    d = get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    names = [d.get("name") or ""] + [x.get("name") or "" for x in (d.get("formerNames") or [])]
    f = d.get("filings") or {}
    out = parse_filing_docs(f.get("recent") or {}, since)
    for page in f.get("files") or []:
        if (page.get("filingTo") or "9999") < since or not page.get("name"):
            continue
        p = get_json(f"https://data.sec.gov/submissions/{page['name']}")
        out += parse_filing_docs(p.get("filings", {}).get("recent", p) if "filings" in p else p, since)
    seen, uniq = set(), []
    for x in sorted(out, key=lambda x: x["ts"]):
        k = x["accession"] or (x["form"], x["ts"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq, [n for n in names if n]


def doc_url(cik: int, accession: str, doc: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{doc}"


def candidates(filings: list, ticker: str, is_member) -> list:
    """8-K (not 8-K/A) filings with item 5.02, accepted inside the study window while `ticker` is an S&P 500 member."""
    return [x for x in filings if x["form"] == "8-K" and "5.02" in x["items"] and START <= x["ts"] < END
            and x["doc"] and is_member(ticker, fu.ny_date(x["ts"]))]


def dedupe(events: list) -> list:
    """One event per ticker inside DEDUPE_DAYS: the first (events: dicts with sym and ts)."""
    out, last = [], {}
    for e in sorted(events, key=lambda e: (e["ts"], e["sym"])):
        if e["sym"] in last and e["ts"] - last[e["sym"]] < DEDUPE_DAYS * 86400:
            continue
        last[e["sym"]] = e["ts"]
        out.append(e)
    return out


# ---------------------------------------------------------------- pricing on a panel (core.factory_us_pit.build_panel)
def entry_session(P: dict, ts: float) -> int:
    """First session whose 09:30 ET open is strictly after the acceptance time."""
    return fu.session_after(P, ts)


def leg(P: dict, sym: str, e: int, h: int, bench: str = fu.BENCH):
    """The long-side numbers of holding sym from the open of session e to the open of session e+h: stock and benchmark return
    (price change plus dividends with an ex-date in (e, e+h]) and the high / low of sessions e..e+h-1 relative to the entry open.
    None when a needed bar is missing."""
    n = P["n"]
    if e < 0 or e + h >= n:
        return None
    o, hi, lo, bo = P["o"].get(sym), P["h"].get(sym), P["l"].get(sym), P["o"].get(bench)
    if not o or not bo or o[e] is None or o[e + h] is None or bo[e] is None or bo[e + h] is None:
        return None
    dv = P["div"].get(sym, {})
    bd = P["div"].get(bench, {})
    highs = [hi[k] for k in range(e, e + h) if hi[k] is not None]
    lows = [lo[k] for k in range(e, e + h) if lo[k] is not None]
    r = o[e + h] / o[e] - 1 + sum(dv.get(k, 0.0) for k in range(e + 1, e + h + 1)) / o[e]
    rb = bo[e + h] / bo[e] - 1 + sum(bd.get(k, 0.0) for k in range(e + 1, e + h + 1)) / bo[e]
    return {"r": r, "rb": rb, "hi": (max(highs) / o[e] - 1) if highs else 0.0, "lo": (min(lows) / o[e] - 1) if lows else 0.0}


def trade_numbers(lg: dict, side: int, basis: str, h: int) -> dict:
    gross = side * (lg["r"] - (lg["rb"] if basis == "adj" else 0.0))
    cost = (COST_SHORT if side < 0 else COST_LONG) + (SPY_LEG if basis == "adj" else 0.0)
    fund = SHORT_FIN_YEAR * h / 252 if side < 0 else 0.0
    mfe = lg["hi"] if side > 0 else -lg["lo"]
    mae = -lg["lo"] if side > 0 else lg["hi"]
    return {"gross": gross, "cost": cost, "fund": fund, "net": gross - cost - fund, "mfe": max(mfe, 0.0), "mae": max(mae, 0.0)}


def control_sessions(P: dict, sym: str, ts: float, own_502_ts: list, split: str, rng: random.Random) -> list:
    """CTRL_N random entry sessions for the same ticker inside the event's split, with a bar, more than CTRL_EXCL sessions from
    any of the ticker's own 5.02 filings (the event's own included)."""
    a, b = BOUNDS[split]
    lo_i, hi_i = bisect.bisect_left(P["open_ts"], a), bisect.bisect_left(P["open_ts"], b)
    near = [entry_session(P, t) for t in own_502_ts]
    op = P["o"].get(sym) or []
    pool = [i for i in range(lo_i, hi_i) if i < len(op) and op[i] is not None
            and all(abs(i - k) > CTRL_EXCL for k in near)]
    return sorted(rng.sample(pool, min(CTRL_N, len(pool))))


def build_row(P: dict, ev: dict, own_502_ts: list):
    """One priced event row, or None (with the reason in the returned tuple) when a bar is missing.
    -> (row or None, reason)."""
    sym, ts = ev["sym"], ev["ts"]
    if sym not in P["o"]:
        return None, "no_bars"
    e = entry_session(P, ts)
    if e >= P["n"]:
        return None, "no_entry_session"
    legs = {}
    for h in HOLDS:
        lg = leg(P, sym, e, h)
        if lg is None:
            return None, "no_bar_for_hold_%d" % h
        legs[h] = lg
    sp = split_of(ts)
    rng = random.Random(f"{SEED}:{sym}:{int(ts)}")
    ctrl = {h: [] for h in HOLDS}
    for k in control_sessions(P, sym, ts, own_502_ts, sp, rng):
        for h in HOLDS:
            lg = leg(P, sym, k, h)
            if lg is not None:
                ctrl[h].append(lg)
    return {"sym": sym, "ts": ts, "acc": ev.get("acc"), "cls": ev["cls"], "split": sp, "misconduct": bool(ev.get("misconduct")),
            "post_cutoff": ts >= POST_CUTOFF_TS, "entry_day": P["days"][e], "entry_ts": P["open_ts"][e],
            "legs": {str(h): legs[h] for h in HOLDS}, "ctrl": {str(h): ctrl[h] for h in HOLDS}}, "ok"


# ---------------------------------------------------------------- rules and evaluation
def rule_id(cls, side, hold, basis):
    return f"{cls}|{'long' if side > 0 else 'short'}|h{hold}|{basis}"


def judged_rules():
    return [(rule_id(c, s, h, b), c, s, h, b) for c, s in JUDGED for h in HOLDS for b in BASES]


def trades_of(rows, cls, side, hold, basis):
    out = []
    for r in rows:
        if r["cls"] != cls:
            continue
        t = trade_numbers(r["legs"][str(hold)], side, basis, hold)
        cs = [trade_numbers(c, side, basis, hold)["net"] for c in r["ctrl"][str(hold)]]
        t.update({"sym": r["sym"], "side": side, "t": r["ts"], "te": r["entry_ts"], "x": r["entry_ts"] + hold * 86400, "ep": 0.0, "xp": 0.0,
                  "reason": "time", "nid": r["acc"], "ctrl_net": sum(cs) / len(cs) if len(cs) >= CTRL_MIN else None})
        out.append(t)
    return sorted(out, key=lambda t: t["t"])


def ctrl_mean(trades):
    return ss.mean([t["ctrl_net"] for t in trades if t.get("ctrl_net") is not None])


def placebo_mean(trades):
    return ss.mean([-t["gross"] - t["cost"] + t["fund"] for t in trades])


def split_stats(trades):
    return {k: stats([t["net"] for t in ss.in_split(trades, *BOUNDS[k])], months_of(k)) for k in BOUNDS}


def evaluate_rules(rows, cfg=None):
    """Stage 0 on train only, then the validation / test criteria for the survivors. -> (table by rule id, evaluated rows)."""
    cfg = cfg or CFG
    train_days = (BOUNDS["train"][1] - BOUNDS["train"][0]) / 86400
    table, evaluated = {}, []
    for rid, cls, side, h, basis in judged_rules():
        tr_all = trades_of(rows, cls, side, h, basis)
        tr = ss.in_split(tr_all, *BOUNDS["train"])
        ok, info = ss.gate(tr, {"size": SIZE}, cfg, train_days)
        cm = ctrl_mean(tr)
        info = dict(info, id=rid, control_mean_train=cm)
        if ok and cm is not None and (info["train_mean"] or 0) <= cm:
            ok, info["reason"] = False, "train net mean not above the random-control mean"
        table[rid] = {"gate": info, "ok": ok, "stats_all": stats([t["net"] for t in tr_all], MONTHS), "stats_by_split": split_stats(tr_all),
                      "control_mean_by_split": {k: ctrl_mean(ss.in_split(tr_all, *BOUNDS[k])) for k in BOUNDS},
                      "placebo_mean_by_split": {k: placebo_mean(ss.in_split(tr_all, *BOUNDS[k])) for k in BOUNDS}}
        if ok:
            r = {"id": rid, "gate": info, "status": "ok", "lev": SIZE["lev"], **ss.evaluate(tr_all, {"size": SIZE}, BOUNDS)}
            va, te = ss.in_split(tr_all, *BOUNDS["validation"]), ss.in_split(tr_all, *BOUNDS["test"])
            cv, ct = ctrl_mean(va), ctrl_mean(te)
            r["extra_criteria"] = {"val_beats_control": (ss.mean([t["net"] for t in va]) or 0) > (cv if cv is not None else 9),
                                   "test_beats_control": (ss.mean([t["net"] for t in te]) or 0) > (ct if ct is not None else 9)}
            evaluated.append(r)
    fam = ss.judge_family(evaluated, cfg) if evaluated else {"holm_m": 0}
    return table, evaluated, fam


def descriptive_table(rows):
    """n, mean, sd, s, N a month, x, hit by class x side x hold x basis x split, with control and reversed-side placebo. Not judged
    (apart from the two judged directions, which also appear in evaluate_rules)."""
    out = {}
    for cls in CLASSES:
        for side in (-1, 1):
            for h in HOLDS:
                for b in BASES:
                    tr = trades_of(rows, cls, side, h, b)
                    out[rule_id(cls, side, h, b)] = {
                        "all": stats([t["net"] for t in tr], MONTHS), "by_split": split_stats(tr),
                        "control_mean_by_split": {k: ctrl_mean(ss.in_split(tr, *BOUNDS[k])) for k in BOUNDS},
                        "placebo_mean_by_split": {k: placebo_mean(ss.in_split(tr, *BOUNDS[k])) for k in BOUNDS},
                        "gross_mean_all": ss.mean([t["gross"] for t in tr])}
    return out


def count_table(events):
    """Event counts by class and split (and the misconduct / post-cutoff subsets). No returns."""
    out = {}
    for e in events:
        c = out.setdefault(e["cls"], {"train": 0, "validation": 0, "test": 0, "total": 0, "misconduct": 0, "post_cutoff": 0})
        c[e.get("split") or split_of(e["ts"]) or "test"] += 1
        c["total"] += 1
        c["misconduct"] += bool(e.get("misconduct"))
        c["post_cutoff"] += e["ts"] >= POST_CUTOFF_TS
    return out
