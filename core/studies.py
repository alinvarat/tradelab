"""Pure calculations for the studies locked in research/news_backtest/protocol_next.md.

(d) turn of month + placebo, (c) 12-1 momentum long/flat, (a) 8-K item filter (rows built by the runner from
news_backtest), (b) Form 4 open-market purchases from the SEC insider-transaction data sets, and the shared
pass rule. Network loaders live at the bottom and are not used in tests.
"""
import calendar
import csv
import io
import json
import random
import time
import zipfile

from . import news_backtest as nb

TOM_HOLD = 4                      # last session of the month + first three sessions of the next month
PLACEBO_SHIFT = (20, 60)          # sessions
DIFF_SHARE_CAP = 0.25             # pass rule (5)


def month_key(ts: int) -> str:
    return time.strftime("%Y-%m", time.gmtime(ts))


def add_months(key: str, k: int) -> str:
    y, m = int(key[:4]), int(key[5:7])
    m0 = y * 12 + (m - 1) + k
    return f"{m0 // 12:04d}-{m0 % 12 + 1:02d}"


def month_end_indices(bars: list) -> list:
    """Index of the last session of every month whose next session is already in the data
    (so the final, possibly unfinished month is never treated as ended)."""
    return [i for i in range(len(bars) - 1) if month_key(bars[i]["t"]) != month_key(bars[i + 1]["t"])]


def window_gross(bars: list, i: int, j: int) -> float | None:
    """Buy the open of session i, sell the close of session j."""
    if i < 0 or j >= len(bars) or j < i:
        return None
    o, c = bars[i].get("o"), bars[j].get("c")
    return c / o - 1 if o and c else None


# ------------------------------------------------------------------ (d) turn of month and placebo
def tom_rows(symbol: str, bars: list, placebo: bool = False) -> list:
    """One row per month end: enter the open of the last session, exit the close of the third session of the next
    month. Control: a random session of the same stock outside every turn-of-month window, same length,
    drawn with random.Random(f"{symbol}:{ts}"). Placebo: the event window is moved 20-60 sessions forward."""
    ends = month_end_indices(bars)
    tom = set()
    for i in ends:
        tom.update(range(i, i + TOM_HOLD))
    free = [k for k in range(len(bars) - TOM_HOLD + 1) if k not in tom]
    rows = []
    for i in ends:
        ts = bars[i]["t"]
        rng = random.Random(f"{symbol}:{ts}")
        if not free:
            break
        k = free[rng.randrange(len(free))]
        start = i
        if placebo:
            start = i + random.Random(f"placebo:{symbol}:{ts}").randint(*PLACEBO_SHIFT)
        g = window_gross(bars, start, start + TOM_HOLD - 1)
        c = window_gross(bars, k, k + TOM_HOLD - 1)
        if g is None or c is None:
            continue
        rows.append({"symbol": symbol, "ts": bars[start]["t"], "split": nb.split_of(bars[start]["t"]),
                     "horizon": TOM_HOLD, "gross": g, "ctrl_gross": c, "asset_class": "stock",
                     "ctrl_start_t": bars[k]["t"], "event_t": ts})
    return rows


# ------------------------------------------------------------------ (c) momentum 12-1
def parse_membership(text: str) -> dict:
    """ticker,start_date,end_date CSV -> {yahoo ticker: [(start, end or None)]}. A ticker can have several spells."""
    out: dict = {}
    for i, line in enumerate(text.strip().splitlines()):
        parts = [x.strip() for x in line.split(",")]
        if i == 0 or len(parts) < 2 or not parts[0]:
            continue
        end = parts[2] if len(parts) > 2 and parts[2] else None
        out.setdefault(parts[0].replace(".", "-"), []).append((parts[1], end))
    return out


def members_on(intervals: dict, day: str) -> set:
    """Members whose spell covers day (start <= day, and no end or day < end)."""
    return {t for t, spells in intervals.items() if any(a <= day and (b is None or day < b) for a, b in spells)}


