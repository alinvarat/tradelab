"""Offline tests for core/fxcom.py (synthetic bars only, no network)."""
import json
import math
import unittest
from datetime import date, datetime, timezone

from core import fxcom as fx


def mk(sym, start, closes, opens=None, guard=False):
    bars = []
    for i, c in enumerate(closes):
        o = (opens or {}).get(i, closes[i - 1] if i else c)
        bars.append({"t": start + 3600 * i, "o": o, "c": c})
    return fx.adjust_hourly(sym, bars, guard)


class Calendar(unittest.TestCase):
    def test_nfp_bar_is_13_utc_in_winter_and_12_in_dst(self):
        a = datetime(2025, 3, 7, 8, 30, tzinfo=fx.ET).timestamp()
        self.assertEqual(a, fx.utc(2025, 3, 7, 13) + 1800)
        b = datetime(2025, 8, 1, 8, 30, tzinfo=fx.ET).timestamp()
        self.assertEqual(b, fx.utc(2025, 8, 1, 12) + 1800)
        self.assertEqual(fx.release_times("GC=F", date(2025, 3, 7)), [(8, 30)])
        self.assertEqual(fx.release_times("EURUSD=X", date(2025, 8, 1)), [(8, 30)])
        self.assertEqual(fx.release_times("GC=F", date(2025, 3, 14)), [])      # second Friday

    def test_eia_and_claims_days(self):
        self.assertEqual(fx.release_times("CL=F", date(2025, 3, 5)), [(10, 30)])      # Wednesday
        self.assertEqual(fx.release_times("CL=F", date(2025, 3, 6)), [])
        self.assertEqual(fx.release_times("NG=F", date(2025, 3, 6)), [(10, 30)])      # Thursday
        self.assertEqual(fx.release_times("GC=F", date(2025, 3, 6)), [(8, 30)])       # claims

    def test_london_open_dst(self):
        self.assertEqual(datetime(2025, 7, 1, 8, tzinfo=fx.LON).astimezone(timezone.utc).hour, 7)
        self.assertEqual(datetime(2025, 1, 7, 8, tzinfo=fx.LON).astimezone(timezone.utc).hour, 8)

    def test_holiday_week_skip(self):
        self.assertTrue(fx.is_holiday(date(2025, 11, 27)))                    # Thanksgiving
        self.assertEqual(fx.release_times("GC=F", date(2025, 11, 27)), [])
        self.assertEqual(fx.release_times("CL=F", date(2025, 11, 26)), [])    # same week, Wednesday
        self.assertTrue(fx.is_holiday(date(2025, 12, 25)))
        self.assertFalse(fx.week_has_holiday(date(2025, 7, 3)))               # July 4 is a Friday: not Mon-Thu
        self.assertEqual(fx.release_times("GC=F", date(2025, 7, 3)), [(8, 30)])


