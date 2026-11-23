"""Input validation regressions found while testing the deployed app (offline)."""
import unittest

import server
from core.engine import Account


class OrderValidation(unittest.TestCase):
    def test_non_finite_or_non_positive_quantities_are_rejected(self):
        for qty in (float("nan"), float("inf"), -5, 0):
            self.assertEqual(Account().place("AAPL", 1, qty).status, "rejected", qty)

    def test_non_finite_limit_price_is_rejected(self):
        self.assertEqual(Account().place("AAPL", 1, 1, "limit", float("nan")).status, "rejected")

    def test_valid_limit_order_stays_pending(self):
        self.assertEqual(Account().place("AAPL", 1, 1, "limit", 10.0).status, "pending")


class NumberParsing(unittest.TestCase):
    def test_num_accepts_and_rejects(self):
        self.assertEqual(server.num("2.5", "x", 0, 10), 2.5)
        for bad in ("nan", "inf", "abc", -1, 11):
            with self.assertRaises(ValueError):
                server.num(bad, "x", 0, 10)

    def test_shock_universe_is_in_core(self):
        from core.universe import TICKERS
        self.assertGreaterEqual(len(TICKERS), 100)


if __name__ == "__main__":
    unittest.main()


class AiAvailability(unittest.TestCase):
    def test_missing_cli_gives_clear_error_without_logging(self):
        from unittest import mock
        from core import ai
        with mock.patch("core.ai.shutil.which", return_value=None):
            out = ai.analyst("AAPL", {}, {}, "")
        self.assertIn("not available", out["error"])
        self.assertEqual(out["text"], "")


class Calendar(unittest.TestCase):
    def test_calendar_lives_in_core_so_a_data_volume_cannot_hide_it(self):
        from core import econ_calendar
        self.assertEqual(econ_calendar.CSV.parent.name, "core")
        self.assertTrue(econ_calendar.CSV.exists())
        self.assertGreater(len(econ_calendar.events()), 5)
