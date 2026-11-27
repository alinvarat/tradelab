"""Offline tests for round 4 (research/news_train/protocol_w4_20261127.md). Synthetic data only, no network, no model call."""
import hashlib
import json
import unittest
from pathlib import Path

from research.news_train import logic as L
from research.news_train import logic_r2 as R
from research.news_train import logic_w4 as W

ROOT = Path(__file__).resolve().parents[1]
NT = ROOT / "research" / "news_train"
P = W.load_params()
P2 = R.load_params()
DAY0 = L.day_ts("2026-08-03")


def row(i, day, gross, items=("2.02",), pre=0.0, in_session=False, price=30.0):
    return {"key": f"sec:{i}", "t_pub": DAY0 + day * 86400 + 3600 * 13, "items": list(items), "text": "x" * 2000,
            "feat": {"rv": 0.01, "kw": 1}, "labels": {R.LAB: {"gross": {"1h": gross}, "pre_move": pre, "in_session": in_session, "p_in": price, "delay_s": 900, "runup5": 0.0}}}


def dec(side="long", exp=1.0, conf=50, flow="none"):
    return {"ok": True, "d": {"1h": side}, "exp": {"1h": exp}, "conf": conf, "flow": flow}


class Lock(unittest.TestCase):
    def test_family_and_split_params(self):
        self.assertEqual(P["k"], 62)
        self.assertEqual(P["model"], "claude-haiku-5-5")
        self.assertLessEqual(P["candidates_max"], 3)

    def test_protocol_hash_and_params_hash(self):
        f = NT / "protocol_w4_20261127.md"
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), f.with_suffix(".sha256").read_text().strip())
        self.assertIn(hashlib.sha256((NT / "params_w4.json").read_bytes()).hexdigest(), f.read_text())

    def test_workflow_is_haiku_only_and_has_no_validation_restore_in_analyze(self):
        t = (ROOT / ".github" / "workflows" / "news_train_w4.yml").read_text()
        self.assertNotIn("sonnet", t.lower())
        self.assertNotIn("\t", t)
        analyze = t[t.index("  analyze:"):]
        self.assertNotIn("w4/val", analyze)
        self.assertIn("w4/train", analyze)


class Split(unittest.TestCase):
    def test_last_third_of_days_is_validation_and_disjoint(self):
        rows = [row(i, d, 0.0) for d in range(30) for i in range(d * 3, d * 3 + 3)]
        tr, va, vd = W.split_rows(rows, P)
        self.assertEqual(len(vd), 10)
        self.assertEqual(len(tr) + len(va), len(rows))
        self.assertTrue({r["key"] for r in tr}.isdisjoint({r["key"] for r in va}))
        self.assertLess(max(L.day_of(r["t_pub"]) for r in tr), min(L.day_of(r["t_pub"]) for r in va))

    def test_80_days_gives_27(self):
        self.assertEqual(len(W.val_days([f"d{i:03d}" for i in range(80)], P["split"]["val_day_fraction"])), 27)

    def test_train_only_guard(self):
        rows = [row(i, i, 0.0) for i in range(6)]
        tr, va, vd = W.split_rows(rows, P)
        W.assert_train_only(tr, vd)
        with self.assertRaises(ValueError):
            W.assert_train_only(rows, vd)


class Rules(unittest.TestCase):
    def test_empty_rule_is_frozen_w3(self):
        r = row(1, 0, 0.01)
        self.assertEqual(W.apply_rule({}, r, dec(exp=0.6), P), 1)
        self.assertEqual(W.apply_rule({}, r, dec(exp=0.4), P), 0)                 # below theta 0.5
        self.assertEqual(W.apply_rule({}, r, dec("short", exp=0.6), P), 0)        # sign disagrees with the direction
        self.assertEqual(W.apply_rule({}, r, {"ok": False}, P), 0)

    def test_restrictions(self):
        r = row(1, 0, 0.01, pre=0.03)
        d = dec("long", 2.0, 60)
        self.assertEqual(W.apply_rule({"theta_pct": 3.0}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"min_conf": 65}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"side_only": "short"}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"gap_rule": "no_chase"}, r, d, P), 0)      # long after a +3% gap
        self.assertEqual(W.apply_rule({"gap_rule": "no_fade"}, r, d, P), 1)
        self.assertEqual(W.apply_rule({"excl_code": "2.02"}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"min_price": 50}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"flow": "flow_only"}, r, d, P), 0)
        self.assertEqual(W.apply_rule({"flow": "no_flow"}, r, d, P), 1)
        self.assertEqual(W.apply_rule({"session": "outside_only"}, row(2, 0, 0.0, in_session=True), d, P), 0)

    def test_small_gap_never_filters(self):
        r = row(1, 0, 0.0, pre=0.005)
        self.assertEqual(W.apply_rule({"gap_rule": "no_chase"}, r, dec(exp=1.0), P), 1)


