import hashlib
import sys
import unittest
from pathlib import Path

STUDIES = Path(__file__).resolve().parents[1] / "research/studies"
sys.path.insert(0, str(STUDIES))
import wallet_follow_core as wc   # noqa: E402
import wallet_follow as wf        # noqa: E402


def row(t, side, price, size, cond="c1", token="a", tx=None):
    return {"t": t, "side": side, "price": price, "size": size, "cond": cond, "token": token, "tx": tx or f"{t}{side}{price}", "idx": 0, "wallet": "w"}


class Parse(unittest.TestCase):
    def test_parse_and_dedupe(self):
        r = wc.parse_row({"timestamp": "5", "side": "buy", "price": "0.4", "size": "10", "token_id": "a", "condition_id": "c", "transaction_hash": "x", "proxy_wallet": "w"})
        self.assertEqual((r["t"], r["side"], r["cond"]), (5, "BUY", "c"))
        self.assertIsNone(wc.parse_row({"side": "BUY"}))
        u, d = wc.dedupe([r, dict(r), dict(r, size=11.0)])
        self.assertEqual((len(u), d), (2, 1))


class Positions(unittest.TestCase):
    def test_position_cost_entry_exit(self):
        rows = [row(100, "BUY", 0.4, 1000), row(200, "BUY", 0.6, 1000), row(900, "SELL", 0.9, 1900)]
        (p,) = wc.positions(rows)
        self.assertAlmostEqual(p["cost"], 1000.0)
        self.assertAlmostEqual(p["entry"], 0.5)
        self.assertEqual(p["first_buy"], 100)
        self.assertEqual(wc.exit_time(p, 5000), 900)            # sold 95% -> own exit
        (q,) = wc.positions([row(100, "BUY", 0.5, 1000), row(300, "SELL", 0.9, 100)])
        self.assertEqual(wc.exit_time(q, 5000), 5000)           # held: market close
        self.assertIsNone(wc.exit_time(q, None))

    def test_two_sided(self):
        rows = [row(1, "BUY", .5, 1, cond="c1", token="a"), row(2, "BUY", .5, 1, cond="c1", token="b"), row(3, "BUY", .5, 1, cond="c2", token="a")]
        self.assertAlmostEqual(wc.two_sided(rows), 0.5)

    def test_summary_counts(self):
        rows = [row(wc.DEPTH_CUTOFF_TS - 10, "BUY", 0.5, 2000, cond=f"c{i}") for i in range(wc.MIN_RESOLVED)]
        cm = {f"c{i}": wc.DEPTH_CUTOFF_TS + 86400 for i in range(wc.MIN_RESOLVED)}
        s = wc.wallet_summary(rows, cm)
        self.assertTrue(s["qualifies"])
        self.assertEqual(s["big_positions"], wc.MIN_RESOLVED)
        self.assertAlmostEqual(wc.med(s["holds"]), (86400 + 10) / 86400, places=3)
        self.assertFalse(wc.wallet_summary(rows[:-1], cm)["qualifies"])           # 99 resolved
        late = [row(wc.DEPTH_CUTOFF_TS + 5, "BUY", 0.5, 2000, cond=f"c{i}") for i in range(wc.MIN_RESOLVED)]
        self.assertFalse(wc.wallet_summary(late, cm)["qualifies"])                # history too short


class Verdict(unittest.TestCase):
    def test_ceiling(self):
        self.assertAlmostEqual(wc.ceiling_multiple(30, 0.49), 2.0)                # one turn at 0.50
        self.assertGreater(wc.ceiling_multiple(10, 0.49), 3.0)       # 3 turns at 0.50 = 8x
        self.assertIsNone(wc.ceiling_multiple(0, 0.5))

    def test_verdict(self):
        self.assertEqual(wc.probe_verdict(2000, 200, 40, 5, 0.5, 0.1)["wallets"], "pass")          # 400 estimated
        self.assertEqual(wc.probe_verdict(2000, 200, 10, 5, 0.5, 0.1)["wallets"], "kill")          # saturated, 100
        self.assertEqual(wc.probe_verdict(2000, 200, 10, 5, 0.5, 0.5)["wallets"], "extend_frame")  # not saturated
        self.assertEqual(wc.probe_verdict(2000, 200, 40, 60, 0.9, 0.1)["standalone"], "component_only")
        self.assertEqual(wc.saturation([5, 5, 5, 5, 5, 5, 5, 5, 5, 5]), 0.5)

    def test_sample_order_is_stable_and_blind(self):
        a = wc.sample_order(["x", "y", "z"])
        self.assertEqual(a, wc.sample_order(["z", "y", "x"]))


class Frame(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(len(wf.FRAME_DATES), 22)
        self.assertEqual(wf.FRAME_DATES[0], "2025-01-01")
        self.assertEqual(wf.FRAME_DATES[-1], "2026-10-01")
        self.assertEqual(wf.ts_of("2025-01-01"), 1735689600 + 12 * 3600)
        mw = wf.month_windows()
        self.assertEqual(mw[0], ("2025-01-01", "2025-02-01"))
        self.assertEqual(mw[11], ("2025-12-01", "2026-01-01"))
        self.assertEqual(mw[-1], ("2026-10-01", "2026-11-01"))


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        for name in ("protocol_wallet_follow_probe_20261127", "protocol_wallet_follow_probe_addendum_20261127"):
            p = STUDIES / (name + ".md")
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), p.with_suffix(".sha256").read_text().strip(),
                             "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
