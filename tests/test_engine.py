import unittest

from core.engine import Account, Quote


def acct(**kw):
    a = Account(**{"balance": 10_000, "leverage": 1, "fee_rate": 0.001, "slippage": 0.0, **kw})
    a.on_quote(Quote("X", 99.0, 101.0, 1))
    return a


class Orders(unittest.TestCase):
    def test_market_buy_fills_at_ask_and_tp(self):
        a = acct()
        o = a.place("X", 1, 10, sl=90, tp=110)
        self.assertEqual((o.status, o.fill_px), ("filled", 101.0))
        t = a.on_quote(Quote("X", 111, 112, 2))
        self.assertEqual(t[0].reason, "take profit")
        self.assertAlmostEqual(t[0].pnl, (111 - 101) * 10 - 1.01 - 1.11, places=6)
        self.assertAlmostEqual(a.balance, 10_000 + t[0].pnl, places=6)

    def test_short_fills_at_bid_and_stop_loss(self):
        a = acct()
        a.place("X", -1, 10, sl=105)
        self.assertEqual(a.positions["X"].entry, 99.0)
        t = a.on_quote(Quote("X", 105, 106, 2))
        self.assertEqual(t[0].reason, "stop loss")
        self.assertLess(t[0].pnl, 0)

    def test_buying_power(self):
        a = acct()
        o = a.place("X", 1, 200)
        self.assertEqual(o.status, "rejected")
        self.assertIn("insufficient", o.note)

    def test_limit_waits_then_fills_at_limit_or_better(self):
        a = acct()
        o = a.place("X", 1, 5, "limit", 95)
        self.assertEqual(o.status, "pending")
        a.on_quote(Quote("X", 96, 97, 2))
        self.assertEqual(o.status, "pending")
        a.on_quote(Quote("X", 93, 94, 3))
        self.assertEqual((o.status, o.fill_px), ("filled", 94))

    def test_stop_buy_triggers_above(self):
        a = acct()
        o = a.place("X", 1, 5, "stop", 105)
        a.on_quote(Quote("X", 104, 106, 2))
        self.assertEqual((o.status, o.fill_px), ("filled", 106))

    def test_closed_market_queues_market_order(self):
        a = Account(balance=10_000, fee_rate=0, slippage=0)
        a.on_quote(Quote("X", 99, 101, 1, open=False))
        o = a.place("X", 1, 1)
        self.assertEqual(o.status, "pending")
        self.assertIn("closed", o.note)
        a.on_quote(Quote("X", 109, 111, 2, open=True))
        self.assertEqual((o.status, o.fill_px), ("filled", 111))

    def test_closed_market_does_not_trigger_stop(self):
        a = acct()
        a.place("X", 1, 1, sl=90)
        a.on_quote(Quote("X", 80, 81, 2, open=False))
        self.assertIn("X", a.positions)

    def test_add_reduce_flip(self):
        a = acct()
        a.place("X", 1, 10)
        a.on_quote(Quote("X", 109, 111, 2))
        a.place("X", 1, 10)
        self.assertAlmostEqual(a.positions["X"].entry, 106.0)
        a.place("X", -1, 5)
        self.assertAlmostEqual(a.positions["X"].qty, 15)
        self.assertEqual(len(a.trades), 1)
        a.place("X", -1, 20)
        self.assertEqual(a.positions["X"].side, -1)
        self.assertAlmostEqual(a.positions["X"].qty, 5)

    def test_fx_conversion(self):
        a = Account(balance=10_000, fee_rate=0, slippage=0)
        a.on_quote(Quote("J", 1000, 1000, 1, fx=0.01))  # priced in a currency worth 0.01 USD
        a.place("J", 1, 100)  # 100,000 units = 1,000 USD
        self.assertAlmostEqual(a.used_margin(), 1000)
        a.on_quote(Quote("J", 1100, 1100, 2, fx=0.01))
        self.assertAlmostEqual(a.unrealized(), 100)

    def test_fees_booked_once(self):
        a = acct()
        a.place("X", 1, 10)
        a.on_quote(Quote("X", 101, 103, 2))
        t, _ = a.close("X")
        self.assertAlmostEqual(t.pnl, 0 - 1.01 - 1.01, places=6)
        self.assertAlmostEqual(a.balance, 10_000 + t.pnl, places=6)

    def test_roundtrip(self):
        a = acct()
        a.place("X", 1, 3, "limit", 90)
        a.place("X", 1, 2, tp=200)
        b = Account.from_dict(a.to_dict())
        self.assertEqual(b.balance, a.balance)
        self.assertEqual(b.positions["X"].qty, 2)
        self.assertEqual(b.place("X", 1, 1, "limit", 1).id, 3)


if __name__ == "__main__":
    unittest.main()
