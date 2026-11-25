import calendar
import math
import random
import unittest
from datetime import date, timedelta

from core import factory_us_pit as fu


def bdays(first, n):
    out, d = [], date.fromisoformat(first)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def panel(days, series, divs=None, splits=None):
    """series: {sym: [(o, h, l, c, v) or None per session]} -> panel."""
    bars = {}
    for s, rows in series.items():
        bars[s] = [{"t": fu.et_ts(d, 9, 30), "o": r[0], "h": r[1], "l": r[2], "c": r[3], "v": r[4]}
                   for d, r in zip(days, rows) if r is not None]
    return fu.build_panel(bars, divs, splits)


def flat(n, p=100.0, v=1e6):
    return [(p, p, p, p, v) for _ in range(n)]


class Time(unittest.TestCase):
    def test_acceptance_read_as_new_york_wall_clock(self):
        self.assertEqual(fu.accept_ts("2024-01-25T16:05:12.000Z"), calendar.timegm((2024, 1, 25, 21, 5, 12)))
        self.assertEqual(fu.accept_ts("2024-07-01T09:00:00.000Z"), calendar.timegm((2024, 7, 1, 13, 0, 0)))
        self.assertEqual(fu.ny_date(fu.et_ts("2024-03-11", 16)), "2024-03-11")

    def test_any_in_is_half_open(self):
        self.assertTrue(fu.any_in([5, 10], 10, 11))
        self.assertFalse(fu.any_in([5, 10], 6, 10))


class Parsing(unittest.TestCase):
    def test_chart_keeps_split_adjusted_bars_and_events(self):
        t = fu.et_ts("2024-05-01", 9, 30)
        res = {"timestamp": [t, t + 86400],
               "indicators": {"quote": [{"open": [10, None], "high": [11, 1], "low": [9, 1], "close": [10.5, 1],
                                         "volume": [100, 1]}]},
               "events": {"dividends": {str(t): {"amount": 0.2, "date": t}},
                          "splits": {str(t + 86400): {"date": t + 86400, "numerator": 2, "denominator": 1}}}}
        bars, divs, splits = fu.parse_chart(res)
        self.assertEqual(len(bars), 1)
        self.assertEqual(divs, {"2024-05-01": 0.2})
        self.assertEqual(splits, {"2024-05-02": 2.0})

    def test_price_as_traded_undoes_later_splits_only(self):
        days = bdays("2024-01-02", 6)
        P = panel(days, {"SPY": flat(6), "A": flat(6, 50.0)}, splits={"A": {days[3]: 2.0, "2024-02-01": 3.0}})
        # a 2:1 split on day 3 and a 3:1 split after the last bar: Yahoo adjusts every earlier bar for both
        self.assertEqual([fu.raw_close(P, "A", i) for i in range(6)], [300.0, 300.0, 300.0, 150.0, 150.0, 150.0])
        self.assertEqual(P["split"]["A"], {3})
        P = panel(days, {"SPY": flat(6), "A": flat(6, 50.0)}, splits={"A": {days[3]}})   # dates only: ratio 1
        self.assertEqual(fu.raw_close(P, "A", 0), 50.0)

    def test_monthly_bars_rejected(self):
        daily = [{"t": k * 86400} for k in range(40)]
        monthly = [{"t": k * 30 * 86400} for k in range(40)]
        self.assertTrue(fu.daily_ok(daily))
        self.assertFalse(fu.daily_ok(monthly))

    def test_submissions_read_older_pages_and_dedupe(self):
        recent = {"form": ["8-K", "4", "8-K/A"], "acceptanceDateTime": ["2025-02-01T16:30:00.000Z"] * 3,
                  "filingDate": ["2025-02-01"] * 3, "items": ["2.02,9.01", "", "2.02"],
                  "accessionNumber": ["a1", "a2", "a3"]}
        page1 = {"form": ["8-K", "8-K", "8-K"], "acceptanceDateTime": ["2018-05-01T07:00:00.000Z",
                                                                       "2025-02-01T16:30:00.000Z",
                                                                       "2015-01-01T07:00:00.000Z"],
                 "filingDate": ["2018-05-01", "2025-02-01", "2015-01-01"], "items": ["8.01", "2.02,9.01", "2.02"],
                 "accessionNumber": ["b1", "a1", "b3"]}
        calls = []

        def get(url):
            calls.append(url)
            if url.endswith("CIK0000000042.json"):
                return {"filings": {"recent": recent, "files": [
                    {"name": "CIK0000000042-submissions-001.json", "filingTo": "2025-01-01"},
                    {"name": "CIK0000000042-submissions-002.json", "filingTo": "2010-01-01"}]}}
            if url.endswith("-001.json"):
                return page1
            raise AssertionError("old page must be skipped")

        f = fu.sec_filings_all(42, get)
        self.assertEqual([x["accession"] for x in f], ["b1", "a1", "a3"])
        self.assertEqual(len(calls), 2)
        sets = fu.filing_sets(f)
        self.assertEqual(len(sets["any"]), 3)
        self.assertEqual(len(sets["t202"]), 2)
        self.assertEqual(len(sets["ev202"]), 1)

    def test_failed_page_raises(self):
        def get(url):
            if url.endswith("-001.json"):
                raise OSError("rate limited")
            return {"filings": {"recent": {}, "files": [{"name": "CIK0000000001-submissions-001.json",
                                                          "filingTo": "2020-01-01"}]}}
        with self.assertRaises(OSError):
            fu.sec_filings_all(1, get)


