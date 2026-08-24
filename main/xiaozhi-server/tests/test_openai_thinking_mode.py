import unittest
from unittest.mock import patch

from core.providers.llm.openai.openai import LLMProvider


class OpenAIThinkingModeTest(unittest.TestCase):
    def test_deepseek_realtime_requests_disable_thinking(self):
        provider = LLMProvider.__new__(LLMProvider)
        provider.base_url = "https://api.deepseek.com"
        request_params = {}

        with patch("core.providers.llm.openai.openai.logger"):
            provider._apply_thinking_disabled(request_params)

        self.assertEqual(
            request_params["extra_body"],
            {"thinking": {"type": "disabled"}},
        )

    def test_unknown_openai_compatible_domain_is_unchanged(self):
        provider = LLMProvider.__new__(LLMProvider)
        provider.base_url = "https://example.invalid/v1"
        request_params = {}

        with patch("core.providers.llm.openai.openai.logger"):
            provider._apply_thinking_disabled(request_params)

        self.assertNotIn("extra_body", request_params)


if __name__ == "__main__":
    unittest.main()
