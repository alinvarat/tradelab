import hashlib
import unittest
from pathlib import Path

from core import notice_fwd as nf

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "research" / "studies" / "protocol_notice_fwd_20261126.md"
T0 = 1_800_000_000


def row(src, key, title, t_pub, lat, res="s"):
    return {"source": src, "key": key, "title": title, "t_pub": t_pub, "res": res, "t_seen": None if lat is None else t_pub + lat}


def joined(*rows):
    return {(r["source"], r["key"]): r for r in rows}


class Lock(unittest.TestCase):
    def test_protocol_unchanged(self):
        self.assertEqual(hashlib.sha256(PROTO.read_bytes()).hexdigest(), PROTO.with_suffix(".sha256").read_text().strip(),
                         "protocol is locked; write a new dated protocol instead")

    def test_constants_match_protocol(self):
        t = PROTO.read_text()
        self.assertEqual((nf.ENTRY_DELAY_S, nf.MAX_LAT_S, nf.SLOW_MIN_ITEMS, nf.MIN_N, nf.PRIMARY_HOLD, nf.HOLDS), (5, 25, 20, 30, 3600, (300, 3600, 14400)))
        self.assertAlmostEqual(nf.SLIP + nf.REST_COST, 0.004)
        for s in ("Minimum n = 30", "2027-02-06", "0.15% against", "0.25% more", "alpha 0.05", "clip 10%", "mean gross < 0.8%", "cluster-level x < 0.2"):
            self.assertIn(s, t)
        self.assertEqual(nf.DEADLINE, "2027-02-06")


class Classify(unittest.TestCase):
    def test_classes(self):
        c = nf.classify
        self.assertEqual(c("eqn_rest", "Binance Will Extend the Monitoring Tag to Include AAA, BBB and Remove CCC on 2026-12-01")["cls"], "monitor")
        self.assertEqual(c("binance_news", "Binance Futures Will Delist DDDUSDT Perpetual Contract on 2026-12-01")["coins"], ["DDD"])
        self.assertEqual(c("okx_announcements", "OKX to delist EEE-USDT perpetual futures on Dec 3")["coins"], ["EEE"])
        x = c("binance_listings", "Binance Will List Foo Token (FOO) with Seed Tag Applied")
        self.assertEqual((x["cls"], x["side"], x["coins"]), ("listing", 1, ["FOO"]))
        self.assertEqual(c("eqn_rest", "업비트 싸이식(CYS) 원화 마켓 추가")["cls"], "kr_listing")
        self.assertEqual(c("eqn_rest", "싸이식(CYS) 거래지원 종료 안내")["cls"], "kr_delist")

    def test_not_notices(self):
        for t in ("Binance Perp Monitor: BULLAUSDT (BULLA) +6.2% in the past 10 seconds", "Bybit Alpha to Delist 1 Token(s) on Nov 26, 2026",
                  "OKX P2P Merchant Deposit Requirements in Pakistan", "TradFi stock listing: ANT CFDs now live on Bybit TradFi!",
                  "Binance Will Update Margin tiers for FOO", "Spot Trading Tournament Season 12", "", None):
            self.assertIsNone(nf.classify("eqn_rest", t), t)
        self.assertIsNone(nf.classify("eqn_rest", "Bybit to Delist 1 Token(s) on Nov 30, 2026"))   # no coin named


class Clusters(unittest.TestCase):
    TITLE = "Binance Futures Will Delist DDDUSDT Perpetual Contract"

    def test_fast_eqn_wins_over_slow_direct_and_gap_reported(self):
        j = joined(row("binance_delist", "b1", self.TITLE, T0 - 3, 80), row("eqn_rest", "e1", self.TITLE, T0 + 20, 4))
        (c,) = nf.clusters(j)
        self.assertTrue(c["eligible"])
        self.assertEqual((c["source"], c["first_any"], c["t_seen"]), ("eqn_rest", "eqn_rest", T0 + 24))
        self.assertAlmostEqual(c["pub_gap_s"], 23)
        self.assertEqual(c["sources"], ["binance_delist", "eqn_rest"])

    def test_slow_minute_resolution_and_killed_sources_are_not_eligible(self):
        self.assertFalse(nf.clusters(joined(row("binance_delist", "b1", self.TITLE, T0, 60)))[0]["eligible"])
        self.assertFalse(nf.clusters(joined(row("eqn_rest", "e1", self.TITLE, T0, 3, res="m")))[0]["eligible"])
        self.assertFalse(nf.clusters(joined(row("eqn_rest", "e1", self.TITLE, T0, 3)), slow=["eqn_rest"])[0]["eligible"])

    def test_seven_day_dedupe(self):
        j = joined(row("eqn_rest", "e1", self.TITLE, T0, 3), row("eqn_rest", "e2", self.TITLE, T0 + 86400, 3), row("eqn_rest", "e3", self.TITLE, T0 + 8 * 86400, 3))
        self.assertEqual(len(nf.clusters(j)), 2)


