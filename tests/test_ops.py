"""Tests for the in-app DVOL scheduler, the ops steward and the realtime quote helper (offline)."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core import data, dvol_collect, steward


def at(*a):
    return datetime(*a, tzinfo=timezone.utc)


class DvolSchedule(unittest.TestCase):
    def test_slots_only_on_protocol_mondays_inside_the_window(self):
        self.assertEqual(dvol_collect.due_slot(at(2026, 11, 30, 9, 0, 10)), "2026-11-30 09:00")
        self.assertEqual(dvol_collect.due_slot(at(2026, 11, 30, 9, 5, 44)), "2026-11-30 09:05")
        self.assertIsNone(dvol_collect.due_slot(at(2026, 11, 30, 9, 5, 46)))     # slot lasts 45 s: late is invalid
        self.assertIsNone(dvol_collect.due_slot(at(2026, 11, 30, 9, 2, 0)))
        self.assertIsNone(dvol_collect.due_slot(at(2026, 12, 1, 9, 0, 5)))       # Tuesday
        self.assertIsNone(dvol_collect.due_slot(at(2026, 11, 23, 9, 0, 5)))      # before the window
        self.assertIsNone(dvol_collect.due_slot(at(2027, 3, 1, 9, 0, 5)))        # after the window
        self.assertEqual(dvol_collect.due_slot(at(2027, 2, 22, 9, 0, 1)), "2027-02-22 09:00")


class Steward(unittest.TestCase):
    def test_review_parses_clips_and_logs_without_any_action(self):
        reply = json.dumps({"status": "ok", "concerns": ["c" * 400] * 9, "ready_to_evaluate": ["x"], "note": "n" * 900})
        with tempfile.TemporaryDirectory() as d:
            out = steward.review({"a": 1}, chat=lambda s, u: ("noise " + reply, "m"), log_path=Path(d) / "l.jsonl")
            self.assertEqual(out["status"], "ok")
            self.assertEqual(len(out["concerns"]), 5)
            self.assertEqual(len(out["concerns"][0]), 160)
            self.assertEqual(len(out["note"]), 300)
            self.assertEqual(len((Path(d) / "l.jsonl").read_text().splitlines()), 1)
            bad = steward.review({"a": 1}, chat=lambda s, u: ("", "no provider"), log_path=Path(d) / "l.jsonl")
            self.assertFalse(bad["ok"])
            self.assertEqual(bad["status"], "unparsed")

    def test_prompt_forbids_tuning_locked_protocols(self):
        self.assertIn("Never suggest changing a locked protocol", steward.SYSTEM)


class QuoteFast(unittest.TestCase):
    def test_same_fields_as_quote_from_a_meta_block(self):
        meta = {"regularMarketPrice": 100.0, "previousClose": 90.0, "regularMarketTime": 4_000_000_000,
                "instrumentType": "EQUITY", "currentTradingPeriod": {"regular": {"start": 0, "end": 5_000_000_000}},
                "shortName": "X", "regularMarketVolume": 5}
        with mock.patch("core.data.get_json", return_value={"chart": {"result": [{"meta": meta}], "error": None}}) as g:
            q = data.quote_fast("XYZ", ttl=1.0)
        self.assertEqual(g.call_args[0][1], 1.0)                       # short cache
        self.assertAlmostEqual(q["change_pct"], 11.111, places=2)
        self.assertEqual({"symbol", "price", "bid", "ask", "prev_close", "change_pct", "volume", "ts", "open"} - set(q), set())


if __name__ == "__main__":
    unittest.main()
