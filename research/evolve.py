"""The owner's idea, done safely: trade the past, change the method, repeat, keep what works.
An evolutionary search over news-shock trading rules. Each generation mutates the best rules found so far.

Three time blocks:
  search    2010-2016  rules are scored here and evolved
  validate  2017-2020  only the survivors are checked here (a rule must also work here to be kept)
  lockbox   2021-2026  opened ONCE at the end for the final pick, to show what repeated searching really earns
Every trial is counted. Costs 0.20% per round trip. Universe: today's large caps (survivorship bias: stocks that
collapsed and left the index are missing, which flatters buying after drops).  python3 -m research.evolve"""
import json
import math
import random
from pathlib import Path

from research import events as E

SPACE = {
    "dir": ["down", "up"], "gap": [0.03, 0.04, 0.05, 0.06, 0.08, 0.10], "vmult": [1.5, 2.0, 2.5, 3.0, 4.0],
    "day": ["any", "follow", "reverse"], "trend": ["any", "falling", "rising"], "hold": [1, 5, 10, 20, 40, 60],
    "side": ["long", "short"],
}
BLOCKS = {"search": ("2010", "2016-12-31"), "validate": ("2017", "2020-12-31"), "lockbox": ("2021", "9999")}
COST = 0.002
OUT = Path(__file__).resolve().parent


def match(e, r):
    if (e["gap"] < 0) != (r["dir"] == "down") or abs(e["gap"]) < r["gap"] or e["vm"] < r["vmult"]:
        return False
    same = (e["day"] < 0) == (e["gap"] < 0)
    if r["day"] == "follow" and not same or r["day"] == "reverse" and same:
        return False
    if r["trend"] == "falling" and e["trend"] >= 0 or r["trend"] == "rising" and e["trend"] < 0:
        return False
    return True


def score(evs, r, block):
    lo, hi = BLOCKS[block]
    rets = []
    for e in evs:
        if lo <= e["d"] <= hi and match(e, r):
            x = e["fwd"].get(r["hold"])
            if x is not None:
                rets.append((x if r["side"] == "long" else -x) - COST)
    n = len(rets)
    if n < 15:
        return {"n": n, "mean": 0.0, "t": -9.0}
    m = sum(rets) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in rets) / (n - 1)) or 1e-9
    return {"n": n, "mean": m * 100, "t": m / (sd / math.sqrt(n)), "win": sum(v > 0 for v in rets) / n * 100}


def mutate(r, rng):
    r = dict(r)
    k = rng.choice(list(SPACE))
    r[k] = rng.choice(SPACE[k])
    return r


def key(r):
    return json.dumps(r, sort_keys=True)


def main(gens=40, pop=60, seed=7):
    spy, allb = E.load_all()
    raw = E.find_events(allb, gap=0.03, vmult=1.5)
    evs = []
    for e in raw:
        b = allb[e["s"]]
        avgv = sum(x["v"] for x in b[e["i"] - 50:e["i"]]) / 50
        f = {}
        for h in SPACE["hold"]:
            x = E.fwd(b, spy, e["i"], h)
            if x:
                f[h] = x[1]  # raw return: what a trade actually earns
        evs.append({**e, "vm": b[e["i"]]["v"] / avgv, "fwd": f})
    rng = random.Random(seed)
    seen, history = {}, []
    popn = [{k: rng.choice(v) for k, v in SPACE.items()} for _ in range(pop)]
    for g in range(gens):
        for r in popn:
            if key(r) not in seen:
                seen[key(r)] = (r, score(evs, r, "search"))
        ranked = sorted(seen.values(), key=lambda x: -x[1]["t"])
        best = ranked[0]
        history.append({"gen": g + 1, "trials": len(seen), "best_search_t": best[1]["t"], "best_search_mean": best[1]["mean"]})
        elite = [r for r, _ in ranked[:10]]
        popn = elite + [mutate(rng.choice(elite), rng) for _ in range(pop - len(elite))]
    ranked = sorted(seen.values(), key=lambda x: -x[1]["t"])
    top = []
    for r, s in ranked[:50]:
        v = score(evs, r, "validate")
        top.append({"rule": r, "search": s, "validate": v})
    survivors = [x for x in top if x["validate"]["t"] > 2 and x["validate"]["mean"] > 0]
    pick = max(survivors, key=lambda x: x["validate"]["t"] + x["search"]["t"]) if survivors else None
    for x in top[:10] + ([pick] if pick else []):
        x["lockbox"] = score(evs, x["rule"], "lockbox")
    res = {"events": len(evs), "trials": len(seen), "history": history, "top10": top[:10],
           "survivors": len(survivors), "pick": pick}
    (OUT / "result_evolve.json").write_text(json.dumps(res, indent=1))
    return res


def show(res):
    print(f"{res['events']} shock events, {res['trials']} rules tried over {len(res['history'])} generations")
    for h in res["history"][::8] + [res["history"][-1]]:
        print(f"  gen {h['gen']:3}  trials {h['trials']:5}  best search: {h['best_search_mean']:+.2f}%/trade t {h['best_search_t']:.1f}")
    print("Top 10 by the search block, then their validate and lockbox results (mean net %/trade, t):")
    for x in res["top10"]:
        s, v, l = x["search"], x["validate"], x["lockbox"]
        print(f"  {json.dumps(x['rule'])}\n     search {s['mean']:+.2f} t{s['t']:.1f} n{s['n']} | validate {v['mean']:+.2f} t{v['t']:.1f} n{v['n']} | lockbox {l['mean']:+.2f} t{l['t']:.1f} n{l['n']}")
    print(f"Survivors (validate t>2): {res['survivors']}")
    if res["pick"]:
        p = res["pick"]
        print(f"PICK {json.dumps(p['rule'])}: search {p['search']['mean']:+.2f}% t{p['search']['t']:.1f}, validate "
              f"{p['validate']['mean']:+.2f}% t{p['validate']['t']:.1f}, LOCKBOX {p['lockbox']['mean']:+.2f}% t{p['lockbox']['t']:.1f} n{p['lockbox']['n']}")


if __name__ == "__main__":
    show(main())
