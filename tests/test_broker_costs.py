import unittest

from core import broker_costs as bc


class Webull(unittest.TestCase):
    def test_buy_has_no_commission_only_pass_through(self):
        per = bc.WEBULL_ORF + bc.WEBULL_OCC + bc.WEBULL_CAT
        self.assertAlmostEqual(bc.webull_option_cost(1, "buy"), per)
        self.assertAlmostEqual(bc.webull_option_cost(10, "buy"), 10 * per)
        self.assertLess(bc.webull_option_cost(1, "buy"), 0.10)           # far below the old 0.65 flat fee

    def test_sell_adds_taf_and_sec_on_proceeds(self):
        buy = bc.webull_option_cost(2, "buy")
        floor = bc.webull_option_cost(2, "sell")
        self.assertAlmostEqual(floor - buy, 2 * bc.WEBULL_FINRA_TAF)
        full = bc.webull_option_cost(2, "sell", premium=1.50)             # proceeds 300 USD
        self.assertAlmostEqual(full - floor, bc.WEBULL_SEC_RATE * 300)

    def test_taf_cap_and_oversize(self):
        self.assertAlmostEqual(bc.webull_option_cost(5000, "sell") - bc.webull_option_cost(5000, "buy"), bc.WEBULL_FINRA_TAF_CAP)
        self.assertAlmostEqual(bc.webull_option_cost(501, "buy") - 501 * (bc.WEBULL_ORF + bc.WEBULL_OCC + bc.WEBULL_CAT),
                               501 * bc.WEBULL_OVERSIZE_FEE)
        self.assertAlmostEqual(bc.webull_option_cost(500, "buy"), 500 * (bc.WEBULL_ORF + bc.WEBULL_OCC + bc.WEBULL_CAT))

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            bc.webull_option_cost(1, "hold")
        with self.assertRaises(ValueError):
            bc.webull_option_cost(-1, "buy")
        self.assertEqual(bc.webull_option_cost(0, "sell"), 0.0)


class Xm(unittest.TestCase):
    def test_eurusd_standard_one_lot(self):
        r = bc.xm_cfd_cost("EURUSD", 1.0, "standard", 0, price=1.10)
        self.assertAlmostEqual(r["notional_usd"], 110_000)
        self.assertAlmostEqual(r["spread_usd"], 20.0)                    # 2.0 pips x 100k units
        self.assertEqual(r["commission_usd"], 0.0)
        self.assertAlmostEqual(r["total_usd"], 20.0)

    def test_zero_account_charges_commission_round_turn(self):
        r = bc.xm_cfd_cost("EURUSD", 2.0, "Zero", 0, price=1.10)
        self.assertAlmostEqual(r["commission_usd"], 2 * 2 * 3.50)
        self.assertLess(r["spread_usd"], bc.xm_cfd_cost("EURUSD", 2.0, "standard", 0, price=1.10)["spread_usd"])

    def test_ordering_of_accounts_on_spread(self):
        for sym, px in (("EURUSD", 1.1), ("XAUUSD", 2000.0), ("USDJPY", 150.0), ("WTI", 70.0)):
            s = [bc.xm_cfd_cost_fraction(sym, a, px)["spread"] for a in ("standard", "ultralow", "zero")]
            self.assertGreater(s[0], s[1])
            self.assertGreater(s[1], s[2])

    def test_notional_and_lots_agree(self):
        a = bc.xm_cfd_cost("XAUUSD", 3.0, "ultralow", 2, price=2000.0)
        b = bc.xm_cfd_cost("XAUUSD", a["notional_usd"], "ultralow", 2, unit="notional", price=2000.0)
        self.assertAlmostEqual(a["total_usd"], b["total_usd"])

    def test_usdjpy_notional_is_usd_base(self):
        r = bc.xm_cfd_cost("USDJPY", 1.0, "standard", 0, price=150.0)
        self.assertAlmostEqual(r["notional_usd"], 100_000)
        self.assertAlmostEqual(r["spread_usd"], 100_000 * 0.02 / 150.0)

    def test_nights_and_mult(self):
        base = bc.xm_cfd_cost_fraction("EURUSD", "standard", 1.1, 0)
        held = bc.xm_cfd_cost_fraction("EURUSD", "standard", 1.1, 10)
        self.assertAlmostEqual(held["swap"], bc.XM_SWAP_ANNUAL * 10 / 365)
        self.assertAlmostEqual(held["round_trip"] - base["round_trip"], held["swap"])
        two = bc.xm_cfd_cost_fraction("EURUSD", "standard", 1.1, 10, mult=2.0)
        self.assertAlmostEqual(two["spread"], 2 * held["spread"])
        self.assertAlmostEqual(two["swap"], 2 * held["swap"])
        self.assertAlmostEqual(held["trade_per_side"], held["spread"] / 2)

    def test_aliases_and_errors(self):
        self.assertEqual(bc.xm_cfd_cost_fraction("GC=F", "standard", 2000.0), bc.xm_cfd_cost_fraction("XAUUSD", "standard", 2000.0))
        with self.assertRaises(KeyError):
            bc.xm_cfd_cost_fraction("FOO", "standard", 1.0)
        with self.assertRaises(KeyError):
            bc.xm_cfd_cost_fraction("EURUSD", "platinum", 1.0)
        with self.assertRaises(ValueError):
            bc.xm_cfd_cost("EURUSD", 1.0, "standard", 0)
        with self.assertRaises(ValueError):
            bc.xm_cfd_cost_fraction("EURUSD", "standard", 0)

    def test_every_symbol_has_all_accounts_and_a_contract_size(self):
        for sym, row in bc.XM_SPREAD.items():
            self.assertEqual(set(row), set(bc.ACCOUNTS))
            self.assertIn(sym, bc.XM_CONTRACT)


if __name__ == "__main__":
    unittest.main()
