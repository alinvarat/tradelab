import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core import screens as sc
from research.studies import sharding as sh

ROOT = Path(__file__).resolve().parent.parent

T0 = 1_700_006_400            # a UTC hour boundary
H = 3600


def build(events, n=1300, drift_after=0.0, qv=3e5):
    """events: {hour_index: close multiplier vs the previous close}. Flat price 1.0 otherwise; after the first event
    the price drifts by drift_after per hour. Returns hourly bars with open = previous close."""
    closes, first = [], min(events)
    for k in range(n):
        prev = closes[-1] if closes else 1.0
        closes.append(prev * events[k] if k in events else prev * (1 + drift_after if k > first else 1.0))
    bars = []
    for k, c in enumerate(closes):
        o = closes[k - 1] if k else 1.0
        bars.append((T0 + k * H, o, max(o, c), min(o, c), c, qv))
    return bars


def oi_series(n=1300, dips=(), base=1000.0, usd=1e7, dip=0.8):
    """Open interest per hour; at the decision time of each hour in `dips` it is `dip` x base."""
    oi = {T0 + k * H: (base, usd) for k in range(n + 1)}
    for k in dips:
        oi[T0 + (k + 1) * H] = (base * dip, usd * dip)
    return oi


def btc(n=1300):
    return {T0 + k * H: (100.0, 100.0) for k in range(n)}


class OiFlushLong(unittest.TestCase):
    def test_long_after_down_flush_with_measured_funding(self):
        h1 = build({800: 0.88}, drift_after=0.01)
        e = T0 + 802 * H
        funding = [(e - 8 * H, 0.0100),            # before entry: not counted
                   (e + H, 0.0002),                # inside the 1-day hold
                   (e + 30 * H, 0.0003)]           # day 2: inside the 3-day hold only
        r = sc.oi_flush_rows("X", h1, oi_series(dips=[800]), btc(), funding)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["ts"], r[0]["kind"]), (e, "oi_flush_long"))
        entry = h1[802][1]
        self.assertAlmostEqual(entry, 0.88 * 1.01, places=9)            # open of the hour after D + 1 h
        self.assertAlmostEqual(r[0]["oi_drop"], -0.2)
        self.assertAlmostEqual(r[0]["move"], -0.12)
        x1 = h1[802 + 23][4]
        self.assertAlmostEqual(r[0]["ret"]["d1"]["net"], x1 / entry - 1 - sc.H2_FEES - 0.0002, places=9)
        x3 = h1[802 + 71][4]
        self.assertAlmostEqual(r[0]["ret"]["d3"]["net"], x3 / entry - 1 - sc.H2_FEES - 0.0005, places=9)
        self.assertAlmostEqual(r[0]["ret"]["d7"]["funding"], -0.0005, places=12)

    def test_btc_leg_is_subtracted_but_not_in_unhedged(self):
        h1 = build({800: 0.88}, drift_after=0.01)
        b = {T0 + k * H: (100.0, 100.0) for k in range(1300)}
        e = T0 + 802 * H
        b[e] = (100.0, 100.0)
        b[T0 + (802 + 23) * H] = (100.0, 102.0)         # BTC +2% close at the d1 exit
        r = sc.oi_flush_rows("X", h1, oi_series(dips=[800]), b, [])
        entry, x1 = h1[802][1], h1[802 + 23][4]
        self.assertAlmostEqual(r[0]["ret"]["d1"]["net"], (x1 / entry - 1) - 0.02 - sc.H2_FEES, places=9)
        self.assertAlmostEqual(r[0]["ret"]["d1"]["net_unhedged"], (x1 / entry - 1) - sc.H2_FEES, places=9)


