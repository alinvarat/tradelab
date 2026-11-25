import json
import math
import os
import random
import unittest

from core import sweep_config as sc
from core import sweep_meta as sm

T0 = sc.day("2023-01-01")
DAY = 86400


def trade(rule, i, net, src="s", dur=3600, t0=T0):
    t = t0 + i * DAY
    return {"src": src, "rule": rule, "t": t, "x": t + dur, "net": net}


class Pieces(unittest.TestCase):
    def test_pav(self):
        self.assertEqual(sm.pav_increasing([1.0, 3.0, 2.0, 4.0], [1, 1, 1, 1]), [1.0, 2.5, 2.5, 4.0])
        self.assertEqual(sm.pav_increasing([3.0, 1.0], [1, 3]), [1.5, 1.5])
        self.assertEqual(sm.pav_increasing([1.0, 2.0, 3.0], [1, 1, 1]), [1.0, 2.0, 3.0])

    def test_trailing_means_use_only_closed_trades(self):
        tr = [trade("R", i, float(i)) for i in range(5)]
        out = sm.trailing_means([dict(z) for z in tr], 3)
        by_i = {int((z["t"] - T0) // DAY): z["m"] for z in out}
        self.assertIsNone(by_i[0])
        self.assertIsNone(by_i[2])
        self.assertAlmostEqual(by_i[3], (0 + 1 + 2) / 3)            # trade 3 sees trades 0..2, not itself
        self.assertAlmostEqual(by_i[4], (1 + 2 + 3) / 3)
        # a trade still open at the entry of the next one is not counted
        slow = [trade("R", i, 1.0, dur=3 * DAY) for i in range(6)]
        out2 = {int((z["t"] - T0) // DAY): z["m"] for z in sm.trailing_means([dict(z) for z in slow], 2)}
        self.assertIsNone(out2[3])                                   # at day 3 only trade 0 (exit day 3) is closed: x <= t counts it, trade 1 exits day 4
        self.assertEqual(out2[4], 1.0)                               # trades 0 and 1 closed
        # future changes do not change the past: remove the last trade, earlier m values are identical
        a = {z["t"]: z["m"] for z in sm.trailing_means([dict(z) for z in tr], 3)}
        b = {z["t"]: z["m"] for z in sm.trailing_means([dict(z) for z in tr[:4]], 3)}
        for t, m in b.items():
            self.assertEqual(a[t], m)

    def test_rules_are_separate(self):
        tr = [trade("A", i, 1.0) for i in range(5)] + [trade("B", i, -1.0) for i in range(5)]
        out = {(z["rule"], int((z["t"] - T0) // DAY)): z["m"] for z in sm.trailing_means(tr, 3)}
        self.assertEqual(out[("A", 4)], 1.0)
        self.assertEqual(out[("B", 4)], -1.0)

    def test_fit_scorer_monotone_and_cut(self):
        r = random.Random(1)
        rows = []
        for i in range(500):
            m = r.uniform(-1, 1)
            rows.append({"m": m, "net": m * 0.5 + r.gauss(0, 0.2)})
        sc_ = sm.fit_scorer(rows, 10)
        iso = [b["iso"] for b in sc_["bins"]]
        self.assertEqual(iso, sorted(iso))
        self.assertGreater(sc_["top_value"], 0)
        top_n = sum(1 for z in rows if z["m"] >= sc_["cut"])
        self.assertTrue(45 <= top_n <= 55)
        self.assertIsNone(sm.fit_scorer(rows[:20], 10))

    def test_select(self):
        ts = [{"m": None, "net": 1}, {"m": -0.1, "net": 1}, {"m": 0.2, "net": 1}, {"m": 0.5, "net": 1}]
        self.assertEqual(len(sm.select(ts, "trailing")), 2)
        sc_ = {"cut": 0.4, "top_value": 0.1}
        self.assertEqual([z["m"] for z in sm.select(ts, "decile", sc_)], [0.5])
        self.assertEqual(sm.select(ts, "decile", {"cut": 0.4, "top_value": -0.1}), [])
        self.assertEqual(sm.select(ts, "decile", None), [])

    def test_control_p(self):
        rng = random.Random(3)
        uni = [0.0] * 50 + [1.0] * 50
        self.assertLess(sm.control_p([1.0] * 30, uni, 500, rng), 0.01)
        self.assertGreater(sm.control_p([0.0] * 30, uni, 500, rng), 0.9)
        self.assertEqual(sm.control_p([], uni, 10, rng), 1.0)


class Evaluate(unittest.TestCase):
    bounds = {"train": [T0, T0 + 300 * DAY], "validation": [T0 + 300 * DAY, T0 + 500 * DAY], "test": [T0 + 500 * DAY, T0 + 700 * DAY]}

    def pool(self):
        out = []
        for i in range(700):
            out.append(trade("good", i, 0.01 + 0.001 * math.sin(i)))
            out.append(trade("bad", i, -0.01 + 0.001 * math.sin(i)))
        return out

    def test_persistent_rule_is_selected_and_beats_random(self):
        res = sm.evaluate(self.pool(), self.bounds, window=60, bins=4, draws=500, seed=1, min_trades=30, alpha=0.05)
        for strat in ("trailing", "decile"):
            r = res[strat]
            self.assertEqual(r["status"], "ok")
            self.assertTrue(r["passed"], (strat, r["criteria"]))
            self.assertAlmostEqual(r["splits"]["validation"]["mean"], 0.01, places=2)
            self.assertAlmostEqual(r["splits"]["validation"]["universe_mean"], 0.0, places=2)
        self.assertIsNotNone(res["decile"]["scorer"])
        self.assertIsNone(res["trailing"]["scorer"])

    def test_two_losing_rules_select_nothing(self):
        pool = [trade("a", i, -0.01) for i in range(700)] + [trade("b", i, -0.02) for i in range(700)]
        res = sm.evaluate(pool, self.bounds, window=60, bins=10, draws=200, seed=1, min_trades=30, alpha=0.05)
        self.assertFalse(res["trailing"]["passed"])
        self.assertEqual(res["trailing"]["splits"]["test"]["n"], 0)
        self.assertEqual(res["decile"]["splits"]["test"]["n"], 0)               # top bin value is negative: no trades

    def test_thin_pool_is_gated(self):
        res = sm.evaluate([trade("a", i, 0.01) for i in range(80)], self.bounds, draws=50)
        self.assertEqual(res["trailing"]["status"], "gate")

    def test_scorer_never_sees_validation_or_test(self):
        pool = self.pool()
        base = sm.evaluate(pool, self.bounds, draws=200, seed=2)["decile"]["scorer"]
        flipped = [dict(z, net=-z["net"]) if z["t"] >= self.bounds["validation"][0] else z for z in pool]
        again = sm.evaluate(flipped, self.bounds, draws=200, seed=2)["decile"]["scorer"]
        self.assertEqual(base["cut"], again["cut"])                              # train windows only use closed train trades
        self.assertEqual([b["mean"] for b in base["bins"]], [b["mean"] for b in again["bins"]])


class Adapters(unittest.TestCase):
    def test_sweep_trades_and_filter(self):
        rows = [{"rule": "fw[sig=prev,thr=1]", "t": 1, "x": 2, "net": 0.1}, {"rule": "fw[thr=1]", "t": 1, "x": 2, "net": 0.2}]
        self.assertEqual(len(sm.sweep_trades(rows, "sweep_fundwin2", "sig=prev")), 1)
        self.assertEqual(len(sm.sweep_trades(rows, "sweep_x")), 2)

    def test_event_trades(self):
        rows = [{"ts": 1000.0, "ret": {"4h": {"net": 0.05}, "1d": {"net": None}, "7d": {"net": -0.1}}}]
        tr = sm.event_trades(rows, "l1f")
        self.assertEqual({(z["rule"], z["x"] - z["t"], z["net"]) for z in tr}, {("l1f/4h", 14400, 0.05), ("l1f/7d", 604800, -0.1)})

    def test_poly_trades_take_the_underpriced_side(self):
        row = {"kind": "hourly", "off": 60, "lb": 60, "end": 5000.0, "fair": 0.5, "mkt": 0.52, "yes": {"t": 10, "net": -1.0}, "no": {"t": 11, "net": 1.06}}
        tr = sm.poly_trades([row, dict(row, fair=0.6, mkt=0.55), dict(row, fair=0.5, mkt=0.5), dict(row, fair=None)])
        self.assertEqual([(z["rule"], z["t"], z["net"]) for z in tr], [("hourly/off60/lb60", 11, 1.06), ("hourly/off60/lb60", 10, -1.0)])


class Config(unittest.TestCase):
    def test_config_is_valid(self):
        p = os.path.join(sc.ROOT, "research", "sweeps", "meta", "meta1.json")
        cfg = json.load(open(p))
        self.assertEqual(cfg["kind"], "meta")
        self.assertAlmostEqual(cfg["alpha"], 0.05 / (2 * len(cfg["pools"])))
        a, b = sc.day(cfg["splits"]["train"][1]), sc.day(cfg["splits"]["validation"][0])
        self.assertEqual(a, b)
        self.assertEqual(sc.day(cfg["splits"]["validation"][1]), sc.day(cfg["splits"]["test"][0]))


if __name__ == "__main__":
    unittest.main()
