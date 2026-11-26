"""Offline tests for research/news_train round 2 (1-hour labels, GDELT corpus, calibration, selection, forward trigger). Synthetic data only."""
import hashlib
import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from research.news_train import logic as L
from research.news_train import logic_r2 as R

ROOT = Path(__file__).resolve().parents[1] / "research" / "news_train"
P = R.load_params()


def ts(s):  # 'YYYY-MM-DD HH:MM' UTC
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())


def session(day, o0=100.0, step=1.0):
    """Regular session of a winter day (EST): bars start 14:30 UTC, hourly, the last bar 20:30 UTC. Open o0 + step*i, close = next open."""
    out = []
    for i, hm in enumerate(["14:30", "15:30", "16:30", "17:30", "18:30", "19:30", "20:30"]):
        o = o0 + step * i
        out.append({"t": ts(f"{day} {hm}"), "o": o, "h": o + 1, "l": o - 1, "c": o + step})
    return out


def week():
    bars = []
    for n, d in enumerate(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09", "2026-01-12", "2026-01-13"]):
        bars += session(d, 100 + 10 * n)
    return bars


class Lock(unittest.TestCase):
    def test_addendum_and_params_hash(self):
        add = ROOT / "protocol_r2_20261126.md"
        self.assertEqual(hashlib.sha256(add.read_bytes()).hexdigest(), add.with_suffix(".sha256").read_text().strip(),
                         "protocol_r2 is locked; write a new dated addendum")
        self.assertIn(hashlib.sha256((ROOT / "params_r2.json").read_bytes()).hexdigest(), add.read_text())

    def test_round1_files_untouched(self):
        proto = ROOT / "protocol.md"
        self.assertEqual(hashlib.sha256(proto.read_bytes()).hexdigest(), (ROOT / "protocol.sha256").read_text().strip())

    def test_registry(self):
        reg = R.versions_registry()["versions"]
        self.assertLessEqual(len(reg), P["max_versions"])
        for v in reg:
            R.check_version(v)
        with self.assertRaises(ValueError):
            R.check_version(dict(reg[0], sha256="0" * 64))

    def test_costs_and_model_match_round1(self):
        v2 = L.load_params()
        for k in ("cost", "holds", "seed", "model", "bootstrap"):
            if k != "seed":
                self.assertEqual(v2[k], P[k])
        self.assertEqual(P["model"], "claude-haiku-5-5")


class Splits(unittest.TestCase):
    def test_split(self):
        d = L.day_ts
        self.assertIsNone(R.split_r2(d("2025-11-30"), P))
        self.assertEqual(R.split_r2(d("2025-12-01"), P), "train")
        self.assertEqual(R.split_r2(d("2026-04-01"), P), "validation")
        self.assertEqual(R.split_r2(d("2026-07-10"), P), "buffer")
        self.assertEqual(R.split_r2(d("2026-08-01"), P), "sealed_hist")
        self.assertEqual(R.split_r2(d("2026-11-26") + 86399, P), "sealed_hist")
        self.assertEqual(R.split_r2(d("2026-11-27"), P), "fwd")

    def test_dev_guard(self):
        with self.assertRaises(L.SealError):
            R.assert_dev(L.day_ts("2026-07-01"), P)

    def test_sec_time_is_utc(self):
        self.assertEqual(R.utc_ts("2026-11-25T22:26:14.000Z"), 1795645574)    # Atom feed time of the same accession
        self.assertEqual(R.fix_ts(__import__("core.factory_us_pit", fromlist=["x"]).accept_ts("2026-11-25T22:26:14.000Z")), 1795645574)


class StockLabel(unittest.TestCase):
    def test_in_session_rounds_to_next_bar(self):
        bars = week()
        t_pub = ts("2026-01-07 16:40")                     # 11:40 ET, inside the 16:30 UTC bar
        lab, why = R.stock_label_1h(bars, t_pub, 93, P)
        self.assertEqual(why, "ok")
        self.assertTrue(lab["in_session"])
        self.assertEqual(lab["entry_ts"], ts("2026-01-07 17:30"))
        self.assertEqual(lab["p_in"], 123.0)               # 3rd day (n=2): 120 + step 3? bar i=3 opens at 120+3
        self.assertAlmostEqual(lab["gross"]["1h"], 124.0 / 123.0 - 1)
        self.assertAlmostEqual(lab["gross"]["eod"], 127.0 / 123.0 - 1)
        self.assertAlmostEqual(lab["pre_move"], 123.0 / 122.0 - 1)
        self.assertEqual(lab["delay_s"], 3000)

    def test_after_close_enters_next_open_and_last_bar_has_no_1h(self):
        bars = week()
        lab, _ = R.stock_label_1h(bars, ts("2026-01-07 21:30"), 93, P)
        self.assertFalse(lab["in_session"])
        self.assertEqual(lab["entry_ts"], ts("2026-01-08 14:30"))
        lab2, _ = R.stock_label_1h(bars, ts("2026-01-07 20:40"), 93, P)    # after the 20:30 bar started: next session
        self.assertEqual(lab2["entry_ts"], ts("2026-01-08 14:30"))
        lab3, _ = R.stock_label_1h(bars, ts("2026-01-07 20:20"), 93, P)    # entry = the 20:30 half-hour bar
        self.assertEqual(lab3["entry_ts"], ts("2026-01-07 20:30"))
        self.assertIsNone(lab3["gross"]["1h"])
        self.assertIsNotNone(lab3["gross"]["eod"])

    def test_no_lookahead_in_pre_fields(self):
        bars = week()
        lab, _ = R.stock_label_1h(bars, ts("2026-01-08 15:00"), 93, P)
        # nothing at or after the entry bar's close may enter the pre-entry fields
        b2 = [dict(b) for b in bars]
        for b in b2:
            if b["t"] >= lab["entry_ts"]:
                b["c"] *= 3
                b["h"] *= 3
        lab2, _ = R.stock_label_1h(b2, ts("2026-01-08 15:00"), 93, P)
        for k in ("pre_move", "day_move", "runup5", "p_in"):
            self.assertEqual(lab[k], lab2[k])

    def test_missing_bars(self):
        self.assertEqual(R.stock_label_1h(week(), ts("2026-02-20 15:00"), 93, P)[1], "no_entry_bar")
        self.assertEqual(R.stock_label_1h(week()[3:], ts("2026-01-05 14:00"), 93, P)[1], "no_prior_bar")


class Gdelt(unittest.TestCase):
    def line(self, title, domain="coindesk.com", themes="ECON_BITCOIN,1"):
        f = [""] * 27
        f[1], f[3], f[4], f[7] = "20260301120000", domain, "https://x/" + title[:5], themes
        f[26] = f"<PAGE_AUTHORS>a</PAGE_AUTHORS><PAGE_TITLE>{title}</PAGE_TITLE>"
        return "\t".join(f)

    def test_parse_and_coin(self):
        r = R.parse_gkg_line(self.line("Bitcoin ETF sees record inflows"))
        self.assertEqual(R.coin_of(r["title"], r["themes"], P), "BTC")
        self.assertIsNone(R.coin_of("Bitcoin and Ethereum rally together", "", P))          # two coins
        self.assertEqual(R.coin_of("Bitcoin Cash upgrade goes live, crypto miners say", "", P), "BCH")
        self.assertIsNone(R.coin_of("Ripple effect hits the housing market", "WB_X", P))     # no crypto context
        self.assertIsNone(R.parse_gkg_line("a\tb"))

    def test_stamps(self):
        self.assertEqual(len(R.gkg_stamps("2026-03-01", 1)), 96)
        self.assertEqual(R.gkg_stamps("2026-03-01", 4)[1], "20260301010000")

    def test_spam(self):
        self.assertTrue(R.is_spam("X", "tickerreport.com", P))
        self.assertTrue(R.is_spam("Acme LLC Acquires 5,000 Shares of Grayscale Bitcoin Trust", "x.com", P))
        self.assertFalse(R.is_spam("Bitcoin falls below key level", "coindesk.com", P))

    def test_dedupe_and_cap(self):
        t = 1_700_000_000
        rows = [{"t": t, "coin": "BTC", "title": "Bitcoin jumps as ETF inflows rise - CoinDesk", "domain": "a", "url": "1"},
                {"t": t + 900, "coin": "BTC", "title": "Bitcoin jumps as ETF inflows rise | Decrypt", "domain": "b", "url": "2"},
                {"t": t + 900, "coin": "BTC", "title": "Bitcoin jumps as ETF inflows rise sharply", "domain": "c", "url": "3"},
                {"t": t + 99999, "coin": "BTC", "title": "Bitcoin jumps as ETF inflows rise - CoinDesk", "domain": "a", "url": "4"},
                {"t": t, "coin": "ETH", "title": "Bitcoin jumps as ETF inflows rise - CoinDesk", "domain": "a", "url": "5"}]
        out = R.dedupe_rows(rows, P)
        self.assertEqual(sorted((r["coin"], r["t"]) for r in out), [("BTC", t), ("BTC", t + 99999), ("ETH", t)])
        many = [{"t": t + i, "coin": "BTC", "title": f"w{i} " * 5, "domain": "a", "url": str(i)} for i in range(50)]
        self.assertEqual(len(R.cap_per_coin_day(many, P)), P["gdelt"]["cap_per_coin_day"])

    def test_redaction(self):
        s = R.redact_title("Bitcoin (BTC) hits record on March 3, 2026", "BTC", P)
        self.assertNotIn("itcoin", s)
        self.assertNotIn("2026", s)


class Replies(unittest.TestCase):
    def test_parse(self):
        ok = R.parse_reply2('{"d":{"5m":"none","1h":"short","1d":"long"},"exp":{"5m":0.1,"1h":-1.2,"1d":2},"flow":"forced_sell","conf":70,"why":"x"}', "crypto")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["exp"]["1h"], -1.2)
        self.assertFalse(R.parse_reply2('{"d":{"1h":"short"}}', "crypto")["ok"])
        self.assertFalse(R.parse_reply2("nope", "stock")["ok"])
        self.assertTrue(R.parse_reply2('{"d":{"1h":"none","eod":"none"},"conf":1}', "stock")["ok"])

    def test_effective_requires_agreeing_sign_and_size(self):
        dec = {"ok": True, "d": {"1h": "short", "eod": "long"}, "exp": {"1h": -1.0, "eod": -2.0}}
        eff = R.effective(dec, {"1h": 0.5, "eod": 0.5}, True)
        self.assertEqual(eff["d"], {"1h": "short", "eod": "none"})                     # eod: direction disagrees with expected sign
        self.assertEqual(R.effective(dec, {"1h": 1.5, "eod": 0.5}, True)["d"]["1h"], "none")
        self.assertEqual(R.effective(dec, {"1h": None}, True)["d"]["1h"], "none")
        self.assertEqual(R.effective(dec, {}, False), dec)

    def test_fit_theta_uses_trade_floor(self):
        rows, decs = [], {}
        for i in range(100):
            g = -0.03 if i % 2 else 0.03
            rows.append({"key": str(i), "market": "stock", "labels": {R.LAB: {"gross": {"1h": g}}}})
            decs[str(i)] = {"ok": True, "d": {"1h": "short" if g < 0 else "long", "eod": "none"}, "exp": {"1h": -2 if g < 0 else 2, "eod": 0}}
        self.assertEqual(R.fit_theta(rows, decs, "stock", "1h", P), 0)                # perfect, trades everything
        self.assertIsNone(R.fit_theta(rows[:10], decs, "stock", "1h", P))             # fewer than the floor: never trade


