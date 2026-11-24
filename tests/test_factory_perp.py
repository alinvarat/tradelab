"""Offline tests for core/factory_perp.py (factory_crypto_2), synthetic data only."""
import math
import random
import unittest
from statistics import mean, pstdev

from core import factory as fa
from core import factory_perp as fp

T0 = 1_700_006_400          # 2023-11-15 00:00 UTC
DAY = 86400
H = 3600
NAN = float("nan")


class Parsers(unittest.TestCase):
    def test_symbols(self):
        self.assertEqual(fp.base_of("1000PEPEUSDT"), "PEPE")
        self.assertEqual(fp.base_of("1000000MOGUSDT"), "MOG")
        self.assertEqual(fp.base_of("BTCUSDT"), "BTC")
        self.assertTrue(fp.eligible_symbol("1000PEPEUSDT", ("USDC",)))
        self.assertFalse(fp.eligible_symbol("BTCUSDT_240329"))
        self.assertFalse(fp.eligible_symbol("ETHBTC"))
        self.assertFalse(fp.eligible_symbol("USDCUSDT", ("USDC",)))
        self.assertFalse(fp.eligible_symbol("1000USDCUSDT", ("USDC",)))

    def test_kline_csv_header_and_microseconds(self):
        txt = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,"
               "taker_buy_quote_volume,ignore\n"
               "1700006400000,1,2,0.5,1.5,10,1700092799999,100,5,4,60,0\n"
               "1735689600000000,2,3,1,2.5,10,1735775999999999,200,5,4,50,0\n")
        self.assertEqual(fp.parse_kline_csv(txt), [(1700006400, 1.0, 2.0, 0.5, 1.5, 100.0, 60.0),
                                                   (1735689600, 2.0, 3.0, 1.0, 2.5, 200.0, 50.0)])

    def test_funding_csv_rounds_jitter_to_the_minute(self):
        txt = "calc_time,funding_interval_hours,last_funding_rate\n1700006400005,8,0.0001\n1700035199998,8,-0.0002\n"
        self.assertEqual(fp.parse_funding_csv(txt), [(1700006400, 0.0001), (1700035200, -0.0002)])

    def test_dvol_pages(self):
        pages = [{"result": {"data": [[1700006400000, 50, 51, 49, 50.5], [1700092800000, 1, 1, 1, 52]]}},
                 {"result": {"data": [[1700006400000, 0, 0, 0, 50.5]]}}, None]
        self.assertEqual(fp.parse_dvol_pages(pages), [(1700006400, 50.5), (1700092800, 52.0)])

    def test_months_between_is_half_open(self):
        jan25, feb1 = 1674604800, 1675209600           # 2023-01-25, 2023-02-01 00:00 UTC
        self.assertEqual(fp.months_between(jan25, feb1), ["2023-01", "2023-02"])
        self.assertEqual(fp.months_between(jan25, feb1 - DAY), ["2023-01"])


class FundingLookup(unittest.TestCase):
    def test_half_open_sums_and_gate(self):
        f = fp.Funding({"X": [(200, 0.2), (100, 0.1), (300, 0.3)]}, {("X", "2023-02")})
        self.assertAlmostEqual(f.sum("X", 100, 300), 0.5)        # 100 excluded, 300 included
        self.assertEqual(f.count("X", 0, 100), 1)
        self.assertEqual(f.sum("Y", 0, 1000), 0.0)
        self.assertFalse(f.ok("X", 1674604800, 1675209600))      # touches 2023-02
        self.assertTrue(f.ok("X", 1674604800, 1675209600 - DAY))
        self.assertTrue(f.ok("Y", 1674604800, 1675209600))

    def test_settle_hours(self):
        f = fp.Funding({"X": [(3600, 0.1), (3601, 0.1), (7200 * 10, 0.1)]})
        self.assertEqual(f.settle_hours(0, 5), {0, 1})


