import calendar
import unittest
from unittest.mock import patch

from core import options_forward as of
from research.studies import options_forward as runner

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
    def test_all_filing_types_are_eligible_only_in_the_new_window(self):
        start = of.ALL_ITEMS_START_TS
        self.assertIsNone(of.filing_protocol({"ts": start - 1, "items": ["8.01"]}))
        self.assertEqual(of.filing_protocol({"ts": start - 1, "items": ["2.02"]}), of.EARNINGS_PROTOCOL)
        for items in (["2.02"], ["5.02"], ["8.01"], []):
            self.assertEqual(of.filing_protocol({"ts": start, "items": items}), of.ALL_ITEMS_PROTOCOL)

    def test_iso_variants(self):
        self.assertEqual(of.iso_to_ts("2026-11-23T21:30:05Z"), calendar.timegm((2026, 11, 23, 21, 30, 5)))
        self.assertEqual(of.iso_to_ts("2026-11-23T21:30:05.000Z"), calendar.timegm((2026, 11, 23, 21, 30, 5)))
        self.assertEqual(of.iso_to_ts("2026-11-23T16:30:05-0500"), calendar.timegm((2026, 11, 23, 21, 30, 5)))
        with self.assertRaises(ValueError):
            of.iso_to_ts("yesterday")

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

    def test_expiry_at_least_seven_days_by_date(self):
        now = calendar.timegm((2026, 11, 24, 15, 0, 0))
        dec1, nov30, dec4 = (calendar.timegm((2026, 12, d % 100, 0, 0, 0)) if d > 100 else calendar.timegm((2026, 11, d, 0, 0, 0))
                             for d in (101, 30, 104))
        self.assertEqual(of.choose_expiry([nov30, dec1, dec4], now), dec1)      # exactly 7 calendar days counts
        self.assertIsNone(of.choose_expiry([nov30], now))

    def test_valid_ask_and_median(self):
        self.assertTrue(of.valid_ask(0.05))
        for bad in (0, -0.01, None, "x", float("nan")):
            self.assertFalse(of.valid_ask(bad))
        bars = [{"c": 1, "v": 80e6}] * 10 + [{"c": 1, "v": 110e6}] * 10
        self.assertAlmostEqual(of.median_dollar_volume(bars), 95e6)
        self.assertIsNone(of.median_dollar_volume(bars[:19]))

    def test_random_control_direction_is_deterministic(self):
        self.assertEqual(of.random_direction("AAPL", "x"), of.random_direction("AAPL", "x"))
        self.assertIn(of.random_direction("AAPL", "x"), ("long", "short"))


class Returns(unittest.TestCase):
    def test_trade_return_pays_ask_and_fees_and_haircut(self):
        self.assertAlmostEqual(of.trade_return(1.0, 2.0), (200 - 0.65) / (100 + 0.65) - 1)
        self.assertAlmostEqual(of.trade_return(1.0, 0.0), (-0.65) / 100.65 - 1)     # the exit fee is still paid
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


class WebullVariant(unittest.TestCase):
    def test_default_costs_are_unchanged_and_variant_is_cheaper(self):
        self.assertAlmostEqual(of.trade_return(1.0, 2.0), (200 - 0.65) / (100 + 0.65) - 1)    # locked model untouched
        wb = {"buy_fee": of.webull_buy_fee, "sell_fee": of.webull_sell_fee}
        self.assertGreater(of.trade_return(1.0, 2.0, **wb), of.trade_return(1.0, 2.0))
        cost = of.webull_buy_fee(1.0)
        proceeds_fee = of.webull_sell_fee(2.0)
        self.assertAlmostEqual(of.trade_return(1.0, 2.0, **wb), (200 - proceeds_fee) / (100 + cost) - 1)
        self.assertGreater(of.webull_sell_fee(0.0), 0)          # a zero bid still pays the per-contract fees

    def test_account_with_webull_fees(self):
        trades = [{"entry_ts": 1, "exit_ts": 2, "entry_ask": 0.10, "exit_bid": 0.30}]
        r = of.simulate_account(trades, start=100, whole_contracts=False,
                                buy_fee=of.webull_buy_fee, sell_fee=of.webull_sell_fee)
        unit = 10 + of.webull_buy_fee(0.10)
        n = 20 / unit
        self.assertAlmostEqual(r["end_equity_usd"], 80 + n * (30 - of.webull_sell_fee(0.30)))
        self.assertGreater(r["end_equity_usd"], of.simulate_account(trades, start=100, whole_contracts=False)["end_equity_usd"])

    def test_summary_reports_variant_without_touching_verdict(self):
        start = of.ALL_ITEMS_START_TS
        model = {"entry_ts": start, "exit_ts": start + 86400, "entry_ask": 0.20, "exit_bid": 0.40}
        trade = {"symbol": "AAA", "ts": start, "model": model, "control": {**model, "exit_bid": 0.10}}
        out = runner.protocol_summary({"open": [], "closed": [trade], "calls": []})
        self.assertIn("webull_cost_variant", out)
        v = out["webull_cost_variant"]
        self.assertGreater(v["account_whole_contracts"]["end_equity_usd"], out["account_whole_contracts"]["end_equity_usd"])
        self.assertTrue(v["verdict"]["verdict"].startswith("collecting"))
        self.assertTrue(out["verdict"]["verdict"].startswith("collecting"))


