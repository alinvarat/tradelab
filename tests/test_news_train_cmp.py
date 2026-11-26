"""Offline tests for the Sonnet-vs-Haiku comparison (research/news_train/protocol_cmp_20261126.md). Synthetic data only, no network, no model call."""
import hashlib
import json
import unittest
from pathlib import Path

from core import ai_news
from research.news_train import logic as L
from research.news_train import logic_cmp as C
from research.news_train import logic_r2 as R
from research.news_train import run_cmp as X

ROOT = Path(__file__).resolve().parents[1]
NT = ROOT / "research" / "news_train"
P = C.load_params()
P2 = R.load_params()


class Lock(unittest.TestCase):
    def test_protocol_hash_and_params(self):
        f = NT / "protocol_cmp_20261126.md"
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), f.with_suffix(".sha256").read_text().strip())
        self.assertIn(hashlib.sha256((NT / "params_cmp.json").read_bytes()).hexdigest(), f.read_text())

    def test_models_and_registry(self):
        self.assertEqual(P["models"], {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"})
        for s in X.SETS:
            X.version_of(s)                                   # prompt sha256 equals the locked registry
        self.assertEqual(ai_news.CLAUDE_MODEL, "claude-haiku-5-5")   # core default untouched

    def test_workflow_structure(self):
        t = (ROOT / ".github" / "workflows" / "news_train_cmp.yml").read_text()
        self.assertNotIn("\t", t)
        for j in ("  leak:", "  hist_prep:", "  hist_call:", "  hist_merge:", "  fwd:"):
            self.assertIn(j, t)
        self.assertIn("claude-sonnet-5-5", t)
        self.assertIn("workflow_dispatch:", t)
        self.assertNotIn("pull_request", t)


class Gate(unittest.TestCase):
    def table(self, last_known):
        out = []
        for m in ("2025-10", "2025-11", "2025-12", "2026-06", "2026-07"):
            known = m <= last_known
            out.append({"asset": "^GSPC", "month": m, "answered": 6 if known else 0, "acc_answered": 0.8 if known else None})
        return out

    def test_cutoff_rule_matches_round1_haiku(self):
        self.assertEqual(C.leak_cutoff(self.table("2025-11"), P["leak_rule"]), "2025-11")
        self.assertEqual(C.leak_cutoff(self.table("2026-06"), P["leak_rule"]), "2026-06")
        self.assertIsNone(C.leak_cutoff([{"month": "2025-01", "answered": 3, "acc_answered": 1.0}], P["leak_rule"]))
        self.assertIsNone(C.leak_cutoff([{"month": "2025-01", "answered": 9, "acc_answered": 0.5}], P["leak_rule"]))

    def test_eligibility(self):
        self.assertEqual(C.first_eligible_day("2026-06"), "2026-07-01")
        self.assertEqual(C.first_eligible_day("2025-12"), "2026-01-01")
        self.assertTrue(C.eligible(L.day_ts("2026-07-01"), "2026-06"))
        self.assertFalse(C.eligible(L.day_ts("2026-06-30"), "2026-06"))
        self.assertTrue(C.eligible(L.day_ts("2020-01-01"), None))
        self.assertEqual(C.combined_cutoff("2025-11", "2026-06"), "2026-06")


class Stats(unittest.TestCase):
    def test_sign_test(self):
        self.assertEqual(C.sign_test([1, 1, 1, 1, 1])["p"], 2 * 1 / 32)
        s = C.sign_test([1, -1, 0, 0])
        self.assertEqual((s["n_nonzero"], s["ties"], s["p"]), (2, 2, 1.0))
        self.assertIsNone(C.sign_test([0, 0])["p"])

    def test_paired_summary_detects_shift(self):
        diffs = [0.01 + 0.001 * (i % 3) for i in range(300)]
        days = [f"d{i // 10}" for i in range(300)]
        r = C.paired_summary(diffs, days, 300, 1)
        self.assertGreater(r["lo"], 0)
        self.assertLess(r["sign"]["p"], 0.001)
        z = C.paired_summary([0.01, -0.01] * 100, [f"d{i // 4}" for i in range(200)], 300, 1)
        self.assertLess(abs(z["mean_diff"]), 1e-9)

    def test_pair_direction_own_entry_and_discordance(self):
        items = {"a": {"day": "d1"}, "b": {"day": "d1"}, "c": {"day": "d2"}}
        long_ = {"ok": True, "d": {"1h": "long"}, "exp": {"1h": 1.0}}
        none = {"ok": True, "d": {"1h": "none"}, "exp": {"1h": 0.0}}
        dh = {"a": long_, "b": none, "c": long_}
        ds = {"a": long_, "b": long_, "c": {"ok": False}}
        # Sonnet enters later: a smaller gross on item a; item c has no Sonnet reply and is excluded
        lh = {k: {"gross": {"1h": 0.02}} for k in items}
        ls = {k: {"gross": {"1h": 0.01}} for k in items}
        rows = C.pair_direction(items, dh, ds, lh, ls, "crypto", "1h", {"1h": 0}, True, P2)
        self.assertEqual([r["key"] for r in rows], ["a", "b"])
        self.assertLess(rows[0]["d"], 0)                       # later entry earns less
        self.assertEqual(rows[1]["a"], 0.0)                    # Haiku abstained
        self.assertEqual(C.discordant(rows), 1)

    def test_project_and_fire(self):
        p = C.project(50, 300, 0, 5 * 86400)
        self.assertEqual(p["rate_per_day"], 10.0)
        self.assertEqual(p["days_left"], 25.0)
        self.assertIsNone(C.project(0, 300, 0, 100))
        now = L.day_ts("2026-12-01")
        self.assertEqual(C.fire_reason(300, 100, now, P), "min_n")
        self.assertIsNone(C.fire_reason(299, 100, now, P))
        self.assertIsNone(C.fire_reason(300, 99, now, P))
        self.assertEqual(C.fire_reason(1, 0, L.day_ts("2027-03-31"), P), "hard_stop_underpowered")

    def test_latency(self):
        s = C.latency_stats([1, 2, 3, 4, 10])
        self.assertEqual((s["n"], s["median_s"]), (5, 3))
        self.assertEqual(C.latency_stats([None]), {"n": 0})


class Forward(unittest.TestCase):
    def test_pre_label_has_no_outcome(self):
        t = 1_800_000_000
        bars = [(t - 7200 + 60 * i, 1.0, 1.0, 100.0 + i * 0.01) for i in range(130)]
        lab = C.crypto_pre_label(bars, t, P2)
        self.assertIsNotNone(lab)
        self.assertEqual(lab["gross"], {})
        self.assertIsNotNone(lab["pre_1h"])
        self.assertIsNone(C.crypto_pre_label([], t, P2))

    def test_item_redacts_and_keys(self):
        it = C.title_to_item("eqn_rest", "k1", "Bitcoin jumps 5% on 2026-11-28", 1_800_000_000, "BTC", P2)
        self.assertNotIn("itcoin", it["text"])
        self.assertEqual(it["key"], "ing:eqn_rest:k1")

    def test_candidates_dedupe_and_start(self):
        start = L.day_ts("2026-11-27")
        j = {("eqn_rest", "1"): {"t_seen": start + 10, "title": "Bitcoin ETF sees record crypto inflows today"},
             ("eqn_rest", "2"): {"t_seen": start + 20, "title": "Bitcoin ETF sees record crypto inflows today"},
             ("eqn_rest", "3"): {"t_seen": start - 5, "title": "Ethereum crypto network upgrade goes live this week"},
             ("sec_8k", "4"): {"t_seen": start + 30, "title": "Bitcoin crypto treasury 8-K filing disclosed here"}}
        c = X.fwd_crypto_candidates(j, start)
        self.assertEqual([x["url"] for x in c], ["1"])

    def test_decide_once_and_prompt_identity(self):
        calls = []

        def fake(mk, jobs, parse, **kw):
            calls.append((mk, [j["user_sha"] for j in jobs]))
            return [{"key": j["key"], "ok": True, "model": mk, "lat_s": 1.0 if mk == "haiku" else 3.0, "d": {}, "user_sha": j["user_sha"]} for j in jobs], False, {}
        decs = {}
        todo = {"w1": [("k1", "same prompt")]}
        X.decide_heads(todo, decs, {"w1": "sys"}, {"w1": None}, fake)
        self.assertEqual(calls[0][1], calls[1][1])             # both models got identical bytes
        n = len(calls)
        X.decide_heads(todo, decs, {"w1": "sys"}, {"w1": None}, fake)
        self.assertEqual(len(calls), n)                        # an answered item is never called again
        self.assertEqual(decs[("sonnet", "w1", "k1")]["attempts"], 1)

    def test_run_model_switches_model_and_stops_on_limit(self):
        old = ai_news.CLAUDE_MODEL
        try:
            seen = []

            def empty_chat(system, user, timeout=0):
                seen.append(ai_news.CLAUDE_MODEL)
                return "", "claude exit 1"
            jobs = [{"key": str(i), "system": "s", "user": "u", "user_sha": "x"} for i in range(40)]
            res, stopped, _ = X.run_model("sonnet", jobs, lambda t: {"ok": False}, parallel=1, stop_after=3, retries=0, chat=empty_chat)
            self.assertTrue(stopped)
            self.assertLess(len(res), 10)                      # stopped after a run of empty replies, did not hammer the limit
            self.assertEqual(set(seen), {"claude-sonnet-5-5"})
            ok_chat = lambda system, user, timeout=0: ('{"d":{"5m":"none","1h":"none","1d":"none"}}', "claude/claude-haiku-5-5")  # noqa: E731
            res, stopped, _ = X.run_model("haiku", jobs[:2], lambda t: X.R.parse_reply2(t, "crypto"), parallel=1, retries=0, chat=ok_chat)
            self.assertFalse(stopped)
            self.assertTrue(all(r["ok"] and r["lat_s"] >= 0 for r in res))
        finally:
            ai_news.CLAUDE_MODEL = old

    def test_cap_per_coin_day(self):
        base = L.day_ts("2026-11-28")
        items = {f"k{i}": {"t_seen": base + i, "sym": "BTC", "text_named": f"title number {i}"} for i in range(20)}
        keep = X.capped_keys(items, list(items))
        self.assertEqual(len(keep), P["fwd"]["cap_per_coin_day"])
        self.assertEqual(keep, X.capped_keys(items, list(items)))

    def test_fwd_without_ingest_reports_blocker(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out, state, r2 = d + "/out", d + "/state", d + "/r2"
            X.fwd(out, state, d + "/none", r2, now=L.day_ts("2026-11-28"), bars_fn=lambda *a: [], run=lambda *a, **k: ([], False, {}))
            prog = json.load(open(out + "/fwd/progress.json"))
            self.assertIn("blocker", prog)
            self.assertEqual(prog["crypto"]["paired_settled_capped"], 0)
            self.assertFalse(prog["stock"]["scoring_open"])


if __name__ == "__main__":
    unittest.main()
