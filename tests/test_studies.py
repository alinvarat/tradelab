import calendar
import unittest

from core import studies as st


def day(s):
    return calendar.timegm((int(s[:4]), int(s[5:7]), int(s[8:10]), 14, 30, 0))


def bars_for(days, start=100.0, step=1.0):
    out, p = [], start
    for d in days:
        out.append({"t": day(d), "o": p, "h": p, "l": p, "c": p + step / 2, "v": 1})
        p += step
    return out


def business_days(first, n):
    out, t = [], day(first)
    while len(out) < n:
        g = __import__("time").gmtime(t)
        if g.tm_wday < 5:
            out.append(__import__("time").strftime("%Y-%m-%d", g))
        t += 86400
    return out


class Months(unittest.TestCase):
    def test_add_months_wraps_years(self):
        self.assertEqual(st.add_months("2024-01", -1), "2023-12")
        self.assertEqual(st.add_months("2024-12", 1), "2025-01")
        self.assertEqual(st.add_months("2024-05", -12), "2023-05")

    def test_month_end_needs_the_next_session(self):
        b = bars_for(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29"])
        self.assertEqual(st.month_end_indices(b), [1])       # February is not known to be over yet

    def test_window_is_open_to_close(self):
        b = bars_for(["2024-01-30", "2024-01-31", "2024-02-01"])
        self.assertAlmostEqual(st.window_gross(b, 0, 2), b[2]["c"] / b[0]["o"] - 1)
        self.assertIsNone(st.window_gross(b, 1, 5))


class TurnOfMonth(unittest.TestCase):
    def setUp(self):
        self.b = bars_for(business_days("2023-01-02", 300))

    def test_event_starts_at_the_last_session_and_control_is_outside_every_window(self):
        rows = st.tom_rows("AAA", self.b)
        ends = st.month_end_indices(self.b)
        window = {self.b[k]["t"] for i in ends for k in range(i, i + st.TOM_HOLD) if k < len(self.b)}
        self.assertTrue(rows)
        self.assertEqual(rows[0]["ts"], self.b[ends[0]]["t"])
        for r in rows:
            self.assertNotIn(r["ctrl_start_t"], window)
            self.assertEqual(r["horizon"], st.TOM_HOLD)

    def test_rows_are_deterministic(self):
        self.assertEqual(st.tom_rows("AAA", self.b), st.tom_rows("AAA", self.b))

    def test_placebo_moves_the_window_20_to_60_sessions(self):
        idx = {b["t"]: i for i, b in enumerate(self.b)}
        placebo = st.tom_rows("AAA", self.b, placebo=True)
        self.assertTrue(placebo)
        for p in placebo:
            shift = idx[p["ts"]] - idx[p["event_t"]]
            self.assertGreaterEqual(shift, 20)
            self.assertLessEqual(shift, 60)


class Momentum(unittest.TestCase):
    def test_top_decile_is_the_best_12_1_and_control_is_the_whole_basket(self):
        days = business_days("2022-01-03", 340)
        pool = {f"S{i:02d}": bars_for(days, 100.0, step=0.01 * (i + 1)) for i in range(20)}
        rows = st.momentum_rows(pool)
        self.assertTrue(rows)
        r = rows[0]
        self.assertEqual(r["basket"], 20)
        self.assertEqual(r["top"], ["S19", "S18"])          # top 10% of 20 = the two steepest
        self.assertGreater(r["gross"], r["ctrl_gross"])
        self.assertEqual(r["month"], st.add_months(st.month_key(r["ts"]), 0))

    def test_too_few_names_means_no_month(self):
        days = business_days("2022-01-03", 340)
        self.assertEqual(st.momentum_rows({"A": bars_for(days)}), [])


class PointInTime(unittest.TestCase):
    def test_membership_spells_and_dot_tickers(self):
        m = st.parse_membership("ticker,start_date,end_date\nAAL,1996-01-02,1997-01-15\nAAL,2015-03-23,2024-09-23\n"
                                "BRK.B,2010-02-16,\n")
        self.assertEqual(m["AAL"], [("1996-01-02", "1997-01-15"), ("2015-03-23", "2024-09-23")])
        self.assertIn("BRK-B", m)
        self.assertEqual(st.members_on(m, "2020-01-31"), {"AAL", "BRK-B"})
        self.assertEqual(st.members_on(m, "2024-09-23"), {"BRK-B"})        # gone on its end date
        self.assertEqual(st.members_on(m, "2000-01-31"), set())

    def test_non_members_are_never_picked(self):
        days = business_days("2022-01-03", 340)
        pool = {f"S{i:02d}": bars_for(days, 100.0, step=0.01 * (i + 1)) for i in range(20)}
        allowed = {f"S{i:02d}" for i in range(15)}                         # the steepest five are not members
        rows = st.momentum_rows(pool, members=lambda day: allowed)
        self.assertTrue(rows)
        for r in rows:
            self.assertTrue(set(r["top"]) <= allowed)
            self.assertEqual(r["basket"], 15)
            self.assertAlmostEqual(r["coverage"], 1.0)
        self.assertEqual(rows[0]["top"], ["S14"])                          # 10% of 15 = 1


class LlmEarnings(unittest.TestCase):
    def test_parse_reply(self):
        self.assertEqual(st.parse_direction('ok {"direction": "Short", "confidence": 80, "reason": "guide cut"}'),
                         {"direction": "short", "confidence": 80, "reason": "guide cut"})
        self.assertEqual(st.parse_direction("no json")["direction"], "skip")
        self.assertEqual(st.parse_direction('{"direction": "buy"}')["direction"], "skip")
        self.assertEqual(st.parse_direction('{"direction": "long", "confidence": 250}')["confidence"], 100)

    def test_exhibit_and_text(self):
        self.assertEqual(st.pick_exhibit(["a8-k.htm", "aex991.htm", "R1.htm"], "a8-k.htm"), "aex991.htm")
        self.assertEqual(st.pick_exhibit(["a8-k.htm"], "a8-k.htm"), "a8-k.htm")
        self.assertEqual(st.html_text("<html><style>x{}</style><p>Revenue&nbsp;up  <b>9%</b></p></html>"),
                         "Revenue up 9%")

    def test_short_gains_when_price_falls_and_both_sides_pay_cost(self):
        self.assertAlmostEqual(st.signed_net(-0.05, -1), 1.05 * (1 - 0.0009) ** 2 - 1)
        self.assertLess(st.signed_net(0.0, 1), 0)
        self.assertEqual(st.signed_net(0.05, 0), 0.0)

    def test_summary_and_verdict(self):
        rows = []
        for i in range(80):
            g = 0.02 if i % 2 else -0.02
            for h in (1, 3, 5):
                rows.append({"symbol": f"S{i % 20}", "ts": 1790000000 + 86400 * 31 * (i // 20), "horizon": h,
                             "gross": g, "direction": "long" if g > 0 else "short", "confidence": 90,
                             "rand_sign": 1 if i % 3 else -1})
        h1 = st.llm_summary(rows, 1)
        self.assertEqual(h1["n"], 80)
        self.assertEqual(h1["hit"], 1.0)
        self.assertGreater(h1["mean_diff"], 0)
        self.assertEqual(st.llm_verdict(rows), "edge candidate")
        self.assertEqual(st.llm_verdict(rows[:30]), "too few, keep collecting")


class ForwardEarnings(unittest.TestCase):
    def rows(self, n, g5):
        out = []
        for i in range(n):
            for h, g in ((1, 0.0), (3, 0.01), (5, g5 if i % 4 else -g5 / 2)):
                out.append({"symbol": f"S{i % 50}", "ts": 1796000000 + 86400 * 31 * (i // 50), "horizon": h,
                            "gross": g, "direction": "long", "confidence": 80, "rand_sign": -1 if i % 2 else 1})
        return out

    def test_waits_for_600_trades(self):
        self.assertEqual(st.llm_forward_verdict(self.rows(100, 0.03)), "collecting (100/600 trades)")

    def test_clear_h5_drift_is_an_edge_and_flat_is_not(self):
        self.assertEqual(st.llm_forward_verdict(self.rows(640, 0.03)), "edge")
        self.assertEqual(st.llm_forward_verdict(self.rows(640, 0.0)), "no edge shown")


class Other8K(unittest.TestCase):
    def test_prompt_allows_skipping_routine_filings(self):
        self.assertIn("skip", st.LLM_SYSTEM_8K)
        self.assertIn("8-K", st.LLM_SYSTEM_8K)


class WideEarnings(unittest.TestCase):
    def test_form_idx_keeps_only_plain_8k(self):
        text = ("Form Type   Company Name   CIK   Date Filed   File Name\n" + "-" * 40 + "\n"
                "8-K              APPLE INC                        320193      20261020    edgar/data/320193/0001140361-26-042798.txt\n"
                "8-K/A            3M CO 2                          66740       20261020    edgar/data/66740/0000066740-26-000099.txt\n"
                "10-Q             MICROSOFT CORP                   789019      20261020    edgar/data/789019/0000950170-26-000001.txt\n")
        got = st.parse_form_idx(text)
        self.assertEqual(got, [{"form": "8-K", "cik": 320193, "accession": "0001140361-26-042798", "date": "2026-10-20"}])

    def test_liquidity_tiers_and_exclusions(self):
        def mk(price, vol, n=25):
            return [{"t": i, "o": price, "h": price, "l": price, "c": price, "v": vol} for i in range(n)]
        self.assertEqual(st.liquidity_cost(mk(50, 3_000_000), 22), 0.0009)       # 150M/day
        self.assertEqual(st.liquidity_cost(mk(50, 1_000_000), 22), 0.0020)       # 50M
        self.assertEqual(st.liquidity_cost(mk(50, 200_000), 22), 0.0040)         # 10M
        self.assertIsNone(st.liquidity_cost(mk(50, 50_000), 22))                 # 2.5M: too thin
        self.assertIsNone(st.liquidity_cost(mk(2, 50_000_000), 22))              # under 3 USD
        self.assertIsNone(st.liquidity_cost(mk(50, 3_000_000), 3))               # not enough history

    def test_tier_cost_is_charged_on_both_sides(self):
        self.assertAlmostEqual(st.signed_net(0.0, 1, 1.0, 0.004), (1 - 0.004) ** 2 - 1)
        self.assertAlmostEqual(st.signed_net(0.0, 1, 2.0, 0.004), (1 - 0.008) ** 2 - 1)

    def test_daily_book_averages_each_entry_session(self):
        rows = [{"horizon": 1, "direction": "long", "gross": 0.02, "entry_t": 1},
                {"horizon": 1, "direction": "short", "gross": 0.02, "entry_t": 1},
                {"horizon": 1, "direction": "skip", "gross": 0.5, "entry_t": 1},
                {"horizon": 3, "direction": "long", "gross": 0.5, "entry_t": 2},
                {"horizon": 1, "direction": "long", "gross": 0.01, "entry_t": 2}]
        book = st.daily_book(rows)
        self.assertEqual([t for t, _ in book], [1, 2])
        self.assertAlmostEqual(book[0][1], (st.signed_net(0.02, 1) + st.signed_net(0.02, -1)) / 2)
        p = st.leverage_path([0.1, -0.5], 2)
        self.assertAlmostEqual(p["end_equity"], 0.0)
        self.assertAlmostEqual(p["worst_drawdown"], -1.0)


class Items(unittest.TestCase):
    def test_only_locked_items_count_and_each_counts_once(self):
        self.assertEqual(st.item_tags(["2.02", "9.01"]), ["2.02"])
        self.assertEqual(st.item_tags(["5.02", "1.01", "7.01"]), ["1.01", "5.02"])
        self.assertEqual(st.item_tags(["8.01"]), [])


class Form4(unittest.TestCase):
    def test_officer_open_market_purchase_over_50k_only(self):
        subs = [{"ACCESSION_NUMBER": a, "FILING_DATE": "05-MAR-2024", "DOCUMENT_TYPE": d, "ISSUERTRADINGSYMBOL": s}
                for a, d, s in (("1", "4", "AAPL"), ("2", "4", "AAPL"), ("3", "4", "AAPL"), ("4", "4/A", "AAPL"),
                                ("5", "4", "XXXX"), ("6", "4", "BRK.B"), ("7", "4", "AAPL"))]
        owners = [{"ACCESSION_NUMBER": a, "RPTOWNER_RELATIONSHIP": r}
                  for a, r in (("1", "Officer"), ("2", "Director"), ("3", "TenPercentOwner"), ("4", "Officer"),
                               ("5", "Director"), ("6", "Director,TenPercentOwner"), ("7", "Officer"))]
        trans = [{"ACCESSION_NUMBER": a, "TRANS_CODE": c, "TRANS_SHARES": n, "TRANS_PRICEPERSHARE": p,
                  "TRANS_ACQUIRED_DISP_CD": ad}
                 for a, c, n, p, ad in (("1", "P", "1000", "60", "A"), ("2", "P", "100", "60", "A"),
                                        ("2", "P", "100", "60", "A"), ("3", "P", "5000", "60", "A"),
                                        ("4", "P", "5000", "60", "A"), ("5", "P", "5000", "60", "A"),
                                        ("6", "P", "500", "200", "A"), ("7", "A", "9000", "60", "A"))]
        got = st.insider_purchases(subs, owners, trans, {"AAPL", "BRK-B"})
        self.assertEqual(sorted(g["accession"] for g in got), ["1", "6"])
        self.assertEqual(got[0]["date"], "2024-03-05")
        self.assertAlmostEqual(got[0]["value"], 60000)

    def test_filing_dates_and_conservative_stamp(self):
        self.assertEqual(st.parse_filing_date("05-MAR-2024"), "2024-03-05")
        self.assertEqual(st.parse_filing_date("2024-03-05"), "2024-03-05")
        self.assertIsNone(st.parse_filing_date("nope"))
        ts = st.conservative_ts("2024-03-05")
        self.assertEqual(ts, calendar.timegm((2024, 3, 6, 4, 0, 0)))   # after 22:00 ET on the filing date


class Verdict(unittest.TestCase):
    def rows(self, diff_by_split, n=200, symbols=10):
        out = []
        for sp, d, ts in (("train", diff_by_split[0], day("2020-03-02")),
                          ("validation", diff_by_split[1], day("2023-03-01")),
                          ("test", diff_by_split[2], day("2025-03-03"))):
            for i in range(n):
                out.append({"symbol": f"S{i % symbols}", "ts": ts + 86400 * 31 * (i // symbols), "split": sp,
                            "gross": 0.02 + d + (0.001 if i % 2 else -0.001), "ctrl_gross": 0.02})
        return out

    def test_a_clear_spread_out_edge_passes(self):
        v = st.verdict(self.rows((0.01, 0.01, 0.01)))
        self.assertTrue(v["passed"], v["checks"])

    def test_negative_test_slice_fails(self):
        v = st.verdict(self.rows((0.01, 0.01, -0.01)))
        self.assertFalse(v["checks"]["3_diff_pos_test"])
        self.assertFalse(v["passed"])

    def test_one_symbol_carrying_the_result_fails(self):
        v = st.verdict(self.rows((0.01, 0.01, 0.01), symbols=2))
        self.assertFalse(v["checks"]["5_no_group_over_25pct"])

    def test_empty_never_passes(self):
        self.assertFalse(st.verdict([])["passed"])


if __name__ == "__main__":
    unittest.main()
