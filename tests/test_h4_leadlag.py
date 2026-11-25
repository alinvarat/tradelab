"""Offline tests with synthetic data for the H4 BTC lead-lag screen (core/screens.py H4 section, run.py wrappers)."""
import unittest

from core import screens as sc

B = sc.H4_BAR
T0 = 1_700_000_000 - (1_700_000_000 % B)       # a bar boundary


def flat_btc(n, start=T0, ret_fn=lambda i: 0.0005 * (1 if i % 2 else -1)):
    """n bars of BTC with alternating small returns; returns dict bar -> (open, close)."""
    out, px = {}, 100.0
    for i in range(n):
        c = px * (1 + ret_fn(i))
        out[start + i * B] = (px, c)
        px = c
    return out


def alt_from(btc, beta, qv=50000.0, noise=None):
    """alt whose 5-minute return is exactly beta * BTC's (plus optional per-bar override)."""
    out, px = {}, 50.0
    for t in sorted(btc):
        o, c = btc[t]
        r = beta * (c / o - 1)
        if noise and t in noise:
            r = noise[t]
        out[t] = (px, px * (1 + r), qv)
        px = px * (1 + r)
    return out


class Events(unittest.TestCase):
    def test_threshold_side_and_cooldown(self):
        btc = flat_btc(40)
        btc[T0 + 20 * B] = (100.0, 100.81)         # +0.81% counts
        btc[T0 + 25 * B] = (100.0, 99.0)           # inside the 12-bar cooldown: ignored
        btc[T0 + 33 * B] = (100.0, 99.1)           # -0.9%, after the cooldown
        btc[T0 + 10 * B] = (100.0, 100.79)         # below the threshold
        ev = sc.btc_events(btc, T0, T0 + 100 * B)
        self.assertEqual([(e["bar"], e["side"]) for e in ev], [(T0 + 20 * B, 1), (T0 + 33 * B, -1)])
        self.assertEqual(ev[0]["ts"], T0 + 21 * B)              # entry = open of the next bar
        self.assertEqual(sc.btc_events(btc, T0 + 26 * B, T0 + 30 * B), [])   # window respected

    def test_cooldown_boundary(self):
        btc = flat_btc(40)
        btc[T0 + 5 * B] = (100.0, 101.0)
        btc[T0 + 17 * B] = (100.0, 101.0)          # exactly 12 bars later: allowed
        self.assertEqual(len(sc.btc_events(btc, T0, T0 + 100 * B)), 2)


class Beta(unittest.TestCase):
    def test_beta_two_and_volume(self):
        n = 600
        btc = flat_btc(n)
        alt = alt_from(btc, 2.0, qv=1000.0)
        bar = T0 + 500 * B
        b, qv = sc.trailing_beta(alt, btc, bar, bars=400, min_n=300)
        self.assertAlmostEqual(b, 2.0, places=6)
        self.assertAlmostEqual(qv, 1000.0)

    def test_event_bar_and_future_excluded(self):
        btc = flat_btc(600)
        alt = alt_from(btc, 1.0)
        bar = T0 + 500 * B
        base = sc.trailing_beta(alt, btc, bar, bars=400, min_n=300)
        alt2 = dict(alt)
        for k in range(0, 50):                      # change the event bar and everything after it
            t = bar + k * B
            alt2[t] = (alt[t][0], alt[t][0] * 1.5, 1e9)
        self.assertEqual(base, sc.trailing_beta(alt2, btc, bar, bars=400, min_n=300))

    def test_missing_bars_and_flat_btc(self):
        btc = flat_btc(600)
        alt = alt_from(btc, 1.0)
        bar = T0 + 500 * B
        for k in range(1, 300):
            alt.pop(bar - k * B)
        self.assertIsNone(sc.trailing_beta(alt, btc, bar, bars=400, min_n=300))     # only 101 bars matched
        flat = {t: (100.0, 100.0) for t in btc}
        self.assertIsNone(sc.trailing_beta(alt_from(btc, 1.0), flat, bar, bars=400, min_n=300))

    def test_volume_counts_missing_as_zero(self):
        btc = flat_btc(600)
        alt = alt_from(btc, 1.0, qv=1000.0)
        bar = T0 + 500 * B
        for k in range(1, 201):
            alt.pop(bar - k * B)
        b, qv = sc.trailing_beta(alt, btc, bar, bars=400, min_n=100)
        self.assertAlmostEqual(qv, 500.0)