def flat_panel(n, syms=("AUSDT",), missing=()):
    days = [T0 + k * DAY for k in range(n)]
    close = {d: {s: 10.0 for s in syms if (s, k) not in missing} for k, d in enumerate(days)}
    for d in days:
        close[d]["BTCUSDT"] = 100.0
    return days, close


class RunPerp(unittest.TestCase):
    def setUp(self):
        # settlement at T = days[0]+1d must NOT count for hold 0; each later one ends a hold window (included)
        self.fund = fp.Funding({"AUSDT": [(T0 + DAY, 0.5)] + [(T0 + k * DAY, 0.001) for k in (2, 3, 4)]})

    def test_long_pays_funding_and_2x_doubles_only_cost(self):
        days, close = flat_panel(4)
        feats = [{}] * 4
        s1 = fp.run_perp(days, close, feats, lambda f, i: {"AUSDT": 1.0}, self.fund, hedge=False)
        s2 = fp.run_perp(days, close, feats, lambda f, i: {"AUSDT": 1.0}, self.fund, hedge=False, cost_mult=2.0)
        self.assertAlmostEqual(s1[0][1], -0.001 - 0.002)
        self.assertAlmostEqual(s1[1][1], -0.001)
        self.assertAlmostEqual(s2[0][1], -0.001 - 0.004)
        self.assertAlmostEqual(s2[1][1], -0.001)
        sh = fp.run_perp(days, close, feats, lambda f, i: {"AUSDT": -1.0}, self.fund, hedge=False)
        self.assertAlmostEqual(sh[1][1], 0.001)                  # a short receives positive funding
        self.assertEqual(s1[0][0], days[1])

    def test_hedge_leg_pays_turnover(self):
        days, close = flat_panel(4)
        s = fp.run_perp(days, close, [{}] * 4, lambda f, i: {"AUSDT": 1.0}, self.fund, hedge=True)
        self.assertAlmostEqual(s[0][1], -0.001 - 2 * 0.002)       # long A + short BTC both opened

    def test_vanished_coin(self):
        days, close = flat_panel(4, missing={("AUSDT", 2), ("AUSDT", 3)})
        st = {}
        strat = lambda f, i: {"AUSDT": -1.0} if "AUSDT" in close[days[i]] else {}
        s = fp.run_perp(days, close, [{}] * 4, strat, self.fund, hedge=False, stats=st)
        self.assertAlmostEqual(s[0][1], 0.001 - 0.002)
        self.assertEqual(s[1][1], 0.0)                            # vanished: no return, no funding
        self.assertAlmostEqual(s[2][1], -0.002)                   # exit turnover at the next rebalance
        self.assertEqual((st["vanished_short"], st["vanished_long"]), (1, 0))
        self.assertEqual(st["event_ts"], [days[1], days[2]])


def make_bars(n=70):
    rb = [0.0] + [0.01 if k % 2 else -0.01 for k in range(1, n)]
    btc, c = [], 100.0
    for k in range(n):
        c *= 1 + rb[k]
        btc.append((T0 + k * DAY, c, c, c, c, 5e6, 2.5e6))
    bars = {"BTCUSDT": btc}
    for j in range(10):
        rows = []
        for k in range(n):
            p = 10 * (1 + 0.001 * j) ** k
            imb = 0.1
            if j == 1:
                imb = 0.5 if k == 50 else (0.1 if k % 2 == 0 else -0.1)
            rows.append((T0 + k * DAY, p, p, p, p, 5e6, (imb + 1) / 2 * 5e6))
        bars[f"C{j}USDT"] = rows
    rows, c = [], 10.0
    for k in range(n):
        c *= 1 + 2 * rb[k]
        rows.append((T0 + k * DAY, c, c, c, c, 5e6, 2.75e6))
    bars["C2USDT"] = rows
    return bars


