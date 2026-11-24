import unittest

from core import screens as sc


class ListingParsers(unittest.TestCase):
    def test_binance_spot_listing_only(self):
        self.assertEqual(sc.binance_listing_symbols("Binance Will List Sapien (SAPIEN) with Seed Tag Applied"), ["SAPIEN"])
        self.assertEqual(sc.binance_listing_symbols("Introducing AltLayer (ALT) on Binance Launchpool! Farm ALT"), [])
        self.assertEqual(sc.binance_listing_symbols("Binance Adds ACA, AMP, GHST & More Pairs on Cross Margin"), [])
        self.assertEqual(sc.binance_listing_symbols("Binance Futures Will Launch USDⓈ-M FOO Perpetual"), [])

    def test_upbit_krw_additions(self):
        self.assertEqual(sc.upbit_listing_symbols("KRW, BTC 마켓 디지털 자산 추가 (NEAR, YGG)"), ["NEAR", "YGG"])
        self.assertEqual(sc.upbit_listing_symbols("로켓풀(RPL), 아큐라스트(ACU), 디브릿지(DBR) 원화 마켓 디지털 자산 추가"),
                         ["RPL", "ACU", "DBR"])
        self.assertEqual(sc.upbit_listing_symbols("BTC 마켓 디지털 자산 추가 (FOO)"), [])
        self.assertEqual(sc.upbit_listing_symbols("거래 유의 종목 지정 안내 (FOO)"), [])


class BinanceKinds(unittest.TestCase):
    def test_futures_launch_symbols(self):
        f = sc.binance_futures_symbols
        self.assertEqual(f("Binance Futures Will Launch USDⓈ-Margined BANUSDT and AKTUSDT Perpetual Contracts With up to 75x Leverage"),
                         ["BAN", "AKT"])
        self.assertEqual(f("Binance Futures Will Launch USDⓈ-Margined 1000CATUSDT Perpetual Contract With up to 75x Leverage"), ["CAT"])
        self.assertEqual(f("Binance Futures Will Launch USDⓈ-Margined TSLAUSDT Equity Perpetual Contract (2026-01-28)"), [])
        self.assertEqual(f("Binance Futures Will Launch USDⓈ-Margined KATUSDT Perpetual Contract Pre-Market Trading (2026-03-02)"), [])
        self.assertEqual(f("Binance Futures Will Launch Multiple TradFi USDⓈ-Margined Perpetual Contracts (2026-11-20)"), [])

    def test_add_notice_symbols(self):
        self.assertEqual(sc.binance_add_symbols("Binance Will Add Cow Protocol (COW) and Cetus Protocol (CETUS) on Earn, Buy Crypto, Convert, Margin & Futures"),
                         ["COW", "CETUS"])
        self.assertEqual(sc.binance_add_symbols("Binance Will Add 7 New Pairs"), [])

    def test_trimmed_pick_ignores_one_outlier(self):
        bounds = {"train": (0, 100), "validation": (100, 200)}
        rows = [{"ts": i, "symbol": "S", "ret": {"a": {"net": 0.01}, "b": {"net": 5.0 if i == 0 else -0.01}}} for i in range(10)]
        rows += [{"ts": 100 + i, "symbol": "V", "ret": {"a": {"net": 0.01 * (i % 3 - 1)}, "b": {"net": 0.0}}} for i in range(10)]
        self.assertEqual(sc.judge(rows, ["a", "b"], bounds)["pick"], "b")
        self.assertEqual(sc.judge(rows, ["a", "b"], bounds, pick_trim=5)["pick"], "a")


class DataGate(unittest.TestCase):
    BOUNDS = {"train": (0, 100), "validation": (100, 200), "test": (200, 300)}

    def rows(self, n=12, base=0, sym="S"):
        return [{"ts": base + i, "symbol": f"{sym}{i}", "ret": {"h": {"net": 0.01 * ((i % 3) - 1)}}} for i in range(n)]

    def test_repeated_rows_make_the_verdict_invalid(self):
        good = self.rows() + self.rows(base=100, sym="V")
        self.assertTrue(sc.integrity(good, ["h"], self.BOUNDS)["ok"])
        doubled = good + good                                   # the L4 failure: same markets fetched again
        j = sc.judge(doubled, ["h"], self.BOUNDS)
        self.assertTrue(j["verdict"].startswith("invalid data"))
        self.assertIsNone(j["pick"])

    def test_a_thin_validation_split_is_invalid(self):
        j = sc.judge(self.rows() + self.rows(n=3, base=100, sym="V"), ["h"], self.BOUNDS)
        self.assertTrue(j["verdict"].startswith("invalid data"))

    def test_no_losers_is_flagged(self):
        rows = [{"ts": i, "symbol": f"S{i}", "ret": {"h": {"net": 0.05}}} for i in range(12)]
        w = sc.integrity(rows + self.rows(base=100, sym="V"), ["h"], self.BOUNDS)["warnings"]
        self.assertTrue(any("no losing event" in x for x in w))


