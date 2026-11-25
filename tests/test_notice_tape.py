"""Offline tests for core/notice_tape.py with titles seen in the 2026-11-25 endpoint probe."""
import random
import unittest

from core import notice_tape as nt


class Classify(unittest.TestCase):
    def test_okx_delist_list(self):
        r = nt.classify_title("OKX to delist DORA, ICX, STORJ, ZEUS and ELF spot trading pairs")
        self.assertEqual(r, [("delist", ["DORA", "ICX", "STORJ", "ZEUS", "ELF"])])

    def test_kucoin_listing(self):
        self.assertEqual(nt.classify_title("jelly-my-jelly (JELLYJELLY) Gets Listed on KuCoin!"),
                         [("listing", ["JELLYJELLY"])])

    def test_name_words_are_not_tickers(self):
        r = nt.classify_title("Bitget Announcement on the Listing of Cow Protocol (COW)")
        self.assertEqual(r, [("listing", ["COW"])])

    def test_skips(self):
        self.assertEqual(nt.classify_title("Bitget spot copy trading now supports 2 trading pairs"), [])
        self.assertEqual(nt.classify_title("Bitget announcement on the removal of 1 trading pair under spot bot trading on November 22, 2026"), [])
        self.assertEqual(nt.classify_title("Important Notice: Regarding Transfers from/to MEXC Global Limited"), [])

    def test_perp_delist_and_tags(self):
        self.assertEqual(nt.classify_title("Bybit Will Delist the ABCUSDT Perpetual Contract")[0][0], "perp_delist")
        self.assertEqual(nt.classify_title("KuCoin Adds Monitoring Tag to FOO (FOO)")[0][0], "monitoring")
        self.assertEqual(nt.classify_title("Adjustment of Funding Rate Interval for BAR-USDT perpetual")[0][0], "funding_interval")

    def test_prefix_stripped(self):
        self.assertEqual(nt.title_symbols("New Listing: 1000PEPEUSDT Perpetual Contract"), ["PEPE"])


class Cells(unittest.TestCase):
    def path(self, closes):
        return [(c * 1.001, c * 0.999, c) for c in closes]

    def test_short_gain_and_stop(self):
        closes = [100.0] * 4 + [90.0] * 200
        v = nt.cell_return(self.path(closes), -1, 3600, 60, 0.25)
        self.assertAlmostEqual(v, 0.10 - nt.COST, places=6)
        spike = [100.0] * 3 + [140.0] + [100.0] * 200
        v2 = nt.cell_return(self.path(spike), -1, 3600, 60, 0.25)
        self.assertAlmostEqual(v2, -(0.25 + nt.STOP_SLIP) - nt.COST, places=6)

    def test_missing_bar(self):
        self.assertIsNone(nt.cell_return([None] * 300, 1, 3600, 60, 0.1))

    def test_bench_removed(self):
        closes = [100.0] * 2 + [110.0] * 200
        bench = [50.0] * 2 + [55.0] * 200
        v = nt.cell_return(self.path(closes), 1, 3600, 60, 0.25, bench)
        self.assertAlmostEqual(v, -nt.COST, places=6)


class Holm(unittest.TestCase):
    def test_step_down(self):
        out = nt.holm({"a": 0.001, "b": 0.02, "c": 0.5, "d": None})
        self.assertTrue(out["a"][1])
        self.assertFalse(out["c"][1])
        self.assertFalse(out["d"][1])
        self.assertLessEqual(out["a"][0], out["b"][0])

    def test_family_needs_tiny_p(self):
        pv = {f"c{i}": 0.5 for i in range(191)}
        pv["x"] = 0.0004
        self.assertFalse(nt.holm(pv)["x"][1])       # 192 * 0.0004 = 0.077
        pv["x"] = 0.00002
        self.assertTrue(nt.holm(pv)["x"][1])

    def test_verdict(self):
        vals = [0.05 + random.Random(i).uniform(-0.02, 0.02) for i in range(60)]
        v = nt.cell_verdict(vals, (vals[:30], vals[30:]), 34, 0.001)
        self.assertTrue(v["pass"])
        self.assertFalse(nt.cell_verdict(vals[:10], (vals[:5], vals[5:]), 34, 0.001)["pass"])
        self.assertFalse(nt.cell_verdict(vals, (vals[:30], vals[30:]), 34, 0.2)["pass"])


if __name__ == "__main__":
    unittest.main()
