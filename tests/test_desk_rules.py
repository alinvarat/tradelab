"""Offline tests for the v4.19 frozen rules, risk state, input blocks and fast-news feeds (pure; no network, no model)."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import desk_feeds as df
from core import desk_rules as dr

NOW = 1_800_000_000.0


def dec(**kw):
    d = {"symbol": "AAA", "action": "short", "size_pct": 10.0, "leverage": 2.0, "review_in_min": 60, "expected_move_pct": None}
    d.update(kw)
    return d


def gate(d=None, rs=None, eq=147.0, **kw):
    rs = rs or dr.new_risk_state(eq, NOW)
    args = dict(news_type="other", forced=False, rs=rs, eq=eq, now=NOW, n_open=0)
    args.update(kw)
    return dr.gate(d or dec(), **args), rs


class Shrinkage(unittest.TestCase):
    def test_shrink_toward_zero_by_n(self):
        self.assertAlmostEqual(dr.shrink(-4.96, 13), -4.96 * 13 / 33)
        self.assertAlmostEqual(dr.shrink(1.85, 10), 1.85 / 3)
        self.assertAlmostEqual(dr.shrink(-1.16, 251), -1.16 * 251 / 271)
        self.assertEqual(dr.shrink(5.0, 0), 0.0)

    def test_cells_for_the_prompt_are_labelled_and_need_n(self):
        st = {"type:analyst/hold/1d": {"n": 13, "mean_pct": -4.96, "hit": 0.0}, "mover/short/1d": {"n": 10, "mean_pct": 1.85, "hit": 0.7},
              "news/buy/1h": {"n": 2, "mean_pct": 0.6, "hit": 0.5}}
        rows = dr.shrunk_cells(st)
        self.assertEqual(len(rows), 2)                         # n=2 is below the floor
        self.assertTrue(rows[0].startswith("type:analyst/hold/1d n=13 raw -4.96% shrunk -1.95%"))
        self.assertIn("shrunk +0.62%", rows[1])

    def test_source_labels(self):
        self.assertEqual(dr.desk_source("forced-flow notice: delist"), "forced")
        self.assertEqual(dr.desk_source("recent linked headline"), "news")
        self.assertEqual(dr.desk_source("top mover in its asset class"), "mover")

    def test_every_rule_states_its_evidence(self):
        for k, v in dr.RULES.items():
            self.assertTrue(v["text"] and v["evidence"], k)
        self.assertTrue(any("n=13" in v["evidence"] for v in dr.RULES.values()))
        self.assertTrue(any("n=10" in v["evidence"] for v in dr.RULES.values()))


class Gate(unittest.TestCase):
    def test_analyst_note_is_refused_but_forced_flow_is_not(self):
        g, _ = gate(news_type="analyst")
        self.assertTrue(g["veto"].startswith("R1"))
        g, _ = gate(news_type="analyst", forced=True)
        self.assertIsNone(g["veto"])

    def test_small_expected_move_vetoes_and_never_enlarges(self):
        self.assertTrue(gate(dec(expected_move_pct=0.2))[0]["veto"].startswith("R8"))
        g, _ = gate(dec(expected_move_pct=50.0))
        self.assertEqual(g["size_pct"], 10.0)                  # a big stated move does not raise the size

    def test_longs_are_halved_and_shorts_are_not_favoured(self):
        self.assertEqual(gate(dec(action="buy"))[0]["size_pct"], 5.0)
        self.assertEqual(gate(dec(action="short"))[0]["size_pct"], 10.0)
        self.assertIn("R2", gate(dec(action="buy"))[0]["rules"])

    def test_caps_and_time_exit(self):
        g, _ = gate(dec(size_pct=90.0, leverage=15.0, review_in_min=2000, action="short"))
        self.assertEqual((g["size_pct"], g["leverage"], g["review_in_min"]), (dr.SIZE_CAP_PCT, dr.LEV_CAP, dr.REVIEW_MAX_MIN))
        self.assertEqual(g["max_hold_s"], dr.MAX_HOLD_S)
        self.assertEqual(gate(forced=True)[0]["max_hold_s"], dr.FORCED_HOLD_S)
        for rule in ("R3", "R5"):
            self.assertIn(rule, g["rules"])

    def test_position_and_daily_entry_limits(self):
        self.assertTrue(gate(n_open=dr.MAX_POS)[0]["veto"].startswith("R5"))
        rs = dr.new_risk_state(147.0, NOW)
        for _ in range(dr.MAX_ENTRIES_DAY):
            dr.note_entry(rs, 5.0, NOW)
        self.assertTrue(gate(rs=rs)[0]["veto"].startswith("R5"))
        self.assertIsNone(gate(rs=rs, is_add=True)[0]["veto"])             # an add is not a new entry
        self.assertTrue(gate(extra_entries=dr.MAX_ENTRIES_DAY)[0]["veto"].startswith("R5"))

    def test_no_martingale_after_a_loss(self):
        rs = dr.new_risk_state(147.0, NOW)
        dr.note_entry(rs, 4.0, NOW)
        dr.risk_trade_closed(rs, -1.0)
        g, _ = gate(dec(size_pct=10.0), rs=rs)
        self.assertEqual(g["size_pct"], 4.0)
        self.assertIn("R6", g["rules"])
        dr.risk_trade_closed(rs, 1.0)
        self.assertEqual(gate(dec(size_pct=10.0), rs=rs)[0]["size_pct"], 10.0)

    def test_no_averaging_down(self):
        self.assertTrue(dr.may_add(1, 100.0, 101.0))
        self.assertFalse(dr.may_add(1, 100.0, 99.0))
        self.assertTrue(dr.may_add(-1, 100.0, 99.0))
        self.assertFalse(dr.may_add(-1, 100.0, 101.0))
        self.assertFalse(dr.may_add(1, 100.0, 100.0))

    def test_nothing_ever_raises_size_or_leverage(self):
        for size in (0.6, 5.0, 19.0, 100.0):
            for lev in (1.0, 2.5, 20.0):
                for act in ("buy", "short"):
                    g, _ = gate(dec(size_pct=size, leverage=lev, action=act))
                    self.assertLessEqual(g["size_pct"], size)
                    self.assertLessEqual(g["leverage"], lev)


class RiskState(unittest.TestCase):
    def test_bank_at_3x_and_halt_at_0_4x_and_cohort_roll(self):
        rs = dr.new_risk_state(100.0, NOW)
        self.assertTrue(dr.risk_status(rs, 100.0, NOW)["allow"])
        st = dr.risk_status(rs, 300.0, NOW + 60)
        self.assertTrue(st["banked"] and not st["allow"])
        rs = dr.new_risk_state(100.0, NOW)
        st = dr.risk_status(rs, 40.0, NOW + 60)
        self.assertTrue(st["halted"] and not st["allow"])
        st = dr.risk_status(rs, 40.0, NOW + dr.COHORT_DAYS * 86400 + 1)      # a new 30-day cohort starts from today's equity
        self.assertTrue(st["allow"] and not st["halted"])
        self.assertEqual(rs["cohort_eq"], 40.0)

    def test_drawdown_half_then_cooldown_then_reset(self):
        rs = dr.new_risk_state(100.0, NOW)
        rs["day_eq"] = 88.0                                      # isolate from the daily-loss halt
        st = dr.risk_status(rs, 88.0, NOW + 3600)
        self.assertTrue(st["allow"] and st["mult"] == 0.5)
        rs["day_eq"] = 80.0                                      # isolate from the daily-loss halt
        st = dr.risk_status(rs, 79.0, NOW + 7200)
        self.assertFalse(st["allow"])
        self.assertTrue(rs["cool_until"] > NOW)
        st = dr.risk_status(rs, 79.0, NOW + 7200 + dr.DD_COOLDOWN_S + 1)
        self.assertEqual(rs["peak"], 79.0)                       # the brake cannot lock forever
        self.assertTrue(st["allow"])

    def test_daily_loss_halt_ends_next_utc_day(self):
        rs = dr.new_risk_state(100.0, NOW)
        self.assertFalse(dr.risk_status(rs, 96.5, NOW + 60)["allow"])
        self.assertTrue(dr.risk_status(rs, 96.5, NOW + 86400 + 60)["allow"])

    def test_loss_streak_halves_size_until_a_win(self):
        rs = dr.new_risk_state(100.0, NOW)
        dr.risk_trade_closed(rs, -1)
        self.assertEqual(dr.risk_status(rs, 100.0, NOW)["mult"], 1.0)
        dr.risk_trade_closed(rs, -1)
        self.assertEqual(dr.risk_status(rs, 100.0, NOW)["mult"], 0.5)
        dr.risk_trade_closed(rs, 2)
        self.assertEqual(dr.risk_status(rs, 100.0, NOW)["mult"], 1.0)

    def test_bank_and_halt_levels_are_the_event_book_levels(self):
        from core import event_book
        self.assertEqual((dr.BANK_MULT, dr.HALT_MULT), (event_book.BANK_MULT, event_book.HALT_MULT))


class Blocks(unittest.TestCase):
    def test_fast_news_block_has_labels_latency_and_window(self):
        rows = [{"source": "eqn_rest", "title": "XYZ to be delisted", "t_pub": NOW - 10, "t_seen": NOW - 5, "lat_s": 5.0, "cls": "delist", "coins": ["XYZ"]},
                {"source": "prnewswire", "title": "old", "t_pub": None, "t_seen": NOW - 4000, "lat_s": None, "cls": None, "coins": []}]
        b = dr.fast_news_block(rows, NOW, {"eqn_rest": {"median_s": 4.4}, "okx": {"median_s": None}})
        self.assertEqual(len(b["items"]), 1)
        self.assertEqual((b["items"][0]["src"], b["items"][0]["latency_s"], b["items"][0]["flow"]), ("eqn_rest", 5.0, "delist"))
        self.assertEqual(b["source_latency_median_s"], {"eqn_rest": 4.4})
        self.assertIn("no edge", b["evidence"])

    def test_stale_feeds_are_flagged_not_silently_missing(self):
        h = dr.feed_health({"eqn_rest": {"last_ok_age_s": 2.0}, "sec_8k": {"last_ok_age_s": 900.0}, "okx": {"last_ok_age_s": None}},
                           {"event_book": {"ts": NOW - 100, "max_age_s": 3600}, "notice_fwd": {"ts": None, "max_age_s": 3600},
                            "okx_funding_fwd": {"ts": NOW - 50000, "max_age_s": 43200}}, NOW)
        self.assertEqual(sorted(h["stale"]), ["ledger:notice_fwd", "ledger:okx_funding_fwd", "okx", "sec_8k"])

    def test_flow_rates_state_the_negative_recent_result(self):
        self.assertIn("lost 1.8% per trade", dr.FLOW_RECENT_OOS)
        self.assertIn("48 trades", dr.FLOW_RECENT_OOS)
        self.assertTrue(any("mon_tag" in r for r in dr.FLOW_BASE_RATES))


class Feeds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, rows):
        from core import news_ingest
        with open(Path(self.tmp.name) / f"{news_ingest._day(time.time())}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.write('{"broken')                                  # a partial line must not drop the rest

    def test_forced_candidates_only_for_coins_in_the_universe(self):
        now = time.time()
        self.write([{"event": "item", "source": "eqn_rest", "key": "k1", "title": "t1", "t_pub": now - 8, "t_seen": now - 4, "lat_s": 4.0},
                    {"event": "item", "source": "eqn_rest", "key": "k2", "title": "t2", "t_pub": now - 8, "t_seen": now - 4, "lat_s": 4.0},
                    {"event": "item", "source": "eqn_rest", "key": "k3", "title": "t3", "t_pub": now - 8, "t_seen": now - 5000, "lat_s": 4.0}])
        fake = {"t1": {"cls": "delist", "side": -1, "coins": ["XRP"]}, "t2": {"cls": "delist", "side": -1, "coins": ["TINYCOIN"]},
                "t3": {"cls": "delist", "side": -1, "coins": ["ADA"]}}
        with mock.patch.object(df.notice_fwd, "classify", side_effect=lambda src, title: fake.get(title)):
            f = df.Feeds(ingest_dir=self.tmp.name, universe={"XRP-USD", "ADA-USD"})
            out = f.forced_candidates(now)
        self.assertEqual(list(out), ["XRP-USD"])               # TINYCOIN is not tradable here; t3 is older than the window
        self.assertEqual(out["XRP-USD"]["cls"], "delist")
        self.assertEqual(out["XRP-USD"]["lat_s"], 4.0)

    def test_block_flags_missing_ledgers_and_reads_the_log(self):
        now = time.time()
        self.write([{"event": "item", "source": "eqn_rest", "key": "k1", "title": "hello", "t_pub": now - 8, "t_seen": now - 4, "lat_s": 4.0}])
        with mock.patch.object(df.notice_fwd, "classify", return_value=None):
            f = df.Feeds(ingest_dir=self.tmp.name, universe=set())
            f.source_health = lambda: {"eqn_rest": {"last_ok_age_s": 3.0, "median_s": 4.4, "n": 60}}
            f.ledgers["event_book"] = {"ts": now - 60, "view": {"events_seen": 1}}
            block, health = f.block(now)
        self.assertEqual(block["fast_news"]["items"][0]["title"], "hello")
        self.assertIn("ledger:notice_fwd", block["freshness"]["stale"])
        self.assertNotIn("ledger:event_book", block["freshness"]["stale"])
        self.assertIn("not available", block["forward_ledgers"]["notice_fwd"]["status"])
        self.assertEqual(health["stale"], block["freshness"]["stale"])

    def test_compact_ledgers(self):
        eb = df.compact_ledger("event_book", {"run_utc": "2026-11-26T06:52:10Z", "events_seen": 1, "open": 0, "closed": 0, "components": {"l1f": 0}})
        self.assertEqual(eb["view"]["events_seen"], 1)
        self.assertGreater(eb["ts"], 1.7e9)
        ok = df.compact_ledger("okx_funding_fwd", {"updated_utc": "2026-11-26T04:01:45Z", "meta": {"settlements": 5},
                                                   "cohorts": {"a": {"mean_net_2x": -0.005, "e_value_edge": 0.9, "verdict": "continue"},
                                                               "b": {"mean_net_2x": -0.009, "e_value_edge": 1.0, "verdict": "continue"}}})
        self.assertEqual(ok["view"]["mean_net_2x_range"], [-0.009, -0.005])
        nf = df.compact_ledger("notice_fwd", {"updated_utc": "2026-11-27T01:00:00Z", "verdict": {"verdict": "underpowered", "n": 0}, "clusters": 3, "pending": 1})
        self.assertEqual(nf["view"]["verdict"], "underpowered")

    def test_funding_context(self):
        f = df.Feeds(ingest_dir=self.tmp.name, universe={"BTC-USD"})
        body = json.dumps({"data": [{"fundingRate": "0.0001", "nextFundingRate": "0.00015", "fundingTime": str(int((time.time() + 1800) * 1000))}]}).encode()
        f.fetch = lambda url: body
        f.refresh_funding()
        c = f.candidate_context("BTC-USD")["funding_okx"]
        self.assertEqual((c["rate_pct"], c["predicted_pct"]), (0.01, 0.015))
        self.assertEqual(f.candidate_context("ETH-USD"), {})


if __name__ == "__main__":
    unittest.main()
