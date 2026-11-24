"""Offline tests for the LLM trader (fake model, synthetic quotes)."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import llm_trader as lt
from core.storage import write_json_atomic


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
                  mock.patch("core.llm_trader.archive_headlines", return_value=[]),
                  mock.patch("core.llm_trader.recent_news", return_value={}),
                  mock.patch("core.llm_trader.buzz_symbols", return_value={}),
                  mock.patch("core.llm_trader.ny_time", return_value=(5, (12, 0), "2026-11-28"))):
            p.start()
            self.addCleanup(p.stop)
        self.replies = []
        self.prompts = []

        self.debate_calls = []
        self.analyst_calls = []
        self.risk_calls = []
        self.risk_replies = []

        def chat(system, user):
            if system in (lt.ANALYST_NEWS, lt.ANALYST_PRICE, lt.ANALYST_MACRO):
                self.analyst_calls.append(user)
                return json.dumps({"notes": {"AAA": "note for AAA"}}), "fake-model"
            if system == lt.RISK:
                self.risk_calls.append(user)
                return (self.risk_replies.pop(0) if self.risk_replies else '{"reviews":[]}'), "fake-model"
            if system.startswith(lt.BULL) or system.startswith(lt.BEAR):   # research stage: separate from decisions
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
            {"symbol": "AAA", "action": "fly", "size_pct": 1},            # unknown action
            {"symbol": "ZZZ", "action": "short", "size_pct": 1},          # short needs a candidate too
            {"symbol": "HELD", "action": "sell"}, {"foo": 1}, "junk"], "market_view": "m" * 500})
        out = lt.parse_decisions("noise " + text + " tail", {"AAA"}, {"HELD"})
        syms = [(d["symbol"], d["action"]) for d in out["decisions"]]
        self.assertEqual(syms, [("AAA", "buy"), ("HELD", "sell")])
        self.assertEqual(out["decisions"][0]["size_pct"], lt.SIZE_MAX * 100)
        self.assertEqual(len(out["decisions"][0]["reason"]), 200)
        self.assertEqual(out["decisions"][0]["confidence"], 1.0)
        self.assertEqual(len(out["rejected"]), 6)
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
        self.assertEqual(len(self.debate_calls), 4)
        ctx = json.loads(self.prompts[0].split("JSON):\n", 1)[1])
        self.assertEqual(ctx["bull_case"]["AAA"], "case for AAA")
        self.assertIn("bear_case", ctx)
        self.assertIn("bull_rebuttal", ctx)
        self.assertIn("analysts", ctx)
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
        self.t.chat = lambda s, u: ("", "down") if s.startswith((lt.BULL, lt.BEAR)) else real(s, u)
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

    def test_every_stage_starts_with_the_same_cacheable_block(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "leverage": 1, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12), BBB=quote("BBB", px=50, move=9)))
        texts = self.analyst_calls + self.prompts + self.risk_calls
        self.assertTrue(texts)
        shared = self.analyst_calls[0][:self.analyst_calls[0].rindex("]")]     # header + market + candidates list
        for u in texts:
            self.assertTrue(u.startswith(shared), u[:200])

    def test_position_review_waits_for_its_market_to_open(self):
        now = time.time()
        self.t.acct.positions["NVDA"] = object()
        self.t.links["NVDA"] = {"review_at": now - 1}
        self.t.calls.update(last_ts=0.0, last_idle=now)
        self.assertIsNone(self.t.due(now, False, idle=False, quotes={"NVDA": {"open": False}}))
        self.assertEqual(self.t.due(now, False, idle=False, quotes={"NVDA": {"open": True}}), "position review")
        self.assertEqual(self.t.due(now, False, idle=False), "position review")      # no quotes: old behaviour
        del self.t.acct.positions["NVDA"]
        del self.t.links["NVDA"]

    def test_closed_market_headline_waits_for_the_briefing(self):
        self.t.calls["last_idle"] = time.time()
        with mock.patch("core.llm_trader.recent_news", return_value={"AAPL": {"title": "Apple wins deal", "source": "X",
                                                                             "lexicon": 0.4, "seen": "2026-11-24T03:00"}}):
            self.t.scan(self.market(AAPL=quote("AAPL", open_=False)))
            self.t.scan(self.market(AAPL=quote("AAPL", open_=False)))
        self.assertEqual(self.prompts, [])
        self.assertEqual([r["title"] for r in self.t.calls["overnight"]["AAPL"]], ["Apple wins deal"])

    def test_pre_open_briefing_runs_once_in_the_window(self):
        self.t.calls["last_idle"] = time.time()
        self.t.calls["overnight"] = {"AAPL": [{"title": "Apple wins deal"}]}
        self.replies.append(json.dumps({"note": "quiet night", "watchlist": [
            {"symbol": "AAPL", "bias": "long", "why": "deal"}, {"symbol": "NOT-A-SYMBOL", "bias": "long", "why": "x"}]}))
        with mock.patch("core.llm_trader.ny_time", return_value=(1, (9, 15), "2026-11-24")):
            self.t.scan(self.market())
            self.t.scan(self.market())
        self.assertEqual(len(self.prompts), 1)
        self.assertTrue(self.prompts[0].startswith("Overnight data (JSON):"))
        b = self.t.calls["briefing"]
        self.assertEqual([w["symbol"] for w in b["watchlist"]], ["AAPL"])
        self.assertEqual(self.t.calls["overnight"], {})
        self.assertIn("pre_open_briefing", self.log_kinds())

    def test_watchlist_starts_the_first_cycle_at_the_open(self):
        now = time.time()
        self.t.calls.update(last_idle=now, briefing={"date": "2026-11-24", "made_ts": now, "note": "n",
                                                     "watchlist": [{"symbol": "CCC", "bias": "long", "why": "deal"}]})
        with mock.patch("core.llm_trader.ny_time", return_value=(1, (9, 31), "2026-11-24")):
            self.t.scan(self.market(SPY=quote("SPY")))
            self.t.scan(self.market(SPY=quote("SPY")))
        self.assertEqual(len(self.prompts), 1)
        call = next(json.loads(l) for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines() if '"kind": "call"' in l)
        self.assertEqual(call["trigger"], "market open (pre-open watchlist)")
        self.assertTrue(call["context"]["candidates"][0]["why"].startswith("pre-open watchlist"))
        self.assertIn("pre_open_briefing", call["context"])

    def test_unchanged_scheduled_scan_is_skipped(self):
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        m = self.market(AAA=quote("AAA", px=100, move=3))
        self.t.scan(m)
        self.assertEqual(len(self.prompts), 1)
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market(AAA=quote("AAA", px=100.1, move=3.1)))
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("skip", self.log_kinds())
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market(AAA=quote("AAA", px=102, move=4)))
        self.assertEqual(len(self.prompts), 2)                    # 2% >= a quarter of the 5% stock threshold

    def test_held_top_mover_is_not_resent_until_it_moves_on(self):
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.reply({"symbol": "AAA", "action": "hold", "reason": "no edge"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=3)))
        self.assertIn("AAA", self.t.calls.get("held", {}))

        def last_cands():
            calls = [json.loads(l) for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines() if '"kind": "call"' in l]
            return [c["symbol"] for c in calls[-1]["context"]["candidates"]]
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market(AAA=quote("AAA", px=100.5, move=3.5), BBB=quote("BBB", px=103, move=3)))
        self.assertNotIn("AAA", last_cands())                     # held, moved 0.5% < 1.25%: not re-sent
        self.assertIn("BBB", last_cands())
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market(AAA=quote("AAA", px=102, move=5), BBB=quote("BBB", px=106, move=6)))
        self.assertIn("AAA", last_cands())                        # moved 2% since the hold: back in

    def test_desk_stats_group_outcomes_by_source_and_action(self):
        self.t.cands = ([{"symbol": "A", "why": "recent linked headline", "action": "buy", "out": {"86400": 0.02}}] * 3
                        + [{"symbol": "B", "why": "recent linked headline", "action": "short", "out": {"86400": 0.03}}] * 2
                        + [{"symbol": "C", "why": "new shock", "action": "hold", "out": {"3600": -0.01}}])
        st = self.t.desk_stats(min_n=1)
        self.assertEqual(st["news/buy/1d"], {"n": 3, "mean_pct": 2.0, "hit": 1.0})
        self.assertEqual(st["news/short/1d"]["mean_pct"], -3.0)       # the stock beat SPY: the short lost
        self.assertNotIn("shock/hold/1d", st)                           # no outcome yet
        self.assertEqual(st["shock/hold/1h"]["mean_pct"], -1.0)
        self.assertEqual(self.t.desk_stats(), {})                       # nothing reaches 5 outcomes

    def test_generic_words_need_market_context(self):
        m = lt._macro_symbols
        self.assertNotIn("PL=F", m("Platinum Equity agrees to buy Amex unit"))
        self.assertIn("PL=F", m("Platinum prices jump as supply tightens"))
        self.assertNotIn("GBPUSD=X", m("Champion wins pound for pound title"))
        self.assertIn("GBPUSD=X", m("Pound falls against the dollar after BoE"))
        self.assertIn("HG=F", m("Copper futures hit a record"))
        self.assertNotIn("HG=F", m("Copper Property CTL Pass Through Trust reports"))
        self.assertIn("GC=F", m("Spot gold climbs"))                   # specific phrases need no extra context
        self.assertIn("BTC-USD", m("Bitcoin slides below 60k"))

    def test_junk_and_irrelevant_headlines_are_dropped(self):
        self.assertTrue(lt.is_junk("How to Invest in VanEck Biotech ETF (BBH)"))
        self.assertTrue(lt.is_junk("$100 Invested In State Street Technology Select Sector SPDR ETF 20 Years Ago Would Be Worth This Much Today"))
        self.assertTrue(lt.is_junk("S&P 500 Movers: HPE, DLTR"))
        self.assertTrue(lt.is_junk("3 Stocks to Buy Before Black Friday"))
        self.assertFalse(lt.is_junk("Dollar Tree beats Q3 estimates and raises guidance"))
        self.assertFalse(lt.relevant("How biotech ETFs fared", "SMH", "VanEck Semiconductor ETF"))
        self.assertTrue(lt.relevant("Semiconductor stocks slide as AMD drops", "SMH", "VanEck Semiconductor ETF"))
        self.assertTrue(lt.relevant("DLTR shares jump", "DLTR", "Dollar Tree, Inc."))

    def test_similar_past_headlines_give_a_base_rate(self):
        import tempfile as _tf
        rows = [{"key": f"k{i}", "horizon": "1d", "symbol": f"S{i}", "abnormal": 0.02 if i % 2 else -0.01, "t0": i,
                 "title": f"Acme rival beats third quarter EPS estimates and raises guidance {i}", "source": "x", "sentiment": 0}
                for i in range(12)]
        rows.append({"key": "z", "horizon": "1d", "symbol": "Z", "abnormal": 0.5, "t0": 1,
                     "title": "Totally unrelated mining accident", "source": "x", "sentiment": 0})
        with _tf.TemporaryDirectory() as d:
            p = Path(d) / "labels.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in rows))
            with mock.patch.object(lt.news_archive, "LABELS", p):
                lt._LABELS.update(ts=0.0, rows=[], by_type={})
                sim = lt.similar_past("Widget Co beats third quarter EPS estimates, raises guidance", "WID")
        self.assertEqual(sim["n"], 8)
        self.assertEqual(sim["type_base_rate"]["n"], 12)                  # all 12 earnings rows; the mining row is "other"
        self.assertTrue(all("beats" in e["title"] for e in sim["examples"]))

    def test_news_type_classification(self):
        self.assertEqual(lt.news_type("Acme beats Q3 EPS, raises guidance"), "earnings")
        self.assertEqual(lt.news_type("Big Co agrees to acquire Small Co for $2B"), "m&a")
        self.assertEqual(lt.news_type("Analyst upgrades Acme to overweight"), "analyst")
        self.assertEqual(lt.news_type("FDA approves Acme drug"), "fda/clinical")
        self.assertEqual(lt.news_type("Something unusual happened"), "other")

    def test_headline_shows_move_since_the_desk_first_saw_it(self):
        heads = [{"title": "Acme beats Q3 EPS", "source": "X", "lexicon": 0.5, "ai_scores": {}, "seen": "", "key": "k1"}]
        with mock.patch.object(lt, "archive_headlines", return_value=[dict(h) for h in heads]):
            c1 = self.t.build_context(1000.0, [{"symbol": "AAA", "ratio": None, "why": "x"}], self.market(AAA=quote("AAA", px=100)), [])
        with mock.patch.object(lt, "archive_headlines", return_value=[dict(h) for h in heads]):
            c2 = self.t.build_context(1600.0, [{"symbol": "AAA", "ratio": None, "why": "x"}], self.market(AAA=quote("AAA", px=104)), [])
        h1, h2 = c1["candidates"][0]["headlines"][0], c2["candidates"][0]["headlines"][0]
        self.assertEqual((h1["move_since_desk_saw_pct"], h1["type"]), (0.0, "earnings"))
        self.assertEqual((h2["minutes_since_desk_saw"], h2["move_since_desk_saw_pct"]), (10, 4.0))
        self.assertNotIn("key", h2)
        self.assertEqual(c2["candidates"][0]["news_type"], "earnings")

    def test_scheduled_scan_needs_a_meaningful_mover(self):
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market())                                   # nothing moved: no call
        self.assertEqual(self.prompts, [])
        self.assertIn("skip", self.log_kinds())
        self.t.calls.update(last_idle=0.0, last_ts=0.0)
        self.t.scan(self.market(AAA=quote("AAA", move=3)))           # 3% >= half of the 5% stock threshold
        self.assertEqual(len(self.prompts), 1)

    def test_abnormal_is_only_for_us_stocks_while_spy_trades(self):
        self.t.context = {"SPY": quote("SPY", move=4.7, open_=False), "^VIX": quote("^VIX", px=20)}
        ctx = self.t.build_context(time.time(), [{"symbol": "AAA", "ratio": None, "why": "x"}],
                                   {"AAA": quote("AAA", move=3)}, [])
        self.assertIsNone(ctx["candidates"][0]["abnormal_pct"])

    def test_short_opens_a_short_with_the_stop_above_and_a_short_control(self):
        self.reply({"symbol": "AAA", "action": "short", "size_pct": 5, "leverage": 2, "stop_pct": 5, "target_pct": 10,
                    "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=-12)))
        p = self.t.acct.positions["AAA"]
        self.assertEqual(p.side, -1)
        self.assertGreater(p.sl, p.entry)
        self.assertLess(p.tp, p.entry)
        ctrl = next(iter(self.t.ctrl.positions.values()))
        self.assertEqual(ctrl.side, -1)
        self.assertGreater(ctrl.sl, ctrl.entry)
        view = self.t.view()["positions"][0]
        self.assertEqual(view["side"], "short")

    def test_buy_while_short_is_refused_until_sold(self):
        self.reply({"symbol": "AAA", "action": "short", "size_pct": 5, "stop_pct": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=-12)))
        out = self.t._buy({"symbol": "AAA", "size_pct": 5, "stop_pct": 5, "reason": "r"},
                          self.market(AAA=quote("AAA", px=100, move=-12)), time.time())
        self.assertEqual(out["status"], "skipped")
        self.assertIn("opposite", out["why"])

    def test_extended_hours_requote_only_the_focus_set(self):
        self.t.calls["overnight"] = {"AAPL": [{"title": "x"}]}
        quotes = {"AAPL": quote("AAPL", open_=False), "MSFT": quote("MSFT", open_=False)}
        ext = dict(quote("AAPL", px=110, move=10), session="pre")
        with mock.patch("core.llm_trader.ny_time", return_value=(1, (8, 0), "2026-11-24")), \
             mock.patch("core.llm_trader.data.quote_ext", return_value=ext) as qe:
            self.t._extended(quotes)
        qe.assert_called_once_with("AAPL")
        self.assertEqual(quotes["AAPL"]["session"], "pre")
        self.assertFalse(quotes["MSFT"]["open"])
        with mock.patch("core.llm_trader.ny_time", return_value=(1, (21, 0), "2026-11-24")), \
             mock.patch("core.llm_trader.data.quote_ext") as qe2:
            self.t._extended({"AAPL": quote("AAPL", open_=False)})
        qe2.assert_not_called()

    def test_sell_while_closed_is_queued_and_fills_at_the_open(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "stop_pct": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.assertIn("AAA", self.t.acct.positions)
        self.t.acct.on_quote(self.t._q(quote("AAA", px=100, open_=False)))
        out = self.t._sell("AAA", "model sell", time.time())
        self.assertEqual(out["status"], "queued for the open")
        self.assertIn("AAA", self.t.acct.positions)
        self.assertTrue(self.t.view()["positions"][0]["exit_queued"])
        self.t.calls.update(last_idle=time.time(), last_ts=time.time())
        self.t.scan(self.market(AAA=quote("AAA", px=101, move=1)))
        self.assertNotIn("AAA", self.t.acct.positions)
        self.assertIn("exit_queued", self.log_kinds())

    def test_missing_quote_does_not_start_a_review(self):
        now = time.time()
        self.t.acct.positions["NVDA"] = object()
        self.t.links["NVDA"] = {"review_at": now - 1}
        self.t.calls.update(last_ts=0.0, last_idle=now)
        self.assertIsNone(self.t.due(now, False, quotes={}))
        del self.t.acct.positions["NVDA"]
        del self.t.links["NVDA"]

    def test_no_briefing_call_without_overnight_input(self):
        self.t.calls.update(last_idle=time.time(), overnight={})
        with mock.patch("core.llm_trader.ny_time", return_value=(1, (9, 15), "2026-11-24")):
            self.t.scan(self.market())
        self.assertEqual(self.prompts, [])

    def test_all_analysts_failing_stops_the_cycle(self):
        real = self.t.chat
        calls = []
        def chat(s, u):
            calls.append(s)
            return ("", "rate limited") if s in (lt.ANALYST_NEWS, lt.ANALYST_PRICE, lt.ANALYST_MACRO) else real(s, u)
        self.t.chat = chat
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertEqual(len(calls), 3)                          # only the three analysts
        self.assertEqual(self.t.last_error, "rate limited")

    def test_short_target_is_capped_below_100(self):
        self.reply({"symbol": "AAA", "action": "short", "size_pct": 5, "stop_pct": 5, "target_pct": 150, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=-12)))
        self.assertGreater(self.t.acct.positions["AAA"].tp, 0)

    def test_preflight_refuses_a_closed_market_buy_before_risk_review(self):
        self.reply({"symbol": "BBB", "action": "buy", "size_pct": 5, "stop_pct": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12), BBB=quote("BBB", open_=False)))
        self.assertNotIn("BBB", self.t.acct.positions)
        self.assertFalse(any("BBB" in u for u in self.risk_calls))
        d = next(x for x in self.t.decisions if x["symbol"] == "BBB")
        self.assertEqual(d["executed"]["why"], "market closed or stale quote")

    def test_a_headline_is_used_once_and_a_new_one_still_counts(self):
        h1 = {"BBB": {"title": "BBB wins contract", "source": "X", "lexicon": 0.4, "seen": "t"}}
        h2 = {"BBB": {"title": "BBB raises guidance", "source": "X", "lexicon": 0.4, "seen": "t"}}
        self.t.calls["last_idle"] = time.time()
        with mock.patch("core.llm_trader.recent_news", return_value=h1):
            self.t.scan(self.market())
            self.t.calls["last_ts"] = 0
            self.t.scan(self.market())
        self.assertEqual(len(self.prompts), 1)
        self.t.calls["last_ts"] = 0
        with mock.patch("core.llm_trader.recent_news", return_value=h2):
            self.t.scan(self.market())
        self.assertEqual(len(self.prompts), 2)

    def test_tail_lines_skips_a_cut_first_line(self):
        p = Path(self.tmp.name) / "big.jsonl"
        p.write_text("".join(json.dumps({"i": i}) + "\n" for i in range(1000)))
        rows = lt._loads_ok(lt.tail_lines(p, 50, max_bytes=500))
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["i"], 999)

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


class WholeMarket(Base):
    def test_class_specific_shock_thresholds_and_no_volume_requirement_outside_stocks(self):
        now = time.time()
        for sym, pct in (("EURUSD=X", 1.2), ("GC=F", 2.2), ("BTC-USD", 5.2)):
            q = quote(sym, px=100, move=pct)
            q["volume"] = None
            self.assertEqual(self.t.shock(q, now), 1.0, sym)
            q = quote(sym, px=100, move=pct - 0.3)
            q["volume"] = None
            self.assertIsNone(self.t.shock(q, now), sym)
        self.assertEqual(self.t.shock(quote("AAA", px=100, move=5.5, vol=1e5), now), None)   # stock volume still matters

    def test_control_is_drawn_from_the_same_asset_class(self):
        self.reply({"symbol": "GC=F", "action": "buy", "size_pct": 5, "leverage": 2, "stop_pct": 5,
                    "review_in_min": 60, "reason": "gold breakout"})
        m = self.market(**{"GC=F": quote("GC=F", px=2000, move=3), "SI=F": quote("SI=F", px=30)})
        self.t.scan(m)
        self.assertIn("GC=F", self.t.acct.positions)
        ctrl = next(iter(self.t.ctrl.positions))
        self.assertEqual(lt.asset_class(ctrl), "commodity")
        self.assertNotEqual(ctrl, "GC=F")

    def test_scheduled_scan_calls_the_model_for_a_mover_below_the_shock_threshold(self):
        self.t.calls["last_idle"] = 0
        self.t.scan(self.market(AAA=quote("AAA", move=3)))          # 3%: under the 5% shock, over half of it
        self.assertEqual(len(self.prompts), 1)
        call = next(json.loads(l) for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines() if '"kind": "call"' in l)
        self.assertEqual(call["trigger"], "scheduled scan")
        ctx = call["context"]
        self.assertEqual(ctx["protocol"], lt.PROTOCOL_VERSION)
        self.assertEqual(ctx["universe_classes"]["crypto"], len(lt.ASSETS["crypto"]))
        self.assertTrue(ctx["movers"])
        self.assertIn("gold", ctx["market"])

    def test_recent_news_is_a_candidate_and_triggers_a_call(self):
        self.t.calls["last_idle"] = time.time()
        with mock.patch("core.llm_trader.recent_news", return_value={"BBB": {"title": "BBB wins contract", "source": "X",
                                                                            "lexicon": 0.4, "seen": "2026-11-24T01:00"}}):
            self.t.scan(self.market())
        self.assertEqual(len(self.prompts), 1)
        call = next(json.loads(l) for l in (Path(self.tmp.name) / "l.jsonl").read_text().splitlines() if '"kind": "call"' in l)
        self.assertEqual(call["trigger"], "new signals")
        cand = next(c for c in call["context"]["candidates"] if c["symbol"] == "BBB")
        self.assertEqual(cand["why"], "recent linked headline")

    def test_macro_headline_words_map_to_tradable_symbols(self):
        self.assertIn("GC=F", lt._macro_symbols("Gold hits a record as the dollar falls"))
        self.assertIn("CL=F", lt._macro_symbols("OPEC cuts oil output"))
        self.assertIn("BTC-USD", lt._macro_symbols("Bitcoin ETF inflows surge"))
        self.assertNotIn("GC=F", lt._macro_symbols("A gold medal for the swimmer"))

    def test_view_reports_the_universe_and_protocol(self):
        v = self.t.view()
        self.assertEqual(v["protocol"], lt.PROTOCOL_VERSION)
        self.assertEqual(v["universe_size"], len(lt.ALL))
        self.assertEqual(v["classes"]["fx"], len(lt.ASSETS["fx"]))
        self.t.pairs = [{"id": "1", "asset_class": "commodity", "s1": 0.02, "ctrl": 0.0},
                        {"id": "2", "asset_class": "stock", "s1": -0.01, "ctrl": 0.0}]
        self.assertEqual(self.t.evaluate()["by_class"]["commodity"]["n"], 1)


class HeavyDesk(Base):
    def test_risk_manager_can_veto_or_reduce_but_never_increase_size(self):
        self.risk_replies.append(json.dumps({"reviews": [{"symbol": "AAA", "approve": False,
                                                          "size_multiplier": 1, "reason": "too concentrated"}]}))
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertNotIn("AAA", self.t.acct.positions)
        self.assertIn("risk_veto", self.log_kinds())
        self.risk_replies.append(json.dumps({"reviews": [{"symbol": "AAA", "approve": True,
                                                          "size_multiplier": 0.5, "reason": "halve it"}]}))
        self.t.calls["last_ts"] = 0
        self.t.seen.clear()
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 10, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        self.assertEqual(self.t.decisions[-1]["size_pct"], 5)
        self.assertEqual(self.t.decisions[-1]["size_pct_before_risk"], 10)
        self.assertIn("risk_reduce", self.log_kinds())

    def test_risk_parser_never_accepts_an_increase(self):
        out = lt.parse_reviews('{"reviews":[{"symbol":"AAA","size_multiplier":9,"approve":true}]}', {"AAA"})
        self.assertEqual(out["AAA"]["size_multiplier"], 1.0)
        self.assertEqual(lt.parse_reviews("no json", {"AAA"}), {})

    def test_analyst_notes_are_in_the_decision_context(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", move=12)))
        ctx = json.loads(self.prompts[0].split("JSON):\n", 1)[1])
        self.assertEqual(ctx["analysts"]["news"]["AAA"], "note for AAA")
        self.assertEqual(len(self.analyst_calls), 3)


class Pairing(Base):
    def buy_then_close(self, legacy=False, skew=30.0):
        """Buy AAA, pretend the fill used a quote older than the decision, then close both legs."""
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        link = self.t.links["AAA"]
        for acct in (self.t.acct, self.t.ctrl):
            for p in acct.positions.values():
                p.opened_ts = link["ts"] - skew
                if legacy:
                    p.ref = None
        self.t.calls["last_ts"] = 0
        link["review_at"] = 0
        self.reply({"symbol": "AAA", "action": "sell", "reason": "exit"})
        m = self.market(AAA=quote("AAA", px=112, move=14))
        m[link["ctrl"]] = quote(link["ctrl"], px=101)
        self.t.scan(m)
        self.t.scan(m)
        return link

    def test_market_buy_fills_on_the_quote_the_model_was_shown_not_a_stale_account_quote(self):
        old = time.time() - 86400
        self.t.acct.on_quote(lt.Quote("AAA", 49.0, 49.1, old))
        for s in ("BBB", "CCC", "DDD", "EEE"):
            self.t.ctrl.on_quote(lt.Quote(s, 50.0, 50.1, old))
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        p = self.t.acct.positions["AAA"]
        self.assertAlmostEqual(p.entry, 110.02 * 1.0002, delta=0.02)     # today's ask (plus slippage), not the day-old 49.1
        cp = next(iter(self.t.ctrl.positions.values()))
        self.assertGreater(cp.entry, 99.0)                              # the control also fills on the fresh quote
        self.assertEqual(p.ref, self.t.links["AAA"]["id"])

    def test_pair_is_booked_by_reference_even_when_the_fill_timestamp_is_older_than_the_decision(self):
        link = self.buy_then_close(skew=30)
        self.assertEqual(len(self.t.pairs), 1, "a stale quote timestamp must not lose the pair")
        model, control = self.t.acct.trades[-1], self.t.ctrl.trades[-1]
        self.assertEqual(model.ref, link["id"])
        self.assertEqual(control.ref, link["id"])

    def test_legacy_control_opened_on_a_very_old_quote_pairs_by_its_close_time(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        link = self.t.links["AAA"]
        self.t.acct.positions["AAA"].opened_ts = link["ts"] - 30
        self.t.acct.positions["AAA"].ref = None
        cp = next(iter(self.t.ctrl.positions.values()))
        cp.opened_ts = link["ts"] - 3 * 86400        # stale quote the control account still had
        cp.ref = None
        self.t.calls["last_ts"] = 0
        link["review_at"] = 0
        self.reply({"symbol": "AAA", "action": "sell", "reason": "exit"})
        m = self.market(AAA=quote("AAA", px=112, move=14))
        m[link["ctrl"]] = quote(link["ctrl"], px=101)
        self.t.scan(m)
        self.t.scan(m)
        self.assertEqual(len(self.t.pairs), 1)

    def test_a_link_saved_before_references_existed_still_pairs_without_the_five_second_window(self):
        self.buy_then_close(legacy=True, skew=30)
        self.assertEqual(len(self.t.pairs), 1)
        self.assertIsNone(self.t.acct.trades[-1].ref)

    def test_references_and_links_survive_a_state_round_trip(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        self.t.save()
        again = lt.LlmTrader(self.t.state_path, self.t.log_path, chat=self.t.chat)
        self.assertEqual(again.acct.positions["AAA"].ref, again.links["AAA"]["id"])
        self.assertEqual(next(p.ref for p in again.ctrl.positions.values()), again.links["AAA"]["id"])

    def test_concurrent_state_saves_leave_one_complete_file_and_no_temp_files(self):
        from concurrent.futures import ThreadPoolExecutor

        def writer(i):
            for n in range(40):
                write_json_atomic(self.t.state_path, {"writer": i, "n": n, "pad": "x" * 2000})

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(writer, range(8)))
        doc = json.loads(self.t.state_path.read_text())
        self.assertIn("writer", doc)
        self.assertEqual(list(self.t.state_path.parent.glob("*.tmp")), [])

    def test_missing_control_trade_is_reported_once_instead_of_vanishing(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        link = self.t.links["AAA"]
        self.t.acct.close("AAA", reason="manual")
        self.t.ctrl.positions.clear()               # simulate a control order that never produced a trade
        self.t.ctrl.trades = []
        for _ in range(3):
            self.t.scan(self.market(AAA=quote("AAA", px=110)))
        self.assertEqual(self.log_kinds().count("pair_waiting"), 1)
        self.assertEqual(self.t.pairs, [])


class LimitOrderStatus(Base):
    def pending_buy(self, limit=98):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "entry": "limit", "limit_price": limit, "valid_min": 30,
                    "stop_pct": 6, "review_in_min": 60, "reason": "buy the dip"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        return self.t.pending["AAA"]

    def test_pending_scale_in_does_not_open_a_control_before_it_fills(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "stop_pct": 6, "review_in_min": 60, "reason": "first"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        link_id = self.t.links["AAA"]["id"]
        ctrl_before = set(self.t.ctrl.positions)
        self.t.calls["last_ts"] = 0
        self.t.seen.clear()
        self.pending_buy()
        self.assertIn("AAA", self.t.pending)
        self.assertEqual(set(self.t.ctrl.positions), ctrl_before)      # no second control for an unfilled add-on
        self.assertEqual(self.t.links["AAA"]["id"], link_id)
        self.assertNotIn("limit_filled", self.log_kinds())
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertIn("AAA", self.t.pending)
        self.assertEqual(set(self.t.ctrl.positions), ctrl_before)

    def test_a_price_after_the_validity_window_does_not_fill(self):
        meta = self.pending_buy()
        meta["expires"] = time.time() - 1
        self.t.scan(self.market(AAA=quote("AAA", px=97.5)))            # through the limit, but too late
        self.assertNotIn("AAA", self.t.acct.positions)
        self.assertNotIn("AAA", self.t.pending)
        self.assertIn("limit_expired", self.log_kinds())
        self.assertNotIn("limit_filled", self.log_kinds())

    def test_a_rejected_limit_order_is_logged_and_cleared(self):
        meta = self.pending_buy()
        order = next(o for o in self.t.acct.orders if o.id == meta["order_id"])
        order.status = "rejected"
        self.t.scan(self.market(AAA=quote("AAA", px=100)))
        self.assertNotIn("AAA", self.t.pending)
        self.assertIn("limit_rejected", self.log_kinds())

    def test_log_api_attaches_the_fill_to_the_cycle_that_placed_the_order(self):
        meta = self.pending_buy()
        self.t.scan(self.market(AAA=quote("AAA", px=97.5)))
        cycles = lt.build_cycles(lt.read_log_tail(self.t.log_path))["cycles"]
        events = [a for c in cycles for a in c["actions"] if a["kind"] == "limit_filled"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["order_id"], meta["order_id"])


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

    def test_each_position_uses_the_leverage_the_model_chose_for_margin(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 1, "stop_pct": 6, "review_in_min": 60, "reason": "low lev"},
                   {"symbol": "BBB", "action": "buy", "size_pct": 5, "leverage": 20, "stop_pct": 6, "review_in_min": 60, "reason": "high lev"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12), BBB=quote("BBB", px=50, move=9)))
        a, b = self.t.acct.positions["AAA"], self.t.acct.positions["BBB"]
        self.assertEqual((a.leverage, b.leverage), (1.0, 20.0))
        expected = a.qty * a.entry + b.qty * b.entry / 20
        self.assertAlmostEqual(self.t.acct.used_margin(), expected, delta=0.05)
        margins = {p["symbol"]: p["margin_usd"] for p in self.t.view()["positions"]}
        self.assertAlmostEqual(margins["AAA"], a.qty * a.entry, delta=0.1)
        self.assertAlmostEqual(margins["BBB"], b.qty * b.entry / 20, delta=0.1)

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

    def test_limit_entry_saved_before_references_still_activates(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 3, "entry": "limit", "limit_price": 98, "valid_min": 30,
                    "stop_pct": 6, "review_in_min": 60, "reason": "buy the dip"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.t.pending["AAA"].pop("link_id")                     # state written by the previous version
        for o in self.t.acct.orders:
            o.ref = None
        self.t.scan(self.market(AAA=quote("AAA", px=97.5)))
        self.assertIn("AAA", self.t.acct.positions)
        self.assertIn("AAA", self.t.links)
        self.assertEqual(len(self.t.ctrl.positions), 1)

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
        self.assertAlmostEqual(self.t.acct.positions["AAA"].financing, expected, delta=expected * 0.05)
        self.assertIn("financing", self.log_kinds())

    def test_pair_returns_include_financing_and_reconcile_with_the_balance(self):
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 5, "leverage": 5, "stop_pct": 30, "review_in_min": 60, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=100, move=12)))
        self.t.last_fin = time.time() - 6 * 3600
        self.t._charge_financing(time.time())
        self.assertGreater(self.t.acct.positions["AAA"].financing, 0)
        self.t.calls["last_ts"] = 0
        self.t.links["AAA"]["review_at"] = 0
        self.reply({"symbol": "AAA", "action": "sell", "reason": "exit"})
        m = self.market(AAA=quote("AAA", px=101, move=2))
        m[self.t.links["AAA"]["ctrl"]] = quote(self.t.links["AAA"]["ctrl"], px=99)
        self.t.scan(m)
        self.t.scan(m)
        self.assertEqual(len(self.t.pairs), 1)
        self.assertAlmostEqual(self.t.acct.balance, self.t.acct.initial + sum(t.pnl for t in self.t.acct.trades), places=6)
        last = self.t.acct.trades[-1]
        self.assertAlmostEqual(self.t.pairs[0]["s1"], last.pnl / (last.qty * last.entry), places=9)

    def test_a_rejected_control_order_is_logged(self):
        self.t.ctrl.balance = 0
        self.reply({"symbol": "AAA", "action": "buy", "size_pct": 4, "reason": "r"})
        self.t.scan(self.market(AAA=quote("AAA", px=110, move=12)))
        self.assertIn("control_rejected", self.log_kinds())

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
        self.assertLessEqual(lt.SCAN_S, 15)
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
