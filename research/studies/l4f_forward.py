"""Run one L4f poll on GitHub Actions (Kuber cannot reach the Polymarket API: connection reset).
Usage: python research/studies/l4f_forward.py <state_dir>   (state_dir holds polymarket_longshot_state.json)"""
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from core import market_collect as mc   # noqa: E402


def main():
    d = Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    mc.DIR = d
    mc.UA = mc.BROWSER_UA
    st = mc.l4f_once()
    view = mc.ledger_view("l4f")
    (d / "l4f_summary.json").write_text(json.dumps({k: v for k, v in view.items() if k != "closed"} | {
        "closed_last": view["closed"][-10:], "last_error": mc.STATUS["listings"]["last_error"]}, indent=1, default=str))
    print(json.dumps({"equity": st["equity"], "pending": len(st["pending"]), "closed": len(st["closed"]),
                      "error": mc.STATUS["listings"]["last_error"]}))


if __name__ == "__main__":
    main()
