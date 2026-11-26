"""Offline tests for research/news_train round 3 Track A (magnitude). Synthetic data only."""
import hashlib
import json
import math
import random
import unittest
from pathlib import Path

from research.news_train import logic as L
from research.news_train import logic_r3 as T

ROOT = Path(__file__).resolve().parents[1] / "research" / "news_train"
P = T.load_params()


class Lock(unittest.TestCase):
    def test_protocol_hash_and_params(self):
        add = ROOT / "protocol_r3_20261126.md"
        self.assertEqual(hashlib.sha256(add.read_bytes()).hexdigest(), add.with_suffix(".sha256").read_text().strip(), "protocol_r3 is locked; write a dated addendum")
        self.assertIn(hashlib.sha256((ROOT / "params_r3.json").read_bytes()).hexdigest(), add.read_text())
        self.assertEqual(P["model"], "claude-haiku-5-5")

    def test_registry_and_round2_untouched(self):
        for v in T.versions_registry()["versions"]:
            T.check_version(v)
        self.assertLessEqual(len(T.versions_registry()["versions"]), P["max_versions"])
        for n in ("protocol_r2_20261126", "protocol_r2_addendum_20261126", "protocol_r2_addendum2_20261126"):
            f = ROOT / (n + ".md")
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), f.with_suffix(".sha256").read_text().strip())

    def test_refuse_forward(self):
        with self.assertRaises(L.SealError):
            T.assert_allowed(L.day_ts("2026-11-27"), P)
        T.assert_allowed(L.day_ts("2026-11-26"), P)
        with self.assertRaises(L.SealError):
            T.assert_dev(L.day_ts("2026-07-01"), P)


class Stats(unittest.TestCase):
    def test_spearman_ranks_ties(self):
        self.assertEqual(T.ranks([3, 1, 1, 2]), [4.0, 1.5, 1.5, 3.0])
        self.assertAlmostEqual(T.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]), 1.0)
        self.assertAlmostEqual(T.spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]), -1.0)

    def test_partial_removes_control(self):
        rng = random.Random(1)
        z = [rng.random() for _ in range(400)]
        x = [v + 0.05 * rng.random() for v in z]           # x is z plus noise
        y = [v + 0.05 * rng.random() for v in z]           # y is z plus noise: x and y correlate only through z
        self.assertGreater(T.spearman(x, y), 0.8)
        self.assertLess(abs(T.partial_spearman(x, y, [z])), 0.2)
        y2 = [v + w for v, w in zip(y, x)]                  # now y has a part that comes from x itself
        self.assertGreater(T.partial_spearman(x, y2, [z]), 0.3)

    def test_auc(self):
        self.assertEqual(T.auc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0)
        self.assertEqual(T.auc([1, 1, 1, 1], [0, 1, 0, 1]), 0.5)
        self.assertIsNone(T.auc([1, 2], [1, 1]))

    def test_bootstrap_detects_signal_and_noise(self):
        rng = random.Random(2)
        rows = []
        for d in range(40):
            for _ in range(10):
                rv, pre, noise = rng.random(), rng.random(), rng.random()
                y = rv + 0.5 * noise
                rows.append({"day": f"2026-01-{d + 1:02d}", "y": y, "h": noise + 0.2 * rng.random(), "rv": rv, "pre": pre, "kw": rng.random(), "hp": 0.0, "big": 0})
        t = T.gate_tests(rows, 60, 5)
        self.assertGreater(t["T1_partial"]["point"], 0.3)
        self.assertLess(t["T1_partial"]["p"], 0.05)
        rows2 = [dict(r, h=rng.random()) for r in rows]
        t2 = T.gate_tests(rows2, 60, 5)
        self.assertGreater(t2["T1_partial"]["p"], 0.05)


class Features(unittest.TestCase):
    def test_crypto_rv_uses_only_past_bars(self):
        bars = [(60 * i, 1, 1, 100.0 * (1.001 if i % 2 else 1.0)) for i in range(3000)]
        entry = 60 * 2000
        a = T.crypto_rv(bars, entry, 24, 1000)
        bars2 = [b if b[0] < entry else (b[0], 1, 1, b[3] * 5) for b in bars]      # change the future: rv must not move
        self.assertEqual(a, T.crypto_rv(bars2, entry, 24, 1000))
        self.assertGreater(a, 0)
        self.assertIsNone(T.crypto_rv(bars, 60 * 500, 24, 1000))

    def test_stock_rv_excludes_entry_bar(self):
        bars = [{"t": 3600 * i, "o": 100.0, "h": 101, "l": 99, "c": 100.0 * (1.01 if i % 2 else 1.0)} for i in range(60)]
        a = T.stock_rv(bars, 3600 * 40, 35, 14)
        bars[40] = dict(bars[40], c=1000.0)
        self.assertEqual(a, T.stock_rv(bars, 3600 * 40, 35, 14))

    def test_big_threshold_and_target(self):
        self.assertAlmostEqual(T.big_threshold("stock", P), 0.0036)
        self.assertAlmostEqual(T.big_threshold("crypto", P), 0.008)
        self.assertAlmostEqual(T.target({"gross": {"1h": -0.02}}, "1h"), 0.02)
        self.assertIsNone(T.target({"gross": {"1h": None}}, "1h"))

    def test_parse_reply(self):
        r = T.parse_reply3('x {"abs1h": 1.5, "p_big": 70, "why": "a"}')
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["abs1h"], 0.015)
        self.assertAlmostEqual(r["p_big"], 0.7)
        self.assertFalse(T.parse_reply3('{"abs1h": -1}')["ok"])
        self.assertFalse(T.parse_reply3("no json")["ok"])


class Selection(unittest.TestCase):
    def test_select_lock_floor_and_none(self):
        v = {"m0": {"stock": {"n": 500, "reply_ok": 1.0, "partial": 0.01}, "crypto": {"n": 900, "reply_ok": 1.0, "partial": 0.08}},
             "m1": {"stock": {"n": 500, "reply_ok": 1.0, "partial": 0.04}, "crypto": {"n": 900, "reply_ok": 0.9, "partial": 0.2}},
             "m2": {"stock": {"n": 500, "reply_ok": 1.0, "partial": 0.04}, "crypto": {"n": 100, "reply_ok": 1.0, "partial": 0.3}}}
        lock = T.select_lock(v, P)
        self.assertEqual(lock, {"stock": "m1", "crypto": "m0"})            # tie -> lower number; reply floor and n floor applied
        self.assertEqual(T.select_lock({"m0": {"stock": {"n": 500, "reply_ok": 1, "partial": 0.0}}}, P), {"stock": None, "crypto": None})

    def test_verdict_unread_below_min_n(self):
        tests = {k: {"p": 0.001, "point": 0.1} for k in ("T1_partial", "T2_vs_keyword", "T3_vs_pre")}
        self.assertTrue(T.verdict(tests, 100, 3, P)["verdict"].startswith("unread"))
        self.assertEqual(T.verdict(tests, 400, 3, P)["verdict"], "done condition met")
        tests["T1_partial"]["p"] = 0.2
        self.assertEqual(T.verdict(tests, 400, 3, P)["verdict"], "not met")


if __name__ == "__main__":
    unittest.main()
