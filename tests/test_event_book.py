"""Offline tests for core/event_book.py (synthetic trades only)."""
import random
import unittest

from core import event_book as eb

MON = 1796083200   # 2026-12-01 is a Tuesday; used only as an arbitrary base
BASE = (MON // 86400) * 86400


def trade(day, ret, w=0.5, ctrl=None):
    t = BASE + day * 86400
    return {"entry_ts": t, "exit_ts": t + 4 * 3600, "w": w, "ret": ret, "ctrl": ctrl if ctrl is not None else [0.0] * 3,
            "min_notional": 5.0}


class Sizing(unittest.TestCase):
    def test_kelly_and_caps(self):
        r = [0.1, 0.1, -0.05, 0.1]
        f = eb.kelly_fraction(r)
        self.assertAlmostEqual(f, (0.0625) / ((0.01 * 3 + 0.0025) / 4), places=6)
        w = eb.frozen_weight(r, stop=0.25)
        self.assertLessEqual(w["weight"], 1.0)        # 0.25 loss cap / 0.25 stop
        self.assertEqual(eb.frozen_weight([-0.1, -0.2], 0.25)["weight"], 0.0)

    def test_split_unit(self):
        self.assertEqual(eb.split_unit(1.0, 4), 0.25)

    def test_order_minimums(self):
        self.assertIsNone(eb.order_qty(147, 0.02, 100.0))               # 2.94 USD < 5
        self.assertAlmostEqual(eb.order_qty(147, 0.5, 10.0, qty_step=1.0), 7.0)
        self.assertIsNone(eb.order_qty(147, 0.5, 10.0, min_qty=10.0))


class Trade(unittest.TestCase):
    def test_short_stop_and_exit(self):
        net, st = eb.trade_return(-1, 100.0, [(110.0, 99.0), (126.0, 100.0)], 90.0, 0.25)
        self.assertTrue(st)
        self.assertAlmostEqual(net, -(0.25 + eb.STOP_SLIP) - eb.FEE_ROUND - eb.EXTRA_COST)
        net, st = eb.trade_return(-1, 100.0, [(105.0, 95.0)], 90.0, 0.25)
        self.assertFalse(st)
        self.assertAlmostEqual(net, 0.10 - eb.FEE_ROUND - eb.EXTRA_COST)

    def test_long(self):
        net, st = eb.trade_return(1, 100.0, [(101.0, 70.0)], 80.0, 0.25)
        self.assertTrue(st)


class Wallet(unittest.TestCase):
    def test_compounding_and_bank(self):
        tr = [trade(0, 1.0, w=1.0), trade(1, 1.0, w=1.0)]    # +100% twice: 147 -> 294 -> 588 >= 441: banked, reset
        r = eb.run_wallet(tr, -1)
        self.assertEqual(r["banked"], 1)
        self.assertEqual(r["equity"], 147.0)
        r2 = eb.run_wallet(tr, -1, bank=False)
        self.assertAlmostEqual(r2["equity"], 588.0)

    def test_halt(self):
        tr = [trade(0, -0.7, w=1.0), trade(1, 1.0, w=1.0)]
        r = eb.run_wallet(tr, -1)
        self.assertTrue(r["halted"])
        self.assertEqual(r["trades"], 1)
        self.assertEqual(r["skipped"], 1)

    def test_min_notional_skips(self):
        r = eb.run_wallet([trade(0, 0.5, w=0.01)], -1)
        self.assertEqual(r["trades"], 0)

    def test_control_ledger(self):
        tr = [trade(0, 0.1, ctrl=[0.0, 0.2, None])]
        self.assertAlmostEqual(eb.run_wallet(tr, 1)["equity"], 147 + 147 * 0.5 * 0.2)
        self.assertEqual(eb.run_wallet(tr, 2)["trades"], 0)


class Series(unittest.TestCase):
    def test_paired_series_length_and_clip(self):
        tr = [trade(1, 0.2, w=1.0, ctrl=[0.0] * 3)]
        s = eb.paired_series(tr, BASE, BASE + 3 * 86400, n_controls=3)
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0], 0.0)
        self.assertGreater(s[1], 0.0)

    def test_mondays(self):
        m = eb.monday_starts(BASE, BASE + 15 * 86400)
        self.assertTrue(all(__import__("time").gmtime(t).tm_wday == 0 for t in m))
        self.assertIn(len(m), (2, 3))

    def test_controls_exclude_event_coin(self):
        c = eb.random_controls(random.Random(1), ["A", "B", "C"], {"A"}, n=20)
        self.assertNotIn("A", c)
        self.assertEqual(len(c), 20)

    def test_cohorts(self):
        tr = [trade(0, 1.0, w=1.0), trade(1, 1.0, w=1.0)]
        m = eb.monday_starts(BASE, BASE + 10 * 86400)
        out = eb.cohort_outcomes(tr, m[:1], BASE + 60 * 86400, n_controls=3)
        self.assertEqual(out[0]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
