"""Offline tests for research/news_train (logic, seal, lock, registry). Synthetic data only."""
import hashlib
import json
import unittest
from pathlib import Path

from core import news_backtest as nb
from research.news_train import logic as L

ROOT = Path(__file__).resolve().parents[1] / "research" / "news_train"
P = L.load_params()


def bars(t0, n, px, step=0.0):
    return [(t0 + 60 * i, px + step * i, px + step * i, px + step * i + step) for i in range(n)]


class Lock(unittest.TestCase):
    def test_protocol_and_params_hash(self):
        proto = ROOT / "protocol.md"
        self.assertEqual(hashlib.sha256(proto.read_bytes()).hexdigest(), (ROOT / "protocol.sha256").read_text().strip(),
                         "protocol.md is locked; write a dated addendum instead")
        self.assertIn(hashlib.sha256((ROOT / "params.json").read_bytes()).hexdigest(), proto.read_text())

    def test_registry_matches_prompts_and_cap(self):
        reg = L.versions_registry()["versions"]
        self.assertLessEqual(len(reg), P["max_versions"])
        for v in reg:
            L.check_version(v)
        with self.assertRaises(ValueError):
            L.check_version(dict(reg[0], sha256="0" * 64))

    def test_stock_cost_pinned_to_backtest_engine(self):
        self.assertAlmostEqual(P["cost"]["stock_side"], nb.cost_per_side("stock"), places=9)

    def test_claude_only(self):
        self.assertEqual(P["model"], "claude-haiku-5-5")


class Seal(unittest.TestCase):
    def test_splits(self):
        d = L.day_ts
        self.assertEqual(L.split_of(d("2024-06-01"), P), "train")
        self.assertEqual(L.split_of(d("2026-06-30"), P), "validation")
        self.assertEqual(L.split_of(d("2026-07-15"), P), "buffer")
        self.assertEqual(L.split_of(d("2026-09-01"), P), "sealed")
        self.assertEqual(L.split_of(d("2026-11-01"), P), "burned")
        self.assertEqual(L.split_of(d("2026-11-30"), P), "sealed")

    def test_dev_loader_rejects_sealed(self):
        L.assert_dev(L.day_ts("2026-06-30"), P)
        for day in ("2026-07-01", "2026-08-02", "2026-11-30"):
            with self.assertRaises(L.SealError):
                L.assert_dev(L.day_ts(day), P)
        with self.assertRaises(L.SealError):
            L.check_dev_rows([{"t_pub": L.day_ts("2026-09-01")}], P)


class Labels(unittest.TestCase):
    def test_crypto_entry_no_lookahead_and_pre_move(self):
        t0 = 1_700_000_000 // 60 * 60
        b = bars(t0, 3000, 100.0, 0.01)
        t_pub = t0 + 3700
        lab = L.crypto_label(b, t_pub, 93, P)
        te = t_pub + 98
        last_end = (te - 60) // 60 * 60 + 60 if (te - 60) % 60 else te
        self.assertLessEqual(lab["entry_ts"], te)
        # entry price is the close of a bar that ended at or before te
        opens = [x[0] for x in b if x[0] + 60 <= te]
        self.assertAlmostEqual(lab["p_in"], b[len(opens) - 1][3])
        self.assertGreater(lab["pre_1h"], 0)
        self.assertGreater(lab["gross"]["1d"], 0)
        _ = last_end

    def test_crypto_stale_bar_is_missing(self):
        t0 = 1_700_000_000 // 60 * 60
        self.assertIsNone(L.crypto_label(bars(t0, 10, 100.0), t0 + 4000, 93, P))

    def sessions(self, n):
        out, t = [], L.day_ts("2026-03-02") + 14 * 3600 + 30 * 60      # 09:30 ET (winter) as 14:30 UTC
        for k in range(n):
            out.append({"t": t + 86400 * k, "o": 100.0 + k, "h": 0, "l": 0, "c": 101.0 + k})
        return out

    def test_stock_after_close_enters_next_open(self):
        b = self.sessions(12)
        t_pub = b[7]["t"] + 23400 + 3600          # an hour after the close of session 7
        lab, why = L.stock_label(b, t_pub, 93, P)
        self.assertEqual(why, "ok")
        self.assertEqual(lab["entry_ts"], b[8]["t"])
        self.assertAlmostEqual(lab["gross"]["1d"], 109.0 / 108.0 - 1)
        self.assertAlmostEqual(lab["gap"], 108.0 / 108.0 - 1)

    def test_stock_intraday_dropped(self):
        b = self.sessions(12)
        lab, why = L.stock_label(b, b[7]["t"] + 3600, 93, P)
        self.assertIsNone(lab)
        self.assertEqual(why, "intraday_no_bars")


