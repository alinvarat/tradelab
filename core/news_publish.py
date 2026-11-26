"""Publish the pod's news-ingest log (core/news_ingest.py: t_pub, t_seen, t_llm per item) to a git data branch so that
GitHub Actions research jobs can read it (the app sits behind Cloudflare and a login). Stdlib only.

Credential: the pod gets NO GitHub token by default. The publisher does nothing (and says so in /api/news_latency under
ingest.publish) until the repo secret TRADELAB_DATA_PUSH_TOKEN is set (a fine-grained PAT, contents:write on this repo only;
see ops/SYSTEM_MAP.md) and the deploy has run once more, which copies it into the pod environment. It only reads the
local log and writes to the data branch; it never touches the ingest loop, the bot or any other repo.

Layout on branch data/news-ingest (append-only, create-only; a file is never rewritten):
    news_ingest/<YYYYMMDD>/<start>-<end>.jsonl     byte range [start, end) of the pod's UTC-day file, whole lines only
The day is the pod's file day (event time of the row). The reader joins parts and drops duplicate rows, so a part written
twice with other boundaries (cursor lost after a volume reset) does no harm. Uploads are small: one part per file per
cycle, at most MAX_PART_BYTES, at most MAX_BYTES_PER_CYCLE in total, so a backlog drains over several cycles.

Settings (environment): TRADELAB_DATA_PUSH_TOKEN (secret), TRADELAB_DATA_REPO (default alinvarat/tradelab),
TRADELAB_NEWS_PUSH_BRANCH (default data/news-ingest), TRADELAB_NEWS_PUSH_MINUTES (default 10, minimum 1)."""
import base64
import json
import os
import random
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TOKEN_ENV = "TRADELAB_DATA_PUSH_TOKEN"
API = "https://api.github.com"
MAX_PART_BYTES = 256 * 1024
MAX_BYTES_PER_CYCLE = 1024 * 1024
MAX_FILES_PER_CYCLE = 4
TRIES = 4
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 60.0
FAIL_SLEEP_CAP_S = 3600.0
COMMITTER = {"name": "tradelab-research", "email": "tradelab-research@users.noreply.github.com"}
CURSOR_NAME = ".publish_cursor.json"          # not *.jsonl: prune_logs and reload_window must not see it
RETRY_STATUS = {0, 429, 500, 502, 503, 504}

_lock = threading.Lock()
STATE = {"enabled": False, "branch": None, "repo": None, "parts": 0, "bytes": 0, "cycles": 0, "failures": 0,
         "consecutive_failures": 0, "last_ok_utc": None, "last_error": None, "last_cycle": None}


def _cfg(env=None):
    env = os.environ if env is None else env
    token = (env.get(TOKEN_ENV) or "").strip()
    try:
        minutes = max(1.0, float(env.get("TRADELAB_NEWS_PUSH_MINUTES") or 10))
    except ValueError:
        minutes = 10.0
    return {"token": token if token and "\n" not in token and "\r" not in token else "",
            "repo": (env.get("TRADELAB_DATA_REPO") or "alinvarat/tradelab").strip(),
            "branch": (env.get("TRADELAB_NEWS_PUSH_BRANCH") or "data/news-ingest").strip(),
            "interval_s": minutes * 60}


def enabled(env=None):
    return bool(_cfg(env)["token"])


def backoff_s(attempt, retry_after=None, rand=random.random):
    """Seconds to wait before retry number `attempt` (1-based): exponential with jitter, capped; Retry-After wins when longer."""
    wait = min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** (attempt - 1)) * (0.75 + 0.5 * rand())
    if retry_after:
        wait = max(wait, min(float(retry_after), BACKOFF_CAP_S))
    return wait


def http(method, url, token, body=None, accept="application/vnd.github+json", timeout=20):
    """-> (status, bytes, headers). Status 0 = network error. The token is never returned, logged or put in an error."""
    data = None if body is None else json.dumps(body).encode()
    req = Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tradelab-news-publish", **({"Content-Type": "application/json"} if data else {})})
    try:
        with urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except HTTPError as e:
        try:
            return e.code, e.read(), dict(e.headers)
        except Exception:  # noqa: BLE001
            return e.code, b"", {}
    except Exception:  # noqa: BLE001
        return 0, b"", {}


def call(transport, method, url, token, body=None, sleep=time.sleep, rand=random.random):
    """One API call with retries on network errors, 429, 5xx and secondary rate limits (403 with Retry-After)."""
    status, raw, hdr = 0, b"", {}
    for attempt in range(1, TRIES + 1):
        status, raw, hdr = transport(method, url, token, body)
        ra = {k.lower(): v for k, v in (hdr or {}).items()}.get("retry-after")
        if status not in RETRY_STATUS and not (status == 403 and ra):
            break
        if attempt < TRIES:
            sleep(backoff_s(attempt, ra, rand))
    return status, raw


def _j(raw):
    try:
        return json.loads(raw or b"{}")
    except ValueError:
        return {}


def ensure_branch(transport, cfg, sleep=time.sleep):
    """Make sure the data branch exists (an orphan commit with a README when it does not). -> True/False."""
    base = f"{API}/repos/{cfg['repo']}"
    st, _ = call(transport, "GET", f"{base}/git/ref/heads/{cfg['branch']}", cfg["token"], sleep=sleep)
    if st == 200:
        return True
    if st != 404:
        return False
    readme = ("Append-only copy of the Kuber pod's news-ingest log (core/news_ingest.py), written by core/news_publish.py. "
              "Public news metadata only: t_pub, t_seen, t_llm per item. Files are created once and never rewritten.\n")
    st, raw = call(transport, "POST", f"{base}/git/trees", cfg["token"],
                   {"tree": [{"path": "README.md", "mode": "100644", "type": "blob", "content": readme}]}, sleep=sleep)
    tree = _j(raw).get("sha")
    if st not in (200, 201) or not tree:
        return False
    st, raw = call(transport, "POST", f"{base}/git/commits", cfg["token"],
                   {"message": "news-ingest data branch: start", "tree": tree, "parents": [], "author": COMMITTER, "committer": COMMITTER},
                   sleep=sleep)
    commit = _j(raw).get("sha")
    if st not in (200, 201) or not commit:
        return False
    st, _ = call(transport, "POST", f"{base}/git/refs", cfg["token"], {"ref": "refs/heads/" + cfg["branch"], "sha": commit}, sleep=sleep)
    return st in (200, 201, 422)           # 422: another writer created it first