def setup_event(side=1, alt_move=0.0, beta=2.0, n=600, hold_px=None):
    """BTC moves 0.9% (up or down) at bar 500 of n; returns btc, alt, events."""
    btc = flat_btc(n)
    bar = T0 + 500 * B
    btc[bar] = (100.0, 100.0 * (1 + 0.009 * side))
    alt = alt_from(btc, beta)
    # alt's event bar: the alt barely moves (laggard) or by alt_move
    px = alt[bar][0]
    alt[bar] = (px, px * (1 + alt_move), 50000.0)
    return btc, alt, bar


class Rows(unittest.TestCase):
    def run_rows(self, btc, alt, funding=None):
        ev = sc.btc_events(btc, T0 + 450 * B, T0 + 600 * B)
        if funding is None:                             # one settled rate a few hours before entry: a measured, live perp
            funding = [(T0 + 501 * B - 4 * 3600, 0.0)]
        return ev, sc.leadlag_rows("AAAUSDT", alt, btc, ev, sorted(funding), bars=400, min_n=300)

    def set_exit_bar(self, alt, bar, k, close):
        t = bar + B + (k - 1) * B
        o = alt[t][0]
        alt[t] = (o, close, 50000.0)

    def test_long_after_btc_rise(self):
        btc, alt, bar = setup_event(side=1, alt_move=0.001)
        entry_open = alt[bar + B][0]
        self.set_exit_bar(alt, bar, 3, entry_open * 1.02)
        ev, rows = self.run_rows(btc, alt)
        self.assertEqual(len(ev), 1)
        r = rows[0]
        self.assertEqual(r["ts"], bar + B)
        self.assertTrue(r["lag"])                       # 0.1% < 0.3 * 2 * 0.9% = 0.54%
        self.assertAlmostEqual(r["beta"], 2.0, places=2)
        self.assertAlmostEqual(r["ret"]["m15"]["gross"], 0.02, places=9)
        self.assertAlmostEqual(r["ret"]["m15"]["net"], 0.02 - sc.H4_COST, places=9)

    def test_short_after_btc_fall_uses_short_gain(self):
        btc, alt, bar = setup_event(side=-1, alt_move=-0.001)
        entry_open = alt[bar + B][0]
        self.set_exit_bar(alt, bar, 6, entry_open * 0.97)
        ev, rows = self.run_rows(btc, alt)
        r = rows[0]
        self.assertEqual(r["side"], -1)
        self.assertTrue(r["lag"])
        self.assertAlmostEqual(r["ret"]["m30"]["gross"], 1 - 0.97, places=9)     # 1 - exit/entry, not entry/exit - 1
        self.assertAlmostEqual(sc.short_gain(100.0, 50.0), 0.5)

    def test_lag_flag_boundary(self):
        # BTC +0.9%, beta 2 -> threshold 0.54%; an alt that already moved 0.6% is not lagging
        btc, alt, bar = setup_event(side=1, alt_move=0.006)
        _, rows = self.run_rows(btc, alt)
        self.assertFalse(rows[0]["lag"])
        # an alt that moved against BTC counts as lagging
        btc, alt, bar = setup_event(side=1, alt_move=-0.004)
        _, rows = self.run_rows(btc, alt)
        self.assertTrue(rows[0]["lag"])
        # short side mirrors: alt already fell 0.6% -> not lagging
        btc, alt, bar = setup_event(side=-1, alt_move=-0.006)
        _, rows = self.run_rows(btc, alt)
        self.assertFalse(rows[0]["lag"])

    def test_funding_sign_and_window(self):
        btc, alt, bar = setup_event(side=1)
        entry = bar + B
        fund = [(entry - 1, 0.01), (entry, 0.001), (entry + 3 * B - 1, 0.002), (entry + 3 * B, 0.5)]
        _, rows = self.run_rows(btc, alt, fund)
        f = rows[0]["ret"]["m15"]["funding"]
        self.assertAlmostEqual(f, -(0.001 + 0.002))        # a long pays; [entry, exit) only
        btc, alt, bar = setup_event(side=-1)
        entry = bar + B
        _, rows = self.run_rows(btc, alt, [(entry - 3600, 0.0), (entry, 0.001)])
        self.assertAlmostEqual(rows[0]["ret"]["m15"]["funding"], 0.001)    # a short receives a positive rate

    def test_no_measured_funding_means_no_row(self):
        btc, alt, bar = setup_event(side=1)
        entry = bar + B
        self.assertEqual(self.run_rows(btc, alt, [])[1], [])                          # no funding file at all
        self.assertEqual(self.run_rows(btc, alt, [(entry - 86400 - 1, 0.001)])[1], [])  # older than 24 h
        self.assertEqual(self.run_rows(btc, alt, [(entry, 0.001)])[1], [])             # settles at entry: not before it
        self.assertEqual(len(self.run_rows(btc, alt, [(entry - 86400, 0.001)])[1]), 1)  # exactly 24 h before counts

    def test_not_live_or_illiquid_or_low_beta_skipped(self):
        btc, alt, bar = setup_event(side=1)
        dead = dict(alt)
        del dead[bar + B]                                  # perp has no bar at entry
        self.assertEqual(self.run_rows(btc, dead)[1], [])
        illiquid = alt_from(btc, 2.0, qv=10.0)
        self.assertEqual(self.run_rows(btc, illiquid)[1], [])
        inverse = alt_from(btc, -1.0)
        self.assertEqual(self.run_rows(btc, inverse)[1], [])

    def test_no_lookahead_in_selection(self):
        btc, alt, bar = setup_event(side=1, alt_move=0.001)
        _, a = self.run_rows(btc, alt)
        alt2 = dict(alt)
        for k in range(1, 20):
            t = bar + B + k * B
            alt2[t] = (alt[t][0], alt[t][0] * 3, 1e12)     # wild future after entry
        _, b = self.run_rows(btc, alt2)
        for key in ("beta", "alt_move", "lag", "qv", "ts"):
            self.assertEqual(a[0][key], b[0][key])


