"""Offline tests for the H1 screen (perp-vs-index snapback): core.screens.basis_snap_rows / basis_snap_summary and the
run.py wiring, all on synthetic bars with known answers."""
import unittest
from unittest import mock

from core import screens as sc
from research.studies import binance_vision as bv

T0 = int(bv.utc(2024, 1, 10))
S = sc.BS_STEP


def at(k):
    return T0 + k * S


def make(price, prem_by_bar, n=140, qv=20000.0, spot=lambda k: 100.0):
    """price(k) -> perp open and close of bar k; prem_by_bar {k: premium}; every bar exists."""
    perp = {at(k): (price(k), price(k), qv) for k in range(n)}
    prem = {at(k): prem_by_bar.get(k, 0.0) for k in range(n)}
    sp = {at(k): spot(k) for k in range(n)}
    return prem, perp, sp


FUND = [(at(-10), 0.0001), (at(25), 0.0003)]        # one settlement before the event, one inside the hold


def long_case():
    price = lambda k: 100.0 if k < 20 else (99.0 if k < 31 else 99.5)
    prem = {20: -0.006, **{k: -0.004 for k in range(21, 30)}, 30: -0.0005}
    return make(price, prem)


class BasisSnapRows(unittest.TestCase):
    def test_long_snaps_back_and_pays_costs_and_funding(self):
        prem, perp, spot = long_case()
        rows, st = sc.basis_snap_rows("XUSDT", 1, prem, perp, spot, FUND)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["ts"], at(21))                   # decision at bar 20's close = entry time
        self.assertEqual((r["entry"], r["exit"], r["hold_bars"], r["by_premium"]), (99.0, 99.5, 10, True))
        gross = 99.5 / 99.0 - 1
        self.assertAlmostEqual(r["ret"]["snap"]["gross"], gross, places=12)
        self.assertAlmostEqual(r["ret"]["snap"]["net"], gross - sc.BS_COST - 0.0003, places=12)   # long pays +0.03%
        self.assertEqual(r["kind"], "long_discount")
        self.assertEqual(st["events"], 1)

    def test_no_snapback_exits_after_four_hours_at_bar_49(self):
        price = lambda k: 100.0 if k < 20 else (99.0 if k < 69 else 98.0)
        prem, perp, spot = make(price, {20: -0.006, **{k: -0.004 for k in range(21, 80)}})
        rows, _ = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)
        r = rows[0]
        self.assertEqual((r["hold_bars"], r["by_premium"], r["exit"]), (48, False, 98.0))    # open of bar 20+49 = 69
        self.assertAlmostEqual(r["ret"]["snap"]["net"], 98.0 / 99.0 - 1 - sc.BS_COST - 0.0003, places=12)
        self.assertEqual(r["ret"]["snap"], r["ret"]["timed"])

    def test_short_mirror_uses_short_gain_and_receives_funding(self):
        price = lambda k: 100.0 if k < 20 else (101.0 if k < 31 else 100.5)
        prem = {20: 0.006, **{k: 0.004 for k in range(21, 30)}, 30: 0.0005}
        prem, perp, spot = make(price, prem)
        rows, _ = sc.basis_snap_rows("X", -1, prem, perp, spot, FUND)
        r = rows[0]
        self.assertEqual((r["kind"], r["entry"], r["exit"]), ("short_premium", 101.0, 100.5))
        self.assertAlmostEqual(r["ret"]["snap"]["gross"], sc.short_gain(101.0, 100.5), places=12)
        self.assertAlmostEqual(r["ret"]["snap"]["net"], sc.short_gain(101.0, 100.5) - sc.BS_COST + 0.0003, places=12)

    def test_timed_control_exits_at_four_hours_even_after_snap(self):
        prem, perp, spot = long_case()
        r = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0][0]
        self.assertAlmostEqual(r["ret"]["timed"]["gross"], 99.5 / 99.0 - 1, places=12)    # bar 69 open is still 99.5
        price = lambda k: 100.0 if k < 20 else (99.0 if k < 31 else (99.5 if k < 60 else 97.0))
        prem, perp, spot = make(price, {20: -0.006, 30: -0.0005, **{k: -0.004 for k in range(21, 30)}})
        r = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0][0]
        self.assertAlmostEqual(r["ret"]["snap"]["gross"], 99.5 / 99.0 - 1, places=12)
        self.assertAlmostEqual(r["ret"]["timed"]["gross"], 97.0 / 99.0 - 1, places=12)   # bar 69 open = 97

    def test_spot_must_not_have_fallen_as_fast(self):
        prem, perp, _ = long_case()
        spot = {at(k): (100.0 if k < 20 else 99.0) for k in range(140)}        # spot fell as much as the perp
        rows, st = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["spot_lag"], 1)
        spot = {at(k): (100.0 if k < 20 else 99.9) for k in range(140)}        # perp fell 0.9 pp more: ok
        self.assertEqual(len(sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0]), 1)
        spot = {at(k): (100.0 if k < 20 else 98.5) for k in range(140)}        # spot fell MORE than the perp
        self.assertEqual(sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0], [])

    def test_thresholds_are_inclusive_and_strict_direction(self):
        prem, perp, spot = long_case()
        prem[at(20)] = -0.0049
        self.assertEqual(sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0], [])
        prem[at(20)] = -0.005
        self.assertEqual(len(sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)[0]), 1)
        self.assertEqual(sc.basis_snap_rows("X", -1, prem, perp, spot, FUND)[0], [])   # a discount is not a short signal

    def test_illiquid_incomplete_and_no_funding_are_dropped_and_counted(self):
        prem, perp, spot = long_case()
        thin = {k: (v[0], v[1], 5000.0) for k, v in perp.items()}               # 12 x 5000 = 60k < 100k
        rows, st = sc.basis_snap_rows("X", 1, prem, thin, spot, FUND)
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["illiquid"], 1)
        gap = dict(perp)
        del gap[at(40)]                                                          # a hole inside the holding window
        rows, st = sc.basis_snap_rows("X", 1, prem, gap, spot, FUND)
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["incomplete"], 1)
        rows, st = sc.basis_snap_rows("X", 1, prem, perp, spot, [(at(25), 0.0003)])   # no settlement before entry
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["no_funding"], 1)
        rows, st = sc.basis_snap_rows("X", 1, prem, perp, spot, [(at(-400), 0.0001)])  # 33 h before: perp not live
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["no_funding"], 1)

    def test_one_trade_at_a_time_then_a_new_event_after_the_exit(self):
        price = lambda k: 100.0 if k < 20 else (99.0 if k < 31 else (99.5 if k < 80 else 98.5))
        prem_by = {20: -0.006, **{k: -0.006 for k in range(21, 30)}, 30: -0.0005, 80: -0.006, 81: -0.0005}
        prem, perp, spot = make(price, prem_by)
        rows, st = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND)
        self.assertEqual([r["ts"] for r in rows], [at(21), at(81)])
        self.assertEqual(st["busy"], 9)             # bars 21..29 are still candidates while the first trade is open
        self.assertEqual(rows[1]["exit"], 98.5)

    def test_blocked_month_drops_events(self):
        prem, perp, spot = long_case()
        rows, st = sc.basis_snap_rows("X", 1, prem, perp, spot, FUND, blocked={(2024, 1)})
        self.assertEqual(rows, [])
        self.assertGreaterEqual(st["blocked"], 1)
        self.assertEqual(len(sc.basis_snap_rows("X", 1, prem, perp, spot, FUND, blocked={(2023, 6)})[0]), 1)

    def test_window_months_cross_month_edges(self):
        t = bv.utc(2024, 2, 1) + 600
        self.assertEqual(sc.basis_window_months(t), {(2024, 1), (2024, 2)})            # 24 h back reaches January
        self.assertEqual(sc.basis_window_months(bv.utc(2024, 2, 10)), {(2024, 2)})
        self.assertEqual(sc.basis_window_months(bv.utc(2024, 2, 29) + 23 * 3600 + 3000), {(2024, 2), (2024, 3)})