def momentum_rows(bars_by_symbol: dict, top_frac: float = 0.1, min_names: int = 10, members=None) -> list:
    """Each month end m: score = close(end of m-1) / close(end of m-12) - 1. Hold the top decile equal weight from
    the next session's open to the close of the last session of m+1, flat otherwise. Control: the equal-weight
    basket of every stock that had a score that month, same entry and exit. Both pay a full round trip each month
    (the rule exits at month-end close and re-enters at the next open, so every month is a new position).
    members: optional {"YYYY-MM-DD": set} or callable(day) -> set of point-in-time members; only they are eligible,
    and each row then records coverage = scored members / members."""
    ends = {s: {month_key(b[i]["t"]): i for i in month_end_indices(b)} for s, b in bars_by_symbol.items()}
    months = sorted(set().union(*[set(e) for e in ends.values()])) if ends else []
    rows = []
    for m in months:
        m1, m12, nxt = add_months(m, -1), add_months(m, -12), add_months(m, 1)
        scores, legs, entry_t = {}, {}, None
        eligible = None
        if members is not None:
            any_end = next((bars_by_symbol[s][e[m]]["t"] for s, e in ends.items() if m in e), None)
            if any_end is None:
                continue
            day = time.strftime("%Y-%m-%d", time.gmtime(any_end))
            eligible = members(day) if callable(members) else members.get(day, set())
        for s, e in ends.items():
            if eligible is not None and s not in eligible:
                continue
            if not all(k in e for k in (m, m1, m12, nxt)):
                continue
            b = bars_by_symbol[s]
            base = b[e[m12]]["c"]
            if not base:
                continue
            g = window_gross(b, e[m] + 1, e[nxt])
            if g is None:
                continue
            scores[s] = b[e[m1]]["c"] / base - 1
            legs[s] = g
            t = b[e[m] + 1]["t"]
            entry_t = t if entry_t is None else min(entry_t, t)
        if len(scores) < min_names:
            continue
        k = max(1, int(len(scores) * top_frac))
        top = sorted(scores, key=lambda s: (-scores[s], s))[:k]
        rows.append({"symbol": "MOM12-1", "month": nxt, "ts": entry_t, "split": nb.split_of(entry_t),
                     "horizon": "1m", "gross": sum(legs[s] for s in top) / k,
                     "ctrl_gross": sum(legs.values()) / len(legs), "asset_class": "stock",
                     "basket": len(legs), "top": top,
                     "coverage": (len(legs) / len(eligible)) if eligible else None})
    return rows


# ------------------------------------------------------------------ (a) 8-K items
ITEMS = ("2.02", "1.01", "5.02")


def item_tags(items: list) -> list:
    """The locked items a filing lists; an 8-K with several counts under each of them."""
    return [i for i in ITEMS if i in items]


# ------------------------------------------------------------------ (b) Form 4 purchases
def parse_filing_date(s: str) -> str | None:
    s = (s or "").strip()
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%b-%y"):
        try:
            return time.strftime("%Y-%m-%d", time.strptime(s.title() if "%b" in fmt else s, fmt))
        except ValueError:
            continue
    return None


def conservative_ts(filing_date: str) -> int:
    """No acceptance time: Section 16 forms accepted up to 22:00 ET keep that day's date, i.e. at most 03:00 UTC
    of the next day. 04:00 UTC next day is never earlier than the real acceptance, so entry is never early."""
    return calendar.timegm(time.strptime(filing_date, "%Y-%m-%d")) + 86400 + 4 * 3600


