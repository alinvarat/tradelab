import random
import unittest

from core import thin_a as ta
from core.thin_a import HOUR, DAY


def bar(ts, o, h, l, c, qv=10000.0):
    return (ts, o, h, l, c, qv)


def flat_hours(t0, n, px=1.0, qv=10000.0):
    return [bar(t0 + i * HOUR, px, px, px, px, qv) for i in range(n)]


class Costs(unittest.TestCase):
    def test_side_cost_by_age(self):
        self.assertAlmostEqual(ta.side_cost(2, 0.001), 0.011)
        self.assertAlmostEqual(ta.side_cost(30, 0.001), 0.006)
        self.assertAlmostEqual(ta.side_cost(2, 0.001, 2.0), 0.022)

    def test_trade_net(self):
        self.assertAlmostEqual(ta.trade_net(1.0, 1.1, 2, 26, 0.001), 0.1 - 0.011 - 0.006)


class Listing(unittest.TestCase):
    def test_listing_day_needs_a_gap_after_scan_start(self):
        s = ta.SCAN_START
        self.assertIsNone(ta.listing_day([(s, 1, 1, 1, 1, 5.0)], s))                 # already trading at scan start
        self.assertEqual(ta.listing_day([(s + 20 * DAY, 1, 1, 1, 1, 0.0), (s + 21 * DAY, 1, 1, 1, 1, 3.0)], s), s + 21 * DAY)
        self.assertIsNone(ta.listing_day([], s))

    def test_price_at_carries_last_close_and_counts_stale_hours(self):
        bars = [bar(0, 1, 1, 1, 1.5), bar(HOUR, 1, 1, 1, 2.0)]
        self.assertEqual(ta.price_at(bars, 2 * HOUR), (2.0, 0))
        self.assertEqual(ta.price_at(bars, 5 * HOUR), (2.0, 3))
        self.assertIsNone(ta.price_at(bars, HOUR - 1))      # the second bar is not closed yet; the first closes at HOUR

    def test_a1_enters_at_hour_two_close(self):
        h = flat_hours(0, 100)
        e = {r[0]: r for r in ta.listing_entries(h, 0)}
        self.assertEqual(e["A1"][1], 3 * HOUR)               # close of the bar opened at hour 2
        self.assertEqual(e["A1"][2], 1.0)

    def test_a2_dip_needs_a_30_percent_fall_from_the_running_high(self):
        h = flat_hours(0, 60)
        h[5] = bar(5 * HOUR, 1.0, 1.0, 0.65, 0.69)           # close 0.69 <= 0.70 x high 1.0
        e = {r[0]: r for r in ta.listing_entries(h, 0)}
        self.assertEqual(e["A2"][1], 6 * HOUR)
        h2 = flat_hours(0, 60)
        h2[5] = bar(5 * HOUR, 1.0, 1.0, 0.8, 0.72)
        self.assertNotIn("A2", {r[0] for r in ta.listing_entries(h2, 0)})

    def test_a3_breakout_needs_volume_and_a_new_high(self):
        h = [bar(i * HOUR, 1.0, 1.0 + 0.001 * i, 1.0, 1.0, 1000.0) for i in range(30)]
        h[10] = bar(10 * HOUR, 1.0, 1.5, 1.0, 1.4, 5000.0)    # close above the 24 h high, 5x median volume
        e = {r[0]: r for r in ta.listing_entries(h, 0)}
        self.assertEqual(e["A3"][1], 11 * HOUR)
        h[10] = bar(10 * HOUR, 1.0, 1.5, 1.0, 1.4, 1500.0)    # volume too low
        self.assertNotIn("A3", {r[0] for r in ta.listing_entries(h, 0)})

    def test_listing_rows_a1_known_return(self):
        d0 = ta.SCAN_START + 400 * DAY
        daily = [bar(ta.SCAN_START + 8 * DAY, 1, 1, 1, 1, 0.0), bar(d0, 1, 1, 1, 1, 50000.0)]
        h = [bar(d0 + i * HOUR, 1.0, 1.0, 1.0, 1.0 if i < 3 else 1.2, 5000.0) for i in range(41 * 24)]
        rows, why = ta.listing_rows("kucoin", "ABC", daily, h)
        a1 = [r for r in rows if r["rule"] == "A1"][0]
        self.assertEqual(a1["symbol"], "kucoin:ABC")
        r6 = a1["ret"]["6h"]                                  # entry close of hour 2 = 1.0, exit at 3h+6h: close 1.2
        self.assertAlmostEqual(r6["gross"], 0.2)
        self.assertAlmostEqual(r6["net"], 0.2 - 0.011 - 0.011)   # exit age 9h < 24 h: 1.0% haircut + 0.1% fee
        self.assertAlmostEqual(r6["net2"], 0.2 - 0.022 - 0.022)
        self.assertIsNotNone(r6["ctl"])                       # control entries are at 1.2 -> 1.2, so about -0.012
        self.assertLess(r6["ctl"], 0)

    def test_low_first_day_volume_is_skipped(self):
        d0 = ta.SCAN_START + 400 * DAY
        daily = [bar(ta.SCAN_START + 8 * DAY, 1, 1, 1, 1, 0.0), bar(d0, 1, 1, 1, 1, 50000.0)]
        h = [bar(d0 + i * HOUR, 1, 1, 1, 1, 10.0) for i in range(41 * 24)]
        self.assertEqual(ta.listing_rows("kucoin", "ABC", daily, h)[0], [])

    def test_gate_daily_a4(self):
        d0 = ta.SCAN_START + 400 * DAY
        daily = [bar(ta.SCAN_START + 8 * DAY, 1, 1, 1, 1, 0.0)] + [bar(d0 + i * DAY, 1, 1, 1, 1.0 if i < 2 else 1.3, 20000.0) for i in range(45)]
        rows, _ = ta.listing_rows("gate", "XYZ", daily, None, gate=True)
        r = rows[0]["ret"]["3d"]
        self.assertAlmostEqual(r["gross"], 0.3)
        self.assertAlmostEqual(r["net"], 0.3 - 2 * (0.002 + 0.01))


