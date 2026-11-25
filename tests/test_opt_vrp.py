"""Offline tests for the opt_vrp study (core/opt_vrp.py, research/studies/opt_vrp.py). Synthetic data only."""
import hashlib
import math
import unittest
from pathlib import Path

from core import opt_vrp as ov
from research.studies import opt_vrp as io

FOLDER = Path(__file__).resolve().parents[1] / "research" / "studies"
D = "2025-01-10"
E = ov.entry_times(D, "am")[0]
EXP = ov.expiry_ts(D)


class ProtocolLock(unittest.TestCase):
    def test_protocol_unchanged(self):
        got = hashlib.sha256((FOLDER / "protocol_opt_vrp_20261125.md").read_bytes()).hexdigest()
        self.assertEqual(got, (FOLDER / "protocol_opt_vrp_20261125.sha256").read_text().strip(),
                         "protocol is locked; write a new dated protocol instead")


class Strikes(unittest.TestCase):
    grid = [float(k) for k in range(50000, 70001, 1000)]

    def test_put_and_call(self):
        s = ov.sigma_d(50)
        self.assertAlmostEqual(s, 0.5 / math.sqrt(365))
        self.assertEqual(ov.pick_strikes(self.grid, 60000, s, 1.0, "put"), (58000.0, 57000.0))   # 58430 -> 58000; need 786
        self.assertEqual(ov.pick_strikes(self.grid, 60000, s, 1.0, "call"), (62000.0, 63000.0))  # 61570 -> 62000
        self.assertEqual(ov.pick_strikes(self.grid, 60000, s, 1.3, "put")[0], 57000.0)

    def test_wing_is_nearest_beyond_half_sigma(self):
        grid = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]
        short, wing = ov.pick_strikes(grid, 150.0, 0.1, 1.0, "put")      # target 135 -> 130; need 7.5 -> 120
        self.assertEqual((short, wing), (130.0, 120.0))

    def test_no_grid_and_no_wing(self):
        self.assertEqual(ov.pick_strikes([100.0], 150.0, 0.1, 1.0, "put"), (None, "no_wing"))
        self.assertEqual(ov.pick_strikes([200.0], 150.0, 0.1, 1.0, "put"), (None, "no_grid"))
        self.assertEqual(ov.pick_strikes([100.0, 101.0], 150.0, 0.1, 1.0, "put"), (None, "no_wing"))

    def test_parse_name(self):
        self.assertEqual(ov.parse_name("BTC-27NOV26-90000-P"), ("BTC", "2026-11-27", 90000.0, "put"))
        self.assertEqual(ov.parse_name("ETH_USDC-1DEC26-3000-C"), ("ETH", "2026-12-01", 3000.0, "call"))
        self.assertIsNone(ov.parse_name("BTC-PERPETUAL"))


