"""Offline tests for core/p1_rest.py (synthetic series, no network), research/studies/p4_newperp.py step 0 helpers and the P1/P4 protocol lock."""
import hashlib
import unittest
from pathlib import Path

from core import d1_liq as d1
from core import p1_rest as p1
from research.studies import p4_newperp as p4

PROTO = Path(__file__).resolve().parents[1] / "research" / "studies" / "protocol_p1p4_20261126.md"
ADD2 = PROTO.with_name("protocol_p1p4_20261126_addendum_step2.md")


def flat(price=100.0, qv=10000.0, n=6000):
    s = d1.Series()
    base = int((d1.START - d1.T0) // 60) - 1700
    for i in range(base, base + n):
        s.o[i] = s.h[i] = s.l[i] = s.c[i] = price
        s.qv[i], s.tb[i] = qv, qv / 2
    return s, base


def bar(s, i, low=None, high=None, close=100.0, qv=10000.0):
    s.o[i] = 100.0
    s.l[i] = 100.0 if low is None else low
    s.h[i] = 100.0 if high is None else high
    s.c[i] = close
    s.qv[i] = qv


class Fills(unittest.TestCase):
    def test_touch_is_not_a_fill_through_is(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=96.95)           # limit 97.00; needs low <= 96.903
        self.assertEqual(p1.find_fills(s)[(0.03, 1)], [])
        bar(s, i, low=97.0)            # exactly at the limit: still not a fill
        self.assertEqual(p1.find_fills(s)[(0.03, 1)], [])
        bar(s, i, low=96.89)
        f = p1.find_fills(s)
        self.assertEqual(f[(0.03, 1)], [i])
        self.assertEqual(f[(0.05, 1)], [])
        self.assertEqual(f[(0.03, -1)], [])

    def test_ask_side_needs_through(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, high=103.05)         # limit 103.00; needs high >= 103.103
        self.assertEqual(p1.find_fills(s)[(0.03, -1)], [])
        bar(s, i, high=103.2)
        self.assertEqual(p1.find_fills(s)[(0.03, -1)], [i])

    def test_deep_wick_fills_every_shallower_cell(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=91.0)            # -9%: through 3, 5 and 8%
        f = p1.find_fills(s)
        self.assertEqual([f[(d, 1)] for d in p1.DS], [[i], [i], [i]])

    def test_volume_floors(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=96.0, qv=4000.0)                  # bar volume below 5,000 USDT
        self.assertEqual(p1.find_fills(s)[(0.03, 1)], [])
        s2, base2 = flat(qv=1000.0)                     # 24 h volume 1.44M < 5M
        bar(s2, base2 + 3000, low=96.0, qv=10000.0)
        self.assertEqual(p1.find_fills(s2)[(0.03, 1)], [])

    def test_missing_reference_bar_is_skipped(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=96.0)
        s.c[i - 2] = float("nan")
        self.assertEqual(p1.find_fills(s)[(0.03, 1)], [])


class Trades(unittest.TestCase):
    def test_bid_fill_gross_and_excursions(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=96.9)
        t = p1.rest_trade(s, 1, i, 97.0, 5)
        self.assertAlmostEqual(t["gross"], 100.0 / 97.0 - 1, places=9)
        self.assertEqual(t["reason"], "time")
        self.assertEqual(t["xi"], i + 6)
        self.assertEqual(t["te"], d1.T0 + i * 60)
        self.assertAlmostEqual(t["mfe"], 3.0 / 97.0, places=9)      # only the fill bar close counts on the fill bar
        self.assertAlmostEqual(t["mae"], 0.1 / 97.0, places=9)

    def test_stop_on_a_later_bar_and_on_the_fill_bar(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, low=96.9)
        bar(s, i + 2, low=90.0)
        t = p1.rest_trade(s, 1, i, 97.0, 5)
        self.assertEqual(t["reason"], "stop")
        self.assertAlmostEqual(t["gross"], -(d1.STOP + d1.STOP_SLIP))
        self.assertEqual(t["x"], d1.T0 + (i + 3) * 60)
        s2, b2 = flat()
        j = b2 + 3000
        bar(s2, j, low=90.0)                            # the fill bar itself trades 7% through the limit: stopped (pessimistic)
        self.assertEqual(p1.rest_trade(s2, 1, j, 97.0, 5)["reason"], "stop")

    def test_ask_fill_loses_when_price_keeps_rising(self):
        s, base = flat()
        i = base + 3000
        bar(s, i, high=103.2)
        for j in range(i + 1, i + 8):
            s.o[j] = s.h[j] = s.l[j] = s.c[j] = 106.0
        t = p1.rest_trade(s, -1, i, 103.0, 5)
        self.assertAlmostEqual(t["gross"], -(106.0 / 103.0 - 1), places=9)

    def test_no_exit_bar_drops_the_fill(self):
        s, base = flat(n=3010)
        i = base + 3000
        bar(s, i, low=96.0)
        self.assertIsNone(p1.rest_trade(s, 1, i + 5, 97.0, 15))

    def test_one_position_at_a_time(self):
        s, base = flat()
        i = base + 3000
        for j in (i, i + 1, i + 20):
            bar(s, j, low=96.9)
        rows = p1.cell_rows(s, "ABCUSDT", [i, i + 1, i + 20], 0.03, 5, 1)
        self.assertEqual([r[1] for r in rows], [i, i + 20])         # i+1 falls before the exit of the first (bar i+6)
        g = dict(zip(p1.FIELDS, rows[0]))
        self.assertAlmostEqual(g["gross"], 100.0 / 97.0 - 1, places=5)
        self.assertEqual(g["side"], 1)

    def test_symbol_rows_covers_all_cells(self):
        s, base = flat()
        bar(s, base + 3000, low=91.0)
        rows, counts = p1.symbol_rows(s, "ABCUSDT")
        cells = {(r[3], r[4], r[2]) for r in rows}
        self.assertEqual(cells, {(d, h, 1) for d in p1.DS for h in p1.HOLDS})
        self.assertEqual(counts["3b"], 1)
        self.assertEqual(counts["3a"], 0)


class Stats(unittest.TestCase):
    def row(self, sym, i, gross, taker=None, ctrl=None):
        return [sym, i, 1, 0.03, 5, gross, ctrl, taker, 0.01, 0.01, "time", d1.T0 + i * 60, d1.T0 + (i + 6) * 60]

    def test_costs_and_controls_are_applied(self):
        f = p1.fill_trade(self.row("A", 100, 0.02, taker=0.01, ctrl=0.0))
        self.assertAlmostEqual(f["net"], 0.02 - 0.0022 - 0.0001)
        self.assertAlmostEqual(f["taker_net"], 0.01 - 0.0040 - 0.0001)
        self.assertAlmostEqual(f["ctrl_net"], -0.0022 - 0.0001)

    def test_cluster_is_one_utc_hour_equal_weight(self):
        i0 = int((d1.START - d1.T0) // 60) + 600                 # a multiple of 60 (START is midnight)
        a = p1.fill_trade(self.row("A", i0 + 5, 0.03))
        b = p1.fill_trade(self.row("B", i0 + 50, 0.01))
        c = p1.fill_trade(self.row("C", i0 + 65, -0.02))
        cl = p1.clusters([a, b, c])
        self.assertEqual(len(cl), 2)
        self.assertEqual(cl[0]["n_fills"], 2)
        self.assertAlmostEqual(cl[0]["gross"], 0.02)
        self.assertAlmostEqual(cl[0]["net"], 0.02 - 0.0023)
        self.assertEqual(cl[1]["t"], cl[0]["t"] + 3600)

    def test_top_share_and_gap(self):
        self.assertGreater(p1.top_share([10.0] + [0.1] * 99), 0.5)
        self.assertLess(p1.top_share([1.0] * 100), 0.5)
        self.assertIsNone(p1.top_share([-1.0, -2.0]))
        fills = [p1.fill_trade(self.row("A", 100, 0.02, taker=0.0)), p1.fill_trade(self.row("B", 200, 0.02, taker=0.01))]
        self.assertAlmostEqual(p1.late_taker_gap(fills), (0.02 - 0.0023 - (0 - 0.0041) + 0.02 - 0.0023 - (0.01 - 0.0041)) / 2)

    def test_cells_and_constants(self):
        self.assertEqual(len(p1.cells()), 18)
        self.assertEqual(p1.cell_id(0.03, 5, 1), "d3|h5m|bid")
        self.assertEqual(p1.cell_id(0.08, 15, -1), "d8|h15m|ask")
        self.assertAlmostEqual(p1.COST, 0.0022)
        self.assertAlmostEqual(p1.COST_TAKER, 0.0040)

    def test_audit_notional_counts_only_prints_through_the_limit_in_the_minute(self):
        ts0 = d1.T0 + 60 * 1000
        prints = [(ts0 + 5, 96.8, 2.0, True), (ts0 + 10, 96.95, 100.0, True), (ts0 + 59, 96.0, 1.0, True), (ts0 + 61, 90.0, 50.0, True),
                  (ts0 - 1, 90.0, 50.0, True)]
        n = p1.through_notional(prints, ts0, 97.0, 1)               # 96.8*2 + 96.0*1 only (96.95 is not 0.1% through 97.0)
        self.assertAlmostEqual(n, 96.8 * 2 + 96.0)
        self.assertTrue(p1.audit_supported(150.0))
        self.assertFalse(p1.audit_supported(149.0))
        self.assertAlmostEqual(p1.through_notional([(ts0 + 1, 103.2, 1.0, False)], ts0, 103.0, -1), 103.2)

    def test_audit_pick_is_deterministic(self):
        self.assertEqual(p1.audit_pick("A", 5, 0.03, 1), p1.audit_pick("A", 5, 0.03, 1))


class P4Step0(unittest.TestCase):
    def test_find_rows_walks_any_nesting_and_dedupes(self):
        row = {"kind": "newperp_short", "symbol": "XUSDT", "ts": 1.0, "ret": {"V1": {"net": 0.1}}}
        out = []
        p4.find_rows({"a": [{"rows": [row, {"kind": "weekend"}]}], "b": {"c": row}}, out)
        self.assertEqual(len(out), 2)

    def test_stats_x_is_n_per_month_times_s_squared(self):
        st = p4.stats([0.1, 0.0, 0.2, 0.1], 2.0, cap=1.0)
        self.assertEqual(st["n"], 4)
        self.assertAlmostEqual(st["N_per_month"], 2.0)
        self.assertAlmostEqual(st["x"], round(2.0 * (st["mean"] / st["sd"]) ** 2, 4), places=3)
        self.assertLessEqual(st["x_capped"], st["x"])


class P4Step1(unittest.TestCase):
    def test_base_names(self):
        self.assertEqual(p4.base_name("1000PEPE"), "PEPE")
        self.assertEqual(p4.base_name("1INCH"), "1INCH")
        self.assertEqual(p4.base_name("kBONK"), "BONK")
        self.assertEqual(p4.base_name("eth"), "ETH")
        self.assertEqual(p4.base_name("1000000MOG"), "MOG")

    def test_step2_bounds_are_the_protocol_ones(self):
        self.assertEqual(p4.STEP2_BOUNDS["train"][0], p4.cf.utc(2023))
        self.assertEqual(p4.STEP2_BOUNDS["test"][1], p4.cf.utc(2026, 10, 29))
        self.assertEqual(p4.KILL1_MIN, 60)


class P4Step2(unittest.TestCase):
    def week(self, n=150, last_close=None, spike=None):
        t0 = p4.cf.utc(2025, 3, 1)
        bars = {}
        for k in range(n):
            t = t0 + k * 3600
            bars[t] = (t, 100.0, 100.0, 100.0, 100.0)
        if last_close is not None:
            t = t0 + (p4.HOLD_BARS - 1) * 3600
            bars[t] = (t, 100.0, 100.0, last_close, last_close)
        if spike is not None:
            t = t0 + 10 * 3600
            bars[t] = (t, 100.0, spike, 100.0, 100.0)
        btc = {t: (t, 100.0, 100.0, 100.0, 100.0) for t in bars}
        return t0, bars, btc

    def test_short_gain_and_cost(self):
        t0, bars, btc = self.week(last_close=80.0)
        t, why = p4.v1_trade(bars, btc, t0)
        self.assertIsNone(why)
        self.assertAlmostEqual(t["gross"], 0.2)
        self.assertAlmostEqual(t["net"], 0.2 - 0.0028)
        self.assertEqual(t["reason"], "time")
        self.assertEqual(t["xt"], t0 + p4.HOLD_BARS * 3600)

    def test_hedge_leg_is_added(self):
        t0, bars, btc = self.week(last_close=80.0)
        last = t0 + (p4.HOLD_BARS - 1) * 3600
        btc[last] = (last, 100.0, 110.0, 100.0, 110.0)          # BTC rallies 10% while the coin falls 20%
        t, _ = p4.v1_trade(bars, btc, t0)
        self.assertAlmostEqual(t["gross"], 0.2 + 0.1)

    def test_stop_at_135_percent(self):
        t0, bars, btc = self.week(spike=140.0)
        t, _ = p4.v1_trade(bars, btc, t0)
        self.assertEqual(t["reason"], "stop")
        self.assertAlmostEqual(t["gross"], -0.35)
        self.assertEqual(t["xt"], t0 + 11 * 3600)
        self.assertAlmostEqual(t["mae"], 0.40)

    def test_short_week_is_a_gap_and_missing_data_drops(self):
        t0, bars, btc = self.week(n=100)
        t, _ = p4.v1_trade(bars, btc, t0)
        self.assertEqual(t["reason"], "gap")
        self.assertEqual(p4.v1_trade(bars, {}, t0), (None, "no_btc_bar"))
        self.assertEqual(p4.v1_trade({}, btc, t0), (None, "no_bar_at_entry"))

    def test_mirror_is_the_opposite_leg(self):
        t0, bars, btc = self.week(last_close=80.0)
        m, _ = p4.v1_trade(bars, btc, t0, 1)
        self.assertAlmostEqual(m["gross"], -0.2)


class Lock(unittest.TestCase):
    def test_protocol_hash(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol_p1p4_20261126.md is locked: write a dated addendum instead of editing it")

    def test_step2_addendum_hash(self):
        self.assertEqual(hashlib.sha256(ADD2.read_bytes()).hexdigest(), ADD2.with_suffix(".sha256").read_text().strip(),
                         "the step 2 addendum is locked: write a new dated addendum instead of editing it")


if __name__ == "__main__":
    unittest.main()
