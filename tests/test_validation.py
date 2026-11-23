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


class FastChecks(unittest.TestCase):
    def make(self, d):
        from unittest import mock
        from core import autotrader
        patcher = mock.patch.object(autotrader, "STATE", __import__("pathlib").Path(d) / "auto.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        with mock.patch("core.data.fx_to_usd", return_value=0.03):
            return autotrader.AutoTrader()

    def test_no_history_download_when_month_already_rebalanced(self):
        import tempfile, time
        from unittest import mock
        from core import autotrader
        with tempfile.TemporaryDirectory() as d:
            at = self.make(d)
            at.model = {"status": "live", "ts": time.time(), "p": {}}
            at.rebalanced = time.strftime("%Y-%m", time.gmtime())
            with mock.patch.object(autotrader.R, "panel", side_effect=AssertionError("panel must not run")):
                at.rebalance()  # would raise if the long history were fetched every minute

    def test_default_check_interval_is_one_minute(self):
        from core import autotrader, hunter
        self.assertLessEqual(autotrader.EVERY_S, 60)
        self.assertLessEqual(hunter.EVERY_S, 60)


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
