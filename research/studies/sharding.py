"""Split one study over N parallel GitHub Actions jobs and merge the parts (.github/workflows/research_sharded.yml).

A study `x` supports sharding when research/studies/run.py defines (looked up by name, not through STUDIES):

    rows_x(symbols_slice) -> list[dict]                        (or {"rows": [...], "gaps": {"name": count}})
    summarize_x(all_rows) -> dict
    symbols_x() -> list[str]          optional; default: every Binance spot USDT symbol ever listed

`rows_x` sees only its slice, so anything that needs the whole universe (daily cross-sectional ranks, random controls,
split labels, `core.screens.judge`, Bonferroni) belongs in `summarize_x`. The split is deterministic: the de-duplicated,
sorted universe, then `[i::N]` with a 0-based shard index. Stdlib only, no network.
"""
import hashlib
import json
import os
import re


class MergeError(Exception):
    """Raised with every problem found, so a missing or inconsistent part is never merged silently."""


def split(symbols, i, n):
    """Shard i (0-based) of n: sorted(set(symbols))[i::n]."""
    if not isinstance(n, int) or not isinstance(i, int) or n < 1 or not 0 <= i < n:
        raise ValueError(f"bad shard {i} of {n}")
    return sorted(set(symbols))[i::n]


def universe_hash(symbols):
    return hashlib.sha256("\n".join(sorted(set(symbols))).encode()).hexdigest()[:16]


def normalize_result(result):
    """rows_x may return a list of rows or {"rows": [...], "gaps": {...}}; returns (rows, gaps)."""
    if isinstance(result, dict):
        rows, gaps = result.get("rows") or [], result.get("gaps") or {}
    else:
        rows, gaps = list(result or []), {}
    if not isinstance(rows, list) or not isinstance(gaps, dict):
        raise TypeError("rows_<study> must return a list or {'rows': list, 'gaps': dict}")
    return rows, gaps


def make_part(study, i, n, universe, result, seconds=0.0):
    """The JSON written by one shard job."""
    universe = sorted(set(universe))
    rows, gaps = normalize_result(result)
    return {"study": study, "shard": i, "shards": n, "n_universe": len(universe), "universe_hash": universe_hash(universe),
            "symbols": split(universe, i, n), "rows": rows, "gaps": gaps, "seconds": round(seconds, 1)}


def sum_gaps(gap_dicts):
    out = {}
    for g in gap_dicts:
        for k, v in (g or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = out.get(k, 0) + v
            else:
                out.setdefault(k, []).append(v)
    return out


def merge_parts(parts, study):
    """Check that the parts are exactly shards 0..N-1 of one universe and concatenate rows in shard order.

    Returns (rows, info). Raises MergeError listing every problem."""
    errors = []
    if not parts:
        raise MergeError(f"no parts for {study}")
    ns = {p.get("shards") for p in parts}
    hashes = {p.get("universe_hash") for p in parts}
    sizes = {p.get("n_universe") for p in parts}
    if len(ns) != 1:
        errors.append(f"parts disagree on the shard count: {sorted(map(str, ns))}")
    if len(hashes) != 1 or len(sizes) != 1:
        errors.append("parts were built from different universes")
    if any(p.get("study") != study for p in parts):
        errors.append(f"a part belongs to another study: {sorted({str(p.get('study')) for p in parts})}")
    n = max((x for x in ns if isinstance(x, int)), default=0)
    seen = {}
    for p in parts:
        seen.setdefault(p.get("shard"), []).append(p)
    dup = sorted(k for k, v in seen.items() if len(v) > 1 and isinstance(k, int))
    missing = [k for k in range(n) if k not in seen]
    extra = sorted(str(k) for k in seen if not (isinstance(k, int) and 0 <= k < n))
    if dup:
        errors.append(f"duplicate shards: {dup}")
    if missing:
        errors.append(f"missing shards: {missing}")
    if extra:
        errors.append(f"shard index out of range: {extra}")
    if not errors:
        syms = [s for k in range(n) for s in seen[k][0].get("symbols", [])]
        if len(syms) != len(set(syms)) or len(syms) != parts[0].get("n_universe"):
            errors.append(f"symbol slices overlap or do not cover the universe ({len(syms)} vs {parts[0].get('n_universe')})")
    if errors:
        raise MergeError("; ".join(errors))
    ordered = [seen[k][0] for k in range(n)]
    rows = [r for p in ordered for r in p.get("rows", [])]
    info = {"shards": n, "n_symbols": parts[0]["n_universe"], "universe_hash": parts[0]["universe_hash"],
            "shard_gaps": sum_gaps(p.get("gaps") for p in ordered),
            "shard_rows": [len(p.get("rows", [])) for p in ordered],
            "shard_seconds_max": max(p.get("seconds", 0) for p in ordered),
            "shard_seconds_sum": round(sum(p.get("seconds", 0) for p in ordered), 1)}
    return rows, info


def part_files(directory, study):
    """{shard index: path} for files named exactly <study>_<digits>.json (not <study>.json or <study>_summary.json)."""
    pat = re.compile(r"^%s_(\d+)\.json$" % re.escape(study))
    out = {}
    for root, _dirs, files in os.walk(directory):
        for f in files:
            m = pat.match(f)
            if m:
                out.setdefault(int(m.group(1)), []).append(os.path.join(root, f))
    return out


def merge_dir(directory, study):
    """Load every part file under `directory` and merge them (filename index must match the part's own index)."""
    files = part_files(directory, study)
    errors, parts = [], []
    for k in sorted(files):
        if len(files[k]) > 1:
            errors.append(f"shard {k} appears in {len(files[k])} files")
        for path in files[k]:
            with open(path) as fh:
                p = json.load(fh)
            if p.get("shard") != k:
                errors.append(f"{os.path.basename(path)} holds shard {p.get('shard')}")
            parts.append(p)
    if errors:
        raise MergeError("; ".join(errors))
    return merge_parts(parts, study)