def fake_row(sym, ts, beta, lag=True, nets=(0.01, 0.01, 0.01)):
    return {"symbol": sym, "market": "perp", "ts": ts, "kind": "btc_leadlag", "side": 1, "beta": beta, "lag": lag,
            "ret": {h: {"net": n, "gross": n, "funding": 0.0} for h, n in zip(sc.H4_HOLDS, nets)}}


class Selection(unittest.TestCase):
    def test_top_beta_and_disjoint_control(self):
        rows = [fake_row(f"S{i:02d}", 1000, beta=1 + i / 100) for i in range(14)]
        rows.append(fake_row("LATE", 1000, beta=9.0, lag=False))           # not lagging: never picked
        top, ctl, seen, traded = sc.pick_trades(rows)
        self.assertEqual(sorted(r["symbol"] for r in top), ["S09", "S10", "S11", "S12", "S13"])
        self.assertEqual(len(ctl), 5)
        self.assertFalse({r["symbol"] for r in top} & {r["symbol"] for r in ctl})
        self.assertNotIn("LATE", {r["symbol"] for r in top + ctl})
        self.assertEqual((seen, traded), (1, 1))
        self.assertEqual([r["symbol"] for r in ctl], [r["symbol"] for r in sc.pick_trades(rows)[1]])   # reproducible

    def test_needs_2k_candidates(self):
        rows = [fake_row(f"S{i:02d}", 1000, beta=1 + i / 100) for i in range(9)]
        top, ctl, seen, traded = sc.pick_trades(rows)
        self.assertEqual((top, ctl, seen, traded), ([], [], 1, 0))

    def test_paired_rows(self):
        rows = [fake_row(f"S{i:02d}", 1000, beta=1 + i / 100, nets=(0.02, 0.0, 0.0) if i >= 5 else (0.0, 0.0, 0.0))
                for i in range(10)]
        top, ctl, _, _ = sc.pick_trades(rows)
        pr = sc.paired_rows(top, ctl)
        self.assertEqual(len(pr), 1)
        self.assertAlmostEqual(pr[0]["ret"]["m15"]["net"], 0.02)           # top mean 0.02, control mean 0.0
        self.assertAlmostEqual(pr[0]["ret"]["m30"]["net"], 0.0)


