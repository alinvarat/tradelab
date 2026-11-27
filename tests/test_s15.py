"""Offline tests for the S1-S5 stage-0 probe arithmetic (core/s15.py). Small inputs with answers known by hand."""
import unittest

from core import s15


class Shared(unittest.TestCase):
    def test_poisson_upper(self):
        self.assertAlmostEqual(s15.poisson_upper95(0), 2.9957, places=2)
        self.assertAlmostEqual(s15.poisson_upper95(5), 10.51, places=1)

    def test_top_share(self):
        self.assertAlmostEqual(s15.top_share({"a": 5, "b": 3, "c": 1, "d": 1, "e": 10}, 4), 19 / 20)
        self.assertEqual(s15.top_share({}), 0.0)

    def test_sd_step_needs_20_returns(self):
        self.assertIsNone(s15.sd_step([1.0 + 0.01 * i for i in range(10)], 1))
        closes = [100.0 * (1.01 if i % 2 else 1.0) for i in range(60)]
        self.assertGreater(s15.sd_step(closes, 1), 0.0)


class S1(unittest.TestCase):
    def test_refresh_kill_arithmetic(self):
        self.assertAlmostEqual(s15.refresh_seconds(2000), 240.0)
        self.assertAlmostEqual(s15.refresh_seconds(500), 60.0)

    def test_book_round_trip(self):
        bids, asks = [(99.0, 10)], [(101.0, 10)]
        self.assertAlmostEqual(s15.book_round_trip(bids, asks, 100.0), 0.02)
        self.assertIsNone(s15.book_round_trip(bids, asks, 5000.0))      # book too thin: not measured

    def test_cluster_and_approach(self):
        pos = [{"coin": "X", "side": "long", "liq": 90.0, "notional": 600.0},
               {"coin": "X", "side": "long", "liq": 90.2, "notional": 400.0},
               {"coin": "X", "side": "long", "liq": 80.0, "notional": 5000.0}]
        cl = s15.ladder_clusters(pos)
        self.assertEqual(len(cl), 2)
        near = [c for c in cl if c["lo"] == 90.0][0]
        self.assertEqual(near["notional"], 1000.0)
        self.assertEqual(near["n"], 2)
        books = {"X": {"bids": [(90.9, 1.0)], "asks": [(91.1, 1.0)]}}
        ap = s15.approaches(cl, {"X": 91.0}, books)
        self.assertEqual(len(ap), 1)             # the 80.0 cluster is 12% away
        self.assertAlmostEqual(ap[0]["visible_depth"], 90.9)


class S2(unittest.TestCase):
    def test_fee(self):
        self.assertAlmostEqual(s15.pool_fee("A / B 1%"), 0.01)
        self.assertAlmostEqual(s15.pool_fee("A / B", "pumpswap"), 0.0025)
        self.assertAlmostEqual(s15.pool_fee("A / B", "unknown"), 0.003)

    def test_cp_round_trip(self):
        self.assertAlmostEqual(s15.cp_round_trip(98.0, 0.0), 1 - (49 * 24.5 / 73.5) / 49, places=9)      # tiny pool, no fee: two impacts
        rt = s15.cp_round_trip(2_000_000.0, 0.003)
        self.assertTrue(0.0059 < rt < 0.0063)
        self.assertGreater(s15.cp_round_trip(2000.0, 0.003), rt)                 # thinner pool costs more
        self.assertIsNone(s15.cp_round_trip(None, 0.003))

    def test_entrants_skip_baseline(self):
        polls = [{"t": 0, "ids": ["a", "b"]}, {"t": 30, "ids": ["a", "c"]}, {"t": 60, "ids": ["c", "b", "d"]}]
        e = s15.new_entrants(polls)
        self.assertEqual([(x["id"], x["first_t"], x["prev_t"]) for x in e], [("c", 30, 0), ("d", 60, 30)])

    def test_distinct_sellers(self):
        tr = [{"kind": "sell", "wallet": "w1", "t": 100}, {"kind": "sell", "wallet": "w1", "t": 120},
              {"kind": "buy", "wallet": "w2", "t": 130}, {"kind": "sell", "wallet": "w3", "t": 10}]
        self.assertEqual(s15.distinct_sellers(tr, 4000), 0)
        self.assertEqual(s15.distinct_sellers(tr, 200), 2)


