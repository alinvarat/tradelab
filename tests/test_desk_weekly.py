"""Offline tests for the weekly review, the outcome publisher and their wiring (pure; fake transport, no network)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from core import desk_publish as dp
from core import desk_rules as dr
from core import desk_weekly as dw
from research.llm_trader import weekly

ROOT = Path(__file__).resolve().parent.parent
D0 = 1_795_000_000.0       # a UTC day start is not needed: rows are spread over distinct days by 86400 steps


def row(i, abn, action="hold", src="news", nt="analyst", h=86400, day=None, **kw):
    r = {"v": 2, "protocol": dr.TAG, "ts": D0 + (i if day is None else day) * 86400 + 3600, "symbol": f"S{i}", "cls": "stock", "src": src,
         "news_type": nt, "action": action, "h": h, "abn": abn, "veto": None, "forced": False, "em": None, "rv": None, "stale": []}
    r.update(kw)
    return r


class Review(unittest.TestCase):
    def test_tag_and_next_tag(self):
        self.assertEqual(dw.next_tag("v4.19"), "v4.20")
        p = dw.propose([])
        self.assertEqual((p["current_tag"], p["next_tag"]), (dr.TAG, dw.next_tag(dr.TAG)))
        self.assertEqual(p["changes"], [])
        self.assertIn("no change proposed", p["note"])

    def test_overlapping_candidates_collapse_to_one_per_symbol_day(self):
        rows = [row(0, -0.05, symbol="X", ts=D0 + 100), row(0, -0.05, symbol="X", ts=D0 + 5000), row(1, -0.05, symbol="X", day=1)]
        self.assertEqual(len(dw.collapse(rows)), 2)

    def test_duplicate_uploaded_rows_do_not_double_count(self):
        line = json.dumps(row(0, -0.02))
        self.assertEqual(len(dw.load_rows([line, line, "", "{bad", json.dumps({"abn": None, "ts": 1})])), 1)

    def test_negative_long_cell_with_enough_clusters_proposes_a_veto_with_evidence(self):
        rows = [row(i, -0.04, day=i % 8) for i in range(40)]            # 40 distinct symbols on 8 days, analyst hold 1d -4%
        p = dw.propose(rows)
        ids = [c["id"] for c in p["changes"]]
        self.assertIn("veto:type:analyst/hold/1d", ids)
        ev = next(c for c in p["changes"] if c["id"] == "veto:type:analyst/hold/1d")["evidence"]
        self.assertEqual((ev["clusters"], ev["days"], ev["mean_pct"]), (40, 8, -4.0))
        self.assertAlmostEqual(ev["shrunk_pct"], -4.0 * 40 / 60, places=2)

    def test_thin_or_short_evidence_proposes_nothing(self):
        self.assertEqual(dw.propose([row(i, -0.04, day=i % 8) for i in range(13)])["changes"], [])     # n=13 is below the floor
        self.assertEqual(dw.propose([row(i, -0.04, day=i % 3) for i in range(60)])["changes"], [])     # three days only

    def test_shorts_are_never_proposed_as_a_new_or_bigger_position(self):
        rows = [row(i, -0.05, action="short", src="mover", nt=None, day=i % 8) for i in range(60)]     # shorts earned +5%
        p = dw.propose(rows)
        self.assertGreater(p["cells"]["mover/short/1d"]["mean_pct"], 4)
        self.assertEqual(p["changes"], [])                                # evidence for shorts proposes nothing
        for c in dw.propose([row(i, -0.04, day=i % 8) for i in range(40)])["changes"]:
            self.assertIn(c["kind"], ("veto", "relax"))

    def test_a_rule_that_cost_money_is_proposed_for_relaxing(self):
        rows = [row(i, 0.03, action="buy", veto="R2", day=i % 8) for i in range(40)]       # vetoed longs would have earned +3%
        p = dw.propose(rows)
        self.assertTrue(any(c["id"] == "relax:R2/1d" for c in p["changes"]))
        saved = dw.propose([row(i, -0.03, action="buy", veto="R2", day=i % 8) for i in range(40)])
        self.assertFalse([c for c in saved["changes"] if c["kind"] == "relax"])   # a rule that saved money stays
        self.assertLess(saved["rule_scores"]["R2/1d"]["shrunk_pct"], 0)

    def test_input_scores_split_by_presence_and_stale_share(self):
        rows = [row(i, 0.01, action="short", forced=(i % 2 == 0), em=(3.0 if i % 2 else None), stale=(["sec_8k"] if i % 4 == 0 else []),
                    h=3600, day=i) for i in range(8)]
        p = dw.propose(rows)
        self.assertEqual(p["input_scores"]["forced_flow=present/1h"]["clusters"], 4)
        self.assertEqual(p["input_scores"]["stated_expected_move=absent/1h"]["clusters"], 4)
        self.assertEqual(p["stale_share"], {"sec_8k": 0.25})

    def test_feed_quality_reports_latency_and_silent_days(self):
        ing = [{"event": "item", "source": "eqn_rest", "t_seen": D0 + i, "lat_s": 4.0 + i, "res": "s"} for i in range(5)] + \
              [{"event": "item", "source": "sec_8k", "t_seen": D0, "lat_s": 90.0, "res": "m"}]
        q = dw.feed_quality(ing, 7)
        self.assertEqual((q["eqn_rest"]["items"], q["eqn_rest"]["median_s"], q["eqn_rest"]["silent_days"]), (5, 6.0, 6))
        self.assertIsNone(q["sec_8k"]["median_s"])                          # minute-resolution rows stay out of latency

    def test_report_lists_every_change_with_its_evidence(self):
        p = dw.propose([row(i, -0.04, day=i % 8) for i in range(40)])
        md = dw.render_md(p, "2026-12-06")
        self.assertIn("veto:type:analyst/hold/1d", md)
        self.assertIn('"clusters": 40', md)
        self.assertIn("changes nothing", md)

    def test_runner_writes_report_and_proposal_for_the_current_tag_only(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "desk" / "desk_outcomes" / "20261201").mkdir(parents=True)
            rows = [row(i, -0.04, day=i % 8) for i in range(40)] + [row(99, 0.5, protocol="v4.18"), row(98, 0.5, v=1), row(97, 0.5, protocol="pre-v4.19")]
            (t / "desk" / "desk_outcomes" / "20261201" / "0-1.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            (t / "ing" / "news_ingest" / "20261201").mkdir(parents=True)
            now = time.time()
            (t / "ing" / "news_ingest" / "20261201" / "0-1.jsonl").write_text(
                json.dumps({"event": "item", "source": "eqn_rest", "t_seen": now - 60, "lat_s": 4.0, "res": "s"}) + "\n")
            p = weekly.run(t / "desk", t / "ing", t / "out", "2026-12-06", now=now)
            self.assertEqual(p["window"]["rows"], 40)                       # v4.18, pre-v4.19 and version-1 (mislabelled) rows are not v4.19 evidence
            self.assertTrue((t / "out" / "20261206_review.md").exists())
            self.assertEqual(json.loads((t / "out" / "20261206_proposal.json").read_text())["current_tag"], dr.TAG)


class Fake:
    def __init__(self):
        self.calls, self.files, self.branch = [], {}, False

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url))
        if "/git/ref/heads/" in url:
            return (200, b"{}", {}) if self.branch else (404, b"{}", {})
        if url.endswith("/git/trees"):
            return 201, b'{"sha":"t"}', {}
        if url.endswith("/git/commits"):
            return 201, b'{"sha":"c"}', {}
        if url.endswith("/git/refs"):
            self.branch = True
            return 201, b"{}", {}
        if method == "PUT":
            self.files[url.split("/contents/")[1]] = body
            return 201, b"{}", {}
        return 500, b"", {}


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_no_token_is_a_noop(self):
        (self.d / "20261201.jsonl").write_text('{"a":1}\n')
        fake = Fake()
        r = dp.cycle(self.d, fake, env={})
        self.assertEqual((r["enabled"], r["ok"], r["parts"], fake.calls), (False, True, 0, []))

    def test_publishes_whole_lines_to_the_bot_desk_branch_once(self):
        (self.d / "20261201.jsonl").write_text('{"a":1}\n{"a":2}\n{"par')
        fake = Fake()
        env = {"TRADELAB_DATA_PUSH_TOKEN": "SECRET"}
        r = dp.cycle(self.d, fake, env=env, sleep=lambda s: None)
        self.assertEqual((r["ok"], r["parts"]), (True, 1))
        path = next(iter(fake.files))
        self.assertTrue(path.startswith("desk_outcomes/20261201/"), path)
        self.assertEqual(dp.cycle(self.d, fake, env=env, sleep=lambda s: None)["parts"], 0)     # the cursor stops a re-upload
        self.assertNotIn("SECRET", json.dumps(dp.view()))

    def test_part_path_layout_matches_the_weekly_reader(self):
        self.assertEqual(dp.part_path("20261201", 0, 10), "desk_outcomes/20261201/0000000000-0000000010.jsonl")


class Wiring(unittest.TestCase):
    def test_keeper_dispatches_the_weekly_review_on_sunday(self):
        k = (ROOT / ".github" / "workflows" / "keeper.yml").read_text()
        self.assertIn("bot_weekly.yml", k)
        self.assertIn('"$h:$m" = "04:00"', k)

    def test_workflow_opens_a_pr_but_never_merges(self):
        w = (ROOT / ".github" / "workflows" / "bot_weekly.yml").read_text()
        for s in ("data/bot-desk", "data/news-ingest", "research/llm_trader/weekly.py", "gh pr create", "gh issue create", "workflow_dispatch"):
            self.assertIn(s, w)
        self.assertNotIn("gh pr merge", w)
        self.assertNotIn("--auto", w)
        self.assertNotIn("push:", w)
        self.assertNotIn("\t", w)

    def test_server_starts_the_publisher_and_the_trader_view_shows_it(self):
        self.assertIn("desk_publish.loop", (ROOT / "server.py").read_text())
        self.assertIn("outcome_publish", (ROOT / "core" / "llm_trader.py").read_text())


if __name__ == "__main__":
    unittest.main()
