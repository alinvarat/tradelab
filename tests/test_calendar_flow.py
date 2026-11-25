"""Offline tests for calendar_flow_1 (core/calendar_flow.py, research/studies/calendar_flow.py): synthetic data only."""
import json
import math
import time
import unittest
from datetime import date, datetime, timezone
from unittest import mock

from core import calendar_flow as cf
from research.studies import binance_vision as bv
from research.studies import calendar_flow as cfs


def ts(y, m=1, d=1, h=0):
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())


class Basics(unittest.TestCase):
    def test_variant_count_and_bar(self):
        self.assertEqual(cf.K_TOTAL, 22)
        self.assertEqual(len(cf.NEWPERP_VARIANTS), cf.K_VARIANTS["R2"])
        self.assertAlmostEqual(cf.BAR, 0.05 / 22)
        self.assertLess(cf.BAR, 0.0023)

    def test_short_gain_formula(self):
        self.assertAlmostEqual(cf.leg_gain(-1, 100.0, 50.0), 0.5)         # a halving is +50%, never +100%
        self.assertAlmostEqual(cf.leg_gain(-1, 100.0, 150.0), -0.5)
        self.assertAlmostEqual(cf.leg_gain(1, 100.0, 110.0), 0.1)

    def test_chicago_times_follow_dst(self):
        F, S, X = cf.weekend_times(date(2024, 1, 5))                     # winter, CST = UTC-6
        self.assertEqual((F, S, X), (ts(2024, 1, 5, 22), ts(2024, 1, 7, 23), ts(2024, 1, 9, 23)))
        F, S, X = cf.weekend_times(date(2024, 7, 5))                     # summer, CDT = UTC-5
        self.assertEqual((F, S, X), (ts(2024, 7, 5, 21), ts(2024, 7, 7, 22), ts(2024, 7, 9, 22)))
        F, S, _ = cf.weekend_times(date(2024, 3, 8))                     # spring forward on Sunday 10 March
        self.assertEqual(S - F, 48 * 3600)
        F, S, _ = cf.weekend_times(date(2024, 11, 1))                    # fall back on Sunday 3 November
        self.assertEqual(S - F, 50 * 3600)

    def test_fridays_window(self):
        self.assertEqual(cf.fridays(ts(2024, 5, 30), ts(2024, 6, 5)), [date(2024, 5, 31)])

    def test_walk_stop_first_and_gap(self):
        flat = (0, 100.0, 100.0, 100.0, 100.0)
        both = (3600, 100.0, 110.0, 90.0, 100.0)                          # touches stop 105 and target 95
        px, k, why = cf.walk([flat, both], -1, 105.0, 95.0)
        self.assertEqual((px, k, why), (105.0, 1, "stop"))
        gap = (3600, 108.0, 109.0, 107.0, 108.0)                          # opens above the short stop: fills at the open
        px, k, why = cf.walk([flat, gap], -1, 105.0, None)
        self.assertEqual((px, why), (108.0, "stop"))
        px, k, why = cf.walk([flat, flat], 1, 95.0, 101.0)
        self.assertEqual((k, why), (1, "time"))
        px, k, why = cf.walk([flat, (3600, 100.0, 102.0, 99.0, 101.0)], 1, 95.0, 101.0)
        self.assertEqual((px, why), (101.0, "target"))

    def test_funding_window_and_stamp_jitter(self):
        t = 1_700_000_000
        f = cf.Funding([(t + 0.003, 0.01), (t + 28800.002, 0.02)])
        self.assertAlmostEqual(f.sum(t - 100, t), 0.01)                   # settlement at hh:00:00.003 counts at exit == t
        self.assertAlmostEqual(f.sum(t, t + 100), 0.0)                    # and not at entry == t
        self.assertAlmostEqual(f.pnl(-1, t - 100, t), 0.01)               # short receives a positive rate
        self.assertAlmostEqual(f.pnl(1, t - 100, t), -0.01)
        self.assertTrue(f.covers(t, t + 3600))
        self.assertFalse(f.covers(t + 10 * 86400, t + 10 * 86400 + 3600))

    def test_funding_hole_inside_a_window_is_not_zero_funding(self):
        t = 1_700_000_000
        full = cf.Funding([(t + 28800 * k, 0.0001) for k in range(10)])
        holed = cf.Funding([(t + 28800 * k, 0.0001) for k in range(10) if k not in (3, 4, 5)])
        self.assertTrue(full.covers(t, t + 28800 * 9))
        self.assertFalse(holed.covers(t, t + 28800 * 9))                  # a 32h hole must skip the trade
        self.assertTrue(holed.covers(t, t + 28800 * 2))                   # a window before the hole is fine

    def test_sane_catches_bad_rows(self):
        good = cf.make_trade(-1, 100.0, 90.0, 0.0014)
        self.assertEqual(cf.sane([{"symbol": "A", "ts": 1, "ret": {"h": good}}]), [])
        bad = dict(good, entry=0.0)
        self.assertTrue(cf.sane([{"symbol": "A", "ts": 1, "ret": {"h": bad}}]))
        wrong = dict(good, net=good["net"] + 0.5)
        self.assertTrue(cf.sane([{"symbol": "A", "ts": 1, "ret": {"h": wrong}}]))
        pump = cf.make_trade(1, 100.0, 260.0, 0.0014)                     # a long that gains +160% is real, not an error
        self.assertEqual(cf.sane([{"symbol": "A", "ts": 1, "ctl": {"h": pump}}]), [])
        impossible = dict(cf.make_trade(-1, 100.0, 90.0, 0.0014), exit=-5.0)
        self.assertTrue(cf.sane([{"symbol": "A", "ts": 1, "ret": {"h": impossible}}]))


