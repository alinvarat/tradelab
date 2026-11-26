import hashlib
import os
import random
import unittest
from datetime import date, timedelta

from core import factory_us_pit as fu
from core import keyperson as kp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bdays(first, n):
    out, d = [], date.fromisoformat(first)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def panel(days, series, divs=None):
    bars = {}
    for s, rows in series.items():
        bars[s] = [{"t": fu.et_ts(d, 9, 30), "o": r[0], "h": r[1], "l": r[2], "c": r[3], "v": 1e6} for d, r in zip(days, rows)]
    return fu.build_panel(bars, divs)


FLAGS0 = {"role": "ceo", "action": "departure", "immediate": False, "terminated": False, "misconduct": False,
          "planned": False, "interim": False, "returning": False}


class Prompt(unittest.TestCase):
    def test_prompt_hash_is_in_the_protocol(self):
        with open(os.path.join(ROOT, "research", "studies", "keyperson_prompt.txt"), "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(h, kp.PROMPT_SHA256)
        with open(os.path.join(ROOT, "research", "studies", "protocol_keyperson_20261126.md")) as f:
            self.assertIn(h, f.read())


class Text(unittest.TestCase):
    def test_section_and_prefilter(self):
        raw = ("<p>Item 2.02 Results</p><p>Item 5.02 Departure of Directors or Certain Officers</p><p>The CEO resigned effective immediately."
               "</p><p>Item 9.01 Exhibits</p><p>SIGNATURE</p>")
        sec = kp.item_502_section(kp.html_to_text(raw))
        self.assertTrue(sec.startswith("Item 5.02"))
        self.assertIn("resigned", sec)
        self.assertNotIn("Exhibits", sec)
        self.assertTrue(kp.passes_prefilter(sec))
        self.assertFalse(kp.passes_prefilter("The Board elected a new Chief Financial Officer."))
        self.assertEqual(kp.item_502_section("nothing here"), "")

    def test_redaction(self):
        t = "Acme Widgets Inc. (ACME) said Mr. Smith resigned. John A. Doe, Chief Executive Officer, will leave. Doe held the role."
        r = kp.redact(t, ["ACME WIDGETS INC"], "ACME")
        self.assertNotIn("Acme", r)
        self.assertNotIn("Doe", r)
        self.assertNotIn("Smith", r)
        self.assertIn("Chief Executive Officer", r)
        self.assertIn("[COMPANY]", r)


class Labels(unittest.TestCase):
    def test_parse(self):
        good = '{"role":"ceo","action":"departure","immediate":true,"terminated":false,"misconduct":false,"planned":false,"interim":false,"returning":false}'
        self.assertEqual(kp.parse_label("x " + good)["immediate"], True)
        self.assertIsNone(kp.parse_label(""))
        self.assertIsNone(kp.parse_label('{"role":"cfo"}'))
        self.assertIsNone(kp.parse_label(good.replace("true", '"yes"', 1)))
        none = kp.parse_label(good.replace('"ceo"', '"none"'))
        self.assertEqual(none["role"], "none")
        self.assertFalse(none["immediate"])

    def test_precedence(self):
        d = dict(FLAGS0)
        self.assertEqual(kp.derive_class(dict(d, immediate=True, planned=True)), "abrupt")
        self.assertEqual(kp.derive_class(dict(d, action="both", terminated=True, returning=True, interim=True)), "abrupt")
        self.assertEqual(kp.derive_class(dict(d, action="appointment", returning=True, interim=True)), "return")
        self.assertEqual(kp.derive_class(dict(d, planned=True, interim=True)), "planned")
        self.assertEqual(kp.derive_class(dict(d, action="appointment", interim=True)), "interim")
        self.assertEqual(kp.derive_class(dict(d, action="appointment")), "other")
        self.assertEqual(kp.derive_class(dict(d, role="none", action="none", immediate=True)), "other")
        self.assertEqual(kp.derive_class(dict(d, action="appointment", immediate=True)), "other")   # abrupt needs a departure

    def test_label_retries_once_on_empty(self):
        calls = []

        def chat(s, u):
            calls.append(1)
            return ("", "no") if len(calls) == 1 else ('{"role":"none","action":"none","immediate":false,"terminated":false,'
                                                          '"misconduct":false,"planned":false,"interim":false,"returning":false}', "m")
        flags, served, _ = kp.label_filing("text", chat)
        self.assertEqual(len(calls), 2)
        self.assertEqual(flags["role"], "none")


class Filings(unittest.TestCase):
    def test_parse_and_candidates(self):
        cols = {"form": ["8-K", "8-K/A", "10-K", "8-K"], "acceptanceDateTime": ["2018-03-01T16:30:00.000Z"] * 4,
                "filingDate": ["2018-03-01"] * 4, "items": ["5.02,9.01", "5.02", "", "2.02"],
                "accessionNumber": ["a", "b", "c", "d"], "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"]}
        fl = kp.parse_filing_docs(cols)
        self.assertEqual([x["accession"] for x in fl], ["a", "b", "d"])
        got = kp.candidates(fl, "T", lambda s, d: True)
        self.assertEqual([x["accession"] for x in got], ["a"])          # 8-K only, item 5.02 only
        self.assertEqual(kp.candidates(fl, "T", lambda s, d: False), [])
        self.assertEqual(kp.doc_url(5, "0001-18-000001", "x.htm"), "https://www.sec.gov/Archives/edgar/data/5/000118000001/x.htm")

    def test_dedupe_keeps_first_within_window(self):
        ev = [{"sym": "A", "ts": 1000.0}, {"sym": "A", "ts": 1000.0 + 5 * 86400}, {"sym": "A", "ts": 1000.0 + 40 * 86400}, {"sym": "B", "ts": 1001.0}]
        got = kp.dedupe(ev)
        self.assertEqual([(e["sym"], e["ts"]) for e in got], [("A", 1000.0), ("B", 1001.0), ("A", 1000.0 + 40 * 86400)])