def put_part(transport, cfg, path, data, message, sleep=time.sleep):
    """Create one file. -> 'ok', 'exists' (created earlier, treated as done) or 'fail'. Never replaces an existing file."""
    st, raw = call(transport, "PUT", f"{API}/repos/{cfg['repo']}/contents/{path}", cfg["token"],
                   {"message": message, "content": base64.b64encode(data).decode(), "branch": cfg["branch"],
                    "committer": COMMITTER, "author": COMMITTER}, sleep=sleep)
    if st in (200, 201):
        return "ok"
    if st == 422 and b"sha" in (raw or b""):         # "sha wasn't supplied": the file is already there
        return "exists"
    return "fail"


def read_cursor(dirpath):
    try:
        d = json.loads((Path(dirpath) / CURSOR_NAME).read_text())
        return {str(k): int(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def write_cursor(dirpath, cur):
    p = Path(dirpath) / CURSOR_NAME
    tmp = p.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(cur, sort_keys=True))
        os.replace(tmp, p)
    except OSError:
        pass


def pending(dirpath, cursor, max_part=MAX_PART_BYTES, max_total=MAX_BYTES_PER_CYCLE, max_files=MAX_FILES_PER_CYCLE):
    """Unpublished whole lines, oldest day first: [(day, start, end, bytes)]. A part never ends inside a line, so the
    writer thread appending at the same moment cannot produce a torn row."""
    out, total = [], 0
    files = sorted(Path(dirpath).glob("2???????.jsonl")) if Path(dirpath).exists() else []
    for f in files:
        if len(out) >= max_files or total >= max_total:
            break
        start = cursor.get(f.stem, 0)
        try:
            size = f.stat().st_size
            if size <= start:
                continue
            with open(f, "rb") as fh:
                fh.seek(start)
                chunk = fh.read(min(max_part, max_total - total, size - start))
        except OSError:
            continue
        cut = chunk.rfind(b"\n") + 1
        if cut == 0:
            continue                                  # no complete line yet (or one line longer than a part: wait)
        chunk = chunk[:cut]
        out.append((f.stem, start, start + cut, chunk))
        total += cut
    return out


def part_path(day, start, end):
    return f"news_ingest/{day}/{start:010d}-{end:010d}.jsonl"


def cycle(dirpath, transport=http, env=None, sleep=time.sleep):
    """One publish pass. Never raises. -> dict with the outcome; updates STATE (no secrets in it)."""
    cfg = _cfg(env)
    res = {"enabled": bool(cfg["token"]), "parts": 0, "bytes": 0, "ok": True, "error": None}
    with _lock:
        STATE.update(enabled=res["enabled"], branch=cfg["branch"], repo=cfg["repo"])
    if not cfg["token"]:
        return res
    try:
        cursor = read_cursor(dirpath)
        todo = pending(dirpath, cursor)
        if todo:
            if not ensure_branch(transport, cfg, sleep):
                raise RuntimeError("data branch not reachable")
            for day, start, end, data in todo:
                n = data.count(b"\n")
                r = put_part(transport, cfg, part_path(day, start, end), data, f"news-ingest {day} +{n} rows", sleep)
                if r == "fail":
                    raise RuntimeError("upload failed for " + part_path(day, start, end))
                cursor[day] = end
                write_cursor(dirpath, cursor)
                res["parts"] += 1
                res["bytes"] += len(data)
    except Exception as exc:  # noqa: BLE001
        res.update(ok=False, error=(type(exc).__name__ + ": " + str(exc)).replace(cfg["token"], "***")[:120])   # never a token
    with _lock:
        STATE["cycles"] += 1
        STATE["parts"] += res["parts"]
        STATE["bytes"] += res["bytes"]
        STATE["last_cycle"] = time.time()
        if res["ok"]:
            STATE["consecutive_failures"] = 0
            if res["parts"]:
                STATE["last_ok_utc"] = time.time()
            STATE["last_error"] = None
        else:
            STATE["failures"] += 1
            STATE["consecutive_failures"] += 1
            STATE["last_error"] = res["error"]
    return res


def view():
    with _lock:
        s = dict(STATE)
    s["enabled"] = enabled()
    if not s["enabled"]:
        s["reason"] = f"no {TOKEN_ENV} in the environment: the log stays on the pod volume only"
    return s


def loop(dirpath=None, transport=http, sleep=time.sleep):
    """Daemon-thread body: publish every N minutes, back off after failures, never exit, never raise."""
    from . import news_ingest
    while True:
        cfg = _cfg()
        wait = cfg["interval_s"]
        try:
            if cfg["token"]:
                r = cycle(dirpath or news_ingest.DIR, transport, sleep=sleep)
                if not r["ok"]:
                    with _lock:
                        n = STATE["consecutive_failures"]
                    wait = min(FAIL_SLEEP_CAP_S, wait * 2 ** min(n, 6))
            else:
                wait = max(wait, 600)
        except Exception:  # noqa: BLE001
            wait = max(wait, 600)
        sleep(wait * (0.9 + 0.2 * random.random()))
