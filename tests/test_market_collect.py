import gzip
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core import market_collect as mc


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


if __name__ == "__main__":
    unittest.main()
