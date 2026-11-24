import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import event_trader_broad as eb


def quote(sym, px=100.0, move=0.0, vol=2e6, open_=True):
    return {"symbol": sym, "price": px, "bid": px * 0.9998, "ask": px * 1.0002, "prev_close": px / (1 + move / 100),
            "change_pct": move, "volume": vol, "ts": time.time(), "open": open_, "name": sym, "currency": "USD"}


class Broad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch("core.event_trader.data.fx_to_usd", return_value=0.03),
                  mock.patch.object(eb.BroadEventTrader, "avg50", return_value=1e6)):
            p.start()
            self.addCleanup(p.stop)
        self.t = eb.BroadEventTrader(Path(self.tmp.name) / "s.json", Path(self.tmp.name) / "l.jsonl", rng_seed=1)

    def test_same_universe_as_the_deepseek_trader(self):
        from core.universe import ALL
        self.assertEqual(self.t.tickers, list(ALL))

    def test_class_thresholds(self):
        now = time.time()
        self.assertTrue(self.t.is_shock(quote("EURUSD=X", move=-1.2), now)[0])      # FX 1%
        self.assertFalse(self.t.is_shock(quote("EURUSD=X", move=0.8), now)[0])
        self.assertTrue(self.t.is_shock(quote("GC=F", move=2.1), now)[0])           # commodity 2%
        self.assertFalse(self.t.is_shock(quote("AAPL", move=5.5, vol=1e5), now)[0])  # stock needs volume

    def test_down_shock_opens_a_leveraged_short_and_a_same_class_short_control(self):
        quotes = {"BTC-USD": quote("BTC-USD", 60000, move=-6.0), "ETH-USD": quote("ETH-USD", 3000, move=-1.0),
                  "AAPL": quote("AAPL", 200, move=0.2)}
        self.t.scan(quotes)
        ev = self.t.events[-1]
        self.assertEqual(ev["entry"]["side"], "short")
        self.assertAlmostEqual(ev["entry"]["notional_usd"], ev["entry"]["margin_usd"] * 3)
        self.assertEqual(ev["control"]["symbol"], "ETH-USD")                       # same class, not AAPL
        self.assertEqual(ev["control"]["side"], "short")
        pos = self.t.acct.positions["BTC-USD"]
        self.assertEqual(pos.side, -1)
        self.assertGreater(pos.sl, quotes["BTC-USD"]["bid"])                        # stop above a short

    def test_up_shock_goes_long(self):
        self.t.scan({"SOL-USD": quote("SOL-USD", 150, move=7.0), "XRP-USD": quote("XRP-USD", 1, move=0.5)})
        self.assertEqual(self.t.events[-1]["entry"]["side"], "long")
        self.assertIn("positions", self.t.view())


if __name__ == "__main__":
    unittest.main()
