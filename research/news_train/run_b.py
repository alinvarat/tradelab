"""News-analyst training round 3, Track B2: Korean/Chinese crypto headlines from GDELT translingual GKG (protocol_r3_addendum_b_20261126.md).
Reuses round-2 evaluation code read-only (run_r2 eval/merge/select with version w1); writes only data/news-train-r3b.

    run_b.py pull    <out> <start_day> <end_day>
    run_b.py build   <parts_dir> <out>
    run_b.py sealed  <out> <data_dir>
(eval/merge/select/analyze: run_r2.py modes via run_b.py wrappers below, with the CJK keyword baseline)
"""
import glob
import html
import io
import json
import os
import re
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402
from research.news_train import run_r2 as RR  # noqa: E402

PB = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "params_r3b.json")))
RR.P["keyword"] = PB["keyword"]            # CJK + English keyword baseline, in memory only
log, wjsonl, rjsonl = RR.log, RR.wjsonl, RR.rjsonl


def url_tr(stamp):
    return f"https://data.gdeltproject.org/gdeltv2/{stamp}.translation.gkg.csv.zip"


def coin_of_cjk(title):
    hits, work = set(), title
    # longest names first so that 'bitcoin cash' is not read as bitcoin
    pairs = sorted(((n, s) for s, names in PB["coins"].items() for n in names), key=lambda x: -len(x[0]))
    for n, s in pairs:
        if n in work:
            hits.add(s)
            work = work.replace(n, " ")
    low = work.lower()
    for s, names in PB["latin"].items():
        for n in names:
            if re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", low):
                hits.add(s)
    return next(iter(hits)) if len(hits) == 1 else None


def redact(title, coin):
    s = title
    for n in sorted(PB["coins"].get(coin, []) + PB["latin"].get(coin, []) + [coin], key=len, reverse=True):
        s = re.sub(re.escape(n), "[COIN]", s, flags=re.I)
    return L.scrub_dates(s)


def pull_stamp(stamp):
    raw = RR.http(url_tr(stamp))
    if raw is None:
        return None
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        txt = z.read(z.namelist()[0]).decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    t = R.stamp_ts(stamp)
    rows, n = [], 0
    for line in txt.split("\n"):
        f = line.split("\t")
        if len(f) < 27:
            continue
        m = re.search(r"srclc:([a-z]+)", f[25])
        if not m or m.group(1) not in PB["langs"]:
            continue
        n += 1
        mt = re.search(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", f[26], re.S)
        if not mt:
            continue
        title = re.sub(r"\s+", " ", html.unescape(mt.group(1))).strip()
        coin = coin_of_cjk(title)
        if coin and len(title) >= PB["dedupe"]["min_chars"]:
            rows.append({"t": t, "coin": coin, "title": title, "domain": f[3].lower(), "lang": m.group(1)})
    return rows, len(raw), n


def pull(out, start, end):
    rows, failed, files, cjk, t0 = [], 0, 0, 0, __import__("time").time()
    for day in RR.days_between(start, end):
        with ThreadPoolExecutor(12) as ex:
            res = list(ex.map(pull_stamp, R.gkg_stamps(day, 1)))
        for r in res:
            files += 1
            if r is None:
                failed += 1
            else:
                rows += r[0]
                cjk += r[2]
        log(day, "coin rows", len(rows), "cjk rows", cjk, "failed", failed)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, f"rows_{start}_{end}.jsonl.gz"), rows)
    json.dump({"start": start, "end": end, "files": files, "failed": failed, "rows": len(rows), "cjk_rows": cjk}, open(os.path.join(out, f"pull_{start}_{end}.json"), "w"))


