"""Offline tests for core/news_latency_fwd.py (synthetic feeds and bars only)."""
import json
import unittest

from core import news_latency_fwd as nl

P = {"min_pre_coverage": 3, "large_move": 0.01, "snap_max_age_s": 60, "latest_entry_s": 3300, "min_conf": 60,
     "cost_rt": {"crypto": 0.0014, "stock": 0.002}, "min_trades": 3, "min_days": 2}

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>8-K - ACME CORP (0000012345) (Filer)</title>
<link href="https://www.sec.gov/Archives/edgar/data/12345/000001234526000123-index.htm"/>
<summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-11-26 &lt;br&gt;Item 2.02: Results Item 9.01: Exhibits</summary>
<updated>2026-11-26T10:15:23-05:00</updated><id>urn:tag:sec.gov,2008:accession-number=0000012345-26-000123</id></entry>
<entry><title>8-K - ACME CORP (0000012345) (Filer)</title><link href="x"/><updated>2026-11-26T10:15:23-05:00</updated>
<id>urn:tag:sec.gov,2008:accession-number=0000012345-26-000123</id></entry></feed>"""


def bars(t0, n, px, step=0.0, vol=10):
    return [[t0 + 60 * i, px + step * i, px + step * i, px + step * i, px + step * i, vol] for i in range(n)]


class Parsers(unittest.TestCase):
    def test_ts(self):
        self.assertEqual(nl.parse_ts("2026-11-26T10:15:23-05:00"), (1795706123.0, "s"))
        t, res = nl.parse_ts("Thu, 26 Nov 2026 14:00 GMT")
        self.assertEqual((t, res), (1795701600.0, "m"))
        self.assertAlmostEqual(nl.parse_ts("1795701600123")[0], 1795701600.123, places=2)
        self.assertEqual(nl.parse_ts("garbage"), (None, None))

    def test_edgar_dedup_and_items(self):
        r = nl.parse_edgar_atom(ATOM)
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0]["cik"], r[0]["items"], r[0]["form"]), (12345, ["2.02", "9.01"], "8-K"))
        self.assertEqual(nl.stock_candidate({**r[0], "source": "sec_8k"}, {12345: "ACME"}), ("ACME", ""))
        self.assertEqual(nl.stock_candidate({**r[0], "source": "sec_8k", "items": ["9.01"]}, {12345: "ACME"})[1], "immaterial_8k")

    def test_rss_ticker(self):
        x = b"<rss><channel><item><title>Acme (NASDAQ: ACME) beats</title><guid>g1</guid><pubDate>Thu, 26 Nov 2026 14:00:05 GMT</pubDate></item></channel></rss>"
        it = nl.parse_rss(x, "prn")[0]
        self.assertEqual((it["key"], it["res"]), ("prn:g1", "s"))
        self.assertEqual(nl.ticker_from_text(it["title"]), "ACME")

    def test_binance_okx(self):
        b = nl.parse_binance({"data": {"catalogs": [{"articles": [{"code": "c1", "title": "T", "releaseDate": 1795701600000}]}]}}, "b")
        self.assertEqual(b[0]["t_pub"], 1795701600.0)
        o = nl.parse_okx_announcements({"data": [{"details": [{"title": "T", "url": "u", "pTime": "1795701600000"}]}]}, "o")
        self.assertEqual(o[0]["key"], "o:u")

    def test_candles_and_chart(self):
        self.assertEqual(nl.parse_okx_candles({"data": [["120000", "2", "2", "2", "2", "1"], ["60000", "1", "1", "1", "1", "1"]]})[0][0], 60.0)
        d = {"chart": {"result": [{"timestamp": [60, 120], "indicators": {"quote": [{"open": [1, None], "high": [1, None], "low": [1, None], "close": [1, None], "volume": [5, None]}]}, "meta": {"regularMarketPrice": 3}}]}}
        b, m = nl.parse_yahoo_chart(d)
        self.assertEqual((len(b), m["regularMarketPrice"]), (1, 3))

    def test_haiku(self):
        self.assertEqual(nl.parse_haiku('x {"direction":"UP","confidence":"72","instrument":"btc"}')["instrument"], "BTC")
        self.assertIsNone(nl.parse_haiku(""))
        self.assertIsNone(nl.parse_haiku('{"direction":"maybe","confidence":1}'))
        self.assertEqual(nl.parse_haiku('{"direction":"none","confidence":500}')["confidence"], 100)

    def test_rth(self):
        self.assertTrue(nl.in_rth(1795706123.0))        # Thu 10:15 ET
        self.assertFalse(nl.in_rth(1795701600.0))


def item(t_pub=1000000.0, direction="up", conf=80, px=100.0, move=0.02, market="crypto", key="k1", inst="BTC", t_llm_off=20):
    t0 = t_pub - 300
    b = bars(t0, 5, px) + bars(t0 + 300, 66, px * (1 + move / 2), 0.0)
    b = [r for r in b if r[0] < t_pub + 3600]
    b = [[r[0]] + [px * (1 + move) if r[0] >= t_pub + 1200 else px] * 4 + [10] for r in b]
    return {"key": key, "source": "s", "market": market, "instrument": inst, "t_pub": t_pub, "t_seen": t_pub + 5,
            "t_llm": t_pub + t_llm_off, "llm": {"direction": direction, "confidence": conf}, "bars": b, "status": "scored",
            "snap": {"t_req": t_pub + t_llm_off + 5, "price": px, "price_t": t_pub + t_llm_off + 4, "bid": px, "ask": px * 1.0001}}


class Metrics(unittest.TestCase):
    def test_close_before_open_after(self):
        b = bars(0, 5, 1.0, 1.0)
        self.assertEqual(nl.close_before(b, 120), 2.0)      # bars 0 and 1 ended by 120
        self.assertIsNone(nl.close_before(b, 10000))
        self.assertEqual(nl.open_after(b, 61), 3.0)

    def test_evaluate_and_fraction(self):
        e = nl.evaluate_item(item(), P)
        self.assertEqual(e["excluded"], "")
        self.assertAlmostEqual(e["move"], 0.02, places=6)
        self.assertTrue(e["large"])
        self.assertAlmostEqual(e["f_snap"], 0.0, places=2)       # nothing had moved yet at t_llm
        self.assertAlmostEqual(e["gross"], 0.02, places=3)
        self.assertLess(e["gross"], 0.02)                      # paid the ask

    def test_short_gains_on_fall(self):
        e = nl.evaluate_item(item(direction="down", move=-0.02), P)
        self.assertGreater(e["gross"], 0.019)

    def test_thin_stock_excluded(self):
        it = item(market="stock", inst="AAA")
        it["bars"] = [b for b in it["bars"] if b[0] >= it["t_pub"]]
        self.assertEqual(nl.evaluate_item(it, P)["excluded"], "thin_pre_window")

    def test_too_late(self):
        e = nl.evaluate_item(item(t_llm_off=3400), P)
        self.assertEqual(e.get("excluded_trade"), "too_late")
        self.assertFalse(e["trade"])

    def test_overlap_one_trade_per_instrument(self):
        evs = []
        for i, off in enumerate((20, 40)):
            e = nl.evaluate_item(item(key=f"k{i}", t_llm_off=off), P)
            e["t_exit"] = 1000000.0 + 3600
            evs.append(e)
        self.assertEqual(len(nl.select_trades(evs, P)), 1)

    def test_stale_snapshot_no_entry(self):
        it = item()
        it["snap"]["price_t"] = it["snap"]["t_req"] - 500
        e = nl.evaluate_item(it, P)
        self.assertIsNone(e["entry"])
        self.assertIsNotNone(e["gross_bar"])

    def test_percentile_and_boot(self):
        self.assertEqual(nl.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertAlmostEqual(nl.percentile(list(range(11)), 0.9), 9.0)
        ci = nl.boot_ci([0.01, 0.02, 0.03, 0.04], ["a", "a", "b", "b"], n=200)
        self.assertEqual(ci["days"], 2)
        self.assertLessEqual(ci["lo"], ci["hi"])

    def test_summarize_end_to_end(self):
        rows = []
        for i in range(6):
            r = item(t_pub=1000000.0 + i * 86400, key=f"k{i}", inst=f"C{i}")
            rows.append({**r, "res": "s", "cold": False})
        rows.append({"key": "cold", "source": "s", "market": "crypto", "t_pub": 5.0, "t_seen": 9.0, "cold": True, "status": "cold_start"})
        out = nl.summarize(rows, P)
        self.assertEqual(out["latency_s"]["seen_minus_pub"]["ALL"]["n"], 6)
        self.assertEqual(out["latency_s"]["seen_minus_pub"]["ALL"]["median"], 5)
        self.assertEqual(out["latency_s"]["llm_minus_seen"]["ALL"]["median"], 15)
        self.assertEqual(out["pnl"]["crypto"]["n"], 6)
        self.assertEqual(out["fraction_of_move"]["crypto"]["items_large"], 6)
        self.assertIn(out["verdict"]["crypto"], ("edge candidate (forward)", "no edge shown"))
        json.dumps(out)


if __name__ == "__main__":
    unittest.main()
