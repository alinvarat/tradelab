"""Forward paper ledger notice_fwd (protocol_notice_fwd_20261126.md). Runs on GitHub Actions only (workflow notice_fwd.yml, dispatched by
keeper.yml every 30 minutes). Public OKX data and the pod's published log, no keys, no orders.

    python research/studies/notice_fwd.py counts <ingest_root> <out_dir>      outcome-free: counts and latencies per source, no price
    python research/studies/notice_fwd.py forward <ingest_root> <state_dir>   enters new notices, settles matured ones, rewrites summary.json
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import notice_fwd as nf   # noqa: E402
from research.news_train import ingest_branch as ib   # noqa: E402

OKX = "https://www.okx.com/api/v5"
UA = {"User-Agent": "Mozilla/5.0 tradelab-research", "Accept": "application/json"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(path, tries=3):
    last = None
    for k in range(tries):
        try:
            with urlopen(Request(OKX + path, headers=UA), timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:   # noqa: BLE001
            last = e
            time.sleep(1 + k)
    log(f"GET {path.split('?')[0]} failed: {type(last).__name__} {last}")
    return None


def perps():
    d = get("/public/instruments?instType=SWAP") or {}
    return {x["instId"] for x in d.get("data") or [] if x.get("instId", "").endswith("-USDT-SWAP") and x.get("state") == "live"}


def get_page(inst, after_ms):
    time.sleep(0.12)
    d = get(f"/market/history-trades?instId={inst}&type=2&after={int(after_ms)}&limit=100") or {}
    out = []
    for x in d.get("data") or []:
        try:
            out.append({"ts": int(x["ts"]), "px": float(x["px"])})
        except (KeyError, TypeError, ValueError):
            pass
    return out


def tape(inst, t):
    return nf.tape_fill(get_page, inst, t)


def bars_for(inst, t):
    time.sleep(0.12)
    b = int(-(-t // 60) * 60)
    d = get(f"/market/history-candles?instId={inst}&bar=1m&after={(b + 1) * 1000}&limit=3") or {}
    out = {}
    for r in d.get("data") or []:
        try:
            out[int(r[0]) // 1000] = float(r[1])
        except (IndexError, TypeError, ValueError):
            pass
    return out


def counts(ingest_root, out_dir, state=None):
    joined = ib.join(ib.load_rows(ingest_root))
    table = nf.latency_table(joined)
    slow = nf.slow_sources(table, (state or {}).get("slow_sources", ()))
    cls = nf.clusters(joined, slow)
    by_status = {}
    for c in cls:
        k = f"{c['cls']}:{'fast' if c['eligible'] else 'too_slow'}"
        by_status[k] = by_status.get(k, 0) + 1
    res = {"updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "items_total": len(joined), "sources": table,
           "slow_sources": slow, "clusters": len(cls), "clusters_by_class_and_speed": dict(sorted(by_status.items())),
           "korean_notices_seen": sum(1 for c in cls if c["cls"].startswith("kr_")),
           "pub_gap_s_eqn_minus_direct": [c["pub_gap_s"] for c in cls if c["pub_gap_s"] is not None]}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "counts.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return joined, table, slow, cls, res


def forward(ingest_root, sd):
    sd = Path(sd)
    sd.mkdir(parents=True, exist_ok=True)
    state = json.loads((sd / "state.json").read_text()) if (sd / "state.json").exists() else {}
    joined, table, slow, cls, res = counts(ingest_root, sd, state)
    state["slow_sources"] = slow
    now = time.time()
    ledger = nf.Ledger(state.get("ledger"))
    st, rows, notices = nf.step(state, cls, now, perps(), tape, bars_for)
    for r in rows:
        ledger.add(r)
    st["ledger"] = ledger.dump()
    (sd / "state.json").write_text(json.dumps(st))
    for name, items in (("trades.jsonl", rows), ("notices.jsonl", notices)):
        with open(sd / name, "a") as f:
            for x in items:
                f.write(json.dumps(x, separators=(",", ":")) + "\n")
    allrows = [json.loads(x) for x in (sd / "trades.jsonl").read_text().splitlines() if x.strip()]
    ep = nf.sq.EProcess(alpha=nf.ALPHA, lo=nf.CLIP, hi=nf.CLIP, paired=True)
    ep.__dict__.update(ledger.dump())
    summary = {**res, "meta": st["meta"], "pending": len(st["pending"]), "verdict": nf.verdict(allrows, ep.view(), time.strftime("%Y-%m-%d", time.gmtime()))}
    (sd / "summary.json").write_text(json.dumps(summary, indent=1))
    log(json.dumps({"meta": summary["meta"], "verdict": summary["verdict"]})[:1500])
    return summary


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in ("counts", "forward"):
        sys.exit(__doc__)
    (counts if sys.argv[1] == "counts" else forward)(sys.argv[2], sys.argv[3])