class Costs(unittest.TestCase):
    def tr(self, asset, side, pin, pout, t_in, t_out, size=1.0):
        return fx.Trade(t_in, t_out, asset, side, pin, pout, size, 0.0, "g")

    def test_short_gain_and_costs(self):
        t_in = fx.utc(2025, 3, 4, 10)
        t = self.tr("EURUSD=X", -1, 100.0, 90.0, t_in, t_in + 7200)
        self.assertAlmostEqual(fx.trade_frac(t, fx.Rates()), 0.10 - 2 * 0.00015)         # short gain = 1 - exit/entry
        self.assertAlmostEqual(fx.trade_frac(t, fx.Rates(), 2.0), 0.10 - 4 * 0.00015)    # double cost
        self.assertAlmostEqual(fx.trade_frac(t, fx.Rates(), 1.0, flip=True), -0.10 - 2 * 0.00015)

    def test_commodity_holding_cost(self):
        t0 = fx.utc(2025, 3, 4, 0)
        long_ = self.tr("GC=F", 1, 100.0, 100.0, t0, t0 + 86400)
        short = self.tr("GC=F", -1, 100.0, 100.0, t0, t0 + 86400)
        self.assertAlmostEqual(fx.trade_frac(long_, fx.Rates()), -2 * 0.0006 - 0.0004)
        self.assertAlmostEqual(fx.trade_frac(short, fx.Rates()), -2 * 0.0006 - 0.0001)
        self.assertAlmostEqual(fx.trade_frac(short, fx.Rates(), 2.0), -4 * 0.0006 - 0.0002)

    def test_fx_swap_triple_wednesday_and_rate_sign(self):
        wed_in = datetime(2025, 3, 5, 16, tzinfo=fx.ET).timestamp()
        wed_out = datetime(2025, 3, 5, 18, tzinfo=fx.ET).timestamp()
        self.assertAlmostEqual(fx.hold_cost_hourly("EURUSD=X", 1, wed_in, wed_out, fx.Rates()), 3 / 365 * 0.005)
        tue_in = datetime(2025, 3, 4, 16, tzinfo=fx.ET).timestamp()
        tue_out = datetime(2025, 3, 4, 18, tzinfo=fx.ET).timestamp()
        r = fx.Rates({"EUR": [(fx.day_ts(date(2025, 1, 1)), 3.0)], "USD": [(fx.day_ts(date(2025, 1, 1)), 5.0)]},
                     {"EUR": 1, "USD": 1})
        # long EURUSD earns EUR - USD = -2%/yr: cost = markup + 2%
        self.assertAlmostEqual(fx.hold_cost_hourly("EURUSD=X", 1, tue_in, tue_out, r), (0.005 + 0.02) / 365)
        # short USDJPY (long JPY) with USD 5%, JPY 3%: short pays base (USD) and earns quote (JPY): cost = markup + 2%
        r2 = fx.Rates({"JPY": [(fx.day_ts(date(2025, 1, 1)), 3.0)], "USD": [(fx.day_ts(date(2025, 1, 1)), 5.0)]},
                      {"JPY": 1, "USD": 1})
        self.assertAlmostEqual(fx.hold_cost_hourly("USDJPY=X", -1, tue_in, tue_out, r2), (0.005 + 0.02) / 365)

    def test_rates_point_in_time(self):
        r = fx.Rates({"EUR": [(fx.day_ts(date(2025, 1, 1)), 3.0)]}, {"EUR": 45})
        self.assertIsNone(r.get("EUR", fx.day_ts(date(2025, 2, 1))))
        self.assertEqual(r.get("EUR", fx.day_ts(date(2025, 2, 20))), 3.0)
        self.assertEqual(r.annual("GBP", 0), 0.0)
        self.assertEqual(r.missing["GBP"], 1)

    def test_parse_fred(self):
        rows = fx.parse_fred_csv("DATE,DFF\n2025-01-01,4.33\n2025-01-02,.\n2025-01-03,4.3\n")
        self.assertEqual([v for _, v in rows], [4.33, 4.3])


