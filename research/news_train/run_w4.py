"""News analyst training round 4: IO and orchestration (protocol_w4_20261127.md). GitHub Actions only (news_train_w4.yml). Never run locally.

    run_w4.py stage   <hh_labels.jsonl.gz> <out>                      split the opened HH labels by UTC day: out/train, out/val, out/split.json
    run_w4.py analyze <train_labels.jsonl.gz> <split.json> <hh_cache> <out>   error analysis + greedy rule fit on TRAIN rows only (a validation row raises)

Locked files are imported, never edited."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from research.news_train import logic as L  # noqa: E402
from research.news_train import logic_r2 as R  # noqa: E402
from research.news_train import logic_w4 as W  # noqa: E402
from research.news_train import run_hh as X  # noqa: E402

P = W.load_params()
P2 = R.load_params()
log, wjsonl, rjsonl, jdump = X.log, X.wjsonl, X.rjsonl, X.jdump


def hh_decisions(cache, set_name="stock_w3", model="haiku"):
    """{key: reply} of one model from the cached HH decisions (an ok reply wins over a failed one)."""
    out = {}
    for (s, m, k), r in X.load_cache(cache).items():
        if s == set_name and m == model and (r.get("ok") or k not in out):
            out[k] = r
    return out


def stage(labels_path, out):
    rows = rjsonl(labels_path)
    tr, va, vd = W.split_rows(rows, P)
    wjsonl(os.path.join(out, "train", "labels.jsonl.gz"), tr)
    wjsonl(os.path.join(out, "val", "labels.jsonl.gz"), va)
    rep = {"rows": len(rows), "unique_keys": len({r["key"] for r in rows}), "train": len(tr), "validation": len(va),
           "days_total": len({L.day_of(r["t_pub"]) for r in rows}), "validation_days": vd, "rule": P["split"]["rule"]}
    jdump(os.path.join(out, "split.json"), rep)
    log(json.dumps({k: v for k, v in rep.items() if k != "validation_days"}), "val_days", vd[0], "..", vd[-1])


def analyze(train_labels, split_json, cache, out):
    vd = json.load(open(split_json))["validation_days"]
    rows = rjsonl(train_labels)
    W.assert_train_only(rows, vd)
    decs = hh_decisions(cache)
    res = W.analysis(rows, decs, P, P2)
    res["decisions_ok"] = sum(1 for r in rows if (decs.get(r["key"]) or {}).get("ok"))
    res["greedy_w3"] = W.greedy_fit(rows, decs, P, P2)
    jdump(os.path.join(out, "analysis_train.json"), res)
    log(json.dumps({"baseline": res["baseline_w3"], "greedy": {k: res["greedy_w3"][k] for k in ("rule", "steps", "evaluations")}}, default=str))


def main():
    a = sys.argv
    if a[1] == "stage":
        stage(a[2], a[3])
    elif a[1] == "analyze":
        analyze(a[2], a[3], a[4], a[5])
    else:
        raise SystemExit("modes: stage | analyze")


if __name__ == "__main__":
    main()