class Shocks(unittest.TestCase):
    def base(self):
        return [bar(i * HOUR, 1.0, 1.0, 1.0, 1.0, 1000.0) for i in range(24 * 40)]

    def test_up_shock_needs_age_return_and_volume(self):
        h = self.base()
        i = 24 * 35
        h[i] = bar(i * HOUR, 1.0, 1.2, 1.0, 1.1, 20000.0)
        e = ta.shock_entries(h, 0.0)
        self.assertEqual([(x[0], x[1], x[2]) for x in e], [("A5", (i + 1) * HOUR, 1.0)])
        h[i] = bar(i * HOUR, 1.0, 1.2, 1.0, 1.1, 6000.0)      # 6x the median only
        self.assertEqual(ta.shock_entries(h, 0.0), [])
        h[i] = bar(10 * HOUR, 1.0, 1.2, 1.0, 1.1, 20000.0)    # too young (< 30 days)
        self.assertEqual(ta.shock_entries(self.base()[:10] + [h[i]], 0.0), [])

    def test_down_shock_threshold(self):
        h = self.base()
        i = 24 * 35
        h[i] = bar(i * HOUR, 1.0, 1.0, 0.8, 0.85, 20000.0)
        self.assertEqual([x[0] for x in ta.shock_entries(h, 0.0)], ["A6"])
        h[i] = bar(i * HOUR, 1.0, 1.0, 0.8, 0.9, 20000.0)     # -10% is not enough
        self.assertEqual(ta.shock_entries(h, 0.0), [])

    def test_one_entry_per_day(self):
        h = self.base()
        i = 24 * 35
        h[i] = bar(i * HOUR, 1.0, 1.2, 1.0, 1.1, 20000.0)
        h[i + 3] = bar((i + 3) * HOUR, 1.0, 1.2, 1.0, 1.1, 20000.0)
        self.assertEqual(len(ta.shock_entries(h, 0.0)), 1)


