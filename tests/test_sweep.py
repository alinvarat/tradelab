import gzip
import json
import math
import os
import random
import tempfile
import unittest
from unittest import mock

from core import sweep_board as sb
from core import sweep_config as sc
from core import sweep_engine as se
from core import sweep_stats as ss
from research.sweeps import hooks

T0 = 1_704_067_200          # 2024-01-01 00:00 UTC, a Monday
NAN = float("nan")
FREE = {"model": "perp", "fee": 0.0, "slip": 0.0}


def mkbars(o, h, l, c, fund=None, t0=T0, step=3600):
    n = len(c)
    return {"ts": [t0 + i * step for i in range(n)], "o": list(o), "h": list(h), "l": list(l), "c": list(c),
            "v": [10.0] * n, "tb": [6.0] * n, "fund": list(fund) if fund else [0.0] * n, "prem": None}


def from_closes(closes, fund=None, step=3600, t0=T0):
    o = [closes[0]] + closes[:-1]
    h = [max(a, b) for a, b in zip(o, closes)]
    l = [min(a, b) for a, b in zip(o, closes)]
    return mkbars(o, h, l, closes, fund, t0, step)


def walk(n, seed=1, vol=0.004):
    r = random.Random(seed)
    p, out = 100.0, []
    for _ in range(n):
        p *= 1 + r.gauss(0, vol)
        out.append(p)
    return out


def sig(n, *idx):
    return [i in idx for i in range(n)]


def rule(exit_, cost=FREE, k=1, lev=1, entry=None):
    r = {"exit": exit_, "size": {"lev": lev, "k": k}, "cost": cost}
    if entry:
        r["entry"] = entry
    return r


def same(a, b):
    return all((x != x and y != y) or x == y for x, y in zip(a, b)) and len(a) == len(b)


