"""sweep config: load, grid expansion, validation, chunking and the pre-registration check.

A family is one JSON file research/sweeps/<name>.json:

    {"family": "mix1", "version": 1, "alpha": 0.05, "account_usd": 147, "chunk_target": 20,
     "gate": {"min_train_trades": 30, "target_multiple": 3.0, "mfe_quantile": 0.9},
     "pass": {"min_val_trades": 30, "min_test_trades": 20},
     "defs": {"data": {name: spec}, "splits": {name: {train: [from, to], validation: [...], test: [...]}}, "cost": {name: spec}},
     "rules": [{"id": "streak_rev", "data": "perp1h", "splits": "hourly", "cost": "perp",
                "long": [{"f": "streak", "le": -4}], "short": "mirror",
                "exit": {"time": 6, "stop": {"atr": 2}}, "size": {"lev": 3, "k": 2},
                "grid": {"long.0.le": [-3, -4], "exit.time": [3, 6]}}]}

`grid` is a dotted path (list indexes are numbers) -> values; the cartesian product is expanded into one rule per
combination, id "streak_rev[long.0.le=-3,exit.time=3]". data: {source: binance_vision|yahoo, market: futures/um|spot,
tf: 1h|4h|1d, symbols, extras: [funding, premium], start, end}. Dates are YYYY-MM-DD (UTC).
"""
import calendar
import copy
import hashlib
import itertools
import json
import math
import os
import subprocess
import time

from core import sweep_engine as se

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = ("binance_vision", "yahoo")
TFS = {"1h": 1, "4h": 4, "1d": 24}
COST_MODELS = ("perp", "spot", "etf", "xm")
LEV_MAX = {"perp": 20, "spot": 1, "etf": 4, "xm": 100}
SPLIT_NAMES = ("train", "validation", "test")
ENTRY_MODES = ("next_open", "close")
EXIT_ON = ("same", "open", "close")


class ConfigError(ValueError):
    pass


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def day(s):
    return float(calendar.timegm(time.strptime(s, "%Y-%m-%d")))


def load(path):
    """(config dict, sha256 of the file bytes)."""
    with open(path, "rb") as f:
        raw = f.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    try:
        for p in parts[:-1]:
            cur = cur[int(p)] if isinstance(cur, list) else cur[p]
        last = parts[-1]
        if isinstance(cur, list):
            cur[int(last)]       # must exist
            cur[int(last)] = value
        else:
            cur[last] = value
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise ConfigError(f"grid path {path!r} does not exist in the rule ({type(e).__name__})") from e


def _fmt(v):
    return json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else str(v)


def _ref(defs, kind, v):
    if isinstance(v, str):
        if v not in defs.get(kind, {}):
            raise ConfigError(f"unknown {kind} def {v!r}")
        return copy.deepcopy(defs[kind][v])
    return copy.deepcopy(v)


def _conds(rule, key):
    v = rule.get(key)
    if v in (None, "mirror"):
        return []
    return v


def validate(rule):
    rid = rule["id"]

    def bad(msg):
        raise ConfigError(f"{rid}: {msg}")
    data = rule.get("data")
    if not isinstance(data, dict) or data.get("source") not in SOURCES or data.get("tf") not in TFS:
        bad("data needs source (binance_vision|yahoo) and tf (1h|4h|1d)")
    if not data.get("symbols") or not data.get("start") or not data.get("end"):
        bad("data needs symbols, start, end")
    if data["source"] == "yahoo" and data["tf"] != "1d":
        bad("yahoo data is daily only")
    if data["source"] == "binance_vision" and data.get("market", "futures/um") not in ("futures/um", "spot"):
        bad("market must be futures/um or spot")
    extras = data.get("extras", [])
    sp = rule.get("splits")
    if not isinstance(sp, dict) or any(k not in sp for k in SPLIT_NAMES):
        bad("splits needs train, validation, test")
    prev = None
    for k in SPLIT_NAMES:
        a, b = day(sp[k][0]), day(sp[k][1])
        if not a < b or (prev is not None and a < prev):
            bad("splits must be ordered, non-overlapping, train first")
        prev = b
    lg, sh = rule.get("long"), rule.get("short")
    if not lg and not (isinstance(sh, list) and sh):
        bad("needs a long list or an explicit short list")
    if sh == "mirror" and not lg:
        bad("short 'mirror' needs a long list")
    try:
        long_c, short_c = se.side_conditions(rule)
    except ValueError as e:
        bad(str(e))
    for c in long_c + short_c:
        name = c.get("f")
        if name not in se.FEATURES:
            bad(f"unknown feature {name!r}")
        try:
            se.cond_op(c)
        except ValueError as e:
            bad(str(e))
        if name in se.NEEDS_REF and c.get("ref") not in data["symbols"]:
            bad(f"{name} needs ref in data.symbols")
        if name in se.NEEDS_FUNDING and ("funding" not in extras or data["source"] != "binance_vision"
                                         or data.get("market", "futures/um") != "futures/um"):
            bad(f"{name} needs data.extras funding on futures/um")
        if name in se.NEEDS_PREMIUM and ("premium" not in extras or data["source"] != "binance_vision"):
            bad(f"{name} needs data.extras premium")
    ex = rule.get("exit") or {}
    if not isinstance(ex.get("time"), int) or ex["time"] < 1:
        bad("exit.time must be an integer >= 1")
    if ex.get("on", "same") not in EXIT_ON or rule.get("entry", "next_open") not in ENTRY_MODES:
        bad("bad entry or exit.on")
    for k in ("stop", "target", "trail"):
        if ex.get(k) is not None and not (isinstance(ex[k], dict) and len(ex[k]) == 1 and next(iter(ex[k])) in ("atr", "pct")
                                          and ex[k][next(iter(ex[k]))] > 0):
            bad(f"exit.{k} must be {{'atr': x}} or {{'pct': x}} with x > 0")
    cm = rule.get("cost") or {}
    if cm.get("model") not in COST_MODELS:
        bad(f"cost.model must be one of {COST_MODELS}")
    sz = rule.get("size") or {}
    lev, k = sz.get("lev"), sz.get("k", 1)
    if not isinstance(lev, (int, float)) or lev <= 0 or lev > LEV_MAX[cm["model"]]:
        bad(f"size.lev must be in (0, {LEV_MAX[cm['model']]}] for {cm['model']}")
    if not isinstance(k, int) or k < 1:
        bad("size.k must be an integer >= 1")
    if cm["model"] == "xm":
        from core import broker_costs as bc
        for s in data["symbols"]:
            bc._norm(s, cm.get("account", "standard"))     # raises KeyError for a symbol XM has no cost row for


