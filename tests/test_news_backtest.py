import random
import unittest

from core import news_backtest as nb


def bars(rows):
    return [{"t": t, "o": o, "h": o, "l": o, "c": c, "v": 1} for t, o, c in rows]


class Costs(unittest.TestCase):
    def test_both_sides_pay_fee_slippage_and_half_spread(self):
        c = nb.cost_per_side("stock")
        self.assertAlmostEqual(c, 0.0005 + 0.0002 + 0.0002)
        self.assertAlmostEqual(nb.net_return(0.10, "stock"), 1.10 * (1 - c) ** 2 - 1)
        self.assertLess(nb.net_return(0.0, "stock"), 0)

    def test_unknown_class_falls_back_to_a_spread(self):
        self.assertAlmostEqual(nb.cost_per_side("???"), 0.0005 + 0.0002 + 0.0002)


class EventWindow(unittest.TestCase):
    def setUp(self):
        self.b = bars([(1000, 10, 12), (2000, 13, 11), (3000, 9, 15), (4000, 16, 16)])

    def test_filing_before_the_open_fills_at_that_open(self):
        r = nb.event_return(self.b, 500, 1)
        self.assertEqual(r["entry_t"], 1000)
        self.assertEqual(r["exit_t"], 1000)
        self.assertAlmostEqual(r["gross"], 12 / 10 - 1)      # open to close of the same session

    def test_filing_during_the_session_waits_for_the_next_open(self):
        r = nb.event_return(self.b, 1500, 1)
        self.assertEqual(r["entry_t"], 2000)
        self.assertAlmostEqual(r["gross"], 11 / 13 - 1)

    def test_horizon_counts_sessions_not_calendar_days(self):
        r = nb.event_return(self.b, 500, 3)
        self.assertEqual(r["entry_t"], 1000)
        self.assertEqual(r["exit_t"], 3000)
        self.assertAlmostEqual(r["gross"], 15 / 10 - 1)

    def test_window_past_the_last_bar_is_missing_not_stale(self):
        self.assertIsNone(nb.event_return(self.b, 500, 5))
        self.assertIsNone(nb.event_return(self.b, 9999, 1))

    def test_bad_horizon_is_rejected(self):
        with self.assertRaises(ValueError):
            nb.event_return(self.b, 500, 0)


class Splits(unittest.TestCase):
    def test_dates_fall_into_train_validation_test(self):
        def ts(day):
            import calendar, time
            return calendar.timegm(time.strptime(day, "%Y-%m-%d"))
        self.assertEqual(nb.split_of(ts("2022-12-31")), "train")
        self.assertEqual(nb.split_of(ts("2023-01-01")), "validation")
        self.assertEqual(nb.split_of(ts("2024-12-31")), "validation")
        self.assertEqual(nb.split_of(ts("2025-01-02")), "test")


class Control(unittest.TestCase):
    def test_control_is_another_symbol_of_the_same_class(self):
        pool = {"AAPL": [], "MSFT": [], "SPY": []}
        got = nb.pick_control("AAPL", "stock", pool, random.Random(1))
        self.assertEqual(got, "MSFT")

    def test_no_control_when_the_class_has_one_member(self):
        self.assertIsNone(nb.pick_control("AAPL", "stock", {"AAPL": []}, random.Random(1)))


class Stats(unittest.TestCase):
    def test_bootstrap_never_reports_certainty(self):
        self.assertGreater(nb.bootstrap_p([1.0] * 50, random.Random(2)), 0)
        self.assertLess(nb.bootstrap_p([1.0] * 50, random.Random(2)), 0.01)
        self.assertEqual(nb.bootstrap_p([], random.Random(2)), 1.0)

    def test_summary_pair_difference_and_sign(self):
        rows = [{"gross": 0.02, "ctrl_gross": 0.0, "asset_class": "stock"}] * 20
        s = nb.summarize(rows, random.Random(3))
        self.assertEqual(s["n"], 20)
        self.assertGreater(s["mean_diff"], 0)
        self.assertGreater(s["mean_net"], 0)
        self.assertLess(s["p_diff"], 0.01)
        self.assertEqual(s["hit"], 1.0)

    def test_costs_can_turn_a_positive_gross_into_a_loss(self):
        s = nb.summarize([{"gross": 0.0005, "ctrl_gross": 0.0005, "asset_class": "stock"}])
        self.assertLess(s["mean_net"], 0)


class ClusteredStats(unittest.TestCase):
    def test_cluster_is_symbol_and_month(self):
        self.assertEqual(nb.cluster_key({"symbol": "AAPL", "ts": 1704067200}), "AAPL:2024-01")   # 2024-01-01
        self.assertEqual(nb.cluster_key({"symbol": "AAPL", "ts": 1706745600}), "AAPL:2024-02")   # 2024-02-01

    def test_block_bootstrap_is_wider_when_one_cluster_carries_the_mean(self):
        # 10 tiny losses in 10 clusters plus 40 big wins all inside one cluster
        values = [-0.001] * 10 + [0.01] * 40
        keys = [f"X:{i}" for i in range(10)] + ["Y:0"] * 40
        iid = nb.bootstrap_p(values, random.Random(5))
        block = nb.block_bootstrap_p(values, keys, random.Random(5))
        self.assertLess(iid, 0.01)
        self.assertGreater(block, 0.2)

    def test_block_bootstrap_equals_iid_shape_for_singletons(self):
        self.assertLess(nb.block_bootstrap_p([1.0] * 50, [str(i) for i in range(50)], random.Random(2)), 0.01)
        self.assertEqual(nb.block_bootstrap_p([], [], random.Random(2)), 1.0)

    def test_double_cost_lowers_net_and_keeps_gross(self):
        rows = [{"gross": 0.003, "ctrl_gross": 0.001, "symbol": "A", "ts": 0}] * 10
        one, two = nb.summarize(rows), nb.summarize(rows, cost_mult=2.0)
        self.assertAlmostEqual(one["mean_gross"], two["mean_gross"])
        self.assertLess(two["mean_net"], one["mean_net"])
        self.assertEqual(two["cost_mult"], 2.0)

    def test_contributions_rank_symbols_by_paired_difference(self):
        rows = ([{"symbol": "A", "gross": 0.05, "ctrl_gross": 0.0}] * 3
                + [{"symbol": "B", "gross": 0.0, "ctrl_gross": 0.01}] * 2)
        con = nb.contributions(rows)
        self.assertEqual([c["symbol"] for c in con], ["A", "B"])
        self.assertEqual(con[0]["n"], 3)
        self.assertGreater(con[0]["share_of_total_diff"], 1)      # B's loss offsets part of A
        self.assertAlmostEqual(sum(c["share_of_total_diff"] for c in con), 1.0)


if __name__ == "__main__":
    unittest.main()