class Ledger(unittest.TestCase):
    def setUp(self):
        self.days = bdays("2024-01-02", 6)
        self.P = panel(self.days, {
            "SPY": [(100, 100, 100, 100, 1), (100, 101, 99, 101, 1), (102, 102, 102, 102, 1), (102, 103, 101, 103, 1),
                    (103, 103, 103, 103, 1), (103, 103, 103, 103, 1)],
            "A": [(10, 10, 10, 10, 1), (10, 11, 10, 11, 1), (12, 12, 12, 12, 1), None, (9, 9, 9, 9, 1),
                  (9, 9, 9, 9, 1)]}, divs={"A": {self.days[2]: 0.5}, "SPY": {self.days[2]: 1.0}})

    def test_marks(self):
        self.assertEqual(fu.marks(1, "o", 3, "c"), [(1, "o"), (1, "c"), (2, "c"), (3, "c")])
        self.assertEqual(fu.marks(1, "c", 2, "o"), [(1, "c"), (2, "o")])
        self.assertEqual(fu.marks(1, "c", 4, "o"), [(1, "c"), (2, "c"), (3, "c"), (4, "o")])

    def test_long_with_hedge_and_cost(self):
        t = {"sym": "A", "i0": 1, "f0": "o", "i1": 2, "f1": "c", "w": 0.5, "side": 1, "beta": 1.0}
        pnl = fu.book(self.P, [t], cost=0.001)
        # A: 10 -> 11 (day 1) -> 12 (day 2) = +20%; SPY 100 -> 101 -> 102 = +2%
        # cost per side: 0.001 on the stock leg (0.5) and on the hedge leg (0.5 x beta 1) = 0.001
        self.assertAlmostEqual(pnl[1], 0.5 * (0.1 - 0.01) - 0.001)
        self.assertAlmostEqual(pnl[2], 0.5 * (0.1 - 0.01) - 0.001)
        self.assertAlmostEqual(sum(pnl), 0.5 * (0.2 - 0.02) - 0.002)
        self.assertAlmostEqual(fu.trade_return(self.P, t, 0.001), 0.2 - 0.02 - 0.004)
        t["beta"] = 0.5
        self.assertAlmostEqual(fu.trade_return(self.P, t, 0.001), 0.2 - 0.5 * 0.02 - 2 * 1.5 * 0.001)

    def test_short_gain_is_one_minus_exit_over_entry(self):
        t = {"sym": "A", "i0": 1, "f0": "c", "i1": 4, "f1": "c", "w": 1.0, "side": -1, "beta": 0.0}
        r = fu.trade_return(self.P, t, 0.0, borrow_day=0.0)
        self.assertAlmostEqual(r, 1 - 9 / 11)          # day 3 has no bar: carried, then the day-4 close

    def test_short_pays_cost_and_borrow(self):
        t = {"sym": "A", "i0": 1, "f0": "c", "i1": 4, "f1": "c", "w": 1.0, "side": -1, "beta": 0.0}
        r = fu.trade_return(self.P, t, 0.001, borrow_day=0.0001)
        self.assertAlmostEqual(r, (1 - 9 / 11) - 2 * 0.001 - 3 * 0.0001)   # 3 held closes (days 2, 3, 4)
        pnl = fu.book(self.P, [dict(t, w=0.5)], 0.001, borrow_day=0.0001)
        self.assertAlmostEqual(sum(pnl), 0.5 * r)
        self.assertAlmostEqual(pnl[1], -0.0005)                            # entry cost only on the entry day

    def test_dividend_added_to_overnight_exit(self):
        t = {"sym": "A", "i0": 1, "f0": "c", "i1": 2, "f1": "o", "w": 1.0, "side": 1, "beta": 1.0, "div": True}
        # both legs get their own dividend: A 12 + 0.5 over 11, SPY 102 + 1 over 101
        self.assertAlmostEqual(fu.trade_return(self.P, t, 0.0), (12.5 / 11 - 1) - (103 / 101 - 1))
        t["div"] = False
        self.assertAlmostEqual(fu.trade_return(self.P, t, 0.0), (12 / 11 - 1) - (102 / 101 - 1))


