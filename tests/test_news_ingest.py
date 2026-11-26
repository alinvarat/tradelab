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


if __name__ == "__main__":
    unittest.main()
