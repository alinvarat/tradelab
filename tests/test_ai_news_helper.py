import unittest

from core import ai_news


class Helper(unittest.TestCase):
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
