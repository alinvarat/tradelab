import calendar
import unittest

from core import options_forward as of

ATOM = """<?xml version="1.0"?><feed>
<entry>
<title>8-K - APPLE INC (0000320193) (Filer)</title>
<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/0000320193-26-000001-index.htm"/>
<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-11-23 &lt;br&gt;Item 2.02: Results of Operations and Financial Condition
&lt;br&gt;Item 9.01: Financial Statements and Exhibits</summary>
<updated>2026-11-23T16:30:05-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0000320193-26-000001</id>
</entry>
<entry>
<title>8-K - NEVADA POWER CO (0000071180) (Filer)</title>
<summary type="html">&lt;br&gt;Item 8.01: Other Events</summary>
<updated>2026-11-23T09:00:00-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0001104659-26-000002</id>
</entry></feed>"""


class Feed(unittest.TestCase):
    def test_atom_entries_items_and_utc_time(self):
        got = of.parse_current_atom(ATOM)
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["accession"], "0000320193-26-000001")
        self.assertEqual(got[0]["cik"], 320193)
        self.assertEqual(got[0]["items"], ["2.02", "9.01"])
        self.assertEqual(got[0]["updated"], calendar.timegm((2026, 11, 23, 21, 30, 5)))
        self.assertTrue(got[0]["index_url"].endswith("-index.htm"))
        self.assertEqual(got[1]["items"], ["8.01"])


class Contracts(unittest.TestCase):
    chain = {"calls": [{"strike": s, "ask": 1.0, "contractSymbol": f"C{s}"} for s in (100, 104, 105, 106, 110)],
             "puts": [{"strike": s, "ask": 1.0, "contractSymbol": f"P{s}"} for s in (90, 94, 95, 96, 100)]}

    def test_otm_strike_choice(self):
        self.assertEqual(of.pick_contract(self.chain, 100.0, "long")["strike"], 105)
        self.assertEqual(of.pick_contract(self.chain, 100.0, "short")["strike"], 95)
        self.assertIsNone(of.pick_contract(self.chain, 100.0, "skip"))
        self.assertIsNone(of.pick_contract(self.chain, 200.0, "long"))

    def test_expiry_at_least_seven_days(self):
        now = 1_800_000_000
        exps = [now + 3 * 86400, now + 7 * 86400 - 1, now + 10 * 86400, now + 30 * 86400]
        self.assertEqual(of.choose_expiry(exps, now), now + 10 * 86400)
        self.assertIsNone(of.choose_expiry([now], now))

    def test_random_control_direction_is_deterministic(self):
        self.assertEqual(of.random_direction("AAPL", "x"), of.random_direction("AAPL", "x"))
        self.assertIn(of.random_direction("AAPL", "x"), ("long", "short"))


class Returns(unittest.TestCase):
    def test_trade_return_pays_ask_and_fees_and_haircut(self):
        self.assertAlmostEqual(of.trade_return(1.0, 2.0), (200 - 0.65) / (100 + 0.65) - 1)
        self.assertAlmostEqual(of.trade_return(1.0, 0.0), -1.0)
        self.assertLess(of.trade_return(1.0, 2.0, haircut=0.1), of.trade_return(1.0, 2.0))

    def test_intrinsic_and_sessions(self):
        self.assertEqual(of.intrinsic("long", 105, 110), 5)
        self.assertEqual(of.intrinsic("short", 95, 110), 0)
        self.assertEqual(of.sessions_after(["2026-11-20", "2026-11-23", "2026-11-24"], "2026-11-20"), 2)


class Account(unittest.TestCase):
    def test_whole_contracts_can_be_unaffordable(self):
        trades = [{"entry_ts": 1, "exit_ts": 2, "entry_ask": 5.0, "exit_bid": 10.0}]   # 500.65 USD a contract
        r = of.simulate_account(trades, start=147)
        self.assertEqual(r["taken"], 0)
        self.assertEqual(r["unaffordable"], 1)
        self.assertAlmostEqual(r["end_equity_usd"], 147)

    def test_fractional_compounds_and_stake_is_20_percent(self):
        trades = [{"entry_ts": 1, "exit_ts": 2, "entry_ask": 0.10, "exit_bid": 0.30}]
        r = of.simulate_account(trades, start=100, whole_contracts=False)
        unit = 0.10 * 100 + of.FEE
        n = 20 / unit
        self.assertAlmostEqual(r["end_equity_usd"], 80 + n * (30 - of.FEE))


class Verdict(unittest.TestCase):
    def test_collecting_until_150(self):
        self.assertTrue(of.verdict([])["verdict"].startswith("collecting"))

    def test_edge_needs_return_diff_and_haircut(self):
        good = [{"symbol": f"S{i % 40}", "ts": 1_800_000_000 + 86400 * 31 * (i // 40), "ret": 0.8 if i % 3 else -1.0,
                 "ctrl_ret": -0.5, "ret_haircut": 0.6 if i % 3 else -1.0} for i in range(200)]
        self.assertEqual(of.verdict(good)["verdict"], "edge")
        bad = [dict(t, ret=-0.2, ret_haircut=-0.3) for t in good]
        self.assertEqual(of.verdict(bad)["verdict"], "no edge shown")


if __name__ == "__main__":
    unittest.main()
