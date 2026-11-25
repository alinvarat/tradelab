"""Offline tests for research/studies/d3d4_core.py and the evaluation plumbing of d3d4.py (synthetic data, no network) and the D3/D4 protocol lock."""
import hashlib
import unittest
from pathlib import Path

from core import forced_flow as ff
from research.studies import d3d4 as run
from research.studies import d3d4_core as dc

PROTO = Path(__file__).resolve().parents[1] / "research" / "studies" / "protocol_d3d4_20261126.md"
DAY, HOUR = dc.DAY, dc.HOUR


def flat_bars(t0, hours, px=100.0):
    return {t0 + i * HOUR: (px, px, px, px) for i in range(hours)}


class Parsers(unittest.TestCase):
    def test_removals(self):
        t = "Binance Will Extend the Monitoring Tag to Include STMX & TROY, Remove the Monitoring Tag for CVX & SUN, and Remove the Seed Tag for ARKM, BLUR"
        self.assertEqual(dc.monitoring_removed(t), ["CVX", "SUN"])
        self.assertEqual(dc.monitoring_removed("Binance Will Remove the Monitoring Tag for ABC on 2025-01-02"), ["ABC"])
        self.assertEqual(dc.monitoring_removed("Binance Will Extend the Monitoring Tag to Include A1, B2 on 2025-01-02"), [])
        self.assertEqual(dc.monitoring_removed("Binance Will Extend the Monitoring Tag to Include X and Remove the Seed Tag for GMX & SU"), [])
        t2 = "Binance Will Extend the Monitoring Tag to Include WAN, Remove the Monitoring Tag for GPS & MBL, and Remove the Seed Tag for BERA, BIO"
        self.assertEqual(dc.monitoring_removed(t2), ["GPS", "MBL"])

    def test_base(self):
        self.assertEqual(dc.base_of("1000PEPEUSDT"), "PEPE")
        self.assertEqual(dc.base_of("ABCUSDT"), "ABC")
        self.assertIsNone(dc.base_of("BTCUSDT_250627"))
        self.assertIsNone(dc.base_of("ETHUSDC"))


class TagBook(unittest.TestCase):
    def test_state(self):
        book = dc.tag_book([{"sym": "A", "ts": 100}, {"sym": "A", "ts": 300}], [{"sym": "A", "ts": 200}], [{"sym": "A", "ts": 400}])
        self.assertFalse(dc.tagged(book, "A", 100))        # the add itself is not before t
        self.assertTrue(dc.tagged(book, "A", 150))
        self.assertFalse(dc.tagged(book, "A", 150, min_age=100))
        self.assertFalse(dc.tagged(book, "A", 250))        # removed
        self.assertTrue(dc.tagged(book, "A", 350))         # added again
        self.assertFalse(dc.tagged(book, "A", 450))        # delist notice
        self.assertFalse(dc.tagged(book, "B", 450))