class Economics(unittest.TestCase):
    def row(self, delivery):
        return {"status": "ok", "side": "put", "short_k": 58000.0, "long_k": 57000.0, "s_px": 0.001, "s_idx": 60000.0,
                "l_px": 0.0005, "l_idx": 60000.0, "index": 60000.0, "delivery": delivery}

    def test_otm_win_base(self):
        e = ov.side_econ(self.row(59000.0), "base")
        self.assertAlmostEqual(e["credit"], 54 - 33 - 6.75 - 4.125)           # 10.125
        self.assertAlmostEqual(e["pnl"], 10.125)
        self.assertEqual(e["width"], 1000.0)
        self.assertAlmostEqual(e["margin_b"], (0.15 - 2000 / 60000) * 60000 + 54 + 33)

    def test_short_only_itm_and_full_loss(self):
        e = ov.side_econ(self.row(57500.0), "base")
        self.assertAlmostEqual(e["pnl"], 10.125 - 500 - 0.00015 * 57500)       # delivery fee capped at 0.00015
        full = ov.side_econ(self.row(56000.0), "base")
        self.assertAlmostEqual(full["pnl"], 10.125 - 1000 - 2 * 0.00015 * 56000)

    def test_high_cost_is_worse(self):
        b, h = ov.side_econ(self.row(59000.0), "base"), ov.side_econ(self.row(59000.0), "high")
        self.assertLess(h["credit"], b["credit"])
        self.assertAlmostEqual(h["credit"], 45 - 37.5 - 11.25 - 9.375)    # haircut 25%, fees x2

    def test_struct_max_loss_and_condor(self):
        e = ov.struct_econ([self.row(59000.0)], "base", "BTC")
        self.assertAlmostEqual(e["max_loss"], 1000 - 10.125)
        call = dict(self.row(59000.0), side="call", short_k=62000.0, long_k=63000.0)
        c = ov.struct_econ([self.row(59000.0), call], "base", "BTC")
        self.assertAlmostEqual(c["credit"], 2 * 10.125)
        self.assertAlmostEqual(c["max_loss"], 1000 - 2 * 10.125)           # one wing only
        self.assertEqual(c["step"], 0.01)

    def test_reasons(self):
        r = self.row(59000.0)
        self.assertEqual(ov.struct_econ([dict(r, status="no_short_print")], "base", "BTC")["reason"], "no_short_print")
        self.assertEqual(ov.struct_econ([r, dict(r, side="call", status="no_wing")], "base", "BTC")["reason"], "call:no_wing")
        self.assertEqual(ov.struct_econ([dict(r, delivery=None)], "base", "BTC")["reason"], "no_delivery")
        self.assertEqual(ov.struct_econ([dict(r, s_px=0.0001, l_px=0.01)], "base", "BTC")["reason"], "no_credit")
        self.assertEqual(ov.struct_econ([dict(r, s_px=0.2, l_px=0.0001)], "base", "BTC")["reason"], "credit_ge_width")

    def test_short_call_gain(self):
        r = {"status": "ok", "side": "call", "short_k": 62000.0, "long_k": 63000.0, "s_px": 0.001, "s_idx": 60000.0,
             "l_px": 0.0005, "l_idx": 60000.0, "index": 60000.0, "delivery": 62300.0}
        e = ov.side_econ(r, "base")
        self.assertAlmostEqual(e["pnl"], 10.125 - 300 - 0.00015 * 62300)


class Sizing(unittest.TestCase):
    econ = {"max_loss": 989.875, "margin_a": 989.875, "margin_b": 7087.0, "step": 0.01, "credit": 10.125, "pnl": 10.125}

    def test_steps(self):
        self.assertEqual(ov.size_steps(147.0, self.econ, "A"), (2, None))
        self.assertEqual(ov.size_steps(147.0, self.econ, "B"), (1, None))
        self.assertEqual(ov.size_steps(40.0, self.econ, "A"), (0, "size_below_minimum"))
        self.assertEqual(ov.size_steps(147.0, dict(self.econ, margin_b=20000.0), "B"), (0, "margin"))