class Returns(unittest.TestCase):
    def test_close_at_finds_the_containing_bar(self):
        bars = [(0, 1.0), (60, 2.0), (180, 4.0)]
        self.assertEqual(sc.close_at(bars, 61, 60), 2.0)
        self.assertIsNone(sc.close_at(bars, 125, 60))      # bar 120 missing
        self.assertEqual(sc.close_at(bars, 239, 60), 4.0)

    def test_listing_return_is_abnormal_to_btc_and_net_of_cost(self):
        ts = 1_000_000
        m1 = [(ts + 60 + i * 60, 100.0 if i == 0 else 110.0) for i in range(300)]
        bench = [(ts + 60 + i * 60, 50.0 if i == 0 else 51.0) for i in range(300)]
        r = sc.listing_returns(ts, m1, [], bench, [], cost=0.006)
        self.assertAlmostEqual(r["15m"]["raw"], 0.10)
        self.assertAlmostEqual(r["15m"]["abn"], 0.08)
        self.assertAlmostEqual(r["15m"]["net"], 0.074)
        self.assertNotIn("1d", r)                            # no hourly bars given

    def test_short_side_gains_when_the_coin_falls(self):
        ts = 1_000_000
        m1 = [(ts + 60 + i * 60, 100.0 if i == 0 else 80.0) for i in range(300)]
        bench = [(ts + 60 + i * 60, 50.0) for i in range(300)]
        r = sc.listing_returns(ts, m1, [], bench, [], cost=0.006, side=-1)
        self.assertAlmostEqual(r["15m"]["net"], 0.20 - 0.006)

    def test_delist_symbols(self):
        self.assertEqual(sc.binance_delist_symbols("Binance Will Delist EPIC, QUICK on 2026-10-28"), ["EPIC", "QUICK"])
        self.assertEqual(sc.binance_delist_symbols("Binance Will Delist BAR and FOO on 2025-01-02"), ["BAR", "FOO"])
        self.assertEqual(sc.binance_delist_symbols("Notice of Removal of Spot Trading Pairs - 2026-11-20"), [])
        self.assertEqual(sc.binance_delist_symbols("Binance Futures Will Delist PTBUSDT and MITOUSDT USDⓈ-M Perpetual Contracts"), [])

    def test_alpha_remove_symbols(self):
        f = sc.binance_alpha_remove_symbols
        self.assertEqual(f("Binance Alpha Will Remove PTB, AA, OWL, DORA, ELIZAOS, MEMES, 哭哭马  (2026-10-23)"),
                         ["PTB", "AA", "OWL", "DORA", "ELIZAOS", "MEMES"])
        self.assertEqual(f("Binance Alpha Will Remove SUP, SLX (SLIMEX), CAI (2026-10-20)"), ["SUP", "SLX", "CAI"])
        self.assertEqual(f("Binance Will Delist EPIC, QUICK on 2026-10-28"), [])

    def test_missing_entry_bar_gives_nothing(self):
        self.assertEqual(sc.listing_returns(0, [], [], [], []), {})


class Judge(unittest.TestCase):
    def _rows(self, mean_train, mean_val, n=60):
        rows = []
        for i in range(n):
            for split, base, m in (("train", 0, mean_train), ("validation", 10_000_000, mean_val)):
                x = m + (0.01 if i % 2 else -0.01)
                rows.append({"ts": base + i * 86400, "symbol": f"S{i}", "ret": {"1h": {"net": x}, "1d": {"net": x - 0.02}}})
        return rows

    BOUNDS = {"train": (0, 10_000_000), "validation": (10_000_000, 20_000_000), "test": (20_000_000, 30_000_000)}

    def test_clear_edge_passes_and_picks_best_train_horizon(self):
        j = sc.judge(self._rows(0.03, 0.03), ["1h", "1d"], self.BOUNDS)
        self.assertEqual(j["pick"], "1h")
        self.assertEqual(j["verdict"], "passed")

    def test_negative_validation_is_killed(self):
        self.assertEqual(sc.judge(self._rows(0.03, -0.02), ["1h", "1d"], self.BOUNDS)["verdict"], "killed")

    def test_one_huge_event_cannot_carry_the_result(self):
        rows = self._rows(0.03, -0.012)
        rows.append({"ts": 15_000_000, "symbol": "X", "ret": {"1h": {"net": 5.0}, "1d": {"net": 5.0}}})
        j = sc.judge(rows, ["1h", "1d"], self.BOUNDS)
        self.assertLess(j["robust"]["without_best_1"], 0)
        self.assertEqual(j["verdict"], "killed")


class L1bLedger(unittest.TestCase):
    def test_new_events_are_returned_once(self):
        seen = set()
        ev = [{"venue": "binance", "symbol": "FOO", "ts": 100.4}]
        self.assertEqual(len(sc.new_listing_events(seen, ev)), 1)
        self.assertEqual(sc.new_listing_events(seen, ev), [])

    def test_result_pays_spread_fees_and_removes_btc(self):
        r = sc.l1b_result(entry_ask=10.0, exit_bid=11.0, btc_entry=100.0, btc_exit=102.0)
        self.assertAlmostEqual(r["raw"], 0.10)
        self.assertAlmostEqual(r["net"], 0.10 - 0.02 - 0.002)