class AccountOrder(unittest.TestCase):
    def test_exit_cash_funds_an_entry_at_the_same_time(self):
        trades = [{"entry_ts": 1, "exit_ts": 5, "entry_ask": 0.2, "exit_bid": 0.4},
                  {"entry_ts": 5, "exit_ts": 9, "entry_ask": 0.2, "exit_bid": 0.2}]
        r = of.simulate_account(trades, start=100, stake=1.0)
        self.assertEqual(r["taken"], 2)
        self.assertIn("months_3x", r)
        self.assertIn("worst_drawdown", r)


class Verdict(unittest.TestCase):
    def test_summary_keeps_old_and_new_options_wallets_separate(self):
        state = {"open": [{}, {"protocol": of.ALL_ITEMS_PROTOCOL}], "closed": [], "gaps": [{}],
                 "calls": {"older": {}, "newer": {"protocol": of.ALL_ITEMS_PROTOCOL}}}
        with patch.object(runner.time, "time", return_value=of.ALL_ITEMS_START_TS):
            result = runner.summary(state)
        self.assertEqual(result["protocol"], of.ALL_ITEMS_PROTOCOL)
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["gaps"], 1)
        self.assertEqual(result["by_protocol"][of.EARNINGS_PROTOCOL]["open"], 1)

    def test_matched_wallets_use_both_legs_and_stress_both_exits(self):
        start = of.ALL_ITEMS_START_TS
        model = {"entry_ts": start, "exit_ts": start + 86400, "entry_ask": 0.20, "exit_bid": 0.40}
        trade = {"symbol": "AAA", "ts": start, "model": model, "control": {**model, "exit_bid": 0.10}}
        wallets = runner.protocol_summary({"open": [], "closed": [trade], "calls": []})["matched_whole_contract_wallets"]
        self.assertGreater(wallets["model"]["base"]["end_equity_usd"], 147.0)
        self.assertLess(wallets["control"]["base"]["end_equity_usd"], 147.0)
        for arm in wallets.values():
            self.assertLess(arm["stress"]["end_equity_usd"], arm["base"]["end_equity_usd"])

    def test_collecting_until_150(self):
        self.assertTrue(of.verdict([])["verdict"].startswith("collecting"))

    def test_edge_needs_return_diff_and_haircut(self):
        good = [{"symbol": f"S{i % 40}", "ts": 1_800_000_000 + 86400 * 31 * (i // 40), "ret": 0.8 if i % 3 else -1.0,
                 "ctrl_ret": -0.5, "ret_haircut": 0.6 if i % 3 else -1.0} for i in range(200)]
        self.assertEqual(of.verdict(good)["verdict"], "edge")
        bad = [dict(t, ret=-0.2, ret_haircut=-0.3) for t in good]
        self.assertEqual(of.verdict(bad)["verdict"], "no edge shown")

    def test_missing_control_keeps_the_model_trade(self):
        rows = [{"symbol": f"S{i % 40}", "ts": 1_800_000_000 + 86400 * 31 * (i // 40), "ret": 0.8 if i % 3 else -1.0,
                 "ctrl_ret": None if i % 5 == 0 else -0.5, "ret_haircut": 0.6 if i % 3 else -1.0} for i in range(200)]
        v = of.verdict(rows)
        self.assertEqual(v["n"], 200)
        self.assertEqual(v["n_paired"], 160)


if __name__ == "__main__":
    unittest.main()
