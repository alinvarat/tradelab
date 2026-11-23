"""Run the locked protocol.md: variants V0-V3 on train/validation, choose, then open the test once."""
from datetime import date
import json
import math
from pathlib import Path

from core import research as R

HERE = Path(__file__).parent
UNI = ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ", "BTC-USD"]
LOOKBACKS = (21, 63, 126, 252)
VOLT = 0.12


def inv_vol(px, s, i):
    r = [px[s][j] / px[s][j - 1] - 1 for j in range(max(1, i - 62), i + 1) if px[s][j] and px[s][j - 1]]
    v = R._std(r) if len(r) > 5 else 0
    return 1 / v if v else 0


def port_vol(px, w, i):
    rets = []
    for j in range(max(1, i - 62), i + 1):
        rets.append(sum(wt * (px[s][j] / px[s][j - 1] - 1) for s, wt in w.items() if px[s][j] and px[s][j - 1]))
    return R._std(rets) * math.sqrt(252) if len(rets) > 5 else 0


def ensemble(px, i, guard, smas):
    if i < max(LOOKBACKS):
        return {}
    cash = {lb: px["SHY"][i] / px["SHY"][i - lb] - 1 for lb in LOOKBACKS}
    cand = []
    for s in UNI:
        if px[s][i] is None or any(px[s][i - lb] is None for lb in LOOKBACKS):
            continue
        rets = [px[s][i] / px[s][i - lb] - 1 for lb in LOOKBACKS]
        votes = sum(r > cash[lb] for r, lb in zip(rets, LOOKBACKS))
        if votes >= 3 and (not guard or (smas[s][i] is not None and px[s][i] > smas[s][i])):
            cand.append((sum(rets) / len(rets), s))
    top = [s for _, s in sorted(cand, reverse=True)[:4]]
    iv = {s: inv_vol(px, s, i) for s in top}
    tot = sum(iv.values())
    return {s: v / tot for s, v in iv.items()} if tot else {}


def rule(name, days, px):
    me = R.month_ends(days)
    smas = {s: R._sma_none(px[s], 200) for s in UNI}

    def f(i, prev):
        if i not in me and prev is not None:
            return prev
        if name == "V0":
            return R.dual_weights(px, UNI, i, 63, 3)
        w = ensemble(px, i, name == "V3", smas)
        if name in ("V2", "V3") and w:
            vol = port_vol(px, w, i)
            scale = min(1.0, VOLT / vol) if vol else 1.0
            w = {s: v * scale for s, v in w.items()}
            if scale < 1:
                w["SHY"] = 1 - scale
        return w
    return f


def main():
    days, px = R.panel(UNI + ["SHY"], "2004-01-01")
    idx = lambda d: next(i for i, x in enumerate(days) if x >= d)
    periods = {"train": ("2005-02-01", "2018-12-31"), "valid": ("2019-01-01", "2022-12-31"), "test": ("2023-01-01", days[-1])}
    ends = {k: (idx(a), max(i for i, x in enumerate(days) if x <= b)) for k, (a, b) in periods.items()}
    curves = {n: R.run(days, px, rule(n, days, px))[0] for n in ("V0", "V1", "V2", "V3")}
    spy = [px["SPY"][i] / px["SPY"][0] for i in range(len(days))]
    spy = [v if v == v else 1 for v in spy]
    out = {"asof": date.today().isoformat(), "days": [days[0], days[-1]], "train_valid": {}}
    for n, c in curves.items():
        out["train_valid"][n] = {p: R.stats(days, c, *ends[p]) for p in ("train", "valid")}
    out["train_valid"]["SPY"] = {p: R.stats(days, spy, *ends[p]) for p in ("train", "valid")}
    base = out["train_valid"]["V0"]["valid"]
    ok = {n: v["valid"] for n, v in out["train_valid"].items() if n not in ("V0", "SPY")
          and v["valid"]["sharpe"] > base["sharpe"] and v["valid"]["mdd"] <= base["mdd"]}
    choice = max(ok, key=lambda n: ok[n]["sharpe"]) if ok else "V0"
    out["choice"] = choice
    (HERE / "choice_before_test.json").write_text(json.dumps({"choice": choice, "train_valid": out["train_valid"]}, indent=1))
    out["test"] = {n: R.stats(days, c, *ends["test"]) for n, c in curves.items()}
    out["test"]["SPY"] = R.stats(days, spy, *ends["test"])
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    show = lambda s: "cagr %5.1f vol %4.1f sharpe %4.2f mdd %5.1f worst_yr %6.1f pos %s" % (
        s["cagr"], s["vol"], s["sharpe"], s["mdd"], s["worst_year"], s["pos_years"])
    for p in ("train", "valid"):
        print("==", p)
        for n in ("V0", "V1", "V2", "V3", "SPY"):
            print(n, show(out["train_valid"][n][p]))
    print("choice:", choice)
    print("== test")
    for n in ("V0", "V1", "V2", "V3", "SPY"):
        print(n, show(out["test"][n]))


if __name__ == "__main__":
    main()