class Selection(unittest.TestCase):
    def test_trade_floor_and_ties(self):
        cells = {"w0": {"stock": {"n_traded": 100, "score_per_offered": -0.01}, "crypto": {"n_traded": 500, "score_per_offered": 0.5}},
                 "w1": {"stock": {"n_traded": 1, "score_per_offered": 0.5}, "crypto": {"n_traded": 500, "score_per_offered": 0.5}},
                 "w2": {"stock": {"n_traded": 40, "score_per_offered": -0.02}, "crypto": {"n_traded": 20, "score_per_offered": 9}}}
        self.assertEqual(R.select_lock(cells, P), {"stock": "w0", "crypto": "w0"})
        self.assertEqual(R.select_lock({"w1": cells["w1"]}, P), {"stock": None, "crypto": "w1"})


class ForwardTrigger(unittest.TestCase):
    def test_counts_decisions_only(self):
        bars = {"A": week()}
        ver = {"calib": False}
        items = [{"key": f"k{i}", "sym": "A", "t_pub": ts("2026-01-05 15:00")} for i in range(3)] + \
                [{"key": "late", "sym": "A", "t_pub": ts("2026-01-13 15:00")}]
        decs = {"k0": {"ok": True, "d": {"1h": "long", "eod": "none"}}, "k1": {"ok": True, "d": {"1h": "none", "eod": "none"}},
                "k2": {"ok": False}, "late": {"ok": True, "d": {"1h": "long", "eod": "none"}}}
        now = ts("2026-01-13 15:30")                       # the last item's session has not closed yet
        r = R.fwd_trigger(items, decs, bars, now, P, ver, None)
        self.assertEqual((r["settled"], r["traded"], r["fire"]), (2, 1, False))
        P2 = json.loads(json.dumps(P))
        P2["done"]["min_traded"] = 1
        self.assertTrue(R.fwd_trigger(items, decs, bars, now, P2, ver, None)["fire"])


class Runner(unittest.TestCase):
    def test_write_once_guards_and_no_other_models(self):
        src = (ROOT / "run_r2.py").read_text()
        self.assertIn("refusing a second run", src)
        self.assertIn('os.path.exists(os.path.join(fd, "result.json"))', src)
        self.assertIn("assert_dev", src)
        self.assertNotIn("openrouter", src.lower())
        wf = (ROOT.parents[1] / ".github" / "workflows" / "news_train_r2.yml").read_text()
        self.assertNotIn("\t", wf)
        self.assertEqual(len(re.findall(r"^on:\n  workflow_dispatch:", wf, re.M)), 1)
        self.assertIn("schedule:", wf)
        self.assertEqual(sorted(re.findall(r"^  ([a-z_]+):\n    (?:if|needs|runs-on)", wf, re.M)),
                         sorted(["probe", "plan_build", "gdelt", "stock", "build_publish", "plan_eval", "eval", "eval_merge", "analyze", "sealed_crypto", "fwd"]))


if __name__ == "__main__":
    unittest.main()
