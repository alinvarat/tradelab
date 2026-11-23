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
