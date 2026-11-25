import unittest

from core import smallcap_intraday as si


def bar(m, o, h=None, l=None, c=None, v=1000):
    c = o if c is None else c
    return [m, o, max(o, c) if h is None else h, min(o, c) if l is None else l, c, v]


def reg_day(prices):
    """prices: list of closes per 5m bar from 09:30; open = previous close."""
    out, prev = [], prices[0]
    for k, c in enumerate(prices):
        out.append(bar(570 + 5 * k, prev, c=c))
        prev = c
    return out


class T(unittest.TestCase):
    def test_rules_unique(self):
        ids = [r["id"] for r in si.build_rules()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 36 + 10 + 4)

    def test_event_detection_point_in_time(self):
        days = {}
        for k in range(12):
            d = f"2026-10-{k + 1:02d}"
            days[d] = {"pre": [], "reg": [bar(570 + 5 * j, 5.0, v=40000) for j in range(78)]}
        d = "2026-10-13"
        days[d] = {"pre": [bar(300, 6.5, v=20000), bar(555, 6.4, v=20000)], "reg": reg_day([6.5] * 78)}
        ev = si.find_events("ABC", days, [], "2026-10-20", True)
        self.assertEqual(len(ev), 1)
        self.assertAlmostEqual(ev[0]["gap"], 0.28, places=2)
        self.assertEqual(ev[0]["prev_date"], "2026-10-12" if "2026-10-12" in days else "2026-10-12")
        self.assertEqual(si.find_events("ABC", days, ["2026-10-13"], "2026-10-20", True), [])   # split day
        self.assertEqual(si.find_events("ABC", days, [], "2026-10-13", False), [])               # day not complete

    def test_orb_enters_next_open_and_stops(self):
        # ORB 5 min: first bar high 10.1 low 9.9; bar 2 closes 10.3 (signal); entry = bar 3 open
        bars = [bar(570, 10.0, 10.1, 9.9, 10.0), bar(575, 10.0, 10.35, 10.0, 10.3), bar(580, 10.3, 10.5, 10.2, 10.4),
                bar(585, 10.4, 10.4, 9.8, 9.85)] + [bar(590 + 5 * k, 9.85) for k in range(70)]
        ev = {"sym": "ABC", "date": "2026-10-13", "gap": 0.3, "adv20": 1e6, "reg": bars}
        rule = {"id": "t", "orb": 5, "exit": "stoporb_eod"}
        t = si.orb_trade(ev, rule)
        self.assertEqual(t["ep"], 10.3)                 # next bar open, not the signal close
        self.assertEqual(t["xp"], 9.9)                  # stopped at ORB low
        self.assertLess(t["net"], t["gross"])

    def test_trailing_stop(self):
        bars = [bar(570, 10.0), bar(575, 10.0, 12.0, 10.0, 12.0), bar(580, 12.0, 12.0, 10.8, 11.0)]
        r = si.run_trade(bars, 0, time_min=955, trail=0.08)
        self.assertAlmostEqual(r["xp"], 12.0 * 0.92)

    def test_no_trade_without_breakout(self):
        bars = [bar(570 + 5 * k, 10.0) for k in range(78)]
        ev = {"sym": "A", "date": "2026-10-13", "gap": 0.3, "adv20": 1e6, "reg": bars}
        self.assertIsNone(si.orb_trade(ev, {"id": "t", "orb": 15, "exit": "trail8_eod"}))

    def test_halt_parse_and_classify(self):
        xml = ("<rss><item><ndaq:HaltDate>11/24/2026</ndaq:HaltDate><ndaq:HaltTime>10:05:00</ndaq:HaltTime>"
               "<ndaq:IssueSymbol>ABC</ndaq:IssueSymbol><ndaq:ReasonCode>LUDP</ndaq:ReasonCode>"
               "<ndaq:ResumptionTradeTime>10:10:00</ndaq:ResumptionTradeTime></item></rss>")
        h = si.parse_nasdaq_halts(xml)
        self.assertEqual(h[0]["sym"], "ABC")
        self.assertEqual(si.hhmm(h[0]["resume_trade"]), 610)
        self.assertEqual(si.us_date(h[0]["halt_date"]), "2026-11-24")
        self.assertEqual(si.classify_text("announces pricing of public offering"), "offering")
        self.assertEqual(si.classify_text("receives FDA clearance"), "fda")
        self.assertEqual(si.classify_text("", ()), "none")

    def test_evaluate_pending(self):
        t0 = si.BOUNDS["train"][0]
        trades = [{"t": t0 + 86400 * k, "x": t0 + 86400 * k + 3600, "date": "2026-10-01", "net": 0.01, "gross": 0.02, "cost": 0.01,
                   "fund": 0.0, "mfe": 0.05, "mae": 0.01, "ctrl_net": 0.0} for k in range(5)]
        out = si.evaluate_family({"r": trades}, t0 + 86400 * 40)
        self.assertEqual(out["gate_survivors"], 0)      # too few train trades
        self.assertEqual(out["passed"], [])


if __name__ == "__main__":
    unittest.main()