class Stats(unittest.TestCase):
    def test_rolling_ols_matches_naive(self):
        rng = random.Random(3)
        x = [None] + [rng.gauss(0, 0.01) for _ in range(99)]
        y = [None] + [0.7 * a + rng.gauss(0, 0.005) for a in x[1:]]
        y[50] = None
        out = fu.rolling_ols(x, y, win=20)
        self.assertIsNone(out[20])                    # window 0..19 contains the None at 0
        self.assertIsNotNone(out[21])
        self.assertIsNone(out[60])                    # window 40..59 contains y[50]
        i = 90
        xs, ys = x[i - 20:i], y[i - 20:i]
        mx, my = sum(xs) / 20, sum(ys) / 20
        sxx = sum((a - mx) ** 2 for a in xs)
        sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        syy = sum((b - my) ** 2 for b in ys)
        beta = sxy / sxx
        ssr = sum((b - my - beta * (a - mx)) ** 2 for a, b in zip(xs, ys))
        b, corr, sd = out[i]
        self.assertAlmostEqual(b, beta, places=9)
        self.assertAlmostEqual(corr, sxy / math.sqrt(sxx * syy), places=9)
        self.assertAlmostEqual(sd, math.sqrt(ssr / 18), places=9)

    def test_coverage_counts_member_days_with_bar_and_cik(self):
        days = bdays("2021-03-01", 10)
        b = flat(10)
        b[4] = None
        P = panel(days, {"SPY": flat(10), "A": flat(10), "B": b})
        cov = fu.coverage(P, [{"A", "B", "X"}] * 10, {"A", "B"})      # X: member without bars or CIK
        self.assertEqual(cov["validation"]["member_days"], 30)
        self.assertAlmostEqual(cov["validation"]["usable_share"], 19 / 30)
        self.assertTrue(cov["validation"]["flag_under_70"])
        self.assertIsNone(cov["train"]["usable_share"])
        self.assertFalse(cov["train"]["flag_under_70"])
        cov = fu.coverage(P, [{"A", "B"}] * 10, {"A", "B"})
        self.assertFalse(cov["validation"]["flag_under_70"])
        m = fu.members_by_session(P, {"A": [("2021-03-02", "2021-03-04"), ("2021-03-10", None)], "B": []})
        self.assertEqual([("A" in x) for x in m], [False, True, True, False, False, False, False, True, True, True])

    def test_vix_gross(self):
        days = bdays("2020-01-02", 260)
        vix = [(20, 20, 20, x, 1) for x in [15.0] * 130 + [25.0] * 129 + [30.0]]
        P = panel(days, {"SPY": flat(260), "^VIX": vix})
        self.assertIsNone(fu.vix_gross(P, 251))
        self.assertEqual(fu.vix_gross(P, 259), 1.0)
        P["c"]["^VIX"][259] = 16.0
        self.assertEqual(fu.vix_gross(P, 259), 0.5)


