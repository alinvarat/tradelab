import math
import random
import unittest
from unittest import mock

from research.studies import indicators_1 as I


def walk(n, seed=1, sec=3600, t0=1700000000 // 3600 * 3600, vol=0.004):
    r = random.Random(seed)
    p, rows = 100.0, []
    for k in range(n):
        q = p * (1 + r.gauss(0, vol))
        rows.append((t0 + k * sec, p, max(p, q) * 1.002, min(p, q) * 0.998, q, 10 + r.random()))
        p = q
    return I.arrays(rows)


class Gate(unittest.TestCase):
    def test_family_and_gate(self):
        self.assertEqual(len(I.FAMILY), 54)
        self.assertEqual(len(set(I.FAMILY)), 54)
        st = {(g["market"], g["tf"]): g["status"] for g in I.gate_table()}
        self.assertEqual(st[("crypto", "1d")], "in")
        self.assertEqual(st[("fx", "4h")], "out_step0")
        self.assertEqual(st[("fx", "15m")], "out_depth")
        self.assertEqual(st[("gold", "1d")], "out_step0")
        self.assertTrue(all(st[("etf", tf)] == "out_step0" for tf in I.TFS))
        self.assertFalse(any(m == "etf" for m, _, _ in I.FAMILY))
        self.assertFalse(any(r == "vwap" and (tf == "1d" or m == "fx") for m, tf, r in I.FAMILY))

    def test_step0_monotone(self):
        self.assertLess(I.step0("crypto", "4h")["trades_needed_per_month"], I.step0("crypto", "15m")["trades_needed_per_month"])


class Signals(unittest.TestCase):
    def test_no_lookahead_and_valid_positions(self):
        a = walk(1500, seed=3)
        cut = 1000
        short = {k: v[:cut] for k, v in a.items()}
        for rule in I.RULES:
            full = I.SIGNALS[rule](a, "1h")
            part = I.SIGNALS[rule](short, "1h")
            for x, y in zip(full[:4], part[:4]):
                self.assertEqual(x[:cut], y[:cut], rule)
            pos = I.positions(a, full)
            self.assertEqual(len(pos), 1500)
            self.assertTrue(set(pos) <= {-1, 0, 1})

    def test_rules_trade(self):
        a = walk(3000, seed=5, vol=0.01)
        traded = [r for r in I.RULES if any(I.positions(a, I.SIGNALS[r](a, "1h")))]
        self.assertGreaterEqual(len(traded), 6, traded)

    def test_stop_exits(self):
        c = [100.0] * 30 + [100, 100, 100, 100, 100, 100, 60, 60, 60]
        n = len(c)
        a = {"ts": list(range(n)), "o": c, "h": [x + 1 for x in c], "l": [x - 1 for x in c], "c": c, "v": [1.0] * n}
        le = [False] * n
        le[20] = True
        z = [False] * n
        pos = I.positions(a, (le, z, z, z, None))
        self.assertEqual(pos[20], 1)
        self.assertEqual(pos[36], 0)          # stopped on the 60 close
        self.assertEqual(pos[35], 1)


class Engine(unittest.TestCase):
    def test_returns_and_costs(self):
        a = {"ts": [0, 3600, 7200, 10800], "o": [100, 100, 110, 110], "h": [0] * 4, "l": [0] * 4, "c": [100, 110, 110, 100], "v": [1] * 4}
        cost = I.Cost("BTCUSDT")
        r = I.bar_returns(a, [1, 1, 0, 0], cost, 3600)
        # bar0 decided long at close 100, filled at open 100 -> 110: +10% less 0.07% entry
        self.assertAlmostEqual(r[0][1], 0.10 - I.CRYPTO_SIDE, places=9)
        self.assertAlmostEqual(r[1][1], 0.0 - 0.0, places=9)             # hold: 110 -> 110
        r2 = I.bar_returns(a, [1, 1, 0, 0], cost, 3600, mult=2.0)
        self.assertAlmostEqual(r2[0][1], 0.10 - 2 * I.CRYPTO_SIDE, places=9)
        f = I.bar_returns(a, [1, 1, 0, 0], cost, 3600, sign=-1)
        self.assertAlmostEqual(f[0][1], -0.10 - I.CRYPTO_SIDE, places=9)

    def test_funding_charged_to_long(self):
        a = {"ts": [0, 28800, 57600, 86400], "o": [100] * 4, "h": [0] * 4, "l": [0] * 4, "c": [100] * 4, "v": [1] * 4}
        cost = I.Cost("BTCUSDT", funding=[(28800, 0.001)])
        r = dict(I.bar_returns(a, [1, 1, 1, 1], cost, 28800))
        self.assertAlmostEqual(r[28800], -I.CRYPTO_SIDE - 0.001, places=9)

    def test_xm_cost_uses_broker_costs(self):
        c = I.Cost("EURUSD=X")
        self.assertAlmostEqual(c.side(1.1), 0.00020 / 1.1 / 2, places=9)
        self.assertGreater(c.hold(0, 86400, 1, 2.0), c.hold(0, 86400, 1, 1.0))

    def test_resample(self):
        a = walk(24, seed=2)
        r = I.resample(a, 14400, 4)
        self.assertGreaterEqual(len(r["ts"]), 4)
        self.assertTrue(all(t % 14400 == 0 for t in r["ts"]))
        for t, c in zip(r["ts"], r["c"]):
            self.assertEqual(c, a["c"][a["ts"].index(t + 10800)])


class Judge(unittest.TestCase):
    def test_pass_and_fail(self):
        days = [(86400 * k, 0.01 + (0.002 if k % 2 else -0.002)) for k in range(300)]
        b = {"train": (0, 86400 * 100), "validation": (86400 * 100, 86400 * 200), "test": (86400 * 200, 86400 * 300)}
        good = I.judge_cell(days, days, [(t, -r) for t, r in days], b, 0.001, 365, n_boot=5000)
        self.assertTrue(good["passed"], good)
        bad = I.judge_cell([(t, -r) for t, r in days], days, days, b, 0.001, 365, n_boot=5000)
        self.assertFalse(bad["passed"])


class Smoke(unittest.TestCase):
    def test_end_to_end_offline(self):
        t0 = I.T(2024, 1, 1) - 40 * 86400

        def fake_crypto(sym):
            a = walk(24 * 700, seed=sum(map(ord, sym)), t0=t0)
            rows = [(t, o, h, l, c, v, t + 3599, 1, 1, 0, 0) for t, o, h, l, c, v in zip(a["ts"], a["o"], a["h"], a["l"], a["c"], a["v"])]
            return {"15m": ([], []), "1h": (rows, []), "funding": ([(float(t), 0.0001) for t in range(t0, t0 + 700 * 86400, 28800)], [])}

        b = {"train": (t0, I.T(2024)), "validation": (I.T(2024), I.T(2024, 7)), "test": (I.T(2024, 7), t0 + 700 * 86400)}
        fam = [(m, tf, r) for m, tf, r in I.FAMILY if m == "crypto" and tf in ("1h", "4h")]
        with mock.patch.object(I, "fetch_crypto", fake_crypto), mock.patch.object(I, "FAMILY", fam), \
                mock.patch.dict(I.BOUNDS, {"crypto": b}), mock.patch.object(I, "MIN_DAYS", 20):
            summ, rows = I.study_indicators_1([])
        self.assertEqual(summ["family_size"], len(fam))
        self.assertEqual(len(rows), len(fam))
        self.assertEqual(sum(summ["counts"].values()), len(fam))
        self.assertEqual(summ["fetch_errors"], [])


if __name__ == "__main__":
    unittest.main()