def expand(cfg):
    """The config's rules with every grid expanded and every def resolved: list of rule dicts with id, gkey, bounds."""
    defs = cfg.get("defs", {})
    out, seen = [], set()
    for entry in cfg["rules"]:
        grid = entry.get("grid") or {}
        keys = list(grid)
        combos = list(itertools.product(*[grid[k] for k in keys])) if keys else [()]
        for combo in combos:
            r = copy.deepcopy({k: v for k, v in entry.items() if k != "grid"})
            for k, v in zip(keys, combo):
                _set_path(r, k, copy.deepcopy(v))
            suffix = ",".join(f"{k}={_fmt(v)}" for k, v in zip(keys, combo))
            r["style"] = entry["id"]
            r["id"] = f"{entry['id']}[{suffix}]" if suffix else entry["id"]
            for kind, key in (("data", "data"), ("splits", "splits"), ("cost", "cost")):
                if key not in r:
                    raise ConfigError(f"{r['id']}: missing {key}")
                r[key] = _ref(defs, kind, r[key])
            if isinstance(r["cost"], dict) and "model" not in r["cost"] and "model" in defs.get("cost", {}):
                pass
            if r["id"] in seen:
                raise ConfigError(f"duplicate rule id {r['id']}")
            seen.add(r["id"])
            validate(r)
            r["gkey"] = hashlib.sha256(canon(r["data"]).encode()).hexdigest()[:12]
            r["bounds"] = {k: [day(r["splits"][k][0]), day(r["splits"][k][1])] for k in SPLIT_NAMES}
            out.append(r)
    return out


def chunks(rules, target):
    """{chunk id: [rule ids]}: rules grouped by data group (a chunk never mixes groups, so one shard loads few groups),
    each group cut into pieces of ceil(n_rules / target)."""
    size = max(1, math.ceil(len(rules) / max(1, target)))
    by = {}
    for r in rules:
        by.setdefault(r["gkey"], []).append(r["id"])
    out, n = {}, 0
    for gk in sorted(by):
        ids = sorted(by[gk])
        for j in range(0, len(ids), size):
            out[f"c{n:03d}"] = ids[j:j + size]
            n += 1
    return out


def git_state(relpath, root=ROOT, run=subprocess.run):
    """(tracked, clean, last commit sha) of a file in the checkout."""
    def git(*a):
        return run(["git", "-C", root, *a], capture_output=True, text=True)
    try:
        tracked = git("ls-files", "--error-unmatch", relpath).returncode == 0
        clean = git("diff", "--quiet", "HEAD", "--", relpath).returncode == 0
        commit = git("log", "-1", "--format=%H", "--", relpath).stdout.strip()
    except OSError:
        return False, False, ""
    return tracked, clean, commit


def preregistration(cfg, sha, relpath, board=None, check_git=True, root=ROOT, run=subprocess.run):
    """Pre-registration facts of a run. Problems (the run must stop): the file is not committed unchanged, or an earlier run of
    the same family and version used a different file (a changed family needs a new version number)."""
    problems = []
    commit = ""
    if check_git:
        tracked, clean, commit = git_state(relpath, root, run)
        if not (tracked and clean and commit):
            problems.append(f"{relpath} is not committed unchanged (tracked={tracked}, clean={clean}); commit it before the run")
    for r in (board or {}).get("runs", []):
        if r.get("family") == cfg["family"] and r.get("version") == cfg["version"] and r.get("config_sha256") != sha:
            problems.append(f"family {cfg['family']} v{cfg['version']} already ran with config {r.get('config_sha256', '')[:12]}; "
                            "bump `version` for a changed file")
    return {"config_sha256": sha, "config_commit": commit, "config_path": relpath, "problems": problems,
            "preregistered": not problems and check_git}