def synth_rows(n, mean, venue="kucoin", rule="A1", spread=0.05, start=None):
    rng = random.Random(3)
    rows = []
    b = ta.BOUNDS
    for sp, (a, z) in b.items():
        for k in range(n):
            ts = a + (z - a) * k / n
            net = rng.gauss(mean, spread)
            rows.append({"symbol": f"{venue}:S{sp}{k}", "venue": venue, "rule": rule, "kind": rule, "ts": ts,
                         "ret": {"6h": {"net": net, "net2": net - 0.02, "gross": net + 0.02, "ctl": 0.0, "excess": net}}})
    return rows


class Verdict(unittest.TestCase):
    def test_pass_on_a_strong_consistent_edge(self):
        v = ta.verdict(synth_rows(400, 0.06), ["6h"])
        self.assertEqual(v["verdict"], "pass", v)
        self.assertGreaterEqual(v["per_week_validation"], 3)

    def test_kill_on_a_negative_validation(self):
        self.assertEqual(ta.verdict(synth_rows(400, -0.02), ["6h"])["verdict"], "killed")

    def test_too_few_events_per_week_blocks_a_pass(self):
        v = ta.verdict(synth_rows(40, 0.2), ["6h"])
        self.assertNotEqual(v["verdict"], "pass")

    def test_duplicates_make_the_data_invalid(self):
        rows = synth_rows(100, 0.05)
        v = ta.verdict(rows + rows[:30], ["6h"])
        self.assertTrue(v["verdict"].startswith("invalid data"))

    def test_double_cost_negative_blocks_a_pass(self):
        rows = synth_rows(400, 0.03)
        for r in rows:
            r["ret"]["6h"]["net2"] = r["ret"]["6h"]["net"] - 0.2
        self.assertNotEqual(ta.verdict(rows, ["6h"])["verdict"], "pass")

    def test_summarize_covers_every_rule(self):
        s = ta.summarize(synth_rows(100, 0.05))
        self.assertEqual(set(s["per_rule"]), set(ta.RULE_HOLDS))
        self.assertEqual(s["per_rule"]["A2"]["verdict"], "no data")
        self.assertIn("audit_top", s["per_rule"]["A1"])


class Fetchers(unittest.TestCase):
    def test_parse_bars_column_orders(self):
        from research.studies import thin_a as io
        self.assertEqual(io.parse_bars("kucoin", [["100", "1.0", "1.5", "2.0", "0.5", "7", "99"]]), [(100, 1.0, 2.0, 0.5, 1.5, 99.0)])
        self.assertEqual(io.parse_bars("mexc", [[100000, "1.0", "2.0", "0.5", "1.5", "7", 103599, "99"]]), [(100, 1.0, 2.0, 0.5, 1.5, 99.0)])
        self.assertEqual(io.parse_bars("bitget", [["100000", "1.0", "2.0", "0.5", "1.5", "7", "99", "98"]]), [(100, 1.0, 2.0, 0.5, 1.5, 99.0)])
        self.assertEqual(io.parse_bars("gate", [["100", "99", "1.5", "2.0", "0.5", "1.0", "7", "true"]]), [(100, 1.0, 2.0, 0.5, 1.5, 99.0)])
        self.assertEqual(io.parse_bars("kucoin", [["x"], None]), [])
        self.assertEqual(io.parse_bars("kucoin", None), [])

    def test_clean_bars_rejects_bars_outside_the_window(self):
        from research.studies import thin_a as io
        g = {}
        bars = [(50, 1, 1, 1, 1, 1), (100, 1, 1, 1, 1, 1), (100, 2, 2, 2, 2, 2), (3000, 1, 1, 1, 1, 1)]
        out = io.clean_bars(bars, 100, 1000, g)
        self.assertEqual([b[0] for b in out], [100])
        self.assertEqual(g["out_of_window"], 2)

    def test_universe_flags_ranks_51_to_350_and_drops_leveraged(self):
        from research.studies import thin_a as io
        items = [(f"C{i:03d}", 1000.0 - i, "") for i in range(400)] + [("BTC3L", 5.0, "")]
        syms = io.universe_symbols({"kucoin": items, "gate": [("AAA", 0.0, "1700000000")]})
        d = {s.split(":")[1]: s for s in syms}
        self.assertEqual(d["C000"], "kucoin:C000:L")
        self.assertEqual(d["C049"], "kucoin:C049:L")
        self.assertEqual(d["C050"], "kucoin:C050:LS")
        self.assertEqual(d["C349"], "kucoin:C349:LS")
        self.assertEqual(d["C350"], "kucoin:C350:L")
        self.assertNotIn("BTC3L", d)
        self.assertEqual(d["AAA"], "gate:AAA:L:1700000000")


