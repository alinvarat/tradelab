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

    def test_a_slot_is_taken_only_when_the_snapshot_has_books_and_no_errors(self):
        old = list(dvol_collect.STATUS["taken"])
        try:
            dvol_collect.STATUS["taken"].clear()
            self.assertFalse(dvol_collect.mark_taken("x", {"books": 0, "errors": 0}))
            self.assertFalse(dvol_collect.mark_taken("x", {"books": 20, "errors": 1}))
            self.assertFalse(dvol_collect.mark_taken("x", None))
            self.assertIn("incomplete", dvol_collect.STATUS["last_error"])
            self.assertTrue(dvol_collect.mark_taken("x", {"books": 20, "errors": 0}))
            self.assertEqual(dvol_collect.STATUS["taken"], ["x"])
        finally:
            dvol_collect.STATUS["taken"][:] = old


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


class SingleModel(unittest.TestCase):
    def test_every_component_uses_flash_1017_and_a_swap_is_flagged(self):
        import io
        import os
        from core import ai_news
        self.assertEqual(ai_news.DECISION_MODEL, "openrouter/deepseek/deepseek-v4.1-flash-1017")
        self.assertEqual(ai_news.OPENCODE_MODEL, ai_news.DECISION_MODEL)

        class R(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        fake = lambda served: (lambda req, timeout: R(json.dumps(
            {"model": served, "choices": [{"message": {"content": "x"}}]}).encode()))
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "k"}), mock.patch("core.ai_news.opencode_available", return_value=False):
            _, same = ai_news.chat("s", "u", urlopen=fake("deepseek/deepseek-v4.1-flash-1017"), model=ai_news.DECISION_MODEL)
            _, other = ai_news.chat("s", "u", urlopen=fake("vendor/other"), model=ai_news.DECISION_MODEL)
        self.assertEqual(same, "deepseek/deepseek-v4.1-flash-1017")
        self.assertIn("SERVED: vendor/other", other)


class ThbAtOpen(unittest.TestCase):
    def test_thb_profit_equals_usd_return_so_fx_moves_do_not_fake_a_loss(self):
        self.assertAlmostEqual(data.thb_at_open(147.0, 147.0), 5000.0)
        self.assertAlmostEqual(data.thb_at_open(148.47, 147.0), 5050.0, places=1)       # +1% in USD is +50 THB
        self.assertAlmostEqual(data.thb_at_open(147.5, 147.5) - 5000.0, 0.0)             # opened at a different USD amount
        self.assertEqual(data.thb_at_open(10.0, 0.0), 0.0)


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


class Spend(unittest.TestCase):
    def test_usage_cost_is_counted_and_estimated_when_missing(self):
        from core import ai_news
        before = ai_news.spend()
        c1 = ai_news.record_usage({"usage": {"prompt_tokens": 1000, "completion_tokens": 100, "cost": 0.0012,
                                             "prompt_tokens_details": {"cached_tokens": 800}}})
        c2 = ai_news.record_usage({"usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}})
        after = ai_news.spend()
        self.assertAlmostEqual(c1, 0.0012)
        self.assertAlmostEqual(c2, ai_news.PRICE_IN)
        self.assertAlmostEqual(after["total_usd"] - before["total_usd"], 0.0012 + ai_news.PRICE_IN)
        self.assertEqual(after["tokens_cached"] - before["tokens_cached"], 800)
        self.assertEqual(ai_news.record_usage({}), 0.0)



class CacheLayout(unittest.TestCase):
    def test_role_goes_last_and_system_is_shared(self):
        from core import ai_news
        a = ai_news.cache_messages("ROLE A", "DATA")
        b = ai_news.cache_messages("ROLE B", "DATA")
        self.assertEqual(a[0], b[0])
        self.assertTrue(a[1]["content"].startswith("DATA"))
        self.assertTrue(a[1]["content"].endswith("ROLE A"))


class ExtendedHours(unittest.TestCase):
    def chart(self, now, pre=True, age=60, price=105.0):
        win = {"start": now - 3600, "end": now + 3600}
        far = {"start": now - 90000, "end": now - 80000}
        return {"meta": {"currentTradingPeriod": {"pre": win if pre else far, "post": far if pre else win,
                                                  "regular": far},
                         "regularMarketPrice": 102.0, "previousClose": 100.0, "currency": "USD"},
                "timestamp": [now - 600, now - age], "indicators": {"quote": [{"close": [104.0, price]}]}}

    def test_pre_market_quote_uses_previous_close_and_wide_spread(self):
        from core import data
        now = 1_800_000_000
        q = data.ext_quote_from_chart("AAA", self.chart(now), now)
        self.assertEqual(q["session"], "pre")
        self.assertTrue(q["open"])
        self.assertAlmostEqual(q["change_pct"], 5.0)
        self.assertAlmostEqual(q["ask"] - q["bid"], 105.0 * data.EXT_SPREAD)

    def test_after_hours_change_is_vs_regular_close_and_stale_prints_are_ignored(self):
        from core import data
        now = 1_800_000_000
        q = data.ext_quote_from_chart("AAA", self.chart(now, pre=False, price=102.0 * 1.02), now)
        self.assertEqual(q["session"], "post")
        self.assertAlmostEqual(q["change_pct"], 2.0)
        self.assertIsNone(data.ext_quote_from_chart("AAA", self.chart(now, age=3600), now))
