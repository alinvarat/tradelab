import unittest

from core import factory as fa

T0 = 1_700_006_400


def bars(path, qv=5e6):
    return [(T0 + k * 86400, p, p, p, p, qv) for k, p in enumerate(path)]


class Factory(unittest.TestCase):
    def setUp(self):
        n = 60
        self.b = {"BTCUSDT": bars([100.0] * n)}
        for j in range(12):                                   # 12 coins: coin j drifts j*0.1% a day
            self.b[f"C{j}USDT"] = bars([10 * (1 + 0.001 * j) ** k for k in range(n)])
        self.days, self.close, self.qv = fa.panel(self.b)
        self.f = fa.features(self.days, self.close, self.qv)

    def test_features_need_31_days_and_volume(self):
        self.assertEqual(self.f[29], {})
        self.assertIn("C5USDT", self.f[40])
        thin = dict(self.b, THINUSDT=bars([1.0] * 60, qv=1e4))
        d, c, q = fa.panel(thin)
        self.assertNotIn("THINUSDT", fa.features(d, c, q)[40])

    def test_momentum_earns_the_drift_spread_minus_costs(self):
        s = fa.run(self.days, self.close, self.f, fa.STRATEGIES["xs_momentum_r7"])
        late = [r for t, r in s[45:]]
        # long top 5 (j=7..11) half, short bottom 5 (j=0..4) half: spread ~ 0.5*(0.9%) - 0.5*(0.2%) per day,
        # minus funding on the 0.5 short; no turnover once ranks are stable
        exp = 0.5 * mean_g(7, 11) - 0.5 * mean_g(0, 4) - 0.5 * fa.FUNDING_DAY
        self.assertAlmostEqual(late[-1], exp, places=6)

    def test_turnover_is_charged(self):
        s = fa.run(self.days, self.close, self.f, fa.STRATEGIES["xs_momentum_r7"])
        first = [r for t, r in s if r != 0.0][0]
        later = s[-1][1]
        self.assertLess(first, later)                         # day one pays to build the book

    def test_judge_bonferroni_and_months(self):
        import random
        rng = random.Random(1)
        good = [(T0 + k * 86400, 0.01 + rng.gauss(0, 0.01)) for k in range(800)]
        flat = [(T0 + k * 86400, rng.gauss(0, 0.01)) for k in range(800)]
        bounds = {"train": (T0, T0 + 300 * 86400), "validation": (T0 + 300 * 86400, T0 + 600 * 86400),
                  "test": (T0 + 600 * 86400, T0 + 800 * 86400)}
        out = fa.judge_all({"good": good, "good@2x": good, "flat": flat, "flat@2x": flat}, bounds)
        self.assertEqual(out["n_strategies"], 2)
        self.assertIn("good", out["passed"])
        self.assertNotIn("flat", out["passed"])
        self.assertGreater(out["strategies"]["good"]["validation_3x_check"]["months_3x"], 0)


def mean_g(a, b):
    return sum(0.001 * j for j in range(a, b + 1)) / (b - a + 1)


if __name__ == "__main__":
    unittest.main()