class Stable(unittest.TestCase):
    T = 1_700_000_040

    def bars(self, n=130):
        return [[self.T + 60 * k, 1.0, 1.0, 1.0, 1.0] for k in range(n)]

    def test_target_trade_cooldown_and_fee_scenarios(self):
        b = self.bars()
        b[0][2:5] = [1.0012, 1.0012, 1.0012]                             # signal bar: +12 bp -> sell the stablecoin
        b[1][1:5] = [1.0011, 1.0012, 1.0000, 1.0001]                      # entry bar closes within 2 bp of 1.0000
        b[3][1:5] = [1.0020, 1.0020, 1.0020, 1.0020]                      # inside the 30 minute cooldown: ignored
        b[40][2:5] = [1.0015, 1.0015, 1.0015]                             # after the cooldown: a second signal
        rows, gaps, cool = cf.stable_rows("USDCUSDT", [tuple(x) for x in b])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["ts"], self.T + 60 * 41)
        r = rows[0]
        self.assertEqual((r["side"], r["exit_reason"]), (-1, "target"))
        gain = 1 - (1.0001 * 1.0001) / (1.0011 * 0.9999)
        self.assertAlmostEqual(r["ret"]["f0"]["net"], gain, places=9)
        self.assertAlmostEqual(r["ret"]["f10"]["net"], gain - 0.0020, places=9)     # 10 bp per side
        self.assertAlmostEqual(r["ret"]["f0"]["dcost"], 0.0002, places=9)            # doubling adds 2 x 1 bp spread
        self.assertAlmostEqual(r["ret"]["f2"]["dcost"], 0.0006, places=9)
        self.assertEqual(cf.sane(rows), [])
        self.assertEqual(r["ctl"]["f0"]["side"], 1)

    def test_stop_taken_before_target(self):
        b = self.bars(70)
        b[0][2:5] = [1.0012, 1.0012, 1.0012]
        b[1][1:5] = [1.0011, 1.0045, 1.0011, 1.0040]
        rows, _g, _c = cf.stable_rows("USDCUSDT", [tuple(x) for x in b])
        self.assertEqual(rows[0]["exit_reason"], "stop")
        self.assertLess(rows[0]["ret"]["f0"]["net"], 0)
        self.assertGreater(rows[0]["ret"]["f0"]["exit"], rows[0]["ret"]["f0"]["entry"])

    def test_buy_below_par(self):
        b = self.bars(70)
        b[0][2:5] = [0.9985, 0.9985, 0.9985]
        b[1][1:5] = [0.9986, 0.9999, 0.9986, 0.9999]
        rows, _g, _c = cf.stable_rows("USDCUSDT", [tuple(x) for x in b])
        self.assertEqual(rows[0]["side"], 1)
        self.assertGreater(rows[0]["ret"]["f0"]["net"], 0.0010)