class OiFlushShort(unittest.TestCase):
    def test_short_after_up_flush_receives_funding(self):
        h1 = build({800: 1.12}, drift_after=-0.01)
        e = T0 + 802 * H
        r = sc.oi_flush_rows("X", h1, oi_series(dips=[800]), btc(), [(e + 5 * H, 0.0004)])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["kind"], "oi_flush_short")
        entry, x1 = h1[802][1], h1[802 + 23][4]
        self.assertAlmostEqual(r[0]["ret"]["d1"]["net"], 1 - x1 / entry - sc.H2_FEES + 0.0004, places=9)
        self.assertLess(1 - x1 / entry, 1.0)                       # short gain is 1 - exit/entry, never above 100%
        self.assertAlmostEqual(r[0]["ret"]["d7"]["net"], 1 - h1[802 + 167][4] / entry - sc.H2_FEES + 0.0004, places=9)


class OiFlushFilters(unittest.TestCase):
    def rows(self, h1=None, oi=None, start_ts=0.0, b=None):
        return sc.oi_flush_rows("X", h1 or build({800: 0.88}), oi or oi_series(dips=[800]), b or btc(), [], start_ts)

    def test_baseline_fires_once(self):
        self.assertEqual(len(self.rows()), 1)

    def test_open_interest_drop_must_reach_15_percent(self):
        self.assertEqual(self.rows(oi=oi_series(dips=[800], dip=0.86)), [])
        self.assertEqual(len(self.rows(oi=oi_series(dips=[800], dip=0.84))), 1)

    def test_price_move_must_reach_10_percent(self):
        self.assertEqual(self.rows(h1=build({800: 0.92})), [])
        self.assertEqual(len(self.rows(h1=build({800: 0.89}))), 1)

    def test_oi_up_or_flat_is_no_flush(self):
        self.assertEqual(self.rows(oi=oi_series(dips=[800], dip=1.3)), [])
        self.assertEqual(self.rows(oi=oi_series()), [])

    def test_missing_oi_snapshot_is_no_event(self):
        oi = oi_series(dips=[800])
        del oi[T0 + 801 * H]
        self.assertEqual(self.rows(oi=oi), [])

    def test_thin_volume_and_thin_open_interest(self):
        self.assertEqual(self.rows(h1=build({800: 0.88}, qv=1e4)), [])
        self.assertEqual(self.rows(oi=oi_series(dips=[800], usd=4e5, dip=0.8)), [])

    def test_no_history_gap_in_the_hours(self):
        h1 = build({800: 0.88})
        self.assertEqual(self.rows(h1=h1[:100] + h1[120:]), [])
        self.assertEqual(self.rows(h1=build({400: 0.88}), oi=oi_series(dips=[400])), [])   # fewer than 720 hours before

    def test_entry_before_start_is_dropped(self):
        self.assertEqual(self.rows(start_ts=T0 + 803 * H), [])
        self.assertEqual(len(self.rows(start_ts=T0 + 802 * H)), 1)

    def test_cooldown_is_seven_days(self):
        h1 = build({800: 0.88, 900: 0.88, 1000: 0.88})
        r = sc.oi_flush_rows("X", h1, oi_series(dips=[800, 900, 1000]), btc(), [])
        self.assertEqual([x["ts"] for x in r], [T0 + 802 * H, T0 + 1002 * H])

    def test_holds_cut_off_at_end_of_data(self):
        r = self.rows(h1=build({800: 0.88}, n=802 + 24 * 3 + 5), oi=oi_series(n=1000, dips=[800]))
        self.assertEqual(sorted(r[0]["ret"]), ["d1", "d3"])
        self.assertEqual(self.rows(h1=build({800: 0.88}, n=802 + 10), oi=oi_series(n=1000, dips=[800])), [])


class HourlyParser(unittest.TestCase):
    def test_keeps_only_on_the_hour_rows(self):
        self.assertEqual(sc.oi_hourly_row("2024-01-01 03:00:00,BTCUSDT,100.5,4000000,1.2,1.3,0.9".split(",")),
                         (1704078000, 100.5, 4000000.0))
        self.assertIsNone(sc.oi_hourly_row("2024-01-01 03:05:00,BTCUSDT,100.5,4000000".split(",")))
        self.assertIsNone(sc.oi_hourly_row("2024-01-01 03:00:00,BTCUSDT,,4000000".split(",")))
        self.assertEqual(sc.oi_hourly_row("1704078000000,BTCUSDT,1,2".split(","))[0], 1704078000)


