import unittest

from core import fwd_crypto as fc

H, D = 3600, 86400
T0 = 1795564800  # 2026-11-25 00:00 UTC


def flat_hours(n, start=T0, px=1.0, qv=1e6):
    return [(start + i * H, px, px, px, px, qv) for i in range(n)]


def btc_flat(bars):
    return {b[0]: (100.0, 100.0) for b in bars}


class Money(unittest.TestCase):
    def test_short_gain_and_hedge(self):
        # price halves: +50%; BTC flat; fees 0.4%
        self.assertAlmostEqual(fc.trade_return(1.0, 0.5, 100, 100, 0.0), 0.5 - 0.004)
        # price doubles: -100%
        self.assertAlmostEqual(fc.trade_return(1.0, 2.0, 100, 100, 0.0), -1.0 - 0.004)
        # BTC fell 10% (BTC short gains 0.1): hedge removes it from the coin short's gain
        self.assertAlmostEqual(fc.trade_return(1.0, 0.9, 100, 90, 0.0), 0.1 - 0.1 - 0.004)

    def test_funding_sign_and_window(self):
        f = [(T0, 0.001), (T0 + 8 * H, -0.002), (T0 + 24 * H, 0.5)]
        # positive rate: short receives; negative: short pays; settlement at exactly the end is excluded
        self.assertAlmostEqual(fc.funding_paid(f, T0, T0 + 24 * H), 0.001 - 0.002)
        self.assertAlmostEqual(fc.trade_return(1.0, 1.0, 100, 100, fc.funding_paid(f, T0, T0 + 24 * H)), -0.001 - 0.004)
        self.assertFalse(fc.perp_live(f, T0))                      # nothing settled in the 24 h before T0
        self.assertTrue(fc.perp_live(f, T0 + 10 * H))
        self.assertFalse(fc.perp_live(f, T0 + 49 * H))             # last settlement more than 24 h before


class Detection(unittest.TestCase):
    def series(self, spike_hour, move=1.10):
        n = 760
        bars = flat_hours(n)
        t = bars[spike_hour][0]
        bars[spike_hour] = (t, 1.0, move, 1.0, move, 1e6)
        for i in range(spike_hour + 1, n):               # price stays at the new level
            bars[i] = (bars[i][0], move, move, move, move, 1e6)
        return bars

    def test_hourly_event_found_once_with_next_open_entry(self):
        bars = self.series(730)
        ev = fc.detect_hourly("AAAUSDT", bars, btc_flat(bars), [(bars[725][0], 0.0001)], bars[730][0])
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["entry_ts"], bars[731][0])
        self.assertEqual(ev[0]["line"], "L12B_F")

    def test_hourly_needs_perp_volume_move_and_not_cooldown(self):
        bars = self.series(730)
        b = btc_flat(bars)
        self.assertEqual(fc.detect_hourly("AAAUSDT", bars, b, [], bars[730][0]), [])              # no perp
        self.assertEqual(fc.detect_hourly("AAAUSDT", bars, b, [(bars[725][0], 0.0)], bars[731][0]), [])  # shock hour before window
        self.assertEqual(fc.detect_hourly("AAAUSDT", bars, b, [(bars[725][0], 0.0)], bars[730][0], last_event_ts=bars[731][0] - 5 * H), [])
        small = self.series(730, move=1.05)                                                         # +5% only
        self.assertEqual(fc.detect_hourly("AAAUSDT", small, btc_flat(small), [(small[725][0], 0.0)], small[730][0]), [])
        thin = [(x[0], x[1], x[2], x[3], x[4], 1e3) for x in bars]                                  # volume below 200k
        self.assertEqual(fc.detect_hourly("AAAUSDT", thin, b, [(bars[725][0], 0.0)], bars[730][0]), [])
        # BTC rose the same 10%: not 6 points beyond BTC
        bb = {x[0]: (100.0, 110.0) if x[0] == bars[730][0] else (100.0, 100.0) for x in bars}
        self.assertEqual(fc.detect_hourly("AAAUSDT", bars, bb, [(bars[725][0], 0.0)], bars[730][0]), [])

    def test_daily_event(self):
        d = [(T0 + i * D, 1.0, 1.0, 1.0, 1.0, 3e6) for i in range(40)]
        d[30] = (d[30][0], 1.0, 1.3, 1.0, 1.25, 3e6)
        d[31] = (d[31][0], 1.25, 1.25, 1.2, 1.2, 3e6)
        btc = {x[0]: (100.0, 100.0) for x in d}
        f = [(d[30][0] + 4 * H, 0.0001)]
        ev = fc.detect_daily("BBBUSDT", d, btc, f, d[30][0])
        self.assertEqual([(e["line"], e["entry_ts"]) for e in ev], [("L8B_F", d[31][0])])
        self.assertEqual(fc.detect_daily("BBBUSDT", d, btc, [], d[30][0]), [])
        self.assertEqual(fc.detect_daily("BBBUSDT", d, btc, f, d[30][0], last_event_ts=d[31][0] - 3 * D), [])
        low = [(x[0], x[1], x[2], x[3], x[4], 1e5) for x in d]                                       # 20-day volume < 2M
        self.assertEqual(fc.detect_daily("BBBUSDT", low, btc, f, d[30][0]), [])


