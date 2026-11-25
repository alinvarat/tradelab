import random
import unittest
from array import array
from unittest import mock

from core import passive_mm as mm

D0 = mm.T(2024, 1, 1)


def arr(pairs):
    return array("d", [t for t, _ in pairs]), array("d", [p for _, p in pairs])


def sim(pairs, k=1, tick=1.0, **kw):
    ts, px = arr(pairs)
    return mm.simulate_day(ts, px, D0, tick, k, **kw)


class Basics(unittest.TestCase):
    def test_sample_days_every_tenth_epoch_day(self):
        d = mm.sample_days(mm.T(2022), mm.T(2022, 3))
        self.assertTrue(all((x // 86400) % 10 == 3 for x in d))
        self.assertEqual(len(d), 6)
        self.assertEqual(d[1] - d[0], 10 * 86400)

    def test_pick_universe_is_deterministic_and_skips_majors(self):
        syms = ["BTCUSDT", "ETHUSDT", "USDCUSDT", "BTCUSDC"] + [f"C{i}USDT" for i in range(100)]
        a = mm.pick_universe(syms, exclude_bases=("USDC",), n=30)
        self.assertEqual(a, mm.pick_universe(list(reversed(syms)), exclude_bases=("USDC",), n=30))
        self.assertEqual(len(a), 30)
        self.assertFalse({"BTCUSDT", "ETHUSDT", "USDCUSDT", "BTCUSDC"} & set(a))

    def test_infer_tick_and_load_sorting(self):
        self.assertAlmostEqual(mm.infer_tick([1.0, 1.003, 1.001, 1.001, 1.0]), 0.001)
        self.assertEqual(mm.infer_tick([5.0, 5.0]), 0.0)
        ts, px, n = mm.load_trades([(5, 2.0, 3, True), (1, 1.0, 2, False)])
        self.assertEqual((list(ts), list(px), n), ([1, 5], [1.0, 2.0], 8.0))

    def test_reverse_day_mirrors_time_and_order(self):
        ts, px = arr([(10, 1.0), (20, 2.0)])
        rts, rpx = mm.reverse_day(ts, px, D0)
        self.assertEqual(list(rpx), [2.0, 1.0])
        self.assertEqual(list(rts), [2 * D0 + 86400 - 20, 2 * D0 + 86400 - 10])


class Simulation(unittest.TestCase):
    def test_through_trade_fills_bid_and_hour_flatten(self):
        # ref 100 at 5 s; bid 99 (k=1). Trade at 99 only touches: no fill. Trade at 98 passes through: fill at 99.
        r = sim([(D0 + 5, 100), (D0 + 62, 99), (D0 + 63, 98), (D0 + 3000, 100)])
        self.assertEqual((r["fills"], r["buys"], r["sells"]), (1, 1, 0))
        # long 1 at 99, flattened at last hour trade 100 minus a tick = 99: gross 0 (scale = first ref 100)
        self.assertAlmostEqual(r["gross"], 0.0)
        self.assertAlmostEqual(r["maker_n"], 0.99)
        self.assertAlmostEqual(r["taker_n"], 0.99)
        self.assertEqual(r["flattens"], 1)

    def test_touch_is_not_a_fill(self):
        r = sim([(D0 + 5, 100), (D0 + 62, 99), (D0 + 63, 101)])
        self.assertEqual(r["fills"], 0)
        self.assertEqual(r["gross"], 0.0)

    def test_latency_blocks_a_trade_one_tick_after_decision(self):
        r = sim([(D0 + 5, 100), (D0 + 60.5, 98)])          # decision at 60 s, quote live from 61 s
        self.assertEqual(r["fills"], 0)
        r = sim([(D0 + 5, 100), (D0 + 61.5, 98)])
        self.assertEqual(r["buys"], 1)

    def test_stale_reference_gives_no_quote(self):
        r = sim([(D0 + 5, 100), (D0 + 400, 90)])
        self.assertEqual(r["steps"], 10)                   # 60..300 s, then 420..660 s; the gap in between has no fresh trade

    def test_round_trip_earns_the_spread(self):
        # buy at 99, new reference 100, sell at 101 within the hour; flat afterwards; gross = 2 / scale 100
        r = sim([(D0 + 5, 100), (D0 + 62, 98), (D0 + 100, 100), (D0 + 125, 102)])
        self.assertEqual((r["buys"], r["sells"]), (1, 1))
        self.assertAlmostEqual(r["gross"], 0.02)
        self.assertEqual(r["flattens"], 0)
        self.assertAlmostEqual(mm.net_pnl(r), 0.02 - 0.0002 * (0.99 + 1.01))
        self.assertAlmostEqual(mm.net_pnl(r, 2.0), 0.02 - 0.0004 * 2.0)

    def test_cap_stops_one_sided_accumulation(self):
        pairs = [(D0 + 5, 100)]
        p, t = 100, D0 + 5
        for s in range(1, 10):                              # falling market: a through trade each step
            p -= 2
            pairs.append((D0 + 60 * s + 2, p - 5))
            pairs.append((D0 + 60 * s + 3, p))
        r = sim(pairs, cap=3)
        self.assertEqual(r["buys"], 3)
        self.assertEqual(r["max_inv"], 3)
        self.assertGreater(r["steps_cap"], 0)
        self.assertLess(r["gross"], 0)                      # adverse selection: bought a falling market

    def test_one_fill_per_side_per_step(self):
        r = sim([(D0 + 5, 100), (D0 + 62, 98), (D0 + 63, 97), (D0 + 64, 96)])
        self.assertEqual(r["buys"], 1)

    def test_flat_at_every_hour_boundary(self):
        rnd = random.Random(3)
        pairs, p = [], 100.0
        for i in range(4000):
            p = max(5.0, p + rnd.choice([-1, 0, 1]))
            pairs.append((D0 + i * 21.0, p))
        r = sim(pairs, k=1)
        self.assertGreater(r["fills"], 10)
        self.assertGreaterEqual(r["flattens"], 1)

    def test_sell_side_mirror(self):
        r = sim([(D0 + 5, 100), (D0 + 62, 102), (D0 + 3000, 100)])
        self.assertEqual((r["sells"], r["buys"]), (1, 0))
        # short at 101, flatten buy at 100 + 1 tick = 101: zero gross
        self.assertAlmostEqual(r["gross"], 0.0)

    def test_no_trade_hour_and_thin_day(self):
        self.assertEqual(sim([])["fills"], 0)
        ts, px = arr([(D0 + i, 1.0 + (i % 2)) for i in range(50)])
        self.assertIsNone(mm.process_day(ts, px, D0))

    def test_process_day_has_rows_and_control_for_each_rule(self):
        rnd = random.Random(1)
        pairs, p = [], 100.0
        for i in range(600):
            p = max(5.0, p + rnd.choice([-1, 1]))
            pairs.append((D0 + i * 30.0, p))
        ts, px = arr(pairs)
        row = mm.process_day(ts, px, D0, notional=1e6)
        self.assertEqual(set(row["res"]), set(mm.RULES))
        self.assertEqual(set(row["ctl"]), set(mm.RULES))
        self.assertEqual(row["tick"], 1.0)


def fake(sym, ts, edge, ctl=0.0, fills=5, vol=1e6):
    def res(g):
        return {"gross": g, "maker_n": 0.0, "taker_n": 0.0, "fills": fills, "max_inv": 1, "abs_inv_sum": 2,
                "steps": 10, "steps_cap": 0, "worst_hour": -0.001}
    return {"symbol": sym, "ts": ts, "tick": 0.01, "price": 1.0, "notional": vol,
            "res": {r: res(edge) for r in mm.RULES}, "ctl": {r: res(ctl) for r in mm.RULES}}


def synthetic(edge, ctl, seed=5):
    rnd = random.Random(seed)
    rows = []
    for ts in mm.sample_days():
        for s in ("AUSDT", "BUSDT", "CUSDT"):
            rows.append(fake(s, ts, edge + rnd.gauss(0, 0.0005), ctl + rnd.gauss(0, 0.0005), vol=rnd.random() * 1e7))
    return rows


class Summary(unittest.TestCase):
    def test_real_edge_passes_every_gate(self):
        s = mm.summarize(synthetic(0.003, 0.0))
        self.assertEqual(s["verdict"], "passed", s["gates"])
        self.assertTrue(all(s["gates"].values()))
        self.assertIn("2024", s["pick_by_year"])
        self.assertEqual(set(s["pick_by_daily_volume_third"]) - {"cuts_usdt"}, {"low", "mid", "high"})

    def test_no_edge_is_killed(self):
        s = mm.summarize(synthetic(-0.002, 0.0))
        self.assertEqual(s["verdict"], "killed")

    def test_edge_that_the_reversed_control_also_has_fails_the_control_gate(self):
        s = mm.summarize(synthetic(0.003, 0.004))
        self.assertFalse(s["gates"]["beats_reversed_control_validation"])
        self.assertNotEqual(s["verdict"], "passed")

    def test_fees_can_flip_the_sign(self):
        rows = synthetic(0.0, 0.0)
        for w in rows:
            for r in w["res"].values():
                r["gross"] = 0.0005
                r["maker_n"] = 4.0               # maker fee 0.0008 > gross 0.0005
        s = mm.summarize(rows)
        self.assertLess(s["table"]["k1"]["validation"]["mean_net"], 0)
        self.assertEqual(s["verdict"], "killed")

    def test_table_numbers(self):
        s = mm.summarize([fake("A", mm.T(2024, 1, 3), 0.01, 0.0, fills=4)] * 1, bounds=mm.BOUNDS)
        t = s["table"]["k1"]["validation"]
        self.assertEqual((t["n"], t["mean_net"], t["fills_per_day"], t["positive_days"]), (1, 0.01, 4.0, 1.0))
        self.assertAlmostEqual(t["mean_abs_inv"], 0.2)


class RowsFn(unittest.TestCase):
    def test_rows_counts_gaps_and_builds_rows(self):
        from research.studies import run
        pairs, p = [], 100.0
        rnd = random.Random(2)
        for i in range(300):
            p = max(5.0, p + rnd.choice([-1, 1]))
            pairs.append((D0 + i * 40.0, p, 2.0, True))
        calls = []

        def fake_iter(market, period, kind, sym, d, parse=None, **kw):
            calls.append(d)
            n = len(calls)
            return None if n == 1 else [] if n == 2 else iter(pairs)
        with mock.patch("research.studies.binance_vision.iter_file", fake_iter), \
                mock.patch.object(mm, "sample_days", lambda: [D0, D0 + 86400, D0 + 2 * 86400]):
            out = run.rows_h3_passive_mm(["XUSDT"])
            self.assertEqual(run.rows_h3_passive_mm([])["rows"], [])
        self.assertEqual((out["gaps"]["agg_failed"], out["gaps"]["agg_missing"]), (1, 1))
        self.assertEqual(len(out["rows"]), 1)
        self.assertEqual(out["rows"][0]["symbol"], "XUSDT")
        self.assertIn("k1", out["rows"][0]["res"])


if __name__ == "__main__":
    unittest.main()