class Latency(unittest.TestCase):
    def test_table_and_sticky_slow(self):
        rows = [row("okx_announcements", f"k{i}", "OKX news", T0, 90 + i) for i in range(20)] + [row("eqn_rest", f"e{i}", "x", T0, 4) for i in range(25)]
        tb = nf.latency_table(joined(*rows))
        self.assertTrue(tb["okx_announcements"]["slow"])
        self.assertFalse(tb["eqn_rest"]["slow"])
        self.assertEqual(tb["eqn_rest"]["median_lat_s"], 4)
        self.assertEqual(nf.slow_sources({"eqn_rest": {"slow": False}}, ["okx_announcements"]), ["okx_announcements"])
        small = nf.latency_table(joined(row("okx_announcements", "k", "x", T0, 90)))
        self.assertFalse(small["okx_announcements"]["slow"])            # fewer than 20 items: no kill yet


class Fills(unittest.TestCase):
    def pages(self, trades):
        def get_page(inst, after):
            older = sorted((t for t in trades if t["ts"] < after), key=lambda t: -t["ts"])
            return older[:2]
        return get_page

    def test_first_print_at_or_after(self):
        tr = [{"ts": (T0 + d) * 1000 + 100, "px": 100 + d} for d in range(0, 10)]
        f = nf.tape_fill(self.pages(tr), "X", T0 + 5)
        self.assertEqual((f["px"], f["src"]), (105, "tape"))

    def test_none_when_walk_never_crosses_or_no_print(self):
        tr = [{"ts": (T0 + 6) * 1000 + i, "px": 1.0} for i in range(500)]   # a dense burst: 6 pages of 2 never reach the entry second
        self.assertIsNone(nf.tape_fill(self.pages(tr), "X", T0 + 5))
        self.assertIsNone(nf.tape_fill(lambda i, a: [], "X", T0))

    def test_bar_fallback(self):
        b = (T0 // 60 + 1) * 60
        self.assertEqual(nf.bar_fill({b: 7.0}, b - 30)["px"], 7.0)
        self.assertIsNone(nf.bar_fill({b: 7.0}, b + 1))


class Arithmetic(unittest.TestCase):
    def test_net_costs(self):
        g, n = nf.trade_net(1, 100, 101, 3600)
        self.assertAlmostEqual(g, 0.01)
        self.assertAlmostEqual(n, 101 / (100 * 1.0015) - 1 - 0.0025 - 0.0003)
        g, n = nf.trade_net(-1, 100, 99, 300)
        self.assertAlmostEqual(n, -(99 / (100 * 0.9985) - 1) - 0.0025)
        self.assertLess(nf.trade_net(1, 100, 101, 3600, mult=2)[1], n + 1)
        self.assertLess(nf.trade_net(1, 100, 101, 3600, mult=2)[1], nf.trade_net(1, 100, 101, 3600)[1])

    def test_control_side_is_fixed(self):
        self.assertEqual(nf.control_side("a", 3600), nf.control_side("a", 3600))


class Walk(unittest.TestCase):
    """One full entry and exit cycle with injected prices."""
    def test_full_cycle_and_verdict(self):
        j = joined(row("eqn_rest", "e1", "Binance Futures Will Delist DDDUSDT Perpetual Contract", T0, 3),
                   row("eqn_rest", "e2", "OKX to list Foo Token (FOO) on Dec 1", T0, 3),
                   row("eqn_rest", "e3", "Binance Will Extend the Monitoring Tag to Include QQQ on 2026-12-01", T0, 3),
                   row("binance_listings", "b9", "Binance Will List Bar (BAR)", T0, 90))
        cls = nf.clusters(j)
        self.assertEqual(len(cls), 4)
        t_entry = T0 + 3 + 5

        def tape(inst, t):
            px = 100.0 if t < t_entry + 10 else 99.0 if t > t_entry + 5000 else 99.5
            return {"px": px, "ts": t, "src": "tape"}
        state = {}
        perps = {"DDD-USDT-SWAP", "FOO-USDT-SWAP", "BAR-USDT-SWAP"}      # QQQ has none
        # too early: nothing is entered
        state, rows, notices = nf.step(state, cls, t_entry + 10, perps, tape, lambda i, t: {})
        self.assertEqual(rows, [])
        self.assertEqual(sorted(state["seen"].values()), ["no_perp", "too_slow"])   # only the two that need no price
        now = t_entry + 4 * 3600 + 3600
        state, rows, notices = nf.step(state, cls, t_entry + 200, perps, tape, lambda i, t: {})
        self.assertEqual(sorted(n["status"] for n in notices), ["pending", "pending"])
        self.assertEqual(rows, [])                                          # 5 min hold not due yet (300 + 120)
        state, rows, _ = nf.step(state, cls, now, perps, tape, lambda i, t: {})
        self.assertEqual(len(rows), 6)                                      # 2 pending clusters x 3 holds
        self.assertEqual(state["pending"], {})
        self.assertEqual(sorted(set(state["seen"].values())), ["no_perp", "settled", "too_slow"])
        short = [r for r in rows if r["coin"] == "DDD" and r["hold"] == 3600][0]
        self.assertEqual((short["entry_px"], short["exit_px"]), (100.0, 99.5))
        self.assertGreater(short["gross"], 0)
        self.assertIsNotNone(short["nn_net"])
        led = nf.Ledger()
        for r in rows:
            led.add(r)
        self.assertEqual(led.ep.n, 2)
        v = nf.verdict(rows, led.ep.view(), "2026-12-01")
        self.assertEqual((v["n"], v["verdict"]), (2, "underpowered"))
        self.assertEqual(nf.verdict([], led.ep.view(), "2027-03-01")["verdict"], "not_found")

    def test_bar_entry_is_not_evidence_and_failed_entry_is_dropped(self):
        cls = nf.clusters(joined(row("eqn_rest", "e1", "Binance Futures Will Delist DDDUSDT Perpetual Contract", T0, 3)))
        b = (T0 // 60 + 1) * 60
        state, _, _ = nf.step({}, cls, T0 + 300, {"DDD-USDT-SWAP"}, lambda i, t: None, lambda i, t: {b: 1.0})
        self.assertEqual(state["pending"][cls[0]["id"]]["entry"]["src"], "bar")
        none = {}
        for k in range(3):
            none, _, _ = nf.step(none, cls, T0 + 300 + k, {"DDD-USDT-SWAP"}, lambda i, t: None, lambda i, t: {})
        self.assertEqual(none["seen"][cls[0]["id"]], "no_entry")

    def test_kill_reasons_at_min_n(self):
        rows = [{"hold": 3600, "entry_src": "tape", "net": -0.01 - i * 1e-4, "gross": 0.002, "net_2x": -0.02, "ctrl_net": -0.02, "nn_net": -0.02,
                 "t_entry": T0 + i * 86400} for i in range(30)]
        v = nf.verdict(rows, {"decision": "continue"}, "2026-12-30")
        self.assertEqual(v["verdict"], "kill")
        self.assertIn("mean net <= 0", v["reasons"])
        self.assertIn("mean gross < 0.8%", v["reasons"])
        good = [dict(r, net=0.03 + (i % 3) * 0.01, gross=0.04, net_2x=0.02) for i, r in enumerate(rows)]
        self.assertEqual(nf.verdict(good, {"decision": "continue"}, "2026-12-30")["verdict"], "continue")
        self.assertEqual(nf.verdict(good, {"decision": "edge"}, "2026-12-30")["verdict"], "found")
        self.assertEqual(nf.verdict(good[:10], {"decision": "edge"}, "2026-12-30")["verdict"], "underpowered")


class Wiring(unittest.TestCase):
    def test_keeper_and_workflow(self):
        k = (ROOT / ".github" / "workflows" / "keeper.yml").read_text()
        self.assertIn("notice_fwd.yml", k)
        self.assertIn("11|41", k)
        w = (ROOT / ".github" / "workflows" / "notice_fwd.yml").read_text()
        for s in ("data/notice-fwd", "data/news-ingest", "tradelab-notice-fwd-state", "mode == 'counts'", "mode == 'forward'"):
            self.assertIn(s, w)
        self.assertNotIn("\t", w)


if __name__ == "__main__":
    unittest.main()