class NewPerp(unittest.TestCase):
    def test_listing_detection(self):
        self.assertFalse(cf.first_bar_is_listing(ts(2020)))
        self.assertTrue(cf.first_bar_is_listing(ts(2020, 1, 2)))

    def test_variants_stop_and_hedge(self):
        t0 = (1_700_000_000 // 3600) * 3600
        h1, btc = [], {}
        for k in range(24 * 9):
            t = t0 + 3600 * k
            hi = 140.0 if k == 30 else 100.0
            h1.append((t, 100.0, hi, 100.0, 100.0, 1.0))
            btc[t] = (t, 50000.0, 50000.0, 50000.0, 50000.0, 1.0)
        fund = cf.Funding([(t0 - 57600 + 28800 * j, 0.0001) for j in range(40)])
        row, skipped = cf.newperp_row("NEWUSDT", h1, btc, fund, fund)
        self.assertEqual(skipped, 0)
        self.assertEqual(row["ts"], t0)
        self.assertEqual(sorted(row["ret"]), ["V1", "V2", "V3"])
        v1 = row["ret"]["V1"]
        self.assertEqual((v1["reason"], v1["exit"], v1["side"]), ("stop", 135.0, -1))
        self.assertAlmostEqual(v1["cost"], 0.0028)                       # two legs
        self.assertEqual(v1["hedge"], [50000.0, 50000.0])
        self.assertEqual(row["ret"]["V2"]["reason"], "time")
        self.assertEqual(row["ctl"]["V1"]["side"], 1)
        self.assertEqual(cf.sane([row]), [])
        self.assertIsNone(cf.newperp_row("X", [], btc, fund, fund)[0])

    def test_missing_funding_skips_variant(self):
        t0 = (1_700_000_000 // 3600) * 3600
        h1 = [(t0 + 3600 * k, 100.0, 100.0, 100.0, 100.0, 1.0) for k in range(24 * 9)]
        btc = {b[0]: b for b in h1}
        row, skipped = cf.newperp_row("X", h1, btc, None, None)
        self.assertIsNone(row)
        self.assertEqual(skipped, 3)


class Weekend(unittest.TestCase):
    def synthetic(self):
        F, S, _X = cf.weekend_times(date(2024, 5, 31))
        base = lambda t: 100.0 + math.sin(t / 40000.0) * 0.5            # noqa: E731
        pf = base(F)
        h1, btc = [], {}
        for t in range(ts(2024, 4, 20), ts(2024, 6, 12), 3600):
            if S <= t < S + 4 * 3600:
                px = base(t) * 1.10
                bar = (t, px, px, px, px, 1e6)
            elif t == S + 4 * 3600:
                px = base(t) * 1.10
                bar = (t, px, px, pf - 0.01, pf, 1e6)                     # touches the Friday price
            else:
                px = base(t)
                bar = (t, px, px, px, px, 1e6)
            h1.append(bar)
            btc[t] = (t, 100.0, 100.0, 100.0, 100.0, 1e6)
        fund = cf.Funding([(t, 0.0001) for t in range(ts(2024, 4, 19), ts(2024, 6, 13), 28800)])
        return h1, btc, fund, F, S, pf

    def test_fade_to_friday_close(self):
        h1, btc, fund, F, S, pf = self.synthetic()
        rows, gaps = cf.weekend_rows("ETHUSDT", h1, btc, fund, fund, ts(2024, 5, 30), ts(2024, 6, 5))
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertTrue(r["signal"])
        self.assertEqual((r["F"], r["S"], r["ts"]), (F, S, S))
        t = r["ret"]["gapfade"]
        self.assertEqual((t["side"], t["reason"]), (-1, "target"))
        self.assertAlmostEqual(t["exit"], pf)
        self.assertAlmostEqual(t["cost"], 0.0028)
        self.assertTrue(0.07 < t["net"] < 0.1, t["net"])
        self.assertEqual(cf.sane(rows), [])
        self.assertEqual(r["ctl"]["gapfade"]["side"], 1)

    def test_btc_is_not_hedged(self):
        h1, btc, fund, _F, _S, _pf = self.synthetic()
        rows, _g = cf.weekend_rows("BTCUSDT", h1, btc, fund, fund, ts(2024, 5, 30), ts(2024, 6, 5))
        self.assertAlmostEqual(rows[0]["ret"]["gapfade"]["cost"], 0.0014)
        self.assertIsNone(rows[0]["ret"]["gapfade"]["hedge"])

    def test_members_are_top_ten_by_volume(self):
        rows = [{"kind": "wk_cand", "F": 100, "symbol": f"S{k:02d}", "qv30": 1e9 - k * 1e6, "signal": True, "S": 150,
                 "ts": 150} for k in range(12)]
        events, weeks, low = cf.weekly_members(rows)
        self.assertEqual(len(events), 10)
        self.assertEqual({e["symbol"] for e in events}, {f"S{k:02d}" for k in range(10)})
        self.assertEqual((weeks, low), (1, 1e9 - 9e6))
        self.assertTrue(all(e["kind"] == "weekend_fade" for e in events))


class Expiry(unittest.TestCase):
    def test_types_and_last_friday(self):
        self.assertEqual(cf.last_friday(2024, 2), date(2024, 2, 23))
        self.assertEqual(cf.expiry_type(ts(2024, 6, 28)), "quarterly")
        self.assertEqual(cf.expiry_type(ts(2024, 7, 26)), "monthly")
        self.assertEqual(cf.expiry_type(ts(2024, 7, 19)), "weekly")
        self.assertEqual(cf.expiry_type(ts(2024, 7, 18)), "daily")
        days = cf.last_friday_days(2024, (2024, 3))
        self.assertEqual(days, [ts(2024, 1, 26), ts(2024, 2, 23), ts(2024, 3, 29)])

    def test_nearest_strike_uses_round_strikes_only(self):
        self.assertEqual(cf.nearest_strike(64300, [63000, 64000, 64250, 65000], 1000), 64000)
        self.assertEqual(cf.nearest_strike(64500, [64000, 65000], 1000), 64000)
        self.assertIsNone(cf.nearest_strike(64500, [64250], 1000))
        self.assertIsNone(cf.nearest_strike(64500, None, 1000))

    def test_pin_signal_window_and_trade(self):
        X1, X2 = ts(2024, 6, 10), ts(2024, 6, 11)
        spot00 = {X1: 64300.0, X2: 64900.0}
        perp = {}
        for X in (X1, X2):
            for k in range(480):
                last = k == 479 and X == X1
                perp[X + 60 * k] = (X + 60 * k, 64300.0, 64300.0, 64100.0 if last else 64300.0, 64100.0 if last else 64300.0)
        info = {X1: {"strikes": [63000.0, 64000.0, 65000.0]}, X2: {"strikes": [63000.0, 64000.0, 65000.0]}}
        fund = cf.Funding([(X1 + 8 * 3600 + 0.003, 0.0001)])
        rows, cnt = cf.pin_rows("BTCUSDT", info, spot00, perp, fund, 1000)
        self.assertEqual(len(rows), 1)                                    # day 2: 65000 is only 0.15% away, no signal
        t = rows[0]["ret"]["pin"]
        self.assertEqual(t["side"], -1)                                   # K below P: short
        self.assertAlmostEqual(t["net"], (1 - 64100 / 64300) - 0.0014 + 0.0001, places=9)
        self.assertEqual(rows[0]["src"], "api")
        self.assertEqual(cnt["signals"], 1)

    def test_pin_grid_fallback_counted(self):
        X = ts(2024, 6, 10)
        perp = {X + 60 * k: (X + 60 * k, 64300.0, 64300.0, 64300.0, 64300.0) for k in range(480)}
        fund = cf.Funding([(X + 8 * 3600, 0.0001)])
        rows, cnt = cf.pin_rows("BTCUSDT", {X: {"strikes": None}}, {X: 64300.0}, perp, fund, 1000)
        self.assertEqual(cnt["grid_strikes"], 1)
        self.assertEqual(rows[0]["src"], "grid")

    def test_unpin_variants(self):
        X = ts(2024, 6, 28)
        perp = {X + 8 * 3600 - 60: (X + 8 * 3600 - 60, 100.0, 100.0, 100.0, 100.0)}
        for k in range(1440):
            t = X + 8 * 3600 + 60 * k
            perp[t] = (t, 100.0, 100.0, 96.0 if k == 10 else 100.0, 96.0 if k == 10 else 100.0)
        fund = cf.Funding([(X + h * 3600, 0.0001) for h in (8, 16, 24, 32)])
        rows, cnt = cf.unpin_rows("BTCUSDT", [X], perp, fund)
        r = rows[0]
        self.assertEqual((r["ret"]["V1"]["reason"], r["ret"]["V1"]["exit"]), ("stop", 97.0))
        self.assertEqual(r["ret"]["V2"]["reason"], "time")
        self.assertEqual(r["ctl"]["V1"], r["ret"]["V2"])
        self.assertEqual(r["ts"], X + 8 * 3600)
        self.assertEqual(cf.sane(rows), [])


class DayOfWeek(unittest.TestCase):
    def panel(self):
        t0 = ts(2023, 11, 6)                                              # a Monday
        days = [t0 + 86400 * k for k in range(60)]
        bars = {"BTCUSDT": [(d, 0, 0, 0, 100.0 * 1.01 ** k, 5e6) for k, d in enumerate(days)]}
        for j in range(12):
            bars[f"C{j}USDT"] = [(d, 0, 0, 0, 10.0 * 1.03 ** k, 5e6) for k, d in enumerate(days)]
        d, close, qv = cf.fa.panel(bars)
        return d, close, qv

    def test_monday_leg_is_sunday_close_to_monday_close(self):
        days, close, qv = self.panel()
        series, missing = cf.dow_legs(days, close, qv, {d: 0.0001 for d in days})
        mon = dict(series["btc_long_Mon"])
        for t, r in series["btc_long_Mon"]:
            if time.gmtime(t).tm_wday == 0:
                self.assertAlmostEqual(r, 0.01 - 0.004, places=9)         # 1% day minus 0.4% round trip
            else:
                self.assertEqual(r, 0.0)
        sun_entries = [r for t, r in series["btc_long_Sun"] if time.gmtime(t).tm_wday == 6]
        self.assertTrue(sun_entries and all(abs(r - 0.006) < 1e-9 for r in sun_entries))
        self.assertEqual(mon[days[1]], 0.0)                               # Tuesday: flat
        self.assertEqual(missing, 0)

    def test_alt_minus_btc_costs_and_funding(self):
        days, close, qv = self.panel()
        fd = {d: 0.0001 for d in days}
        s1, _ = cf.dow_legs(days, close, qv, fd)
        s2, _ = cf.dow_legs(days, close, qv, fd, cost_mult=2.0)
        wed1 = [r for t, r in s1["alt_minus_btc_Wed"] if time.gmtime(t).tm_wday == 2]
        wed2 = [r for t, r in s2["alt_minus_btc_Wed"] if time.gmtime(t).tm_wday == 2]
        self.assertAlmostEqual(wed1[-1], 0.03 - 0.01 - 0.008 + 0.0001, places=9)
        self.assertAlmostEqual(wed2[-1], 0.03 - 0.01 - 0.016 + 0.0001, places=9)
        self.assertEqual(wed1[0], 0.0)                                    # fewer than 31 days of history: no position

    def test_top_by_volume_needs_history_and_volume(self):
        days, close, qv = self.panel()
        picks = cf.top_by_volume(days, close, qv)
        self.assertEqual(picks[29], [])
        self.assertEqual(len(picks[40]), 12)
        self.assertNotIn("BTCUSDT", picks[40])


class Report(unittest.TestCase):
    def rows(self, win=True, per_split=400):
        out = []
        for sp, y in (("train", 2021), ("validation", 2023), ("test", 2025)):
            for k in range(per_split):
                t = ts(y) + k * 157000
                px = 99.0 if win else 101.0
                out.append({"symbol": f"S{k}", "market": f"S{k}", "ts": t, "kind": "x",
                            "ret": {"h": cf.make_trade(-1, 100.0, px + (k % 7) * 0.01, 0.0014)},
                            "ctl": {"h": cf.make_trade(1, 100.0, px + (k % 7) * 0.01, 0.0014)}})
        return out

    def test_pass_needs_the_gate_and_all_criteria(self):
        rep = cf.rule_report(self.rows(), ["h"], n_boot=2000)
        self.assertEqual(rep["verdict"], "PASS", rep)
        self.assertTrue(rep["gate_3_per_week"])
        self.assertGreater(rep["events_per_week"], 3)
        thin = cf.rule_report(self.rows(per_split=40), ["h"], n_boot=2000)
        self.assertFalse(thin["passed"])
        self.assertTrue(thin["passed_stats"])
        self.assertIn("diagnostic", thin["verdict"])

    def test_rule_that_does_not_beat_its_random_control_cannot_pass(self):
        rows = self.rows()
        for r in rows:                     # the mirrored trade earns the same as the real one: no directional edge
            r["ctl"]["h"] = dict(r["ret"]["h"])
        rep = cf.rule_report(rows, ["h"], n_boot=2000)
        self.assertFalse(rep["criteria"]["beats_random_control"])
        self.assertFalse(rep["passed"])
        for r in rows:
            r.pop("ctl")                   # no control rows at all: also not a pass
        self.assertFalse(cf.rule_report(rows, ["h"], n_boot=2000)["passed"])

    def test_losing_rule_fails(self):
        rep = cf.rule_report(self.rows(win=False), ["h"], n_boot=2000)
        self.assertEqual(rep["verdict"], "fail")
        self.assertFalse(rep["passed"])

    def test_double_cost_check(self):
        rows = self.rows()
        for r in rows:                     # a thin edge: 0.1% net, but the double cost 0.14% turns it negative
            r["ret"]["h"] = cf.make_trade(-1, 100.0, 99.74, 0.0014)
        rep = cf.rule_report(rows, ["h"], n_boot=2000)
        self.assertGreater(rep["splits"]["validation"]["mean"], 0)
        self.assertLess(rep["splits"]["validation"]["mean_2x"], 0)
        self.assertFalse(rep["criteria"]["double_cost_positive"])
        self.assertFalse(rep["passed"])

    def test_invalid_rows_void_the_verdict(self):
        rows = self.rows()
        rows[0]["ret"]["h"] = dict(rows[0]["ret"]["h"], exit=-1.0)
        rep = cf.rule_report(rows, ["h"], n_boot=2000)
        self.assertEqual(rep["verdict"], "invalid")

    def test_empty_rule_does_not_raise(self):
        rep = cf.rule_report([], ["h"], n_boot=2000)
        self.assertFalse(rep["passed"])


class Summarize(unittest.TestCase):
    def test_empty_and_mixed_rows_survive(self):
        with mock.patch.object(cfs, "_yahoo_cme_gap", return_value={}):
            out = cfs.summarize_calendar_flow_1([])
            for k in ("R1_stable_revert", "R2_newperp_short", "R3_weekend_fade", "R4_day_of_week", "R5_expiry_pin",
                      "R6_expiry_unpin"):
                self.assertIn(k, out)
                self.assertNotEqual(out[k].get("verdict"), "error", out[k])
            days = [ts(2023, 11, 6) + 86400 * k for k in range(60)]
            rows = [{"kind": "daily_bars", "symbol": "BTCUSDT", "t": days, "c": [100.0 * 1.01 ** k for k in range(60)],
                     "q": [5e6] * 60, "funding": [(d + 28800, 0.0001) for d in days]}]
            rows += [{"kind": "daily_bars", "symbol": f"C{j}USDT", "t": days, "c": [10.0 * 1.03 ** k for k in range(60)],
                      "q": [5e6] * 60} for j in range(12)]
            out = cfs.summarize_calendar_flow_1(rows)
            self.assertNotEqual(out["R4_day_of_week"].get("verdict"), "error", out["R4_day_of_week"])
            self.assertEqual(len(out["R4_day_of_week"]["legs"]), 14)
            json.dumps(out, default=str)

    def test_registered_as_sharded_study(self):
        from research.studies import run
        self.assertIsNotNone(run.sharded_study("calendar_flow_1"))
        self.assertIn("calendar_flow_1", run.sharded_names())


class Listing(unittest.TestCase):
    def test_list_files_reads_first_month(self):
        pre = "data/futures/um/monthly/klines/ABCUSDT/1h/"
        xml = ("<ListBucketResult><IsTruncated>false</IsTruncated>"
               f"<Contents><Key>{pre}ABCUSDT-1h-2021-04.zip</Key></Contents>"
               f"<Contents><Key>{pre}ABCUSDT-1h-2021-04.zip.CHECKSUM</Key></Contents>"
               f"<Contents><Key>{pre}ABCUSDT-1h-2021-03.zip</Key></Contents></ListBucketResult>")

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return xml.encode()
        self.assertEqual(bv.list_files("futures/um", "monthly", "klines", "ABCUSDT", "1h", opener=lambda u, t: R()),
                         ["2021-03", "2021-04"])


if __name__ == "__main__":
    unittest.main()