def b1_world(seed=1, n=320, shock_at=300):
    rng = random.Random(seed)
    days = bdays("2019-01-02", n)
    spy_r = [rng.gauss(0, 0.01) for _ in range(n)]
    xlk_r = [a + rng.gauss(0, 0.004) for a in spy_r]
    xlf_r = [rng.gauss(0, 0.01) for _ in range(n)]

    def path(rs, p=50.0):
        out = []
        for r in rs:
            o = p
            p = p * (1 + r)
            out.append((o, max(o, p) * 1.001, min(o, p) * 0.999, p, 1e6))
        return out
    ser = {"SPY": path(spy_r, 300.0), "XLK": path(xlk_r), "XLF": path(xlf_r)}
    for j in range(8):
        rs = [a + rng.gauss(0, 0.008) for a in xlk_r]
        if j == 0:
            rs[shock_at] = xlk_r[shock_at] - 0.09
        ser[f"S{j}"] = path(rs)
    ser["^VIX"] = [(1, 1, 1, 15.0, 1)] * (n - 1) + [(1, 1, 1, 30.0, 1)]
    ser["^VIX"][shock_at] = (1, 1, 1, 30.0, 1)
    return days, ser


class B1(unittest.TestCase):
    def setUp(self):
        self.days, self.ser = b1_world()
        self.P = panel(self.days, self.ser)
        self.syms = [f"S{j}" for j in range(8)]
        self.members = [set(self.syms)] * self.P["n"]
        self.cik = set(self.syms)

    def run_b1(self, P, any8k=None):
        sc = fu.b1_scores(P, self.syms, etfs=("XLK", "XLF"))
        return sc, fu.b1_trades(P, sc, self.members, self.cik, any8k or {}, rng=random.Random(fu.SEED))

    def test_shocked_name_is_bought_next_open_and_hedged(self):
        sc, (tr, ct) = self.run_b1(self.P)
        hit = [t for t in tr if t["signal_i"] == 300]
        self.assertEqual(hit[0]["sym"], "S0")              # lowest z first
        t = hit[0]
        self.assertEqual((t["i0"], t["f0"], t["i1"], t["f1"]), (301, "o", 302, "c"))
        self.assertEqual(t["w"], min(1.0 / len(hit), 0.10))   # G = 1.0 (high VIX), capped at 10%
        self.assertLess(t["z"], -2.5)
        self.assertGreater(t["beta"], 0.5)            # beta to SPY of an XLK-driven stock
        for c in [c for c in ct if c["signal_i"] == 300]:
            self.assertLess(abs(c["z"]), 0.5)

    def test_8k_in_window_blocks_the_name(self):
        any8k = {"S0": [fu.et_ts(self.days[299], 12)]}
        _, (tr, _) = self.run_b1(self.P, any8k)
        self.assertNotIn("S0", [t["sym"] for t in tr if t["signal_i"] == 300])
        any8k = {"S0": [fu.et_ts(self.days[300], 16, 5)]}      # after the decision close: unknown, no effect
        _, (tr, _) = self.run_b1(self.P, any8k)
        self.assertIn("S0", [t["sym"] for t in tr if t["signal_i"] == 300])

    def test_future_bars_do_not_change_decisions(self):
        _, (tr, _) = self.run_b1(self.P)
        ser = {k: list(v) for k, v in self.ser.items()}
        rng = random.Random(9)
        for s in ser:
            for i in range(301, len(ser[s])):
                o, h, l, c, v = ser[s][i]
                m = 1 + rng.gauss(0, 0.2)
                ser[s][i] = (o * m, h * m * 1.5, l * m * 0.5, c * m, v)
        _, (tr2, _) = self.run_b1(panel(self.days, ser))
        key = lambda ts: [(t["sym"], t["signal_i"], round(t["z"], 9), t["w"]) for t in ts if t["signal_i"] <= 300]
        self.assertEqual(key(tr), key(tr2))


