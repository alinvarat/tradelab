"""Offline tests of the L1f margin arm (core/margin_arm.py, margin_step in core/market_collect.py, core/margin_publish.py): pure maths and one
full entry and exit through listings_once with fake network readers. No network, no key."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from core import margin_arm as ma
from core import margin_publish as mp
from core import market_collect as mc

T0 = 1_800_000_000
ROOT = Path(__file__).resolve().parent.parent


def spec(coin_rates):
    return {"data": [{"assetName": c, "specs": [{"vipLevel": "0", "dailyInterestRate": str(r), "borrowLimit": str(lim)},
                                                  {"vipLevel": "1", "dailyInterestRate": "0.0001", "borrowLimit": "1"}]}
                     for c, (r, lim) in coin_rates.items()]}


class Pure(unittest.TestCase):
    def test_spec_snapshot_cost_and_limit(self):
        rows = ma.spec_rows(spec({"FOO": (0.0024, 1000)}))
        self.assertEqual(rows, {"FOO": {"daily_rate": 0.0024, "limit": 1000.0}})
        s = ma.snapshot(rows, "FOO", 5.0)
        self.assertTrue(s["borrowable"] and s["daily_rate"] == 0.0024)
        self.assertFalse(ma.snapshot(rows, "BAR", 5.0)["borrowable"])
        self.assertAlmostEqual(ma.borrow_cost([0.0024, 0.0048], 4 * 3600), 0.0036 * 5 / 24)     # ceil(4 h) + 1 = 5 hours charged
        self.assertAlmostEqual(ma.borrow_cost([0.0024, None], 4 * 3600 + 30), 0.0024 * 6 / 24)
        self.assertEqual(ma.borrow_cost([None, None], 3600), 0.0)
        self.assertTrue(ma.limit_ok(s, 29.4, 10.0))                    # 1000 coins * 10 >= 29.4
        self.assertFalse(ma.limit_ok(s, 29.4, 0.01))                   # 1000 * 0.01 < 29.4
        self.assertFalse(ma.limit_ok(ma.snapshot(rows, "BAR", 5.0), 1.0, 10.0))

    def test_has_perp(self):
        def get(url, *a, **k):
            if url.endswith("1000FOOUSDT"):
                return {"bidPrice": "1.0"}
            raise HTTPError(url, 400, "bad", {}, None)
        self.assertTrue(ma.has_perp(get, "FOO"))
        self.assertFalse(ma.has_perp(get, "ZZZ"))
        self.assertIsNone(ma.has_perp(mock.Mock(side_effect=OSError("down")), "FOO"))


def run_arm(coin, rates, quotes, steps, state_dir):
    """Drive listings_once at the times in `steps` with one delist notice; returns the pending/closed state of the margin arm."""
    notice = [{"kind": "delist", "venue": "binance", "symbol": coin, "ts": T0 - 30, "title": "Binance Will Delist"}]
    q = iter(quotes)
    spec_docs = iter(rates)

    def get(url, timeout=8, headers=None):
        if url == ma.SPEC_URL:
            return next(spec_docs)
        if url.startswith(ma.FAPI_BOOK):
            raise HTTPError(url, 400, "no such symbol", {}, None)
        if url.startswith(ma.SPOT_BOOK):
            bid, ask = next(q)
            return {"bidPrice": str(bid), "askPrice": str(ask)}
        raise AssertionError(url)

    with mock.patch.object(mc, "DIR", Path(state_dir)), mock.patch.object(mc, "MARGIN_ARM", True), \
            mock.patch.object(mc, "listing_notices", return_value=notice), mock.patch.object(mc, "get", side_effect=get), \
            mock.patch.object(mc, "quote", return_value=None), mock.patch.object(mc, "_btc_mid", return_value=100.0):
        for t in steps:
            mc.listings_once(T0 + t)
        return mc._l1b_load("l1fm")


class FullTrade(unittest.TestCase):
    def test_entry_and_exit_with_the_measured_borrow_cost(self):
        with tempfile.TemporaryDirectory() as d:
            st = run_arm("FOO", [spec({"FOO": (0.0024, 100000)}), spec({"FOO": (0.0048, 100000)})], [(10.0, 10.1), (8.9, 9.0)],
                         [0, 61, 61 + 4 * 3600], d)
            self.assertEqual(st["pending"], [])
            c = st["closed"][0]
            self.assertEqual((c["entry_px"], c["exit_px"], c["px_venue"]), (10.0, 9.0, "binance"))      # short sells the bid, buys back the ask
            cost = 0.0036 * 5 / 24
            self.assertAlmostEqual(c["borrow_cost"], round(cost, 6))
            self.assertAlmostEqual(c["net"], 0.10 - 0.002 - cost)                                       # raw 10%, fees 0.2%, BTC flat
            self.assertAlmostEqual(st["equity"], round(147.0 + 29.4 * c["net"], 4))
            self.assertIs(c["binance_perp_now"], False)
            self.assertEqual((c["borrow0"]["daily_rate"], c["borrow1"]["daily_rate"]), (0.0024, 0.0048))
            rows = [json.loads(x) for x in (Path(d) / "margin_arm").glob("*.jsonl").__next__().read_text().splitlines()]
            self.assertEqual([r["type"] for r in rows], ["event", "heartbeat", "trade", "heartbeat"])
            self.assertTrue(rows[0]["borrow0"]["borrowable"])

    def test_not_borrowable_is_skipped_and_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            st = run_arm("FOO", [spec({"OTHER": (0.001, 1)})], [], [0, 61], d)
            self.assertEqual(st["pending"], [])
            self.assertEqual(st["closed"][0]["skipped"], "not borrowable at the notice")
            self.assertEqual(st["equity"], 147.0)

    def test_squeeze_stops_the_short(self):
        with tempfile.TemporaryDirectory() as d:
            st = run_arm("FOO", [spec({"FOO": (0.0024, 100000)}), spec({"FOO": (0.0024, 100000)})],
                         [(10.0, 10.1), (12.9, 13.0)], [0, 61, 120], d)
            c = st["closed"][0]
            self.assertTrue(c["stopped"])
            self.assertAlmostEqual(c["net"], -0.30 - 0.002 - c["borrow_cost"])


class Publish(unittest.TestCase):
    def test_heartbeat_file_goes_to_the_l1f_margin_branch(self):
        calls, files = [], {}

        def fake(method, url, token, body=None, **kw):
            calls.append((method, url))
            if "/git/ref/heads/" in url:
                return (200, b"{}", {}) if files else (404, b"{}", {})
            if url.endswith("/git/trees"):
                return 201, b'{"sha":"t"}', {}
            if url.endswith("/git/commits"):
                return 201, b'{"sha":"c"}', {}
            if url.endswith("/git/refs"):
                files["_branch"] = body["ref"]
                return 201, b"{}", {}
            files[url.split("/contents/")[1]] = body
            return 201, b"{}", {}
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "20261201.jsonl").write_text('{"type":"heartbeat","t":1}\n')
            env = {"TRADELAB_DATA_PUSH_TOKEN": "SECRET"}
            self.assertEqual(mp.cycle(d, fake, env={}, sleep=lambda s: None)["enabled"], False)
            r = mp.cycle(d, fake, env=env, sleep=lambda s: None)
            self.assertEqual((r["ok"], r["parts"]), (True, 1))
            self.assertEqual(files["_branch"], "refs/heads/data/l1f-margin")
            self.assertTrue(next(k for k in files if k.startswith("margin_arm/20261201/")))
            self.assertEqual(mp.cycle(d, fake, env=env, sleep=lambda s: None)["parts"], 0)


class Wiring(unittest.TestCase):
    def test_pod_starts_the_publisher_and_the_protocol_is_locked(self):
        self.assertIn("margin_publish.loop", (ROOT / "server.py").read_text())
        import hashlib
        p = ROOT / "research/studies/protocol_l1f_margin_arm_20261127.md"
        want = (ROOT / "research/studies/protocol_l1f_margin_arm_20261127.sha256").read_text().split()[0]
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), want)
