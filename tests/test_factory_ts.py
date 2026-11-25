import random
import unittest

from core import factory_ts as ft

T0 = 1_704_067_200          # 2024-01-01 00:00 UTC, a Monday


def mk(closes, spread=0.0, t0=T0):
    """hourly bars with o = previous close"""
    bars, prev = [], closes[0]
    for k, c in enumerate(closes):
        hi, lo = max(prev, c) * (1 + spread), min(prev, c) * (1 - spread)
        bars.append((t0 + k * 3600, prev, hi, lo, c))
        prev = c
    return bars


def g_of(bars):
    ts, o, h, l, c, _ = ft.grid(bars, 0, 10**11)
    return ts, o, h, l, c


def walk(n, seed=1, vol=0.004):
    r = random.Random(seed)
    p, out = 100.0, []
    for _ in range(n):
        p *= 1 + r.gauss(0, vol)
        out.append(p)
    return out


class Basics(unittest.TestCase):
    def test_grid_fills_missing_hours_flat_and_counts(self):
        b = mk([100, 101, 102, 103])
        del b[2]
        ts, o, h, l, c, miss = ft.grid(b, 0, 10**11)
        self.assertEqual((len(ts), miss), (4, 1))
        self.assertEqual(c[2], c[1])

    def test_resample_4h_aligned_and_complete_only(self):
        b = mk([100 + k for k in range(10)], t0=T0 + 2 * 3600)      # starts at 02:00: first full block is 04-07
        ts, o, h, l, c, _ = ft.grid(b, 0, 10**11)
        ro, rh, rl, rc, end = ft.resample(ts, o, h, l, c, 4)
        self.assertEqual(len(rc), 2)
        self.assertEqual(rc[0], c[5])
        self.assertEqual(ts[end[0]] % (4 * 3600), 3 * 3600)

    def test_rsi_extremes_and_sma(self):
        up = [float(k) for k in range(1, 40)]
        self.assertEqual(ft.rsi(up)[-1], 100.0)
        self.assertAlmostEqual(ft.rsi([float(40 - k) for k in range(39)])[-1], 0.0)
        self.assertEqual(ft.sma([1, 2, 3, 4], 2), [None, 1.5, 2.5, 3.5])


class Engine(unittest.TestCase):
    def test_cost_on_change_and_funding_sign(self):
        ts = [T0 + k * 3600 for k in range(4)]
        c = [100.0] * 4
        pos = [0.0, 1.0, 1.0, 0.0]
        r = dict(ft.hourly_returns(ts, c, pos, {}))
        self.assertAlmostEqual(r[ts[2]], -ft.ONE_WAY)
        self.assertAlmostEqual(r[ts[3]], 0.0)
        self.assertAlmostEqual(dict(ft.hourly_returns(ts, c, pos, {}, cost_mult=2.0))[ts[2]], -2 * ft.ONE_WAY)
        # position 1 held across a settlement at ts[2] with rate +0.01% pays; a short receives
        f = {ts[2]: 0.0001}
        self.assertAlmostEqual(dict(ft.hourly_returns(ts, c, pos, f))[ts[2]], -ft.ONE_WAY - 0.0001)
        neg = dict(ft.hourly_returns(ts, c, [0, -1.0, -1.0, 0], f))
        self.assertAlmostEqual(neg[ts[2]], -ft.ONE_WAY + 0.0001)

    def test_portfolio_weights_daily_and_funding_map(self):
        a, b = [(0, 0.06)], [(0, 0.0), (3600, 0.12)]
        self.assertEqual(ft.portfolio([a, b], 6), [(0, 0.01), (3600, 0.02)])
        self.assertEqual(ft.daily([(0, 1), (3600, 2), (86400, 3)]), [(0, 3), (86400, 3)])
        self.assertAlmostEqual(ft.funding_map([(28800.004, 0.0001), (28800.9, 0.0002)])[28800], 0.0003)

    def test_entries_counts_flat_to_pos_and_flips(self):
        ts = list(range(0, 8 * 3600, 3600))
        pos = [0, 1, 1, 0, -1, 1, 1, 0]
        self.assertEqual(ft.entries(ts, pos, 0, 10**9), 3)

    def test_lev_table_ruin_and_3x(self):
        h = [(T0 + k * 3600, 0.05) for k in range(40)]           # +5% an hour
        t = ft.lev_table(h, 0, 10**11)
        self.assertGreater(t[-1]["median_month"], 3)
        crash = [(T0, -0.2)] + [(T0 + 3600, 0.0)]
        self.assertEqual(ft.lev_table(crash, 0, 10**11, (5,))[0]["ruined"], 1)


