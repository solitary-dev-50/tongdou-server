import unittest
from types import SimpleNamespace

from core.personality.policy import (
    DEFAULT_PERSONALITY_MODE,
    build_personality_prompt,
    normalize_personality_mode,
    personality_mode_from_config,
    review_personality_reply,
)
from core.utils.prompt_manager import PromptManager


class _Logger:
    def bind(self, **_kwargs):
        return self

    def debug(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class _Cache:
    def __init__(self):
        self.values = {}

    def get(self, cache_type, key):
        return self.values.get((cache_type, key))

    def set(self, cache_type, key, value):
        self.values[(cache_type, key)] = value


class TongDouPersonalityPromptTest(unittest.TestCase):
    def test_invalid_or_missing_mode_falls_back_to_balanced(self):
        self.assertEqual(normalize_personality_mode(None), DEFAULT_PERSONALITY_MODE)
        self.assertEqual(normalize_personality_mode("unknown"), "balanced")
        self.assertEqual(normalize_personality_mode(" DRAMATIC "), "dramatic")

    def test_nested_device_mode_has_priority(self):
        config = {
            "tongdou_personality_mode": "gentle",
            "tongdou_personality": {"mode": "dramatic"},
        }
        self.assertEqual(personality_mode_from_config(config), "dramatic")

    def test_original_device_role_is_preserved_before_runtime_rules(self):
        original = "你知道用户常用的提醒习惯。"
        prompt = build_personality_prompt(original, "balanced")
        self.assertTrue(prompt.startswith(original))
        self.assertIn("你始终是铜豆", prompt)
        self.assertIn('mode="balanced"', prompt)

    def test_three_modes_are_independent_scripts(self):
        gentle = build_personality_prompt("", "gentle")
        balanced = build_personality_prompt("", "balanced")
        dramatic = build_personality_prompt("", "dramatic")

        self.assertIn("温柔提醒", gentle)
        self.assertNotIn("嘴欠打工搭子", gentle)
        self.assertIn("嘴欠打工搭子", balanced)
        self.assertNotIn("彻底戏精", balanced)
        self.assertIn("彻底戏精", dramatic)
        self.assertNotIn("温柔提醒", dramatic)

    def test_runtime_rules_forbid_customer_service_and_fake_success(self):
        prompt = build_personality_prompt("", "balanced")
        self.assertIn("等候您的指令", prompt)
        self.assertIn("工具失败时必须承认失败", prompt)
        self.assertIn("不使用表情符号", prompt)

    def test_cross_cultural_character_is_in_every_mode(self):
        for mode in ("gentle", "balanced", "dramatic"):
            with self.subTest(mode=mode):
                prompt = build_personality_prompt("", mode)
                self.assertIn("嘴欠但没有恶意", prompt)
                self.assertIn("有点自恋", prompt)
                self.assertIn("涨工资、咖啡、小费或贿赂", prompt)
                self.assertIn("不连续讲笑话", prompt)
                self.assertIn("不知道时必须认", prompt)
                self.assertIn("政治、种族、宗教、性别或身体缺陷", prompt)
                self.assertIn("网络梗、影视梗或名人梗", prompt)

    def test_fact_answer_must_stop_without_forced_follow_up(self):
        prompt = build_personality_prompt("", "balanced")
        self.assertIn("回答完就停", prompt)
        self.assertIn("不为了续聊追加问题", prompt)

    def test_prompt_cache_is_separated_by_personality_mode(self):
        manager = PromptManager.__new__(PromptManager)
        manager.config = {"tongdou_personality_mode": "gentle"}
        manager.logger = _Logger()
        manager.cache_manager = _Cache()
        manager.CacheType = SimpleNamespace(DEVICE_PROMPT="device_prompt")

        gentle = manager.get_quick_prompt("基础角色", "device-1")
        manager.config["tongdou_personality_mode"] = "dramatic"
        dramatic = manager.get_quick_prompt("基础角色", "device-1")

        self.assertIn("温柔提醒", gentle)
        self.assertIn("彻底戏精", dramatic)
        self.assertNotEqual(gentle, dramatic)
        self.assertEqual(len(manager.cache_manager.values), 2)

    def test_enhanced_prompt_contains_runtime_personality(self):
        manager = PromptManager.__new__(PromptManager)
        manager.config = {"tongdou_personality_mode": "balanced"}
        manager.logger = _Logger()
        manager.cache_manager = _Cache()
        manager.CacheType = SimpleNamespace(DEVICE_PROMPT="device_prompt")
        manager.base_prompt_template = (
            "<identity>{{ base_prompt }}</identity>\n"
            "emoji_enabled={{ emoji_enabled }}"
        )
        manager.context_data = ""
        manager._get_current_time_info = lambda: ("2026-08-26", "星期三", "")

        prompt = manager.build_enhanced_prompt(
            "基础角色",
            "device-1",
            emoji_enabled=False,
        )

        self.assertIn("基础角色", prompt)
        self.assertIn("你始终是铜豆", prompt)
        self.assertIn("嘴欠打工搭子", prompt)
        self.assertIn("emoji_enabled=False", prompt)


class TongDouPersonalityReplyReviewTest(unittest.TestCase):
    def test_short_grounded_tongdou_reply_passes(self):
        review = review_personality_reply(
            "现在是百分之百。小喇叭已经顶到头了，别再拧我了。"
        )
        self.assertTrue(review.ok)
        self.assertEqual(review.violations, ())

    def test_customer_service_reply_is_rejected(self):
        review = review_personality_reply("我在这里，等候您的指令。")
        self.assertFalse(review.ok)
        self.assertIn("customer_service_tone", review.violations)

    def test_emoji_voice_reply_is_rejected(self):
        review = review_personality_reply("😏 到点了，别装没听见。")
        self.assertFalse(review.ok)
        self.assertIn("emoji_in_voice_reply", review.violations)

    def test_generic_assistant_closing_is_rejected(self):
        review = review_personality_reply("好，那就这样。有事随时喊我。")
        self.assertFalse(review.ok)
        self.assertIn("customer_service_tone", review.violations)

    def test_chat_tilde_is_rejected_for_voice(self):
        review = review_personality_reply("那就保持满格音量~")
        self.assertFalse(review.ok)
        self.assertIn("chat_tilde_in_voice_reply", review.violations)

    def test_failed_tool_cannot_claim_success(self):
        review = review_personality_reply(
            "提醒已经创建成功。", tool_succeeded=False
        )
        self.assertFalse(review.ok)
        self.assertIn("false_success_claim", review.violations)

    def test_truthful_tool_failure_is_not_treated_as_success(self):
        review = review_personality_reply(
            "提醒没有创建成功，网络断了。你连上网后再叫我一次。",
            tool_succeeded=False,
        )
        self.assertTrue(review.ok)

    def test_long_reply_is_reported_without_rewriting_it(self):
        text = "这句话有点长。" * 30
        review = review_personality_reply(text, max_length=20)
        self.assertFalse(review.ok)
        self.assertIn("reply_too_long", review.violations)
        self.assertEqual(review.text_length, len(text))


if __name__ == "__main__":
    unittest.main()
