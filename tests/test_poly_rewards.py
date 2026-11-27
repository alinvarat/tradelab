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
        self.assertAlmostEqual(rc.STANDALONE_DAILY, 0.0373, places=4)
        self.assertEqual(rc.after_min_payout(0.9), 0.0)
        self.assertEqual(rc.after_min_payout(1.0), 1.0)


def trade(t, price, idx=0, side="SELL", size=10):
    return {"t": t, "side": side, "idx": idx, "price": price, "size": size}


SH = lambda T, B, A: 0.5   # noqa: E731


class Simulation(unittest.TestCase):
    def run_sim(self, trades, **kw):
        args = dict(t0=0, t1=7200, v=4.0, frac=0.5, units=1, min_size=20.0, share_at=SH, mid_at=lambda T: 0.5, daily_pool=24.0)
        args.update(kw)
        return rc.simulate_market(trades, **args)

    def test_reward_only(self):
        out = self.run_sim([trade(100, 0.5)])
        day = out[0]
        self.assertAlmostEqual(day["reward"], 24.0 * 0.5 * 2 / 24)    # two hours
        self.assertEqual(day["fills"], 0)

    def test_touch_never_fills(self):
        # bid 0.48, ask 0.52: prints AT the limit or 0.05% through do not fill (rule: 0.1% through)
        for p in (0.48, 0.4796, 0.50):
            self.assertEqual(self.run_sim([trade(100, p)], t1=3600)[0]["fills"], 0, p)
        self.assertEqual(self.run_sim([trade(100, 0.52, idx=0, side="BUY")], t1=3600)[0]["fills"], 0)
        self.assertEqual(self.run_sim([trade(100, 0.48, idx=1, side="BUY")], t1=3600)[0]["fills"], 0)   # NO 0.48 = YES 0.52, a touch

    def test_through_fill_and_adverse_mark(self):
        # bid at 0.48 hit by a print at 0.47 (>0.1% through), size 10 of our 20: partial fill, then the price falls to 0.40
        out = self.run_sim([trade(100, 0.47), trade(3700, 0.40)], mark_s=3700, t1=3600)
        self.assertEqual(out[0]["fills"], 1)
        self.assertAlmostEqual(out[0]["filled_shares"], 10.0)
        self.assertAlmostEqual(out[0]["fill_pnl"], 10 * (0.40 - 0.005 - 0.48))

    def test_partial_fills_accumulate_to_size_and_stop(self):
        trs = [trade(100, 0.47, size=15), trade(200, 0.46, size=15), trade(300, 0.45, size=15), trade(3700, 0.40)]
        out = self.run_sim(trs, mark_s=3700, t1=3600)
        self.assertAlmostEqual(out[0]["filled_shares"], 20.0)      # 15 + 5, never more than the order
        self.assertEqual(out[0]["fills"], 2)

    def test_ask_fill_uses_yes_equivalent_of_no_trades(self):
        # NO trade at 0.47 = YES 0.53; the NO bid is 1 - 0.52 = 0.48, so 0.47 is through it
        out = self.run_sim([trade(100, 0.47, idx=1, side="BUY"), trade(3700, 0.60)], mark_s=3700, t1=3600)
        self.assertEqual(out[0]["fills"], 1)
        self.assertAlmostEqual(out[0]["fill_pnl"], 10 * (0.52 - 0.60 - 0.005))

    def test_no_quote_without_mid(self):
        self.assertEqual(self.run_sim([trade(100, 0.3)], mid_at=lambda T: None), {})

    def test_zero_reward_isolates_fill(self):
        out = self.run_sim([trade(100, 0.47), trade(3700, 0.40)], mark_s=3700, t1=3600, daily_pool=0.0)
        self.assertEqual(out[0]["reward"], 0.0)

    def test_reward_stops_when_a_side_is_filled(self):
        # whole bid taken at second 1800 of a 3600 s window sampled every 600 s: samples at 0, 600, 1200 count, 1800 does not
        out = self.run_sim([trade(1800, 0.47, size=100), trade(3700, 0.40)], mark_s=3700, t1=3600, reward_step=600)
        self.assertAlmostEqual(out[0]["reward"], 24.0 * 0.5 * 3 * 600 / 86400)

    def test_resolution_loss_at_high_price(self):
        # YES bid 0.94 on a 0.95 market, filled by a print at 0.93; the market resolves NO: the stake is lost, not -0.005
        mid = lambda T: 0.95   # noqa: E731
        trs = [trade(100, 0.93), trade(900, 0.945)]          # a benign later print: the 24 h mark looks fine
        res = self.run_sim(trs, mid_at=mid, v=4.0, frac=0.25, units=1, min_size=20.0, t1=3600, yes_won=False)
        self.assertAlmostEqual(res[0]["fill_pnl"], 10 * (0.0 - 0.94))
        self.assertGreater(res[0]["fill_pnl_mtm"], res[0]["fill_pnl"] + 8)    # the 24 h mark hides almost the whole loss
        won = self.run_sim(trs, mid_at=mid, v=4.0, frac=0.25, units=1, min_size=20.0, t1=3600, yes_won=True)
        self.assertAlmostEqual(won[0]["fill_pnl"], 10 * (1.0 - 0.94))
        self.assertEqual(won[0]["open_usd"], 0.0)
        open_ = self.run_sim(trs, mid_at=mid, v=4.0, frac=0.25, units=1, min_size=20.0, t1=3600)
        self.assertAlmostEqual(open_[0]["open_usd"], 10 * 0.94)               # unresolved inventory is reported
        st = self.run_sim(trs, mid_at=mid, v=4.0, frac=0.25, units=1, min_size=20.0, t1=3600, stress=True)
        self.assertAlmostEqual(st[0]["fill_pnl"], -10 * 0.94)                 # tail stress: unresolved >= 0.80 goes to 0

    def test_single_sided_only_inside_the_band(self):
        # mid 0.95: not eligible, no quote at all; mid 0.30: a YES bid only (cheaper token), no ask side
        self.assertEqual(self.run_sim([trade(100, 0.1)], mid_at=lambda T: 0.95, mode="single"), {})
        out = self.run_sim([trade(100, 0.5)], mid_at=lambda T: 0.30, mode="single", t1=3600)
        self.assertEqual(out[0]["fills"], 0)
        out = self.run_sim([trade(100, 0.1)], mid_at=lambda T: 0.30, mode="single", t1=3600)
        self.assertEqual(out[0]["fills"], 1)           # only the bid leg filled (10 of 20 shares)
        self.assertAlmostEqual(out[0]["filled_shares"], 10.0)

    def test_single_reward_stops_when_mid_leaves_band(self):
        mids = {0: 0.5, 600: 0.5, 1200: 0.95}
        out = self.run_sim([trade(5, 0.5)], mid_at=lambda T: mids.get(T, 0.5) if T < 1200 else 0.95, mode="single", t0=0, t1=3600,
                           reward_step=600, share_at=SH)
        # refresh at 0 quotes (mid 0.5, eligible); samples 0,600 pay, 1200..3000 are outside the band
        self.assertAlmostEqual(out[0]["reward"], 24.0 * 0.5 * 2 * 600 / 86400)

    def test_summary_and_equity(self):
        eq, dd = rc.equity_stats([0.1, -0.2, 0.05])
        self.assertAlmostEqual(eq, 1.1 * 0.8 * 1.05)
        self.assertAlmostEqual(dd, 0.2)
        per = {"a": {0: {"reward": 1.0, "fill_pnl": -0.5, "fills": 1, "quote_hours": 1}, 1: {"reward": 1.0, "fill_pnl": 0.0, "fills": 0, "quote_hours": 1}}}
        s = rc.summarise(per, 100.0)
        self.assertAlmostEqual(s["net_mean"], 0.0075)
        self.assertAlmostEqual(rc.monthly(0.0), 0.0)

    def test_reward_never_exceeds_the_allocation_bound(self):
        # reconciliation invariant: a market-day of full two-sided quoting pays at most pool x share (same formula as allocate)
        m = mk("a", pool=450.0, qc=2.1, mid=0.95, v=4.0, ms=20.0)
        gross = rc.reward_for(m, 1, 0.5, "two")
        q = rc.our_q(1, 20.0, 4.0, 2.0, 0.95, "two")
        out = rc.simulate_market([trade(100, 0.95)], 0, 86400, 4.0, 0.5, 1, 20.0, lambda T, B, A: q / (q + 2.1), lambda T: 0.95, 450.0)
        paid = sum(r["reward"] for r in out.values())
        self.assertLessEqual(paid, gross * (1 + 1e-9))
        self.assertAlmostEqual(paid, gross, places=6)