def fake_row(ts, kind, nets, symbol="A"):
    return {"symbol": symbol, "market": f"{ts}{symbol}", "ts": ts, "kind": kind,
            "ret": {f"d{d}": {"net": v, "net_unhedged": v, "funding": 0.0} for d, v in zip(sc.H2_HOLDS, nets)}}


class Summary(unittest.TestCase):
    B = sc.h2_bounds()

    def rows(self, kind, per_split, base, spread=0.001):
        out, n = [], 0
        for sp, count in per_split.items():
            a, b = self.B[sp]
            for k in range(count):
                n += 1
                v = base + spread * ((k % 7) - 3)
                out.append(fake_row(a + 3600 * 5 * k + 86400 * (k % 5), kind, (v, v, v), f"S{n}"))
        return out

    def test_good_rule_passes_all_checks(self):
        rows = self.rows("oi_flush_long", {"train": 400, "validation": 400, "test": 400}, 0.03)
        s = sc.oi_flush_summary(rows)["oi_flush_long"]
        self.assertTrue(s["passed"], s["gates"])
        self.assertGreaterEqual(s["per_week"], 3)

    def test_costly_rule_fails_double_cost(self):
        rows = self.rows("oi_flush_long", {"train": 400, "validation": 400, "test": 400}, 0.003, spread=0.0005)
        s = sc.oi_flush_summary(rows)["oi_flush_long"]
        self.assertFalse(s["gates"]["double_cost_validation_positive"])
        self.assertFalse(s["passed"])

    def test_rare_rule_fails_three_a_week_and_losing_rule_fails(self):
        rare = self.rows("oi_flush_short", {"train": 30, "validation": 30, "test": 30}, 0.05)
        s = sc.oi_flush_summary(rare)["oi_flush_short"]
        self.assertFalse(s["gates"]["three_a_week"])
        self.assertFalse(s["passed"])
        lose = self.rows("oi_flush_short", {"train": 400, "validation": 400, "test": 400}, -0.02)
        self.assertFalse(sc.oi_flush_summary(lose)["oi_flush_short"]["passed"])

    def test_empty_input_does_not_crash(self):
        s = sc.oi_flush_summary([])
        self.assertFalse(s["oi_flush_long"]["passed"])
        self.assertEqual(s["oi_flush_short"]["rows"], 0)

    def test_bonferroni_constant(self):
        self.assertAlmostEqual(sc.H2_ALPHA, 0.025)


class ShardedRun(unittest.TestCase):
    def run_py(self, *args):
        r = subprocess.run([sys.executable, str(ROOT / "research/studies/run.py"), *args], capture_output=True, text=True,
                           cwd=ROOT, timeout=120)
        return r.returncode, r.stdout, r.stderr

    def test_study_is_sharded_and_merges_offline(self):
        universe = ["AUSDT", "BUSDT"]
        B = sc.h2_bounds()
        rows = [fake_row(B["train"][0] + 86400 * k, "oi_flush_long", (0.01, 0.01, 0.01), f"A{k}") for k in range(12)]
        with tempfile.TemporaryDirectory() as d:
            for i in range(2):
                part = sh.make_part("h2_oi_flush", i, 2, universe,
                                    {"rows": rows if i == 0 else [], "gaps": {"metrics_days_failed": i + 1}})
                Path(d, f"h2_oi_flush_{i}.json").write_text(json.dumps(part))
            code, out, err = self.run_py("h2_oi_flush", "--merge", d, "--out", f"{d}/h2_oi_flush.json")
            self.assertEqual(code, 0, err)
            summ = json.loads(out)
            self.assertEqual(summ["rows"], 12)
            self.assertEqual(summ["shard_gaps"], {"metrics_days_failed": 3})
            self.assertIn("oi_flush_short", summ)
            self.assertFalse(summ["oi_flush_long"]["passed"])

    def test_missing_shards_fail(self):
        with tempfile.TemporaryDirectory() as d:
            code, _, err = self.run_py("h2_oi_flush", "--merge", d)
            self.assertEqual(code, 2)
            self.assertIn("merge failed", err)


if __name__ == "__main__":
    unittest.main()
