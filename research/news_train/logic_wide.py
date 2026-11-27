"""CMP addendum 3 (protocol_cmp_addendum3_20261128.md): the forward stock-wide arm. Pure logic, no network, no clock, stdlib only.

Universe: every plain 8-K the pod's EDGAR feed (`sec_8k` rows on data/news-ingest) saw, whose issuer is not a point-in-time S&P 500 member
(that universe is round 2's and stays there), with a stock_items code or none listed. A UTC day is selected once, after it has closed:
the day's candidates are ranked by sha256(seed:key) and admitted in that order until `cap_per_day` pass the checks. Selection never reads a decision or an outcome."""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_PATH = os.path.join(HERE, "params_cmp_a3.json")
TITLE = re.compile(r"^([\w/\-.]+)\s+-\s+(.*?)\s+\((\d{10})\)")


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return json.load(f)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def parse_title(title):
    """EDGAR atom title 'FORM - Company (0001234567) (Filer)' -> (form, company, cik) or None."""
    m = TITLE.match(title or "")
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def day_of(ts):
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def day_end(day):
    import datetime
    return int(datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp()) + 86400


def pool(joined, start_ts, p):
    """Pod rows (ingest_branch.join) of the EDGAR source that are plain 8-Ks with a CIK, published at or after start_ts.
    -> [{key, acc, cik, t_pub, t_seen, day}] sorted by (t_pub, key)."""
    out = []
    for (src, key), d in joined.items():
        if src != p["source"] or not str(key).startswith("sec:") or not _num(d.get("t_pub")) or not _num(d.get("t_seen")) or d["t_pub"] < start_ts:
            continue
        pt = parse_title(d.get("title"))
        if not pt or pt[0] != p["form"]:
            continue
        out.append({"key": key, "acc": key[4:], "cik": pt[2], "t_pub": d["t_pub"], "t_seen": d["t_seen"], "day": day_of(d["t_pub"])})
    return sorted(out, key=lambda r: (r["t_pub"], r["key"]))


def rank(seed, key):
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def day_ready(day, now, p):
    """A day is selected once, p.day_close_wait_s after it has closed (the pod publishes its log in parts)."""
    return now >= day_end(day) + p["day_close_wait_s"]


def select_day(rows, p, check):
    """rows: one day's pool. check(row) -> (item or None, reason). Rows are tried in sha order until cap_per_day items are admitted or
    max_examine_per_day rows were tried. A check that raises counts as an error and is not retried. -> (items, stats)."""
    items, rejected, examined, errors = [], {}, 0, 0
    for r in sorted(rows, key=lambda r: rank(p["seed"], r["key"])):
        if len(items) >= p["cap_per_day"] or examined >= p["max_examine_per_day"]:
            break
        examined += 1
        try:
            it, why = check(r)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if it:
            items.append(it)
        else:
            rejected[why] = rejected.get(why, 0) + 1
    return items, {"pool": len(rows), "examined": examined, "admitted": len(items), "errors": errors, "rejected": rejected}


def pick_ticker(tickers):
    """One ticker per CIK for the price lookup: shortest, then alphabetical."""
    return sorted(tickers, key=lambda s: (len(s), s))[0] if tickers else None


def in_spell(spells, tickers, ny_day):
    """True when any ticker of the issuer is an S&P 500 member on ny_day (spells: {ticker: [(from, to or None)]})."""
    return any(a <= ny_day and (b is None or ny_day < b) for s in tickers for a, b in spells.get(s, []))