class Pricing(unittest.TestCase):
    def setUp(self):
        self.days = bdays("2019-01-02", 120)
        n = len(self.days)
        stock = [(100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1) for i in range(n)]
        spy = [(200.0, 200.0, 200.0, 200.0, 1)] * n
        self.P = panel(self.days, {"SPY": spy, "XYZ": stock}, divs={"XYZ": {self.days[12]: 1.0}})

    def test_entry_is_next_open_after_acceptance(self):
        d = self.days[10]
        self.assertEqual(kp.entry_session(self.P, fu.et_ts(d, 8, 0)), 10)       # before the open: same session
        self.assertEqual(kp.entry_session(self.P, fu.et_ts(d, 9, 30)), 11)      # at the open: next session
        self.assertEqual(kp.entry_session(self.P, fu.et_ts(d, 17, 0)), 11)

    def test_leg_and_trade(self):
        lg = kp.leg(self.P, "XYZ", 10, 5)
        self.assertAlmostEqual(lg["r"], 115 / 110 - 1 + 1.0 / 110)               # open 15 vs open 10, one dividend inside
        self.assertAlmostEqual(lg["rb"], 0.0)
        self.assertAlmostEqual(lg["hi"], (110 + 4 + 1) / 110 - 1)                # max high of sessions 10..14
        self.assertAlmostEqual(lg["lo"], 99 / 110 + 10 / 110 - 1)                # min low is session 10: 99 + 10
        self.assertIsNone(kp.leg(self.P, "XYZ", 118, 5))
        long_ = kp.trade_numbers(lg, 1, "raw", 5)
        self.assertAlmostEqual(long_["net"], lg["r"] - kp.COST_LONG)
        short = kp.trade_numbers(lg, -1, "raw", 5)
        self.assertAlmostEqual(short["net"], -lg["r"] - kp.COST_SHORT - kp.SHORT_FIN_YEAR * 5 / 252)
        adj = kp.trade_numbers(dict(lg, rb=0.01), 1, "adj", 5)
        self.assertAlmostEqual(adj["gross"], lg["r"] - 0.01)
        self.assertAlmostEqual(adj["cost"], kp.COST_LONG + kp.SPY_LEG)
        self.assertGreaterEqual(short["mfe"], 0.0)

    def test_control_sessions_stay_away_from_own_filings(self):
        own = [fu.et_ts(self.days[60], 17, 0)]
        rng = random.Random(1)
        # the whole panel is inside one split
        for k, v in kp.BOUNDS_DAYS.items():
            if v[0] <= self.days[0] < v[1]:
                split = k
        picks = kp.control_sessions(self.P, "XYZ", own[0], own, split, rng)
        self.assertEqual(len(picks), kp.CTRL_N)
        self.assertTrue(all(abs(i - 61) > kp.CTRL_EXCL for i in picks))

    def test_build_row(self):
        ev = {"sym": "XYZ", "ts": fu.et_ts(self.days[30], 17, 0), "cls": "abrupt", "acc": "a"}
        row, why = kp.build_row(self.P, ev, [ev["ts"]])
        self.assertEqual(why, "ok")
        self.assertEqual(row["entry_day"], self.days[31])
        self.assertEqual(set(row["legs"]), {"1", "5", "20"})
        self.assertIsNone(kp.build_row(self.P, dict(ev, sym="NOPE"), [])[0])
        late = dict(ev, ts=fu.et_ts(self.days[115], 17, 0))
        self.assertEqual(kp.build_row(self.P, late, [])[1], "no_bar_for_hold_5")