class Account(unittest.TestCase):
    def e(self, pnl):
        return {"max_loss": 10.0, "margin_a": 10.0, "margin_b": 30.0, "step": 1.0, "credit": 1.0, "pnl": pnl}

    def test_compounding_and_months(self):
        tr = [("2025-01-05", self.e(1.0)), ("2025-01-06", self.e(1.0)), ("2025-02-03", self.e(-10.0))]
        r = ov.sim(tr, ["2025-01", "2025-02", "2025-03"], "A")
        self.assertEqual([t["steps"] for t in r["trades"]], [2, 2, 3])             # floor(0.2*147/10)=2; 149/10*.2=2; ...
        self.assertAlmostEqual(r["trades"][0]["ret"], 2 / 147)
        self.assertEqual(r["funded_months"], 2)                                   # Jan 147, Feb 151, Mar 121 -> below start
        self.assertAlmostEqual(r["month_multiple"]["2025-02"], r["ending_equity"] / (147 + 4))

    def test_ruin_stops(self):
        tr = [(f"2025-01-{d:02d}", self.e(-10.0)) for d in range(1, 20)]
        r = ov.sim(tr, ["2025-01"], "A")
        self.assertTrue(r["ruined"] or r["attrition"])
        self.assertGreaterEqual(r["ending_equity"], 0.0)
        self.assertLess(len(r["trades"]), 19)

    def test_funded_3x(self):
        big = dict(self.e(60.0), max_loss=10.0)                                  # +600% on risk per step
        r = ov.sim([("2025-01-02", big), ("2025-01-03", big)], ["2025-01"], "A")
        self.assertEqual(r["funded_3x"], ["2025-01"])

    def test_ceiling_all_win_vs_oracle(self):
        tr = [(f"2025-01-{d:02d}", dict(self.e(-10.0), credit=6.0)) for d in range(1, 29)]
        c = ov.ceiling(tr, ["2025-01"])
        self.assertEqual(c["all_win"]["months_3x"], 1)       # compounding reaches 3x within about 12 trades
        self.assertEqual(c["oracle"]["months_3x"], 0)        # oracle skips every losing day
        small = [(f"2025-01-{d:02d}", dict(self.e(-10.0), credit=0.3)) for d in range(1, 29)]
        self.assertEqual(ov.ceiling(small, ["2025-01"])["all_win"]["months_3x"], 0)

    def test_draw_share(self):
        pool = [float(i) for i in range(100)]
        self.assertLess(ov.draw_share([99.0, 98.0, 97.0, 96.0, 95.0], pool), 0.01)
        self.assertGreater(ov.draw_share([0.0, 1.0, 2.0], pool), 0.99)
        self.assertEqual(ov.draw_share([1.0] * 5, pool), ov.draw_share([1.0] * 5, pool))
        self.assertIsNone(ov.draw_share([], pool))


class Features(unittest.TestCase):
    def test_rv_and_return(self):
        closes = {3600 * i: 100.0 * (1.01 if i % 2 else 1.0) for i in range(300)}
        rv = ov.rv_annual(closes, 3600 * 250, 168)
        self.assertGreater(rv, 50)
        del closes[3600 * 200]
        self.assertIsNone(ov.rv_annual(closes, 3600 * 250, 168))
        self.assertAlmostEqual(ov.ret_24h({0: 100.0, 86400: 103.0}, 86400), 0.03)

    def test_percentile(self):
        self.assertAlmostEqual(ov.percentile([1, 2, 3, 4, 5], 0.6), 3.4)

    def test_add_features_only_past(self):
        days = [{"date": ov.add_days("2025-01-01", i), "dvol_am": 50.0 + i, "skew": 0.01 * (i % 5)} for i in range(100)]
        ov.add_features(days)
        self.assertIsNone(days[10]["dvol_pct_ok"])
        self.assertTrue(days[99]["dvol_pct_ok"])               # rising DVOL is above the 60th percentile of the past
        days[99]["dvol_am"] = 0.0
        ov.add_features(days)
        self.assertFalse(days[99]["dvol_pct_ok"])
        self.assertIsNotNone(days[50]["skew_ok"])

    def test_filters(self):
        day = {"date": "2025-01-11", "dvol_am": 60.0, "rv168": 40.0, "ret24": -0.03, "dvol_pm": 50.0, "rv72": 50.0}
        self.assertEqual(ov.rule_filter("R1_bull_put_spread_vrp", day, "BTC"), (True, None))
        self.assertEqual(ov.rule_filter("R8_evening_condor_12h", day, "BTC"), (False, None))
        self.assertEqual(ov.rule_filter("R5_post_shock_condor", day, "BTC"), (True, None))
        self.assertEqual(ov.rule_filter("R5_post_shock_condor", day, "ETH"), (False, None))
        self.assertEqual(ov.rule_filter("R6_weekend_condor", day, "BTC"), (True, None))        # Saturday
        self.assertEqual(ov.rule_filter("R1_bull_put_spread_vrp", dict(day, rv168=None), "BTC")[1], "no_rv")

    def test_skew_from_prints(self):
        d0 = ov.day_ts("2025-01-10")
        t = (d0 + 7 * 3600 + 600) * 1000
        pr = []
        for i in range(4):
            pr.append({"timestamp": t + i, "instrument_name": "BTC-11JAN25-50000-P", "iv": 70.0, "index_price": 60000.0})
            pr.append({"timestamp": t + i, "instrument_name": "BTC-11JAN25-70000-C", "iv": 55.0, "index_price": 60000.0})
        self.assertAlmostEqual(ov.skew_from_prints(pr, "2025-01-10"), 15.0)
        self.assertIsNone(ov.skew_from_prints(pr[:4], "2025-01-10"))