class B2(unittest.TestCase):
    SPEC = {"N1": (0.003, -0.002), "N2": (0.002, -0.003), "N3": (0.001, 0.003), "N4": (0.004, 0.004),
            "N5": (-0.001, -0.004), "N6": (0.0, 0.001)}

    def world(self, divs=None, splits=None):
        n = 40
        days = bdays("2021-03-01", n)
        ser = {"SPY": flat(n, 400.0)}
        for s, (on, idd) in self.SPEC.items():
            rows, c = [], 100.0
            for i in range(n):
                o = c * math.exp(on) if i else c
                c = o * math.exp(idd)
                rows.append((o, max(o, c), min(o, c), c, 1e6))
            ser[s] = rows
        return days, panel(days, ser, divs, splits)

    def picks(self, P, t202=None, k=2, day=30):
        names = list(self.SPEC)
        feats = fu.b2_features(P, names)
        tr, ct = fu.b2_trades(P, feats, [set(names)] * P["n"], set(names), t202 or {}, rng=random.Random(1), k=k)
        return [t["sym"] for t in tr if t["signal_i"] == day], [t for t in ct if t["signal_i"] == day], tr

    def test_highest_overnight_among_weak_intraday(self):
        _, P = self.world()
        got, ctrl, tr = self.picks(P)
        self.assertEqual(got, ["N1", "N2"])
        self.assertEqual(len(ctrl), 2)
        t = tr[0]
        self.assertEqual((t["f0"], t["i1"] - t["i0"], t["f1"], t["w"], t["beta"]), ("c", 1, "o", 0.04, 1.0))

    def test_split_and_202_filters(self):
        days, P = self.world(splits={"N1": {bdays("2021-03-01", 40)[25]}})
        self.assertEqual(self.picks(P)[0], ["N2", "N5"])
        days, P = self.world()
        t202 = {"N2": [fu.et_ts(days[29], 8)]}
        self.assertEqual(self.picks(P, t202)[0], ["N1", "N5"])

    def test_missing_next_bar_does_not_change_picks(self):
        days, P = self.world()
        before = self.picks(P)[0]
        P["o"]["N1"][31] = P["h"]["N1"][31] = P["l"]["N1"][31] = P["c"]["N1"][31] = P["v"]["N1"][31] = None
        got, _, tr = self.picks(P)
        self.assertEqual(got, before)
        t = [x for x in tr if x["signal_i"] == 30 and x["sym"] == "N1"][0]
        spy = P["o"]["SPY"][31] / P["c"]["SPY"][30] - 1
        self.assertAlmostEqual(fu.trade_return(P, t, 0.0), -spy)       # no exit bar: the last price is carried

    def test_price_floor_uses_the_price_as_traded(self):
        days, P0 = self.world()
        want = self.picks(P0)[0]
        for splits, expect in ((None, ["N2", "N5"]), ({"N1": {days[35]: 20.0}}, want)):
            _, P = self.world(splits=splits)
            for i in range(P["n"]):                  # N1 adjusted for a later 20:1 split: about $5, volume x20
                for k in "ohlc":
                    P[k]["N1"][i] *= 0.05
                P["v"]["N1"][i] *= 20
            self.assertEqual(self.picks(P)[0], expect)

    def test_ex_dividend_overnight_left_out(self):
        days, P = self.world(divs={"N1": {bdays("2021-03-01", 40)[25]: 1.0}})
        f = fu.b2_features(P, ["N1"])["N1"]
        self.assertAlmostEqual(f["on"][30] - f["on"][10], 19 * 0.003, places=9)
        self.assertAlmostEqual(f["id"][30] - f["id"][10], 20 * -0.002, places=9)


