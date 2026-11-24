import unittest

from core import screens as sc


class ListingParsers(unittest.TestCase):
    def test_binance_spot_listing_only(self):
        self.assertEqual(sc.binance_listing_symbols("Binance Will List Sapien (SAPIEN) with Seed Tag Applied"), ["SAPIEN"])
        self.assertEqual(sc.binance_listing_symbols("Introducing AltLayer (ALT) on Binance Launchpool! Farm ALT"), [])
        self.assertEqual(sc.binance_listing_symbols("Binance Adds ACA, AMP, GHST & More Pairs on Cross Margin"), [])
        self.assertEqual(sc.binance_listing_symbols("Binance Futures Will Launch USDⓈ-M FOO Perpetual"), [])

    def test_upbit_krw_additions(self):
        self.assertEqual(sc.upbit_listing_symbols("KRW, BTC 마켓 디지털 자산 추가 (NEAR, YGG)"), ["NEAR", "YGG"])
        self.assertEqual(sc.upbit_listing_symbols("로켓풀(RPL), 아큐라스트(ACU), 디브릿지(DBR) 원화 마켓 디지털 자산 추가"),
                         ["RPL", "ACU", "DBR"])
        self.assertEqual(sc.upbit_listing_symbols("BTC 마켓 디지털 자산 추가 (FOO)"), [])
        self.assertEqual(sc.upbit_listing_symbols("거래 유의 종목 지정 안내 (FOO)"), [])


class Returns(unittest.TestCase):
    def test_close_at_finds_the_containing_bar(self):
        bars = [(0, 1.0), (60, 2.0), (180, 4.0)]
        self.assertEqual(sc.close_at(bars, 61, 60), 2.0)
        self.assertIsNone(sc.close_at(bars, 125, 60))      # bar 120 missing
        self.assertEqual(sc.close_at(bars, 239, 60), 4.0)

    def test_listing_return_is_abnormal_to_btc_and_net_of_cost(self):
        ts = 1_000_000
        m1 = [(ts + 60 + i * 60, 100.0 if i == 0 else 110.0) for i in range(300)]
        bench = [(ts + 60 + i * 60, 50.0 if i == 0 else 51.0) for i in range(300)]
        r = sc.listing_returns(ts, m1, [], bench, [], cost=0.006)
        self.assertAlmostEqual(r["15m"]["raw"], 0.10)
        self.assertAlmostEqual(r["15m"]["abn"], 0.08)
        self.assertAlmostEqual(r["15m"]["net"], 0.074)
        self.assertNotIn("1d", r)                            # no hourly bars given

    def test_missing_entry_bar_gives_nothing(self):
        self.assertEqual(sc.listing_returns(0, [], [], [], []), {})


class Judge(unittest.TestCase):
    def _rows(self, mean_train, mean_val, n=60):
        rows = []
        for i in range(n):
            for split, base, m in (("train", 0, mean_train), ("validation", 10_000_000, mean_val)):
                x = m + (0.01 if i % 2 else -0.01)
                rows.append({"ts": base + i * 86400, "symbol": f"S{i}", "ret": {"1h": {"net": x}, "1d": {"net": x - 0.02}}})
        return rows

    BOUNDS = {"train": (0, 10_000_000), "validation": (10_000_000, 20_000_000), "test": (20_000_000, 30_000_000)}

    def test_clear_edge_passes_and_picks_best_train_horizon(self):
        j = sc.judge(self._rows(0.03, 0.03), ["1h", "1d"], self.BOUNDS)
        self.assertEqual(j["pick"], "1h")
        self.assertEqual(j["verdict"], "passed")

    def test_negative_validation_is_killed(self):
        self.assertEqual(sc.judge(self._rows(0.03, -0.02), ["1h", "1d"], self.BOUNDS)["verdict"], "killed")

    def test_one_huge_event_cannot_carry_the_result(self):
        rows = self._rows(0.03, -0.012)
        rows.append({"ts": 15_000_000, "symbol": "X", "ret": {"1h": {"net": 5.0}, "1d": {"net": 5.0}}})
        j = sc.judge(rows, ["1h", "1d"], self.BOUNDS)
        self.assertLess(j["robust"]["without_best_1"], 0)
        self.assertEqual(j["verdict"], "killed")


class L1bLedger(unittest.TestCase):
    def test_new_events_are_returned_once(self):
        seen = set()
        ev = [{"venue": "binance", "symbol": "FOO", "ts": 100.4}]
        self.assertEqual(len(sc.new_listing_events(seen, ev)), 1)
        self.assertEqual(sc.new_listing_events(seen, ev), [])

    def test_result_pays_spread_fees_and_removes_btc(self):
        r = sc.l1b_result(entry_ask=10.0, exit_bid=11.0, btc_entry=100.0, btc_exit=102.0)
        self.assertAlmostEqual(r["raw"], 0.10)
        self.assertAlmostEqual(r["net"], 0.10 - 0.02 - 0.002)


if __name__ == "__main__":
    unittest.main()