class Features(unittest.TestCase):
    def setUp(self):
        self.bars = make_bars()
        self.fund_rows = {"C0USDT": [(T0 + k * 8 * H, 0.0001) for k in range(3 * 75)]}
        self.days, self.close, self.qv, self.taker = fp.panel_perp(self.bars)
        self.f = fp.perp_features(self.days, self.close, self.qv, self.taker, fp.Funding(self.fund_rows))

    def test_fund7_is_average_daily_funding(self):
        self.assertAlmostEqual(self.f[65]["C0USDT"]["fund7"], 21 * 0.0001 / 7)
        self.assertIsNone(self.f[65]["C4USDT"]["fund7"])

    def test_taker_imbalance_z(self):
        self.assertAlmostEqual(self.f[50]["C1USDT"]["z_imb"], 5.0, places=6)
        self.assertIsNone(self.f[50]["C4USDT"]["z_imb"])           # constant imbalance: sd 0

    def test_beta_and_residual_return(self):
        v = self.f[65]["C2USDT"]
        self.assertAlmostEqual(v["beta60"], 2.0, places=6)
        self.assertAlmostEqual(v["e1"], 0.0, places=9)
        self.assertIsNone(self.f[59]["C2USDT"]["beta60"])          # needs 60 return pairs

    def test_funding_gap_month_blocks_trading(self):
        bad = {("C3USDT", fp.ym(self.days[40] + DAY))}
        f = fp.perp_features(self.days, self.close, self.qv, self.taker, fp.Funding(self.fund_rows, bad))
        self.assertNotIn("C3USDT", f[40])
        self.assertIn("C4USDT", f[40])
        self.assertIn("C3USDT", self.f[40])

    def test_daily_adv_window(self):
        days = [T0 + k * DAY for k in range(25)]
        qv = {d: {"A": float(k), **({} if k == 10 else {"B": 1.0})} for k, d in enumerate(days)}
        adv = fp.daily_adv(days, qv)
        self.assertAlmostEqual(adv[22]["A"], mean(range(2, 22)))
        self.assertNotIn("A", adv[19])
        self.assertNotIn("B", adv[22])                            # day 10 missing inside the window