class B3(unittest.TestCase):
    def setUp(self):
        self.days = bdays("2019-01-02", 400)
        self.P = panel(self.days, {"SPY": flat(400), "A": flat(400, 50.0)})
        self.members = [{"A"}] * 400
        self.f1 = fu.et_ts(self.days[10], 7)
        self.pi = fu.session_on_or_after(self.P, fu.add_days(self.days[10], 364))

    def test_predicted_date_candidate_and_exit(self):
        f2 = fu.et_ts(self.days[self.pi + 1], 16, 30)          # reports after the close of P+1
        c = fu.b3_candidates(self.P, {"A": [self.f1, f2]}, self.members, {"A"})
        i = self.pi - 5
        self.assertEqual(c, [(i, "A", self.pi + 2)])           # exit at the close of the first session opening after it
        c = fu.b3_candidates(self.P, {"A": [self.f1]}, self.members, {"A"})
        self.assertEqual(c, [(i, "A", i + 10)])                # no filing: P+5 sessions

    def test_recent_202_blocks(self):
        recent = fu.et_ts(self.days[self.pi - 20], 7)
        self.assertEqual(fu.b3_candidates(self.P, {"A": [self.f1, recent]}, self.members, {"A"}), [])

    def test_recent_8ka_202_blocks_when_filter_set_given(self):
        recent = fu.et_ts(self.days[self.pi - 20], 7)                   # an 8-K/A with item 2.02: a filter, not an event
        ev = {"A": [self.f1]}
        self.assertEqual(len(fu.b3_candidates(self.P, ev, self.members, {"A"})), 1)
        self.assertEqual(fu.b3_candidates(self.P, ev, self.members, {"A"}, {"A": sorted([self.f1, recent])}), [])

    def test_name_already_held_is_not_bought_again(self):
        P = panel(self.days, {"SPY": flat(400), "A": flat(400), "B": flat(400)})
        tr, _ = fu.b3_trades(P, [(100, "A", 108), (103, "A", 110), (103, "B", 110)], {}, [{"A", "B"}] * 400, cap_n=2)
        self.assertEqual([(t["sym"], t["i0"]) for t in tr], [("A", 100), ("B", 103)])
        tr, _ = fu.b3_trades(P, [(100, "A", 108), (108, "A", 115)], {}, [{"A"}] * 400)
        self.assertEqual([t["i0"] for t in tr], [100, 108])             # exited at 108's close: free again

    def test_capacity_and_ticker_order(self):
        names = [f"N{j:02d}" for j in range(25)]
        P = panel(self.days, {"SPY": flat(400), **{s: flat(400) for s in names}})
        cands = [(100, s, 108) for s in reversed(names)]
        tr, _ = fu.b3_trades(P, sorted(cands), {}, [set(names)] * 400)
        self.assertEqual([t["sym"] for t in tr], names[:20])
        tr, _ = fu.b3_trades(P, sorted(cands + [(108, "N24", 115), (109, "N23", 115)]), {}, [set(names)] * 400)
        self.assertEqual([t["sym"] for t in tr][20:], ["N24", "N23"])   # exits at 108's close free slots for 108

    def test_top_half_filter_uses_completed_windows_only(self):
        P = panel(self.days, {"SPY": flat(400), "A": [(50 * 1.01 ** i,) * 4 + (1e6,) for i in range(400)],
                              "B": [(50 * 0.99 ** i,) * 4 + (1e6,) for i in range(400)]})
        cands = sorted((d, s, d + 5) for d in (10, 30, 50, 70, 90) for s in ("A", "B"))
        tr, _ = fu.b3_trades(P, cands, {}, [{"A", "B"}] * 400, filter_top_half=True)
        self.assertEqual([(t["sym"], t["i0"]) for t in tr], [("A", 90)])

    def test_control_entry_sits_mid_quarter_without_a_release(self):
        ts_list = [fu.et_ts(self.days[10 + 63 * k], 7) for k in range(6)]
        sess = [10 + 63 * k for k in range(6)]
        for seed in range(5):
            j = fu.b3_control_entry(self.P, "A", 250, 5, ts_list, self.members, random.Random(seed))
            self.assertIsNotNone(j)
            last = max(s for s in sess if s <= j)
            self.assertTrue(30 <= j - last <= 60, j)
            self.assertFalse(any(j <= s <= j + 6 for s in sess), j)
            self.assertLessEqual(abs(j - 250), 252)
        self.assertIsNone(fu.b3_control_entry(self.P, "A", 250, 5, [], self.members, random.Random(1)))