def trade(name, direction, price, ts, tid, idx=60000.0, iv=60.0):
    return {"instrument_name": name, "direction": direction, "price": price, "timestamp": ts, "trade_id": tid,
            "index_price": idx, "iv": iv}


def instruments(created=0):
    out = []
    for k in range(50000, 70001, 1000):
        for typ, c in (("put", "P"), ("call", "C")):
            out.append({"name": f"BTC-11JAN25-{k}-{c}", "strike": float(k), "type": typ, "creation_ms": created, "period": "day"})
    return out


def hours_for(date, n_days=12, px=100.0):
    base = ov.day_ts(date) - 9 * 86400
    return {base + 3600 * i: (px, px, px, px * (1.001 if i % 2 else 1.0)) for i in range(24 * (n_days + 9))}


class BuildDay(unittest.TestCase):
    def prints(self):
        t = E * 1000 + 60000
        return [trade("BTC-11JAN25-58000-P", "sell", 0.001, t, 1), trade("BTC-11JAN25-57000-P", "buy", 0.0005, t + 1, 2),
                trade("BTC-11JAN25-62000-C", "sell", 0.001, t + 2, 3), trade("BTC-11JAN25-63000-C", "buy", 0.0005, t + 3, 4),
                trade("BTC-11JAN25-58000-P", "buy", 0.0009, E * 1000 - 5000, 5, idx=60100.0)]   # last print before entry

    def build(self, **kw):
        args = dict(asset="BTC", date=D, instruments=instruments(), prints_am=self.prints(), prints_pm=[], usdc_am=None,
                    usdc_pm=None, dvol={E - 300 - 3600: 50.0}, hours=hours_for(D), delivery=60000.0)
        args.update(kw)
        return ov.build_day_rows(**args)

    def test_ok_rows(self):
        rows = self.build()
        day, sides = rows[0], {(r["win"], r["k"], r["side"]): r for r in rows[1:]}
        self.assertEqual(day["dvol_am"], 50.0)
        r = sides[("am", 1.0, "put")]
        self.assertEqual((r["status"], r["short_k"], r["long_k"], r["index"], r["index_src"]), ("ok", 58000.0, 57000.0, 60100.0, "print"))
        self.assertEqual(sides[("am", 1.0, "call")]["status"], "ok")
        self.assertEqual(sides[("am", 1.3, "call")]["status"], "no_short_print")    # k=1.3 call strikes had no prints
        self.assertEqual(sides[("pm", 1.0, "put")]["status"], "no_dvol")
        self.assertEqual(day["period"], "day")

    def test_fill_window_and_direction(self):
        late = self.prints()
        late[0] = trade("BTC-11JAN25-58000-P", "sell", 0.001, (E + 3600) * 1000, 1)          # outside [E, E+60min)
        self.assertEqual({(r["side"], r["status"]) for r in self.build(prints_am=late)[1:] if r["win"] == "am" and r["k"] == 1.0},
                         {("put", "no_short_print"), ("call", "ok")})
        wrong = self.prints()
        wrong[1] = trade("BTC-11JAN25-57000-P", "sell", 0.0005, E * 1000 + 5000, 2)           # sell print cannot fill the long
        st = {(r["side"]): r["status"] for r in self.build(prints_am=wrong)[1:] if r["win"] == "am" and r["k"] == 1.0}
        self.assertEqual(st["put"], "no_long_print")

    def test_unlisted_strikes_and_creation(self):
        rows = self.build(instruments=instruments(created=(E + 1) * 1000))
        self.assertTrue(all(r["status"] == "no_expiry" for r in rows[1:] if r["win"] == "am"))

    def test_gap_day_is_dropped(self):
        rows = self.build(gaps=["trades"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gaps"], ["trades"])

    def test_index_fallback_to_binance(self):
        pr = [p for p in self.prints() if p["trade_id"] != 5]
        r = [x for x in self.build(prints_am=pr)[1:] if x["side"] == "put" and x["k"] == 1.0 and x["win"] == "am"][0]
        self.assertEqual(r["index_src"], "binance_1h")

    def test_block_combo_liquidation_prints_are_not_fills(self):
        pr = self.prints()
        pr[0] = dict(pr[0], block_trade_id="b1")                              # negotiated block price on the short put
        st = {r["side"]: r["status"] for r in self.build(prints_am=pr)[1:] if r["win"] == "am" and r["k"] == 1.0}
        self.assertEqual(st["put"], "no_short_print")
        self.assertEqual(st["call"], "ok")
        for flag in ("combo_trade_id", "liquidation"):
            q = self.prints()
            q[2] = dict(q[2], **{flag: "x"})
            st = {r["side"]: r["status"] for r in self.build(prints_am=q)[1:] if r["win"] == "am" and r["k"] == 1.0}
            self.assertEqual(st["call"], "no_short_print")
        self.assertTrue(ov.tradable({"liquidation": None, "block_trade_id": None}))

    def test_usdc_legs_ignore_other_asset(self):
        usdc = [trade("ETH_USDC-11JAN25-58000-P", "sell", 55.0, E * 1000 + 1000, 9)]
        self.assertIsNone(ov.usdc_legs(usdc, D, 58000.0, 57000.0, "put", E, "BTC")["s"])
        self.assertEqual(io.usdc_only([{"instrument_name": "BTC_USDC-1-P"}, {"instrument_name": "SOL_USDC-1-P"}], "BTC"),
                         [{"instrument_name": "BTC_USDC-1-P"}])
        self.assertIsNone(io.usdc_only(None, "BTC"))

    def test_month_concentration(self):
        c = ov.month_concentration([{"date": "2025-01-02", "ror": 0.5}, {"date": "2025-02-02", "ror": -0.1},
                                    {"date": "2025-03-02", "ror": 0.1}])
        self.assertEqual(c["signal_months"], 3)
        self.assertAlmostEqual(c["positive_month_share"], 2 / 3)
        self.assertAlmostEqual(c["mean_ror_without_best_month"], 0.0)

    def test_usdc_legs(self):
        usdc = [trade("BTC_USDC-11JAN25-58000-P", "sell", 55.0, E * 1000 + 1000, 9), trade("BTC_USDC-11JAN25-57000-P", "buy", 28.0, E * 1000 + 2000, 10)]
        r = [x for x in self.build(usdc_am=usdc)[1:] if x["side"] == "put" and x["k"] == 1.0 and x["win"] == "am"][0]
        self.assertEqual((r["usdc"]["s"], r["usdc"]["l"]), (55.0, 28.0))
        rep = ov.usdc_report({("BTC", D, "am", 1.0, "put"): r})
        self.assertEqual(rep["by_win_k"]["am_k1.0_put"]["share_both_legs_usdc"], 1.0)
        self.assertEqual(rep["ratio_samples"], 2)


MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


class Summarize(unittest.TestCase):
    def rows(self, delivery=60000.0, sell=0.001, buy=0.0005):
        out = []
        hours = {ov.day_ts("2024-12-20") + 3600 * j: (100, 101, 99, 100.0 * (1.001 if j % 2 else 1.0)) for j in range(24 * 80)}
        for i in range(40):
            d = ov.add_days("2025-01-01", i)
            e = ov.entry_times(d, "am")[0]
            nxt = ov.add_days(d, 1)
            ds = f"{int(nxt[8:])}{MON[int(nxt[5:7]) - 1]}{nxt[2:4]}"
            pr = [trade(f"BTC-{ds}-50000-P", "buy", 0.0001, e * 1000 - 1000, f"{d}-pre")]      # last print before entry: index 60000
            ins, tid = [], 0
            for k in range(50000, 70001, 1000):
                for c in "PC":
                    ins.append({"name": f"BTC-{ds}-{k}-{c}", "strike": float(k), "type": "put" if c == "P" else "call",
                                "creation_ms": 0, "period": "day"})
                    for dr, px in (("sell", sell), ("buy", buy)):
                        tid += 1
                        pr.append(trade(f"BTC-{ds}-{k}-{c}", dr, px, e * 1000 + 60000 + tid, f"{d}-{tid}"))
            out += ov.build_day_rows("BTC", d, ins, pr, [], None, None, {e - 300 - 3600: 50.0}, hours, delivery)
        return out

    def test_end_to_end_shape(self):
        s = ov.summarize(self.rows())
        self.assertEqual(s["n_tests"], 8)
        t = s["tests"]["R3_iron_condor_vrp|BTC"]
        self.assertEqual(t["funnel"]["confirm"]["executable"], 40)
        self.assertGreater(t["splits"]["confirm"]["base"]["margin_A"]["trades"], 0)
        self.assertEqual(t["verdict"]["label"], "STOPPED")                     # tiny credits cannot reach 3x
        self.assertEqual(s["tests"]["R4_high_dvol_condor|BTC"]["funnel"]["confirm"]["filter_missing"], {"no_dvol_history": 40})
        self.assertEqual(s["passed"], [])
        self.assertTrue(s["data_ok"])
        self.assertIn("R6_weekend_condor|BTC", s["stopped_step0"])

    def test_losing_delivery_is_negative(self):
        s = ov.summarize(self.rows(delivery=50000.0))
        t = s["tests"]["R3_iron_condor_vrp|BTC"]["splits"]["confirm"]["base"]["margin_A"]
        self.assertLess(t["mean_ror"], 0)
        self.assertLess(t["ending_equity"], 147.0)

    def test_scored_path_when_ceiling_allows(self):
        from unittest import mock
        fake = {"all_win": {"share_3x": 1.0}, "oracle": {"share_3x": 1.0}}
        with mock.patch.object(ov, "ceiling", return_value=fake):
            s = ov.summarize(self.rows(sell=0.004))
        t = s["tests"]["R3_iron_condor_vrp|BTC"]
        c = t["splits"]["confirm"]
        self.assertTrue(c["step0_pass"])
        self.assertEqual(c["high"]["margin_A"]["trades"], 40)
        self.assertEqual(c["base"]["draw_share"], 1.0)                   # signal = whole pool, so no draw can beat it
        self.assertEqual(t["verdict"]["label"], "FAIL")
        self.assertEqual(c["high"]["margin_B"]["sizing_attrition"].get("margin", 0), 40 - c["high"]["margin_B"]["trades"])

    def test_verdict_logic(self):
        def res(step0=True, db=0.001, dh=0.001, tpw=4.0, ror=0.1, fa=1, fb=1):
            m = {"trades_per_week": tpw, "mean_ror": ror}
            return {"splits": {"confirm": {"step0_pass": step0, "base": {"draw_share": db},
                                           "high": {"draw_share": dh, "margin_A": dict(m, funded_3x_months=fa),
                                                    "margin_B": dict(m, funded_3x_months=fb)}}}}
        self.assertEqual(ov.verdict(res())["label"], "PASS")
        self.assertEqual(ov.verdict(res(fb=0))["label"], "CONDITIONAL")
        self.assertEqual(ov.verdict(res(fa=0, fb=0))["label"], "FAIL")
        self.assertEqual(ov.verdict(res(dh=0.01))["label"], "FAIL")
        self.assertEqual(ov.verdict(res(tpw=2.9))["label"], "FAIL")
        self.assertEqual(ov.verdict(res(ror=-0.01))["label"], "FAIL")
        self.assertEqual(ov.verdict(res(step0=False))["label"], "STOPPED")
        self.assertAlmostEqual(ov.BAR, 0.003125)


class Fetching(unittest.TestCase):
    def test_trade_paging_dedupes_and_never_stalls(self):
        pages = [{"trades": [{"trade_id": "a", "timestamp": 1}, {"trade_id": "b", "timestamp": 2}], "has_more": True},
                 {"trades": [{"trade_id": "b", "timestamp": 2}, {"trade_id": "c", "timestamp": 2}], "has_more": True},
                 {"trades": [{"trade_id": "c", "timestamp": 2}], "has_more": True},
                 {"trades": [{"trade_id": "d", "timestamp": 3}], "has_more": False}]
        urls = []

        def get(url, **kw):
            urls.append(url)
            return pages[len(urls) - 1]
        out = io.fetch_trades("BTC", 0, 10, get)
        self.assertEqual([t["trade_id"] for t in out], ["a", "b", "c", "d"])
        self.assertIn("start_timestamp=3", urls[3])                        # no new id on page 3 -> moved 1 ms past the edge

    def test_trade_failure_is_a_gap(self):
        def get(url, **kw):
            raise RuntimeError("boom")
        self.assertIsNone(io.fetch_trades("BTC", 0, 10, get))

    def test_delivery_and_dvol_paging(self):
        pages = {0: {"data": [{"date": "2026-10-02", "delivery_price": 1.0}] * 1, "records_total": 150},
                 100: {"data": [{"date": "2021-03-25", "delivery_price": 2.0}], "records_total": 150}}
        d = io.fetch_delivery("BTC", "2021-03-24", lambda url, **kw: pages[int(url.split("offset=")[1].split("&")[0])])
        self.assertEqual(d, {"2026-10-02": 1.0, "2021-03-25": 2.0})
        calls = []

        def get(url, **kw):
            calls.append(url)
            if len(calls) == 1:                                              # first page of window 1 holds the NEWEST rows
                return {"data": [[1500000, 1, 2, 0, 56.0]], "continuation": 1000000}
            return {"data": [[1000000, 1, 2, 0, 55.0]], "continuation": None}
        v = io.fetch_dvol("BTC", 0, 30 * 86400, get)
        self.assertEqual((v[1000], v[1500]), (55.0, 56.0))
        self.assertEqual(len(calls), 3)                                      # window 1 + its continuation + window 2
        self.assertIn("start_timestamp=0&", calls[1])                        # continuation moves the END, never the start
        self.assertIn("end_timestamp=1000000&", calls[1])

    def test_shard_unit_with_fake_api(self):
        d = "2021-03-31"
        e = ov.entry_times(d, "am")[0]
        exp = ov.expiry_ts(d)
        ins = [{"instrument_name": f"BTC-1APR21-{k}-{c}", "strike": k, "option_type": t, "creation_timestamp": 0,
                "settlement_period": "day", "expiration_timestamp": exp * 1000}
               for k in range(50000, 70001, 1000) for c, t in (("P", "put"), ("C", "call"))]

        def get(url, **kw):
            if "get_instruments" in url:
                return ins
            if "get_delivery_prices" in url:
                return {"data": [{"date": "2021-04-01", "delivery_price": 60000.0}], "records_total": 1}
            if "get_volatility_index_data" in url:
                return {"data": [[(e - 300 - 3600) * 1000, 50, 50, 50, 50.0]], "continuation": None}
            return {"trades": [], "has_more": False}
        rows, gaps = io.shard_unit("BTC", "2021-03", get, lambda a, s, t: hours_for(d, px=60000.0))
        self.assertEqual(gaps["trades"], 0)
        self.assertEqual(sum(1 for r in rows if r["kind"] == "day"), 8)        # 2021-03-24 .. 2021-03-31
        r31 = [r for r in rows if r["date"] == d and r["kind"] == "side" and r["win"] == "am" and r["k"] == 1.0 and r["side"] == "put"][0]
        self.assertEqual(r31["status"], "no_short_print")                        # no prints in the fake tape
        self.assertEqual(r31["delivery"], 60000.0)

    def test_registration_and_universe(self):
        from research.studies import run
        self.assertIsNotNone(run.sharded_study("opt_vrp"))
        u = run.symbols_opt_vrp()
        self.assertEqual(len(u), 136)
        self.assertEqual(u[0], "BTC:2021-03")
        self.assertEqual(len(ov.month_days("2021-03")), 8)
        self.assertEqual(ov.month_days("2026-10")[-1], "2026-10-31")
        self.assertEqual(run.rows_opt_vrp.__name__, "rows_opt_vrp")


if __name__ == "__main__":
    unittest.main()
