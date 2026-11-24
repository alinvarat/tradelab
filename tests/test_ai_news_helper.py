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



class ClaudeCli(unittest.TestCase):
    """Owner 2026-11-25: Claude Haiku 5.5 via the Claude Code CLI (Max plan). No process or network in tests."""

    @staticmethod
    def _run(result="hi", code=0, subtype="success", models=("claude-haiku-5-5",), sent=None):
        import json as _json
        from types import SimpleNamespace as NS

        def run(cmd, input=None, capture_output=True, text=True, timeout=0, cwd=None):
            if sent is not None:
                sent.append((cmd, input, cwd))
            out = {"type": "result", "subtype": subtype, "is_error": subtype != "success", "result": result,
                   "total_cost_usd": 0.0123, "usage": {"input_tokens": 100, "output_tokens": 20,
                                                       "cache_read_input_tokens": 900},
                   "modelUsage": {m: {} for m in models}}
            return NS(returncode=code, stdout=_json.dumps(out), stderr="")
        return run

    def test_command_stdin_and_label(self):
        sent = []
        before = ai_news.spend()
        text, name = ai_news._chat_claude("ROLE", "DATA", 30, True, run=self._run(sent=sent))
        self.assertEqual((text, name), ("hi", "claude/claude-haiku-5-5"))
        cmd, stdin, cwd = sent[0]
        self.assertEqual(cmd[:4], ["claude", "-p", "--model", "claude-haiku-5-5"])   # full id, not an alias
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")
        self.assertIn("--no-session-persistence", cmd)
        self.assertEqual(cmd[cmd.index("--system-prompt") + 1], ai_news.CACHE_SYSTEM)
        self.assertTrue(stdin.startswith("DATA") and stdin.endswith("ROLE"))       # prompt via stdin, not argv
        self.assertIsNotNone(cwd)
        after = ai_news.spend()
        self.assertEqual(after["total_usd"], before["total_usd"])                  # plan: nothing billed per call
        self.assertAlmostEqual(after["notional_usd"] - before["notional_usd"], 0.0123)
        self.assertEqual(after["tokens_in"] - before["tokens_in"], 1000)

    def test_other_model_is_flagged_and_errors_give_no_text(self):
        self.assertIn("SERVED: claude-x", ai_news._chat_claude("s", "u", 30, False, run=self._run(models=("claude-x",)))[1])
        self.assertEqual(ai_news._chat_claude("s", "u", 30, False, run=self._run(code=1)), ("", "claude exit 1"))
        self.assertEqual(ai_news._chat_claude("s", "u", 30, False, run=self._run(subtype="error_during_execution"))[0], "")

    def test_ready_needs_token_and_cli_and_has_no_fallback(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "t"}), \
                mock.patch.object(ai_news.shutil, "which", return_value="/x/claude"):
            self.assertTrue(ai_news.claude_ready())
            self.assertIn("claude-haiku-5-5", ai_news.providers())
            self.assertNotIn(ai_news.MODEL, ai_news.providers())          # one Claude scorer, one label
            with mock.patch.object(ai_news, "custom_available", return_value=True):
                # Claude fails -> empty answer, never a silent DeepSeek answer under the v4.18 tag
                self.assertEqual(ai_news.chat("s", "u", run=self._run(code=2))[0], "")
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "t"}), \
                mock.patch.object(ai_news.shutil, "which", return_value=None):
            self.assertFalse(ai_news.claude_ready())
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_OAUTH_TOKEN"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ai_news.shutil, "which", return_value="/x/claude"):
            self.assertFalse(ai_news.claude_ready())

    def test_headline_scores_parse(self):
        run = self._run(result='[{"id": "1", "score": 0.5, "confidence": 0.8, "category": "earnings"}]')
        self.assertIn("1", ai_news.score_claude([{"id": "1", "title": "X beats", "symbols": ["X"]}], run=run))


class FallbackReason(unittest.TestCase):
    def test_provider_failure_stays_visible_behind_the_openrouter_error(self):
        import os
        from unittest import mock

        def fake_urlopen(req, timeout=0):
            raise RuntimeError("boom")
        with mock.patch.dict(os.environ, {"TRADELAB_LLM_API_KEY": "k", "OPENROUTER_API_KEY": "k"}), \
                mock.patch.object(ai_news, "CUSTOM_MODEL", "m1"), \
                mock.patch.object(ai_news, "claude_ready", return_value=False), \
                mock.patch.object(ai_news, "opencode_available", return_value=False), \
                mock.patch.object(ai_news, "_chat_custom", return_value=("", "custom provider error: HTTPError 400")):
            text, reason = ai_news.chat("s", "u", urlopen=fake_urlopen, model=ai_news.DECISION_MODEL)
        self.assertEqual(text, "")
        self.assertTrue(reason.startswith("custom provider error: HTTPError 400; then openrouter error"), reason)