class Data(unittest.TestCase):
    def test_gate_drops_last_and_off_hour(self):
        bars = [{"t": 3600 * i, "o": 1, "c": 1} for i in range(10)] + [{"t": 36000 + 1800, "o": 1, "c": 1}]
        ok, info, clean = fx.gate_hourly(bars, min_bars=5)
        self.assertEqual(info["off_hour"], 1)
        self.assertEqual(len(clean), 10)          # sorted: the off-hour bar is last in time and dropped as unfinished or off
        ok2, _, _ = fx.gate_hourly(bars, min_bars=50)
        self.assertFalse(ok2)

    def test_hourly_roll_guard(self):
        closes = [100.0 + 0.1 * (i % 2) for i in range(200)] + [150.0 + 0.1 * (i % 2) for i in range(200, 260)]
        g = mk("CL=F", fx.utc(2025, 3, 3), closes, guard=True)
        raw = mk("CL=F", fx.utc(2025, 3, 3), closes, guard=False)
        self.assertEqual(g.rolls, 1)
        self.assertAlmostEqual(g.c[200] / g.c[199], 1.0, places=6)
        self.assertAlmostEqual(raw.c[200] / raw.c[199], 1.5, places=2)

    def test_daily_clip(self):
        bars = []
        for i in range(120):
            c = 100.0 * (1 + 0.001 * (i % 3)) * (1.5 if i >= 100 else 1.0)
            bars.append({"t": fx.utc(2024, 1, 1, 17) + 86400 * i, "o": c, "c": c})
        ch = {"meta": {"exchangeTimezoneName": "America/New_York"}, "bars": bars}
        a = fx.build_daily("CL=F", ch, fx.utc(2030), True)
        self.assertGreaterEqual(a.clipped, 1)
        self.assertLess(max(abs(x) for x in a.ret), 0.2)
        raw = fx.build_daily("CL=F", ch, fx.utc(2030), False)
        self.assertGreater(max(abs(x) for x in raw.ret), 0.4)

    def test_session_flags(self):
        h = mk("EURUSD=X", fx.utc(2025, 3, 4), [100.0 + (i % 2) * 0.1 for i in range(60)])
        i17 = next(i for i, x in enumerate(h.ehour) if x == 17)
        self.assertTrue(h.flag[i17])
        self.assertFalse(fx.can_enter(h, i17 - 1))      # entry bar would start at 17:00 ET
        self.assertFalse(fx.can_enter(h, i17))


