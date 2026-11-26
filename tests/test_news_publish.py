import json
import tempfile
import unittest
from pathlib import Path

from core import news_publish as np_

ENV = {"TRADELAB_DATA_PUSH_TOKEN": "SECRET-TOKEN-VALUE"}


class Fake:
    """Records calls; behaves like the GitHub endpoints the publisher uses."""

    def __init__(self, branch=True, put_status=201, fail_first=0, put_body=b"{}"):
        self.calls, self.branch, self.put_status, self.fail_first, self.put_body = [], branch, put_status, fail_first, put_body
        self.files = {}

    def __call__(self, method, url, token, body=None):
        self.calls.append((method, url, token, body))
        if self.fail_first > 0:
            self.fail_first -= 1
            return 503, b"", {}
        if "/git/ref/heads/" in url:
            return (200, b"{}", {}) if self.branch else (404, b"{}", {})
        if url.endswith("/git/trees"):
            return 201, b'{"sha":"t1"}', {}
        if url.endswith("/git/commits"):
            return 201, b'{"sha":"c1"}', {}
        if url.endswith("/git/refs"):
            self.branch = True
            return 201, b"{}", {}
        if method == "PUT":
            path = url.split("/contents/")[1]
            if self.put_status == 201 and path in self.files:
                return 422, b'{"message":"Invalid request.\\n\\n\\"sha\\" wasn\'t supplied."}', {}
            if self.put_status == 201:
                self.files[path] = body
            return self.put_status, self.put_body, {}
        return 500, b"", {}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        np_.STATE.update(parts=0, bytes=0, cycles=0, failures=0, consecutive_failures=0, last_error=None, last_ok_utc=None)
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)

    def write(self, day, text):
        with open(self.d / f"{day}.jsonl", "ab") as f:
            f.write(text.encode())


class NoToken(Base):
    def test_no_secret_is_a_clean_noop(self):
        self.write("20261126", '{"a":1}\n')
        fake = Fake()
        r = np_.cycle(self.d, fake, env={}, sleep=self.sleep)
        self.assertEqual((r["enabled"], r["ok"], r["parts"]), (False, True, 0))
        self.assertEqual(fake.calls, [])
        self.assertFalse(np_.enabled({}))
        self.assertFalse(np_.enabled({"TRADELAB_DATA_PUSH_TOKEN": "a\nb"}))
        self.assertTrue(np_.enabled(ENV))


class Publish(Base):
    def test_uploads_whole_lines_as_create_only_part_and_advances_cursor(self):
        self.write("20261126", '{"r":1}\n{"r":2}\n{"torn":')
        fake = Fake()
        r = np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertEqual((r["ok"], r["parts"]), (True, 1))
        path = "news_ingest/20261126/0000000000-0000000016.jsonl"
        sent = fake.files[path]
        self.assertEqual(sent["branch"], "data/news-ingest")
        self.assertNotIn("sha", sent)                                     # create-only: never replaces a file
        import base64
        self.assertEqual(base64.b64decode(sent["content"]), b'{"r":1}\n{"r":2}\n')
        self.assertEqual(np_.read_cursor(self.d), {"20261126": 16})
        # nothing new -> no upload; the torn line completes -> only the new bytes go
        n = len(fake.calls)
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertEqual(len(fake.calls), n)
        self.write("20261126", '1}\n')
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertIn("news_ingest/20261126/0000000016-0000000027.jsonl", fake.files)

    def test_cursor_file_is_not_a_log_file(self):
        self.write("20261126", '{"r":1}\n')
        np_.cycle(self.d, Fake(), env=ENV, sleep=self.sleep)
        self.assertEqual([p.name for p in self.d.glob("*.jsonl")], ["20261126.jsonl"])
        self.assertTrue((self.d / np_.CURSOR_NAME).exists())

    def test_missing_branch_is_created_as_orphan(self):
        self.write("20261126", '{"r":1}\n')
        fake = Fake(branch=False)
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        commit = next(c for c in fake.calls if c[1].endswith("/git/commits"))
        self.assertEqual(commit[3]["parents"], [])
        self.assertTrue(fake.branch)

    def test_backlog_is_batched_and_oldest_day_first(self):
        big = ('{"x":"' + "a" * 1000 + '"}\n') * 600          # about 600 KB
        self.write("20261124", big)
        self.write("20261126", big)
        r = np_.cycle(self.d, Fake(), env=ENV, sleep=self.sleep)
        self.assertLessEqual(r["bytes"], np_.MAX_BYTES_PER_CYCLE)
        self.assertLessEqual(r["parts"], np_.MAX_FILES_PER_CYCLE)
        cur = np_.read_cursor(self.d)
        self.assertIn("20261124", cur)
        self.assertLessEqual(cur["20261124"], np_.MAX_PART_BYTES)

    def test_old_day_growing_after_midnight_is_still_published(self):
        self.write("20261125", '{"r":1}\n')
        fake = Fake()
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.write("20261125", '{"r":2}\n')
        self.write("20261126", '{"r":3}\n')
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertEqual(sorted(p.split("/")[1] for p in fake.files), ["20261125", "20261125", "20261126"])

    def test_existing_part_counts_as_done(self):
        self.write("20261126", '{"r":1}\n')
        fake = Fake()
        np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        (self.d / np_.CURSOR_NAME).unlink()                       # cursor lost (volume reset): same range is re-sent
        r = np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertTrue(r["ok"])
        self.assertEqual(np_.read_cursor(self.d), {"20261126": 8})