class Books(unittest.TestCase):
    def test_absorption_residuals(self):
        f = {s: {"r1": x, "z_imb": z} for s, x, z in (("A", 0, 0), ("B", 1, 2), ("C", 2, 4), ("D", 3, 7))}
        a = fp.absorption(f)
        raw = {"A": 0.2, "B": -0.1, "C": -0.4, "D": 0.3}           # z - (-0.2 + 2.3 r1)
        sd = pstdev(raw.values())
        for s, e in raw.items():
            self.assertAlmostEqual(a[s], e / sd)
        self.assertAlmostEqual(pstdev(a.values()), 1.0)

    def test_a1_shorts_high_funding(self):
        f = {f"C{j}": {"fund7": j * 1e-4} for j in range(10)}
        f["X"] = {"fund7": None}
        w = fp.a1_carry({})(f, 0)
        self.assertAlmostEqual(w["C9"], -0.1)
        self.assertAlmostEqual(w["C0"], 0.1)
        self.assertNotIn("X", w)

    def test_a2_holds_half_of_yesterdays_book(self):
        days = [T0, T0 + DAY, T0 + 2 * DAY]
        close = {d: {f"C{j}": 1.0 for j in range(10)} for d in days}
        fn = fp.a2_absorption({"days": days, "close": close, "funding": fp.Funding({})})
        up = {f"C{j}": {"r1": 0.0, "z_imb": float(j)} for j in range(10)}
        down = {f"C{j}": {"r1": 0.0, "z_imb": -float(j)} for j in range(10)}
        w1 = fn(up, 0)
        self.assertAlmostEqual(w1["C9"], -0.05)                   # short high absorption, half book on day one
        self.assertAlmostEqual(w1["C0"], 0.05)
        self.assertEqual(fn(down, 1), {})                         # 0.5*today + 0.5*yesterday cancel
        w3 = fn(down, 2)
        self.assertAlmostEqual(w3["C0"], -0.1)

    def test_rv_regime(self):
        rows, c = [], 100.0
        for k in range(430):
            r = 0 if k == 0 else (0.02 if k >= 400 else 0.01) * (1 if k % 2 else -1)
            c *= 1 + r
            rows.append((T0 + k * DAY, c, c, c, c))
        days = [r[0] for r in rows]
        reg = fp.rv_regime(days, rows)
        self.assertIsNone(reg[394])
        self.assertAlmostEqual(reg[395], 1.0, places=6)
        self.assertAlmostEqual(reg[429], 2.0, places=6)

    def test_dvol_regime_uses_only_finished_candles(self):
        dvol = [(T0 + j * DAY + 8 * H, float(j + 1)) for j in range(8)]    # candles stamped 08:00 UTC
        days = [T0 + k * DAY for k in range(6)]
        reg = fp.dvol_regime(days, dvol, look=3)
        self.assertIsNone(reg[3])
        self.assertAlmostEqual(reg[4], 4 / 2)
        self.assertAlmostEqual(reg[5], 5 / 3)

    def test_regime_book(self):
        f = {f"C{j}": {"r7": j * 0.01, "r3": -j * 0.02} for j in range(10)}
        fn = fp.regime_book([None, 0.5, 1.0, 2.0])
        self.assertEqual(fn(f, 0), {})
        self.assertEqual(fn(f, 1), fa.STRATEGIES["xs_momentum_r7"](f, 1))
        self.assertEqual(fn(f, 2), {})
        self.assertEqual(fn(f, 3), fa.STRATEGIES["xs_reversal_r3"](f, 3))

    def test_pct_ranks_ties(self):
        self.assertEqual(fp.pct_ranks({"a": 1, "b": 2, "c": 2, "d": 3}), {"a": 0.0, "b": 0.5, "c": 0.5, "d": 1.0})

    def test_beta_neutral(self):
        w = fp.beta_neutral(["L1", "L2"], ["S1"], {"L1": 1.0, "L2": 1.0, "S1": 3.0})
        self.assertEqual(set(w), {"L1", "L2", "S1"})
        self.assertAlmostEqual(w["L1"], 0.375)
        self.assertAlmostEqual(w["S1"], -0.25)
        self.assertAlmostEqual(sum(abs(x) for x in w.values()), 1.0)
        w = fp.beta_neutral(["L1"], ["S1"], {"L1": 1.0, "S1": -1.0})
        self.assertAlmostEqual(w["L1"], 0.5)
        self.assertAlmostEqual(w["BTCUSDT"], -1.0)                 # residual beta 0.5*1 - 0.5*(-1)

    def test_a5_hysteresis(self):
        def feats(order):
            return {s: {"e1": float(r), "e3": float(r), "qv_ratio": float(r), "vol30": float(r),
                        "beta60": 1.0, "age": 61} for r, s in enumerate(order)}
        names = [f"C{j}" for j in range(20)]
        fn = fp.a5_ensemble({})
        w1 = fn(feats(names), 0)
        self.assertEqual({s for s, x in w1.items() if x > 0}, {f"C{j}" for j in range(5)})
        self.assertEqual({s for s, x in w1.items() if x < 0}, {f"C{j}" for j in range(15, 20)})
        o2 = names[:4] + ["C5", "C4"] + names[6:]                 # C4 falls to 6th: still in the top 30%
        w2 = fn(feats(o2), 1)
        longs = {s for s, x in w2.items() if x > 0}
        self.assertEqual(longs, {"C0", "C1", "C2", "C3", "C4", "C5"})
        self.assertAlmostEqual(w2["C4"], 0.5 / 6)
        o3 = names[:4] + names[5:11] + ["C4"] + names[11:]         # C4 falls to 11th: out
        w3 = fn(feats(o3), 2)
        self.assertNotIn("C4", w3)
        self.assertIn("C5", w3)                                    # held and still in the top 30%
        fresh = fp.a5_ensemble({})(feats(o2), 0)                   # a new build has no memory
        self.assertNotIn("C4", fresh)

    def test_random_control_same_counts(self):
        inner = lambda ctx: (lambda f, i: {"C0": 0.25, "C1": 0.25, "C2": -1 / 6, "C3": -1 / 6, "C4": -1 / 6})
        f = {f"C{j}": {} for j in range(20)}
        a = fp.random_control(inner, 5)({})(f, 0)
        b = fp.random_control(inner, 5)({})(f, 0)
        self.assertEqual(a, b)
        self.assertEqual(sum(1 for x in a.values() if x > 0), 2)
        self.assertEqual(sum(1 for x in a.values() if x < 0), 3)
        self.assertTrue(set(a) <= set(f))

    def test_registries_keep_batch_1_intact(self):
        self.assertEqual(len(fa.STRATEGY_NAMES), 11)
        self.assertEqual(len(fp.ALL_RULES), 7)
        self.assertEqual(len(fp.PERP_RULES), 5)
        self.assertFalse(set(fp.descriptive_daily()) & set(fp.ALL_RULES))