class HourlyRules(unittest.TestCase):
    def test_r2_enters_at_next_open_without_lookahead(self):
        closes = [100.0 + 0.01 * (i % 2) for i in range(60)] + [101.0] + [101.0 + 0.01 * (i % 2) for i in range(61, 100)]
        start = fx.utc(2025, 3, 4)
        h = mk("EURUSD=X", start, closes, {61: 105.0})
        gs = [g for g in fx.rule_r2(h) if g[0].t_in == h.ts[61]]
        self.assertEqual(len(gs), 1)
        t = gs[0][0]
        self.assertEqual(t.side, 1)
        self.assertAlmostEqual(t.px_in, 105.0, places=6)                 # open of the bar AFTER the signal close
        self.assertAlmostEqual(t.px_out, closes[61], places=6)            # stop hit at close of 61 -> open of 62
        self.assertEqual(t.t_out, h.ts[62])
        self.assertLessEqual(t.size, 20.0)
        # truncating the future does not change the entry
        h2 = mk("EURUSD=X", start, closes[:62], {61: 105.0})
        gs2 = [g for g in fx.rule_r2(h2) if g[0].t_in == h2.ts[61]]
        self.assertEqual(len(gs2), 1)
        self.assertAlmostEqual(gs2[0][0].px_in, 105.0, places=6)
        # a one-bar delay enters one bar later
        gd = [g for g in fx.rule_r2(h, 1) if g[0].t_in == h.ts[62]]
        self.assertEqual(len(gd), 1)

    def test_r3_fades_overextension_and_exits_after_6_bars(self):
        n = 330
        closes = [100.0 * (1 + 0.0005 * math.sin(0.9 * i)) for i in range(n)]
        t = 300
        closes[t] = closes[t - 1] * 0.97
        for i in range(t + 1, n):
            closes[i] = closes[t]
        h = mk("EURUSD=X", fx.utc(2025, 3, 3), closes)
        gs = [g for g in fx.rule_r3(h) if g[0].t_in == h.ts[t + 1]]
        self.assertEqual(len(gs), 1)
        tr = gs[0][0]
        self.assertEqual(tr.side, 1)                                      # opposite of the drop
        self.assertEqual(tr.t_out, h.ts[t + 7])                           # open of bar e+6
        self.assertAlmostEqual(tr.risk, tr.size * 1.5 * abs(closes[t] / closes[t - 6] - 1), places=6)

    def test_r4_continuation_with_et_clock(self):
        start = fx.utc(2025, 1, 6)
        d_idx = 58 * 24 + 13                       # 2025-03-05 13:00 UTC = 08:00 EST
        n = d_idx + 30
        closes = [100.0 * (1 + 0.002 * math.sin(0.37 * i)) for i in range(n)]
        p0 = closes[d_idx - 14]
        for k in range(14):                        # close 19:00 ET prev day .. close 08:00 ET: +2%
            closes[d_idx - 14 + k] = p0 * (1 + 0.02 * k / 13)
        for i in range(d_idx, n):
            closes[i] = p0 * 1.02
        h = mk("GC=F", start, closes)
        self.assertEqual(h.ehour[d_idx], 8)
        gs = [g for g in fx.rule_r4(h) if g[0].t_in == h.ts[d_idx]]
        self.assertEqual(len(gs), 1)
        tr = gs[0][0]
        self.assertEqual(tr.side, 1)
        self.assertEqual(tr.t_out, h.ts[d_idx] + 7 * 3600)               # close of the bar starting 14:00 ET = 15:00 ET
        self.assertEqual(datetime.fromtimestamp(tr.t_out, fx.ET).hour, 15)

    def test_r5_london_breakout_of_asia_range(self):
        base = 24                                   # second day of the series = 2025-01-14 (winter, London = UTC)
        closes = [100.0] * 72
        for k, v in enumerate([100.0, 100.2, 100.0, 100.2, 100.0, 100.1]):
            closes[base + k] = v
        closes[base + 6] = 100.1
        closes[base + 7] = 100.1
        closes[base + 8] = 100.5                    # first close above the Asia high (bar 08:00-09:00 London)
        for i in range(base + 9, 72):
            closes[i] = 100.5
        h = mk("EURUSD=X", fx.utc(2025, 1, 13), closes)
        gs = [g for g in fx.rule_r5(h) if g[0].t_in == h.ts[base + 9]]
        self.assertEqual(len(gs), 1)
        tr = gs[0][0]
        self.assertEqual(tr.side, 1)
        self.assertAlmostEqual(tr.px_in, 100.5, places=6)
        self.assertEqual(tr.t_out, h.ts[base + 15] + 3600)               # 16:00 London close

    def test_r6_fades_release_bar(self):
        n = 290
        closes = [100.0 * (1 + 0.0005 * math.sin(0.9 * i)) for i in range(n)]
        start = fx.utc(2025, 2, 24)
        k = 10 * 24 + 13                            # Thu 2025-03-06 13:00 UTC = 08:00 ET (08:30 release inside)
        closes[k] = closes[k - 1] * 1.01
        for i in range(k + 1, n):
            closes[i] = closes[k]
        h = mk("GC=F", start, closes)
        self.assertEqual(h.ehour[k], 8)
        self.assertIn(k, fx.release_bars(h))
        gs = [g for g in fx.rule_r6(h) if g[0].t_in == h.ts[k + 1]]
        self.assertEqual(len(gs), 1)
        tr = gs[0][0]
        self.assertEqual(tr.side, -1)
        self.assertEqual(tr.t_out, h.ts[k + 4])                           # 3 bars

    def test_r8_spread_entry_legs(self):
        n = 400
        la = [0.001 if i % 2 == 0 else -0.001 for i in range(n)]
        la[300] += 0.003
        ca = [100.0 * math.exp(x) for x in la]
        cb = [50.0] * n
        a = mk("GC=F", fx.utc(2025, 3, 4), ca)
        b = mk("SI=F", fx.utc(2025, 3, 4), cb)
        p = fx.PairH(a, b)
        self.assertTrue(2.5 <= p.z[300] < 4.0)
        gs = [g for g in fx.rule_r8(p) if g[0].t_in == p.ts[301]]
        self.assertEqual(len(gs), 1)
        ga, gb = gs[0]
        self.assertEqual((ga.side, gb.side), (-1, 1))                     # z > 0: short A, long B
        self.assertLessEqual(ga.size, 3.0)
        self.assertAlmostEqual(ga.px_in, ca[300], places=6)               # next open = previous close in the fixture
        self.assertEqual(gb.risk, 0.0)

    def test_cap_groups_open_risk(self):
        def g(t_in, t_out, name):
            return [fx.Trade(t_in, t_out, "GC=F", 1, 1.0, 1.0, 1.0, 0.015, name)]
        ok, skipped = fx.cap_groups([g(0, 100, "a"), g(10, 100, "b"), g(20, 100, "c"), g(200, 300, "d")])
        self.assertEqual([x[0].grp for x in ok], ["a", "b", "d"])
        self.assertEqual(skipped, 1)


