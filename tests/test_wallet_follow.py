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


def pos(cond, token="a", cost=1000.0, bought=2000.0, sold=0.0, proceeds=0.0, t0=100, px0=0.5, usd0=1000.0, t1=None, px1=None, both=False):
    return {"cond": cond, "token": token, "cost": cost, "bought": bought, "sold": sold, "proceeds": proceeds, "t0": t0, "px0": px0, "usd0": usd0,
            "t1": t1, "px1": px1, "both": both}


class Protocol(unittest.TestCase):
    def test_full_positions_and_both(self):
        rows = [row(10, "BUY", 0.4, 1000, cond="c", token="a"), row(20, "BUY", 0.6, 500, cond="c", token="a"), row(30, "SELL", 0.9, 700, cond="c", token="a"),
                row(40, "BUY", 0.3, 100, cond="c", token="b"), row(50, "SELL", 0.5, 5, cond="z", token="a")]
        ps = {(p["cond"], p["token"]): p for p in wc.full_positions(rows)}
        a = ps[("c", "a")]
        self.assertAlmostEqual(a["cost"], 700.0)
        self.assertEqual((a["t0"], a["px0"], a["usd0"], a["t1"], a["px1"]), (10, 0.4, 400.0, 30, 0.9))
        self.assertTrue(a["both"] and ps[("c", "b")]["both"])
        self.assertNotIn(("z", "a"), ps)                              # a sell without a buy is not a position

    def test_realize(self):
        info = {"closed_at": 1000, "payout": {"a": 1.0, "b": 0.0}}
        held = pos("c", cost=500, bought=1000, px0=0.5)
        self.assertEqual(wc.realize(held, info), (1000, 500.0, "resolved"))
        lost = pos("c", token="b", cost=500, bought=1000)
        self.assertEqual(wc.realize(lost, info), (1000, -500.0, "resolved"))
        out = pos("c", cost=500, bought=1000, sold=1000, proceeds=800, t1=300, px1=0.8)
        self.assertEqual(wc.realize(out, None), (300, 300.0, "exit"))
        self.assertIsNone(wc.realize(held, {"closed_at": None, "payout": {}}))                # open
        self.assertIsNone(wc.realize(held, {"closed_at": 5, "payout": {"a": 0.5}}))           # voided / not 0 or 1
        part = pos("c", cost=500, bought=1000, sold=400, proceeds=300, t1=200, px1=0.75)
        self.assertEqual(wc.realize(part, info), (1000, 300 + 600 * 1.0 - 500, "resolved"))

    def _wallet(self, n, pnl, cost=1000.0, closed=500, both=False):
        return [(pos(f"c{i}", cost=cost, both=both), closed, pnl, "resolved") for i in range(n)]

    def test_rank_eligibility_and_order(self):
        D = 100 * wc.DAY
        ws = {"a": self._wallet(60, 10.0, closed=D - 5), "b": self._wallet(60, 30.0, closed=D - 5), "few": self._wallet(49, 99.0, closed=D - 5),
              "small": self._wallet(60, 99.0, cost=100.0, closed=D - 5), "mm": self._wallet(60, 99.0, closed=D - 5, both=True),
              "future": self._wallet(60, 99.0, closed=D + 5), "old": self._wallet(60, 99.0, closed=D - 181 * wc.DAY)}
        r = wc.rank_at(ws, D)
        self.assertEqual([x[0] for x in r], ["b", "a"])               # only closed-before-D positions in the 180-day window count
        self.assertAlmostEqual(r[0][1], 1800.0)

    def test_pools(self):
        ranked = [(f"w{i:03d}", 1000 - i, 60, 1e5, 0.1) for i in range(300)]
        pl = wc.pools(ranked, "2025-04-01")
        self.assertEqual((len(pl["top"]), len(pl["bottom"]), len(pl["rand"])), (50, 50, 100))
        self.assertEqual(pl["top"][0], "w000")
        self.assertEqual(pl["bottom"][-1], "w299")
        self.assertFalse(set(pl["rand"]) & (set(pl["top"]) | set(pl["bottom"])))
        self.assertEqual(pl, wc.pools(ranked, "2025-04-01"))
        self.assertIsNone(wc.pools(ranked[:149], "2025-04-01"))

    def test_signals_filters(self):
        info = {"c1": {"closed_at": 9000, "payout": {"a": 1.0}, "fee": False}, "c2": {"closed_at": 9000, "payout": {"a": 1.0}, "fee": True}}
        ps = [pos("c1", t0=150), pos("c1", token="x", t0=150, usd0=499.0), pos("c1", token="y", t0=150, px0=0.97),
              pos("c2", t0=150), pos("c3", t0=150), pos("c1", token="z", t0=50),
              pos("c1", token="w", t0=160, sold=2000, proceeds=1600, t1=400, px1=0.8)]
        es, dr = wc.signals(ps, info, 100, 200)
        self.assertEqual(dr, {"small": 1, "band": 1, "fee": 1, "open": 1})
        self.assertEqual(len(es), 2)
        self.assertFalse(es[0]["own_exit"])
        self.assertTrue(es[1]["own_exit"] and es[1]["t1"] == 400 and es[1]["pw1"] == 0.8)

    def test_fill_rules(self):
        tape = [{"t": 130, "side": "BUY", "token": "a", "price": 0.99}, {"t": 170, "side": "BUY", "token": "b", "price": 0.1},
                {"t": 175, "side": "BUY", "token": "a", "price": 0.52}, {"t": 5000, "side": "BUY", "token": "a", "price": 0.5}]
        e = {"cond": "c", "token": "a", "t0": 100, "pw": 0.50, "own_exit": False, "payout": 1.0, "closed_at": 9000}
        self.assertAlmostEqual(wc.price_entry(e, tape), 0.52)                    # first BUY at >= 160 s; worse of 0.52 and 0.51
        self.assertAlmostEqual(wc.price_entry(dict(e, pw=0.52), tape), 0.53)     # the wallet's price + 1 cent is worse
        self.assertIsNone(wc.price_entry(dict(e, t0=3000), tape[:3]))            # nothing within 30 minutes
        self.assertIsNone(wc.price_entry(dict(e, pw=0.965), tape))               # 0.975 is above the 0.97 cap: no fill
        self.assertAlmostEqual(wc.price_entry(dict(e, pw=0.95, t0=4900), tape), 0.96)

    def test_trade_resolved_and_exit(self):
        e = {"cond": "c", "token": "a", "t0": 100, "pw": 0.50, "own_exit": False, "payout": 1.0, "closed_at": 9000, "wallet": "w"}
        tr = wc.make_trade(e, 0.52, [])
        self.assertAlmostEqual(tr["net"], (1 - 0.52) / 0.52)
        self.assertAlmostEqual(tr["gross"], 1.0)
        self.assertAlmostEqual(tr["cost"], 1.0 - (1 - 0.52) / 0.52)
        self.assertEqual(tr["x"], 9000)
        lose = wc.make_trade(dict(e, payout=0.0), 0.52, [])
        self.assertAlmostEqual(lose["net"], -1.0)
        ex = dict(e, own_exit=True, t1=1000, pw1=0.70)
        tape = [{"t": 1062, "side": "SELL", "token": "a", "price": 0.66}]
        t2 = wc.make_trade(ex, 0.52, tape)
        self.assertAlmostEqual(t2["net"], (0.66 - 0.52) / 0.52)                  # worse of 0.66 and 0.70 - 0.01 = 0.69
        self.assertEqual(t2["x"], 1062)
        t3 = wc.make_trade(ex, 0.52, [])
        self.assertAlmostEqual(t3["net"], (0.68 - 0.52) / 0.52)                  # no tape sell: their price - 0.02
        self.assertIsNone(wc.make_trade(dict(ex, t1=120), 0.52, []))             # they left before our delayed fill

    def test_cluster_moments_x(self):
        ts = [{"t": 1, "x": 5, "cond": "c1", "net": 0.2, "gross": 0.3, "cost": 0.1, "fund": 0, "mfe": 1, "mae": 1, "entry": 0.5},
              {"t": 2, "x": 9, "cond": "c1", "net": 0.0, "gross": 0.1, "cost": 0.1, "fund": 0, "mfe": 1, "mae": 1, "entry": 0.5},
              {"t": 3, "x": 4, "cond": "c2", "net": -0.4, "gross": -0.3, "cost": 0.1, "fund": 0, "mfe": 1, "mae": 1, "entry": 0.5},
              {"t": 4, "x": 4, "cond": "c3", "net": 0.3, "gross": 0.4, "cost": 0.1, "fund": 0, "mfe": 1, "mae": 1, "entry": 0.5}]
        c = wc.cluster(ts)
        self.assertEqual(len(c), 3)
        self.assertAlmostEqual(c[0]["net"], 0.1)
        self.assertEqual((c[0]["t"], c[0]["x"], c[0]["k"]), (1, 9, 2))
        m = wc.moments(c, 3)
        self.assertEqual(m["n"], 3)
        self.assertAlmostEqual(m["mean"], 0.0)
        self.assertAlmostEqual(m["N"], 1.0)
        m2 = wc.moments([{"net": 0.1}, {"net": 0.3}], 1)                    # mean 0.2, sd 0.1414, s 1.414, N 2, x = 2 * 2 = 4
        self.assertAlmostEqual(m2["x"], 4.0)
        self.assertAlmostEqual(wc.moments([{"net": -0.1}, {"net": -0.3}], 1)["x"], -4.0)
        self.assertAlmostEqual(wc.top_share([{"net": 1.0}] + [{"net": 0.01}] * 99), 1.0 / 1.99)
        self.assertIsNone(wc.top_share([{"net": -1.0}]))
        cx, ncap, mh = wc.capped_x([{"net": 0.1, "t": 0, "x": 10 * wc.DAY}, {"net": 0.3, "t": 0, "x": 10 * wc.DAY}], 1)
        self.assertAlmostEqual(ncap, 60.0)                                   # 20 stakes x 30 / 10 days
        self.assertAlmostEqual(cx, 4.0)                                      # N = 2 is below the cap

    def test_spearman_and_persistence(self):
        self.assertAlmostEqual(wc.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(wc.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertIsNone(wc.spearman([1, 2], [1, 2]))
        self.assertIsNone(wc.spearman([1, 1, 1], [1, 2, 3]))
        D = 200 * wc.DAY
        ws = {}
        for i in range(60):                                                   # a wallet's past score and future ROI move together
            past = [(pos(f"p{i}_{j}", cost=1000.0), D - 10, (i - 30) * 2.0, "resolved") for j in range(60)]
            fut = [(pos(f"f{i}_{j}", cost=1000.0, t0=D + 10), D + 20, (i - 30) * 1.0, "resolved") for j in range(10)]
            ws[f"w{i:02d}"] = past + fut
        r = wc.persistence(ws, D, D + 90 * wc.DAY)
        self.assertEqual(r["eligible"], 60)
        self.assertGreater(r["rho"], 0.99)
        self.assertGreater(r["top_median"], r["all_median"])
        self.assertFalse(wc.persistence_verdict([r])["kill"])
        self.assertTrue(wc.persistence_verdict([dict(r, rho=-0.1)])["kill"])
        self.assertTrue(wc.persistence_verdict([dict(r, top_median=0.0, all_median=0.1)])["kill"])
        self.assertTrue(wc.persistence_verdict([])["kill"])

    def test_permutation(self):
        top = {f"t{i}": [0.5, 0.4] for i in range(5)}
        rnd = {f"r{i}": [-0.1, 0.0] for i in range(10)}
        bm = {"m1": {"wallets": {**top, **rnd}, "top": set(top)}}
        d, p = wc.permutation_p(bm, n_perm=500)
        self.assertGreater(d, 0.4)
        self.assertLess(p, 0.01)
        same = {f"t{i}": [0.1] for i in range(5)}
        same.update({f"r{i}": [0.1] for i in range(10)})
        d2, p2 = wc.permutation_p({"m1": {"wallets": same, "top": {f"t{i}" for i in range(5)}}}, n_perm=200)
        self.assertGreater(p2, 0.9)

    def test_dates_and_shards(self):
        self.assertEqual(len(wc.FOLLOW_MONTHS), 19)
        self.assertEqual((wc.FOLLOW_MONTHS[0], wc.FOLLOW_MONTHS[-1]), ("2025-04-01", "2026-10-01"))
        self.assertEqual(wc.month_end("2025-12-01"), wc.ts_day("2026-01-01"))
        self.assertEqual(wc.split_of(wc.ts_day("2025-12-31")), "train")
        self.assertEqual(wc.split_of(wc.ts_day("2026-01-01")), "validation")
        self.assertEqual(wc.split_of(wc.ts_day("2026-06-01")), "test")
        self.assertIsNone(wc.split_of(wc.ts_day("2026-11-01")))
        self.assertTrue(all(0 <= wf.shard_of(f"x{i}") < wf.SHARDS for i in range(50)))
        self.assertEqual(wf.shard_of("abc"), wf.shard_of("abc"))

    def test_trade_feeds_sweep_gate(self):
        from core import sweep_stats as ss
        tr = []
        for i in range(60):
            win = i % 3 != 0
            e = {"cond": f"c{i}", "token": "a", "t0": 1000 + i, "pw": 0.5, "own_exit": False, "payout": 1.0 if win else 0.0, "closed_at": 5000}
            t = wc.make_trade(e, 0.52, [])
            t["t"] = e["t0"]
            tr.append(t)
        ok, info = ss.gate(wc.cluster(tr), {"size": {"lev": 1, "k": 10}}, {"gate": {"min_train_trades": 30}, "account_usd": 147.0}, 275.0)
        self.assertIn("n_train", info)                                       # the trade dicts carry every field the gate reads
        self.assertEqual(info["n_train"], 60)


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
        for name in ("protocol_wallet_follow_probe_20261127", "protocol_wallet_follow_probe_addendum_20261127",
                     "protocol_wallet_follow_probe_addendum2_20261127", "protocol_wallet_follow_probe_addendum3_20261127", "protocol_wallet_follow_20261127"):
            p = STUDIES / (name + ".md")
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), p.with_suffix(".sha256").read_text().strip(),
                             "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
