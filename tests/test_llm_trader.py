"""Offline tests for the LLM trader (fake model, synthetic quotes)."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import llm_trader as lt


def quote(sym, px=100.0, move=0.0, vol=2e6, ts=None, open_=True):
    return {"symbol": sym, "price": px, "bid": px * 0.9998, "ask": px * 1.0002, "prev_close": px / (1 + move / 100),
            "change_pct": move, "volume": vol, "ts": ts or time.time(), "open": open_, "name": sym + " Inc"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch("core.llm_trader.data.fx_to_usd", return_value=0.03),
                  mock.patch("core.llm_trader.news.symbol_news", return_value={"items": [
                      {"title": "Big news", "source": "X", "sentiment": 0.3}]}),
                  mock.patch.object(lt.LlmTrader, "avg50", return_value=1e6),
                  mock.patch("core.llm_trader.archive_headlines", return_value=[])):
            p.start()
            self.addCleanup(p.stop)
        self.replies = []
        self.prompts = []

        self.debate_calls = []

        def chat(system, user):
            if system in (lt.BULL, lt.BEAR):               # research stage: separate from the decision replies
                self.debate_calls.append(system)
                return json.dumps({"arguments": {"AAA": "case for AAA"}}), "fake-model"
            self.prompts.append(user)
            return (self.replies.pop(0) if self.replies else '{"decisions":[]}'), "fake-model"
        self.t = lt.LlmTrader(Path(self.tmp.name) / "s.json", Path(self.tmp.name) / "l.jsonl", chat=chat, rng_seed=1)
        self.t.context = {"SPY": quote("SPY", move=1.0), "^VIX": quote("^VIX", px=20)}

    def market(self, **over):
        q = {s: quote(s) for s in ("AAA", "BBB", "CCC", "DDD", "EEE")}
        q.update(over)
        return q

    def reply(self, *decisions, view="ok"):
        self.replies.append(json.dumps({"decisions": list(decisions), "market_view": view}))

    def log_kinds(self):
        return [json.loads(l)["kind"] for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines()]


class Parsing(unittest.TestCase):
    def test_validation_rules(self):
        text = json.dumps({"decisions": [
            {"symbol": "aaa", "action": "buy", "size_pct": 999, "reason": "x" * 500, "confidence": 7},
            {"symbol": "ZZZ", "action": "buy", "size_pct": 3},            # not a candidate
            {"symbol": "HHH", "action": "sell"},                          # no position
            {"symbol": "AAA", "action": "short", "size_pct": 1},          # unknown action
            {"symbol": "HELD", "action": "sell"}, {"foo": 1}, "junk"], "market_view": "m" * 500})
        out = lt.parse_decisions("noise " + text + " tail", {"AAA"}, {"HELD"})
        syms = [(d["symbol"], d["action"]) for d in out["decisions"]]
        self.assertEqual(syms, [("AAA", "buy"), ("HELD", "sell")])
        self.assertEqual(out["decisions"][0]["size_pct"], lt.SIZE_MAX * 100)
        self.assertEqual(len(out["decisions"][0]["reason"]), 200)
        self.assertEqual(out["decisions"][0]["confidence"], 1.0)
        self.assertEqual(len(out["rejected"]), 5)
        self.assertEqual(lt.parse_decisions("no json", set(), set())["error"], "no JSON object in reply")
        self.assertEqual(lt.parse_decisions('{"decisions": "x"}', set(), set())["decisions"], [])


class Trading(Base):
    def test_buy_candidate_opens_position_control_and_logs_everything(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "guidance raise", "confidence": 0.7})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        self.assertIn("AAA", self.t.acct.positions)
        self.assertEqual(len(self.t.ctrl.positions), 1)
        self.assertNotIn("AAA", self.t.ctrl.positions)
        self.assertEqual(self.log_kinds().count("call"), 1)
        for kind in ("decision", "order"):
            self.assertIn(kind, self.log_kinds())
        call = next(json.loads(l) for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines() if '"kind": "call"' in l)
        self.assertEqual(call["context"]["candidates"][0]["symbol"], "AAA")
        self.assertEqual(call["context"]["market"]["vix"], 20)
        self.assertIn("guidance raise", call["raw"])
        self.assertEqual(self.t.decisions[0]["executed"]["status"], "filled")

    def test_bull_bear_debate_reaches_the_decision_prompt_and_every_candidate_is_scored(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12), BBB=quote("BBB", px=50, move=9)))
        self.assertEqual(len(self.debate_calls), 2)
        ctx = json.loads(self.prompts[0].split("JSON):\n", 1)[1])
        self.assertEqual(ctx["bull_case"]["AAA"], "case for AAA")
        self.assertIn("bear_case", ctx)
        self.assertIn("track_record", ctx)
        self.assertEqual({(c["symbol"], c["action"]) for c in self.t.cands}, {("AAA", "buy"), ("BBB", "hold")})

    def test_outcomes_scored_vs_spy_for_buys_and_passes_and_fed_back_as_memory(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "reason": "guidance"})
        self.t.context["SPY"] = quote("SPY", px=500, move=1)
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12), BBB=quote("BBB", px=50, move=9)))
        for c in self.t.cands:
            c["ts"] -= 86400 + 60
        self.t.context["SPY"] = quote("SPY", px=505, move=2)            # SPY +1%
        later = self.market(AAA=quote("AAA", px=110), BBB=quote("BBB", px=49))
        self.t.scan(later)
        out = {c["symbol"]: c["out"]["86400"] for c in self.t.cands}
        self.assertAlmostEqual(out["AAA"], 0.10 - 0.01, places=4)
        self.assertAlmostEqual(out["BBB"], -0.02 - 0.01, places=4)
        d = self.t.evaluate()["discrimination"]
        self.assertEqual((d["bought"]["n"], d["passed"]["n"]), (1, 1))
        self.assertEqual({m["symbol"] for m in self.t.memory()}, {"AAA", "BBB"})
        self.assertIn("candidate_outcome", self.log_kinds())

    def test_failed_debate_does_not_block_the_decision(self):
        real = self.t.chat
        self.t.chat = lambda s, u: ("", "down") if s in (lt.BULL, lt.BEAR) else real(s, u)
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertIn("AAA", self.t.acct.positions)

    def test_can_buy_any_listed_stock_but_not_an_unknown_symbol(self):
        self.reply({"symbol": "BBB", "action": "buy", "size_pct": 5, "reason": "my own idea"},
                   {"symbol": "ZZZ", "action": "buy", "size_pct": 5})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertEqual(set(self.t.acct.positions), {"BBB"})
        self.assertTrue(any(json.loads(l).get("rejected") for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines()))

    def test_size_and_exposure_caps(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5}, {"symbol": "BBB", "action": "buy", "size_pct": 5})
        self.t.scan(self.market(AAA=quote("AAA", move=12), BBB=quote("BBB", move=9)))
        eq = self.t.acct.equity()
        for p in self.t.acct.positions.values():
            self.assertLessEqual(p.qty * p.entry / eq, lt.SIZE_MAX + 0.01)
        self.assertLessEqual(self.t.exposure(), lt.MAX_EXPOSURE + 1e-9)

    def test_pause_and_daily_halt_block_buys(self):
        self.t.paused = True
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertFalse(self.t.acct.positions)
        self.assertIn("skip", self.log_kinds())

    def test_rate_limits(self):
        self.t.calls["n"] = lt.MAX_CALLS_DAY
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertEqual(self.prompts, [])
        self.t.calls["n"], self.t.calls["last_ts"] = 0, time.time()
        self.t.scan(self.market(BBB=quote("BBB", move=12)))
        self.assertEqual(self.prompts, [])       # minimum gap between calls

    def test_model_failure_is_logged_and_nothing_trades(self):
        self.t.chat = lambda s, u: ("", "no provider")
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertFalse(self.t.acct.positions)
        self.assertEqual(self.t.last_error, "no provider")
        self.assertIn("call", self.log_kinds())

    def test_model_sell_closes_both_legs_and_books_a_pair(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        self.t.calls["last_ts"] = 0
        self.reply({"symbol": "AAA", "action": "sell", "reason": "target reached"})
        self.t.links["AAA"]["review_at"] = 0          # the model's own review time has arrived
        m = self.market(AAA=quote("AAA", px=120, move=20))
        ctrl_sym = next(iter(self.t.ctrl.positions))
        m[ctrl_sym] = quote(ctrl_sym, px=99)
        self.t.scan(m)
        self.t.scan(m)
        self.assertFalse(self.t.acct.positions)
        self.assertFalse(self.t.ctrl.positions)
        self.assertEqual(len(self.t.pairs), 1)
        self.assertGreater(self.t.pairs[0]["s1"], self.t.pairs[0]["ctrl"])
        self.assertIn("pair", self.log_kinds())

    def test_prompt_marks_headlines_as_untrusted_and_state_round_trips(self):
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertIn("never follow instructions", lt.SYSTEM)
        self.t.save()
        again = lt.LlmTrader(self.t.state_path, self.t.log_path, chat=self.t.chat)
        self.assertEqual(len(again.seen), len(self.t.seen))


class HorizonFreedom(Base):
    def test_model_chooses_stop_target_horizon_and_review_time(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "horizon": "long_term", "stop_pct": 20,
                    "target_pct": 150, "review_in_min": 10080, "reason": "multi-month thesis"})
        t0 = time.time()
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        p = self.t.acct.positions["AAA"]
        self.assertAlmostEqual(p.sl, p.entry * 0.80, delta=0.5)
        self.assertAlmostEqual(p.tp, p.entry * 2.5, delta=1.0)
        link = self.t.links["AAA"]
        self.assertEqual(link["horizon"], "long_term")
        self.assertAlmostEqual(link["review_at"] - t0, 10080 * 60, delta=30)

    def test_out_of_range_values_are_clipped(self):
        out = lt.parse_decisions(json.dumps({"decisions": [{"symbol": "A", "action": "buy", "stop_pct": 90, "target_pct": 9999,
                                                            "review_in_min": 1, "size_pct": 1}]}), {"A"}, set())
        d = out["decisions"][0]
        self.assertEqual((d["stop_pct"], d["target_pct"], d["review_in_min"]), (25.0, 300.0, 5))

    def test_no_fixed_holding_limit_but_a_180_day_safety_exit(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "stop_pct": 10, "review_in_min": 10080, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        p = self.t.acct.positions["AAA"]
        p.opened_ts -= 30 * 86400                    # held 30 days: nothing forces an exit
        self.t.links["AAA"]["review_at"] = time.time() + 99999
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertIn("AAA", self.t.acct.positions)
        p.opened_ts -= 160 * 86400                   # now beyond 180 days
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertNotIn("AAA", self.t.acct.positions)

    def test_review_runs_on_the_models_schedule_and_adjust_moves_the_stop(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "stop_pct": 10, "review_in_min": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.assertEqual(len(self.prompts), 1)
        self.t.calls["last_ts"] = 0
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertEqual(len(self.prompts), 1)       # review not due yet (5 minutes)
        self.t.links["AAA"]["review_at"] = 0
        self.reply({"symbol": "AAA", "action": "adjust", "stop_pct": 3, "target_pct": 20, "review_in_min": 30, "reason": "lock gains"})
        self.t.scan(self.market(AAA=quote("AAA", px=110)))
        self.assertEqual(len(self.prompts), 2)
        p = self.t.acct.positions["AAA"]
        self.assertAlmostEqual(p.sl, 110 * 0.9998 * 0.97, delta=0.3)
        self.assertIn("adjust", self.log_kinds())

    def test_adjust_without_a_position_is_rejected(self):
        out = lt.parse_decisions(json.dumps({"decisions": [{"symbol": "ZZ", "action": "adjust"}]}), {"A"}, {"HELD"})
        self.assertEqual(out["decisions"], [])
        self.assertEqual(len(out["rejected"]), 1)


class ViewData(Base):
    def test_view_converts_control_with_the_same_opening_rate(self):
        self.t.ctrl.balance = 148.5
        with mock.patch("core.llm_trader.data.fx_to_usd", return_value=0.025):
            view = self.t.view()
        self.assertAlmostEqual(view["control_equity_thb"], 4950.0)
        self.assertAlmostEqual(view["equity_thb"], 5000.0)

    def test_view_positions_carry_stop_target_pnl_and_reason_for_the_ui(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "horizon": "swing", "stop_pct": 6, "target_pct": 25,
                    "review_in_min": 120, "reason": "guidance"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        v = self.t.view()
        p = v["positions"][0]
        for key in ("symbol", "entry", "mark", "pnl_pct", "stop", "target", "horizon", "held_hours", "your_reason"):
            self.assertIn(key, p)
        self.assertEqual((p["horizon"], p["your_reason"]), ("swing", "guidance"))
        self.assertIn("discrimination", v["evaluation"])


class LogView(Base):
    def test_cycles_show_why_it_bought_why_it_passed_and_what_happened_next(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "horizon": "swing", "stop_pct": 6, "review_in_min": 60,
                    "reason": "guidance raise"},
                   {"symbol": "BBB", "action": "hold", "reason": "market-wide move, no catalyst"})
        self.t.context["SPY"] = quote("SPY", px=500, move=1)
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12), BBB=quote("BBB", px=50, move=9)))
        for c in self.t.cands:
            c["ts"] -= 3700
        self.t.context["SPY"] = quote("SPY", px=500, move=1)
        self.t.scan(self.market(AAA=quote("AAA", px=104), BBB=quote("BBB", px=49)))
        out = lt.build_cycles(lt.read_log_tail(self.t.log_path))
        self.assertEqual(len(out["cycles"]), 1)
        c = out["cycles"][0]
        self.assertEqual({x["symbol"] for x in c["candidates"]}, {"AAA", "BBB"})
        reasons = {d["symbol"]: (d["action"], d["reason"]) for d in c["decisions"]}
        self.assertEqual(reasons["AAA"], ("buy", "guidance raise"))
        self.assertEqual(reasons["BBB"], ("hold", "market-wide move, no catalyst"))
        self.assertTrue(any(a["kind"] == "order" and a["symbol"] == "AAA" for a in c["actions"]))
        self.assertEqual(c["bull"]["AAA"], "case for AAA")
        self.assertEqual({o["symbol"] for o in c["outcomes"]}, {"AAA", "BBB"})
        self.assertIn("market_view", c)

    def test_blocked_buys_show_the_reason_and_stop_exits_are_logged(self):
        self.t.paused = True
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        c = lt.build_cycles(lt.read_log_tail(self.t.log_path))["cycles"][0]
        self.assertEqual([a["why"] for a in c["actions"] if a["kind"] == "skip"], ["paused"])
        self.t.paused = False
        self.t.calls["last_ts"] = 0
        self.t.seen.clear()
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "stop_pct": 5, "review_in_min": 999, "reason": "r2"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        with mock.patch("core.llm_trader.data.quote_fast", lambda s, ttl=1.0: quote(s, px=90)):
            self.t.watch()
        closed = lt.build_cycles(lt.read_log_tail(self.t.log_path))["closed"]
        self.assertTrue(any(x["kind"] == "trade_closed" and x["reason"] == "stop loss" and x["account"] == "model" for x in closed))

    def test_prompt_asks_for_a_decision_on_every_candidate(self):
        self.assertIn("EVERY candidate", lt.SYSTEM)


class LeverageAndEntry(Base):
    def test_model_chooses_leverage_and_notional_is_margin_times_leverage(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 5, "stop_pct": 4, "review_in_min": 60, "reason": "r"})
        eq = self.t.acct.equity()
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        ex = self.t.decisions[0]["executed"]
        self.assertEqual((ex["status"], ex["leverage"]), ("filled", 5.0))
        self.assertAlmostEqual(ex["notional_usd"], eq * 0.25, delta=0.1)
        self.assertAlmostEqual(ex["margin_usd"], eq * 0.05, delta=0.05)
        p = self.t.acct.positions["AAA"]
        self.assertAlmostEqual(p.qty * p.entry, ex["notional_usd"], delta=0.2)
        cp = next(iter(self.t.ctrl.positions.values()))
        self.assertAlmostEqual(cp.qty * cp.entry, ex["notional_usd"], delta=0.3)       # control gets the same notional
        v = self.t.view()["positions"][0]
        self.assertEqual((v["leverage"], v["entry_type"]), (5.0, "market"))
        self.assertAlmostEqual(v["notional_usd"], ex["notional_usd"], delta=0.3)

    def test_only_margin_limits_size_and_it_is_reported(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 100, "leverage": 20, "stop_pct": 5, "review_in_min": 60, "reason": "all in"})
        eq = self.t.acct.equity()
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        ex = self.t.decisions[0]["executed"]
        self.assertEqual(ex["status"], "filled")
        self.assertGreater(ex["notional_usd"], eq * 10)                               # no rule of ours shrinks it
        self.assertLessEqual(ex["notional_usd"], eq * lt.LEV_MAX)                     # bounded by margin
        self.assertTrue(any("free margin" in c for c in ex["clipped_by"]))

    def test_buying_more_of_a_held_stock_scales_the_position_in_and_the_control_too(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 2, "stop_pct": 6, "review_in_min": 60, "reason": "first"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        q1 = self.t.acct.positions["AAA"].qty
        ctrl_sym = self.t.links["AAA"]["ctrl"]
        c1 = self.t.ctrl.positions[ctrl_sym].qty
        n1 = self.t.links["AAA"]["notional"]
        self.t.calls["last_ts"] = 0
        self.t.seen.clear()
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 2, "stop_pct": 6, "review_in_min": 60, "reason": "add"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.assertGreater(self.t.acct.positions["AAA"].qty, q1 * 1.8)
        self.assertGreater(self.t.ctrl.positions[ctrl_sym].qty, c1 * 1.8)
        self.assertGreater(self.t.links["AAA"]["notional"], n1 * 1.8)
        self.assertTrue(self.t.decisions[-1]["executed"]["scaled_in"])

    def test_only_a_ruined_account_is_blocked(self):
        self.t.acct.balance = self.t.capital_usd * 0.04
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertFalse(self.t.acct.positions)
        self.assertIn("skip", self.log_kinds())

    def test_limit_entry_waits_then_fills_and_creates_the_control(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "entry": "limit", "limit_price": 98, "valid_min": 30,
                    "stop_pct": 6, "review_in_min": 60, "reason": "buy the dip"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        ex = self.t.decisions[0]["executed"]
        self.assertEqual((ex["status"], ex["entry"]), ("pending", "limit"))
        self.assertIn("AAA", self.t.pending)
        self.assertFalse(self.t.acct.positions)
        self.assertFalse(self.t.ctrl.positions)
        self.t.scan(self.market(AAA=quote("AAA", px=97.5)))                           # price drops through the limit
        self.assertIn("AAA", self.t.acct.positions)
        self.assertNotIn("AAA", self.t.pending)
        self.assertIn("AAA", self.t.links)
        self.assertEqual(len(self.t.ctrl.positions), 1)
        self.assertIn("limit_filled", self.log_kinds())

    def test_unfilled_limit_entry_expires(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "entry": "limit", "limit_price": 90, "valid_min": 5,
                    "stop_pct": 6, "review_in_min": 60, "reason": "deep bid"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.t.pending["AAA"]["expires"] = time.time() - 1
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertNotIn("AAA", self.t.pending)
        self.assertFalse(self.t.acct.positions)
        self.assertIn("limit_expired", self.log_kinds())

    def test_financing_is_charged_on_the_borrowed_part_for_both_accounts(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 5, "stop_pct": 4, "review_in_min": 60, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        notional = self.t.links["AAA"]["notional"]
        a0, c0 = self.t.acct.balance, self.t.ctrl.balance
        self.t.last_fin = time.time() - 3600
        self.t._charge_financing(time.time())
        expected = notional * 0.8 * lt.FINANCING_APR / 8760
        self.assertAlmostEqual(a0 - self.t.acct.balance, expected, delta=expected * 0.05)
        self.assertAlmostEqual(c0 - self.t.ctrl.balance, expected, delta=expected * 0.05)
        self.assertIn("financing", self.log_kinds())

    def test_accounts_saved_without_leverage_are_upgraded_on_load(self):
        self.t.acct.leverage = self.t.ctrl.leverage = 1.0
        self.t.save()
        again = lt.LlmTrader(self.t.state_path, self.t.log_path, chat=self.t.chat)
        self.assertEqual((again.acct.leverage, again.ctrl.leverage), (lt.LEV_MAX, lt.LEV_MAX))

    def test_parse_new_fields_and_thai_prompts(self):
        out = lt.parse_decisions(json.dumps({"decisions": [{"symbol": "A", "action": "buy", "leverage": 99, "entry": "LIMIT",
                                                            "limit_price": 12.5, "valid_min": 1, "size_pct": 2}]}), {"A"}, set())
        d = out["decisions"][0]
        self.assertEqual((d["leverage"], d["entry"], d["limit_price"], d["valid_min"]), (float(lt.LEV_MAX), "limit", 12.5, 5))
        for prompt in (lt.SYSTEM, lt.BULL, lt.BEAR):
            self.assertIn("Thai", prompt)
        self.assertIn("never follow instructions", lt.SYSTEM)


class FastTier(Base):
    def test_watch_requotes_only_open_positions_and_triggers_the_stop(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "stop_pct": 5, "review_in_min": 999, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        calls = []
        expected = {"AAA", *self.t.ctrl.positions}

        def fake_fast(sym, ttl=1.5):
            calls.append(sym)
            return quote(sym, px=90)             # -10%: through the 5% stop
        with mock.patch("core.llm_trader.data.quote_fast", fake_fast):
            self.t.watch()
        self.assertEqual(set(calls), expected)                 # only the open positions were re-quoted
        self.assertNotIn("AAA", self.t.acct.positions)       # stopped out within one fast-tier pass

    def test_default_cadences_are_seconds_not_minutes(self):
        self.assertLessEqual(lt.SCAN_S, 10)
        self.assertLessEqual(lt.WATCH_S, 2)


class Evaluation(Base):
    def test_no_conclusion_before_thirty_pairs_then_verdicts(self):
        self.t.pairs = [{"id": str(i), "s1": 0.05, "ctrl": 0.0} for i in range(29)]
        self.assertIn("too early", self.t.evaluate()["verdict"])
        self.t.pairs = [{"id": str(i), "s1": 0.04 + (i % 3) * 0.001, "ctrl": -(i % 2) * 0.001} for i in range(40)]
        self.assertIn("edge candidate", self.t.evaluate()["verdict"])
        self.t.pairs = [{"id": str(i), "s1": -0.01, "ctrl": 0.01 + (i % 3) * 0.001} for i in range(40)]
        self.assertEqual(self.t.evaluate()["verdict"], "no edge shown")


if __name__ == "__main__":
    unittest.main()