def bigrams(s):
    s = re.sub(r"[^\w]", "", s.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def dedupe(rows):
    d = PB["dedupe"]
    out, recent = [], {}
    for r in sorted(rows, key=lambda r: (r["t"], r["title"])):
        bg = bigrams(r["title"])
        dup = False
        for t0, b0 in recent.get(r["coin"], []):
            if r["t"] - t0 <= d["window_s"] and len(bg & b0) / max(1, len(bg | b0)) >= d["jaccard"]:
                dup = True
                break
        if not dup:
            out.append(r)
            recent[r["coin"]] = [x for x in recent.get(r["coin"], []) if r["t"] - x[0] <= d["window_s"]] + [(r["t"], bg)]
    return out


def split_b(ts):
    d = PB["dates"]
    if ts < L.day_ts(d["clean_start"]):
        return None
    if ts < L.day_ts(d["clean_train_end"]):
        return "train"
    if ts < L.day_ts(d["dev_end"]):
        return "validation"
    if ts < L.day_ts(d["refuse_from"]):
        return "sealed"
    raise L.SealError("t_pub at or after refuse_from")


def build(parts, out):
    rows = []
    for p in sorted(glob.glob(os.path.join(parts, "rows_*.jsonl.gz"))):
        rows += rjsonl(p)
    stats = {"raw_coin_rows": len(rows)}
    rows = dedupe(rows)
    by = {}
    for r in rows:
        by.setdefault((r["coin"], L.day_of(r["t"])), []).append(r)
    rows = []
    for v in by.values():
        v.sort(key=lambda r: L.unit(f"{PB['seed']}:{r['coin']}:{r['t']}:{r['title'][:20]}"))
        rows += v[:PB["dedupe"]["cap_per_coin_day"]]
    stats["after_dedupe_cap"] = len(rows)
    pools = {"train": [], "validation": [], "sealed": []}
    for r in rows:
        sp = split_b(r["t"])
        if sp:
            pools[sp].append(r)
    stats["pool"] = {k: len(v) for k, v in pools.items()}
    items = []
    for sp, rs in pools.items():
        for r in sorted(rs, key=lambda r: L.unit(f"{PB['seed']}:{r['coin']}:{r['t']}:{r['title'][:20]}"))[:PB["sample"][sp]]:
            items.append({"key": f"tr:{r['coin']}:{r['t']}:{int(L.unit(r['title']) * 1e8)}", "market": "crypto", "src": r["domain"] + " (" + r["lang"] + ")", "cls": None,
                          "t_pub": r["t"], "sym": r["coin"], "split": sp, "items": [], "text": redact(r["title"], r["coin"]), "text_named": r["title"],
                          "descr": "Instrument: a crypto token with a perpetual contract. The headline is in Korean or Chinese."})
    stats["picked"] = {sp: sum(1 for i in items if i["split"] == sp) for sp in pools}
    stats["by_lang_dev"] = {}
    dev = [i for i in items if i["split"] != "sealed"]
    for i in dev:
        lg = i["src"].split("(")[-1].rstrip(")")
        stats["by_lang_dev"][lg] = stats["by_lang_dev"].get(lg, 0) + 1
    t0, t1 = L.day_ts("2025-11-30"), L.day_ts(PB["dates"]["dev_end"]) + 2 * 86400
    labelled, drops = [], {}
    for coin in sorted({i["sym"] for i in dev}):
        bars, src, failed = RR.coin_bars(coin, t0, t1)
        mine = [i for i in dev if i["sym"] == coin]
        if not bars:
            drops["no_bars"] = drops.get("no_bars", 0) + len(mine)
            continue
        for it in mine:
            lab = R.crypto_label_r2(bars, it["t_pub"], RR.P)
            if not lab:
                drops["no_entry_bar"] = drops.get("no_entry_bar", 0) + 1
                continue
            labelled.append(dict(it, price_src=src, labels={R.LAB: lab}))
    stats["drops"], stats["dev_labelled"] = drops, len(labelled)
    os.makedirs(out, exist_ok=True)
    wjsonl(os.path.join(out, "dev.jsonl.gz"), labelled)
    wjsonl(os.path.join(out, "sealed_items.jsonl.gz"), [i for i in items if i["split"] == "sealed"])
    json.dump(stats, open(os.path.join(out, "build_report_b.json"), "w"), indent=1)
    log(json.dumps(stats))


def sealed(out, data):
    from core import ai_news
    if os.path.exists(os.path.join(data, "sealed_b", "result.json")):
        raise SystemExit("Track B sealed set already opened: refusing a second run")
    lk = json.load(open(os.path.join(R.HERE, "LOCK_R3B.json")))
    if not lk.get("version"):
        raise SystemExit("no candidate: sealed set stays unopened")
    ver = next(v for v in R.versions_registry()["versions"] if v["id"] == lk["version"])
    assert ver["sha256"] == lk["prompt_sha256"], "LOCK_R3B.json does not match the round-2 registry"
    system = open(R.check_version(ver)).read()
    theta = json.load(open(os.path.join(data, "calib.json"))).get(ver["id"])
    items = rjsonl(os.path.join(data, "sealed_items.jsonl.gz"))
    t0, t1 = L.day_ts(PB["dates"]["sealed_from"]) - 86400, L.day_ts(PB["dates"]["refuse_from"]) + 2 * 86400
    bars_by, rows, drops = {}, [], {}
    for it in items:
        split_b(it["t_pub"])
        if it["sym"] not in bars_by:
            bars_by[it["sym"]] = RR.coin_bars(it["sym"], t0, t1)[0]
        bars = bars_by[it["sym"]]
        lab = R.crypto_label_r2(bars, it["t_pub"], RR.P) if bars else None
        if not lab:
            drops["no_label"] = drops.get("no_label", 0) + 1
            continue
        rows.append(dict(it, labels={R.LAB: lab}))
    log("sealed B labelled", len(rows), drops)
    calls = RR.decide_all(rows, ver, system, None)
    decs = {c["key"]: c for c in calls}
    res, m_total = RR.score_sealed(rows, decs, ver, theta, PB["k_versions"])
    prim = next(c for c in res["cells"] if c["market"] == "crypto" and c["hold"] == RR.P["primary"]["crypto"])
    extra, verdict = RR.done_checks(prim, m_total)
    res.update(extra, version=ver["id"], drops=drops, verdict=verdict, theta=theta, spend=ai_news.spend(), failed_replies=sum(1 for c in calls if not c["ok"]))
    os.makedirs(os.path.join(out, "sealed_b"), exist_ok=True)
    json.dump(res, open(os.path.join(out, "sealed_b", "result.json"), "w"), indent=1, default=str)
    wjsonl(os.path.join(out, "sealed_b", "calls.jsonl.gz"), calls)
    log(json.dumps({k: v for k, v in res.items() if k != "cells"}, default=str))


def main():
    a = sys.argv
    mode = a[1]
    if mode == "pull":
        pull(a[2], a[3], a[4])
    elif mode == "build":
        build(a[2], a[3])
    elif mode == "eval":
        RR.run_eval(a[2], a[3], a[4], a[5], int(a[6]), int(a[7]), int(a[8]) if len(a) > 8 else 300)
    elif mode == "merge":
        RR.merge(a[2], a[3], a[4])
    elif mode == "select":
        RR.select(a[2], a[3])
    elif mode == "analyze":
        RR.analyze(a[2], a[3], a[4])
    elif mode == "sealed":
        sealed(a[2], a[3])
    else:
        raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