class DailyBook(unittest.TestCase):
    def chart(self, f, n=420, start=None):
        start = start or fx.utc(2023, 1, 2, 17)
        bars = []
        for i in range(n):
            c = f(i)
            bars.append({"t": start + 86400 * i, "o": c, "c": c})
        return {"meta": {"exchangeTimezoneName": "America/New_York"}, "bars": bars}

    def test_r1_trend_makes_money_both_ways(self):
        for sign in (1, -1):
            ch = self.chart(lambda i, s=sign: 100.0 * math.exp(s * 0.002 * i + 0.01 * math.sin(i)))
            a = fx.build_daily("GC=F", ch, fx.utc(2030), True)
            series, rec, info = fx.run_daily({"GC=F": a}, fx.Rates(), "R1_tsmom_voltarget")
            self.assertEqual(len(series), 420)
            self.assertTrue(all(r == 0.0 for _, r in series[:253]))
            self.assertGreater(sum(r for _, r in series[260:]), 0)
            self.assertGreater(info["changes"], 0)
            self.assertGreater(info["below_min_notional"], 0)           # weights at 147 USD are tiny

    def test_r7_usd_base_pairs_flip_sign(self):
        syms = ["EURUSD=X", "AUDUSD=X", "USDJPY=X", "USDCHF=X"]
        data = {s: fx.build_daily(s, self.chart(lambda i: 100.0 * (1 + 0.003 * math.sin(i)), 120), fx.utc(2030), True)
                for s in syms}
        d = data["EURUSD=X"].dates[100]

        def rates(jpy):
            t0 = fx.day_ts(date(2020, 1, 1))
            return fx.Rates({"USD": [(t0, 5.0)], "AUD": [(t0, 7.0)], "EUR": [(t0, 4.5)], "CHF": [(t0, 1.0)],
                             "JPY": [(t0, jpy)]}, {k: 1 for k in ("USD", "AUD", "EUR", "CHF", "JPY")})
        w = fx.r7_targets(data, d, rates(0.1), True)           # top: AUD, EUR long; bottom: CHF, JPY short vs USD
        self.assertGreater(w["AUDUSD=X"][0], 0)
        self.assertGreater(w["EURUSD=X"][0], 0)
        self.assertGreater(w["USDJPY=X"][0], 0)                # short JPY = long USDJPY
        self.assertGreater(w["USDCHF=X"][0], 0)
        w2 = fx.r7_targets(data, d, rates(10.0), True)         # JPY now top: long JPY = short USDJPY
        self.assertLess(w2["USDJPY=X"][0], 0)
        self.assertIsNone(fx.r7_targets(data, d, rates(0.1), False))     # only on the last bar of the week


