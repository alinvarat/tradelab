"""Offline tests for core/forced_flow.py with titles and bodies seen in the 2026-11-25 probe (no prices, no network)."""
import json
import random
import unittest

from core import forced_flow as ff
from core import sweep_stats as ss


class Parsers(unittest.TestCase):
    def test_monitoring_include_only(self):
        t = "Binance Will Extend the Monitoring Tag to Include ANT, FIRO, KP3R, MDX, MOB, REEF, VAI, XMR, ZEC & ZEN, and Remove the Seed Tag for GMX & SUSHI on 2024-01-04"
        self.assertEqual(ff.monitoring_symbols(t), ["ANT", "FIRO", "KP3R", "MDX", "MOB", "REEF", "VAI", "XMR", "ZEC", "ZEN"])
        t2 = "Binance Will Extend the Monitoring Tag to Include COS, DEGO, FORTH, FUN, HOOK, LRC, MBOX, OXT & WIF, Remove the Monitoring Tag for FLOW, and Remove the Seed Tag for ONDO & VIRTUAL on 2026-03-06"
        self.assertEqual(ff.monitoring_symbols(t2), ["COS", "DEGO", "FORTH", "FUN", "HOOK", "LRC", "MBOX", "OXT", "WIF"])
        self.assertEqual(ff.monitoring_symbols("Binance Will Extend the Monitoring Tag to GPS on 2025-03-07"), ["GPS"])
        self.assertEqual(ff.monitoring_symbols("Binance Will Remove the Seed Tag for BONK, EIGEN on 2025-07-21"), [])
        self.assertEqual(ff.monitoring_symbols("Binance Will List Jupiter (JUP) with Seed Tag Applied"), [])

    def test_fut_delist(self):
        self.assertEqual(ff.fut_delist_symbols("Binance Futures Will Delist USDⓈ-M ABCUSDT and DEFUSDT Perpetual Contracts (2026-01-01)"), ["ABC", "DEF"])
        self.assertEqual(ff.fut_delist_symbols("Binance Futures Will Delist 1000XECUSDT Perpetual Contract"), ["XEC"])
        self.assertEqual(ff.fut_delist_symbols("Binance Margin Will Delist ABC on 2026-01-01"), [])
        self.assertEqual(ff.fut_delist_symbols("Binance Futures Will Delist Multiple XⓈ-M Perpetual Contracts (2026-01-01)", "ABCUSDT, DEFUSDT"), ["ABC", "DEF"])
        self.assertEqual(ff.fut_delist_symbols("Binance Futures Will Delist and Update the Leverage & Margin Tiers of XⓈ-M ABCUSDT Perpetual Contracts"), [])

    def test_pair_removal_usdt_only(self):
        txt = "At 2026-11-20 03:00 (UTC): GAS/TRY, HBAR/BNB, ABC/USDT and DEF/USDT"
        self.assertEqual(ff.pair_removal_symbols(txt), ["ABC", "DEF"])
        self.assertEqual(ff.pair_removal_symbols("At 2026-04-24 03:00 (UTC): 1INCH/BTC, WIF/BTC and XRP/MXN"), [])

    def test_flatten_body(self):
        body = json.dumps({"node": "root", "child": [{"node": "element", "tag": "p", "child": [{"node": "text", "text": "At X: AAA/USDT"}]}]})
        self.assertIn("AAA/USDT", ff.flatten_body(body))

    def test_kr(self):
        self.assertEqual(ff.kr_class("[거래지원 종료] 싸이식(CYS) 거래지원 종료 안내"), "delist")
        self.assertEqual(ff.kr_class("투자유의 종목 지정 안내 - 싸이식(CYS)"), "caution")
        self.assertEqual(ff.kr_class("[이벤트] 업비트 입출금 이벤트 (이벤트 종료)"), "")
        self.assertEqual(ff.kr_class("투자유의 종목 지정 해제 안내 - 싸이식(CYS)"), "")
        self.assertEqual(ff.kr_class("거래지원 종료 일정 연장 안내 (CYS)"), "")
        self.assertEqual(ff.kr_class("Notice of Digital Asset Market Support Termination (AAA) (Completed)"), "")
        self.assertEqual(ff.kr_symbols("[거래지원 종료] 싸이식(CYS), 아이콘(ICX) 거래지원 종료"), ["CYS", "ICX"])
        self.assertEqual(ff.kr_symbols("Notice on market support termination (AAA, BBB)"), ["AAA", "BBB"])

    def test_bybit(self):
        self.assertEqual(ff.bybit_class_symbols("Delisting of GALFT, PIXFI, PAWS, B3TR, SAND and MANA"), ("delist", ["GALFT", "PIXFI", "PAWS", "B3TR", "SAND", "MANA"]))
        self.assertEqual(ff.bybit_class_symbols("Delisting of SOLOUSDT Perpetual Contract"), ("perp_delist", ["SOLO"]))
        self.assertIsNone(ff.bybit_class_symbols("Bybit Alpha Delisting of ARENA"))
        self.assertIsNone(ff.bybit_class_symbols("Delisting 2 Spot Trading Pairs on Jun 16, 2026"))


