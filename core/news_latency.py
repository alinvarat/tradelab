"""Short-horizon news-latency evaluation: after WE first see a headline, is there a tradable move at +1m/+5m?

Reads the rows written by core.news_archive.settle_latency. Each row has the event stock's return and a deterministic
random control stock's return, both vs SPY over the same interval. The event side pays a round-trip cost (0.05% fee +
0.02% slippage per side) before comparison. Nothing is concluded before `needed` complete pairs per horizon."""
import json
import random
import time
from pathlib import Path
from statistics import mean

from . import news_archive

NEEDED = 100
COST_ROUND_TRIP = 0.0014          # 0.05% fee + 0.02% slippage per side
_CACHE = {"ts": 0.0, "mtime": None, "data": None}


def _rows(path, horizon):
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("horizon") == horizon:
            out.append(r)
    return out


def _stats(rows, needed, cost):
    complete = [r for r in rows if r.get("control_abnormal") is not None]
    out = {"events": len(rows), "complete_pairs": len(complete), "needed": needed,
           "cost_round_trip_pct": cost * 100}
    if complete:
        event = [r["abnormal"] for r in complete]
        ctrl = [r["control_abnormal"] for r in complete]
        diff = [e - c for e, c in zip(event, ctrl)]
        net = [e - cost - c for e, c in zip(event, ctrl)]
        out |= {"mean_event": mean(event), "mean_control": mean(ctrl), "mean_diff": mean(diff),
                "mean_net": mean(net), "share_positive_net": sum(x > 0 for x in net) / len(net)}
        rng = random.Random(20261123)
        boots = sorted(mean(rng.choice(net) for _ in net) for _ in range(2000))
        out["net_ci95"] = (boots[50], boots[1949])
    if len(complete) < needed:
        out["verdict"] = f"too early ({len(complete)}/{needed} complete pairs): no conclusion allowed"
    elif out.get("mean_net", 0) > 0 and out["net_ci95"][0] > 0:
        out["verdict"] = "edge candidate (needs a second non-overlapping window)"
    else:
        out["verdict"] = "no edge shown"
    return out


def evaluate(path=None, needed=NEEDED, cost=COST_ROUND_TRIP, use_cache=True):
    path = Path(path or news_archive.LATENCY_LABELS)
    if use_cache and _CACHE["data"] is not None and _CACHE["mtime"] == (path.stat().st_mtime if path.exists() else None) \
            and time.time() - _CACHE["ts"] < 60:
        return _CACHE["data"]
    out = {"needed": needed, "file": path.name, "horizons": {}}
    for h in news_archive.LATENCY:
        out["horizons"][h] = _stats(_rows(path, h), needed, cost)
    if use_cache:
        _CACHE.update(ts=time.time(), mtime=path.stat().st_mtime if path.exists() else None, data=out)
    return out


if __name__ == "__main__":
    print(json.dumps(evaluate(use_cache=False), indent=1))