class Control(unittest.TestCase):
    def test_seeded_deterministic_and_excludes_event_coin(self):
        pool = ["AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT"]
        a = fc.control_order("L12B_F", T0, "AAAUSDT", pool)
        self.assertEqual(a, fc.control_order("L12B_F", T0, "AAAUSDT", list(reversed(pool))))
        self.assertNotIn("AAAUSDT", a)
        self.assertEqual(sorted(a), ["BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT"])
        orders = {tuple(fc.control_order("L12B_F", T0 + i * H, "AAAUSDT", pool)) for i in range(20)}
        self.assertGreater(len(orders), 3)


class Ledger(unittest.TestCase):
    def ev(self, sym, t=T0 + H, line="L12B_F"):
        return {"line": line, "symbol": sym, "entry_ts": t, "move": 0.1}

    def test_new_state_clock(self):
        s = fc.new_state(T0 + 12 * H + 300)
        self.assertEqual(s["start_ts"], T0 + 12 * H)
        self.assertEqual(s["h_next"], T0 + 12 * H)           # first shock bar opens at or after the start
        self.assertEqual(s["d_next"], T0 + D)               # first full day after the start: 11-26
        self.assertEqual(fc.new_state(T0)["d_next"], T0)

    def test_open_close_equity_and_cap(self):
        s = fc.new_state(T0 + 5)
        for i in range(6):
            p = fc.open_event(s, self.ev(f"C{i}USDT"), 1.0, 100.0, {"symbol": "XUSDT", "entry_px": 2.0, "btc_entry": 100.0})
        ln = s["lines"]["L12B_F"]
        self.assertEqual(len(ln["open"]), 6)
        self.assertEqual(sum(1 for q in ln["open"] if q["stake"] > 0), 5)
        self.assertEqual(ln["open"][0]["stake"], 14.7)        # 10% of 147
        self.assertEqual(ln["skipped_cap"], 1)
        self.assertIsNone(fc.open_event(s, self.ev("C0USDT"), 1.0, 100.0))   # duplicate
        pos = ln["open"][0]
        self.assertFalse(fc.due(pos, T0 + H + D - 1))
        self.assertTrue(fc.due(pos, T0 + H + D + 61))
        row = fc.close_position(s, pos, 0.9, 100.0, 0.01, T0 + 2 * D, {"exit_px": 2.2, "btc_exit": 100.0, "funding": 0.0})
        self.assertAlmostEqual(row["net"], 0.1 + 0.01 - 0.004)
        self.assertAlmostEqual(row["control_net"], -0.1 - 0.004)
        self.assertAlmostEqual(ln["equity"], 147 + 14.7 * (0.106), places=3)
        shadow = ln["open"][-1]
        self.assertEqual(shadow["stake"], 0.0)
        before = ln["equity"]
        fc.close_position(s, shadow, 0.5, 100.0, 0.0, T0 + 2 * D)
        self.assertEqual(ln["equity"], before)                # a shadow trade never moves the ledger
        self.assertEqual(len(ln["closed"]), 2)
        # a new event can now be taken: the slot freed by the first close
        fc.open_event(s, self.ev("NEWUSDT", T0 + 3 * H), 1.0, 100.0)
        self.assertGreater(ln["open"][-1]["stake"], 0)
        self.assertEqual(ln["last_event"]["NEWUSDT"], T0 + 3 * H)

    def test_exit_bar(self):
        self.assertEqual(fc.exit_bar_ts("L12B_F", T0), T0 + 23 * H)
        self.assertEqual(fc.exit_bar_ts("L8B_F", T0), T0)


