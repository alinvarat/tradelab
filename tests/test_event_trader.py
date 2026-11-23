"""Offline tests for the event trader (synthetic quotes, no network)."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import event_trader as et


def quote(sym, px=100.0, move=0.0, vol=2e6, ts=None, open_=True):
    return {"symbol": sym, "price": px, "bid": px * 0.9998, "ask": px * 1.0002, "prev_close": px / (1 + move / 100),
            "change_pct": move, "volume": vol, "ts": ts or time.time(), "open": open_, "name": sym + " Inc", "currency": "USD"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [mock.patch("core.event_trader.data.fx_to_usd", return_value=0.03),
                   mock.patch("core.event_trader.news.symbol_news", return_value={"items": [
                       {"title": "Big news", "source": "X", "sentiment": 0.3}]}),
                   mock.patch.object(et.EventTrader, "avg50", return_value=1e6)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.t = et.EventTrader(Path(self.tmp.name) / "s.json", Path(self.tmp.name) / "l.jsonl", rng_seed=1)

    def market(self, **over):
        q = {s: quote(s) for s in ("AAA", "BBB", "CCC", "DDD")}
        q.update(over)
        return q


class Detection(Base):
    def test_threshold_volume_staleness_and_market_state(self):
        now = time.time()
        self.assertTrue(self.t.is_shock(quote("A", move=5.0), now)[0])
        self.assertFalse(self.t.is_shock(quote("A", move=4.9), now)[0])
        self.assertFalse(self.t.is_shock(quote("A", move=9, vol=1e5), now)[0])           # volume too low
        self.assertFalse(self.t.is_shock(quote("A", move=9, ts=now - 4000), now)[0])     # stale
        self.assertFalse(self.t.is_shock(quote("A", move=9, open_=False), now)[0])       # market closed

    def test_up_shock_opens_rule_and_control_positions(self):
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        ev = self.t.events[0]
        self.assertEqual(ev["direction"], "up")
        self.assertIsNotNone(ev["entry"])
        self.assertIn("AAA", self.t.acct.positions)
        self.assertEqual(len(self.t.ctrl.positions), 1)
        self.assertNotIn("AAA", self.t.ctrl.positions)
        self.assertEqual(ev["headlines"][0]["title"], "Big news")
        self.assertAlmostEqual(self.t.acct.positions["AAA"].qty * 100 / self.t.capital_usd, et.SIZE, delta=0.01)

    def test_down_shock_is_data_only(self):
        self.t.scan(self.market(AAA=quote("AAA", move=-12)))
        self.assertEqual(self.t.events[0]["direction"], "down")
        self.assertFalse(self.t.acct.positions)

    def test_one_event_per_stock_per_day(self):
        m = self.market(AAA=quote("AAA", move=12))
        self.t.scan(m)
        self.t.scan(m)
        self.assertEqual(len(self.t.events), 1)


class Risk(Base):
    def test_max_positions_pause_and_daily_halt(self):
        shocked = {s: quote(s, move=10) for s in ("AAA", "BBB", "CCC", "DDD")}
        others = {s: quote(s) for s in ("EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK")}
        self.t.scan({**shocked, **others})
        self.assertLessEqual(len(self.t.acct.positions), et.MAX_POS)
        self.assertTrue(any(e.get("skipped") == "max positions" for e in self.t.events))
        t2 = et.EventTrader(Path(self.tmp.name) / "s2.json", Path(self.tmp.name) / "l2.jsonl", rng_seed=1)
        t2.paused = True
        t2.scan({"AAA": quote("AAA", move=10), "BBB": quote("BBB")})
        self.assertEqual(t2.events[0]["skipped"], "paused")
        t3 = et.EventTrader(Path(self.tmp.name) / "s3.json", Path(self.tmp.name) / "l3.jsonl", rng_seed=1)
        t3.day_start = {"day": et._day(), "equity": t3.acct.equity() * 2}  # simulate a >3% loss today
        t3.scan({"AAA": quote("AAA", move=10), "BBB": quote("BBB")})
        self.assertEqual(t3.events[0]["skipped"], "daily loss halt")


class Lifecycle(Base):
    def test_time_exit_books_a_pair_and_outcomes_are_recorded(self):
        t = self.t
        t.scan(self.market(AAA=quote("AAA", px=110, move=10)))
        for acct in (t.acct, t.ctrl):
            for p in acct.positions.values():
                p.opened_ts -= et.HOLD_S + 10
        t.events[0]["ts"] -= et.HOLD_S + 10
        later = self.market(AAA=quote("AAA", px=115, move=15), BBB=quote("BBB", px=101), CCC=quote("CCC", px=99),
                            DDD=quote("DDD", px=100))
        t.seen.add(f"{et._day()}:AAA")
        t.scan(later)
        self.assertFalse(t.acct.positions)
        self.assertEqual(len(t.pairs), 1)
        self.assertGreater(t.pairs[0]["s1"], 0)

    def test_outcome_recorded_only_near_its_horizon(self):
        t = self.t
        t.scan(self.market(AAA=quote("AAA", px=110, move=10)))
        t.events[0]["ts"] -= 3660                       # 1 hour and a minute later
        t.seen.add(f"{et._day()}:AAA")
        t.scan(self.market(AAA=quote("AAA", px=121, move=21)))
        self.assertAlmostEqual(t.events[0]["out"]["3600"], 0.10, places=4)
        self.assertNotIn("14400", t.events[0]["out"])
        t.events[0]["ts"] -= 30000                      # long after +1h/+4h: a late scan must not invent values
        t.events[0]["out"] = {}
        t.scan(self.market(AAA=quote("AAA", px=130, move=30)))
        self.assertNotIn("3600", t.events[0]["out"])

    def test_state_round_trips_and_audit_log_is_append_only(self):
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.t.save()
        again = et.EventTrader(self.t.state_path, self.t.log_path)
        self.assertEqual(len(again.events), 1)
        self.assertIn("AAA", again.acct.positions)
        lines = self.t.log_path.read_text().splitlines()
        self.assertTrue(any('"kind": "event"' in l for l in lines))


class Context(Base):
    def test_events_record_market_context_and_spy_relative_outcome(self):
        self.t.context = {"SPY": quote("SPY", px=500, move=3.0), "^VIX": quote("^VIX", px=22.0)}
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=10)))
        ev = self.t.events[0]
        self.assertEqual(ev["spy_move_pct"], 3.0)
        self.assertEqual(ev["abnormal_move_pct"], 7.0)
        self.assertEqual(ev["vix"], 22.0)
        ev["ts"] -= 3660
        self.t.context["SPY"] = quote("SPY", px=505, move=4.0)       # SPY +1% since the event
        self.t.seen.add(f"{et._day()}:AAA")
        self.t.scan(self.market(AAA=quote("AAA", px=121, move=21)))  # stock +10%
        self.assertAlmostEqual(ev["out_vs_spy"]["3600"], 0.10 - 0.01, places=4)


class Evaluation(Base):
    def test_no_conclusion_before_thirty_pairs(self):
        self.t.pairs = [{"id": str(i), "s1": 0.05, "ctrl": 0.0} for i in range(29)]
        self.assertIn("too early", self.t.evaluate()["verdict"])

    def test_edge_and_no_edge_verdicts(self):
        self.t.pairs = [{"id": str(i), "s1": 0.04 + (i % 3) * 0.001, "ctrl": 0.0 - (i % 2) * 0.001} for i in range(40)]
        self.assertIn("edge candidate", self.t.evaluate()["verdict"])
        self.t.pairs = [{"id": str(i), "s1": -0.01, "ctrl": 0.01 + (i % 3) * 0.001} for i in range(40)]
        self.assertEqual(self.t.evaluate()["verdict"], "no edge shown")


if __name__ == "__main__":
    unittest.main()
