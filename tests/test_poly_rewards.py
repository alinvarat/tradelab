import hashlib
import sys
import unittest
from pathlib import Path

STUDIES = Path(__file__).resolve().parents[1] / "research/studies"
sys.path.insert(0, str(STUDIES))
import poly_rewards_core as rc   # noqa: E402
import poly_rewards as pr        # noqa: E402

PROTO = STUDIES / "protocol_poly_rewards_20261126.md"


def book(bids, asks):
    return {"bids": [{"price": str(p), "size": str(s)} for p, s in bids], "asks": [{"price": str(p), "size": str(s)} for p, s in asks]}


class Score(unittest.TestCase):
    def test_score(self):
        self.assertAlmostEqual(rc.score(4, 0), 1.0)
        self.assertAlmostEqual(rc.score(4, 2), 0.25)
        self.assertEqual(rc.score(4, 4), 0.0)
        self.assertEqual(rc.score(4, -1), 0.0)

    def test_qmin(self):
        self.assertAlmostEqual(rc.qmin(9, 0, 0.5), 3.0)
        self.assertAlmostEqual(rc.qmin(9, 3, 0.5), 3.0)
        self.assertAlmostEqual(rc.qmin(9, 6, 0.5), 6.0)
        self.assertEqual(rc.qmin(9, 0, 0.95), 0.0)

    def test_band_and_competition(self):
        b = book([(0.49, 100), (0.40, 100)], [(0.51, 100)])
        mid, qc = rc.competition(b, 4.0)
        self.assertAlmostEqual(mid, 0.5)
        q1, q2 = rc.band_q(*rc.top_of_book(b)[2:], 0.5, 4.0)
        self.assertAlmostEqual(q1, 100 * 0.5625)    # s = 1 cent; the 10-cent bid is outside the band
        self.assertAlmostEqual(q2, 100 * 0.5625)
        self.assertAlmostEqual(qc, 56.25)
        self.assertEqual(rc.competition(book([], [(0.5, 1)]), 4.0), (None, None))


def mk(cond, pool=50.0, qc=100.0, mid=0.5, v=4.0, ms=20.0):
    return {"cond": cond, "pool": pool, "qc": qc, "mid": mid, "v": v, "min_size": ms}


class Allocation(unittest.TestCase):
    def test_costs(self):
        self.assertAlmostEqual(rc.unit_cost(0.5, 20, 2.0, "two"), 20 * 0.96)
        self.assertAlmostEqual(rc.unit_cost(0.3, 20, 2.0, "single"), 20 * 0.28)

    def test_budget_and_share(self):
        k, gross, spent = rc.allocate([mk("a"), mk("b", pool=10)], 0.5, "two")
        self.assertLessEqual(spent, rc.BUDGET)
        self.assertGreater(gross, 0)
        self.assertGreaterEqual(k["a"], k.get("b", 0))
        one = rc.reward_for(mk("a"), 1, 0.5, "two")
        two = rc.reward_for(mk("a"), 2, 0.5, "two")
        self.assertGreater(two, one)
        self.assertLess(two, 2 * one)             # own size dilutes the share
        self.assertLess(two, 50.0)

    def test_qualify_rules(self):
        self.assertFalse(rc.qualifies(mk("x", mid=0.95), 0.5, "single"))
        self.assertFalse(rc.qualifies(mk("x", mid=0.995), 0.5, "two"))
        self.assertFalse(rc.qualifies(mk("x", ms=400), 0.5, "two"))
        self.assertEqual(rc.reward_for(mk("x", mid=0.95), 1, 0.5, "single"), 0.0)

    def test_single_scores_third(self):
        m = mk("a", qc=0.0)
        self.assertAlmostEqual(rc.our_q(1, 20, 4, 2, 0.5, "single") * 3, rc.our_q(1, 20, 4, 2, 0.5, "two"))

    def test_decide_and_payout(self):
        self.assertEqual(rc.decide([{"gross_pct": 0.004, "n_qualifying": 50}]), "kill_complete")
        self.assertEqual(rc.decide([{"gross_pct": 0.02, "n_qualifying": 5}]), "kill_complete")
        self.assertEqual(rc.decide([{"gross_pct": 0.02, "n_qualifying": 50}]), "kill_standalone")
        self.assertEqual(rc.decide([{"gross_pct": 0.04, "n_qualifying": 50}]), "standalone_pass")
        self.assertAlmostEqual(rc.STANDALONE_DAILY, 0.037312, places=5)
        self.assertEqual(rc.after_min_payout(0.9), 0.0)
        self.assertEqual(rc.after_min_payout(1.0), 1.0)