class EvidenceAndParsers(unittest.TestCase):
    def closed(self, nets, ctrl):
        return [{"ts": T0 + i * D, "net": n, "control_net": c} for i, (n, c) in enumerate(zip(nets, ctrl))]

    def test_verdicts(self):
        self.assertEqual(fc.evidence([])["verdict"], "continue")
        loss = fc.evidence(self.closed([-0.5, -0.4] * 60, [0.0] * 120))
        self.assertEqual(loss["verdict"], "no edge")
        win = fc.evidence(self.closed([0.5, 0.4] * 60, [0.0, -0.01] * 60))
        self.assertTrue(win["verdict"].startswith("edge"))
        # model wins but the control wins just as much: no edge over the control, so no early "edge"
        same = fc.evidence(self.closed([0.5, 0.4] * 60, [0.5, 0.4] * 60))
        self.assertFalse(same["verdict"].startswith("edge"))
        flat = fc.evidence(self.closed([0.001, -0.001] * 3, [0.0] * 6), max_events=6)
        self.assertEqual(flat["verdict"], "inconclusive at max")
        self.assertIsNotNone(flat["fixed_at_max"])

    def test_stop_and_truncation(self):
        s = fc.new_state(T0)
        s["lines"]["L12B_F"]["closed"] = self.closed([-0.5, -0.4] * 60, [0.0] * 120)
        self.assertEqual(fc.evidence(s["lines"]["L12B_F"]["closed"])["verdict"], "no edge")
        self.assertFalse(fc.line_active(s, "L12B_F"))
        self.assertTrue(fc.line_active(s, "L8B_F"))
        # past the maximum only the first max_events rows count: later rows cannot flip the read
        rows = self.closed([0.001, -0.001] * 3, [0.0] * 6)
        a = fc.evidence(rows, max_events=6)
        b = fc.evidence(rows + self.closed([0.9] * 20, [0.0] * 20), max_events=6)
        self.assertEqual((a["verdict"], a["fixed_at_max"]), (b["verdict"], b["fixed_at_max"]))
        self.assertEqual(b["n_closed"], 6)

    def test_summary_fields(self):
        s = fc.new_state(T0)
        ln = s["lines"]["L12B_F"]
        for i in range(2):
            fc.open_event(s, {"line": "L12B_F", "symbol": f"S{i}USDT", "entry_ts": T0 + H + i * H}, 1.0, 100.0)
        fc.close_position(s, ln["open"][0], 0.9, 100.0, 0.01, T0 + 2 * D)
        fc.close_position(s, ln["open"][0], 1.5, 100.0, -0.02, T0 + 3 * D, liquidated=False)
        out = fc.line_summary(s, "L12B_F")
        self.assertEqual(out["closed"], 2)
        self.assertGreater(out["worst_drawdown"], 0)
        self.assertAlmostEqual(out["mean_funding"], -0.005)
        self.assertLess(out["equity_double_cost_usd"], out["equity_usd"])
        self.assertEqual(out["liquidated"], 0)

    def test_loss_is_bounded_and_liquidation(self):
        px, liq = fc.exit_price(1.0, [(0, 1, 1.5, 1, 1.4, 1), (1, 1.4, 2.1, 1.4, 1.2, 1)], 1.2)
        self.assertEqual((px, liq), (2.0, True))
        self.assertEqual(fc.exit_price(1.0, [(0, 1, 1.5, 1, 1.4, 1)], 1.4), (1.4, False))
        s = fc.new_state(T0 + 5)
        fc.open_event(s, {"line": "L12B_F", "symbol": "XUSDT", "entry_ts": T0 + H, "move": 0.1}, 1.0, 100.0)
        row = fc.close_position(s, s["lines"]["L12B_F"]["open"][0], 4.7, 100.0, 0.0, T0 + 2 * D)   # price x4.7: -370%
        self.assertEqual(row["net"], -1.0)
        self.assertAlmostEqual(s["lines"]["L12B_F"]["equity"], 147 - 14.7)

    def test_parsers(self):
        k = [[T0 * 1000, "1", "2", "0.5", "1.5", "10", (T0 + H) * 1000 - 1, "15"], [(T0 + H) * 1000, "1", "1", "1", "1", "1", (T0 + 2 * H) * 1000 - 1, "1"]]
        self.assertEqual(fc.parse_klines(k)[0], (T0, 1.0, 2.0, 0.5, 1.5, 15.0))
        self.assertEqual(len(fc.parse_klines(k, now=T0 + H + 10, closed_only=True)), 1)
        o = {"data": [{"fundingTime": str((T0 + 8 * H) * 1000), "fundingRate": "0.0002", "realizedRate": ""},
                      {"fundingTime": str(T0 * 1000), "fundingRate": "0.5", "realizedRate": "0.0001"}]}
        self.assertEqual(fc.parse_okx_funding(o), [(T0, 0.0001), (T0 + 8 * H, 0.0002)])
        self.assertEqual(fc.parse_okx_live_swaps({"data": [{"instId": "A-USDT-SWAP", "state": "live"},
                                                           {"instId": "B-USDT-SWAP", "state": "suspend"},
                                                           {"instId": "C-USD-SWAP", "state": "live"}]}), {"A-USDT-SWAP"})

    def test_symbols(self):
        self.assertTrue(fc.eligible_symbol("SOLUSDT"))
        for bad in ("USDCUSDT", "BTCUPUSDT", "SOLBTC", "WBTCUSDT"):
            self.assertFalse(fc.eligible_symbol(bad))
        self.assertEqual(fc.okx_inst("SOLUSDT"), "SOL-USDT-SWAP")


if __name__ == "__main__":
    unittest.main()
