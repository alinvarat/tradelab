import gzip
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core import market_collect as mc

mc.MARGIN_ARM = False      # the margin arm has its own tests (tests/test_margin_arm.py); the old ledger tests must not reach for the network


class Parsers(unittest.TestCase):
    def test_venue_payloads(self):
        self.assertEqual(mc.parse_coinbase("BTC-USD", {"bid": "90000.1", "ask": "90000.5", "time": "t"})["ask"], 90000.5)
        k = mc.parse_kraken({"result": {"XXBTZUSD": {"b": ["90001.0", "1", "1"], "a": ["90002.0", "1", "1"]}}})
        self.assertEqual(k, [{"venue": "kraken", "pair": "XXBTZUSD", "bid": 90001.0, "ask": 90002.0}])
        b = mc.parse_binance([{"symbol": "BTCUSDT", "bidPrice": "1.5", "askPrice": "1.6"}])
        self.assertEqual(b[0]["bid"], 1.5)

    def test_deribit_expiry_and_30_day_filter(self):
        exp = mc.deribit_expiry("BTC-29NOV26-90000-C")
        self.assertEqual(exp, datetime(2026, 11, 29, 8, tzinfo=timezone.utc).timestamp())
        self.assertIsNone(mc.deribit_expiry("BTC-PERPETUAL"))
        now = datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp()
        rows = [{"instrument_name": "BTC-29NOV26-90000-C", "bid_price": 0.01},
                {"instrument_name": "BTC-26MAR27-90000-C", "bid_price": 0.1},
                {"instrument_name": "BTC-20NOV26-90000-C", "bid_price": 0.0}]
        self.assertEqual([r["i"] for r in mc.slim_deribit(rows, now)], ["BTC-29NOV26-90000-C"])


class Storage(unittest.TestCase):
    def test_append_is_readable_gzip_lines(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.assertTrue(mc.append("venues", {"a": 1}, 1_800_000_000, base))
            self.assertTrue(mc.append("venues", {"a": 2}, 1_800_000_000, base))
            f = next((base / "venues").glob("*.jsonl.gz"))
            with gzip.open(f, "rt") as fh:
                self.assertEqual([json.loads(x)["a"] for x in fh], [1, 2])

    def test_low_disk_pauses_writing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "MIN_FREE_BYTES", 1e30):
            self.assertFalse(mc.append("venues", {"a": 1}, 1_800_000_000, Path(d)))
            self.assertTrue(mc.STATUS["paused_low_disk"])
            self.assertFalse((Path(d) / "venues").exists())


