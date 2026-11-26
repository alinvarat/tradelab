"""Key-person 8-K Item 5.02 events (protocol_keyperson_20261126.md). GitHub Actions only (workflow keyperson.yml).

    python research/studies/keyperson.py <out_dir> events [previous_labels.jsonl]   # stage A: filings, Haiku labels, counts; NO prices
    python research/studies/keyperson.py <out_dir> run <frozen events.json>         # stage B: price the frozen events once, judge

Stage A writes labels.jsonl (every labelled filing), events.json (frozen class events) and events_summary.json.
Stage B writes rows.jsonl.gz and summary.json.
"""
import calendar
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import ai_news                       # noqa: E402
from core import factory_us_pit as fu          # noqa: E402
from core import keyperson as kp               # noqa: E402
from core import news_backtest as nb           # noqa: E402
from core import studies as st                 # noqa: E402
from core import sweep_stats as ss             # noqa: E402

SP500_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
UA = {"User-Agent": "Mozilla/5.0 (TradeLab research)"}


def log(*a):
    print(*a, flush=True)


def sec_get_raw(url, tries=5):
    err = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": nb.SEC_UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
            time.sleep(0.15)
            return body
        except urllib.error.HTTPError as e:
            err = e
            if e.code == 404:
                break
            time.sleep(3 * (k + 1))
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"SEC fetch failed {url}: {err}")


def sec_get_json(url):
    return json.loads(sec_get_raw(url))


def load_spells():
    with urllib.request.urlopen(urllib.request.Request(SP500_URL, headers={"User-Agent": "TradeLab research"}), timeout=60) as r:
        return st.parse_membership(r.read().decode())