class Rolling(unittest.TestCase):
    def test_basic(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(se.roll_sum(x, 2)[1:], [3.0, 5.0, 7.0, 9.0])
        self.assertTrue(math.isnan(se.roll_sum(x, 2)[0]))
        self.assertEqual(se.roll_mean(x, 3)[2:], [2.0, 3.0, 4.0])
        self.assertAlmostEqual(se.roll_std([1.0, 3.0], 2)[1], 1.0)
        self.assertEqual(se.roll_max([1, 3, 2, 5, 4], 2)[1:], [3, 3, 5, 5])
        self.assertEqual(se.roll_min([1, 3, 2, 5, 4], 2)[1:], [1, 2, 2, 4])
        self.assertTrue(same(se.shift([1.0, 2.0, 3.0], 1), [NAN, 1.0, 2.0]))

    def test_nan_window_gives_nan(self):
        self.assertTrue(math.isnan(se.roll_mean([1.0, NAN, 3.0, 4.0], 2)[2]))
        self.assertEqual(se.roll_mean([1.0, NAN, 3.0, 4.0], 2)[3], 3.5)

    def test_pct_rank(self):
        out = se.pct_rank([1.0, 2.0, 3.0, 2.5], 3)
        self.assertTrue(math.isnan(out[2]))
        self.assertAlmostEqual(out[3], 2 / 3)       # 2.5 beats 1, 2 but not 3


class Features(unittest.TestCase):
    def ctx(self, n=400):
        a, b = walk(n, 1), walk(n, 2)
        da, db = from_closes(a), from_closes(b)
        da["fund"] = [0.0001 if i % 8 == 0 else 0.0 for i in range(n)]
        da["prem"] = [0.001 * math.sin(i / 7) for i in range(n)]
        da["m"] = {k: [1.0 + 0.5 * math.sin(i / (5 + j)) for i in range(n)] for j, k in enumerate(se.METRIC_NAMES)}
        return se.Ctx({"A": da, "B": db})

    CONDS = [{"f": "ret", "n": 3}, {"f": "zret", "n": 2, "vol_n": 20}, {"f": "atrp", "n": 10}, {"f": "atr_ratio", "a": 3, "b": 20},
             {"f": "nr", "n": 5}, {"f": "inside"}, {"f": "brk"}, {"f": "clv"}, {"f": "body"}, {"f": "streak"}, {"f": "gap"},
             {"f": "intra"}, {"f": "dd", "n": 20}, {"f": "runup", "n": 20}, {"f": "rngpct", "lb": 30}, {"f": "rvpct", "n": 5, "lb": 30},
             {"f": "volz", "n": 10}, {"f": "taker", "n": 3}, {"f": "takerz", "n": 2, "lb": 30}, {"f": "hour"}, {"f": "dow"}, {"f": "dom"},
             {"f": "fundlast"}, {"f": "fsum", "n": 8}, {"f": "fz", "n": 30}, {"f": "prem"}, {"f": "premz", "n": 20},
             {"f": "xret", "ref": "B", "n": 2}, {"f": "xzret", "ref": "B", "n": 2, "vol_n": 20}, {"f": "rel", "ref": "B", "n": 4},
             {"f": "ratio_mom", "ref": "B", "n": 5}, {"f": "sma_dist", "n": 20}, {"f": "pd_sweep"}, {"f": "asia_sweep"},
             {"f": "orb", "hours": 4}, {"f": "rnd", "step": 5.0}, {"f": "mval", "m": "oi"},
             {"f": "mz", "m": "top_pos", "n": 20}, {"f": "mchg", "m": "oi", "n": 3}]

    def test_no_lookahead(self):
        full = self.ctx(400)
        cut = 260
        def cutv(vv):
            if vv is None:
                return None
            return {a: b[:cut] for a, b in vv.items()} if isinstance(vv, dict) else vv[:cut]
        part = se.Ctx({k: {kk: cutv(vv) for kk, vv in d.items()} for k, d in full.bars.items()})
        for c in self.CONDS:
            a = full.series("A", c)[:cut]
            b = part.series("A", c)
            self.assertTrue(same(a, b), c)

    def test_every_registered_feature_is_covered(self):
        self.assertEqual(sorted(se.FEATURES), sorted({c["f"] for c in self.CONDS}))

    def test_known_values(self):
        d = mkbars([100, 100, 100], [101, 101, 101], [99, 99, 99], [100, 101, 99])
        ctx = se.Ctx({"A": d})
        self.assertEqual(ctx.series("A", {"f": "clv"}), [0.0, 1.0, -1.0])
        self.assertEqual(ctx.series("A", {"f": "streak"}), [0.0, 1.0, -1.0])
        self.assertEqual(ctx.series("A", {"f": "hour"}), [0.0, 1.0, 2.0])
        self.assertEqual(ctx.series("A", {"f": "dow"})[0], 0.0)

    def test_pd_sweep(self):
        # day 1: 24 bars range 99..101; day 2 first bar dips to 98.5 and closes 99.5 (reclaim) -> +1
        n = 48
        o = h = l = c = None
        o = [100.0] * n
        h = [101.0] * 24 + [100.5] * 24
        l = [99.0] * 24 + [99.5] * 24
        c = [100.0] * n
        l[24], c[24] = 98.5, 99.5
        h[30], c[30] = 101.5, 100.5       # sweeps the prior high 101 and closes back below it -> -1
        ctx = se.Ctx({"A": mkbars(o, h, l, c)})
        s = ctx.series("A", {"f": "pd_sweep"})
        self.assertTrue(math.isnan(s[0]))
        self.assertEqual((s[24], s[30], s[25]), (1.0, -1.0, 0.0))

    def test_mirror(self):
        self.assertEqual(se.mirror_cond({"f": "ret", "gt": 0.02}), {"f": "ret", "lt": -0.02})
        self.assertEqual(se.mirror_cond({"f": "ret", "between": [0.01, 0.03]}), {"f": "ret", "between": [-0.03, -0.01]})
        self.assertEqual(se.mirror_cond({"f": "nr", "n": 7, "eq": 1.0}), {"f": "nr", "n": 7, "eq": 1.0})
        with self.assertRaises(ValueError):
            se.mirror_cond({"f": "hour", "in": [1]})

    def test_conditions_and_lag(self):
        ctx = se.Ctx({"A": from_closes([100, 101, 102, 101, 100, 99])})
        up = se.signal(ctx, "A", [{"f": "ret", "n": 1, "gt": 0.0}])
        self.assertEqual(up, [False, True, True, False, False, False])
        lagged = se.signal(ctx, "A", [{"f": "ret", "n": 1, "gt": 0.0, "lag": 1}])
        self.assertEqual(lagged, [False, False, True, True, False, False])
        both = se.signal(ctx, "A", [{"f": "ret", "n": 1, "gt": 0.0}, {"f": "hour", "in": [2]}])
        self.assertEqual(both, [False, False, True, False, False, False])
        with self.assertRaises(ValueError):
            se.cond_op({"f": "ret", "gt": 1, "lt": 2})


class Simulation(unittest.TestCase):
    def run1(self, d, long_idx, rl, short_idx=(), t_to=10**12):
        n = len(d["ts"])
        return se.simulate_symbol(d, "X", sig(n, *long_idx), sig(n, *short_idx), rl, 0, t_to, se.make_cost_fn(rl))

    def test_time_exit_next_open(self):
        d = from_closes([100, 100, 100, 101, 102, 103, 104, 105])
        t = self.run1(d, [2], rule({"time": 2}))
        self.assertEqual(len(t), 1)
        self.assertEqual((t[0]["ep"], t[0]["xp"]), (100, 102))
        self.assertAlmostEqual(t[0]["gross"], 0.02)
        self.assertEqual((t[0]["t"], t[0]["x"]), (d["ts"][2], d["ts"][5]))

    def test_short_sign(self):
        d = from_closes([100, 100, 100, 101, 102, 103, 104, 105])
        t = self.run1(d, [], rule({"time": 2}), short_idx=[2])
        self.assertAlmostEqual(t[0]["gross"], -0.02)

    def test_both_sides_cancel(self):
        d = from_closes([100] * 8)
        self.assertEqual(self.run1(d, [2], rule({"time": 2}), short_idx=[2]), [])

    def test_stop_priority_and_fill(self):
        o = [100, 100, 100, 100, 100, 100, 100, 100]
        h = [100, 100, 100, 100, 103, 100, 100, 100]
        l = [100, 100, 100, 100, 98, 100, 100, 100]
        c = [100] * 8
        d = mkbars(o, h, l, c)
        t = self.run1(d, [2], rule({"time": 4, "stop": {"pct": 0.01}, "target": {"pct": 0.02}}))
        self.assertEqual((t[0]["reason"], round(t[0]["xp"], 6)), ("stop", 99.0))      # stop wins when both are hit in one bar
        self.assertAlmostEqual(t[0]["gross"], -0.01)
        self.assertAlmostEqual(t[0]["mae"], 0.02)

    def test_gap_through_stop_fills_at_open(self):
        o = [100, 100, 100, 100, 97, 97, 97, 97]
        d = mkbars(o, o, o, o)
        t = self.run1(d, [2], rule({"time": 4, "stop": {"pct": 0.01}}))
        self.assertEqual(t[0]["xp"], 97)

    def test_target(self):
        o = [100] * 8
        h = [100, 100, 100, 100, 103, 100, 100, 100]
        d = mkbars(o, h, [100] * 8, [100] * 8)
        t = self.run1(d, [2], rule({"time": 4, "target": {"pct": 0.02}}))
        self.assertEqual((t[0]["reason"], round(t[0]["xp"], 6)), ("target", 102.0))

    def test_trailing_stop_ratchets(self):
        o = [100, 100, 100, 100, 104, 108, 104, 100, 100, 100]
        c = [100, 100, 100, 104, 108, 104, 100, 100, 100, 100]
        h = [max(a, b) for a, b in zip(o, c)]
        l = [min(a, b) for a, b in zip(o, c)]
        d = mkbars(o, h, l, c)
        t = self.run1(d, [2], rule({"time": 6, "trail": {"pct": 0.03}}))
        self.assertEqual(t[0]["reason"], "stop")
        self.assertGreater(t[0]["xp"], 100)            # stop followed the price up, so the exit is a gain

    def test_atr_stop_needs_atr(self):
        d = from_closes(walk(60, 3))
        t = self.run1(d, [2], rule({"time": 3, "stop": {"atr": 2.0}}))
        self.assertEqual(t, [])                          # ATR(14) is not defined at bar 2: the signal is skipped
        t = self.run1(d, [30], rule({"time": 3, "stop": {"atr": 2.0}}))
        self.assertEqual(len(t), 1)

    def test_funding_charged_on_held_bars_only(self):
        fund = [0, 0, 0, 0.001, 0.001, 0, 0, 0]
        d = from_closes([100] * 8, fund=fund)
        t = self.run1(d, [2], rule({"time": 2}))          # holds bars 3 and 4
        self.assertAlmostEqual(t[0]["fund"], 0.002)
        self.assertAlmostEqual(t[0]["net"], -0.002)
        s = self.run1(d, [], rule({"time": 2}), short_idx=[2])
        self.assertAlmostEqual(s[0]["fund"], -0.002)      # a short receives positive funding

    def test_costs_and_2x(self):
        d = from_closes([100] * 8)
        rl = rule({"time": 2}, cost={"model": "perp", "fee": 0.0005, "slip": 0.0002})
        t = self.run1(d, [2], rl)
        self.assertAlmostEqual(t[0]["cost"], 0.0014)
        self.assertAlmostEqual(t[0]["net"] - t[0]["cost"], -0.0028)

    def test_xm_cost_matches_broker_costs(self):
        from core import broker_costs as bc
        f = se.make_cost_fn({"cost": {"model": "xm", "account": "standard"}})
        self.assertAlmostEqual(f("EURUSD=X", 1.1, 2.0), bc.xm_cfd_cost_fraction("EURUSD", "standard", 1.1, nights=2.0)["round_trip"])

    def test_overnight_and_intraday_phases(self):
        o = [100, 100, 102, 102, 105]
        c = [100, 101, 102, 104, 105]
        d = mkbars(o, [max(a, b) for a, b in zip(o, c)], [min(a, b) for a, b in zip(o, c)], c, step=86400)
        ovn = self.run1(d, [1], rule({"time": 1, "on": "open"}, entry="close"))
        self.assertEqual((ovn[0]["ep"], ovn[0]["xp"]), (101, 102))                 # close of bar 1 -> open of bar 2
        intr = self.run1(d, [1], rule({"time": 1, "on": "close"}))
        self.assertEqual((intr[0]["ep"], intr[0]["xp"]), (102, 102))               # open of bar 2 -> close of bar 2
        intr3 = self.run1(d, [2], rule({"time": 1, "on": "close"}))
        self.assertEqual((intr3[0]["ep"], intr3[0]["xp"]), (102, 104))

    def test_no_overlap_and_back_to_back(self):
        d = from_closes([100 + i for i in range(20)])
        t = self.run1(d, range(0, 19), rule({"time": 2}))
        self.assertEqual([x["t"] for x in t][:3], [d["ts"][0], d["ts"][2], d["ts"][4]])    # each new trade starts when the last one ends

    def test_trade_dropped_when_exit_beyond_data(self):
        d = from_closes([100] * 6)
        self.assertEqual(self.run1(d, [4], rule({"time": 3})), [])

    def test_signals_limited_to_window(self):
        d = from_closes([100] * 12)
        n = 12
        t = se.simulate_symbol(d, "X", sig(n, 1, 6), sig(n), rule({"time": 1}), d["ts"][3], d["ts"][9], se.make_cost_fn(rule({"time": 1})))
        self.assertEqual([x["t"] for x in t], [d["ts"][6]])

    def test_cap(self):
        mk = lambda sym, t, x: {"sym": sym, "t": t, "te": t, "x": x}   # noqa: E731
        keep = se.apply_cap([mk("A", 0, 10), mk("B", 5, 8), mk("C", 9, 12), mk("D", 11, 13)], 1)
        self.assertEqual([k["sym"] for k in keep], ["A", "D"])
        keep2 = se.apply_cap([mk("A", 0, 10), mk("B", 5, 8), mk("C", 9, 12)], 2)
        self.assertEqual([k["sym"] for k in keep2], ["A", "B", "C"])     # B has left by the time C enters


class Stats(unittest.TestCase):
    def test_block_p_separates_edge_from_noise(self):
        r = random.Random(5)
        good = [0.004 + r.gauss(0, 0.004) for _ in range(300)]
        flat = [0.004, -0.004] * 150
        self.assertLess(ss.block_p(good, n_boot=2000), 0.01)
        self.assertGreater(ss.block_p(flat, n_boot=2000), 0.05)
        self.assertEqual(ss.block_p([-0.1] * 100), 1.0)
        self.assertEqual(ss.block_p([0.1] * 10), 1.0)

    def test_p_floor_reaches_bonferroni_scale(self):
        good = [0.01 + (0.001 if i % 2 else -0.001) for i in range(200)]
        self.assertLess(ss.p_adaptive(good), 1e-4)

    def test_holm(self):
        adj = ss.holm({"a": 0.001, "b": 0.01, "c": 0.5})
        self.assertAlmostEqual(adj["a"], 0.003)
        self.assertAlmostEqual(adj["b"], 0.02)
        self.assertAlmostEqual(adj["c"], 0.5)
        adj2 = ss.holm({"a": 0.04, "b": 0.01})
        self.assertAlmostEqual(adj2["b"], 0.02)
        self.assertAlmostEqual(adj2["a"], 0.04)

    def test_sign_p(self):
        self.assertLess(ss.sign_p([1.0] * 20), 0.001)
        self.assertGreater(ss.sign_p([1.0, -1.0] * 10), 0.4)

    def test_month_dist_known(self):
        a = T0
        trades = [{"t": a + k * 86400, "x": a + k * 86400 + 3600, "net": 0.01, "mae": 0.0} for k in range(60)]
        d = ss.month_dist(trades, 1.0, a, a + 60 * 86400)
        self.assertEqual(d["n"], 31)
        self.assertAlmostEqual(d["median"], 1.01 ** 30, places=6)
        self.assertEqual(d["share_3x"], 0.0)
        trades[10]["net"] = -1.5       # ruin: every window that contains day 10 is 0
        d2 = ss.month_dist(trades, 1.0, a, a + 60 * 86400)
        self.assertEqual(d2["min"], 0.0)
        self.assertEqual(ss.month_dist(trades, 1.0, a, a + 10 * 86400), {"n": 0})

    def test_liquidation_leaves_five_percent(self):
        a = T0
        trades = [{"t": a, "x": a + 3600, "net": 0.5, "mae": 0.3}]
        d = ss.month_dist(trades, 4.0, a, a + 31 * 86400)       # w * mae = 1.2 >= 0.95
        self.assertAlmostEqual(d["min"], 0.05)

    def good_trades(self, n=60, mfe=0.2, net=0.05, jitter=0.5):
        r = random.Random(1)
        out = []
        for i in range(n):
            nv = net * (1 + r.uniform(-jitter, jitter))
            out.append({"t": T0 + i * 86400, "x": T0 + i * 86400 + 3600, "gross": nv + 0.001, "cost": 0.001, "fund": 0.0,
                        "net": nv, "mfe": mfe, "mae": 0.01})
        return out

    def test_gate_passes_strong_and_drops_weak(self):
        cfg = {"account_usd": 147, "gate": {}}
        rl = {"size": {"lev": 2, "k": 1}}
        ok, info = ss.gate(self.good_trades(), rl, cfg, 60)
        self.assertTrue(ok, info)
        self.assertGreater(info["x"], 2.0)
        ok, info = ss.gate(self.good_trades(10), rl, cfg, 60)
        self.assertFalse(ok)
        self.assertIn("train trades", info["reason"])
        weak = self.good_trades(net=0.0015, mfe=0.003)
        ok, info = ss.gate(weak, rl, cfg, 60)
        self.assertFalse(ok)
        losing = self.good_trades(net=-0.01)
        ok, info = ss.gate(losing, rl, cfg, 60)
        self.assertFalse(ok)
        self.assertIn("placebo", info["reason"])
        self.assertLess(info["x"], 0)

    def test_gate_notional_and_ceiling(self):
        cfg = {"account_usd": 147, "gate": {"min_vol_cost": 0, "min_x": 0}}
        ok, info = ss.gate(self.good_trades(), {"size": {"lev": 2, "k": 1}}, cfg, 60, min_notional_usd=3500)
        self.assertFalse(ok)
        self.assertIn("min notional", info["reason"])
        few_wins = self.good_trades(60, mfe=0.01, net=0.004)
        ok, info = ss.gate(few_wins, {"size": {"lev": 1, "k": 1}}, cfg, 1800)      # 60 trades in 60 months: 1 a month
        self.assertFalse(ok)
        self.assertIn("ceiling", info["reason"])

    def test_gate_vol_cost_and_x(self):
        cfg = {"account_usd": 147, "gate": {"min_vol_cost": 10, "min_x": 0.2}}
        noisy = self.good_trades(net=0.002, mfe=0.2, jitter=0.5)
        for t in noisy:
            t["cost"] = 0.05
        ok, info = ss.gate(noisy, {"size": {"lev": 2, "k": 1}}, cfg, 60)
        self.assertFalse(ok)

    def test_folds(self):
        a = T0
        tr = [{"t": a + k * 86400, "net": 0.01 if k < 180 else -0.01, "cost": 0.001} for k in range(360)]
        f = ss.folds(tr, a, a + 360 * 86400)
        self.assertEqual(len(f), 2)
        self.assertGreater(f[0]["mean"], 0)
        self.assertLess(f[1]["mean"], 0)


def synthetic_cfg():
    return {"family": "t", "version": 1, "alpha": 0.05, "account_usd": 147, "chunk_target": 2,
            "gate": {"min_train_trades": 5, "min_vol_cost": 0, "min_x": 0, "target_multiple": 0, "mfe_quantile": 0.9},
            "pass": {"min_val_trades": 5, "min_test_trades": 5},
            "defs": {"data": {"d": {"source": "binance_vision", "tf": "1h", "symbols": ["AAAUSDT", "BBBUSDT"], "start": "2024-01-01",
                                    "end": "2024-07-01", "extras": ["funding"]}},
                     "splits": {"s": {"train": ["2024-01-01", "2024-03-01"], "validation": ["2024-03-01", "2024-05-01"],
                                      "test": ["2024-05-01", "2024-07-01"]}},
                     "cost": {"free": FREE}},
            "rules": [{"id": "always_long", "data": "d", "splits": "s", "cost": "free", "long": [{"f": "hour", "in": list(range(24))}],
                       "short": None, "exit": {"time": 1}, "size": {"lev": 2, "k": 2}, "grid": {"exit.time": [1, 2]}},
                      {"id": "always_short", "data": "d", "splits": "s", "cost": "free", "long": None,
                       "short": [{"f": "hour", "in": list(range(24))}], "exit": {"time": 1}, "size": {"lev": 2, "k": 2}}]}


def synthetic_ctx():
    n = 24 * 182
    up = [100 * 1.001 ** k for k in range(n)]
    return se.Ctx({"AAAUSDT": from_closes(up), "BBBUSDT": from_closes(up)})


class Config(unittest.TestCase):
    def test_expand_grid_and_ids(self):
        rules = sc.expand(synthetic_cfg())
        self.assertEqual([r["id"] for r in rules], ["always_long[exit.time=1]", "always_long[exit.time=2]", "always_short"])
        self.assertEqual(rules[1]["exit"]["time"], 2)
        self.assertEqual(rules[0]["style"], "always_long")
        self.assertEqual(rules[0]["bounds"]["train"][0], 1704067200.0)
        self.assertEqual(len({r["gkey"] for r in rules}), 1)

    def test_bad_grid_path_and_unknown_feature(self):
        cfg = synthetic_cfg()
        cfg["rules"][0]["grid"] = {"exit.nope.x": [1]}
        with self.assertRaises(sc.ConfigError):
            sc.expand(cfg)
        cfg = synthetic_cfg()
        cfg["rules"][0]["long"] = [{"f": "magic", "gt": 1}]
        with self.assertRaises(sc.ConfigError):
            sc.expand(cfg)

    def test_validation_rules(self):
        muts = (lambda c: c["rules"][1].update(size={"lev": 99, "k": 1}),
                lambda c: c["rules"][1].update(exit={"time": 0}),
                lambda c: c["rules"][1].update(short="mirror", long=None),
                lambda c: c["rules"][1].update(trade=["ZZZ"]),
                lambda c: (c["rules"][1].update(long=[{"f": "fz", "n": 10, "lt": -1}], short=None),
                           c["defs"]["data"]["d"].update(extras=[])),
                lambda c: c["rules"][1].update(long=[{"f": "xret", "ref": "NOPE", "n": 1, "gt": 0.0}], short=None),
                lambda c: c["rules"][1].update(entry="sideways"),
                lambda c: c["defs"]["splits"]["s"].update(test=["2024-01-01", "2024-02-01"]))
        for mut in muts:
            cfg = synthetic_cfg()
            mut(cfg)
            with self.assertRaises(sc.ConfigError):
                sc.expand(cfg)

    def test_chunks_cover_every_rule_once_inside_groups(self):
        cfg = synthetic_cfg()
        cfg["rules"].append(dict(cfg["rules"][1], id="other", data={"source": "yahoo", "tf": "1d", "symbols": ["SPY"], "start": "2010-01-01",
                                                                         "end": "2024-07-01"}, cost={"model": "etf"}))
        rules = sc.expand(cfg)
        ch = sc.chunks(rules, 2)
        ids = [i for v in ch.values() for i in v]
        self.assertEqual(sorted(ids), sorted(r["id"] for r in rules))
        by_id = {r["id"]: r["gkey"] for r in rules}
        for v in ch.values():
            self.assertEqual(len({by_id[i] for i in v}), 1)

    def test_preregistration(self):
        cfg, sha = synthetic_cfg(), "a" * 64
        board = {"runs": [{"family": "t", "version": 1, "config_sha256": "b" * 64}]}
        pre = sc.preregistration(cfg, sha, "x.json", board, check_git=False)
        self.assertTrue(pre["problems"])
        self.assertFalse(pre["preregistered"])
        board["runs"][0]["config_sha256"] = sha
        self.assertEqual(sc.preregistration(cfg, sha, "x.json", board, check_git=False)["problems"], [])

    def test_git_state_uses_git(self):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd[3])
            return mock.Mock(returncode=0, stdout="abc123\n")
        self.assertEqual(sc.git_state("f.json", run=fake), (True, True, "abc123"))
        pre = sc.preregistration(synthetic_cfg(), "a" * 64, "f.json", None, run=fake)
        self.assertTrue(pre["preregistered"])
        self.assertEqual(pre["config_commit"], "abc123")

        def dirty(cmd, **kw):
            return mock.Mock(returncode=1 if cmd[3] == "diff" else 0, stdout="abc\n")
        self.assertTrue(sc.preregistration(synthetic_cfg(), "a" * 64, "f.json", None, run=dirty)["problems"])

    def test_shipped_configs(self):
        files = hooks.family_files()
        self.assertIn("sweep_mix1", files)
        self.assertIn("sweep_price_action1", files)
        for n in ("sweep_fundwin1", "sweep_fundwin2", "sweep_metrics1", "sweep_taker_cont2"):
            self.assertIn(n, files)
        for name, path in files.items():
            cfg, sha = sc.load(path)
            if cfg.get("kind") == "funding_window":
                continue
            rules = sc.expand(cfg)
            self.assertEqual(len({r["id"] for r in rules}), len(rules), name)
            self.assertEqual(len(sha), 64)
            ch = sc.chunks(rules, int(cfg.get("chunk_target", 20)))
            self.assertEqual(sorted(i for v in ch.values() for i in v), sorted(r["id"] for r in rules))
            if name == "sweep_mix1":
                self.assertGreaterEqual(len(rules), 200)
                self.assertGreaterEqual(len({r["style"] for r in rules}), 20)
                kinds = {r["data"]["source"] for r in rules}
                self.assertEqual(kinds, {"binance_vision", "yahoo"})
                self.assertTrue(any(r["cost"]["model"] == "xm" for r in rules))
                self.assertTrue(any(r["cost"]["model"] == "etf" for r in rules))
            for r in rules:                  # thresholds the bounds must respect: splits ordered and inside the data window
                b = r["bounds"]
                self.assertLess(b["test"][1], sc.day(r["data"]["end"]) + 1)
                self.assertGreater(b["train"][0], sc.day(r["data"]["start"]) - 1)


