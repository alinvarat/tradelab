"""Glue between the sweep configs (research/sweeps/<family>.json) and the sharded runner (research/studies/run.py).

`shard_functions()` returns {"symbols_sweep_<f>", "rows_sweep_<f>", "summarize_sweep_<f>"} for every config file; run.py merges it
into its globals, so `research_sharded.yml` (study=sweep_<family>) fans the family out. The shard universe is the list of rule
chunks (core.sweep_config.chunks), each chunk inside one data group. A shard loads each data group it needs once.
"""
import glob
import json
import os
import re
import sys
import time
import traceback

from core import sweep_board as sb
from core import sweep_config as sc
from core import sweep_engine as se
from core import sweep_stats as ss

CONFIG_DIR = os.path.join(sc.ROOT, "research", "sweeps")
BOARD_JSON = os.path.join(sc.ROOT, "reports", "LEADERBOARD.json")
BOARD_MD = os.path.join(sc.ROOT, "reports", "LEADERBOARD.md")
TRADE_FIELDS = ("t", "x", "side", "sym", "ep", "xp", "net", "cost", "fund", "mae", "mfe")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def on_actions():
    return bool(os.environ.get("GITHUB_ACTIONS"))


def family_files():
    out = {}
    for p in sorted(glob.glob(os.path.join(CONFIG_DIR, "*.json"))):
        stem = os.path.splitext(os.path.basename(p))[0]
        if re.fullmatch(r"[a-z0-9_]+", stem):
            out["sweep_" + stem] = p
    return out


def read_board(path=BOARD_JSON):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return sb.empty()