class S3(unittest.TestCase):
    def test_norm_and_universe(self):
        self.assertEqual(s15.norm_base("AAPLSTOCK_USDT"), "AAPL")
        self.assertEqual(s15.norm_base("EURUSD_USDT"), "EURUSD")
        self.assertEqual(s15.norm_base("STOCK_USDT"), "STOCK")
        perps = [{"venue": "gate", "name": "GOLD_USDT", "vol": 5}, {"venue": "mexc", "name": "XAUUSD_USDT", "vol": 9},
                 {"venue": "mexc", "name": "AAPL_USDT", "vol": 7}, {"venue": "gate", "name": "PEPE_USDT", "vol": 99}]
        u = s15.pick_s3_universe(perps, 40)
        self.assertEqual([x["base"] for x in u], ["XAUUSD", "AAPL"])       # PEPE not in the table, GOLD merged with XAUUSD

    def test_episodes_and_same_sign(self):
        ser = [(0, 0.0), (300, 0.02), (600, 0.02), (900, 0.0), (1200, 0.02), (1500, 0.0)]
        self.assertEqual(s15.episodes(ser, 0.01), [(300, 600)])
        self.assertEqual(s15.episodes([(0, 0.02), (300, 0.02), (1200, 0.02), (1500, 0.02)], 0.01), [(0, 300), (1200, 1500)])
        day = [(i * 300, 0.001) for i in range(20)]
        self.assertEqual(s15.same_sign_days(day), (1, 1))
        mixed = [(i * 300, 0.001 if i % 2 else -0.001) for i in range(20)]
        self.assertEqual(s15.same_sign_days(mixed), (1, 0))

    def test_gap_series_and_month_scale(self):
        self.assertEqual(s15.gap_series({0: 101.0, 300: 99.0}, {0: 100.0, 600: 1.0}), [(0, 101.0 / 100.0 - 1.0)])
        self.assertAlmostEqual(s15.month_scale(0, 30.44 * 86400), 1.0)


class S4(unittest.TestCase):
    def test_features_and_match(self):
        a = s15.features("Will the price of Bitcoin be above $100,000 on Nov 28?")
        b = s15.features("Bitcoin price", 100000.0, "greater")
        self.assertEqual((a["cat"], a["entity"], a["level"], a["direction"]), ("crypto", "BTC", 100000.0, "above"))
        self.assertTrue(s15.pair_match(a, b, 1000, 1000 + 1800))
        self.assertFalse(s15.pair_match(a, b, 1000, 1000 + 7200))
        w = s15.features("Will the highest temperature in Chicago be 55° or higher on Nov 28?")
        self.assertEqual((w["cat"], w["entity"], w["level"], w["direction"]), ("weather", "chicago", 55.0, "above"))
        self.assertIsNone(s15.features("Who wins the game?"))

    def test_sources(self):
        self.assertEqual(s15.sources_of("Resolves per CF Benchmarks index"), frozenset({"cfb"}))
        self.assertTrue(s15.source_mismatch(frozenset({"cfb"}), frozenset({"coinbase"})))
        self.assertFalse(s15.source_mismatch(frozenset({"cfb"}), frozenset()))

    def test_fee_lock_allocate(self):
        self.assertAlmostEqual(s15.kalshi_fee(100, 0.5), 1.75)
        self.assertAlmostEqual(s15.kalshi_fee(10, 0.5), 0.18)
        self.assertAlmostEqual(s15.lock_net(0.45, 0.50, 0.02, 0.0, 100), 4.98)
        self.assertAlmostEqual(s15.allocate([{"net_usd": 1.0, "cost_usd": 20.0, "days": 1.0}]), 1.0 / 147.0)
        self.assertEqual(s15.allocate([{"net_usd": -1.0, "cost_usd": 20.0, "days": 1.0}]), 0.0)


