"""Walk-forward comparison of portfolio methods. python3 -m research.run_research"""
import itertools
import json
import sys
from pathlib import Path

from core import research as R

ETF = ["SPY", "QQQ", "EFA", "EEM", "TLT", "IEF", "GLD", "DBC", "VNQ"]
GRID = {
    "buy_hold": [{"asset": "SPY"}],
    "sixty_forty": [{}],
    "equal_weight": [{}],
    "trend_sma": [{"sma": n} for n in (100, 150, 200, 250)],
    "dual_mom": [{"lookback": lb, "top": k} for lb in (63, 126, 189, 252) for k in (1, 2, 3)],
    "tsmom_vt": [{"lookback": lb, "target_vol": tv} for lb in (126, 252) for tv in (0.10, 0.15)],
    "rsi2": [{"entry": e} for e in (5, 10, 15)],
    "tom": [{}],
}
TRAIN_END, TEST_START = "2016-12-31", "2017-01-01"


def main(with_btc=False):
    uni = ETF + (["BTC-USD"] if with_btc else [])
    days, px = R.panel(uni + ["SHY"], "2004-01-01")
    a = next(i for i, d in enumerate(days) if d >= "2006-01-01")
    split = max(i for i, d in enumerate(days) if d <= TRAIN_END)
    end = len(days) - 1
    out = []
    for name, grid in GRID.items():
        res = []
        for p in grid:
            curve, turn = R.run(days, px, R.make_rule(name, days, px, uni, p))
            res.append({"p": p, "train": R.stats(days, curve, a, split), "test": R.stats(days, curve, split, end),
                        "trials": len(grid)})
        best = max(res, key=lambda r: r["train"]["sharpe"])
        avg_test = sum(r["test"]["cagr"] for r in res) / len(res)
        out.append({"method": name, "chosen": best["p"], "train": best["train"], "test": best["test"],
                    "avg_test_cagr_all_params": avg_test, "trials": len(grid)})
    return {"universe": uni, "train": f"{days[a]}..{days[split]}", "test": f"{days[split]}..{days[end]}", "rows": out}


if __name__ == "__main__":
    for btc in (False, True):
        r = main(btc)
        print(f"\nUniverse {r['universe']}\ntrain {r['train']}  test {r['test']}")
        print(f"{'method':14}{'params':34}{'trainCAGR':>10}{'trSharpe':>9}{'testCAGR':>10}{'teSharpe':>9}{'testMDD':>9}{'worstYr':>9}{'posYrs':>8}{'avgAllP':>9}")
        for x in r["rows"]:
            t, s = x["train"], x["test"]
            print(f"{x['method']:14}{json.dumps(x['chosen']):34}{t['cagr']:10.1f}{t['sharpe']:9.2f}{s['cagr']:10.1f}{s['sharpe']:9.2f}{s['mdd']:9.1f}{s['worst_year']:9.1f}{s['pos_years']:>8}{x['avg_test_cagr_all_params']:9.1f}")
        Path(f"research/result_{'btc' if btc else 'etf'}.json").write_text(json.dumps(r, indent=1))