def hourly_closes(n, ret_at):
    c, out = 100.0, [100.0]
    for t in range(1, n):
        c *= 1 + ret_at(t)
        out.append(c)
    return fp.hourly_array([(T0 + t * H, 0, 0, 0, x) for t, x in enumerate(out)], T0, n)


class Hourly(unittest.TestCase):
    def test_hourly_array(self):
        a = fp.hourly_array([(T0 + 2 * H, 0, 0, 0, 5.0), (T0 - H, 0, 0, 0, 9.0)], T0, 4)
        self.assertEqual(a[2], 5.0)
        self.assertTrue(math.isnan(a[0]))

    def test_same_hour_score_excludes_today(self):
        n = 24 * 25
        c = hourly_closes(n, lambda t: 0.5 if t == 22 * 24 + 5 else (0.01 if t % 24 == 5 else 0.0))
        cs, cnt = fp.same_hour_cumsum(c)
        self.assertAlmostEqual(fp.same_hour_score(cs, cnt, 22 * 24 + 5), 0.01)
        self.assertAlmostEqual(fp.same_hour_score(cs, cnt, 20 * 24 + 5), 0.01)
        self.assertIsNone(fp.same_hour_score(cs, cnt, 19 * 24 + 5))
        self.assertAlmostEqual(fp.same_hour_score(cs, cnt, 23 * 24 + 5), (19 * 0.01 + 0.5) / 20)

    def _run(self, placebo):
        n = 24 * 23
        hc = {f"C{j}USDT": hourly_closes(n, (lambda j: lambda t: 0.002 * j if t % 24 == 5 else 0.0)(j))
              for j in range(10)}
        prep = {s: fp.same_hour_cumsum(a) for s, a in hc.items()}
        adv_at = {T0 + d * DAY: {s: 1e7 for s in hc} for d in range(23)}
        return fp.run_hour_of_day(hc, prep, adv_at, fp.Funding({}), T0, n, set(), placebo=placebo)

    def test_gate_book_and_closing_cost(self):
        pnl, turn, st = self._run(False)
        self.assertEqual(st["traded_hour_ts"], [T0 + d * DAY + 5 * H for d in (20, 21, 22)])
        t = 20 * 24 + 5
        self.assertAlmostEqual(pnl[t], 0.1 * 0.002 * 35 - 0.1 * 0.002 * 10)
        self.assertAlmostEqual(turn[t], 1.0)
        self.assertAlmostEqual(turn[t + 1], 1.0)                   # closing charged in the untraded hour
        days = [T0 + d * DAY for d in range(23)]
        out = dict(fp.compound_days(pnl, turn, T0, days))
        self.assertAlmostEqual(out[T0 + 20 * DAY], (1 + 0.005 - 0.002) * (1 - 0.002) - 1)
        self.assertEqual(out[T0 + 5 * DAY], 0.0)

    def test_placebo_scores_hour_plus_12(self):
        pnl, turn, st = self._run(True)
        self.assertEqual(st["traded_hour_ts"], [T0 + d * DAY + 17 * H for d in (20, 21, 22)])
        self.assertAlmostEqual(pnl[20 * 24 + 17], 0.0)

    def test_compound_days(self):
        out = fp.compound_days({0: 0.01, 1: 0.02}, {0: 1.0}, T0, [T0, T0 + DAY], cost_mult=2.0)
        self.assertAlmostEqual(out[0][1], (1 + 0.01 - 0.004) * 1.02 - 1)
        self.assertEqual(out[1], (T0 + DAY, 0.0))


