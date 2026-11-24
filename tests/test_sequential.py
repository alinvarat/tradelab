import random
import unittest

from core import sequential as sq


class EProcessTests(unittest.TestCase):
    def test_clear_positive_edge_stops_early(self):
        rng = random.Random(1)
        v = sq.run([0.03 + rng.gauss(0, 0.02) for _ in range(200)], lo=0.1, hi=0.1)
        self.assertEqual(v["decision"], "edge")
        self.assertLess(v["decided_at_unit"], 60)

    def test_negative_mean_gives_a_futility_stop(self):
        rng = random.Random(2)
        v = sq.run([-0.03 + rng.gauss(0, 0.02) for _ in range(200)], lo=0.1, hi=0.1)
        self.assertEqual(v["decision"], "no edge (negative)")

    def test_false_positive_rate_under_zero_mean_is_controlled(self):
        hits = 0
        for seed in range(200):
            rng = random.Random(seed)
            if sq.run([rng.gauss(0, 0.05) for _ in range(300)], lo=0.2, hi=0.2)["decision"] == "edge":
                hits += 1
        self.assertLessEqual(hits / 200, 0.07)            # alpha 0.05 plus sampling noise

    def test_option_like_returns_with_big_winners(self):
        rng = random.Random(3)
        xs = [(4.0 if rng.random() < 0.3 else -1.0) for _ in range(400)]   # mean +0.5 per trade, loss capped at -1
        self.assertEqual(sq.run(xs, lo=1.0, hi=5.0)["decision"], "edge")

    def test_paired_scaling_stays_in_range(self):
        e = sq.EProcess(paired=True, lo=1.0, hi=3.0)
        for x in (-10, 10, 0.5):
            e.update(x)
        self.assertEqual(e.n, 3)

    def test_daily_means_one_unit_per_day(self):
        rows = [{"ts": 0, "ret": 1.0}, {"ts": 100, "ret": 3.0}, {"ts": 86400, "ret": -1.0}, {"ts": 5, "ret": None}]
        self.assertEqual(sq.daily_means(rows), [2.0, -1.0])


if __name__ == "__main__":
    unittest.main()