def fake_row(kind, ts, net, sym="X", by_premium=True, gross=None):
    return {"ts": ts, "symbol": sym, "market": "perp", "kind": kind, "by_premium": by_premium,
            "ret": {n: {"net": net, "gross": net + sc.BS_COST if gross is None else gross, "funding": 0.0}
                    for n in ("snap", "timed")}}


class Summary(unittest.TestCase):
    bounds = {"train": (bv.utc(2022), bv.utc(2023)), "validation": (bv.utc(2023), bv.utc(2025)),
              "test": (bv.utc(2025), bv.utc(2026, 11))}
    weeks = (bv.utc(2026, 11) - bv.utc(2022)) / (7 * 86400)

    def rows(self, kind, net, per_split=400, jitter=0.0004):
        out = []
        for sp, (a, b) in self.bounds.items():
            for i in range(per_split):
                out.append(fake_row(kind, a + (b - a) * i / per_split, net + jitter * ((i % 7) - 3) / 3, sym=f"S{i % 9}"))
        return out

    def test_edge_passes_every_check(self):
        out = sc.basis_snap_summary(self.rows("long_discount", 0.004), self.bounds, self.weeks)
        long = out["long_discount"]
        self.assertEqual(long["verdict"], "passed")
        self.assertTrue(long["validation_p_below_alpha"] and long["double_cost_validation_positive"])
        self.assertAlmostEqual(long["double_cost"]["table"]["snap"]["validation"]["mean"] + sc.BS_COST,
                               long["base"]["table"]["snap"]["validation"]["mean"], places=4)
        self.assertTrue(out["short_premium"]["verdict"].startswith("invalid") or out["short_premium"]["verdict"] == "no data")

    def test_double_cost_failure_kills_even_when_base_passes(self):
        out = sc.basis_snap_summary(self.rows("short_premium", 0.0015), self.bounds, self.weeks)["short_premium"]
        self.assertTrue(out["base"]["table"]["snap"]["validation"]["mean"] > 0)
        self.assertFalse(out["double_cost_validation_positive"])
        self.assertEqual(out["verdict"], "killed")

    def test_negative_edge_killed_and_too_few_events_killed(self):
        self.assertEqual(sc.basis_snap_summary(self.rows("long_discount", -0.003), self.bounds, self.weeks)["long_discount"]["verdict"], "killed")
        few = self.rows("long_discount", 0.004, per_split=12)                    # 36 rows over ~250 weeks
        out = sc.basis_snap_summary(few, self.bounds, self.weeks)["long_discount"]
        self.assertLess(out["per_week"], 3)
        self.assertEqual(out["verdict"], "killed")

    def test_per_week_by_year_and_concentration(self):
        rows = self.rows("long_discount", 0.004)
        out = sc.basis_snap_summary(rows, self.bounds, self.weeks)["long_discount"]
        self.assertAlmostEqual(out["per_week"], 1200 / self.weeks, places=2)
        self.assertEqual(sorted(out["by_year"]), ["2022", "2023", "2024", "2025", "2026"])
        self.assertEqual(out["symbols"], 9)
        self.assertEqual(out["top5_symbol_share"], round(sum(sorted([sum(1 for r in rows if r["symbol"] == f"S{k}") for k in range(9)])[-5:]) / 1200, 3))
        self.assertEqual(out["share_exit_by_premium"], 1.0)


