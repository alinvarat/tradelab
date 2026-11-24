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