class Greedy(unittest.TestCase):
    def setUp(self):
        # code 2.02 trades lose, code 8.01 trades win; 60 + 60 trades over 40 days
        self.rows, self.decs, n = [], {}, 0
        for d in range(40):
            for code, g in (("2.02", -0.02), ("8.01", 0.02)):
                for _ in range(2 if d % 2 else 1):
                    n += 1
                    r = row(n, d, g, items=(code,))
                    self.rows.append(r)
                    self.decs[r["key"]] = dec("long", 1.0)

    def test_picks_the_planted_exclusion(self):
        P1 = json.loads(json.dumps(P))
        P1["greedy"]["min_trades_train"] = 30
        fit = W.greedy_fit(self.rows, self.decs, P1, P2)
        self.assertEqual(fit["rule"].get("excl_code"), "2.02")
        self.assertGreater(fit["evaluations"], 20)

    def test_noise_selects_nothing(self):
        rows, decs = [], {}
        for i in range(400):
            r = row(i, i % 40, 0.001 * ((i * 7919) % 11 - 5))
            rows.append(r)
            decs[r["key"]] = dec("long" if i % 2 else "short", 1.0 if i % 2 else -1.0)
        P1 = json.loads(json.dumps(P))
        P1["greedy"]["min_paired_t"] = 50.0
        self.assertEqual(W.greedy_fit(rows, decs, P1, P2)["rule"], {})


class Evaluate(unittest.TestCase):
    def test_paired_difference_and_routing(self):
        rows = [row(i, i % 20, 0.02 if i % 2 else -0.02, items=("8.01" if i % 2 else "2.02",)) for i in range(200)]
        w3 = {r["key"]: dec("long", 1.0) for r in rows}
        res = W.evaluate(rows, {"w3": w3, "w4": w3}, [{"id": "same", "dec": "w4", "rule": {}}, {"id": "excl", "dec": "w3", "rule": {"excl_code": "2.02"}}], P, P2)
        self.assertEqual(res["candidates"]["same"]["paired_vs_w3"]["diff_2x"]["mean"], 0.0)
        self.assertGreater(res["candidates"]["excl"]["paired_vs_w3"]["diff_2x"]["mean"], 0)
        best, why = W.route(res, P)
        self.assertEqual(best, "excl")
        self.assertFalse(why["same"]["diff_1x_positive"])

    def test_routes_nothing_below_trade_floor(self):
        rows = [row(i, i % 20, 0.02, items=("8.01",)) for i in range(20)]
        w3 = {r["key"]: dec("long", 1.0) for r in rows}
        res = W.evaluate(rows, {"w3": w3}, [{"id": "c", "dec": "w3", "rule": {"theta_pct": 0.75}}], P, P2)
        self.assertIsNone(W.route(res, P)[0])


class Analysis(unittest.TestCase):
    def test_tables_run_and_cover_registered_dimensions(self):
        rows = [row(i, i % 30, 0.01 * ((i % 5) - 2), items=("2.02", "9.01")) for i in range(150)]
        decs = {r["key"]: dec("long", 1.0) for r in rows}
        res = W.analysis(rows, decs, P, P2)
        for k in ("has_code", "side", "abs_exp_1h", "gap_align", "ny_time", "price", "rv", "delay"):
            self.assertIn(k, res["tables_w3_trades"])
        self.assertEqual(res["baseline_w3"]["n_offered"], 150)
        self.assertEqual(len(res["theta_conf_sweep"]), len(P["analysis"]["theta_grid_pct"]) * len(P["analysis"]["conf_grid"]))
        json.dumps(res, default=str)


if __name__ == "__main__":
    unittest.main()