class Pairs(unittest.TestCase):
    def test_ols_df_half_life(self):
        self.assertEqual(fp.ols([0, 1, 2], [1, 3, 5]), (1.0, 2.0))
        g, t = fp.df_stat([1.0, 0.0, 1.0, 0.0])
        self.assertAlmostEqual(g, -1.0)
        self.assertAlmostEqual(t, -2.0)
        self.assertEqual(fp.half_life(-1.0), math.inf)
        self.assertAlmostEqual(fp.half_life(-0.5), 1.0)

    def test_form_pairs_finds_the_cointegrated_pair(self):
        rng = random.Random(7)

        def rw(n):
            x, out = 0.0, []
            for _ in range(n):
                x += rng.gauss(0, 0.02)
                out.append(x)
            return out
        b = rw(1440)
        e, ar = 0.0, []
        for _ in range(1440):
            e = 0.9 * e + rng.gauss(0, 0.01)
            ar.append(e)
        logs = {"BUSDT": b, "AUSDT": [0.5 + 1.2 * x + y for x, y in zip(b, ar)], "ETHUSDT": rw(1440),
                "BTCUSDT": rw(1440)}
        qv30 = {"BTCUSDT": 100e6, "ETHUSDT": 90e6, "BUSDT": 50e6, "AUSDT": 10e6}
        pairs = fp.form_pairs(logs, qv30)
        self.assertEqual((pairs[0]["A"], pairs[0]["B"]), ("ETHUSDT", "BTCUSDT"))
        ab = [p for p in pairs if (p["A"], p["B"]) == ("AUSDT", "BUSDT")]
        self.assertEqual(len(ab), 1)
        self.assertAlmostEqual(ab[0]["b"], 1.2, delta=0.05)
        self.assertLessEqual(ab[0]["t"], -3.90)
        self.assertTrue(4 <= ab[0]["hl"] <= 72)

    def test_select_universe(self):
        qv30 = {"X": 10e6, "Y": 6e6, "Z": 1e6, "ETHUSDT": 50e6, "BTCUSDT": 60e6}
        full = {"X", "Z", "ETHUSDT", "BTCUSDT"}
        self.assertEqual(fp.select_universe(qv30, full), ["X", "ETHUSDT", "BTCUSDT"])

    def test_pair_z(self):
        s = [0, 1, 0, 1, 2, 0]
        ca = fp.hourly_array([(T0 + t * H, 0, 0, 0, math.exp(x)) for t, x in enumerate(s)], T0, 6)
        cb = fp.hourly_array([(T0 + t * H, 0, 0, 0, 1.0) for t in range(6)], T0, 6)
        z = fp.pair_z(ca, cb, 1.0, 2, 6, win=3)
        for k, t in enumerate(range(2, 6)):
            w = s[t - 2:t + 1]
            self.assertAlmostEqual(z[k], (w[-1] - mean(w)) / pstdev(w), places=9)
        ca[1] = NAN
        z = fp.pair_z(ca, cb, 1.0, 2, 6, win=3)
        self.assertEqual(z[:2], [None, None])
        self.assertIsNotNone(z[2])

    def _hc(self, s):
        ca = fp.hourly_array([(T0 + t * H, 0, 0, 0, math.exp(x)) for t, x in enumerate(s)], T0, len(s))
        cb = fp.hourly_array([(T0 + t * H, 0, 0, 0, 1.0) for t in range(len(s))], T0, len(s))
        return {"A": ca, "B": cb}

    S = [0, 0, 0, 0, 0, 1, 1, 1, 0.5, 0.5, 0.5, 0.5]

    def test_schedule_entry_and_zero_cross_exit(self):
        hc = self._hc(self.S)
        months = [(3, 12, [{"A": "A", "B": "B", "b": 1.0}])]
        tr = fp.a7_schedule(hc, months, entry=1.0, stop=1.5, win=3)
        self.assertEqual([(x["et"], x["xt"], x["sign"]) for x in tr], [(5, 8, -1)])

    def test_schedule_max_hold(self):
        hc = self._hc(self.S)
        months = [(3, 12, [{"A": "A", "B": "B", "b": 1.0}])]
        tr = fp.a7_schedule(hc, months, entry=1.0, stop=1.5, win=3, max_hold=2)
        self.assertEqual([(x["et"], x["xt"], x["sign"]) for x in tr], [(5, 7, -1), (8, 10, 1)])

    def test_schedule_vanished_leg(self):
        hc = self._hc(self.S)
        hc["A"][7] = NAN
        months = [(3, 12, [{"A": "A", "B": "B", "b": 1.0}])]
        tr = fp.a7_schedule(hc, months, entry=1.0, stop=1.5, win=3)
        self.assertEqual([(x["et"], x["xt"]) for x in tr], [(5, 6)])

    def test_simulate_trades(self):
        hc = {"A": fp.hourly_array([(T0 + t * H, 0, 0, 0, x) for t, x in enumerate((100, 110, 121))], T0, 3),
              "B": fp.hourly_array([(T0 + t * H, 0, 0, 0, x) for t, x in enumerate((100, 100, 90))], T0, 3)}
        fund = fp.Funding({"A": [(T0 + 2 * H, 0.01)]})
        tr = [{"A": "A", "B": "B", "b": 0.5, "sign": 1, "et": 0, "xt": 2, "month": 0}]
        pnl, turn = fp.simulate_trades(tr, hc, fund, T0, fund.settle_hours(T0, 3))
        self.assertAlmostEqual(pnl[1], 0.1 / 9 - 0.01 / 9)
        self.assertAlmostEqual(pnl[2], 0.11 / 9 + 0.1 / 18)
        self.assertAlmostEqual(turn[0], 1 / 6)
        self.assertAlmostEqual(turn[2], 0.121 / 0.9 + 0.05)

    def test_random_control_keeps_durations(self):
        hc = self._hc([0.0] * 50)
        months = [(0, 25, []), (25, 50, [])]
        tr = [{"A": "A", "B": "B", "b": 1.0, "sign": 1, "et": 3, "xt": 9, "month": 0},
              {"A": "A", "B": "B", "b": 1.0, "sign": -1, "et": 30, "xt": 31, "month": 1}]
        c1 = fp.a7_random_control(tr, months, hc)
        self.assertEqual(c1, fp.a7_random_control(tr, months, hc))
        for a, b in zip(tr, c1):
            self.assertEqual(a["xt"] - a["et"], b["xt"] - b["et"])
            m0, m1, _ = months[b["month"]]
            self.assertTrue(m0 <= b["et"] and b["xt"] <= m1 - 1)

    def test_events_per_week(self):
        self.assertAlmostEqual(fp.events_per_week([T0 + k * DAY for k in range(14)], T0, T0 + 14 * DAY), 7.0)


if __name__ == "__main__":
    unittest.main()