class Longshot(unittest.TestCase):
    def test_selling_a_losing_long_shot_earns_its_price_on_locked_collateral(self):
        close = 100 * 86400
        hist = [{"t": close - 7 * 86400, "p": 0.95}, {"t": close - 86400, "p": 0.97}]
        r = sc.longshot_sells(hist, close, yes_won=True)
        self.assertEqual(r["T-7d"]["side"], "no")                      # NO traded at 0.05
        self.assertAlmostEqual(r["T-7d"]["net"], 0.05 / 0.95)
        self.assertAlmostEqual(r["T-7d"]["monthly"], 0.05 / 0.95 * 30 / 7)
        self.assertAlmostEqual(r["T-1d"]["net"], 0.03 / 0.97)              # NO at 0.03 also in range
        self.assertNotIn("T-3d", r)                                    # no point within 2 days before T-3d
        hist2 = [{"t": close - 86400, "p": 0.03}]
        self.assertAlmostEqual(sc.longshot_sells(hist2, close, yes_won=True)["T-1d"]["net"], -1.0)  # YES won: lose 0.97/0.97

    def test_no_price_near_the_lead_gives_nothing(self):
        self.assertEqual(sc.longshot_sells([{"t": 0, "p": 0.05}], 100 * 86400, yes_won=False), {})


class SmallCap(unittest.TestCase):
    def bars(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        out = []
        for k in range(25):                              # 25 sessions, 2026-03-02 onward (Mon-Fri)
            day = datetime(2026, 3, 2, 9, 30, tzinfo=ZoneInfo("America/New_York"))
            import datetime as dt
            d = day + dt.timedelta(days=k + 2 * (k // 5))
            out.append({"t": d.timestamp(), "o": 10.0, "c": 10.0, "v": 300_000})
        return out

    def test_overnight_8k_with_a_gap_gives_continuation_and_reversal(self):
        bars = self.bars()
        bars[22] = {**bars[22], "o": 12.0, "c": 13.2}            # gap +20%, then +10% open->close
        from core.screens import _et
        bench = {_et(b["t"]).date(): (100.0, 101.0) for b in bars}
        filing = {"ts": bars[22]["t"] - 3 * 3600, "items": ["8.01"], "accession": "a1"}   # 06:30 ET
        rows = sc.smallcap_events("SMOL", bars, [filing], bench)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["dir"], r["kind"]), ("up", "8.01"))
        self.assertAlmostEqual(r["ret"]["cont_d0"]["net"], (0.10 - 0.01) - 0.01)
        self.assertAlmostEqual(r["ret"]["rev_d0"]["net"], -(0.10 - 0.01) - 0.01)

    def test_filing_during_the_session_or_large_cap_is_ignored(self):
        bars = self.bars()
        bars[22] = {**bars[22], "o": 12.0, "c": 13.2}
        from core.screens import _et
        bench = {_et(b["t"]).date(): (100.0, 101.0) for b in bars}
        during = {"ts": bars[21]["t"] + 3600, "items": ["8.01"], "accession": "a2"}     # 10:30 ET the day before
        self.assertEqual(sc.smallcap_events("SMOL", bars, [during], bench), [])
        big = [{**b, "c": 50.0, "o": 50.0} for b in bars]
        big[22] = {**big[22], "o": 60.0, "c": 61.0}
        overnight = {"ts": bars[22]["t"] - 3 * 3600, "items": ["8.01"], "accession": "a3"}
        self.assertEqual(sc.smallcap_events("BIG", big, [overnight], bench), [])


class Insider(unittest.TestCase):
    def test_entry_after_availability_and_iwm_adjusted_returns(self):
        bars = SmallCap().bars()
        for k in range(22, 25):
            bars[k] = {**bars[k], "o": 10.0, "c": 11.0}
        from core.screens import _et
        bench = {_et(b["t"]).date(): (100.0, 100.0) for b in bars}
        ev = {"accession": "x", "date": "2026-03-31", "value": 5e4, "ts": bars[21]["t"] + 8 * 3600}  # after day 21 open
        self.assertEqual(sc.insider_rows("SMOL", bars, [ev], bench), [])     # only 3 sessions after entry: no horizon yet
        bars += [{**bars[-1], "t": bars[-1]["t"] + 86400 * k} for k in range(1, 4)]
        bench = {_et(b["t"]).date(): (100.0, 100.0) for b in bars}
        rows = sc.insider_rows("SMOL", bars, [ev], bench)
        self.assertEqual(rows[0]["ts"], bars[22]["t"])                       # the session after availability, never the same one
        self.assertAlmostEqual(rows[0]["ret"]["h5"]["net"], 0.10 - 0.01)


if __name__ == "__main__":
    unittest.main()