class S5(unittest.TestCase):
    def test_bar_gap_events(self):
        ts = [i * 60 for i in range(10)]
        a = {t: 100.0 for t in ts}
        b = {t: 100.0 for t in ts}
        va = {t: 1.0 for t in ts}
        for t in (120, 180, 240):
            a[t] = 102.0                      # ln(1.02) = 1.98% >= 1.5%
        a[420] = 102.0                        # a single minute: not an event
        self.assertEqual(s15.bar_gap_events(a, b, va, va), [(120, 240)])
        va2 = dict(va)
        va2[180] = 0.0                        # no volume on one venue in the middle minute: the run breaks
        self.assertEqual(s15.bar_gap_events(a, b, va2, va), [])

    def test_median_gap(self):
        self.assertAlmostEqual(s15.median_abs_log_gap({0: 1.0, 1: 1.0}, {0: 1.0, 1: 1.0}), 0.0)
        self.assertIsNone(s15.median_abs_log_gap({0: 1.0}, {1: 1.0}))


class Registered(unittest.TestCase):
    def test_studies_registered(self):
        run = open("research/studies/run.py").read()
        self.assertIn("research.studies.s15_probe", run)
        from research.studies import s15_probe
        self.assertEqual(sorted(s15_probe.STUDIES), ["s1_hl_ladder", "s2_dex_trending", "s3_anchor_perps", "s4_kalshi_poly", "s5_stale_quote"])


if __name__ == "__main__":
    unittest.main()


class Eval(unittest.TestCase):
    def test_s2_evaluate(self):
        from core import s15_eval as ev
        polls = [{"t": i * 30, "ok": True} for i in range(10)] + [{"t": 400, "ok": False}]
        self.assertAlmostEqual(ev.covered_hours(polls), 270 / 3600.0)
        rows = [{"qualifies": True, "delay_s": 30, "sellers": 3} for _ in range(8)] + [{"qualifies": True, "delay_s": 30, "sellers": 0}] * 3
        out = ev.s2_evaluate(rows, polls, hours_required=0.01)
        self.assertEqual(out["sell_measured"], 11)
        self.assertEqual(out["sell_no_exit"], 3)
        self.assertTrue(any(k.startswith("exit") for k in out["kills"]))      # 3/11 > 20%
        self.assertFalse(any(k.startswith("count") for k in out["kills"]))    # 11 in 0.075 h is a huge rate: no count kill
        self.assertEqual(ev.s2_evaluate(rows, polls)["status"], "RUNNING")

    def test_s2_count_kill_and_void(self):
        from core import s15_eval as ev
        polls = [{"t": i * 30, "ok": True} for i in range(3000)]              # about 25 h covered
        out = ev.s2_evaluate([{"qualifies": True, "delay_s": 30, "sellers": 5}] * 2, polls, hours_required=20)
        self.assertTrue(out["monthly_qualifying"] < 100)
        self.assertTrue(out["status"].startswith("KILL: count"))
        bad = [{"t": i * 30, "ok": i % 3 == 0} for i in range(3000)]
        self.assertTrue(ev.s2_evaluate([], bad, hours_required=0.0)["status"].startswith("VOID"))

    def test_s4_evaluate(self):
        from core import s15_eval as ev
        snaps = [{"t": i * 3600, "matched": [], "alloc_yield": 0.0} for i in range(48)]
        out = ev.s4_evaluate(snaps)
        self.assertTrue(out["status"].startswith("KILL"))
        self.assertEqual(out["pairs_per_day"], 0.0)
        snaps = [{"t": i * 3600, "matched": [{"k": f"K{i}-{j}", "p": f"P{i}-{j}", "mismatch": j == 0} for j in range(6)], "alloc_yield": 0.05}
                 for i in range(48)]
        out = ev.s4_evaluate(snaps)
        self.assertAlmostEqual(out["pairs_per_day"], 144.0)
        self.assertAlmostEqual(out["mismatch_share"], 1 / 6)
        self.assertTrue(out["status"].startswith("SURVIVES"))
        self.assertEqual(ev.s4_evaluate(snaps[:5])["status"], "RUNNING")
        low = [{"t": i * 3600, "matched": snaps[i]["matched"], "alloc_yield": 0.01} for i in range(48)]
        self.assertTrue(ev.s4_evaluate(low)["status"].startswith("KILLED as standalone"))
