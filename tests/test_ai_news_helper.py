import unittest

from core import ai_news


class Helper(unittest.TestCase):
    def setUp(self):
        from unittest import mock
        p = mock.patch.object(ai_news, "custom_available", return_value=False)   # the free-model path
        p.start()
        self.addCleanup(p.stop)

    def test_custom_provider_serves_helpers_directly(self):
        from unittest import mock
        calls = []

        def fake(system, user, timeout=180, model=None, cache_layout=False):
            calls.append(model)
            return "ok", "custom/m"
        with mock.patch.object(ai_news, "custom_available", return_value=True):
            self.assertEqual(ai_news.chat_helper("s", "u", chat_fn=fake), ("ok", "custom/m"))
        self.assertEqual(calls, [ai_news.DECISION_MODEL])

    def test_free_models_first_then_deepseek(self):
        calls = []

        def fake(system, user, timeout=180, model=None, cache_layout=False):
            calls.append(model)
            return ("", "error") if model != ai_news.DECISION_MODEL else ("ok", "deepseek")
        text, name = ai_news.chat_helper("s", "u", chat_fn=fake)
        self.assertEqual((text, name), ("ok", "deepseek"))
        self.assertEqual(calls, ai_news.HELPER_MODELS + [ai_news.DECISION_MODEL])

    def test_first_free_answer_is_used(self):
        def fake(system, user, timeout=180, model=None, cache_layout=False):
            return ("{}", model.split("/", 1)[-1])
        text, name = ai_news.chat_helper("s", "u", chat_fn=fake)
        self.assertEqual(name, ai_news.HELPER_MODELS[0].split("/", 1)[-1])
        self.assertTrue(name.endswith(":free"))


if __name__ == "__main__":
    unittest.main()


class CustomProvider(unittest.TestCase):
    def test_paid_calls_use_the_configured_provider_and_free_ones_do_not(self):
        import io
        import json as _json
        import os
        from unittest import mock
        sent = []

        def fake_urlopen(req, timeout=0):
            sent.append((req.full_url, _json.loads(req.data)["model"]))
            return io.BytesIO(_json.dumps({"model": "m1", "choices": [{"message": {"content": "hi"}}]}).encode())
        with mock.patch.dict(os.environ, {"TRADELAB_LLM_API_KEY": "test-key"}), \
                mock.patch.object(ai_news, "CUSTOM_MODEL", "m1"), \
                mock.patch.object(ai_news, "opencode_available", return_value=False):
            text, name = ai_news.chat("s", "u", urlopen=fake_urlopen, model=ai_news.DECISION_MODEL)
            self.assertEqual((text, name), ("hi", "custom/m1"))
            self.assertTrue(sent[0][0].endswith("/chat/completions"))
            self.assertEqual(sent[0][1], "m1")
            with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-test"}):
                ai_news.chat("s", "u", urlopen=fake_urlopen, model="openrouter/google/gemma-4-31b-it:free")
            self.assertIn("openrouter.ai", sent[-1][0])                 # free helper models stay on OpenRouter

    def test_without_a_key_nothing_changes(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRADELAB_LLM_API_KEY", None)
            self.assertFalse(ai_news.custom_available())


class ScoringProvider(unittest.TestCase):
    def test_headline_scoring_uses_the_configured_provider(self):
        import io
        import json as _json
        import os
        from unittest import mock
        seen = []

        def fake_urlopen(req, timeout=0):
            seen.append(req.full_url)
            reply = _json.dumps({"scores": [{"id": "1", "score": 0.5}]})
            return io.BytesIO(_json.dumps({"choices": [{"message": {"content": reply}}]}).encode())
        with mock.patch.dict(os.environ, {"TRADELAB_LLM_API_KEY": "test-key"}), mock.patch.object(ai_news, "CUSTOM_MODEL", "m1"):
            ai_news.score_openrouter([{"id": "1", "title": "t", "summary": "", "symbols": ["AAPL"]}], urlopen=fake_urlopen)
        self.assertTrue(seen and "openrouter.ai" not in seen[0])


class AnthropicProvider(unittest.TestCase):
    """Owner 2026-11-25: Claude Haiku 5.5 answers paid calls when ANTHROPIC_API_KEY is set (no network in tests)."""

    class _Client:
        def __init__(self, stop="end_turn", text="hi", fail=None):
            self.sent, self.stop, self.text, self.fail = [], stop, text, fail
            self.messages = self

        def create(self, **kw):
            from types import SimpleNamespace as NS
            self.sent.append(kw)
            if self.fail:
                raise self.fail
            return NS(stop_reason=self.stop, model="claude-haiku-5-5",
                      content=[NS(type="thinking", thinking=""), NS(type="text", text=self.text)],
                      usage=NS(input_tokens=1000, output_tokens=200, cache_read_input_tokens=10000,
                               cache_creation_input_tokens=0))

    def test_request_shape_text_and_cost(self):
        c = self._Client()
        before = ai_news.spend()["total_usd"]
        text, name = ai_news._chat_anthropic("ROLE", "DATA", 30, True, client=c)
        self.assertEqual((text, name), ("hi", "anthropic/claude-haiku-5-5"))
        kw = c.sent[0]
        self.assertEqual(kw["model"], "claude-haiku-5-5")
        self.assertNotIn("temperature", kw)                  # Haiku 5.5 rejects sampling parameters
        self.assertEqual(kw["system"], ai_news.CACHE_SYSTEM)
        self.assertTrue(kw["messages"][0]["content"].startswith("DATA"))
        self.assertTrue(kw["messages"][0]["content"].endswith("ROLE"))
        self.assertEqual(kw["cache_control"], {"type": "ephemeral"})
        # 1000*0.10 + 10000*0.01 + 200*0.50 = 300 -> 0.0003 USD
        self.assertAlmostEqual(ai_news.spend()["total_usd"] - before, 0.0003, places=9)

    def test_refusal_and_error_return_no_text(self):
        self.assertEqual(ai_news._chat_anthropic("s", "u", 30, False, client=self._Client(stop="refusal"))[0], "")
        text, reason = ai_news._chat_anthropic("s", "u", 30, False, client=self._Client(fail=RuntimeError("x")))
        self.assertEqual(text, "")
        self.assertTrue(reason.startswith("anthropic error: RuntimeError"))

    def test_paid_calls_go_to_claude_only_when_key_is_set(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}), \
                mock.patch.object(ai_news, "_chat_anthropic", return_value=("ok", "anthropic/claude-haiku-5-5")) as m:
            self.assertEqual(ai_news.chat("s", "u", model=ai_news.DECISION_MODEL)[1], "anthropic/claude-haiku-5-5")
            self.assertIn("claude-haiku-5-5", ai_news.providers())
        self.assertEqual(m.call_count, 1)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(ai_news.anthropic_available())

    def test_headline_scores_parse(self):
        c = self._Client(text='[{"id": "1", "score": 0.5, "confidence": 0.8, "category": "earnings"}]')
        out = ai_news.score_anthropic([{"id": "1", "title": "X beats", "symbols": ["X"]}], client=c)
        self.assertIn("1", out)
