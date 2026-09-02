import unittest
from types import SimpleNamespace

from core.personality.policy import (
    DEFAULT_PERSONALITY_MODE,
    PersonalityVoiceStream,
    build_personality_turn_prompt,
    build_personality_prompt,
    normalize_personality_mode,
    personality_flair_cooldown_turns,
    personality_flair_decision,
    personality_mode_from_config,
    review_personality_reply,
    sanitize_personality_voice_text,
    should_allow_personality_flair,
)
from core.utils.dialogue import Dialogue, Message
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

    def test_turn_style_can_force_a_normal_non_playful_reply(self):
        prompt = build_personality_turn_prompt("balanced", False)
        self.assertIn('flair_allowed="false"', prompt)
        self.assertIn("禁止吐槽、自恋、财迷、夸张", prompt)
        self.assertIn("回答完成立即停", prompt)

    def test_personality_flair_uses_mode_specific_cooldown(self):
        self.assertEqual(personality_flair_cooldown_turns("gentle"), 3)
        self.assertEqual(personality_flair_cooldown_turns("balanced"), 2)
        self.assertEqual(personality_flair_cooldown_turns("dramatic"), 1)

    def test_brief_acknowledgement_never_forces_personality_flair(self):
        self.assertFalse(should_allow_personality_flair("不用了。", 0))
        self.assertTrue(should_allow_personality_flair("你是谁？", 0))
        self.assertFalse(should_allow_personality_flair("你吃饭了吗？", 2))
        self.assertTrue(should_allow_personality_flair("讲个笑话", 2))

    def test_user_playful_comparison_bypasses_cooldown(self):
        cases = (
            "那你觉得是你的头大还是我的头大？",
            "我脸圆还是你脸圆？",
            "我和你谁更聪明？",
            "铜豆，你敢不敢跟我比一下？",
        )
        for query in cases:
            with self.subTest(query=query):
                allowed, reason = personality_flair_decision(query, 2)
                self.assertTrue(allowed)
                self.assertEqual(reason, "user_playful_banter")

    def test_normal_questions_do_not_bypass_active_cooldown(self):
        cases = (
            "你的音量是多少？",
            "你是不是已经设置好提醒了？",
            "今天吃米饭还是吃面？",
        )
        for query in cases:
            with self.subTest(query=query):
                allowed, reason = personality_flair_decision(query, 2)
                self.assertFalse(allowed)
                self.assertEqual(reason, "cooldown_active")

    def test_explicit_joke_request_has_a_distinct_reason(self):
        allowed, reason = personality_flair_decision("我开玩笑的", 2)
        self.assertTrue(allowed)
        self.assertEqual(reason, "user_requested_playfulness")

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

    def test_meaningful_long_reply_is_not_rejected_by_one_size_limit(self):
        text = "这句话有点长。" * 30
        review = review_personality_reply(text, max_length=20)
        self.assertTrue(review.ok)
        self.assertNotIn("reply_too_long", review.violations)
        self.assertEqual(review.text_length, len(text))

    def test_voice_cleanup_removes_chat_format_and_generic_closing(self):
        cleaned = sanitize_personality_voice_text(
            "好嘞，那就保持这样。有事再喊我~"
        )
        self.assertEqual(cleaned, "好嘞，那就保持这样。")

    def test_voice_cleanup_removes_emoji_without_changing_answer(self):
        cleaned = sanitize_personality_voice_text("😏 现在音量是百分之百。")
        self.assertEqual(cleaned, "现在音量是百分之百。")

    def test_stream_cleanup_handles_fragmented_generic_closing(self):
        stream = PersonalityVoiceStream()
        emitted = []
        emitted.extend(stream.feed("好嘞，那就保持这样。"))
        emitted.extend(stream.feed("有事再"))
        emitted.extend(stream.feed("喊我~", final=True))

        self.assertEqual(emitted, ["好嘞，", "那就保持这样。"])
        self.assertEqual(stream.spoken_text, "好嘞，那就保持这样。")

    def test_stream_cleanup_keeps_comma_first_packet_latency(self):
        stream = PersonalityVoiceStream()
        emitted = stream.feed("先说结论，后面再解释")

        self.assertEqual(emitted, ("先说结论，",))


class DialogueRuntimeInstructionTest(unittest.TestCase):
    def test_runtime_instruction_is_sent_but_not_saved_as_history(self):
        dialogue = Dialogue()
        dialogue.put(Message(role="system", content="基础规则"))
        dialogue.put(Message(role="user", content="你是谁？"))

        messages = dialogue.get_llm_dialogue_with_memory(
            runtime_instruction="本轮正常回答"
        )

        self.assertEqual(messages[0], {"role": "system", "content": "基础规则"})
        self.assertEqual(
            messages[1],
            {"role": "system", "content": "本轮正常回答"},
        )
        self.assertEqual(messages[2], {"role": "user", "content": "你是谁？"})
        self.assertEqual(len(dialogue.dialogue), 2)


if __name__ == "__main__":
    unittest.main()