class B4(unittest.TestCase):
    def setUp(self):
        self.days = bdays("2022-01-03", 60)
        a = flat(60)
        a[30] = (100, 111, 100, 110, 5e6)
        for i in range(31, 60):
            a[i] = (110, 110, 110, 110, 1e6)
        self.ser = {"SPY": flat(60, 400.0), "A": a, "B": flat(60), "C": flat(60)}
        self.P = panel(self.days, self.ser)
        self.m = [{"A", "B", "C"}] * 60
        self.cik = {"A", "B", "C"}

    def test_event_day_from_acceptance_time(self):
        for when, want in ((fu.et_ts(self.days[30], 7), 1), (fu.et_ts(self.days[29], 16, 30), 1),
                           (fu.et_ts(self.days[30], 10), 0)):
            ev = fu.b4_events(self.P, {"A": [when]}, self.m, self.cik)
            self.assertEqual(len(ev), want, when)
        ev = fu.b4_events(self.P, {"A": [fu.et_ts(self.days[30], 7)]}, self.m, self.cik)
        self.assertEqual(ev[0][:2], (30, "A"))
        self.assertAlmostEqual(ev[0][2], 0.10)

    def test_entry_exit_stop_and_control(self):
        ev = [(30, "A", 0.10)]
        tr, ct = fu.b4_trades(self.P, ev, self.m, self.cik, rng=random.Random(1))
        self.assertEqual((tr[0]["i0"], tr[0]["f0"], tr[0]["i1"]), (31, "o", 35))
        self.assertEqual(len(ct), 1)
        self.assertIn(ct[0]["sym"], ("B", "C"))
        self.P["c"]["A"][33] = 110 * 0.93
        tr, _ = fu.b4_trades(self.P, ev, self.m, self.cik, rng=random.Random(1))
        self.assertEqual(tr[0]["i1"], 33)

    def test_short_stop_and_missing_entry_keeps_slot_in_cash(self):
        days = bdays("2022-01-03", 5)
        P = panel(days, {"SPY": flat(5), "A": [(100,) * 5, (100, 103, 100, 103, 1), (103, 107, 103, 106.5, 1),
                                                (106, 106, 106, 106, 1), (106, 106, 106, 106, 1)]})
        self.assertEqual(fu.stop_exit(P, "A", 1, 4, side=-1), 2)
        self.assertEqual(fu.stop_exit(P, "A", 1, 4, side=1), 4)
        self.P["o"]["A"][31] = None                             # the top event has no bar at entry
        ev = [(30, "A", 0.10), (30, "B", 0.06)]
        tr, _ = fu.b4_trades(self.P, ev, self.m, self.cik, rng=random.Random(1), cap_n=1)
        self.assertEqual(tr, [])                                # B does not take A's slot (decided at D's close)

    def test_name_already_held_is_skipped(self):
        tr, _ = fu.b4_trades(self.P, [(30, "A", 0.10), (32, "A", 0.08), (32, "B", 0.06)], self.m, self.cik,
                             rng=random.Random(1), cap_n=2)
        self.assertEqual([(t["sym"], t["i0"]) for t in tr], [("A", 31), ("B", 33)])   # A held: B takes the slot

    def test_future_bars_do_not_change_entries(self):
        ev = fu.b4_events(self.P, {"A": [fu.et_ts(self.days[30], 7)]}, self.m, self.cik)
        ser = {k: list(v) for k, v in self.ser.items()}
        for i in range(32, 60):
            ser["A"][i] = (50, 200, 10, 60, 9e6)
        ev2 = fu.b4_events(panel(self.days, ser), {"A": [fu.et_ts(self.days[30], 7)]}, self.m, self.cik)
        self.assertEqual(ev, ev2)


class Issuer(unittest.TestCase):
    def test_one_ticker_per_cik(self):
        keep, dropped = fu.one_per_issuer({"GOOG": 1, "GOOGL": 1, "FOX": 2, "FOXA": 2, "AAPL": 3},
                                          {"GOOG": 100, "GOOGL": 100, "FOX": 50, "FOXA": 90, "AAPL": 10})
        self.assertEqual(keep, {"GOOG", "FOXA", "AAPL"})                # most member days, then alphabetical
        self.assertEqual(dropped, {"GOOGL": "GOOG", "FOX": "FOXA"})


