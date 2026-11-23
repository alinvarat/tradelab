"""Offline tests for the social-buzz monitor (fake sources, no network)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from core import buzz

H = 3600


def ape(rows):
    def fetch(url):
        if "apewisdom" in url:
            page = int(url.rsplit("/", 1)[1])
            return {"pages": 1, "results": rows} if page == 1 else {"pages": 1, "results": []}
        return {"data": {"rows": [{"symbol": s, "name": s + " Inc", "marketCap": str(c), "sector": "x"}
                                  for s, c in UNIVERSE.items()]}}
    return fetch


UNIVERSE = {"YOU": 900e6, "HYP": 400e6, "TINY": 5e6, "SIM1": 300e6, "SIM2": 500e6, "LRG": 90e9}


def row(t, m, m24, rank=1):
    return {"rank": rank, "ticker": t, "name": t, "mentions": m, "mentions_24h_ago": m24, "upvotes": 9, "rank_24h_ago": 50}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.px = {"SPY": 500.0, "HYP": 10.0, "SIM1": 20.0, "SIM2": 30.0, "LRG": 100.0, "TINY": 2.0}
        self.open = True

    def quote(self, s):
        return {"symbol": s, "price": self.px[s], "volume": 5e6, "change_pct": 4.0, "open": self.open}

    def mon(self, rows):
        return buzz.BuzzMonitor(Path(self.tmp.name) / "s.json", Path(self.tmp.name) / "l.jsonl", fetch=ape(rows),
                                quote=self.quote, headlines=lambda s, n: [{"title": "h", "source": "x", "lexicon": 0}], rng_seed=1)

    def kinds(self):
        return [json.loads(l)["kind"] for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines()]


class Detection(unittest.TestCase):
    def test_surge_rule(self):
        m = lambda a, b: {"mentions": a, "mentions_24h": b}
        self.assertTrue(buzz.is_surge(m(60, 10)))
        self.assertFalse(buzz.is_surge(m(19, 0)))          # below the mention floor
        self.assertFalse(buzz.is_surge(m(40, 20)))         # only 2x
        self.assertTrue(buzz.is_surge(m(20, 0)))           # new entry: floor of 5 for the ratio
        self.assertFalse(buzz.is_surge(m(200, 100)))

    def test_liquidity_filter(self):
        self.assertTrue(buzz.liquid({"price": 5, "volume": 1e6, "open": True}))
        self.assertFalse(buzz.liquid({"price": 0.5, "volume": 1e9, "open": True}))
        self.assertFalse(buzz.liquid({"price": 5, "volume": 1e4, "open": True}))
        self.assertFalse(buzz.liquid(None))


class Controls(unittest.TestCase):
    def test_share_classes_of_the_same_company_are_never_controls(self):
        self.assertTrue(buzz.same_company({"name": "Alphabet Inc. Class A Common Stock"}, {"name": "Alphabet Inc. Class C Capital Stock"}))
        self.assertTrue(buzz.same_company({"name": "Berkshire Hathaway Inc. Class B"}, {"name": "Berkshire Hathaway Inc. Class A"}))
        self.assertFalse(buzz.same_company({"name": "NVIDIA Corporation"}, {"name": "Microsoft Corporation"}))
        self.assertFalse(buzz.same_company({"name": ""}, {"name": ""}))


class Monitor(Base):
    def test_word_tickers_are_ignored(self):
        self.px["YOU"] = 10.0
        m = self.mon([row("YOU", 90, 5), row("HYP", 80, 10)])
        m.scan(1_000_000.0)
        self.assertEqual([e["ticker"] for e in m.events], ["HYP"])

    def test_event_only_for_liquid_big_enough_us_stocks_once_per_day(self):
        m = self.mon([row("HYP", 80, 10), row("TINY", 90, 5), row("GHOST", 90, 5), row("LRG", 25, 20)])
        m.scan(1_000_000.0)
        self.assertEqual([e["ticker"] for e in m.events], ["HYP"])      # TINY under cap, GHOST not in universe, LRG not a surge
        ev = m.events[0]
        self.assertEqual(ev["control"]["symbol"] in ("SIM1", "SIM2"), True)
        self.assertEqual(ev["spy_price"], 500.0)
        m.scan(1_000_060.0)
        self.assertEqual(len(m.events), 1)                              # same UTC day: no duplicate
        self.assertIn("event", self.kinds())

    def test_outcomes_use_open_market_prices_relative_to_spy_with_control(self):
        m = self.mon([row("HYP", 80, 10)])
        m.scan(1_000_000.0)
        ctrl = m.events[0]["control"]["symbol"]
        self.px.update({"HYP": 11.0, "SPY": 505.0, ctrl: self.px[ctrl] * 1.02})   # stock +10%, SPY +1%, control +2%
        m.scan(1_000_000.0 + H + 120)
        ev = m.events[0]
        self.assertAlmostEqual(ev["out"][str(H)], 0.10 - 0.01, places=4)
        self.assertAlmostEqual(ev["out_ctrl"][str(H)], 0.02 - 0.01, places=4)

    def test_closed_market_or_late_scan_never_invents_an_outcome(self):
        m = self.mon([row("HYP", 80, 10)])
        m.scan(1_000_000.0)
        self.open = False
        self.px["HYP"] = 12.0
        m.scan(1_000_000.0 + H + 60)
        self.assertEqual(m.events[0]["out"], {})
        self.open = True
        m.scan(1_000_000.0 + H + 7 * H)                                  # far past the 6 h grace window
        self.assertNotIn(str(H), m.events[0]["out"])

    def test_state_round_trip(self):
        m = self.mon([row("HYP", 80, 10)])
        m.scan(1_000_000.0)
        m.save()
        again = buzz.BuzzMonitor(m.state_path, m.log_path, fetch=m.fetch, quote=self.quote)
        self.assertEqual(len(again.events), 1)
        self.assertIn(f"{buzz._day(1_000_000.0)}:HYP", again.seen)


class Evaluation(Base):
    def test_no_conclusion_before_enough_events_then_verdicts(self):
        m = self.mon([])
        m.events = [{"out": {str(24 * H): 0.01}, "out_ctrl": {str(24 * H): 0.0}} for _ in range(50)]
        self.assertIn("too early", m.evaluate()["verdict"])
        rng = __import__("random").Random(2)
        m.events = [{"out": {str(24 * H): 0.03 + rng.gauss(0, .01)}, "out_ctrl": {str(24 * H): rng.gauss(0, .01)}} for _ in range(150)]
        self.assertIn("beat matched controls", m.evaluate()["verdict"])
        m.events = [{"out": {str(24 * H): -0.03 + rng.gauss(0, .01)}, "out_ctrl": {str(24 * H): rng.gauss(0, .01)}} for _ in range(150)]
        self.assertIn("LAG", m.evaluate()["verdict"])
        m.events = [{"out": {str(24 * H): rng.gauss(0, .03)}, "out_ctrl": {str(24 * H): rng.gauss(0, .03)}} for _ in range(150)]
        self.assertIn("no difference", m.evaluate()["verdict"])


if __name__ == "__main__":
    unittest.main()