class ShardRows(unittest.TestCase):
    def test_rows_thin_a_with_fake_fetch(self):
        from unittest import mock
        from research.studies import thin_a as io
        d0 = ta.SCAN_START + 400 * DAY
        daily = [bar(ta.SCAN_START + 8 * DAY, 1, 1, 1, 1, 0.0), bar(d0, 1, 1, 1, 1, 50000.0)]
        hourly = [bar(d0 + i * HOUR, 1.0, 1.0, 1.0, 1.0 if i < 3 else 1.2, 5000.0) for i in range(41 * 24)]

        def fake(venue, base, interval, start, end, gaps):
            return daily if interval == "1d" else hourly
        with mock.patch.object(io, "fetch_bars", fake):
            out = io.rows_thin_a(["kucoin:ABC:L", "gate:XYZ:L:%d" % int(d0)])
        rules = sorted(r["rule"] for r in out["rows"])
        self.assertIn("A1", rules)
        self.assertEqual(rules.count("A4"), 0)               # fake daily bars have one day only: no d0+1 for Gate
        self.assertTrue(all(r["symbol"].startswith("kucoin:") for r in out["rows"]))


class ForwardLogic(unittest.TestCase):
    def test_diff_listings_seeds_then_detects_new_and_gone(self):
        seen, miss = {}, {}
        new, gone, seen, miss = ta.diff_listings(seen, {"kucoin": {"A", "B"}}, 100, miss)
        self.assertEqual((new, gone), ([], []))                       # first call only seeds
        new, gone, seen, miss = ta.diff_listings(seen, {"kucoin": {"A", "B", "C"}}, 200, miss)
        self.assertEqual(new, [("kucoin", "C")])
        new, gone, seen, miss = ta.diff_listings(seen, {"kucoin": {"A", "C"}}, 300, miss)
        self.assertEqual(gone, [])                                    # one missing poll is not yet gone
        new, gone, seen, miss = ta.diff_listings(seen, {"kucoin": {"A", "C"}}, 400, miss)
        self.assertEqual(gone, [("kucoin", "B")])
        new, gone, seen, miss = ta.diff_listings(seen, {"kucoin": set()}, 500, miss)   # a failed fetch changes nothing
        self.assertEqual((new, gone), ([], []))

    def test_exec_gap_uses_bid_against_ask_and_size(self):
        small = {"bid": 1.05, "ask": 1.06, "bid_sz": 100, "ask_sz": 100}
        ref = {"bid": 0.99, "ask": 1.00, "bid_sz": 200, "ask_sz": 50}
        g, side, size = ta.exec_gap(small, ref)
        self.assertEqual(side, "sell_small")
        self.assertAlmostEqual(g, 0.05)
        self.assertAlmostEqual(size, 50.0)                            # limited by the 50-unit reference ask

    def test_f2_candidates_filter_collisions_size_and_persistence(self):
        small = {"AAA": {"bid": 1.05, "ask": 1.06, "bid_sz": 100, "ask_sz": 100},
                 "BBB": {"bid": 3.0, "ask": 3.1, "bid_sz": 100, "ask_sz": 100},      # 3x the reference: ticker collision
                 "CCC": {"bid": 1.05, "ask": 1.06, "bid_sz": 1, "ask_sz": 1}}        # too small
        ref = {"AAA": {"bid": 0.99, "ask": 1.00, "bid_sz": 200, "ask_sz": 200},
               "BBB": {"bid": 1.0, "ask": 1.01, "bid_sz": 200, "ask_sz": 200},
               "CCC": {"bid": 0.99, "ask": 1.00, "bid_sz": 200, "ask_sz": 200}}
        c, n, coll = ta.f2_candidates(small, ref, {"AAA": {"dep": True, "wd": False}}, {"AAA"})
        self.assertEqual((n, coll, [x["base"] for x in c]), (3, 1, ["AAA"]))
        self.assertTrue(c[0]["persist"])
        self.assertEqual(c[0]["status"], {"dep": True, "wd": False})

    def test_f3_due_fires_each_offset_once(self):
        w = [{"key": "k", "t0": 0, "done": []}]
        due, w = ta.f3_due(w, 3700)
        self.assertEqual([o for _, o in due], [3600])
        due, w = ta.f3_due(w, 5 * 3600)
        self.assertEqual([o for _, o in due], [4 * 3600])
        due, w = ta.f3_due(w, 25 * 3600)
        self.assertEqual([o for _, o in due], [24 * 3600])
        self.assertEqual(w, [])

    def test_one_full_walk_of_the_collector(self):
        import json
        import sys
        import tempfile
        from pathlib import Path
        from unittest import mock
        from research.studies import thin_a_forward as fw

        def q(bid, ask):
            return {"bid": bid, "ask": ask, "bid_sz": 500.0, "ask_sz": 500.0, "vol": 1000.0}
        polls = [
            {"kucoin": {"AAA": q(1.0, 1.01)}, "gate": {}, "mexc": {}, "bitget": {}, "binance": {"AAA": q(1.0, 1.01), "BTC": q(50000, 50001)}},
            {"kucoin": {"AAA": q(1.0, 1.01), "NEW": q(2.0, 2.1)}, "gate": {}, "mexc": {}, "bitget": {}, "binance": {"AAA": q(1.0, 1.01), "BTC": q(50000, 50001)}},
            {"kucoin": {"AAA": q(1.0, 1.01), "NEW": q(2.2, 2.25)}, "gate": {}, "mexc": {}, "bitget": {}, "binance": {"AAA": q(1.0, 1.01), "BTC": q(50000, 50001)}},
        ]
        clock = iter([1000.0, 4600.0, 8200.0])
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(fw, "books", side_effect=polls), mock.patch.object(fw, "coin_status", return_value={}), \
                mock.patch.object(fw, "announcements", return_value=[]), mock.patch.object(fw.time, "time", side_effect=lambda: next(clock)), \
                mock.patch.object(sys, "argv", ["x", td]):
            for _ in range(3):
                fw.main()
            rows = [json.loads(x) for x in (Path(td) / "ledger" / "f1_listings.jsonl").read_text().splitlines()]
        kinds = [r["kind"] for r in rows]
        self.assertEqual(kinds, ["new", "snap"])                      # poll 1 seeds, poll 2 sees NEW, poll 3 snapshots it one hour later
        self.assertEqual(rows[0]["base"], "NEW")
        self.assertAlmostEqual(rows[1]["age_h"], 1.0)
        self.assertAlmostEqual(rows[1]["spread"], 2.25 / 2.2 - 1, places=5)


if __name__ == "__main__":
    unittest.main()
