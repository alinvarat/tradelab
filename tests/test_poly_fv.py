import unittest

from core import poly_fv as pf


class PolyFv(unittest.TestCase):
    def test_fair_at_money(self):
        self.assertAlmostEqual(pf.fair_yes(100, 100, 0.001, 30), 0.5)

    def test_fair_deep_itm(self):
        self.assertGreater(pf.fair_yes(110, 100, 0.0005, 10), 0.99)

    def test_fair_expired(self):
        self.assertEqual(pf.fair_yes(99, 100, 0.001, 0), 0.0)

    def test_fee(self):
        self.assertAlmostEqual(pf.fee_per_share(0.5, 0.01, 1), 0.0025)
        self.assertEqual(pf.fee_per_share(0.5, 0, 1), 0.0)

    def test_bet_net(self):
        self.assertAlmostEqual(pf.bet_net(1.0, 0.495, 0, 1), 1 / 0.5 - 1)
        self.assertAlmostEqual(pf.bet_net(0.0, 0.5, 0, 1), -1.0)

    def test_holm(self):
        h = pf.holm([0.01, 0.04, None, 0.03])
        self.assertAlmostEqual(h[0], 0.04)
        self.assertAlmostEqual(h[3], 0.09)
        self.assertIsNone(h[2])

    def test_rule_count(self):
        self.assertEqual(pf.N_RULES, 54)
        self.assertEqual(len({r["id"] for r in pf.RULES}), 54)

    def test_apply_rule_side_and_control(self):
        row = {"id": "m", "coin": "bitcoin", "end": 1000.0, "off": 30, "lb": 60, "fair": 0.7, "mkt": 0.5, "fee_rate": 0, "fee_exp": 1,
               "yes": {"price": 0.5, "t": 900, "net": 1.0, "payoff": 1.0, "sells": [[950, 0.72]]},
               "no": {"price": 0.5, "t": 900, "net": -1.0, "payoff": 0.0, "sells": []}}
        rule = {"thr": 0.12, "off": 30, "lb": 60, "exit": "hold"}
        idx, bet = pf.apply_rule(rule, row)
        self.assertEqual(idx, 0)
        self.assertEqual(bet["net"], 1.0)
        self.assertEqual(bet["ctl"], 0.0)
        rule = dict(rule, exit="fair")
        _, bet = pf.apply_rule(rule, row)
        self.assertTrue(bet["exited"])
        self.assertIsNone(pf.apply_rule(dict(rule, thr=0.25), row))

    def test_market_rows_no_lookahead(self):
        m = {"id": "m", "coin": "bitcoin", "kind": "hourly", "end": 3600 * 10, "yes_won": True, "fee_rate": 0, "fee_exp": 1}
        t0 = m["end"] - 30 * 60
        trades = [{"t": t0 - 60, "side": "BUY", "idx": 0, "price": 0.5, "size": 100},
                  {"t": t0 + 400, "side": "BUY", "idx": 0, "price": 0.55, "size": 100},
                  {"t": t0 + 400, "side": "BUY", "idx": 1, "price": 0.45, "size": 100}]
        spot_t = [t0 - 3000 + 60 * k for k in range(60)]
        spot_c = [100 + 0.01 * (k % 5) for k in range(60)]
        rows = pf.market_rows(m, trades, spot_t, spot_c, 100.0, offsets=(30,), lookbacks=(30,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mkt"], 0.5)
        self.assertEqual(rows[0]["yes"]["price"], 0.55)
        self.assertEqual(rows[0]["no"]["price"], 0.45)


if __name__ == "__main__":
    unittest.main()