def trade(t, price, idx=0, side="SELL", size=10):
    return {"t": t, "side": side, "idx": idx, "price": price, "size": size}


class Simulation(unittest.TestCase):
    def run_sim(self, trades, **kw):
        args = dict(t0=0, t1=7200, v=4.0, frac=0.5, units=1, min_size=20.0, share_at=lambda T: 0.5, mid_at=lambda T: 0.5,
                    daily_pool=24.0)
        args.update(kw)
        return rc.simulate_market(trades, **args)

    def test_reward_only(self):
        out = self.run_sim([trade(100, 0.5)])
        day = out[0]
        self.assertAlmostEqual(day["reward"], 24.0 * 0.5 * 2 / 24)    # two hours
        self.assertEqual(day["fills"], 0)

    def test_bid_fill_and_adverse_mark(self):
        # bid at 0.48 hit at t=100, the price then falls to 0.40: loss (0.40 - 0.005 - 0.48) x 20
        out = self.run_sim([trade(100, 0.48), trade(3000, 0.40)], mark_s=3000, t1=3600)
        self.assertEqual(out[0]["fills"], 1)
        self.assertAlmostEqual(out[0]["fill_pnl"], 20 * (0.40 - 0.005 - 0.48))

    def test_ask_fill_uses_yes_equivalent_of_no_trades(self):
        # a NO trade at 0.48 = YES 0.52 >= our ask 0.52
        out = self.run_sim([trade(100, 0.48, idx=1, side="BUY"), trade(3000, 0.60)], mark_s=3000, t1=3600)
        self.assertEqual(out[0]["fills"], 1)
        self.assertAlmostEqual(out[0]["fill_pnl"], 20 * (0.52 - 0.60 - 0.005))

    def test_no_touch_no_fill_and_no_quote_without_mid(self):
        self.assertEqual(self.run_sim([trade(100, 0.49)])[0]["fills"], 0)
        self.assertEqual(self.run_sim([trade(100, 0.3)], mid_at=lambda T: None), {})

    def test_zero_reward_isolates_fill(self):
        out = self.run_sim([trade(100, 0.48), trade(3000, 0.40)], mark_s=3000, t1=3600, daily_pool=0.0)
        self.assertEqual(out[0]["reward"], 0.0)

    def test_summary_and_equity(self):
        eq, dd = rc.equity_stats([0.1, -0.2, 0.05])
        self.assertAlmostEqual(eq, 1.1 * 0.8 * 1.05)
        self.assertAlmostEqual(dd, 0.2)
        per = {"a": {0: {"reward": 1.0, "fill_pnl": -0.5, "fills": 1, "quote_hours": 1}, 1: {"reward": 1.0, "fill_pnl": 0.0, "fills": 0, "quote_hours": 1}}}
        s = rc.summarise(per, 100.0)
        self.assertAlmostEqual(s["net_mean"], 0.0075)
        self.assertAlmostEqual(rc.monthly(0.0), 0.0)


class Parse(unittest.TestCase):
    def test_parse_reward_market(self):
        row = {"condition_id": "0xabc", "accepting_orders": True, "closed": False, "question": "Q?",
               "tokens": [{"token_id": "1"}, {"token_id": "2"}],
               "rewards": {"rates": [{"asset_address": "0x1", "rewards_daily_rate": 5}, {"rewards_daily_rate": "2.5"}], "min_size": 20, "max_spread": 3.5}}
        m = pr.parse_reward_market(row)
        self.assertEqual((m["cond"], m["yes"], m["pool"], m["min_size"], m["v"]), ("0xabc", "1", 7.5, 20.0, 3.5))
        self.assertIsNone(pr.parse_reward_market(dict(row, rewards={"rates": [], "min_size": 1, "max_spread": 1})))
        self.assertIsNone(pr.parse_reward_market(dict(row, closed=True)))
        self.assertIsNone(pr.parse_reward_market({}))

    def test_shape_has_no_values(self):
        self.assertEqual(pr.shape({"a": 1, "b": [{"c": "x"}]}), {"a": "int", "b": [{"c": "str"}]})


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