def stage_a(out_dir, prev_path=""):
    t0 = time.time()
    spells = load_spells()
    lo_day, hi_day = "2016-11-01", "2026-10-01"
    names = sorted(t for t, sp in spells.items() if any(a < hi_day and (b is None or b >= lo_day) for a, b in sp))
    tick = nb.sec_company_tickers()
    ciks = {s: tick[s] for s in names if s in tick}
    no_cik = [s for s in names if s not in tick]

    def span_days(s):
        return sum(max(0, (date.fromisoformat(min(b or hi_day, hi_day)) - date.fromisoformat(max(a, lo_day))).days) for a, b in spells[s])
    keep, same_issuer = fu.one_per_issuer(ciks, {s: span_days(s) for s in ciks})
    log(f"S&P 500 tickers {len(names)}, with CIK {len(ciks)}, no CIK {len(no_cik)}, share classes dropped {len(same_issuer)}")

    def is_member(sym, day):
        return any(a <= day and (b is None or day < b) for a, b in spells.get(sym, []))

    prev = {}
    if prev_path and os.path.exists(prev_path):
        for line in open(prev_path):
            r = json.loads(line)
            if r.get("prompt_sha256") == kp.PROMPT_SHA256 and r.get("flags") is not None:
                prev[r["accession"]] = r
    log("previous labels reused:", len(prev))

    cand, own502, issuer_names, sec_failed = [], {}, {}, []
    by_year = {}
    for k, (s, c) in enumerate(sorted((s, ciks[s]) for s in keep)):
        try:
            filings, nm = kp.sec_filings_docs(c, sec_get_json)
        except Exception as e:  # noqa: BLE001
            sec_failed.append(s)
            log("  sec failed", s, e)
            continue
        issuer_names[s] = nm
        own502[s] = sorted(x["ts"] for x in filings if "5.02" in x["items"])
        for x in kp.candidates(filings, s, is_member):
            cand.append(dict(x, sym=s, cik=c))
            by_year[x["date"][:4]] = by_year.get(x["date"][:4], 0) + 1
        if k % 100 == 0:
            log(f"  sec {k}/{len(keep)} candidates {len(cand)}")
    log("5.02 candidates", len(cand), "by year", by_year)

    stats = {"candidates": len(cand), "reused_labels": 0, "doc_failed": 0, "no_section": 0, "prefilter_out": 0, "to_label": 0,
             "label_failed": 0, "stamp_hour_as_read": {}}
    for x in cand:
        h = datetime.fromtimestamp(x["ts"], fu.NY).strftime("%H")
        stats["stamp_hour_as_read"][h] = stats["stamp_hour_as_read"].get(h, 0) + 1
    work, labelled = [], {}
    for x in cand:
        if x["accession"] in prev:
            labelled[x["accession"]] = prev[x["accession"]]
            stats["reused_labels"] += 1
            continue
        try:
            raw = sec_get_raw(kp.doc_url(x["cik"], x["accession"], x["doc"])).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            stats["doc_failed"] += 1
            log("  doc failed", x["sym"], x["accession"], e)
            continue
        sec = kp.item_502_section(kp.html_to_text(raw))
        if not sec:
            stats["no_section"] += 1
            continue
        if not kp.passes_prefilter(sec):
            stats["prefilter_out"] += 1
            continue
        work.append((x, kp.redact(sec, issuer_names.get(x["sym"], []), x["sym"])))
    stats["to_label"] = len(work)
    log("to label", len(work), "stats", stats, "seconds", round(time.time() - t0))

    labels_path = os.path.join(out_dir, "labels.jsonl")
    lf = open(labels_path, "w")
    for r in labelled.values():
        lf.write(json.dumps(r, ensure_ascii=False) + "\n")

    def one(item):
        x, text = item
        flags, served, reply = kp.label_filing(text, lambda s_, u_: ai_news.chat(s_, u_, timeout=150, temperature=0))
        return {"accession": x["accession"], "sym": x["sym"], "ts": x["ts"], "form": x["form"], "flags": flags, "served": served,
                "reply": reply, "prompt_sha256": kp.PROMPT_SHA256, "cls": kp.derive_class(flags) if flags else None,
                "sample_text": text[:700] if zlib.crc32(x["accession"].encode()) % 25 == 0 else ""}

    t1 = time.time()
    with ThreadPoolExecutor(max(1, ai_news.CLAUDE_MAX_PARALLEL)) as ex:
        for k, r in enumerate(ex.map(one, work)):
            if r["flags"] is None:
                stats["label_failed"] += 1
            labelled[r["accession"]] = r
            lf.write(json.dumps(r, ensure_ascii=False) + "\n")
            lf.flush()
            if k % 50 == 0:
                log(f"  labelled {k + 1}/{len(work)} failed {stats['label_failed']} s/call {(time.time() - t1) / (k + 1):.1f} spend {ai_news.spend()}")
    lf.close()

    events = []
    for r in labelled.values():
        if r.get("flags") and r["cls"] and r["cls"] != "other":
            events.append({"sym": r["sym"], "ts": r["ts"], "acc": r["accession"], "cls": r["cls"], "role": r["flags"]["role"],
                           "misconduct": r["flags"]["misconduct"], "split": kp.split_of(r["ts"]),
                           "abrupt_and_return": bool(r["flags"]["returning"] and r["cls"] == "abrupt")})
    events = [e for e in kp.dedupe(events) if e["split"]]
    summary = {"stage": "A", "prompt_sha256": kp.PROMPT_SHA256, "stats": stats, "by_year": by_year, "sec_failed": sec_failed,
               "no_cik": len(no_cik), "same_issuer_dropped": same_issuer, "events": len(events), "counts": kp.count_table(events),
               "labelled_not_other": sum(1 for r in labelled.values() if r.get("cls") not in (None, "other")),
               "class_counts_before_dedupe": {c: sum(1 for r in labelled.values() if r.get("cls") == c) for c in (*kp.CLASSES, "other")},
               "abrupt_and_return_flag": sum(1 for e in events if e["abrupt_and_return"]),
               "months": round(kp.MONTHS, 2), "spend": ai_news.spend(), "seconds": round(time.time() - t0),
               "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(os.path.join(out_dir, "events.json"), "w") as f:
        json.dump({"events": events, "own502": own502, "summary": summary}, f)
    with open(os.path.join(out_dir, "events_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    log(json.dumps(summary, default=str)[:3000])


def yahoo(symbol, p1, p2, tries=4):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?period1={p1}&period2={p2}"
           "&interval=1d&events=div%2Csplit&includePrePost=false")
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                d = json.loads(r.read())["chart"]
            if d.get("error") or not d.get("result"):
                return [], {}, {}
            return fu.parse_chart(d["result"][0])
        except Exception as e:  # noqa: BLE001
            if k == tries - 1:
                log("  bars failed", symbol, e)
                return [], {}, {}
            time.sleep(2 * (k + 1))


def stage_b(out_dir, frozen):
    t0 = time.time()
    doc = json.load(open(frozen))
    events, own502 = doc["events"], doc["own502"]
    with open(os.path.join(out_dir, "events.json"), "w") as f:
        json.dump(doc, f)
    syms = sorted({e["sym"] for e in events})
    p1, p2 = calendar.timegm((2016, 1, 1, 0, 0, 0)), calendar.timegm((2026, 12, 31, 0, 0, 0))
    bars, divs, splits, missing = {}, {}, {}, []
    for s in [fu.BENCH] + syms:
        b, dv, sp = yahoo(s, p1, p2)
        if not b or not fu.daily_ok(b):
            missing.append(s)
            continue
        bars[s], divs[s], splits[s] = b, dv, sp
    if fu.BENCH not in bars:
        raise RuntimeError("SPY bars missing: void run")
    P = fu.build_panel(bars, divs, splits)
    rows, dropped = [], {}
    for e in events:
        r, why = kp.build_row(P, e, own502.get(e["sym"], []))
        if r is None:
            dropped[why] = dropped.get(why, 0) + 1
            dropped.setdefault("events_dropped_by_class", {})
            dropped["events_dropped_by_class"][e["cls"]] = dropped["events_dropped_by_class"].get(e["cls"], 0) + 1
            continue
        rows.append(r)
    log("rows", len(rows), "dropped", dropped, "missing bars", len(missing))
    with gzip.open(os.path.join(out_dir, "rows.jsonl.gz"), "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    table, evaluated, fam = kp.evaluate_rules(rows, kp.CFG)
    table_s, evaluated_s, fam_s = kp.evaluate_rules(rows, kp.CFG_STRICT)
    summary = {"stage": "B", "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "prompt_sha256": kp.PROMPT_SHA256,
               "events_frozen": len(events), "rows_priced": len(rows), "dropped": dropped, "tickers_without_bars": missing,
               "counts_priced": kp.count_table(rows), "months": {k: round(kp.months_of(k), 2) for k in kp.BOUNDS},
               "rules_tested": len(table), "event_gate": {"stage0_survivors": [r["id"] for r in evaluated], "holm": fam,
                                                         "passed": [r["id"] for r in evaluated if r.get("passed")],
                                                         "evaluated": [dict(ss.compact(r), criteria=r["criteria"]) for r in evaluated]},
               "sweep_strict_gate": {"stage0_survivors": [r["id"] for r in evaluated_s], "holm": fam_s,
                                     "passed": [r["id"] for r in evaluated_s if r.get("passed")]},
               "judged_rules": table, "descriptive": kp.descriptive_table(rows),
               "post_cutoff_rows": sum(1 for r in rows if r["post_cutoff"]), "seconds": round(time.time() - t0)}
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    log(json.dumps({k: v for k, v in summary.items() if k not in ("judged_rules", "descriptive")}, default=str)[:4000])
    for rid, v in table.items():
        log(rid, v["gate"].get("reason") or "stage0 ok", v["stats_by_split"])


def main():
    out_dir, mode = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    if mode == "events":
        stage_a(out_dir, sys.argv[3] if len(sys.argv) > 3 else "")
    elif mode == "run":
        stage_b(out_dir, sys.argv[3])
    else:
        raise SystemExit("mode: events or run")


if __name__ == "__main__":
    main()