class Signals(unittest.TestCase):
    def bars(self, vol, slope):
        return {i: (100.0 - slope * i, vol) for i in range(0, 40)}

    def test_features_and_signals(self):
        f = dc.sym_features(self.bars(10.0, 1.0), 40)
        self.assertAlmostEqual(f["ret30"], 61 / 91 - 1)
        self.assertTrue(dc.is_fall(f))
        self.assertIsNone(dc.sym_features(self.bars(10.0, 1.0), 20))      # not enough history
        dbars = {"AAAUSDT": self.bars(10.0, 1.0), "BBBUSDT": self.bars(1000.0, 1.0), "CCCUSDT": self.bars(2000.0, 0.0)}
        d = 40
        book = dc.tag_book([{"sym": "AAA", "ts": 1}], [], [])
        rows, pool = dc.build_signals(dbars, [d], book, {})
        self.assertEqual([(r["sym"], r["tag"], r["low"], r["fall"]) for r in rows], [("AAAUSDT", True, True, True)])
        self.assertTrue(all(dc.in_set(s, True, True, True) for s in dc.SETS))
        rows, pool = dc.build_signals(dbars, [d], dc.tag_book([], [], []), {})
        self.assertEqual([(r["sym"], r["tag"]) for r in rows], [("AAAUSDT", False)])
        self.assertFalse(dc.in_set("s2", False, True, True))
        self.assertTrue(dc.in_set("s3", False, True, True))
        rows, pool = dc.build_signals(dbars, [d], book, {"AAA": [d * DAY - 5]})     # delist notice already published: not a candidate
        self.assertEqual(rows, [])

    def test_pool_is_lowvol_not_signalled(self):
        dbars = {"AAAUSDT": self.bars(10.0, 0.0), "BBBUSDT": self.bars(1000.0, 1.0), "CCCUSDT": self.bars(2000.0, 0.0)}
        rows, pool = dc.build_signals(dbars, [40], dc.tag_book([], [], []), {})
        self.assertEqual(rows, [])
        self.assertEqual(pool, {40 * DAY: ["AAAUSDT"]})

    def test_hazard_and_kill(self):
        D = 100 * DAY
        rows = [{"d": D, "sym": "AAAUSDT", "tag": True, "low": True, "fall": True}, {"d": D, "sym": "BBBUSDT", "tag": False, "low": True, "fall": True}]
        nidx = {"AAA": [D + HOUR + DAY // 2]}
        t = dc.hazard_table(rows, nidx, D - 1, D + 1)
        self.assertEqual((t["s1"]["coin_days"], t["s2"]["coin_days"], t["s3"]["coin_days"]), (1, 1, 2))
        self.assertEqual((t["s2"]["hits_day"], t["s2"]["hazard_day"], t["s3"]["hazard_day"]), (1, 1.0, 0.5))
        self.assertTrue(dc.kill1_d3(t)[0])                    # too few coin-days
        big = [dict(rows[0], d=D + i * DAY) for i in range(25)]
        nidx = {"AAA": [D + i * DAY + HOUR + 60 for i in range(25)]}
        t = dc.hazard_table(big, nidx, D, D + 30 * DAY)
        self.assertFalse(dc.kill1_d3(t)[0])
        self.assertEqual(dc.first_notice_after({"A": [5, 9]}, "A", 6), 9)
        self.assertIsNone(dc.first_notice_after({"A": [5, 9]}, "A", 10))

    def test_leads_and_calendar(self):
        nidx = {"A": [10 * DAY], "B": [400 * DAY]}
        r = dc.tag_leads([{"sym": "A", "ts": 0}, {"sym": "B", "ts": 0}, {"sym": "C", "ts": 0}], nidx)
        self.assertEqual((r["adds"], r["delisted_later"], r["share_30d"], r["share_180d"]), (3, 2, round(1 / 3, 4), round(1 / 3, 4)))
        c = dc.notice_calendar([{"ts": 0}, {"ts": 0}, {"ts": 3600 * 5}])      # 1970-01-01 is a Thursday
        self.assertEqual((c["weekday"][3], c["hour_utc"][0], c["hour_utc"][5]), (2, 1, 1))


class Sim(unittest.TestCase):
    E = 10 * HOUR
    HOLD = 3 * DAY

    def bars(self):
        return flat_bars(self.E, 3 * 24 + 8)

    def test_time_exit(self):
        b = self.bars()
        b[self.E + self.HOLD] = (90.0, 90.0, 90.0, 90.0)
        s = dc.short_hourly(b, self.E, self.HOLD)
        self.assertEqual(s["reason"], "time")
        self.assertAlmostEqual(s["gross"], 0.10)
        self.assertEqual((s["te"], s["x"]), (self.E, self.E + self.HOLD))

    def test_stop(self):
        b = self.bars()
        b[self.E + 5 * HOUR] = (100.0, 130.0, 100.0, 120.0)
        s = dc.short_hourly(b, self.E, self.HOLD)
        self.assertEqual(s["reason"], "stop")
        self.assertAlmostEqual(s["gross"], -0.255)
        self.assertEqual(s["x"], self.E + 6 * HOUR)

    def test_notice_exit(self):
        b = self.bars()
        n = self.E + 10 * HOUR
        s = dc.short_hourly(b, self.E, self.HOLD, n, {n + 60: (80.0, 80.0, 80.0, 80.0)})
        self.assertEqual(s["reason"], "notice")
        self.assertAlmostEqual(s["gross"], 0.20)
        self.assertEqual(s["x"], n + 60)
        b[self.E + 11 * HOUR] = (95.0, 95.0, 95.0, 95.0)               # no 1-minute bars: the next hourly open
        s = dc.short_hourly(b, self.E, self.HOLD, n, None)
        self.assertAlmostEqual(s["gross"], 0.05)
        self.assertIsNone(dc.short_hourly(b, self.E, self.HOLD, self.E - 100, None))   # notice before the entry
        s = dc.short_hourly(b, self.E, self.HOLD, self.E + 4 * DAY, None)                # notice after the hold: time exit
        self.assertEqual(s["reason"], "time")

    def test_contract_ended(self):
        b = flat_bars(self.E, 48)
        last = self.E + 47 * HOUR
        b[last] = (100.0, 100.0, 80.0, 80.0)
        s = dc.short_hourly(b, self.E, self.HOLD)
        self.assertEqual(s["reason"], "ended")
        self.assertAlmostEqual(s["gross"], 0.20)
        self.assertEqual(s["x"], last + HOUR)
        self.assertIsNone(dc.short_hourly({}, self.E, self.HOLD))

    def test_funding_and_trade(self):
        self.assertAlmostEqual(dc.fund_income([(10, 0.001), (20, 0.002), (30, 0.003)], 10, 30), 0.005)
        sim = {"te": 1, "x": 2, "gross": 0.10, "mfe": 0.1, "mae": 0.0, "reason": "time"}
        t = dc.make_short("A", 5, sim, 0.005, 0.02)
        self.assertAlmostEqual(t["net"], 0.10 - 0.006 + 0.005)
        self.assertAlmostEqual(t["ctrl_net"], 0.014)
        self.assertAlmostEqual(-t["gross"] - t["cost"] + t["fund"], -0.10 - 0.006 - 0.005)      # reversed side pays the funding
        lg = dc.make_long("A", 5, sim, 0.02)
        self.assertAlmostEqual(lg["net"], 0.094)
        self.assertEqual(lg["fund"], 0.0)

    def test_cluster(self):
        sim = {"te": 1, "x": 2, "gross": 0.10, "mfe": 0.1, "mae": 0.0, "reason": "time"}
        a = dc.make_short("A", 5, sim, 0.0, 0.0)
        b = dc.make_short("B", 5, dict(sim, gross=0.30, x=9), 0.0)
        c = dc.cluster([a, b], lambda t: t["t"])
        self.assertEqual(len(c), 1)
        self.assertAlmostEqual(c[0]["gross"], 0.20)
        self.assertEqual((c[0]["n_coins"], c[0]["x"], c[0]["t"]), (2, 9, 5))
        self.assertAlmostEqual(c[0]["ctrl_net"], -0.006)


class D4(unittest.TestCase):
    def test_events_and_counts(self):
        T0 = dc.START + 10 * DAY
        adds = [{"sym": s, "ts": T0} for s in ("AAA", "BBB", "CCC")]
        rem = [{"sym": "CCC", "ts": T0 + 100 * DAY, "title": "x"}]
        l1f = [{"sym": "BBB", "ts": T0 + 50 * DAY}, {"sym": "ZZZ", "ts": T0 + 50 * DAY}]
        ev = dc.d4_events(adds, rem, l1f, [])
        got = sorted((e["fam"], e["sym"]) for e in ev)
        self.assertEqual(got, [("survive", "AAA"), ("survive", "CCC"), ("tagrm", "CCC")])
        self.assertTrue(all(e["nid"].startswith(e["fam"] + "|") for e in ev))
        c = dc.d4_counts(ev)
        self.assertEqual((c["survive"]["train"], c["tagrm"]["train"], c["train_total"]), (1, 1, 2))
        self.assertTrue(c["killed"])

    def test_exit_series_and_l1f(self):
        a = ff.START
        s = dc.exit_series([{"x": a + 2 * DAY + 5, "net": 0.1}, {"x": a + 2 * DAY + 9, "net": 0.2}], a, a + 10 * DAY)
        self.assertAlmostEqual(s[2], 0.3)
        w = dc.exit_series([{"x": a + 8 * DAY, "net": 0.1}], a, a + 21 * DAY, week=True)
        self.assertEqual(w, [0.0, 0.1, 0.0])
        rows = [{"fam": "l1f_ref", "ts": 5, "rules": {"l1f_ref|h4h|d1m": [0.1, None, 0, 0, "time", 6, 7]}}, {"fam": "mon_tag", "ts": 5, "rules": {}}]
        tr = dc.l1f_exit_trades(rows)
        self.assertEqual(len(tr), 1)
        self.assertAlmostEqual(tr[0]["net"], 0.1 - 0.006 - 0.001)
        self.assertEqual(tr[0]["x"], 7)


class Rules(unittest.TestCase):
    def test_counts_and_ids(self):
        self.assertEqual(len(dc.d3_rules()), 9)
        self.assertEqual(sum(1 for r in dc.d3_rules() if r[1] in dc.JUDGED_SETS), 6)
        self.assertEqual(dc.d3_rule("s2", 7 * DAY), "d3|s2|h7d")
        self.assertEqual(len(dc.d4_rules()), 12)
        self.assertEqual(dc.d4_rule("tagrm", 14400, 60), "d4|tagrm|h4h|d1m")
        self.assertAlmostEqual(dc.COST, 0.006)


class Plumbing(unittest.TestCase):
    """The evaluation path of the run (gate, evaluate, Holm, correlation) on synthetic clusters."""

    def test_evaluate_and_judge(self):
        coin = []
        for i in range(120):
            g = 0.15 if i % 2 == 0 else -0.03
            sim = {"te": ff.START + i * 8 * DAY, "x": ff.START + i * 8 * DAY + 3 * DAY, "gross": g, "mfe": 0.5, "mae": 0.05, "reason": "time"}
            t = dc.make_short("X", ff.START + i * 8 * DAY, sim, 0.001, 0.0)
            t["day"] = i
            coin.append(t)
        clus = dc.cluster(coin, lambda t: t["day"])
        l1f = [{"x": ff.START + 5 * DAY, "net": 0.1}, {"x": ff.START + 40 * DAY, "net": -0.1}]
        table, gate_rows = run.evaluate([("d3|s2|h3d", coin, clus, True), ("d3|s1|h3d", coin, clus, False)], dc.CFG, l1f)
        self.assertTrue(table["d3|s2|h3d"]["ok"], table["d3|s2|h3d"].get("gate"))
        self.assertNotIn("gate", table["d3|s1|h3d"])
        self.assertEqual(len(gate_rows), 1)
        j = run.judge(table, gate_rows, [], dc.CFG, dc.CFG_STRICT, "d3", True)
        self.assertEqual(j["event_gate"]["passed"], [])                       # killed: descriptive only
        self.assertEqual(j["event_gate"]["stage0_survivors"], 1)
        self.assertEqual(run.closest(table, gate_rows)["id"], "d3|s2|h3d")
        self.assertIn("cluster_stats_by_split", table["d3|s2|h3d"])


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a dated addendum instead")


if __name__ == "__main__":
    unittest.main()
