"""Forward arms that read the pod's news-ingest log (branch data/news-ingest). Actions only. Descriptive: no outcomes are read here.

    run_ingest_fwd.py r2 <out> <ingest_dir>   reads <out>/fwd/items.jsonl.gz (just written by the round-2 forward step), writes <out>/fwd/ingest_timing.json
    run_ingest_fwd.py r3 <out> <ingest_dir>   writes <out>/fwd_ingest/progress.json (wire press-release counts)

<ingest_dir> is a checkout of data/news-ingest (may be empty or absent: the pod publishes only after the owner sets the push token).
Never exits non-zero because the log is missing: round 2's own forward scoring must not depend on it."""
import gzip
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import ingest_branch as B  # noqa: E402


def _items(path):
    if not os.path.exists(path):
        return []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, sort_keys=True)


def r2(out, ingest):
    joined = B.join(B.load_rows(ingest))
    res = B.r2_timing(_items(os.path.join(out, "fwd", "items.jsonl.gz")), joined)
    res.update(utc=int(time.time()), pod_rows=len(joined), note="descriptive; entry, decisions, trigger and scoring do not read this")
    _write(os.path.join(out, "fwd", "ingest_timing.json"), res)
    print(json.dumps(res["coverage"]))


def r3(out, ingest):
    joined = B.join(B.load_rows(ingest))
    res = {"utc": int(time.time()), "pod_rows": len(joined), "wires": B.r3_progress(joined),
           "note": "counts only; no scoring is registered for this arm (addendum 2026-11-26)"}
    _write(os.path.join(out, "fwd_ingest", "progress.json"), res)
    print(json.dumps(res))


def main():
    a = sys.argv
    {"r2": r2, "r3": r3}[a[1]](a[2], a[3])


if __name__ == "__main__":
    main()