class Board(unittest.TestCase):
    def run_(self, sha, passed=0, crit=3, p=0.1):
        row = {"id": f"r{sha}", "family": "t", "n_criteria": crit, "val_p": p, "val_mean": 0.001, "p_adj": 1.0, "val_n": 50,
               "test_n": 30, "test_mean": 0.001, "val_mean_2x": 0.0005, "test_mean_2x": 0.0, "val_mult30_median": 1.1,
               "test_mult30_median": 0.9, "x": 0.3}
        return {"family": "t", "version": 1, "config_sha256": sha, "run_id": "1", "n_rules": 10, "n_gate_dropped": 4, "n_evaluated": 6,
                "n_errors": 0, "n_passed": passed, "holm_m": 6, "bonferroni_bar": 0.0083, "top": [row]}

    def test_update_replaces_same_sha_and_ranks(self):
        b = sb.update(None, self.run_("a", crit=3))
        b = sb.update(b, self.run_("b", crit=5, p=0.2))
        b = sb.update(b, self.run_("a", crit=2))        # rerun of config a replaces its entry
        self.assertEqual(b["totals"]["n_rules"], 20)
        self.assertEqual(b["totals"]["runs"], 2)
        self.assertEqual([r["id"] for r in b["top10"]], ["rb", "ra"])

    def test_render(self):
        md = sb.render_md(sb.update(None, self.run_("a", passed=1)))
        self.assertIn("Rules tested (expanded): 10", md)
        self.assertIn("Rules passed: 1", md)
        self.assertIn("t/ra", md)


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.cfg = synthetic_cfg()
        self.rules = sc.expand(self.cfg)
        self.ctx = synthetic_ctx()

    def test_run_rule_ok_for_a_real_edge_and_gate_for_a_loser(self):
        long_ = hooks.run_rule(self.rules[0], self.ctx, self.cfg)
        self.assertEqual(long_["status"], "ok", long_.get("reason"))
        self.assertGreater(long_["validation"]["n"], 100)
        self.assertAlmostEqual(long_["validation"]["mean"], 0.001, places=6)
        self.assertGreater(long_["validation"]["mean_day"], 0)
        self.assertEqual(len(long_["trades"][0]), len(hooks.TRADE_FIELDS))
        short = hooks.run_rule(self.rules[2], self.ctx, self.cfg)
        self.assertEqual(short["status"], "gate")

    def test_missing_data_is_an_error_row(self):
        row = hooks.run_rule(self.rules[0], se.Ctx({"AAAUSDT": self.ctx.bars["AAAUSDT"]}), self.cfg)
        self.assertEqual(row["status"], "error")

    def test_summarize_and_export(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.json")
            with open(path, "w") as f:
                json.dump(self.cfg, f)
            fns = hooks.make_functions("sweep_t", path)
            rows = [hooks.run_rule(r, self.ctx, self.cfg) for r in self.rules]
            with mock.patch.object(hooks, "on_actions", lambda: False):
                summ = fns["summarize_sweep_t"](rows, write_board=False)
            self.assertEqual(summ["n_rules"], 3)
            self.assertEqual(summ["n_gate_dropped"], 1)
            self.assertEqual(summ["n_evaluated"], 2)
            self.assertEqual(summ["holm_m"], 2)
            self.assertEqual(len(summ["top"]), 2)
            self.assertTrue(summ["pre_problems"] == [])
            self.assertIn("always_long", summ["by_style"])
            merged = os.path.join(td, "m.json")
            with open(merged, "w") as f:
                json.dump({"summary": summ, "rows": rows}, f)
            out = os.path.join(td, "o.jsonl.gz")
            n = hooks.export_trades(merged, out)
            with gzip.open(out, "rt") as g:
                lines = [json.loads(x) for x in g]
            self.assertEqual(len(lines), n)
            self.assertGreater(n, 100)
            self.assertEqual(set(lines[0]) >= {"family", "rule", "t", "net"}, True)

    def test_rows_function_loads_each_group_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.json")
            with open(path, "w") as f:
                json.dump(self.cfg, f)
            fns = hooks.make_functions("sweep_t", path)
            ch = sc.chunks(sc.expand(self.cfg), 2)
            loads = []

            def fake_load(spec):
                loads.append(spec["tf"])
                return self.ctx.bars, {}
            with mock.patch("research.sweeps.loaders.load_group", fake_load):
                res = fns["rows_sweep_t"](sorted(ch))
            self.assertEqual(len(loads), 1)
            self.assertEqual(len(res["rows"]), 3)
            self.assertEqual(res["gaps"]["rules_run"], 3)
            self.assertEqual(res["gaps"]["rule_errors"], 0)

    def test_run_py_exposes_sharded_sweeps(self):
        from research.studies import run
        self.assertIn("sweep_mix1", run.sharded_names())
        for n in ("sweep_price_action1", "sweep_fundwin1", "sweep_fundwin2", "sweep_metrics1", "sweep_taker_cont2"):
            self.assertIn(n, run.sharded_names())


class Loaders(unittest.TestCase):
    def test_grid_resample_and_funding(self):
        from research.sweeps import loaders
        rows = [[T0 + i * 3600, 1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i, 10.0, 4.0] for i in range(8) if i != 3]
        d, miss = loaders.to_grid(rows, [(T0 + 1 * 3600 + 0.5, 0.0001), (T0 + 4 * 3600, 0.0002)], None, T0, T0 + 10 * 3600)
        self.assertEqual((len(d["ts"]), miss), (8, 1))
        self.assertEqual(d["v"][3], 0.0)
        self.assertEqual(d["c"][3], d["c"][2])
        self.assertEqual((d["fund"][1], d["fund"][4]), (0.0001, 0.0002))
        r = loaders.resample(d, 4)
        self.assertEqual(len(r["ts"]), 2)
        self.assertEqual(r["o"][0], d["o"][0])
        self.assertEqual(r["c"][0], d["c"][3])
        self.assertEqual(r["h"][1], max(d["h"][4:8]))
        self.assertAlmostEqual(r["fund"][0] + r["fund"][1], 0.0003)

    def test_resample_drops_incomplete_blocks(self):
        from research.sweeps import loaders
        rows = [[T0 + i * 3600, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5] for i in range(1, 10)]      # starts at 01:00
        d, _ = loaders.to_grid(rows, [], None, T0, T0 + 12 * 3600)
        r = loaders.resample(d, 4)
        self.assertEqual(r["ts"], [T0 + 4 * 3600])


class Metrics(unittest.TestCase):
    def test_hourly_last_value_and_resample(self):
        from research.sweeps import loaders
        rows = [[T0 + i * 3600, 4.0] for i in range(8)]
        mrows = [[T0 + 600, 1.0, 2.0, 3.0, 4.0, 5.0], [T0 + 3300, 9.0, 8.0, 7.0, 6.0, 5.0], [T0 + 3600 + 300, 2.0, 2.0, 2.0, 2.0, 2.0]]
        rows = [[r[0], 1, 1, 1, 1, 1.0, 0.5] for r in rows]
        d, _ = loaders.to_grid(rows, [], None, T0, T0 + 10 * 3600, metrics=mrows)
        self.assertEqual(d["m"]["lsr_acct"][0], 9.0)          # the last 5-minute row of the hour
        self.assertEqual(d["m"]["oi"][1], 2.0)
        self.assertTrue(math.isnan(d["m"]["top_pos"][5]))
        r = loaders.resample(d, 4)
        self.assertEqual(len(r["m"]["oi"]), 2)
        self.assertTrue(math.isnan(r["m"]["oi"][0]))        # hour 3 has no metrics row
        d2, _ = loaders.to_grid(rows, [], None, T0, T0 + 10 * 3600)
        self.assertIsNone(d2["m"])
        self.assertIsNone(loaders.resample(d2, 4)["m"])

    def test_parse_metrics_tolerates_quoted_empty_cells(self):
        from research.sweeps import loaders
        r = loaders._parse_metrics(["2024-01-01 00:05:00", "BTCUSDT", "100.5", "2000.0", '""', "1.2", "0.9", ""])
        self.assertEqual(r["sum_open_interest"], 100.5)
        self.assertIsNone(r["count_toptrader_long_short_ratio"])
        self.assertEqual(r["count_long_short_ratio"], 0.9)

    def test_metric_features_and_validation(self):
        d = from_closes([100.0] * 6)
        d["m"] = {k: [1.0, 2.0, 4.0, 8.0, 16.0, 32.0] for k in se.METRIC_NAMES}
        ctx = se.Ctx({"A": d})
        self.assertEqual(ctx.series("A", {"f": "mval", "m": "oi"}), [1.0, 2.0, 4.0, 8.0, 16.0, 32.0])
        self.assertAlmostEqual(ctx.series("A", {"f": "mchg", "m": "oi", "n": 1})[3], 1.0)
        self.assertTrue(math.isnan(se.Ctx({"A": from_closes([1.0, 2.0, 3.0])}).series("A", {"f": "mval", "m": "oi"})[0]))
        cfg = synthetic_cfg()
        cfg["rules"][1].update(long=[{"f": "mz", "m": "oi", "n": 5, "gt": 1.0}], short=None)
        with self.assertRaises(sc.ConfigError):
            sc.expand(cfg)                                    # data has no metrics extra
        cfg["defs"]["data"]["d"]["extras"] = ["funding", "metrics"]
        sc.expand(cfg)
        cfg["rules"][1]["long"] = [{"f": "mz", "m": "nope", "n": 5, "gt": 1.0}]
        with self.assertRaises(sc.ConfigError):
            sc.expand(cfg)


def fw_bars(ts, drift=0.0):
    """Minute bars -60..+60 around a settlement: open 100 + drift * minute (drift in price units per minute)."""
    out = {}
    for m in range(-60, 61):
        o = 100.0 + drift * m
        out[ts + m * 60] = (o, o + 0.005, o - 0.005, o)
    return out


FW_TS = 1_700_000_000 // 60 * 60


class FundingWindow(unittest.TestCase):
    def cfg(self, **over):
        c = {"family": "fw", "version": 1, "kind": "funding_window", "alpha": 0.05, "account_usd": 147,
             "gate": {"min_train_trades": 5, "min_vol_cost": 0, "min_x": 0, "target_multiple": 0},
             "pass": {"min_val_trades": 5, "min_test_trades": 5}, "data": {"min_abs_funding": 0.001, "start": "2024-01-01", "end": "2025-07-01"},
             "splits": {"train": ["2024-01-01", "2024-07-01"], "validation": ["2024-07-01", "2025-01-01"], "test": ["2025-01-01", "2025-07-01"]},
             "grid": {"thr": [0.001, 0.003], "mode": ["fade_payer", "take_payer"], "entry": [-60, -15, -1], "exit": [1, 15, 60], "delay": [0, 5]},
             "size": {"lev": 1, "k": 1}, "cost": {"model": "perp"}}
        c.update(over)
        return c

    def test_make_event_prices(self):
        from core import sweep_events as sev
        ev = sev.make_event("X", FW_TS, 0.004, fw_bars(FW_TS, drift=0.01))
        self.assertEqual(len(ev["v"]), len(sev.PAIRS))
        gl, hi, lo = ev["v"]["-15:15"]
        self.assertAlmostEqual(gl, (100.15 / 99.85) - 1, places=6)
        self.assertAlmostEqual(hi, (100.14 + 0.005) / 99.85 - 1, places=6)      # last held bar starts at minute +14
        self.assertAlmostEqual(lo, (99.85 - 0.005) / 99.85 - 1, places=6)
        bars = fw_bars(FW_TS)
        del bars[FW_TS + 15 * 60]
        ev2 = sev.make_event("X", FW_TS, 0.004, bars)
        self.assertNotIn("-15:15", ev2["v"])
        self.assertNotIn("-60:15", ev2["v"])
        self.assertIn("-15:60", ev2["v"])
        self.assertIsNone(sev.make_event("X", FW_TS, 0.004, {}))

    def test_events_for_symbol_filters_and_counts(self):
        from core import sweep_events as sev
        calls = []

        def bars_fn(ts):
            calls.append(ts)
            return None if ts == FW_TS + 3600 else fw_bars(ts)
        fund = [(FW_TS - 3600 + 0.4, 0.0005), (FW_TS + 0.4, -0.002), (FW_TS + 3600, 0.003), (FW_TS + 7200, 0.003)]
        ev, st = sev.events_for_symbol("X", fund, bars_fn, 0.001, FW_TS - 10, FW_TS + 7200)
        self.assertEqual([e["ts"] for e in ev], [FW_TS])           # ms jitter rounded; 0.0005 ignored; failed one counted; end excluded
        self.assertEqual((st["extreme"], st["failed"]), (2, 1))

    def test_trades_fade_and_take(self):
        from core import sweep_events as sev
        rules = {r["id"]: r for r in sev.expand(self.cfg())}
        ev = sev.make_event("X", FW_TS, 0.004, fw_bars(FW_TS, drift=-0.01))          # price falls 0.01 a minute
        fade = rules[sev.rule_id(0.003, "fade_payer", -15, 15, 0)]
        t = sev.trades_for_rule(fade, [ev])[0]
        self.assertEqual(t["side"], -1)                                              # longs pay (f > 0): fade = short
        gl = ev["v"]["-15:15"][0]
        self.assertAlmostEqual(t["gross"], -gl)
        self.assertAlmostEqual(t["fund"], -0.004)                                    # a short collects the funding
        self.assertAlmostEqual(t["net"], -gl - 0.0014 + 0.004)
        self.assertEqual(t["t"], FW_TS - 15 * 60)
        take = rules[sev.rule_id(0.003, "take_payer", -15, 15, 0)]
        t2 = sev.trades_for_rule(take, [ev])[0]
        self.assertEqual(t2["side"], 1)
        self.assertAlmostEqual(t2["fund"], 0.004)
        neg = sev.make_event("X", FW_TS, -0.004, fw_bars(FW_TS))
        self.assertEqual(sev.trades_for_rule(fade, [neg])[0]["side"], 1)             # shorts pay: fade = long
        late = rules[sev.rule_id(0.003, "fade_payer", -15, 60, 5)]
        self.assertEqual(sev.trades_for_rule(late, [ev])[0]["fund"], -0.004)         # entry at -10: still across the settlement
        after = rules[sev.rule_id(0.003, "fade_payer", -1, 15, 5)]
        self.assertEqual(after["E"], 4)
        self.assertEqual(sev.trades_for_rule(after, [ev])[0]["fund"], 0.0)           # entered after the settlement: no funding

    def test_threshold_and_cap(self):
        from core import sweep_events as sev
        rules = {r["id"]: r for r in sev.expand(self.cfg(size={"lev": 1, "k": 1}))}
        r = rules[sev.rule_id(0.003, "fade_payer", -15, 15, 0)]
        weak = sev.make_event("X", FW_TS, 0.002, fw_bars(FW_TS))
        strong1 = sev.make_event("A", FW_TS + 86400, 0.004, fw_bars(FW_TS + 86400))
        strong2 = sev.make_event("B", FW_TS + 86400, 0.004, fw_bars(FW_TS + 86400))
        tr = sev.trades_for_rule(r, [weak, strong1, strong2])
        self.assertEqual([t["sym"] for t in tr], ["A"])                              # weak is below the threshold; k=1 keeps one

    def test_prev_signal_uses_only_the_earlier_rate(self):
        from core import sweep_events as sev
        cfg = self.cfg()
        cfg["grid"]["sig"] = ["prev", "realized"]
        rules = {r["id"]: r for r in sev.expand(cfg)}
        prev_rule = rules[sev.rule_id(0.003, "fade_payer", -15, 15, 0, "prev")]
        real_rule = rules[sev.rule_id(0.003, "fade_payer", -15, 15, 0)]
        # last settlement was extreme (longs paid 0.4%) but this one settled small and negative: only the prev rule trades
        ev = sev.make_event("X", FW_TS, -0.0002, fw_bars(FW_TS), prev=0.004)
        tp = sev.trades_for_rule(prev_rule, [ev])
        self.assertEqual(len(tp), 1)
        self.assertEqual(tp[0]["side"], -1)                    # chosen by the previous rate's payer (longs)
        self.assertAlmostEqual(tp[0]["fund"], 0.0002)          # but the funding actually settled is what is charged: the short pays
        self.assertEqual(sev.trades_for_rule(real_rule, [ev]), [])
        none_prev = sev.make_event("X", FW_TS, 0.004, fw_bars(FW_TS))
        self.assertEqual(sev.trades_for_rule(prev_rule, [none_prev]), [])
        ev2, st = sev.events_for_symbol("X", [(FW_TS - 28800, 0.004), (FW_TS, 0.0001)], lambda ts: fw_bars(ts), 0.001, 0, FW_TS + 1)
        self.assertEqual([(e["ts"], e["fp"]) for e in ev2], [(FW_TS - 28800, None), (FW_TS, 0.004)])   # a quiet settlement after an extreme one is kept

    def test_placebo_flips_funding_sign(self):
        a = {"t": T0, "x": T0 + 3600, "gross": -0.002, "cost": 0.0014, "fund": -0.01, "net": 0.0066, "mfe": 0.02, "mae": 0.0}
        cfg = {"account_usd": 147, "gate": {"min_train_trades": 1, "min_vol_cost": 0, "min_x": 0, "target_multiple": 0}}
        ok, info = ss.gate([dict(a) for _ in range(5)], {"size": {"lev": 1, "k": 1}}, cfg, 30)
        self.assertAlmostEqual(info["placebo_mean"], 0.002 - 0.0014 - 0.01)       # the reversed side would PAY the 1% funding
        self.assertTrue(ok, info)

    def test_expand_counts_and_twins(self):
        from core import sweep_events as sev
        with open(hooks.family_files()["sweep_fundwin1"]) as f:
            cfg = json.load(f)
        rules = sev.expand(cfg)
        self.assertEqual(len(rules), 136)
        with open(hooks.family_files()["sweep_fundwin2"]) as f:
            rules2 = sev.expand(json.load(f))
        self.assertEqual(len(rules2), 272)
        self.assertEqual(len({r["id"] for r in rules2}), 272)
        self.assertTrue(any("sig=prev" in r["id"] for r in rules2))
        ids = {r["id"] for r in rules}
        self.assertNotIn(sev.rule_id(0.001, "fade_payer", -1, 1, 5), ids)          # entry +4 is not before exit +1
        r0 = next(r for r in rules if r["id"] == sev.rule_id(0.001, "fade_payer", -1, 1, 0))
        self.assertNotIn(sev.twin_id(r0), ids)
        r1 = next(r for r in rules if r["id"] == sev.rule_id(0.001, "fade_payer", -60, 1, 0))
        self.assertIn(sev.twin_id(r1), ids)
        self.assertIsNone(sev.twin_id(next(r for r in rules if r["delay"] == 5)))
        with self.assertRaises(sc.ConfigError):
            sev.expand(self.cfg(cost={"model": "xm"}))

    def test_summarize_end_to_end(self):
        from core import sweep_events as sev
        events = []
        t = sc.day("2024-01-01") + 3600
        end = sc.day("2025-07-01")
        k = 0
        while t < end - 7200:
            ts = int(t) // 60 * 60
            events.append(sev.make_event("AAAUSDT", ts, 0.004 if k % 2 == 0 else -0.004, fw_bars(ts, drift=-0.02 if k % 2 == 0 else 0.02)))
            t += 12 * 3600
            k += 1
        cfg = self.cfg()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "fw.json")
            with open(path, "w") as f:
                json.dump(cfg, f)
            fns = hooks.make_fw_functions("sweep_fw", path)
            with mock.patch.object(hooks, "on_actions", lambda: False), \
                    mock.patch.object(ss, "p_adaptive", lambda v: ss.block_p(v, n_boot=500)):
                summ = fns["summarize_sweep_fw"](events, write_board=False)
            by = {r["id"]: r for r in summ["rule_rows"]}
            self.assertEqual(summ["n_rules"], 68)
            good = by[sev.rule_id(0.003, "fade_payer", -15, 15, 0)]
            self.assertEqual(good["status"], "ok", good.get("reason"))
            self.assertTrue(good["criteria"]["survives_5min_delay"])
            self.assertGreater(good["validation"]["mean"], 0.005)
            no_twin = by[sev.rule_id(0.003, "fade_payer", -1, 1, 0)]
            if no_twin["status"] == "ok":
                self.assertFalse(no_twin["criteria"]["survives_5min_delay"])
            self.assertEqual(by[sev.rule_id(0.003, "take_payer", -15, 15, 0)]["status"], "gate")
            self.assertEqual(summ["n_events"], len(events))
            merged = os.path.join(td, "m.json")
            with open(merged, "w") as f:
                json.dump({"summary": summ, "rows": events}, f)
            n = hooks.export_trades(merged, os.path.join(td, "o.jsonl.gz"))
            self.assertGreater(n, 100)


if __name__ == "__main__":
    unittest.main()