class Scoring(unittest.TestCase):
    def test_net_pnl(self):
        self.assertEqual(L.net_pnl(0, 0.5, "stock", P), 0.0)
        c = P["cost"]["stock_side"]
        self.assertAlmostEqual(L.net_pnl(1, 0.01, "stock", P), 1.01 * (1 - c) ** 2 - 1)
        self.assertLess(L.net_pnl(-1, 0.0, "stock", P), -2 * c)          # borrow on top
        self.assertAlmostEqual(L.net_pnl(1, 0.0, "crypto", P), (1 - 0.002) ** 2 - 1)

    def test_random_expectation_is_negative_for_zero_move(self):
        self.assertLess(L.random_expectation(0.0, "stock", P), 0)

    def test_keyword(self):
        self.assertEqual(L.keyword_side("Company beats and raises guidance", P), 1)
        self.assertEqual(L.keyword_side("Notice of delisting and investigation", P), -1)
        self.assertEqual(L.keyword_side("Annual meeting results", P), 0)

    def test_holm_counts_untested_as_one(self):
        adj = L.holm_adjust({"a": 0.001, "b": 0.01, "c": 0.5}, 9)
        self.assertAlmostEqual(adj["a"], 0.009)
        self.assertAlmostEqual(adj["b"], 0.08)
        self.assertGreaterEqual(adj["c"], adj["b"])

    def test_bootstrap_clusters_by_day(self):
        v = [0.01] * 40 + [-0.001] * 10
        days = [f"2026-01-{1 + i % 10:02d}" for i in range(50)]
        r = L.cluster_bootstrap(v, days, 500, 1)
        self.assertLess(r["p"], 0.05)
        self.assertEqual(r["days"], 10)

    def test_score_cell_abstain_and_skill(self):
        rows, decs = [], {}
        for i in range(60):
            g = 0.03 if i % 2 == 0 else -0.03
            rows.append({"key": f"k{i}", "market": "stock", "t_pub": L.day_ts("2025-02-01") + 86400 * (i % 20), "text": "routine",
                         "labels": {"93": {"gross": {"1d": g}}}})
            decs[f"k{i}"] = {"ok": True, "d": {"1d": "long" if g > 0 else "short"}, "conf": 80}
        c = L.score_cell(rows, decs, "stock", "1d", P)
        self.assertEqual(c["n_traded"], 60)
        self.assertGreater(c["score_per_offered"], 0.02)
        self.assertLess(c["vs_random"]["p"], 0.05)
        none = {k: {"ok": True, "d": {"1d": "none"}, "conf": 0} for k in decs}
        self.assertEqual(L.score_cell(rows, none, "stock", "1d", P)["score_per_offered"], 0.0)

    def test_bad_reply_is_excluded_not_none(self):
        rows = [{"key": "k", "market": "stock", "t_pub": 1.0, "text": "", "labels": {"93": {"gross": {"1d": 0.01}}}}]
        c = L.score_cell(rows, {"k": {"ok": False}}, "stock", "1d", P)
        self.assertEqual(c["n_offered"], 0)
        self.assertEqual(c["excluded"]["no_reply"], 1)


class Analogs(unittest.TestCase):
    def pool(self):
        out = []
        for i in range(6):
            t = 1_000_000 + i * 100_000
            out.append({"key": f"p{i}", "market": "stock", "t_pub": t, "text": "company beats earnings raises guidance revenue", "items": ["2.02"],
                        "labels": {"93": {"gross": {"1d": 0.01 * i}, "exit_ts": {"1d": t + 50_000}}}})
        out.append({"key": "x", "market": "stock", "t_pub": 1_000_000, "text": "chief executive resigns", "items": ["5.02"],
                    "labels": {"93": {"gross": {"1d": 0.0}, "exit_ts": {"1d": 1_050_000}}}})
        return out

    def test_only_closed_before_and_same_market(self):
        idx = L.AnalogIndex(self.pool())
        q = {"key": "q", "market": "stock", "t_pub": 1_300_000, "text": "company beats earnings raises guidance", "items": ["2.02"]}
        got = idx.query(q, q["t_pub"], 5)
        self.assertTrue(got)
        for d in got:
            self.assertLess(d["closed"], q["t_pub"])
        self.assertNotIn("p3", [d["item"]["key"] for d in got])       # t 1.3M: exit 1.35M is after q
        self.assertEqual(idx.query(dict(q, market="crypto"), q["t_pub"], 5), [])


class Prompt(unittest.TestCase):
    def test_render_hides_gross_and_parse(self):
        it = {"key": "k", "market": "stock", "t_pub": 1.0, "text": "x" * 5000, "items": ["2.02"]}
        lab = {"gap": 0.021, "runup5": -0.01, "gross": {"1d": 0.5}}
        u = L.render_user(it, lab, {"uses_pre": True}, None, P)
        self.assertIn("+2.10%", u)
        self.assertNotIn("50.00", u)
        self.assertLessEqual(len(u), P["text_chars"] + 800)
        ok = L.parse_reply('noise {"1d": "short", "conf": 70, "why": "x"}', "stock")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["d"]["1d"], "short")
        self.assertFalse(L.parse_reply("", "stock")["ok"])
        self.assertFalse(L.parse_reply('{"1d": "maybe"}', "stock")["ok"])
        self.assertTrue(L.parse_reply('{"5m":"none","1h":"long","1d":"none","conf":5}', "crypto")["ok"])


class Redaction(unittest.TestCase):
    def test_dates_and_coin(self):
        self.assertEqual(L.scrub_dates("On March 3, 2025 and 2024-05-06"), "On [DATE] and [DATE]")
        self.assertIn("[COIN]", L.redact_coin("Raydium (RAY) Gets Listed on KuCoin! 2025", "RAY"))
        self.assertNotIn("RAY", L.redact_coin("Raydium (RAY) Gets Listed", "RAY"))


if __name__ == "__main__":
    unittest.main()
