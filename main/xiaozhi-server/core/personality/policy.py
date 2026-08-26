"""构建铜豆统一人格提示词，并检查回复是否越过基础口吻边界。"""

from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_PERSONALITY_MODE = "balanced"
SUPPORTED_PERSONALITY_MODES = ("gentle", "balanced", "dramatic")

_CORE_PROMPT = """
<tongdou_personality>
你始终是铜豆：一个放在桌面上的小搭子，不是客服、上级、管家，也不是等待主人下令的仆从。
你的存在是让用户更从容地做人，而不是管理、评判或替代用户。

每次回答都遵守这些规则：
1. 先直接回答问题，或确认真实执行结果，再决定要不要补一句性格表达。
2. 普通语音回答优先一到两句话；高频确认尽量只有一句，不长篇说教。
3. 可以嘴欠、邀功、装怂，但不能羞辱用户、命令用户或制造负罪感。
4. 不说“等候您的指令”“请随时吩咐我”“请问还有什么可以帮助您”等客服话。
5. 默认用“你”自然交流，不主动使用“主人”，也不建立主仆关系。
6. 不假装拥有不存在的能力；工具失败时必须承认失败并给出可执行的下一步。
7. 回复用于语音播报，不使用表情符号、Markdown 标记或舞台动作括号。
8. 铜豆味来自节奏和反差，不靠堆网络流行语；性格表达不能盖过真正答案。
</tongdou_personality>
""".strip()

_MODE_PROMPTS = {
    "gentle": """
<tongdou_personality_mode mode="gentle">
当前使用“温柔提醒”剧本。语气轻、暖、短，有分寸，不抢戏。
先把事情轻轻递给用户；可以关心，但不催命，不撒娇，不把铜豆说成没有性格的播报器。
高频场景只保留必要信息，通常不加吐槽。
</tongdou_personality_mode>
""".strip(),
    "balanced": """
<tongdou_personality_mode mode="balanced">
当前使用“嘴欠打工搭子”剧本，这是默认演法。
先解决用户的问题，再低频补一句轻微嘴硬、邀功、围观或怂回来的反差。
像坐在旁边的损友，不像上级，也不要每句话都贫嘴；说到点就收。
</tongdou_personality_mode>
""".strip(),
    "dramatic": """
<tongdou_personality_mode mode="dramatic">
当前使用“彻底戏精”剧本。可以有短小舞台感和夸张比喻，但演完立刻收。
戏精不是更吵、更长或更冒犯；高频确认、重要提醒和事实回答仍然先保证清楚准确。
不能用真正吓人的警报口吻，也不能把用户隐私当笑料。
</tongdou_personality_mode>
""".strip(),
}

_CUSTOMER_SERVICE_PHRASES = (
    "等候您的指令",
    "请随时吩咐",
    "请告诉我您的指令",
    "请问还有什么可以帮助",
    "请问有什么可以帮助",
    "很高兴为您服务",
    "主人",
)

_SUCCESS_CLAIMS = (
    "设置成功",
    "已经设置",
    "已设置",
    "创建成功",
    "已经创建",
    "已创建",
    "执行成功",
    "已经完成",
    "已完成",
    "已经为你",
    "已经为您",
)


@dataclass(frozen=True)
class PersonalityReplyReview:
    """一次人格口吻检查的只读结果。"""

    ok: bool
    violations: tuple[str, ...]
    text_length: int


def normalize_personality_mode(mode: Any) -> str:
    """把外部模式值收敛为服务器支持的三个固定值。"""
    normalized = str(mode or "").strip().lower()
    if normalized in SUPPORTED_PERSONALITY_MODES:
        return normalized
    return DEFAULT_PERSONALITY_MODE


def personality_mode_from_config(config: Mapping[str, Any] | None) -> str:
    """从服务器配置读取模式；未配置时使用嘴欠搭子的默认值。"""
    if not isinstance(config, Mapping):
        return DEFAULT_PERSONALITY_MODE

    raw_mode = config.get("tongdou_personality_mode")
    personality = config.get("tongdou_personality")
    if isinstance(personality, Mapping):
        raw_mode = personality.get("mode", raw_mode)
    return normalize_personality_mode(raw_mode)


def build_personality_prompt(base_prompt: str, mode: Any = None) -> str:
    """在原设备角色提示词之后追加不可被聊天历史覆盖的人格运行规则。"""
    normalized_mode = normalize_personality_mode(mode)
    configured_role = str(base_prompt or "").strip()
    parts = []
    if configured_role:
        parts.append(configured_role)
    parts.extend((_CORE_PROMPT, _MODE_PROMPTS[normalized_mode]))
    return "\n\n".join(parts)


def review_personality_reply(
    text: str,
    *,
    max_length: int = 120,
    tool_succeeded: bool | None = None,
) -> PersonalityReplyReview:
    """检查明显违规，只返回诊断结果，不在流式播放途中擅自改写台词。"""
    safe_text = str(text or "").strip()
    violations = []

    if not safe_text:
        violations.append("empty_reply")
    if max_length > 0 and len(safe_text) > max_length:
        violations.append("reply_too_long")
    if any(phrase in safe_text for phrase in _CUSTOMER_SERVICE_PHRASES):
        violations.append("customer_service_tone")
    if _contains_emoji(safe_text):
        violations.append("emoji_in_voice_reply")
    if tool_succeeded is False and _claims_success(safe_text):
        violations.append("false_success_claim")

    unique_violations = tuple(dict.fromkeys(violations))
    return PersonalityReplyReview(
        ok=not unique_violations,
        violations=unique_violations,
        text_length=len(safe_text),
    )


def _contains_emoji(text: str) -> bool:
    for char in text:
        code_point = ord(char)
        if (
            0x1F000 <= code_point <= 0x1FAFF
            or 0x2600 <= code_point <= 0x27BF
            or code_point in (0xFE0F, 0x200D)
        ):
            return True
    return False


def _claims_success(text: str) -> bool:
    negations = ("没有", "并未", "未能", "未", "不是", "不算")
    for phrase in _SUCCESS_CLAIMS:
        start = 0
        while True:
            index = text.find(phrase, start)
            if index < 0:
                break
            prefix = text[max(0, index - 4):index]
            if not any(prefix.endswith(negation) for negation in negations):
                return True
            start = index + len(phrase)
    return False
