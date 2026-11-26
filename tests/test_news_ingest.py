import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import news_ingest as ni


def rss(items):
    body = "".join(f"<item><title>{t}</title><link>http://x/{g}</link><guid>{g}</guid><pubDate>{p}</pubDate></item>" for g, t, p in items)
    return f"<rss><channel>{body}</channel></rss>".encode()


SRC = {"name": "prn", "kind": "rss", "url": "http://x", "every": 3, "market": "stock"}


class Base(unittest.TestCase):
    def setUp(self):
        ni.reset()
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(ni, "DIR", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        q = mock.patch.object(ni, "llm_enabled", return_value=False)
        q.start()
        self.addCleanup(q.stop)


class Pure(unittest.TestCase):
    def test_percentile_and_summary(self):
        self.assertEqual(ni.percentile([1, 2, 3, 4, 5], 50), 3)
        self.assertAlmostEqual(ni.percentile(list(range(1, 11)), 90), 9.1)
        self.assertIsNone(ni.percentile([], 50))
        s = ni.lat_summary([(0, 2.0, "s"), (0, 4.0, "s"), (0, 100.0, "m"), (0, -1.0, "s")])
        self.assertEqual((s["n"], s["n_minute_res"], s["n_negative"], s["median_s"]), (3, 1, 1, 2.0))

    def test_backoff_grows_caps_and_blocks_wait_a_minute(self):
        self.assertEqual(ni.backoff_s(3, 0), 3)
        self.assertEqual([ni.backoff_s(3, n) for n in (1, 2, 3)], [6, 12, 24])
        self.assertEqual(ni.backoff_s(3, 20), ni.BACKOFF_MAX_S)
        self.assertGreaterEqual(ni.backoff_s(2, 1, 429), ni.BLOCKED_BACKOFF_S)

    def test_eqn_parsers(self):
        it = ni.parse_eqn_frame('{"source_name":"E","news_title":"BTC up","coins_included":["BTC"],"url":"u","timestamp":1792676405}')
        self.assertEqual((it["t_pub"], it["res"], it["coins"]), (1792676405.0, "s", ["BTC"]))
        self.assertIsNone(ni.parse_eqn_frame("pong"))
        self.assertIsNone(ni.parse_eqn_frame("not json"))
        rows = ni.parse_eqn_rest(json.dumps({"items": [{"no": 7, "time": "2026-11-26T06:15:12.406Z", "en": "Hi", "url": "u"}]}))
        self.assertEqual((rows[0]["key"], rows[0]["res"]), ("eqn:7", "s"))

    def test_llm_filter(self):
        self.assertTrue(ni.eligible_for_llm("eqn_ws", "crypto", {"title": "x"}))
        self.assertTrue(ni.eligible_for_llm("prn", "stock", {"title": "Acme (NASDAQ: ACME) wins"}))
        self.assertFalse(ni.eligible_for_llm("prn", "stock", {"title": "No ticker here"}))
        self.assertTrue(ni.eligible_for_llm("sec_8k", "stock", {"items": ["2.02"]}))
        self.assertFalse(ni.eligible_for_llm("sec_8k", "stock", {"items": ["9.01"]}))

    def test_sec_needs_declared_user_agent(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertNotIn("sec_8k", [s["name"] for s in ni.sources()])
        with mock.patch.dict("os.environ", {"TRADELAB_SEC_UA": "Name a@b.c"}, clear=True):
            sec = ni.sources()[0]
            self.assertEqual((sec["name"], sec["ua"], sec["every"]), ("sec_8k", "Name a@b.c", 2))


class Polling(Base):
    def test_cold_start_not_counted_then_latency_and_conditional_get(self):
        calls = []
        feeds = [(200, rss([("a", "old (NASDAQ: OLD)", "Thu, 26 Nov 2026 06:00:00 +0000")]), {"ETag": "e1"}),
                 (304, b"", {}),
                 (200, rss([("a", "old", "Thu, 26 Nov 2026 06:00:00 +0000"),
                            ("b", "new", "Thu, 26 Nov 2026 06:41:26 +0000")]), {"ETag": "e2"})]
        def fake(url, headers):
            calls.append(dict(headers))
            st, body, h = feeds[len(calls) - 1]
            return st, body, ni.nl.parse_ts("Thu, 26 Nov 2026 06:41:31 +0000")[0], h
        cond = {}
        self.assertEqual(ni.poll_step(SRC, cond, fake), 3)
        self.assertEqual(ni.STATE["sources"]["prn"]["cold_items"], 1)
        ni.poll_step(SRC, cond, fake)
        ni.poll_step(SRC, cond, fake)
        self.assertEqual(calls[1].get("If-None-Match"), "e1")
        self.assertEqual(calls[2].get("If-None-Match"), "e1")
        v = ni.view(now=ni.nl.parse_ts("Thu, 26 Nov 2026 06:42:00 +0000")[0])
        self.assertEqual(v["sources"]["prn"]["seen_minus_published"]["n"], 1)
        self.assertEqual(v["sources"]["prn"]["seen_minus_published"]["median_s"], 5.0)
        self.assertEqual(v["sources"]["prn"]["not_modified"], 1)
        json.dumps(v)
        rows = [json.loads(x) for f in Path(self.tmp.name).glob("*.jsonl") for x in f.read_text().splitlines()]
        self.assertEqual([r["key"] for r in rows], ["prn:b"])

    def test_errors_back_off_and_recover(self):
        cond = {}
        waits = [ni.poll_step(SRC, cond, lambda u, h: (503, b"x", 0.0, {})) for _ in range(3)]
        self.assertEqual(waits, [6, 12, 24])
        self.assertEqual(ni.poll_step(SRC, cond, lambda u, h: (403, b"x", 0.0, {})), 60)
        ok = ni.poll_step(SRC, cond, lambda u, h: (200, rss([]), 1.0, {}))
        self.assertEqual(ok, 3)
        self.assertEqual(ni.STATE["sources"]["prn"]["consecutive_errors"], 0)

    def test_reload_window_restores_statistics(self):
        ni.log_row({"event": "item", "source": "prn", "key": "k", "t_pub": 100.0, "res": "s", "t_seen": 104.0}, 104.0)
        ni.reload_window(now=200.0)
        self.assertEqual(ni.view(now=200.0)["sources"]["prn"]["seen_minus_published"]["median_s"], 4.0)


class Llm(Base):
    def test_t_llm_logged_and_cap_enforced(self):
        it = {"key": "k", "title": "BTC ETF approved", "t_pub": 100.0}
        clock = iter([105.0])
        row = ni.llm_one("eqn_ws", it, 101.0, chat=lambda s, u, **kw: ('{"direction":"up","confidence":80,"instrument":"BTC"}', "claude/claude-haiku-5-5"),
                         now=lambda: next(clock))
        self.assertEqual((row["llm_s"], row["parsed"]["direction"]), (4.0, "up"))
        self.assertEqual(ni.view(now=110.0)["sources"]["eqn_ws"]["llm_minus_published"]["median_s"], 5.0)
        ni.STATE["llm"]["per_hour_cap"] = 1
        self.assertTrue(ni.enqueue_llm({"name": "a"}, it, 1.0))
        self.assertFalse(ni.enqueue_llm({"name": "a"}, it, 2.0))
        self.assertEqual(ni.STATE["llm"]["dropped"], 1)

    def test_unreadable_reply_is_a_failure_not_a_result(self):
        ni.llm_one("a", {"key": "k", "title": "t", "t_pub": 1.0}, 2.0, chat=lambda s, u, **kw: ("", "claude error: X"), now=lambda: 3.0)
        self.assertEqual((ni.STATE["llm"]["ok"], ni.STATE["llm"]["failed"]), (0, 1))

    def test_prompt_uses_haiku_model_only(self):
        seen = {}
        from core import ai_news
        ni.llm_one("a", {"key": "k", "title": "t"}, 2.0, chat=lambda s, u, **kw: seen.update(kw) or ("", "x"), now=lambda: 3.0)
        self.assertEqual(seen["model"], ai_news.CLAUDE_MODEL)
        self.assertEqual(ai_news.CLAUDE_MODEL, "claude-haiku-5-5")


class FakeSock:
    def __init__(self, data):
        self.data, self.sent = data, b""

    def recv(self, n):
        out, self.data = self.data[:n], self.data[n:]
        return out

    def sendall(self, b):
        self.sent += b


class WsFrames(unittest.TestCase):
    def test_text_ping_fragments_and_close(self):
        def srv(op, payload, fin=True):      # server frames are unmasked
            return bytes([(0x80 if fin else 0) | op, len(payload)]) + payload
        data = srv(9, b"hi") + srv(1, b"hel", fin=False) + srv(0, b"lo") + srv(8, b"")
        ws = ni.Ws("wss://x/ws", sock=FakeSock(data))
        self.assertEqual(ws.recv_text(), "hello")
        # pong was sent, masked, with the ping payload
        self.assertEqual(ws.sock.sent[0], 0x8A)
        self.assertTrue(ws.sock.sent[1] & 0x80)
        with self.assertRaises(EOFError):
            ws.recv_text()

    def test_client_frame_is_masked_and_roundtrips(self):
        f = ni.Ws.frame(1, b"ping")
        self.assertEqual(f[0], 0x81)
        mask, body = f[2:6], f[6:]
        self.assertEqual(bytes(b ^ mask[i % 4] for i, b in enumerate(body)), b"ping")



def bn_body(*arts):
    return json.dumps({"data": {"catalogs": [{"articles": [{"code": c, "title": "T " + c, "releaseDate": t} for c, t in arts]}]}}).encode()


class BinanceFast(Base):
    def test_variants_are_distinct_valid_cache_keys_and_skip_the_control(self):
        v = ni.binance_variants(49)
        self.assertEqual(len(v), 12)
        self.assertEqual(len(set(v)), 12)
        self.assertNotIn(ni.BN + "49", v)
        for u in v:
            q = u.split("?")[1].split("&")
            self.assertEqual(sorted(x.split("=")[0] for x in q), sorted(ni.BN_PARAMS))
            self.assertIn("catalogId=49", q)
            self.assertIn("pageSize=10", q)
        self.assertNotEqual(set(v), set(ni.binance_variants(48)))

    def test_cache_expiry_from_age_header(self):
        self.assertEqual(ni.cache_expiry({"Age": "104", "X-Cache": "Hit from cloudfront"}, 1000.0), 1016.0)
        self.assertEqual(ni.cache_expiry({"age": "0"}, 1000.0), 1120.0)
        self.assertEqual(ni.cache_expiry({"X-Cache": "Miss from cloudfront"}, 1000.0), 1120.0)
        self.assertEqual(ni.cache_expiry({"X-Cache": "RefreshHit from cloudfront"}, 1000.0), 1120.0)
        self.assertEqual(ni.cache_expiry({"X-Cache": "Hit from cloudfront"}, 1000.0), 1060.0)
        self.assertEqual(ni.cache_expiry({}, 1000.0), 1120.0)

    def test_next_variant_takes_earliest_expiry_and_respects_gap(self):
        keys = {"a": 130.0, "b": 100.0, "c": 110.0}
        self.assertEqual(ni.next_variant(keys, 90.0), ("b", 11.0))
        self.assertEqual(ni.next_variant(keys, 105.0), ("b", 0.0))
        self.assertEqual(ni.next_variant(keys, 105.0, last_fetch=104.5), ("b", 1.5))

    def test_trace(self):
        self.assertEqual(ni.cache_trace({"X-Cache": "Hit from cloudfront", "Age": "104"}), "Hit:104")
        self.assertEqual(ni.cache_trace({"X-Cache": "Miss from cloudfront"}), "Miss")
        self.assertIsNone(ni.cache_trace({}))

    def run_ticks(self, src, responses, t0=1795680000.0, n=400):
        """Fake clock + fake CDN. responses(url, t) -> (status, body, headers). Returns (log of (t, url), state)."""
        clock = [t0]
        log = []

        def fetch(url, headers):
            st, body, hdr = responses(url, clock[0])
            log.append((clock[0], url))
            return st, body, clock[0], hdr
        state = {}
        for _ in range(n):
            w = ni.multi_step(src, state, now=lambda: clock[0], fetch_fn=fetch)
            clock[0] += max(w, 0.05)
        return log, state

    def test_rotation_polls_each_key_once_per_ttl_and_sees_new_item_fast(self):
        src = {"name": "binance_news_fast", "kind": "binance_multi", "catalog": 49, "every": 2.0, "market": "crypto", "llm": False, "trace": True}
        fill = {}                       # url -> time the fake CDN entry was filled
        t0 = 1795680000.0
        pub = t0 + 300.0                # article published 300 s in (origin knows it from then on)

        def cdn(url, t):
            if url not in fill or t - fill[url] >= ni.BN_TTL_S:
                fill[url] = t
                hdr = {"X-Cache": "Miss from cloudfront"}
            else:
                hdr = {"X-Cache": "Hit from cloudfront", "Age": str(int(t - fill[url]))}
            arts = [("old", int((t0 - 1000) * 1000))]
            if fill[url] >= pub:
                arts.append(("new", int(pub * 1000)))
            return 200, bn_body(*arts), hdr
        log, state = self.run_ticks(src, cdn, t0=t0, n=900)
        st = ni.STATE["sources"]["binance_news_fast"]
        self.assertEqual(st["errors"], 0)
        # about one request per 10 s over 12 keys, not one per 2 s
        span = log[-1][0] - log[0][0]
        self.assertLess(len(log), span / 10 * 1.5)
        rows = [json.loads(x) for f in Path(self.tmp.name).glob("*.jsonl") for x in f.read_text().splitlines()]
        new = [r for r in rows if r["key"] == "binance_news:new"]
        self.assertEqual(len(new), 1)                       # first sighting only
        self.assertLessEqual(new[0]["lat_s"], 14.0)         # 120 s / 12 keys + margin, not up to 120 s
        self.assertTrue(new[0]["via"].startswith("Miss"))
        self.assertNotIn("binance_news:old", [r["key"] for r in rows])  # cold items never counted

    def test_block_pauses_every_key(self):
        src = {"name": "binance_news_fast", "kind": "binance_multi", "catalog": 49, "every": 2.0, "market": "crypto", "llm": False, "trace": True}
        calls = []

        def blocked(url, t):
            calls.append(t)
            return 429, b"x", {}
        self.run_ticks(src, blocked, n=70)
        self.assertLessEqual(len(calls), 2)          # 12 keys, but one 429 pauses all of them for a minute
        self.assertTrue(all(b - a >= 60 for a, b in zip(calls, calls[1:])))


class OkxCandidates(Base):
    HELP_ITEMS = [{"id": "z", "slug": "okx-to-support-zeta-crypto-migration", "title": "OKX to support ZETA crypto migration",
                   "publishTime": 1795687200000, "updatedAt": 1795687218000, "sectionSlug": "announcements-new-listings", "categorySlug": "announcements"},
                  {"id": "u", "slug": "p2p-guide", "title": "Guide & Fees", "publishTime": 1795622400000, "updatedAt": 1795700016000,
                   "sectionSlug": "announcements-p2p-trading", "categorySlug": "announcements"}]

    def page(self):
        inner = json.dumps({"appContext": {"initialProps": {"sectionData": {"articleList": {"list": self.HELP_ITEMS}}}}})
        return ('<html><script>window.__INIT_STATE__.appContext = parseData(' + json.dumps(inner) + ');</script></html>').encode()

    def test_key_is_the_slug_for_any_host_or_locale(self):
        want = "okx_announcements:https://www.okx.com/help/okx-to-support-zeta-crypto-migration"
        for u in ("https://www.okx.com/help/okx-to-support-zeta-crypto-migration",
                  "https://my.okx.com/en-eu/help/okx-to-support-zeta-crypto-migration",
                  "https://app.okx.com/en-us/help/okx-to-support-zeta-crypto-migration/", "okx-to-support-zeta-crypto-migration"):
            self.assertEqual(ni.okx_key(u), want)

    def test_rest_candidate_pairs_with_control_on_key_and_stamp(self):
        body = json.dumps({"data": [{"details": [{"annType": "announcements-new-listings", "title": "OKX to support ZETA crypto migration",
                                                  "url": "https://my.okx.com/en-eu/help/okx-to-support-zeta-crypto-migration", "pTime": "1795687218036"}]}]})
        ctrl = ni.nl.parse_okx_announcements(json.loads(body), "okx_announcements")
        cand = ni.parse_okx_norm(body)
        self.assertEqual(cand[0]["t_pub"], ctrl[0]["t_pub"])
        self.assertEqual(cand[0]["key"], ni.okx_key("okx-to-support-zeta-crypto-migration"))

    def test_help_page_structured_parse(self):
        items = ni.parse_okx_help(self.page())
        self.assertEqual([i["key"] for i in items], [ni.okx_key("okx-to-support-zeta-crypto-migration"), ni.okx_key("p2p-guide")])
        self.assertEqual(items[0]["t_pub"], 1795687218.0)          # updatedAt == API pTime, not publishTime
        self.assertEqual(items[0]["extra"]["publish_time"], 1795687200.0)
        self.assertEqual(items[0]["res"], "s")
        self.assertEqual(items[1]["title"], "Guide & Fees")

    def test_help_page_regex_fallback_on_real_escaped_snippet(self):
        raw = ('window.__INIT_STATE__.appContext = parseData("{\\"appContext\\":{\\"initialProps\\":{\\"sectionData\\":{\\"articleList\\":{\\"list\\":[{'
               '\\"id\\":\\"okx-to-support-zeta-crypto-migration\\",\\"slug\\":\\"okx-to-support-zeta-crypto-migration\\",'
               '\\"title\\":\\"OKX to support ZETA crypto migration\\",\\"publishTime\\":1795687200000,\\"updatedAt\\":1795687218000,'
               '\\"sectionSlug\\":\\"announcements-new-listings\\",\\"categorySlug\\":\\"announcements\\"},{\\"id\\":\\"x\\",\\"slug\\":\\"x\\",'
               '\\"title\\":\\"A \\u0026 B\\",\\"publishTime\\":1795622400000,\\"updatedAt\\":1795682513000,\\"sectionSlug\\":\\"s\\"')
        items = ni.parse_okx_help(raw)                   # truncated JSON: only the regex path can read it
        self.assertEqual([i["t_pub"] for i in items], [1795687218.0, 1795682513.0])
        self.assertEqual(items[1]["title"], "A & B")
        self.assertEqual(ni.parse_okx_help(b"<html>no data</html>"), [])

    def test_help_source_records_latency_with_extra_and_no_llm(self):
        src = next(s for s in ni.sources() if s["name"] == "okx_help_latest")
        cond = {}
        ni.poll_step(src, cond, lambda u, h: (200, self.page(), 1795687300.0, {"ETag": "e1"}))   # cold
        self.HELP_ITEMS = self.HELP_ITEMS + [{"slug": "new-one", "title": "New", "publishTime": 1, "updatedAt": 1795687400000, "sectionSlug": "s"}]
        with mock.patch.object(ni, "llm_enabled", return_value=True), mock.patch.object(ni, "enqueue_llm") as q:
            ni.poll_step(src, cond, lambda u, h: (200, self.page(), 1795687403.5, {}))
            q.assert_not_called()
        rows = [json.loads(x) for f in Path(self.tmp.name).glob("*.jsonl") for x in f.read_text().splitlines()]
        self.assertEqual([(r["key"], r["lat_s"]) for r in rows], [(ni.okx_key("new-one"), 3.5)])
        self.assertIn("publish_time", rows[0])

    def test_new_sources_registered_with_unique_names_and_no_llm(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            srcs = ni.sources()
        names = [s["name"] for s in srcs]
        self.assertEqual(len(names), len(set(names)))
        new = ["binance_listings_fast", "binance_news_fast", "binance_delist_fast", "okx_ann_my", "okx_ann_listings", "okx_help_latest", "okx_help_listings"]
        for n in new:
            self.assertIn(n, names)
        for s in srcs:
            if s["name"] in new:
                self.assertFalse(s["llm"])
        for n in ("binance_listings", "binance_news", "binance_delist", "okx_announcements"):      # controls untouched
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
