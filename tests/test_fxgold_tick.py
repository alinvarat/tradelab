import unittest
from array import array

from core import fxgold_tick as ft


def bars(n, px=1.1, sp=0.0001):
    D = {"ts": array("q", [1_700_000_000 - 1_700_000_000 % 60 + 60 * i for i in range(n)])}
    for k in ("bo", "bh", "bl", "bc"):
        D[k] = array("d", [px] * n)
    for k in ("ao", "ah", "al", "ac"):
        D[k] = array("d", [px + sp] * n)
    return D


class RunTrade(unittest.TestCase):
    def test_flat_long_pays_spread(self):
        D = bars(10)
        t = ft.run_trade(D, "EURUSD", 1, 1, 0.01, None, None, 5)
        self.assertAlmostEqual(t["gross"], 0.0, places=9)           # mid to mid, flat market
        self.assertAlmostEqual(t["cost"], 0.0002 / 1.1001, places=7)  # XM Standard spread is wider than 1 pip
        self.assertLess(t["net"], 0)

    def test_stop_hit_long(self):
        D = bars(10)
        D["bl"][3] = 1.08
        t = ft.run_trade(D, "EURUSD", 1, 1, 0.01, None, None, 8)
        self.assertEqual(t["x"], D["ts"][3] + 60)
        self.assertLess(t["gross"], -0.008)

    def test_target_short(self):
        D = bars(10)
        D["al"][2] = 1.09
        t = ft.run_trade(D, "EURUSD", 1, -1, 0.05, 0.01, None, 8)
        self.assertGreater(t["gross"], 0.008)

    def test_rules_registered(self):
        r = ft.build_rules()
        self.assertEqual(len(r), 36 + 4 + 4 + 4 + 8)


if __name__ == "__main__":
    unittest.main()