class Resolution(unittest.TestCase):
    def test_resolution_of(self):
        t = lambda a, b: {"closed": True, "tokens": [{"winner": a}, {"winner": b}]}   # noqa: E731
        self.assertIs(rc.resolution_of(t(True, False)), True)
        self.assertIs(rc.resolution_of(t(False, True)), False)
        self.assertIsNone(rc.resolution_of(t(False, False)))
        self.assertIsNone(rc.resolution_of(dict(t(True, False), closed=False)))
        self.assertIsNone(rc.resolution_of({}))


class Gaps(unittest.TestCase):
    def test_gaps_are_logged(self):
        ticks = list(range(0, 600, 60)) + list(range(1200, 1800, 60))
        g = rc.tick_gaps(ticks)
        self.assertEqual(g["n_gaps"], 1)
        self.assertEqual(g["gaps"][0], (540, 1200, 660))
        self.assertLess(g["coverage"], 0.7)
        self.assertEqual(rc.tick_gaps(list(range(0, 600, 60)))["n_gaps"], 0)


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
    def test_addendum_unchanged(self):
        add = STUDIES / "protocol_poly_rewards_addendum_20261127.md"
        self.assertEqual(hashlib.sha256(add.read_bytes()).hexdigest(), add.with_suffix(".sha256").read_text().strip())

    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