class ListingLedger(unittest.TestCase):
    def test_notice_enters_after_delay_and_exits_after_four_hours(self):
        t0 = 1_800_000_000
        notice = [{"kind": "listing", "venue": "binance", "symbol": "FOO", "ts": t0 - 30, "title": "Binance Will List Foo (FOO)"}]
        quotes = iter([("kucoin", 9.9, 10.0), ("kucoin", 11.0, 11.1)])
        btc = iter([100.0, 102.0])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "DIR", Path(d)), \
                mock.patch.object(mc, "listing_notices", return_value=notice), \
                mock.patch.object(mc, "quote", side_effect=lambda s: next(quotes)), \
                mock.patch.object(mc, "_btc_mid", side_effect=lambda v: next(btc)):
            st = mc.listings_once(t0)
            self.assertEqual(len(st["pending"]), 1)
            st = mc.listings_once(t0 + 61)
            self.assertEqual(st["pending"][0]["entry_px"], 10.0)
            self.assertAlmostEqual(st["pending"][0]["stake"], 29.4)
            st = mc.listings_once(t0 + 61 + 4 * 3600)
            self.assertEqual(st["pending"], [])
            net = 0.10 - 0.02 - 0.002
            self.assertAlmostEqual(st["closed"][0]["net"], net)
            self.assertAlmostEqual(st["equity"], round(147.0 + 29.4 * net, 4))
            self.assertEqual(mc.listings_view()["n_closed"], 1)

    def test_futures_notice_goes_to_the_short_ledger_only(self):
        t0 = 1_800_000_000
        notice = [{"kind": "futures", "venue": "binance", "symbol": "BAR", "ts": t0 - 30, "title": "t"}]
        quotes = iter([("kucoin", 10.0, 10.1), ("kucoin", 8.9, 9.0)])
        btc = iter([100.0, 100.0])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "DIR", Path(d)), \
                mock.patch.object(mc, "listing_notices", return_value=notice), \
                mock.patch.object(mc, "quote", side_effect=lambda s: next(quotes)), \
                mock.patch.object(mc, "_btc_mid", side_effect=lambda v: next(btc)):
            self.assertEqual(mc.listings_once(t0)["pending"], [])           # not a listing: L1b ignores it
            mc.listings_once(t0 + 61)
            self.assertEqual(mc._l1b_load("l1d")["pending"][0]["entry_px"], 10.0)   # short sells at the bid
            mc.listings_once(t0 + 61 + 7 * 86400)
            closed = mc._l1b_load("l1d")["closed"][0]
            self.assertAlmostEqual(closed["net"], 0.10 - 0.002 - 0.007)       # bought back at the ask 9.0

    def test_delist_short_stops_out_on_a_squeeze(self):
        t0 = 1_800_000_000
        notice = [{"kind": "delist", "venue": "binance", "symbol": "SQZ", "ts": t0 - 30, "title": "t"}]
        quotes = iter([("kucoin", 10.0, 10.1), ("kucoin", 10.5, 10.6), ("kucoin", 12.9, 13.0)])
        btc = iter([100.0, 100.0])
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "DIR", Path(d)), \
                mock.patch.object(mc, "listing_notices", return_value=notice), \
                mock.patch.object(mc, "quote", side_effect=lambda s: next(quotes)), \
                mock.patch.object(mc, "_btc_mid", side_effect=lambda v: next(btc)):
            mc.listings_once(t0)
            mc.listings_once(t0 + 61)                    # short at bid 10.0
            mc.listings_once(t0 + 120)                   # ask 10.6: +6%, below the 25% stop, still open
            self.assertEqual(len(mc._l1b_load("l1f")["pending"]), 1)
            mc.listings_once(t0 + 180)                   # ask 13.0: +30%, stopped
            closed = mc._l1b_load("l1f")["closed"][0]
            self.assertTrue(closed["stopped"])
            self.assertAlmostEqual(closed["net"], -0.30 - 0.002 - 0.001)

    def test_l4f_sells_the_long_shot_side_and_books_resolution(self):
        self.assertEqual(mc.l4f_pick({"bestBid": 0.05, "bestAsk": 0.06, "outcomes": '["Yes","No"]'}), ("yes", 0.05))
        self.assertEqual(mc.l4f_pick({"bestBid": 0.93, "bestAsk": 0.95, "outcomes": '["Yes","No"]'}), ("no", 0.05))
        self.assertIsNone(mc.l4f_pick({"bestBid": 0.40, "bestAsk": 0.42, "outcomes": '["Yes","No"]'}))
        self.assertAlmostEqual(mc.l4f_result("yes", 0.05, yes_won=False), 0.05 / 0.95)
        self.assertEqual(mc.l4f_result("no", 0.05, yes_won=False), -1.0)
        t0 = 1_800_000_000
        listing = {"markets": [{"id": "m1", "question": "q", "endDate": "x", "bestBid": 0.05, "bestAsk": 0.06,
                                "outcomes": '["Yes","No"]', "volumeNum": 1e5}]}
        resolved = {"closed": True, "outcomePrices": '["0", "1"]'}

        def fake_get(url, timeout=8, headers=None):
            return listing if "keyset" in url else resolved
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "DIR", Path(d)), \
                mock.patch.object(mc, "get", side_effect=fake_get):
            st = mc.l4f_once(t0)
            self.assertEqual(st["closed"][0]["net"], 0.05 / 0.95)        # entered and resolved in the same poll here
            self.assertAlmostEqual(st["equity"], 147.0 + 7.35 * 0.05 / 0.95, places=3)
            st = mc.l4f_once(t0 + 1800)
            self.assertEqual(len(st["closed"]), 1)                          # never re-entered
            self.assertEqual(mc.ledger_view("l4f")["n_closed"], 1)

    def test_old_notices_are_not_events(self):
        old = [{"venue": "upbit", "symbol": "BAR", "ts": 1_800_000_000 - 3600, "title": "t"}]
        with tempfile.TemporaryDirectory() as d, mock.patch.object(mc, "DIR", Path(d)), \
                mock.patch.object(mc, "listing_notices", return_value=old):
            self.assertEqual(mc.listings_once(1_800_000_000)["pending"], [])

    def test_kucoin_and_bitget_are_parsed_and_a_blocked_venue_is_isolated(self):
        ms = 1_800_000_000_000
        kucoin = {"data": {"items": [
            {"annType": ["latest-announcements", "new-listings"], "cTime": ms,
             "annTitle": "World Premiere: infiniFi (INFI) Listed on KuCoin"},
            {"annType": ["latest-announcements", "new-listings"], "cTime": ms,
             "annTitle": "KuCoin Futures New Listing: ANTUSDT Pre-IPO Perpetual"},
            {"annType": ["latest-announcements"], "cTime": ms, "annTitle": "KuCoin Will List NOPE (NOPE)"}]}}
        bitget = {"data": [
            {"annSubType": "spot", "cTime": str(ms), "annTitle": "Bitget Announcement on the Listing of Cow Protocol (COW)"},
            {"annSubType": "futures", "cTime": str(ms), "annTitle": "Bitget Announcement on the Listing of AUSDT Stock Perps"}]}
        empty = {"data": {"catalogs": [{"articles": []}]}}

        def fake_get(url, timeout=8, headers=None):
            if "upbit" in url:
                raise OSError("403")
            return kucoin if "kucoin" in url else bitget if "bitget" in url else empty
        with mock.patch.object(mc, "get", side_effect=fake_get):
            ev = mc.listing_notices()
        self.assertEqual({(e["venue"], e["symbol"]) for e in ev}, {("kucoin", "INFI"), ("bitget", "COW")})
        self.assertEqual([e["ts"] for e in ev], [1_800_000_000, 1_800_000_000])
        self.assertEqual(set(mc.STATUS["listings"]["venue_errors"]), {"upbit"})


if __name__ == "__main__":
    unittest.main()
