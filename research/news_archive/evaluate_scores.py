"""Evaluate AI vs lexicon headline scores against SPY-relative returns (see score_protocol.md)."""
import json
import math
from pathlib import Path
import random

DATA = Path(__file__).parent / "data"
NEEDED = 200


def ranks(x):
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    return cov / math.sqrt(va * vb) if va and vb else 0.0


def load(data=DATA, horizon="1d"):
    scores = {}
    path = data / "ai_scores.jsonl"
    for line in path.read_text().splitlines() if path.exists() else []:
        r = json.loads(line)
        if r["confidence"] >= 0.3:
            scores[r["key"]] = r
    seen, rows = set(), []
    path = data / "labels.jsonl"
    for line in path.read_text().splitlines() if path.exists() else []:
        r = json.loads(line)
        if r["horizon"] == horizon and r["key"] in scores and r["key"] not in seen:
            seen.add(r["key"])  # first symbol only
            rows.append((scores[r["key"]]["score"], scores[r["key"]]["lexicon"], r["abnormal"]))
    return rows


def evaluate(rows, seed=20261123):
    out = {"pairs": len(rows), "needed": NEEDED}
    if len(rows) < NEEDED:
        out["verdict"] = f"too early ({len(rows)}/{NEEDED} usable pairs): no conclusion allowed"
        return out
    rng = random.Random(seed)
    ai, lex = [r[0] for r in rows], [r[1] for r in rows]
    ret = [r[2] for r in rows]
    boots = []
    for _ in range(2000):
        idx = [rng.randrange(len(rows)) for _ in rows]
        a, l, y = [ai[i] for i in idx], [lex[i] for i in idx], [ret[i] for i in idx]
        boots.append((spearman(a, y), spearman(l, y)))
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))]
    ai_c, lex_c = spearman(ai, ret), spearman(lex, ret)
    ai_ci = (q([b[0] for b in boots], .025), q([b[0] for b in boots], .975))
    diff_ci = (q([b[0] - b[1] for b in boots], .025), q([b[0] - b[1] for b in boots], .975))
    out |= {"ai_corr": ai_c, "ai_ci": ai_ci, "lexicon_corr": lex_c, "diff_ci": diff_ci}
    useful = ai_c > 0 and ai_ci[0] > 0 and diff_ci[0] > 0
    out["verdict"] = ("AI score useful in this window (needs a later window)" if useful
                      else "no demonstrated advantage")
    return out


if __name__ == "__main__":
    print(json.dumps(evaluate(load()), indent=1))