class Evaluation(unittest.TestCase):
    def test_random_control_counts(self):
        pairs = [(1.0, -1.0)] * 20
        r = fx.control_run(20.0, fx.control_trades(pairs), 100, 2000)
        self.assertLess(r["p"], 0.01)                                     # the all-correct rule beats the control
        mid = fx.control_run(0.0, fx.control_trades(pairs), 100, 2000)
        self.assertTrue(0.3 < mid["p"] < 0.7)
        rng_total = fx.control_trades(pairs)(__import__("random").Random(1))
        self.assertEqual(int(rng_total) % 2, 0)                          # 20 trades of +-1: same parity as 20

    def test_minimum_notional(self):
        t_in = fx.utc(2025, 9, 1, 10)
        small = [fx.Trade(t_in, t_in + 7200, "EURUSD=X", 1, 1.0, 1.01, 0.01, 0.0, "s")]       # 1.47 USD notional
        big = [fx.Trade(t_in, t_in + 7200, "EURUSD=X", 1, 1.0, 1.01, 1.0, 0.0, "b")]
        pts, sk = fx.continuous_trades([small], fx.Rates(), fx.utc(2025, 8, 1), fx.utc(2026, 1, 1))
        self.assertEqual((pts, sk), ([], 1))
        pts, sk = fx.continuous_trades([big], fx.Rates(), fx.utc(2025, 8, 1), fx.utc(2026, 1, 1))
        self.assertEqual(sk, 0)
        self.assertAlmostEqual(pts[0][1], 147.0 * (1 + 0.01 - 0.0003))

    def test_month_multiples_and_summary(self):
        pts = [(fx.utc(2025, 1, 10), 300.0), (fx.utc(2025, 1, 20), 441.0)]
        mm = fx.month_mults(pts, fx.utc(2025, 1, 1), fx.utc(2025, 3, 1), 147.0)
        self.assertAlmostEqual(mm[0], 3.0)
        self.assertAlmostEqual(mm[1], 1.0)
        s = fx.equity_summary(pts, fx.utc(2025, 1, 1), fx.utc(2025, 3, 1))
        self.assertEqual((s["months_3x"], s["end_equity"], s["ruined"]), (1, 441.0, False))

    def test_trimmed_mean(self):
        a, b = fx.trimmed_mean([10.0] + [1.0] * 19, 20)
        self.assertAlmostEqual(a, 19 / 20)
        self.assertAlmostEqual(b, 19 / 20)

    def test_ceiling_counts_3x_months(self):
        bars = []
        for i in range(40):
            d = date(2022, 3, 1 + i) if i < 31 else date(2022, 4, i - 30)
            hot = i in (10, 11, 12)
            bars.append({"t": fx.day_ts(d) + 17 * 3600, "o": 100.0, "c": 110.0 if hot else 100.0})
        ch = {"meta": {"exchangeTimezoneName": "UTC"}, "bars": bars}
        a = fx.build_daily("GC=F", ch, fx.utc(2030), False)
        bd, _ = fx._bounds()
        c = fx.ceiling_daily({"GC=F": a}, bd)
        self.assertEqual(c["validation"]["months_3x"], 1)
        self.assertEqual(c["test"]["months_3x"], 0)


def _synth_chart(sym, rng, hourly):
    import random
    r = random.Random(sym + rng)
    bars, c = [], 100.0
    if hourly:
        start, step, n = fx.utc(2025, 1, 1), 3600, 10000
    else:
        start, step, n = fx.utc(2016, 11, 25, 17), 86400, 3650
    for i in range(n):
        o = c
        c = c * (1 + r.gauss(0, 0.0008 if hourly else 0.008))
        bars.append({"t": start + step * i, "o": o, "h": max(o, c), "l": min(o, c), "c": c, "v": 0})
    return {"meta": {"exchangeTimezoneName": "America/New_York"}, "bars": bars}


class Smoke(unittest.TestCase):
    def test_full_study_on_synthetic_data(self):
        saved = fx.HOURLY
        fx.HOURLY = ["GC=F", "SI=F", "CL=F", "BZ=F", "EURUSD=X", "USDJPY=X", "GBPUSD=X"]
        try:
            summ, series = fx.study(lambda s, r, i: _synth_chart(s, r, i == "1h"),
                                    lambda sid: "DATE,X\n2020-01-01,2.0\n2024-01-01,3.0\n", fx.utc(2026, 11, 26), 40)
        finally:
            fx.HOURLY = saved
        self.assertEqual(sorted(series), sorted(fx.ALL_RULES))
        self.assertEqual(sorted(summ["rules"]), sorted(fx.ALL_RULES))
        self.assertIn("CEILING", summ["first_line"])
        self.assertAlmostEqual(summ["judge_daily_bar"], 0.05 / 8)
        self.assertAlmostEqual(summ["judge_hourly_bar"], 0.05 / 8)
        for name, row in summ["rules"].items():
            self.assertIn("screen_pass", row, name)
            self.assertIn("continuous", row, name)
        json.dumps(summ, default=str)
        json.dumps(series, default=str)


if __name__ == "__main__":
    unittest.main()
