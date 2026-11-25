"""Family meta1 runner (Actions only): python research/sweeps/meta_alloc.py <sweep-rows dir> <event-rows dir> <poly-fv-rows dir> <out dir>.
The three dirs are checkouts of the branches data/sweep-rows, data/event-rows and data/poly-fv-rows. Writes <out>/meta1_summary.json
and, on Actions, updates reports/LEADERBOARD.json / .md with one run entry (family meta1)."""
import glob
import gzip
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import sweep_board as sb       # noqa: E402
from core import sweep_config as sc      # noqa: E402
from core import sweep_meta as sm        # noqa: E402

CONFIG = os.path.join(ROOT, "research", "sweeps", "meta", "meta1.json")
BOARD_JSON = os.path.join(ROOT, "reports", "LEADERBOARD.json")
BOARD_MD = os.path.join(ROOT, "reports", "LEADERBOARD.md")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def lines(path):
    with gzip.open(path, "rt") as f:
        for ln in f:
            if ln.strip():
                yield json.loads(ln)


def collect(cfg, sweep_dir, event_dir, poly_dir):
    """{pool: [trades]} plus coverage counts."""
    sw, cover = [], {}
    sc_cfg = cfg["sweep_rows"]
    for study_dir in sorted(glob.glob(os.path.join(sweep_dir, "rows", "*"))):
        study = os.path.basename(study_dir)
        files = sorted(glob.glob(os.path.join(study_dir, "*.jsonl.gz")), key=lambda p: int(os.path.basename(p).split(".")[0]))
        if study in sc_cfg["exclude_studies"] or not files:
            continue
        t = sm.sweep_trades(lines(files[-1]), study, sc_cfg["require_substring"].get(study))      # latest run of a study only
        cover[study] = len(t)
        sw.extend(t)
    ev = []
    for name in ("l1", "l1f", "l1g"):
        p = os.path.join(event_dir, "rows", f"{name}.jsonl.gz")
        if os.path.exists(p):
            ev.extend(sm.event_trades(lines(p), name))
    po = []
    for p in sorted(glob.glob(os.path.join(poly_dir, "rows", "rows_*.jsonl.gz"))):
        po.extend(sm.poly_trades(lines(p)))
    pools = {"sweep": sw, "event": ev, "poly": po, "all": sw + ev + po}
    cover.update(event=len(ev), poly=len(po))
    return pools, cover


def main(sweep_dir, event_dir, poly_dir, out_dir):
    cfg, sha = sc.load(CONFIG)
    pre = sc.preregistration(cfg, sha, os.path.relpath(CONFIG, ROOT), None, check_git=bool(os.environ.get("GITHUB_ACTIONS")))
    if pre["problems"]:
        sys.exit("pre-registration check failed: " + "; ".join(pre["problems"]))
    bounds = {k: [sc.day(v[0]), sc.day(v[1])] for k, v in cfg["splits"].items()}
    pools, cover = collect(cfg, sweep_dir, event_dir, poly_dir)
    results = {}
    for pool in cfg["pools"]:
        results[pool] = sm.evaluate(pools[pool], bounds, cfg["window"], cfg["bins"], cfg["draws"], cfg["seed"], cfg["min_trades"], cfg["alpha"])
        log(pool, len(pools[pool]), {s: (r["status"], r["n_criteria"], r["splits"]["validation"]["n"], r["splits"]["test"]["n"]) for s, r in results[pool].items()})
    top = []
    for pool, rs in results.items():
        for strat, r in rs.items():
            if r["status"] != "ok":
                continue
            v, t = r["splits"]["validation"], r["splits"]["test"]
            top.append({"id": f"{pool}/{strat}", "family": cfg["family"], "n_criteria": r["n_criteria"], "passed": r["passed"], "lev": None,
                        "val_n": v["n"], "val_mean": v["mean"], "val_mean_2x": None, "val_p": v["ctrl_p"], "p_adj": min(1.0, v["ctrl_p"] * 8),
                        "test_n": t["n"], "test_mean": t["mean"], "test_mean_2x": None, "val_mult30_median": None, "val_share_3x": None,
                        "test_mult30_median": None, "test_share_3x": None, "val_sign_p": None, "folds_positive": 0, "folds_n": 0, "x": None})
    top.sort(key=lambda r: (-r["n_criteria"], r["val_p"]))
    n_rules = sum(len(rs) for rs in results.values())
    run = {"family": cfg["family"], "version": cfg["version"], "config_sha256": sha, "config_commit": pre["config_commit"],
           "preregistered": pre["preregistered"], "run_id": os.environ.get("GITHUB_RUN_ID"), "sha": os.environ.get("GITHUB_SHA"),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_rules": n_rules,
           "n_gate_dropped": sum(1 for rs in results.values() for r in rs.values() if r["status"] != "ok"), "n_evaluated": len(top),
           "n_errors": 0, "n_passed": sum(1 for r in top if r["passed"]), "holm_m": len(top), "bonferroni_bar": cfg["alpha"],
           "top": top[:10], "near_miss": []}
    os.makedirs(out_dir, exist_ok=True)
    summary = {"run": run, "coverage": cover, "pool_sizes": {k: len(v) for k, v in pools.items()}, "results": results}
    with open(os.path.join(out_dir, "meta1_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    if os.environ.get("GITHUB_ACTIONS"):
        try:
            with open(BOARD_JSON) as f:
                board = json.load(f)
        except (OSError, ValueError):
            board = sb.empty()
        nb = sb.update(board, run)
        with open(BOARD_JSON, "w") as f:
            json.dump(nb, f, indent=1)
        with open(BOARD_MD, "w") as f:
            f.write(sb.render_md(nb))
        log("leaderboard", nb["totals"])
    print(json.dumps({k: run[k] for k in ("n_rules", "n_gate_dropped", "n_evaluated", "n_passed")} | {"pool_sizes": summary["pool_sizes"]}))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
