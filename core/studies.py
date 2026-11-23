"""Pure calculations for the studies locked in research/news_backtest/protocol_next.md.

(d) turn of month + placebo, (c) 12-1 momentum long/flat, (a) 8-K item filter (rows built by the runner from
news_backtest), (b) Form 4 open-market purchases from the SEC insider-transaction data sets, and the shared
pass rule. Network loaders live at the bottom and are not used in tests.
"""
import calendar
import csv
import io
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
def momentum_rows(bars_by_symbol: dict, top_frac: float = 0.1, min_names: int = 10) -> list:
    """Each month end m: score = close(end of m-1) / close(end of m-12) - 1. Hold the top decile equal weight from
    the next session's open to the close of the last session of m+1, flat otherwise. Control: the equal-weight
    basket of every stock that had a score that month, same entry and exit. Both pay a full round trip each month
    (the rule exits at month-end close and re-enters at the next open, so every month is a new position)."""
    ends = {s: {month_key(b[i]["t"]): i for i in month_end_indices(b)} for s, b in bars_by_symbol.items()}
    months = sorted(set().union(*[set(e) for e in ends.values()])) if ends else []
    rows = []
    for m in months:
        m1, m12, nxt = add_months(m, -1), add_months(m, -12), add_months(m, 1)
        scores, legs, entry_t = {}, {}, None
        for s, e in ends.items():
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
                     "basket": len(legs), "top": top})
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
