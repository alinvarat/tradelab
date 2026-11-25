"""Offline tests for core/d1_liq.py (synthetic series, no network) and the D1 protocol lock."""
import hashlib
import unittest
from pathlib import Path

from core import d1_liq as d1
from core import sweep_stats as ss

PROTO = Path(__file__).resolve().parents[1] / "research" / "studies" / "protocol_d1_liq_20261126.md"


def series(n_min=6000, price=100.0, qv=10000.0):
    """Flat series from the START minute index minus a baseline day, with an optional spike added by the caller."""
    s = d1.Series()
    base = int((d1.START - d1.T0) // 60) - 1700
    for i in range(base, base + n_min):
        s.o[i] = s.h[i] = s.l[i] = s.c[i] = price
        s.qv[i], s.tb[i] = qv, qv / 2
    return s, base


def spike(s, i0, drop=0.05, qv=200000.0, buy_share=0.1):
    """One 5-minute window starting at minute index i0 (a multiple of 5): price falls `drop`, then recovers over the next minutes."""
    for j in range(5):
        i = i0 + j
        p = 100 * (1 - drop * (j + 1) / 5)
        s.o[i], s.c[i] = (100 if j == 0 else 100 * (1 - drop * j / 5)), p
        s.h[i], s.l[i] = max(s.o[i], p), min(s.o[i], p)
        s.qv[i], s.tb[i] = qv, qv * buy_share
    for j in range(5, 80):
        i = i0 + j
        s.o[i] = s.c[i] = s.h[i] = s.l[i] = 100 * (1 - drop) + (100 * drop * 0.5) * min(1, (j - 5) / 20)


class Events(unittest.TestCase):
    def test_trigger_fade_long(self):
        s, base = series()
        i0 = base + 3000 - (base + 3000) % 5
        spike(s, i0)
        ev = d1.find_events(s)
        self.assertEqual(len(ev), 1)
        e = ev[0]
        self.assertEqual(e["side"], 1)
        self.assertTrue(e["s2"])
        self.assertEqual(e["ts"], d1.T0 + (i0 + 5) * 60)
        self.assertGreaterEqual(e["vm"], 20)

    def test_no_trigger_when_taker_side_disagrees(self):
        s, base = series()
        i0 = base + 3000 - (base + 3000) % 5
        spike(s, i0, buy_share=0.9)           # price falls but takers are buyers: not forced selling
        self.assertEqual(d1.find_events(s), [])

    def test_no_trigger_small_volume_or_move(self):
        s, base = series()
        i0 = base + 3000 - (base + 3000) % 5
        spike(s, i0, qv=20000.0)              # 2x volume only (5 x 20000 vs 5 x 10000 baseline)
        self.assertEqual(d1.find_events(s), [])
        s2, base = series()
        spike(s2, i0, drop=0.02)
        self.assertEqual(d1.find_events(s2), [])

    def test_baseline_excludes_current_window_and_needs_history(self):
        s, base = series(n_min=400)
        spike(s, base + 300 - (base + 300) % 5)
        self.assertEqual(d1.find_events(s, a=d1.T0), [])

    def test_cluster_merge(self):
        s, base = series()
        i0 = base + 3000 - (base + 3000) % 5
        spike(s, i0)
        s.o[i0 + 5] = 100                      # second spike right after the first (< 30 min)
        spike(s, i0 + 10)
        self.assertEqual(len(d1.find_events(s)), 1)


class Trade(unittest.TestCase):
    def test_long_gain_and_time_exit(self):
        s, base = series()
        i0 = base + 3000 - (base + 3000) % 5
        spike(s, i0)
        ev = d1.find_events(s)[0]
        t = d1.trade(s, 1, ev["ts"], 60, 900)
        self.assertEqual(t["te"], ev["ts"] + 60)
        self.assertEqual(t["x"], t["te"] + 900)
        self.assertGreater(t["gross"], 0.015)        # bought near the low, recovers by half the drop
        sh = d1.trade(s, -1, ev["ts"], 60, 900)
        self.assertAlmostEqual(sh["gross"], -t["gross"], places=9)

    def test_stop(self):
        s, base = series()
        i = base + 1000
        for j in range(0, 30):
            s.o[i + j] = s.c[i + j] = s.h[i + j] = 100
            s.l[i + j] = 100
        s.l[i + 3] = 90                                # long entry at 100, low 90: 10% adverse
        t = d1.trade(s, 1, d1.T0 + (i - 1) * 60, 60, 900)
        self.assertEqual(t["reason"], "stop")
        self.assertAlmostEqual(t["gross"], -(d1.STOP + d1.STOP_SLIP))

    def test_missing_bar_drops_trade(self):
        s, base = series()
        self.assertIsNone(d1.trade(s, 1, d1.T0 + (base + 7000) * 60, 60, 900))


class Selection(unittest.TestCase):
    def row(self, ts, x, s2=True, sym="A"):
        return {"sym": sym, "ts": ts, "side": 1, "s2": s2, "r": {"h900d60": [0.01, 0.0, 0.02, 0.01, "time", ts + 60, x]}, "dropped": []}

    def test_one_at_a_time_first_come(self):
        rows = [self.row(1000, 2000), self.row(1500, 2500, sym="B"), self.row(2100, 3000, sym="C")]
        tr, busy, nobar = d1.select(rows, "s1", 900, 60)
        self.assertEqual([t["sym"] for t in tr], ["A", "C"])
        self.assertEqual(busy, 1)

    def test_s2_subset_and_net(self):
        rows = [self.row(1000, 2000, s2=False), self.row(5000, 6000)]
        tr, _, _ = d1.select(rows, "s2", 900, 60)
        self.assertEqual(len(tr), 1)
        self.assertAlmostEqual(tr[0]["net"], 0.01 - d1.COST - d1.FUND)
        self.assertAlmostEqual(tr[0]["ctrl_net"], 0 - d1.COST - d1.FUND)

    def test_gate_placebo_uses_cost(self):
        tr = [{"t": 1.0 + i, "x": 2.0 + i, "gross": 0.03, "cost": d1.COST, "fund": d1.FUND, "net": 0.03 - d1.COST - d1.FUND,
               "mfe": 0.05, "mae": 0.01} for i in range(40)]
        ok, info = ss.gate(tr, {"size": d1.SIZE}, d1.CFG, 540)
        self.assertIn("train_mean", info)


class Rules(unittest.TestCase):
    def test_counts_and_ids(self):
        self.assertEqual([r[0] for r in d1.judged_rules()], ["s1|h5m|d1m", "s1|h15m|d1m", "s1|h60m|d1m", "s2|h5m|d1m", "s2|h15m|d1m", "s2|h60m|d1m"])
        self.assertEqual(len(d1.reported_rules()), 6)
        self.assertAlmostEqual(d1.COST, 0.004)

    def test_universe(self):
        self.assertTrue(d1.is_small("MEMEFIUSDT"))
        self.assertFalse(d1.is_small("1000PEPEUSDT"))
        self.assertFalse(d1.is_small("BTCUSDT"))
        self.assertFalse(d1.is_small("BTCUSDT_250627"))
        self.assertFalse(d1.is_small("ETHUSDC"))


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