def min_notional(rule, trades):
    """USD notional of the smallest tradable lot (XM 0.01 lot); 0 for venues with a tiny minimum."""
    if rule["cost"]["model"] != "xm" or not trades:
        return 0.0
    from core import broker_costs as bc
    acct = rule["cost"].get("account", "standard")
    vals = []
    for t in trades:
        sym, _ = bc._norm(t["sym"], acct)
        vals.append(bc.XM_CONTRACT[sym] * bc.XM_MIN_LOT * (1.0 if sym == "USDJPY" else t["ep"]))
    vals.sort()
    return vals[len(vals) // 2]


def compact_trades(trades):
    return [[round(t[k], 8) if isinstance(t[k], float) else t[k] for k in TRADE_FIELDS] for t in trades]


def run_rule(rule, ctx, cfg, keep_trades=True):
    """One rule -> one result row (status ok | gate | error)."""
    b = rule["bounds"]
    row = {"id": rule["id"], "style": rule["style"], "lev": rule["size"]["lev"], "k": rule["size"].get("k", 1),
           "tf": rule["data"]["tf"], "n_symbols": len(rule["data"]["symbols"])}
    missing = [s for s in rule["data"]["symbols"] if s not in ctx.bars]
    if missing:
        return dict(row, status="error", reason=f"data missing for {missing}")
    trades = se.rule_trades(ctx, rule, rule.get("trade") or rule["data"]["symbols"], b["train"][0], b["test"][1])
    train = ss.in_split(trades, *b["train"])
    ok, info = ss.gate(train, rule, cfg, (b["train"][1] - b["train"][0]) / 86400.0, min_notional(rule, train))
    row["gate"] = info
    if not ok:
        return dict(row, status="gate", reason=info["reason"])
    row.update(ss.evaluate(trades, rule, b))
    row["status"] = "ok"
    row["reason"] = None
    if keep_trades:
        row["trades"] = compact_trades(trades)
    return row


def finish(name, rel, cfg, sha, n_rules, all_rows, write_board=None):
    board = read_board()
    pre = sc.preregistration(cfg, sha, rel, board, check_git=on_actions())
    info = ss.judge_family(all_rows, cfg)
    ev = sorted((r for r in all_rows if r["status"] == "ok"), key=ss.closeness_key)
    top = [ss.compact(r, cfg["family"]) for r in ev[:10]]
    gate_reasons = {}
    for r in all_rows:
        if r["status"] == "gate":
            k = re.sub(r"[-+]?\d+(\.\d+)?", "#", r["reason"])
            gate_reasons[k] = gate_reasons.get(k, 0) + 1
    by_style = {}
    for r in all_rows:
        s = by_style.setdefault(r["style"], {"rules": 0, "gate": 0, "evaluated": 0, "passed": 0, "best_criteria": 0})
        s["rules"] += 1
        s["gate"] += r["status"] == "gate"
        if r["status"] == "ok":
            s["evaluated"] += 1
            s["passed"] += r["passed"]
            s["best_criteria"] = max(s["best_criteria"], r["n_criteria"])
    near = sorted((r for r in all_rows if r["status"] == "gate" and r.get("gate", {}).get("x") is not None),
                  key=lambda r: -r["gate"]["x"])[:10]
    near_miss = [{"id": r["id"], "reason": r["reason"], "x": r["gate"]["x"], "train_mean": r["gate"].get("train_mean"),
                  "n_train": r["gate"]["n_train"], "vol_cost": r["gate"].get("vol_cost")} for r in near]
    run = {"family": cfg["family"], "version": cfg["version"], "config_sha256": sha, "config_commit": pre["config_commit"],
           "preregistered": pre["preregistered"], "run_id": os.environ.get("GITHUB_RUN_ID"), "sha": os.environ.get("GITHUB_SHA"),
           "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_rules": n_rules,
           "n_gate_dropped": sum(r["status"] == "gate" for r in all_rows), "n_evaluated": len(ev),
           "n_errors": sum(r["status"] == "error" for r in all_rows), "n_passed": sum(1 for r in ev if r["passed"]),
           "holm_m": info["holm_m"], "bonferroni_bar": info["bonferroni_bar"], "top": top, "near_miss": near_miss}
    errors = [{"id": r["id"], "reason": r["reason"]} for r in all_rows if r["status"] == "error"][:5]
    if (write_board if write_board is not None else on_actions()) and not pre["problems"]:
        nb = sb.update(board, run)
        os.makedirs(os.path.dirname(BOARD_JSON), exist_ok=True)
        with open(BOARD_JSON, "w") as f:
            json.dump(nb, f, indent=1)
        with open(BOARD_MD, "w") as f:
            f.write(sb.render_md(nb))
        log(f"leaderboard: {nb['totals']}")
    return {"line": name, **run, "pre_problems": pre["problems"], "alpha": info["alpha"], "gate_reasons": gate_reasons,
            "by_style": by_style, "passed": [r["id"] for r in ev if r["passed"]], "error_samples": errors,
            "n_rows": len(all_rows)}


def make_functions(name, path):
    stem = name[len("sweep_"):]
    rel = os.path.relpath(path, sc.ROOT)

    def symbols():
        cfg, sha = sc.load(path)
        rules = sc.expand(cfg)
        pre = sc.preregistration(cfg, sha, rel, read_board(), check_git=on_actions())
        if pre["problems"]:
            raise SystemExit("pre-registration check failed: " + "; ".join(pre["problems"]))
        return sorted(sc.chunks(rules, int(cfg.get("chunk_target", 20))))

    def rows(chunk_ids):
        cfg, _ = sc.load(path)
        rules = {r["id"]: r for r in sc.expand(cfg)}
        ch = sc.chunks(list(rules.values()), int(cfg.get("chunk_target", 20)))
        groups, gaps, out = {}, {"rules_run": 0, "rule_errors": 0, "groups_loaded": 0, "symbols_dropped": 0}, []
        for cid in chunk_ids:
            for rid in ch[cid]:
                rule = rules[rid]
                gk = rule["gkey"]
                if gk not in groups:
                    try:
                        from research.sweeps import loaders
                        bars, dropped = loaders.load_group(rule["data"])
                        groups[gk] = (se.Ctx(bars), None)
                        gaps["groups_loaded"] += 1
                        gaps["symbols_dropped"] += len(dropped)
                    except Exception:      # noqa: BLE001
                        groups[gk] = (None, traceback.format_exc()[-400:])
                ctx, err = groups[gk]
                try:
                    if ctx is None:
                        row = {"id": rid, "style": rule["style"], "status": "error", "reason": "group load failed: " + err}
                    else:
                        row = run_rule(rule, ctx, cfg)
                except Exception:       # noqa: BLE001  an engine bug must show up in the leaderboard, not crash the shard
                    row = {"id": rid, "style": rule["style"], "status": "error", "reason": traceback.format_exc()[-400:]}
                row["chunk"] = cid
                gaps["rules_run"] += 1
                gaps["rule_errors"] += row["status"] == "error"
                out.append(row)
        return {"rows": out, "gaps": gaps}

    def summarize(all_rows, write_board=None):
        cfg, sha = sc.load(path)
        return finish(name, rel, cfg, sha, len(sc.expand(cfg)), all_rows, write_board)

    return {f"symbols_{name}": symbols, f"rows_{name}": rows, f"summarize_{name}": summarize}


def make_fw_functions(name, path):
    """funding_window family: the shard universe is the perp symbols, rows are extreme-funding events, the merge builds the rules."""
    from core import sweep_events as sev
    rel = os.path.relpath(path, sc.ROOT)

    def symbols():
        cfg, sha = sc.load(path)
        sev.expand(cfg)
        pre = sc.preregistration(cfg, sha, rel, read_board(), check_git=on_actions())
        if pre["problems"]:
            raise SystemExit("pre-registration check failed: " + "; ".join(pre["problems"]))
        from research.sweeps import fundwin
        return fundwin.universe()

    def rows(symbols_slice):
        from research.sweeps import fundwin
        cfg, _ = sc.load(path)
        events, gaps = fundwin.load_events(symbols_slice, cfg["data"])
        return {"rows": events, "gaps": gaps}

    def summarize(events, write_board=None):
        cfg, sha = sc.load(path)
        rules = sev.expand(cfg)
        by_id = {r["id"]: r for r in rules}
        rule_rows = []
        for r in rules:
            tr = sev.trades_for_rule(r, events)
            b = r["bounds"]
            train = ss.in_split(tr, *b["train"])
            row = {"id": r["id"], "style": r["style"], "lev": r["lev"], "k": r["k"], "tf": "1m", "n_symbols": len({e["sym"] for e in events})}
            ok, info = ss.gate(train, r, cfg, (b["train"][1] - b["train"][0]) / 86400.0)
            row["gate"] = info
            if not ok:
                rule_rows.append(dict(row, status="gate", reason=info["reason"]))
                continue
            row.update(ss.evaluate(tr, r, b))
            row["status"], row["reason"] = "ok", None
            row["trades"] = compact_trades(tr)
            tw = by_id.get(sev.twin_id(r) or "")
            if r["delay"] == 0:
                ttr = sev.trades_for_rule(tw, events) if tw else []
                vm = ss.mean([t["net"] for t in ss.in_split(ttr, *b["validation"])])
                tm = ss.mean([t["net"] for t in ss.in_split(ttr, *b["test"])])
                row["extra_criteria"] = {"survives_5min_delay": bool(tw) and vm is not None and tm is not None and vm > 0 and tm > 0}
            else:
                row["extra_criteria"] = {"survives_5min_delay": True}
            # the rate settled at the event is not known to an entry before it: such a rule can never pass
            row["extra_criteria"]["no_lookahead"] = not (r["sig"] == "realized" and r["E"] < 0)
            rule_rows.append(row)
        summ = finish(name, rel, cfg, sha, len(rules), rule_rows, write_board)
        summ["rule_rows"] = rule_rows
        summ["n_events"] = len(events)
        summ["n_event_symbols"] = len({e["sym"] for e in events})
        return summ

    return {f"symbols_{name}": symbols, f"rows_{name}": rows, f"summarize_{name}": summarize}


def shard_functions():
    out = {}
    for name, path in family_files().items():
        with open(path) as f:
            kind = json.load(f).get("kind")
        out.update(make_fw_functions(name, path) if kind == "funding_window" else make_functions(name, path))
    return out


def export_trades(merged_json, out_path):
    """Write every evaluated rule's trades of a merged run as jsonl.gz (one line per trade) for later stacking."""
    import gzip
    with open(merged_json) as f:
        d = json.load(f)
    sm = d["summary"]
    n = 0
    with gzip.open(out_path, "wt") as g:
        for r in (sm.get("rule_rows") or d["rows"]):
            for tr in r.get("trades") or []:
                g.write(json.dumps({"family": sm["family"], "v": sm["version"], "cfg": sm["config_sha256"][:12], "rule": r["id"],
                                    **dict(zip(TRADE_FIELDS, tr))}, separators=(",", ":")) + "\n")
                n += 1
    return n