class Judge(unittest.TestCase):
    def test_bonferroni_cost_and_frequency_gates(self):
        days = bdays("2017-01-02", 2560)
        ts = [fu.et_ts(d, 16) for d in days]
        rng = random.Random(5)
        good = [(t, 0.002 + rng.gauss(0, 0.005)) for t in ts]
        bad = [(t, -0.001 + rng.gauss(0, 0.005)) for t in ts]
        zero = [(t, 0.0) for t in ts]
        rules = {"good": {"series": good, "series2x": [(t, r - 0.0005) for t, r in good], "control": zero,
                          "entries": ts},
                 "bad": {"series": bad, "series2x": bad, "control": zero, "entries": ts},
                 "rare": {"series": good, "series2x": good, "control": zero, "entries": ts[::10]}}
        out = fu.judge_all(rules)
        self.assertAlmostEqual(out["bonferroni_bar"], 0.05 / 3)
        self.assertEqual(out["passed"], ["good"])
        v = out["rules"]["good"]["validation"]
        self.assertAlmostEqual(v["diff_mean_day"], v["mean_day"])
        self.assertAlmostEqual(v["entries_per_week"], 5.0, places=1)
        out = fu.judge_all(rules, {"validation": {"flag_under_70": True}})
        self.assertEqual(out["passed"], [])
        d = fu.judge_all(rules, primary=False)
        self.assertNotIn("passed", d)

    def test_each_gate_alone_fails_a_rule(self):
        days = bdays("2017-01-02", 2560)
        ts = [fu.et_ts(d, 16) for d in days]
        rng = random.Random(6)
        va, vb = fu.BOUNDS["validation"]
        te = fu.BOUNDS["test"][0]
        good = [(t, 0.002 + rng.gauss(0, 0.005)) for t in ts]
        noise = [(t, rng.gauss(0, 0.01)) for t in ts]
        vmean = sum(r for t, r in noise if va <= t < vb) / sum(1 for t, _ in noise if va <= t < vb)
        weak = [(t, r - vmean + 0.00005 if va <= t < vb else 0.002) for t, r in noise]   # tiny edge: p far above bar
        test_neg = [(t, -0.002 if t >= te else r) for t, r in good]
        zero = [(t, 0.0) for t in ts]
        rules = {"good": {"series": good, "series2x": good, "control": zero, "entries": ts},
                 "dies_at_2x": {"series": good, "series2x": [(t, r - 0.003) for t, r in good], "control": zero,
                                "entries": ts},
                 "test_negative": {"series": test_neg, "series2x": test_neg, "control": zero, "entries": ts},
                 "weak_p": {"series": weak, "series2x": weak, "control": zero, "entries": ts}}
        out = fu.judge_all(rules)
        self.assertAlmostEqual(out["bonferroni_bar"], 0.0125)
        self.assertEqual(out["passed"], ["good"])
        w = out["rules"]["weak_p"]["validation"]
        self.assertGreater(w["mean_day"], 0)
        self.assertGreater(w["p_block"], 0.0125)
        self.assertLess(out["rules"]["dies_at_2x"]["validation"]["p_block"], 0.0125)
        self.assertLess(out["rules"]["test_negative"]["test"]["mean_day"], 0)

    def test_block_p_direction(self):
        rng = random.Random(8)
        self.assertLess(fu.block_p([0.003 + rng.gauss(0, 0.01) for _ in range(800)]), 0.01)
        self.assertGreater(fu.block_p([-0.003 + rng.gauss(0, 0.01) for _ in range(800)]), 0.9)
        self.assertEqual(fu.block_p([0.1] * 10), 1.0)

    def test_month_multiples_ruin(self):
        t0 = calendar.timegm((2020, 1, 2, 21, 0, 0))
        self.assertEqual(fu.month_multiples([(t0, -0.2)], 6), [0.0])
        self.assertAlmostEqual(fu.month_multiples([(t0, 0.1), (t0 + 86400, 0.1)], 2)[0], 1.44)


if __name__ == "__main__":
    unittest.main()