class Events(unittest.TestCase):
    def test_dedupe_and_overlap(self):
        e = [{"fam": "a", "sym": "X", "ts": 1000.0}, {"fam": "a", "sym": "X", "ts": 1000.0 + 86400}, {"fam": "a", "sym": "X", "ts": 1000.0 + 9 * 86400},
             {"fam": "b", "sym": "X", "ts": 1000.0}]
        self.assertEqual(len(ff.dedupe(e)), 3)
        self.assertTrue(ff.overlaps_l1f({"sym": "X", "ts": 5000.0}, [{"sym": "X", "ts": 5000.0 + 6 * 86400}]))
        self.assertFalse(ff.overlaps_l1f({"sym": "X", "ts": 5000.0}, [{"sym": "X", "ts": 5000.0 + 8 * 86400}, {"sym": "Y", "ts": 5000.0}]))

    def test_rules(self):
        self.assertEqual(len(ff.family_rules("mon_tag")), 6)
        self.assertEqual(ff.rule_id("mon_tag", 14400, 60), "mon_tag|h4h|d1m")


def bars(start, n, f, step=60):
    return {start + i * step: f(i) for i in range(n)}


class Simulation(unittest.TestCase):
    def test_short_time_exit(self):
        # price falls 1% per hour from 100: entry at the open of the first bar after the delay, exit 4 h later
        b = bars(0, 400, lambda i: (100 - i / 60.0, 100 - i / 60.0, 100 - i / 60.0, 100 - i / 60.0))
        s = ff.short_trade(b, 60, 0, 60, 14400 // 4)
        self.assertEqual(s["te"], 60)
        self.assertEqual(s["reason"], "time")
        self.assertAlmostEqual(s["gross"], -((100 - 61 / 60.0) / (100 - 1 / 60.0) - 1), places=6)
        self.assertGreater(s["gross"], 0)

    def test_stop_and_slip(self):
        b = bars(0, 400, lambda i: (100, 100 if i < 30 else 130, 100, 100))
        s = ff.short_trade(b, 60, 0, 60, 3600)
        self.assertEqual(s["reason"], "stop")
        self.assertAlmostEqual(s["gross"], -(0.25 + 0.005))

    def test_missing_entry_or_exit(self):
        b = bars(600, 100, lambda i: (1, 1, 1, 1))
        self.assertIsNone(ff.short_trade(b, 60, 0, 60, 3600))          # no bar near the entry
        b2 = bars(0, 30, lambda i: (1, 1, 1, 1))
        self.assertIsNone(ff.short_trade(b2, 60, 0, 60, 3600))         # no bar at the exit

    def test_trade_format_and_gate_inputs(self):
        s = {"te": 60, "x": 3660, "gross": 0.10, "mfe": 0.12, "mae": 0.01, "reason": "time"}
        t = ff.make_trade("X", 0, s, 14400, ctrl_gross=0.01)
        self.assertAlmostEqual(t["net"], 0.10 - 0.006 - 0.001)
        self.assertAlmostEqual(t["ctrl_net"], 0.01 - 0.006 - 0.001)
        # the reversed-side placebo of the sweep gate is -gross - cost + fund
        self.assertAlmostEqual(-t["gross"] - t["cost"] + t["fund"], -0.105)
        trades = [dict(ff.make_trade("X", 1.7e9 + i * 86400 * 5, s, 14400), t=1.7e9 + i * 86400 * 5) for i in range(25)]
        for i, tr in enumerate(trades):
            tr["gross"] = 0.10 + (0.03 if i % 2 else -0.03)
            tr["net"] = tr["gross"] - tr["cost"] - tr["fund"]
        ok, info = ss.gate(trades, {"size": ff.SIZE}, ff.CFG, 125)
        self.assertIn("x", info)

    def test_control_needs_three_coins(self):
        rng = random.Random(1)
        picks = ff.pick_control(rng, "ADA")
        self.assertEqual(len(picks), ff.N_CONTROL)
        self.assertNotIn("ADA", picks)
        b = bars(0, 400, lambda i: (100, 100, 100 - i / 60.0, 100 - i / 60.0))
        cb = {c: b for c in picks[:3]}
        self.assertIsNotNone(ff.control_gross(cb, picks, 60, 0, 60, 3600))
        self.assertIsNone(ff.control_gross({c: b for c in picks[:2]}, picks, 60, 0, 60, 3600))


class Stats(unittest.TestCase):
    def test_stats_and_corr(self):
        st = ff.stats([0.1, 0.2, 0.0, 0.3], 2.0)
        self.assertEqual(st["n"], 4)
        self.assertAlmostEqual(st["per_month"], 2.0)
        self.assertAlmostEqual(st["x"], round(2.0 * st["s"] ** 2, 4), places=3)
        self.assertAlmostEqual(ff.corr([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)
        self.assertIsNone(ff.corr([1, 1, 1], [1, 2, 3]))

    def test_bounds_cover_the_window(self):
        self.assertEqual(ff.BOUNDS["train"][0], ff.START)
        self.assertEqual(ff.BOUNDS["test"][1], ff.END)
        self.assertEqual(ff.BOUNDS["train"][1], ff.BOUNDS["validation"][0])
        self.assertEqual(ff.BOUNDS["validation"][1], ff.BOUNDS["test"][0])


if __name__ == "__main__":
    unittest.main()
