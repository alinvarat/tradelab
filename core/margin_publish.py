"""Publish the margin-arm rows (margin_arm/<UTC day>.jsonl on the pod volume: events with the borrow snapshot, trades, heartbeats) to the git
data branch data/l1f-margin, so that Actions and the owner can read them (the app is behind a login). Same credential, transport, retries
and append-only layout as core/desk_publish.py; does nothing until TRADELAB_DATA_PUSH_TOKEN is set. Public-market data only.

    margin_arm/<YYYYMMDD>/<start>-<end>.jsonl     byte range [start, end) of the pod's day file, whole lines only"""
import os
import random
import threading
import time

from . import news_publish as npb

BRANCH_ENV = "TRADELAB_MARGIN_PUSH_BRANCH"
INTERVAL_MIN_ENV = "TRADELAB_MARGIN_PUSH_MINUTES"
README = ("Append-only copy of the Kuber pod's L1f margin-arm rows (core/margin_arm.py, core/margin_publish.py): delist-notice events with the "
          "public borrow snapshot, paper trades and heartbeats. Public-market data only. Files are created once and never rewritten.\n")
_lock = threading.Lock()
STATE = {"enabled": False, "branch": None, "parts": 0, "cycles": 0, "failures": 0, "last_ok_utc": None, "last_error": None}


def _cfg(env=None):
    env = os.environ if env is None else env
    cfg = npb._cfg(env)
    try:
        minutes = max(5.0, float(env.get(INTERVAL_MIN_ENV) or 30))
    except ValueError:
        minutes = 30.0
    return {**cfg, "branch": (env.get(BRANCH_ENV) or "data/l1f-margin").strip(), "interval_s": minutes * 60}


def part_path(day, start, end):
    return f"margin_arm/{day}/{start:010d}-{end:010d}.jsonl"


def cycle(dirpath, transport=npb.http, env=None, sleep=time.sleep):
    """One publish pass. Never raises. -> {enabled, parts, bytes, ok, error}."""
    cfg = _cfg(env)
    res = {"enabled": bool(cfg["token"]), "parts": 0, "bytes": 0, "ok": True, "error": None}
    with _lock:
        STATE.update(enabled=res["enabled"], branch=cfg["branch"])
    if not cfg["token"]:
        return res
    try:
        cursor = npb.read_cursor(dirpath)
        todo = npb.pending(dirpath, cursor)
        if todo:
            if not npb.ensure_branch(transport, cfg, sleep, readme=README, message="l1f-margin data branch: start"):
                raise RuntimeError(f"data branch not reachable (GET ref HTTP {getattr(npb.ensure_branch, 'last_status', '?')})")
            for day, start, end, data in todo:
                n = data.count(b"\n")
                r = npb.put_part(transport, cfg, part_path(day, start, end), data, f"l1f-margin {day} +{n} rows", sleep)
                if r == "fail":
                    raise RuntimeError(f"upload failed (PUT HTTP {getattr(npb.put_part, 'last_status', '?')})")
                cursor[day] = end
                npb.write_cursor(dirpath, cursor)
                res["parts"] += 1
                res["bytes"] += len(data)
    except Exception as exc:  # noqa: BLE001
        res.update(ok=False, error=(type(exc).__name__ + ": " + str(exc)).replace(cfg["token"], "***")[:120])
    with _lock:
        STATE["cycles"] += 1
        STATE["parts"] += res["parts"]
        if res["ok"]:
            STATE["last_error"] = None
            if res["parts"]:
                STATE["last_ok_utc"] = time.time()
        else:
            STATE["failures"] += 1
            STATE["last_error"] = res["error"]
    return res


def view():
    with _lock:
        s = dict(STATE)
    s["enabled"] = npb.enabled()
    return s


def loop(dirpath, transport=npb.http, sleep=time.sleep):
    """Daemon-thread body: publish every N minutes (first pass after one minute), back off after failures, never exit, never raise."""
    fails = 0
    sleep(60)
    while True:
        wait = _cfg()["interval_s"]
        try:
            if _cfg()["token"]:
                fails = 0 if cycle(dirpath, transport, sleep=sleep)["ok"] else min(fails + 1, 6)
                wait = min(3600.0, wait * 2 ** fails)
            else:
                wait = max(wait, 600)
        except Exception:  # noqa: BLE001
            wait = max(wait, 600)
        sleep(wait * (0.9 + 0.2 * random.random()))