class Wiring(unittest.TestCase):
    """rows_h1_basis_snapback with the download layer replaced by synthetic zip contents."""

    def setUp(self):
        from research.studies import run
        self.run = run
        prem, perp, spot = long_case()
        month = (2024, 1)
        self.files = {
            ("futures/um", "premiumIndexKlines", month): [(k, 0, 0, 0, v, 0, 0, 0, 0, 0, 0) for k, v in prem.items()],
            ("futures/um", "klines", month): [(k, v[0], v[0], v[0], v[1], 0, 0, v[2], 0, 0, 0) for k, v in perp.items()],
            ("spot", "klines", month): [(k, v, v, v, v, 0, 0, 1, 0, 0, 0) for k, v in spot.items()],
            ("futures/um", "fundingRate", month): list(FUND),
        }

    def fake_fetch(self, market, period, kind, symbol, date, interval=None, parse=None, **kw):
        if symbol == "BADUSDT":
            return None
        if symbol == "NONEUSDT":
            return []
        if symbol == "NOSPOTUSDT" and market == "spot":
            return []
        return self.files.get((market, kind, tuple(date)), [])

    def test_registered_as_a_sharded_study_not_in_studies(self):
        self.assertIn("h1_basis_snapback", self.run.sharded_names())
        self.assertNotIn("h1_basis_snapback", self.run.STUDIES)

    def test_slice_rows_and_gaps(self):
        with mock.patch.object(bv, "fetch", self.fake_fetch):
            out = self.run.rows_h1_basis_snapback(["GOODUSDT", "NOSPOTUSDT", "BADUSDT", "NONEUSDT"])
        rows, gaps = out["rows"], out["gaps"]
        self.assertEqual([r["symbol"] for r in rows], ["GOODUSDT"])
        self.assertEqual(rows[0]["kind"], "long_discount")
        self.assertEqual(gaps["long_discount_events"], 1)
        self.assertEqual(gaps["premium_months_failed"], len(bv.months(bv.utc(2022), bv.utc(2026, 11))))   # BAD: every month
        self.assertEqual(gaps["no_premium_data"], 2)                  # BADUSDT (all months failed) and NONEUSDT (404)
        self.assertGreaterEqual(gaps["spot_months_missing"], 1)
        self.assertEqual(self.run.rows_h1_basis_snapback([]), {"rows": [], "gaps": {}})

    def test_summarize_runs_on_rows(self):
        summ = self.run.summarize_h1_basis_snapback([])
        self.assertEqual(summ["rows"], 0)
        self.assertIn("long_discount", summ)
        self.assertIn("short_premium", summ)

    def test_universe_filter(self):
        with mock.patch.object(bv, "list_symbols", lambda m, q: ["BTCUSDT", "USDCUSDT", "JUPUSDT", "SYRUPUSDT", "ETHUSDT"]):
            self.assertEqual(self.run.symbols_h1_basis_snapback(), ["BTCUSDT", "JUPUSDT", "SYRUPUSDT", "ETHUSDT"])


if __name__ == "__main__":
    unittest.main()
