"""Enumerate hindsight asset, direction and skip choices on frozen weekly tape."""
import json
from itertools import product

from .options import WALLET
from .options_rotation import choices, inputs
from .options_weekly import HERE, month_run, reached


def best(weeks, sales, target, costs):
    menus = [[(None, "cash", None), *((row, asset, side)
              for _, asset, row in picks for side in "CP")]
             for picks in weeks]
    top, selection = WALLET, []
    for path in product(*menus):
        picked = [(row, asset, side) for row, asset, side in path if row is not None]
        balance = month_run([r for r, _, _ in picked], sales, target, costs, WALLET,
                            sides=[side for _, _, side in picked], budget_fraction=.5)
        if balance > top:
            top = balance
            selection = picked
    _, replay = month_run([r for r, _, _ in selection], sales, target, costs, WALLET,
                          sides=[side for _, _, side in selection], budget_fraction=.5, detail=True)
    return {"end": top, "hit": reached(top, WALLET * target),
            "decisions": [[r["entry_day"], asset, side] for r, asset, side in selection],
            "trades": replay}


def main():
    grouped, sales, sources = inputs()
    weeks = choices(grouped)
    months = [f"{y}-{m:02d}" for y,n in ((2025,12),(2026,10)) for m in range(1,n+1)]
    output = {"hindsight_only": True, "start_each_month": WALLET, "input_sha256": sources, "cases": {}}
    for target in (3,6):
        for name, costs in (("base", (.15,.05)), ("stress", (.35,.15))):
            values = {m: best(weeks[m], sales, target, costs) for m in months}
            output["cases"][f"{target}x_{name}"] = values
    (HERE / "options_weekly_ceiling_results.json").write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