class Evaluation(unittest.TestCase):
    def rows(self, n, drift, cls="abrupt"):
        out, t0 = [], kp.BOUNDS["train"][0]
        span = kp.END - t0
        for i in range(n):
            ts = t0 + span * i / n
            lg = {"r": drift + (0.02 if i % 2 else -0.02), "rb": 0.0, "hi": 0.03, "lo": -0.03}
            out.append({"sym": "S%d" % i, "ts": ts, "acc": str(i), "cls": cls, "split": kp.split_of(ts), "entry_ts": ts + 3600,
                        "legs": {str(h): lg for h in kp.HOLDS}, "ctrl": {str(h): [dict(lg, r=0.0)] * 4 for h in kp.HOLDS}})
        return out

    def test_trades_and_counts(self):
        rows = self.rows(10, -0.01)
        tr = kp.trades_of(rows, "abrupt", -1, 5, "raw")
        self.assertEqual(len(tr), 10)
        self.assertIsNotNone(tr[0]["ctrl_net"])
        self.assertEqual(kp.trades_of(rows, "return", 1, 5, "raw"), [])
        ct = kp.count_table([{"cls": "abrupt", "ts": kp.BOUNDS["train"][0] + 1}])
        self.assertEqual(ct["abrupt"]["train"], 1)

    def test_too_few_events_fail_stage0(self):
        table, ev, fam = kp.evaluate_rules(self.rows(10, -0.05))
        self.assertEqual(ev, [])
        self.assertFalse(table["abrupt|short|h5|raw"]["ok"])
        self.assertIn("train trades", table["abrupt|short|h5|raw"]["gate"]["reason"])

    def test_no_edge_does_not_pass(self):
        table, ev, fam = kp.evaluate_rules(self.rows(400, 0.0))
        self.assertFalse(any(r.get("passed") for r in ev))

    def test_descriptive_covers_every_class(self):
        d = kp.descriptive_table(self.rows(6, 0.0))
        self.assertEqual(len(d), len(kp.CLASSES) * 2 * len(kp.HOLDS) * len(kp.BASES))


if __name__ == "__main__":
    unittest.main()