def _float(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def insider_purchases(submissions: list, owners: list, trans: list, symbols: set,
                      min_value: float = 50_000.0) -> list:
    """Rows of the SEC insider-transaction data set tables (dicts by column name) -> one event per Form 4
    accession: an officer or director bought on the open market (code P, acquired) at least min_value USD in
    total. Amendments (4/A), grants (A), exercises (M) and gifts (G) are excluded."""
    rel = {}
    for o in owners:
        r = (o.get("RPTOWNER_RELATIONSHIP") or "").lower()
        if "director" in r or "officer" in r:
            rel[o["ACCESSION_NUMBER"]] = True
    value: dict = {}
    for t in trans:
        if (t.get("TRANS_CODE") or "").strip().upper() != "P":
            continue
        if (t.get("TRANS_ACQUIRED_DISP_CD") or "A").strip().upper() != "A":
            continue
        acc = t["ACCESSION_NUMBER"]
        value[acc] = value.get(acc, 0.0) + _float(t.get("TRANS_SHARES")) * _float(t.get("TRANS_PRICEPERSHARE"))
    out = []
    for s in submissions:
        acc = s.get("ACCESSION_NUMBER")
        sym = (s.get("ISSUERTRADINGSYMBOL") or "").strip().upper().replace(".", "-")
        if (s.get("DOCUMENT_TYPE") or "").strip() != "4" or sym not in symbols:
            continue
        if not rel.get(acc) or value.get(acc, 0.0) < min_value:
            continue
        day = parse_filing_date(s.get("FILING_DATE"))
        if day:
            out.append({"symbol": sym, "accession": acc, "date": day, "value": value[acc]})
    return out


# ------------------------------------------------------------------ DeepSeek reads earnings releases
LLM_SYSTEM = ("You are an equity analyst. You will read one company's earnings press release, published just now. "
              "Decide whether a trader should be long or short this stock for the next 1-5 trading sessions, "
              "or skip it. Use only the text. Reply with JSON only: "
              '{"direction": "long"|"short"|"skip", "confidence": 0-100, "reason": "<one sentence>"}')
LLM_FIRST_DAY = "2026-10-20"
LLM_SYSTEM_8K = ("You are an equity analyst. You will read one company's 8-K current report (a material event filing), "
                 "published just now. Decide whether a trader should be long or short this stock for the next 1-5 "
                 "trading sessions, or skip it when the filing is routine or unclear. Use only the text. Reply with "
                 'JSON only: {"direction": "long"|"short"|"skip", "confidence": 0-100, "reason": "<one sentence>"}')


def html_text(raw: str, limit: int = 15000) -> str:
    """Visible text of an HTML/XBRL document, whitespace collapsed."""
    import html as _html
    import re
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", raw)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = _html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()[:limit]


def pick_exhibit(names: list, primary: str) -> str:
    """The press release of an 8-K: the first EX-99 style .htm file, else the primary document."""
    import re
    hits = [n for n in names if re.search(r"(?i)ex-?99|exhibit99|ex991|dex99", n) and n.lower().endswith((".htm", ".html"))]
    return sorted(hits)[0] if hits else primary


def parse_direction(text: str) -> dict:
    """Model reply -> {'direction','confidence','reason'}; anything unparseable is a skip."""
    import re
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except ValueError:
        d = {}
    direction = str(d.get("direction", "skip")).strip().lower()
    if direction not in ("long", "short", "skip"):
        direction = "skip"
    try:
        conf = max(0, min(100, int(float(d.get("confidence", 0)))))
    except (TypeError, ValueError):
        conf = 0
    return {"direction": direction, "confidence": conf, "reason": str(d.get("reason", ""))[:300]}


def sign_of(direction: str) -> int:
    return {"long": 1, "short": -1}.get(direction, 0)


def signed_net(gross: float, sign: int, cost_mult: float = 1.0, cost_side: float | None = None) -> float:
    """Net of a long (sign 1) or short (sign -1) held from open to close; the short gains -gross.
    cost_side overrides the default stock cost per side (liquidity tiers)."""
    if not sign:
        return 0.0
    if cost_side is None:
        return nb.net_return(sign * gross, "stock", cost_mult)
    return (1 + sign * gross) * (1 - cost_side * cost_mult) ** 2 - 1


LIQ_TIERS = ((100e6, 0.0009), (20e6, 0.0020), (5e6, 0.0040))


def liquidity_cost(bars: list, entry_index: int, days: int = 20, min_price: float = 3.0) -> float | None:
    """Per-side cost from the median dollar volume of the sessions before entry; None = excluded (too thin/cheap)."""
    prev = bars[max(0, entry_index - days):entry_index]
    if len(prev) < days // 2 or not prev[-1].get("c") or prev[-1]["c"] < min_price:
        return None
    dv = sorted((b.get("c") or 0) * (b.get("v") or 0) for b in prev)
    med = dv[len(dv) // 2]
    for floor, cost in LIQ_TIERS:
        if med >= floor:
            return cost
    return None


def parse_form_idx(text: str, forms=("8-K",)) -> list:
    """EDGAR daily form.idx -> [{'form','cik','date','accession'}] for the requested form types."""
    import re
    out = []
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+.*?\s(\d{1,10})\s+(\d{8}|\d{4}-\d{2}-\d{2})\s+(edgar/\S+\.txt)\s*$", line)
        if not m or m.group(1) not in forms:
            continue
        acc = m.group(4).rsplit("/", 1)[-1][:-4]
        d = m.group(3)
        out.append({"form": m.group(1), "cik": int(m.group(2)), "accession": acc,
                    "date": d if "-" in d else f"{d[:4]}-{d[4:6]}-{d[6:]}"})
    return out


def daily_book(rows: list, horizon: int = 1) -> list:
    """[(entry_t, mean net of that session's non-skip trades)] in time order; rows need 'entry_t'."""
    import collections
    by = collections.defaultdict(list)
    for r in rows:
        if r["horizon"] == horizon and r["direction"] != "skip":
            by[r["entry_t"]].append(signed_net(r["gross"], sign_of(r["direction"]), 1.0, r.get("cost_side")))
    return [(t, sum(v) / len(v)) for t, v in sorted(by.items())]


def leverage_path(returns: list, lev: float) -> dict:
    e, peak, dd = 1.0, 1.0, 0.0
    for x in returns:
        e *= max(1 + lev * x, 0.0)
        peak = max(peak, e)
        dd = min(dd, e / peak - 1 if peak else -1.0)
    return {"end_equity": e, "worst_drawdown": dd}


def llm_summary(rows: list, horizon: int, min_conf: int = 0) -> dict:
    """rows: {'symbol','ts','horizon','gross','direction','confidence','rand_sign'} -> protocol statistics."""
    import random as _r
    sub = [r for r in rows if r["horizon"] == horizon]
    taken = [r for r in sub if r["direction"] != "skip" and r["confidence"] >= min_conf]
    if not taken:
        return {"n_events": len(sub), "n": 0}
    mine = [signed_net(r["gross"], sign_of(r["direction"]), 1.0, r.get("cost_side")) for r in taken]
    rand = [signed_net(r["gross"], r["rand_sign"], 1.0, r.get("cost_side")) for r in taken]
    diff = [a - b for a, b in zip(mine, rand)]
    keys = [nb.cluster_key(r) for r in taken]
    rng = _r.Random(20261124)
    k = len(taken)
    return {"n_events": len(sub), "n": k, "skip_rate": 1 - k / len(sub),
            "hit": sum(1 for r in taken if sign_of(r["direction"]) * r["gross"] > 0) / k,
            "mean_gross_signed": sum(sign_of(r["direction"]) * r["gross"] for r in taken) / k,
            "mean_net": sum(mine) / k, "mean_net_2x": sum(signed_net(r["gross"], sign_of(r["direction"]), 2.0,
                                                                     r.get("cost_side")) for r in taken) / k,
            "mean_random_dir": sum(rand) / k, "mean_diff": sum(diff) / k,
            "mean_always_long": sum(signed_net(r["gross"], 1, 1.0, r.get("cost_side")) for r in sub) / len(sub),
            "p_diff_block": nb.block_bootstrap_p(diff, keys, rng), "p_net_block": nb.block_bootstrap_p(mine, keys, rng)}


LLM_FORWARD_FIRST_DAY = "2026-12-01"
LLM_FORWARD_MIN_TRADES = 600


def llm_forward_verdict(rows: list) -> str:
    """protocol_llm_earnings_forward.md: H5 primary, decided once at >= 600 non-skip trades."""
    h5, h3 = llm_summary(rows, 5), llm_summary(rows, 3)
    if h5.get("n", 0) < LLM_FORWARD_MIN_TRADES:
        return f"collecting ({h5.get('n', 0)}/{LLM_FORWARD_MIN_TRADES} trades)"
    ok = (h5["mean_net"] > 0 and h5["p_net_block"] < 0.05 and h5["mean_net_2x"] > 0 and h3.get("mean_net", 0) > 0
          and h5["mean_diff"] > 0 and h5["p_diff_block"] < 0.05)
    return "edge" if ok else "no edge shown"


def llm_verdict(rows: list) -> str:
    h1, h3 = llm_summary(rows, 1), llm_summary(rows, 3)
    if h1.get("n", 0) < 60:
        return "too few, keep collecting"
    ok = (h1["mean_net"] > 0 and h3.get("mean_net", 0) > 0 and h1["p_diff_block"] < 0.05 and h1["mean_net_2x"] > 0)
    return "edge candidate" if ok else "no edge shown"


# ------------------------------------------------------------------ pass rule
def verdict(rows: list, group=None) -> dict:
    """protocol_next.md pass rule. (1) block p_diff < 0.05 on train+validation, (2) mean diff > 0 in train and in
    validation, (3) mean diff > 0 in test, (4) mean net > 0 at 2x cost (all rows), (5) no single group (symbol,
    or month for momentum) holds more than 25% of the summed paired difference."""
    by = {sp: [r for r in rows if r["split"] == sp] for sp in ("train", "validation", "test")}
    tv = by["train"] + by["validation"]
    out = {"all": nb.summarize(rows), "train_validation": nb.summarize(tv),
           **{sp: nb.summarize(v) for sp, v in by.items()}, "all_2x": nb.summarize(rows, cost_mult=2.0)}
    con = nb.contributions(rows, key=group)
    total = sum(c["sum_diff"] for c in con)
    top_share = max((c["sum_diff"] / total for c in con), default=None) if total > 0 else None
    checks = {
        "1_block_p_trainval_lt_0.05": out["train_validation"].get("p_diff_block", 1.0) < 0.05,
        "2_diff_pos_train_and_validation": all(out[sp].get("mean_diff", 0) > 0 for sp in ("train", "validation")),
        "3_diff_pos_test": out["test"].get("mean_diff", 0) > 0,
        "4_net_pos_at_2x_cost": out["all_2x"].get("mean_net", 0) > 0,
        "5_no_group_over_25pct": top_share is not None and top_share <= DIFF_SHARE_CAP,
    }
    out.update(checks=checks, top_share=top_share, top_groups=con[:5],
               passed=all(checks.values()), enough=min(len(v) for v in by.values()) > 0 and len(rows) >= 300)
    return out


# ------------------------------------------------------------------ network (not used in tests)
FORM345_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{y}q{q}_form345.zip"


def read_tsv(zf: zipfile.ZipFile, name: str, keep: tuple) -> list:
    """Rows of one TSV inside the zip, only the columns in keep (missing columns raise, so a format change is
    loud, not a silent empty study)."""
    path = next((n for n in zf.namelist() if n.upper().endswith(name.upper())), None)
    if not path:
        raise KeyError(f"{name} not in {zf.namelist()}")
    with zf.open(path) as f:
        r = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t")
        missing = [k for k in keep if k not in (r.fieldnames or [])]
        if missing:
            raise KeyError(f"{name} lacks {missing}; has {r.fieldnames}")
        return [{k: row.get(k) for k in keep} for row in r]


def form345_quarter(year: int, q: int) -> zipfile.ZipFile | None:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(FORM345_URL.format(y=year, q=q), headers={"User-Agent": nb.SEC_UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    time.sleep(0.15)
    return zipfile.ZipFile(io.BytesIO(body))
