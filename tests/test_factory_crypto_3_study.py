import random
import unittest
from unittest import mock

from research.studies import binance_vision as bv
from research.studies import run

T = 1567296000      # 2019-09-01


def fake_klines(sym, start, end, interval="1h", market="spot", **kw):
    r = random.Random(sum(map(ord, sym)))
    p, rows = 100.0, []
    for t in range(max(int(start), 1693526400), int(end), 3600):      # from 2023-09-01 to keep the test fast
        q = p * (1 + r.gauss(0, 0.004))
        rows.append((t, p, max(p, q) * 1.001, min(p, q) * 0.999, q, 1.0, t + 3599, 1e6, 1, 0, 0))
        p = q
    return rows, []


def fake_funding(sym, start, end, **kw):
    return [(float(t), 0.0001) for t in range(max(int(start), 1693526400), int(end), 8 * 3600)], []


class Study(unittest.TestCase):
    def test_runs_end_to_end_offline(self):
        with mock.patch.object(bv, "klines", fake_klines), mock.patch.object(bv, "funding", fake_funding):
            summ, rows = run.study_factory_crypto_3([])
        self.assertTrue(summ["integrity"]["ok"], summ["integrity"])
        self.assertEqual(summ["n_strategies"], 10)
        self.assertEqual(len(rows), 10)
        v = summ["strategies"]["don_4h_20"]
        self.assertIn("lev_table_validation", v)
        self.assertEqual(v["splits"]["validation"]["days"], 366)