class Verdict(unittest.TestCase):
    def judged(self, p, verdict="passed", pick="m15"):
        return {"verdict": verdict, "pick": pick, "table": {pick: {"validation": {"p": p, "mean": 0.01}}}}

    def pair(self, val, test):
        return {"table": {"m15": {"validation": {"mean": val}, "test": {"mean": test}}}}

    def test_pass_and_each_failure(self):
        ok = sc.h4_verdict(self.judged(0.01), {"verdict": "inconclusive"}, self.pair(0.001, 0.0), 5.0)
        self.assertEqual(ok["verdict"], "passed")
        self.assertEqual(sc.h4_verdict(self.judged(0.03), {"verdict": "passed"}, self.pair(0.001, 0.0), 5.0)["verdict"],
                         "inconclusive")                                  # p 0.03 fails Bonferroni 0.0167
        self.assertFalse(sc.h4_verdict(self.judged(0.03), {"verdict": "passed"}, self.pair(0.001, 0.0), 5.0)
                         ["checks"]["bonferroni"])
        self.assertFalse(sc.h4_verdict(self.judged(0.01), {"verdict": "killed"}, self.pair(0.001, 0.0), 5.0)
                         ["checks"]["double_cost_not_killed"])
        self.assertFalse(sc.h4_verdict(self.judged(0.01), {"verdict": "passed"}, self.pair(-0.001, 0.0), 5.0)
                         ["checks"]["paired_validation_positive"])
        self.assertFalse(sc.h4_verdict(self.judged(0.01), {"verdict": "passed"}, self.pair(0.001, -0.001), 5.0)
                         ["checks"]["paired_test_not_negative"])
        self.assertFalse(sc.h4_verdict(self.judged(0.01), {"verdict": "passed"}, self.pair(0.001, 0.0), 2.9)
                         ["checks"]["frequency_3_events_a_week"])
        self.assertEqual(sc.h4_verdict(self.judged(0.5, "killed"), {"verdict": "killed"}, self.pair(0, 0), 9)["verdict"],
                         "killed")

    def test_no_data(self):
        self.assertEqual(sc.h4_verdict({"verdict": "no data", "pick": None}, {}, {}, 0)["verdict"], "no data")

    def test_cost_constants(self):
        self.assertAlmostEqual(sc.H4_COST, 0.003)


class Wrappers(unittest.TestCase):
    def test_study_functions_exist_and_empty_slice(self):
        from research.studies import run
        self.assertIn("h4_btc_leadlag", run.sharded_names())
        self.assertEqual(run.rows_h4_btc_leadlag([]), {"rows": [], "gaps": {"kline_failed": 0, "funding_failed": 0, "no_perp_data": 0}})
        self.assertNotIn("h4_btc_leadlag", run.STUDIES)

    def test_summarize_empty_and_synthetic(self):
        from research.studies import run
        s = run.summarize_h4_btc_leadlag([])
        self.assertEqual(s["trades"], 0)
        self.assertNotEqual(s["verdict"], "passed")
        t = 1_700_000_000.0
        rows = [fake_row(f"S{i:02d}", t + 3600 * e, beta=1 + i / 100) for e in range(3) for i in range(12)]
        s = run.summarize_h4_btc_leadlag(rows)
        self.assertEqual(s["events_traded"], 3)
        self.assertEqual(s["trades"], 15)
        self.assertIn("checks", s)


if __name__ == "__main__":
    unittest.main()
