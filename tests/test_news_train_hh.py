"""Offline tests for the historical holdout (research/news_train/protocol_hh_20261127.md). Synthetic data only, no network, no model call."""
import copy
import gzip
import hashlib
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

from core import ai_news
from research.news_train import logic as L
from research.news_train import logic_cmp as C
from research.news_train import logic_hh as H
from research.news_train import logic_r2 as R
from research.news_train import run_hh as X

ROOT = Path(__file__).resolve().parents[1]
NT = ROOT / "research" / "news_train"
P = H.load_params()
P2 = R.load_params()
THETA = {"1h": 0.5, "eod": 0.75}
DAY0 = L.day_ts("2026-08-03")


class Lock(unittest.TestCase):
    def test_protocol_hash_and_params(self):
        f = NT / "protocol_hh_20261127.md"
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), f.with_suffix(".sha256").read_text().strip())
        self.assertIn(hashlib.sha256((NT / "params_hh.json").read_bytes()).hexdigest(), f.read_text())

    def test_models_registry_and_core_default(self):
        self.assertEqual(P["models"], {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5"})
        for s in X.SETS:
            X.X.version_of(s)                                  # prompt sha256 equals the locked registry
        self.assertEqual(ai_news.CLAUDE_MODEL, "claude-haiku-5-5")

    def test_family_arithmetic(self):
        self.assertAlmostEqual(P["alpha_k"], 0.10 / (P["k"] * (P["k"] + 1)), places=9)
        self.assertEqual(P["k"], 61)
        self.assertEqual(len(P["family_tests"]), 3)

    def test_window_is_after_both_cutoffs_and_before_forward(self):
        gate = {"cutoff_month": "2025-11"}
        lo, hi = H.window_ts(P)
        self.assertTrue(C.eligible(lo, gate["cutoff_month"]))
        self.assertLess(hi, L.day_ts(P2["dates"]["fwd_from"]))
        self.assertGreaterEqual(L.day_of(lo), P2["dates"]["sealed_hist_from"])

    def test_workflow_structure(self):
        t = (ROOT / ".github" / "workflows" / "news_train_hh.yml").read_text()
        self.assertNotIn("\t", t)
        for j in ("  build:", "  call:", "  merge:"):
            self.assertIn(j, t)
        self.assertIn("workflow_dispatch:", t)
        self.assertNotIn("pull_request", t)
        self.assertNotIn("schedule:", t)
        self.assertNotIn("kuber", t.lower().replace("tradelab", ""))
        self.assertIn("needs: [build, call]", t)
        self.assertIn("needs.build.outputs.go == '1'", t)
        # labels travel in their own artifact, the call jobs download the prompts only
        call = t.split("\n  call:")[1].split("\n  merge:")[0]
        self.assertNotIn("hh-labels", call)
        self.assertIn("data/news-train-hh", t)


class Stats(unittest.TestCase):
    def test_t_sf_known_values(self):
        self.assertAlmostEqual(H.t_sf(0.0, 5), 0.5, places=9)
        self.assertAlmostEqual(H.t_sf(1.0, 1), 0.25, places=7)                    # Cauchy
        self.assertAlmostEqual(H.t_sf(2.0, 1), 0.5 - math.atan(2.0) / math.pi, places=7)
        self.assertAlmostEqual(H.t_sf(2.0, 10), 0.036694, places=5)
        self.assertAlmostEqual(H.t_sf(-1.0, 1), 0.75, places=7)
        self.assertAlmostEqual(H.t_sf(1.96, 100000), 0.0250, places=3)             # normal limit
        self.assertLess(H.t_sf(8.0, 80), 1e-10)

    def test_cluster_t_matches_plain_t_when_one_item_per_day(self):
        r = H.cluster_t([1, 2, 3, 4, 5, 6], [f"d{i}" for i in range(6)])
        self.assertAlmostEqual(r["mean"], 3.5)
        self.assertAlmostEqual(r["t"], 3.5 / (math.sqrt(3.5) / math.sqrt(6)), places=6)     # sd^2 = 3.5
        self.assertAlmostEqual(r["p"], 0.00298, delta=3e-4)
        self.assertEqual(r["df"], 5)

    def test_cluster_t_clusters_by_day(self):
        # ten items of one day move together: with one day-sum the evidence is that of one day, not ten
        vals = [1.0] * 10 + [-0.5, 0.5, -0.4, 0.4, -0.3, 0.3]
        days = ["a"] * 10 + ["b", "c", "d", "e", "f", "g"]
        r = H.cluster_t(vals, days)
        flat = H.cluster_t(vals, [f"x{i}" for i in range(16)])
        self.assertGreater(r["p"], flat["p"])

    def test_cluster_t_undefined_cases_give_none_never_zero(self):
        self.assertIsNone(H.cluster_t([1, 1, 1, 1, 1, 1], list("abcdef"))["p"])           # zero variance
        self.assertIsNone(H.cluster_t([1, 2, 3, 4], list("abcd"))["p"])                    # fewer than 5 days
        self.assertIsNone(H.cluster_t([], [])["p"])

    def test_bootstrap_zero_never_meets_the_bar(self):
        self.assertFalse(H.meets_bar(None, P["alpha_k"]))
        self.assertFalse(H.meets_bar(0.0, P["alpha_k"]))
        self.assertTrue(H.meets_bar(1e-6, P["alpha_k"]))
        self.assertFalse(H.meets_bar(1e-4, P["alpha_k"]))
        # a result that only carries a bootstrap p of 0 has no analytic p: Holm sees 1 and nothing is nominated
        h = {"p": None, "p_boot": 0.0, "mean": 0.02, "mean_per_trade": 0.02, "mean_per_trade_2x": 0.02, "n_traded": 500}
        h3 = {"sign": {"p": None}, "mean_diff": 0.0}
        fam = H.family(h, h, h3, P)
        self.assertEqual(fam["holm_adjusted"]["H1_haiku_vs_random"], 1.0)
        gate = {"ok": {"paired": True, "traded_haiku": True, "traded_sonnet": True, "discordant": True}}
        v = H.verdict(fam, h, h, h3, gate, P)
        self.assertEqual(set(v["nomination"].values()), {"not nominated"})

    def test_holm_family_of_three(self):
        adj = H.holm({"a": 1e-6, "b": 0.5, "c": None}, 3)
        self.assertAlmostEqual(adj["a"], 3e-6)
        self.assertEqual(adj["c"], 1.0)

    def test_verdict_nomination_needs_all_conditions(self):
        gate = {"ok": {"paired": True, "traded_haiku": True, "traded_sonnet": True, "discordant": True}}
        base = {"p": 1e-9, "mean": 0.01, "mean_per_trade": 0.05, "mean_per_trade_2x": 0.04, "n_traded": 150}
        weak = {"p": 0.2, "mean": 0.0, "mean_per_trade": -0.01, "mean_per_trade_2x": -0.02, "n_traded": 150}
        h3 = {"sign": {"p": 0.5}, "mean_diff": 0.0}
        fam = H.family(base, weak, h3, P)
        v = H.verdict(fam, base, weak, h3, gate, P)
        self.assertEqual(v["nomination"]["H1_haiku_vs_random"], "nominated for a forward ledger")
        self.assertEqual(v["nomination"]["H2_sonnet_vs_random"], "not nominated")
        for k, val in (("mean_per_trade_2x", -0.001), ("mean_per_trade", -0.001), ("n_traded", 99), ("mean", -0.1)):
            b = dict(base, **{k: val})
            self.assertEqual(H.verdict(H.family(b, weak, h3, P), b, weak, h3, gate, P)["nomination"]["H1_haiku_vs_random"], "not nominated", k)
        self.assertNotIn("found", json.dumps(v))

    def test_comparison_verdict_words(self):
        h = {"p": 0.5, "mean": 0, "mean_per_trade": 0, "mean_per_trade_2x": 0, "n_traded": 150}
        ok = {"ok": {"paired": True, "traded_haiku": True, "traded_sonnet": True, "discordant": True}}
        for p, md, want in ((1e-5, 0.01, "Sonnet better"), (1e-5, -0.01, "Haiku better"), (0.3, 0.01, "no difference detected")):
            h3 = {"sign": {"p": p}, "mean_diff": md}
            self.assertEqual(H.verdict(H.family(h, h, h3, P), h, h, h3, ok, P)["comparison"], want)
        under = {"ok": dict(ok["ok"], discordant=False)}
        self.assertTrue(H.verdict(H.family(h, h, h3, P), h, h, h3, under, P)["comparison"].startswith("underpowered"))
        unread = {"ok": dict(ok["ok"], traded_sonnet=False)}
        self.assertTrue(H.verdict(H.family(h, h, h3, P), h, h, h3, unread, P)["comparison"].startswith("unread"))


def dec(d1h="none", exp=0.0, ok=True):
    return {"ok": ok, "d": {"1h": d1h, "eod": "none"}, "exp": {"1h": exp, "eod": None}, "conf": 50, "abs1h": 0.01, "p_big": 0.3}


def item(i, gross, day_off=None, items=("8.01",), rv=0.01, pre=0.005):
    t = DAY0 + (i % 12 if day_off is None else day_off) * 86400 + 14 * 3600
    lab = {"entry_ts": t + 100, "p_in": 10.0, "in_session": False, "delay_s": 100, "gross": {"1h": gross, "eod": gross}, "exit_ts": {"1h": t + 3700, "eod": t + 7000},
           "day_move": 0.0, "pre_move": pre, "runup5": None}
    return {"key": f"sec:0000-{i:04d}", "market": "stock", "t_pub": t, "sym": f"S{i % 7}", "items": list(items), "labels": {R.LAB: lab},
            "feat": {"rv": rv, "pre": pre, "kw": 0, "pre_signed": pre}, "text": "text " + str(i), "cik": 100 + i % 7, "day": L.day_of(t)}


class Decisions(unittest.TestCase):
    def test_sides_use_frozen_theta_and_no_label(self):
        decs = {"a": dec("long", 1.0), "b": dec("long", 0.2), "c": dec("short", -0.9), "d": dec("long", -1.0), "e": dec("none", 2.0), "f": dec(ok=False)}
        s = H.sides(decs, THETA, "1h")
        self.assertEqual(s, {"a": 1, "b": 0, "c": -1, "d": 0, "e": 0})                   # below theta, sign mismatch, none: no trade; invalid reply absent

    def test_count_gate(self):
        keys = [f"k{i}" for i in range(12)]
        hd = {k: dec("long", 1.0) if i < 6 else dec() for i, k in enumerate(keys)}            # Haiku trades 6
        sd = {k: dec("long", 1.0) if 3 <= i < 8 else dec() for i, k in enumerate(keys)}       # Sonnet trades 5, overlaps on 3..5
        P_small = copy.deepcopy(P)
        P_small["n"] = {"callable_floor": 12, "min_traded": 5, "min_discordant": 5, "callable_cap": 20}
        g = H.count_gate(hd, sd, THETA, "1h", P_small)
        self.assertEqual((g["paired"], g["traded_haiku"], g["traded_sonnet"], g["discordant"]), (12, 6, 5, 5))
        self.assertTrue(all(g["ok"].values()))
        P_small["n"]["min_discordant"] = 6
        self.assertFalse(H.count_gate(hd, sd, THETA, "1h", P_small)["ok"]["discordant"])


class Arrays(unittest.TestCase):
    def setUp(self):
        self.rows = [item(i, 0.02 if i % 2 else -0.02) for i in range(24)]
        self.long_on_up = {r["key"]: (dec("long", 1.0) if r["labels"][R.LAB]["gross"]["1h"] > 0 else dec("short", -1.0)) for r in self.rows}   # perfect foresight
        self.abstain = {r["key"]: dec() for r in self.rows}

    def test_abstaining_model_scores_zero_and_zero_against_random(self):
        a = H.arrays(self.rows, self.abstain, THETA, "1h", "stock", P2)
        self.assertEqual(sum(a["a"]), 0.0)
        self.assertEqual(sum(a["rnd"]), 0.0)
        res = H.vs_random(a)
        self.assertEqual(res["n_traded"], 0)
        self.assertIsNone(res["mean_per_trade"])
        self.assertEqual(res["mean"], 0.0)

    def test_perfect_foresight_beats_random_by_the_edge_minus_nothing(self):
        a = H.arrays(self.rows, self.long_on_up, THETA, "1h", "stock", P2)
        self.assertEqual(sum(1 for s in a["side"] if s), 24)
        self.assertTrue(all(x > 0 for x in a["a"]))
        for x, r in zip(a["a"], a["rnd"]):
            self.assertGreater(x, r)
        res = H.vs_random(a)
        self.assertGreater(res["mean"], 0.015)
        self.assertGreater(res["mean_per_trade_2x"], 0)
        self.assertEqual(res["n_offered"], 24)

    def test_random_expectation_is_the_cost_drag(self):
        a = H.arrays(self.rows, self.long_on_up, THETA, "1h", "stock", P2)
        for r, g in zip(a["rnd"], a["gross"]):
            self.assertAlmostEqual(r, L.random_expectation(g, "stock", P2))
            self.assertLess(r, 0)                                                      # costs make a random direction lose

    def test_missing_label_or_reply_is_excluded(self):
        rows = [dict(item(1, 0.02)), dict(item(2, 0.02), labels={}), item(3, 0.02)]
        d = {rows[0]["key"]: dec("long", 1.0), rows[2]["key"]: dec(ok=False)}
        d[rows[1]["key"]] = dec("long", 1.0)
        a = H.arrays(rows, d, THETA, "1h", "stock", P2)
        self.assertEqual(len(a["key"]), 1)

    def test_paired_difference_and_sign_test(self):
        ah = H.arrays(self.rows, self.long_on_up, THETA, "1h", "stock", P2)
        asn = H.arrays(self.rows, self.abstain, THETA, "1h", "stock", P2)
        p = H.paired(ah, asn)                                                           # Sonnet abstains, Haiku trades with foresight
        self.assertEqual(p["n"], 24)
        self.assertEqual(p["discordant"], 24)
        self.assertLess(p["mean_diff"], 0)
        self.assertEqual(p["sign"]["neg"], 24)
        self.assertAlmostEqual(p["sign"]["p"], 2.0 / 2 ** 24, places=12)


class Universe(unittest.TestCase):
    def test_exchange_and_candidate_rules(self):
        self.assertTrue(H.exchange_ok("Nasdaq", P))
        self.assertFalse(H.exchange_ok("OTC", P))
        lo, hi = H.window_ts(P)
        f = {"form": "8-K", "ts": lo + 5, "doc": "a.htm", "items": ["8.01", "9.01"]}
        self.assertTrue(H.candidate_ok(f, P, lo, hi))
        self.assertTrue(H.candidate_ok(dict(f, items=[]), P, lo, hi))                      # empty list passes, as round 2
        self.assertFalse(H.candidate_ok(dict(f, items=["9.01"]), P, lo, hi))
        self.assertFalse(H.candidate_ok(dict(f, form="8-K/A"), P, lo, hi))
        self.assertFalse(H.candidate_ok(dict(f, ts=hi), P, lo, hi))                        # window end is exclusive
        self.assertFalse(H.candidate_ok(dict(f, ts=lo - 1), P, lo, hi))
        self.assertFalse(H.candidate_ok(dict(f, doc=""), P, lo, hi))

    def test_sample_caps_per_issuer_is_deterministic_and_order_free(self):
        cands = [{"cik": c, "acc": f"{c:04d}-{n:03d}", "sym": f"S{c}"} for c in range(40) for n in range(6)]
        s1 = H.sample_candidates(cands, P)
        s2 = H.sample_candidates(list(reversed(cands)), P)
        self.assertEqual([c["acc"] for c in s1], [c["acc"] for c in s2])
        per = {}
        for c in s1:
            per[c["cik"]] = per.get(c["cik"], 0) + 1
        self.assertEqual(max(per.values()), P["universe"]["per_issuer_cap"])
        self.assertEqual(len(s1), 40 * P["universe"]["per_issuer_cap"])

    def test_first_n_is_a_prefix(self):
        keys = [f"sec:{i}" for i in range(300)]
        self.assertEqual(H.first_n_by_sha(keys, 50, P["seed"]), H.first_n_by_sha(keys, 120, P["seed"])[:50])

    def bars(self, price, vol, sessions=6, entry_day=10):
        out = []
        for d in range(sessions):
            base = L.day_ts("2026-09-01") + d * 86400
            for h in range(6):
                out.append({"t": base + (14 + h) * 3600 + 1800, "o": price, "h": price, "l": price, "c": price, "v": vol})
        return out, L.day_ts("2026-09-01") + sessions * 86400 + 14 * 3600

    def test_liquidity_floor(self):
        bars, te = self.bars(10.0, 5000)                                                   # 10 x 5000 x 6 bars = 300,000 a session: too thin
        self.assertEqual(H.liquidity(bars, te, 10.0, P), (False, "dollar_volume_below_floor"))
        bars, te = self.bars(10.0, 50000)                                                  # 3,000,000 a session
        self.assertEqual(H.liquidity(bars, te, 10.0, P), (True, "ok"))
        self.assertEqual(H.liquidity(bars, te, 4.99, P), (False, "price_below_floor"))
        bars, te = self.bars(10.0, 50000, sessions=2)
        self.assertEqual(H.liquidity(bars, te, 10.0, P), (False, "too_few_prior_sessions"))

    def test_liquidity_ignores_bars_at_or_after_entry(self):
        bars, te = self.bars(10.0, 50000)
        later = [dict(b, t=te + i * 3600, v=10 ** 9) for i, b in enumerate(bars)]
        thin, te2 = self.bars(10.0, 5000)
        self.assertEqual(H.liquidity(thin + [dict(b, t=te2 + 10 + i * 3600, v=10 ** 9) for i, b in enumerate(bars)], te2, 10.0, P)[0], False)
        self.assertEqual(H.liquidity(bars + later, te, 10.0, P)[0], True)


class Build(unittest.TestCase):
    def test_prior_keys_scan(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "a", "calls"))
            for p, rows in (("a/x.jsonl.gz", [{"key": "sec:1-1"}, {"key": "gdelt:zz"}]), ("a/calls/y.jsonl.gz", [{"key": "sec:2-2"}])):
                with gzip.open(os.path.join(d, p), "wt") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
            self.assertEqual(X.prior_keys(d), {"sec:1-1", "sec:2-2"})

    def test_leak_check_passes_for_the_registered_gate_and_refuses_otherwise(self):
        with tempfile.TemporaryDirectory() as d:
            gate = os.path.join(d, "gate.json")
            tab = {"table": [{"asset": "^GSPC", "month": m, "answered": a, "acc_answered": 1.0 if a else None} for m, a in (("2025-10", 6), ("2025-11", 7), ("2025-12", 0), ("2026-08", 0))]}
            for n in ("s.json", "h.json"):
                json.dump(tab, open(os.path.join(d, n), "w"))
            json.dump({"cutoff_month": "2025-11", "first_eligible_day": "2025-12-01"}, open(gate, "w"))
            rep = X.leak_check(gate, os.path.join(d, "s.json"), os.path.join(d, "h.json"), d)
            self.assertTrue(rep["window_after_both_cutoffs"])
            self.assertEqual(rep["answered_any_month_from_first_eligible"], {"sonnet": 0, "haiku": 0})
            self.assertTrue(os.path.exists(os.path.join(d, "leak_check.json")))
            json.dump({"cutoff_month": "2026-08", "first_eligible_day": "2026-09-01"}, open(gate, "w"))
            with self.assertRaises(SystemExit):
                X.leak_check(gate, "-", "-", d)


def write_jsonl(path, rows):
    with (gzip.open if path.endswith(".gz") else open)(path, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def meta(shard=0):
    m = {"called": 1, "ok": 1, "stopped_early": False, "spend": {"calls": 1, "tokens_in": 10, "tokens_out": 2, "notional_usd": 0.01}, "served_mismatch": 0, "first_served": "claude/x"}
    return {"set": "stock_w3", "shard": shard, "items": 1, "models": {"haiku": dict(m), "sonnet": dict(m)}}


class Merge(unittest.TestCase):
    """The merge step on a small synthetic set (floors patched down): counts gate first, outcomes only afterwards, one shot."""

    def setUp(self):
        self.P0 = X.P
        X.P = copy.deepcopy(P)
        X.P["n"] = {"callable_floor": 40, "min_traded": 5, "min_discordant": 5, "callable_cap": 60}
        X.P["bootstrap"]["n"] = 40
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.parts, self.out, self.r2, self.cache = (os.path.join(d, n) for n in ("parts", "out", "r2", "cache"))
        for p in (self.parts, self.r2, os.path.join(self.cache, "hh")):
            os.makedirs(p)
        json.dump({"w3": {"stock": THETA}}, open(os.path.join(self.r2, "calib.json"), "w"))
        self.rows = [item(i, 0.03 if i % 3 else -0.03, rv=0.005 + 0.0003 * (i % 11), pre=0.002 + 0.0004 * (i % 5)) for i in range(60)]
        self.labels = os.path.join(d, "labels.jsonl.gz")
        write_jsonl(self.labels, self.rows)

    def tearDown(self):
        X.P = self.P0
        self.tmp.cleanup()

    def decisions(self, trade_h=range(0, 60, 2), trade_s=range(1, 60, 3)):
        out = []
        for i, r in enumerate(self.rows):
            up = r["labels"][R.LAB]["gross"]["1h"] > 0
            for m, tr in (("haiku", trade_h), ("sonnet", trade_s)):
                d = dec("long" if up else "short", 1.0 if up else -1.0) if i in tr else dec()
                out.append(dict(d, set="stock_w3", model=m, key=r["key"], lat_s=2.0, served="claude/x"))
                out.append(dict({"ok": True, "abs1h": 0.004 + 0.0001 * i, "p_big": 0.4}, set="stock_m1", model=m, key=r["key"], lat_s=2.0, served="claude/x"))
        write_jsonl(os.path.join(self.parts, "dec_stock_w3_0.jsonl"), out)
        json.dump(meta(), open(os.path.join(self.parts, "meta_stock_w3_0.json"), "w"))

    def test_full_merge_writes_one_result_with_all_blocks(self):
        self.decisions()
        X.merge(self.parts, "-", self.labels, self.out, self.r2, self.cache)
        res = json.load(open(os.path.join(self.out, "result.json")))
        self.assertTrue(all(res["count_gate"]["ok"].values()), res["count_gate"])
        for k in ("H1_haiku_vs_random", "H2_sonnet_vs_random", "H3_sonnet_minus_haiku", "holm_adjusted", "p"):
            self.assertIn(k, res["family"])
        self.assertEqual(res["family"]["m"], 3)
        self.assertIn("nomination", res["verdict"])
        self.assertEqual(res["integrity"]["rows"], 60)
        self.assertEqual(res["integrity"]["unique_keys"], 60)
        self.assertIn("m1", res["descriptive"])
        self.assertIn("per_month", res["descriptive"])
        self.assertEqual(res["spend"]["haiku"]["served_mismatch"], 0)
        self.assertEqual(res["theta_frozen_w3_stock"], THETA)
        self.assertTrue(os.path.exists(os.path.join(self.out, "decisions.jsonl.gz")))

    def test_one_shot_guard(self):
        self.decisions()
        json.dump({}, open(os.path.join(self.cache, "hh", "result.json"), "w"))
        with self.assertRaises(SystemExit):
            X.merge(self.parts, "-", self.labels, self.out, self.r2, self.cache)

    def test_below_the_counts_floor_no_label_is_opened(self):
        self.decisions(trade_h=[0, 1])                                                     # Haiku trades 2 < 5
        X.merge(self.parts, "-", "/nonexistent/labels.jsonl.gz", self.out, self.r2, self.cache)   # a label read would find no file and yield nothing: assert on the output
        self.assertTrue(os.path.exists(os.path.join(self.out, "unread.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "result.json")))
        u = json.load(open(os.path.join(self.out, "unread.json")))
        self.assertTrue(u["verdict"]["comparison"].startswith("unread"))
        self.assertNotIn("family", u)

    def test_cached_decisions_complete_a_partial_run(self):
        self.decisions()
        allrows = list(X.rjsonl(os.path.join(self.parts, "dec_stock_w3_0.jsonl")))
        os.remove(os.path.join(self.parts, "dec_stock_w3_0.jsonl"))
        write_jsonl(os.path.join(self.cache, "hh", "dec_stock_w3_0_r1.jsonl"), allrows[: len(allrows) // 2])
        write_jsonl(os.path.join(self.parts, "dec_stock_w3_1.jsonl"), allrows[len(allrows) // 2:])
        X.merge(self.parts, "-", self.labels, self.out, self.r2, self.cache)
        self.assertEqual(json.load(open(os.path.join(self.out, "result.json")))["count_gate"]["paired"], 60)

    def test_call_skips_cached_ok_decisions(self):
        calls = []

        def fake_run_model(mk, jobs, parse, **kw):
            calls.append((mk, [j["key"] for j in jobs]))
            return [dict(parse('{"d":{"1h":"none","eod":"none"},"exp":{}}'), key=j["key"], model=mk, lat_s=1.0, served="claude/" + P["models"][mk], reply="", user_sha=j["user_sha"]) for j in jobs], False, {}
        d = self.tmp.name
        prep = os.path.join(d, "prep.jsonl.gz")
        rows = [{"set": "stock_w3", "key": f"sec:k{i}", "user": "u", "user_sha": "s"} for i in range(6)]
        write_jsonl(prep, rows)
        write_jsonl(os.path.join(self.cache, "hh", "dec_stock_w3_0_r1.jsonl"), [dict(dec(), set="stock_w3", model="haiku", key="sec:k0")])
        old = X.X.run_model
        X.X.run_model = fake_run_model
        try:
            X.call(os.path.join(d, "o"), prep, "stock_w3", 0, 1, self.cache)
        finally:
            X.X.run_model = old
        haiku = next(k for m, k in calls if m == "haiku")
        self.assertNotIn("sec:k0", haiku)
        self.assertEqual(len(haiku), 5)
        self.assertEqual(len(next(k for m, k in calls if m == "sonnet")), 6)


if __name__ == "__main__":
    unittest.main()
