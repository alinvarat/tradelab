import calendar
import json
import unittest

from core import polymarket_llm as pm

NOW = calendar.timegm((2026, 11, 24, 0, 0, 0))


def market(**kw):
    m = {"id": 1, "question": "Will X happen?", "description": "rules", "outcomePrices": json.dumps(["1", "0"]),
         "clobTokenIds": json.dumps(["Y", "N"]), "startDate": "2026-10-25T00:00:00Z", "endDate": "2026-11-10T00:00:00Z",
         "volumeNum": 50000, "events": [{"id": 77}]}
    m.update(kw)
    return m


class Eligibility(unittest.TestCase):
    def test_in_window_market_and_t0(self):
        e = pm.eligible(market(), NOW)
        self.assertEqual(e["t0"], calendar.timegm((2026, 11, 7, 0, 0, 0)))
        self.assertTrue(e["yes_won"])
        self.assertEqual(e["event"], "77")

    def test_out_of_protocol_markets(self):
        self.assertIsNone(pm.eligible(market(startDate="2026-10-10T00:00:00Z"), NOW))     # before the model's release
        self.assertIsNone(pm.eligible(market(endDate="2026-12-10T00:00:00Z"), NOW))       # not resolved yet
        self.assertIsNone(pm.eligible(market(endDate="2026-10-27T00:00:00Z"), NOW))       # shorter than 4 days
        self.assertIsNone(pm.eligible(market(volumeNum=500), NOW))
        self.assertIsNone(pm.eligible(market(outcomePrices=json.dumps(["0.5", "0.5"])), NOW))


class Pricing(unittest.TestCase):
    def test_price_at_uses_last_point_within_a_day(self):
        h = [{"t": 100, "p": 0.2}, {"t": 200, "p": 0.3}, {"t": 400, "p": 0.9}]
        self.assertEqual(pm.price_at(h, 300), 0.3)
        self.assertIsNone(pm.price_at(h, 50))
        self.assertIsNone(pm.price_at([{"t": 0, "p": 0.5}], 2 * 86400))

    def test_rule_and_returns(self):
        self.assertEqual(pm.side_for(0.7, 0.5), "yes")
        self.assertEqual(pm.side_for(0.3, 0.5), "no")
        self.assertIsNone(pm.side_for(0.55, 0.5))
        self.assertAlmostEqual(pm.bet_return("yes", 0.24, True), 1 / 0.25 - 1)
        self.assertEqual(pm.bet_return("no", 0.24, True), -1.0)
        self.assertIsNone(pm.bet_return("yes", 0.985, True))
        self.assertEqual(pm.parse_p('x {"p_yes": 0.42, "reason": "r"}'), 0.42)
        self.assertIsNone(pm.parse_p('{"p_yes": 1.4}'))
        self.assertIn(pm.control_side("9"), ("yes", "no"))


class Verdict(unittest.TestCase):
    def rows(self, win_every):
        out = []
        for i in range(150):
            won = i % win_every == 0
            out.append({"event": str(i % 60), "t0": NOW + i, "end": NOW + 86400 + i, "q": 0.6 if won else 0.4,
                        "p": 0.3, "yes_won": won, "ret": (1 / 0.31 - 1) if won else -1.0,
                        "ret_stress": (1 / 0.33 - 1) if won else -1.0, "ctrl_ret": -1.0 if i % 2 else 0.2})
        return out

    def test_edge_and_none(self):
        self.assertEqual(pm.summarize(self.rows(2))["verdict"], "edge")
        self.assertEqual(pm.summarize(self.rows(5))["verdict"], "no edge shown")
        self.assertTrue(pm.summarize(self.rows(2)[:10])["verdict"].startswith("too few"))

    def test_account_path_compounds(self):
        rows = [{"t0": 1, "end": 2, "ret": 2.0}, {"t0": 3, "end": 4, "ret": -1.0}]
        r = pm.account_path(rows, 0.5, start=100)
        self.assertAlmostEqual(r["end_equity"], 100 + 50 * 2 - 100)        # 200 after the win, then lose half


if __name__ == "__main__":
    unittest.main()