class Rules(unittest.TestCase):
    def test_donchian_goes_long_on_breakout_and_stops_out(self):
        flat = [100.0] * 80
        up = [100 + 2 * k for k in range(1, 11)]
        drop = [up[-1] - 6 * k for k in range(1, 15)]
        g = g_of(mk(flat + up + drop, spread=0.001))
        pos = ft.rule_donchian(g, 1, 20, 10)
        self.assertEqual(pos[40], 0.0)
        self.assertEqual(pos[82], 1.0)
        self.assertEqual(pos[98:].count(1.0), 0)   # long left during the drop (stop or 10-bar exit)
        self.assertIn(pos[-1], (0.0, -1.0))

    def test_donchian_4h_decides_only_at_block_ends(self):
        g = g_of(mk(walk(1500, 3), spread=0.002))
        pos = ft.rule_donchian(g, 4, 20, 10)
        for i in range(1, len(pos)):
            if (g[0][i] // 3600) % 4 != 3:
                self.assertEqual(pos[i], pos[i - 1])

    def test_wick_long_fires_on_hammer_only_and_holds(self):
        base = walk(300, 5, vol=0.002)
        b = mk(base)
        t, o, h, l, c = b[250]
        b[250] = (t, o, h, o * 0.9, o * 1.0005)          # 10% wick, close back above the midpoint
        pos = ft.rule_wick(g_of(b), +1, 4)
        self.assertEqual([pos[i] for i in (249, 250, 253, 254)], [0.0, 1.0, 1.0, 0.0])
        self.assertEqual(sum(ft.rule_wick(g_of(mk(base)), +1, 4)), 0.0)
        # a down-wick bar that closes in the lower half of its range is not a signal
        b2 = mk(base)
        t, o, h, l, c = b2[250]
        b2[250] = (t, o, h, o * 0.9, o * 0.91)
        self.assertEqual(ft.rule_wick(g_of(b2), +1, 4)[250], 0.0)

    def test_wick_short_mirror(self):
        base = walk(300, 5, vol=0.002)
        b = mk(base)
        t, o, h, l, c = b[250]
        b[250] = (t, o, o * 1.1, l, o * 0.9995)
        self.assertEqual(ft.rule_wick(g_of(b), -1, 4)[250], -1.0)

    def test_weekly_open_break_long_then_flat_at_week_end(self):
        n = 24 * 7 * 3
        closes = [100.0] * n
        for k in range(24 * 7 * 2 + 10, 24 * 7 * 3):
            closes[k] = 112.0                              # third week breaks above W + 0.5 R
        b = mk(closes, spread=0.01)
        pos = ft.rule_weekly_open(g_of(b))
        self.assertEqual(pos[24 * 7 * 2 + 12], 1.0)
        self.assertEqual(pos[-1], 0.0)

    def test_pullback_long_in_uptrend(self):
        up = [100 * 1.001 ** k for k in range(1200)]
        dip = [up[-1] * (1 - 0.004 * k) for k in range(1, 30)]
        g = g_of(mk(up + dip, spread=0.001))
        pos = ft.rule_pullback(g)
        self.assertTrue(any(p == 1.0 for p in pos[1200:]))
        self.assertTrue(all(p == 0.0 for p in pos[:700]))

    def test_trend_vt_long_in_uptrend_and_size_capped(self):
        g = g_of(mk([100 * 1.0007 ** k for k in range(3000)], spread=0.0005))
        pos = ft.rule_trend_vt(g, 4, 20, 100, 180, 6 * 365)
        self.assertTrue(all(0 <= p <= ft.SIZE_CAP for p in pos))
        self.assertGreater(pos[-1], 0)

    def test_no_lookahead_any_rule(self):
        base = walk(2500, 9, vol=0.006)
        cut = 1700
        alt = base[:cut] + walk(2500 - cut, 77, vol=0.02)
        for name, fn in ft.RULES.items():
            a = fn(g_of(mk(base, spread=0.003)))
            b = fn(g_of(mk(alt, spread=0.003)))
            self.assertEqual(a[:cut - 1], b[:cut - 1], name)


class Gate(unittest.TestCase):
    B = {"validation": (0, 8 * 3600 * 100)}

    def cov(self, bars, funding, failed=()):
        return {"X": {"bars": {"validation": bars}, "hours": {"validation": 800}, "funding": {"validation": funding},
                      "failed": list(failed)}}

    def test_gate(self):
        self.assertTrue(ft.integrity(self.cov(800, 100), self.B)["ok"])
        self.assertFalse(ft.integrity(self.cov(700, 100), self.B)["ok"])
        self.assertFalse(ft.integrity(self.cov(800, 50), self.B)["ok"])
        self.assertFalse(ft.integrity(self.cov(800, 100, ["2024-03"]), self.B)["ok"])

    def test_red_flags_identical_means(self):
        r = {n: {"validation": {"mean_day": 0.001, "p_block": 0.5, "days": 5, "nonzero_days": 5, "losing_days": 1}}
             for n in ("a", "b")}
        self.assertTrue(ft.red_flags(r))


if __name__ == "__main__":
    unittest.main()