class Failures(Base):
    def test_retries_with_backoff_then_succeeds(self):
        self.write("20261126", '{"r":1}\n')
        fake = Fake(fail_first=2)
        r = np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertTrue(r["ok"])
        self.assertEqual(len(self.sleeps), 2)
        self.assertLess(self.sleeps[0], self.sleeps[1])

    def test_gives_up_keeps_cursor_and_never_raises(self):
        self.write("20261126", '{"r":1}\n')
        fake = Fake(fail_first=999)
        r = np_.cycle(self.d, fake, env=ENV, sleep=self.sleep)
        self.assertFalse(r["ok"])
        self.assertEqual(np_.read_cursor(self.d), {})
        self.assertEqual(np_.STATE["consecutive_failures"], 1)
        self.assertLessEqual(len(fake.calls), np_.TRIES)
        # recovery on the next cycle sends the same bytes
        r2 = np_.cycle(self.d, Fake(), env=ENV, sleep=self.sleep)
        self.assertTrue(r2["ok"])
        self.assertEqual(np_.STATE["consecutive_failures"], 0)

    def test_transport_exception_is_contained(self):
        self.write("20261126", '{"r":1}\n')

        def boom(*a, **k):
            raise RuntimeError("SECRET-TOKEN-VALUE leaked")
        r = np_.cycle(self.d, boom, env=ENV, sleep=self.sleep)
        self.assertFalse(r["ok"])
        self.assertNotIn("SECRET-TOKEN-VALUE", json.dumps(r) + json.dumps(np_.STATE))

    def test_rejected_upload_is_a_failure(self):
        self.write("20261126", '{"r":1}\n')
        r = np_.cycle(self.d, Fake(put_status=403), env=ENV, sleep=self.sleep)
        self.assertFalse(r["ok"])
        self.assertEqual(np_.read_cursor(self.d), {})

    def test_token_never_in_state_or_view(self):
        self.write("20261126", '{"r":1}\n')
        np_.cycle(self.d, Fake(put_status=403), env=ENV, sleep=self.sleep)
        self.assertNotIn("SECRET-TOKEN-VALUE", json.dumps(np_.STATE) + json.dumps(np_.view()))

    def test_backoff_shape_and_retry_after(self):
        fixed = lambda: 0.5  # noqa: E731
        self.assertEqual([np_.backoff_s(n, None, fixed) for n in (1, 2, 3)], [2.0, 4.0, 8.0])
        self.assertEqual(np_.backoff_s(30, None, fixed), np_.BACKOFF_CAP_S)
        self.assertEqual(np_.backoff_s(1, "30", fixed), 30.0)
        self.assertEqual(np_.backoff_s(1, "9999", fixed), np_.BACKOFF_CAP_S)

    def test_secondary_rate_limit_403_with_retry_after_is_retried(self):
        seen = []

        def t(method, url, token, body=None):
            seen.append(1)
            return (403, b"", {"Retry-After": "5"}) if len(seen) < 3 else (200, b"{}", {})
        st, _ = np_.call(t, "GET", "u", "tok", sleep=self.sleep)
        self.assertEqual((st, len(seen)), (200, 3))


class Config(unittest.TestCase):
    def test_defaults_and_minimum_interval(self):
        c = np_._cfg({"TRADELAB_DATA_PUSH_TOKEN": "x"})
        self.assertEqual((c["branch"], c["interval_s"]), ("data/news-ingest", 600.0))
        self.assertEqual(np_._cfg({"TRADELAB_NEWS_PUSH_MINUTES": "0.1"})["interval_s"], 60.0)
        self.assertEqual(np_._cfg({"TRADELAB_NEWS_PUSH_MINUTES": "junk"})["interval_s"], 600.0)

    def test_ingest_loop_spawns_publisher_and_view_reports_it(self):
        src = (Path(__file__).resolve().parent.parent / "core" / "news_ingest.py").read_text()
        self.assertIn('spawn("publish", news_publish.loop)', src)
        self.assertIn('"publish": news_publish.view()', src)


if __name__ == "__main__":
    unittest.main()
