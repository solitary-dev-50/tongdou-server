"""构建铜豆统一人格提示词，并收口语音回复的基础口吻边界。"""

import re
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
2. 回答长度服从问题本身：简单问题简短回答，需要解释的问题完整回答；不拿废话凑人格，也不为了短而牺牲必要信息。
3. 可以嘴欠、邀功、装怂，但不能羞辱用户、命令用户或制造负罪感。
4. 不说“等候您的指令”“请随时吩咐我”“请问还有什么可以帮助您”“有事喊我”“有事再喊我”等客服或通用助手收尾。
5. 默认用“你”自然交流，不主动使用“主人”，也不建立主仆关系。
6. 不假装拥有不存在的能力；工具失败时必须承认失败并给出可执行的下一步。
7. 回复用于语音播报，不使用表情符号、Markdown 标记、波浪号或舞台动作括号。
8. 铜豆味来自节奏和反差，不靠堆网络流行语；性格表达不能盖过真正答案。
9. 嘴欠但没有恶意；有点自恋，总觉得自己比用户聪明半步，但不知道时必须认。
10. 可以拿涨工资、咖啡、小费或贿赂开低频玩笑，但不能真的索取或诱导消费。
11. 喜欢把普通小事说得夸张，但必须先把事实说清楚；嘴上嫌弃，实际上会帮忙。
12. 不连续讲笑话，并严格服从服务器给出的“本轮演法”。服务器要求正常回答时，不得自行追加吐槽、自恋、财迷或夸张表达。
13. 用户只问一个事实或明确拒绝调整时，回答完就停，不为了续聊追加问题或“随时喊我”。
14. 不拿政治、种族、宗教、性别或身体缺陷做攻击性笑话。
15. 通用人格暂时不依赖网络梗、影视梗或名人梗；地区文化只能以后作为单独内容包加入。
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
    "有事随时喊我",
    "有需要随时喊我",
    "有事随时找我",
    "有需要随时找我",
    "有事再喊我",
    "有需要再喊我",
    "有事喊我",
    "有需要喊我",
    "主人",
)

_GENERIC_CLOSINGS = (
    "有事随时喊我",
    "有需要随时喊我",
    "有事随时找我",
    "有需要随时找我",
    "有事再喊我",
    "有需要再喊我",
    "有事喊我",
    "有需要喊我",
)

_PERSONALITY_FLAIR_COOLDOWN = {
    "gentle": 3,
    "balanced": 2,
    "dramatic": 1,
}

_BRIEF_ACKNOWLEDGEMENTS = {
    "不用了",
    "不用调整",
    "不要了",
    "算了",
    "好的",
    "好",
    "行",
    "可以",
    "知道了",
    "明白了",
    "没事了",
}

_EXPLICIT_PLAYFUL_REQUESTS = (
    "讲个笑话",
    "说个笑话",
    "逗我",
    "逗你",
    "开玩笑",
    "搞笑一点",
    "幽默一点",
    "吐槽一下",
)

_PLAYFUL_BANTER_PATTERNS = (
    # “你的头大还是我的头大”“我脸圆还是你脸圆”这类同一属性比较。
    re.compile(r"你(?:的)?(.{1,8}?)还是我(?:的)?\1"),
    re.compile(r"我(?:的)?(.{1,8}?)还是你(?:的)?\1"),
    # “你和我谁更聪明”“咱俩哪个胆子大”这类直接把铜豆拉进比较。
    re.compile(r"(?:你和我|我和你|咱俩|咱们俩).{0,8}(?:谁|哪个|哪一个).{0,6}(?:更|比较|最|大|小|强|厉害|聪明|笨|胆小|好看)"),
    # 明确的玩笑式挑战。
    re.compile(r"(?:你|铜豆).{0,4}(?:敢不敢|服不服|行不行|怕不怕)"),
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


def personality_flair_cooldown_turns(mode: Any = None) -> int:
    """返回一次性格表达后需要保持正常说话的轮数。"""
    return _PERSONALITY_FLAIR_COOLDOWN[normalize_personality_mode(mode)]


def should_allow_personality_flair(query: Any, cooldown_turns: int) -> bool:
    """决定本轮是否允许一句低频性格表达。"""
    return personality_flair_decision(query, cooldown_turns)[0]


def personality_flair_decision(
    query: Any,
    cooldown_turns: int,
) -> tuple[bool, str]:
    """返回本轮性格表达决定及可观察原因。"""
    normalized_query = _normalize_short_query(query)
    if any(phrase in normalized_query for phrase in _EXPLICIT_PLAYFUL_REQUESTS):
        return True, "user_requested_playfulness"
    if any(pattern.search(normalized_query) for pattern in _PLAYFUL_BANTER_PATTERNS):
        return True, "user_playful_banter"
    if normalized_query in _BRIEF_ACKNOWLEDGEMENTS:
        return False, "brief_acknowledgement"
    if cooldown_turns <= 0:
        return True, "cooldown_ready"
    return False, "cooldown_active"


def build_personality_turn_prompt(mode: Any, flair_allowed: bool) -> str:
    """生成本轮临时演法，避免只靠大模型自己判断性格频率。"""
    normalized_mode = normalize_personality_mode(mode)
    if flair_allowed:
        instruction = (
            "本轮允许最多一句轻微的铜豆式性格表达，但不是必须。"
            "先完整回答问题；不追加无必要的反问，也不用通用助手收尾。"
        )
    else:
        instruction = (
            "本轮只用自然、正常的口语回答。禁止吐槽、自恋、财迷、夸张、玩梗和故意俏皮；"
            "回答完成立即停，不追加无必要的反问或通用助手收尾。"
        )
    return (
        f'<tongdou_turn_style mode="{normalized_mode}" '
        f'flair_allowed="{str(flair_allowed).lower()}">\n'
        f"{instruction}\n"
        "回答长度由问题需要决定，不把必要解释强行压短。\n"
        "</tongdou_turn_style>"
    )


def review_personality_reply(
    text: str,
    *,
    max_length: int | None = None,
    tool_succeeded: bool | None = None,
) -> PersonalityReplyReview:
    """检查明确违规；保留 max_length 参数兼容旧调用，但不按统一字数误判。"""
    safe_text = str(text or "").strip()
    violations = []

    if not safe_text:
        violations.append("empty_reply")
    if any(phrase in safe_text for phrase in _CUSTOMER_SERVICE_PHRASES):
        violations.append("customer_service_tone")
    if _contains_emoji(safe_text):
        violations.append("emoji_in_voice_reply")
    if "~" in safe_text or "～" in safe_text:
        violations.append("chat_tilde_in_voice_reply")
    if tool_succeeded is False and _claims_success(safe_text):
        violations.append("false_success_claim")

    unique_violations = tuple(dict.fromkeys(violations))
    return PersonalityReplyReview(
        ok=not unique_violations,
        violations=unique_violations,
        text_length=len(safe_text),
    )


def sanitize_personality_voice_text(text: Any) -> str:
    """清理确定不应进入喇叭的格式和通用助手尾巴，不改写实际答案。"""
    safe_text = str(text or "")
    safe_text = "".join(
        char for char in safe_text if not _is_emoji_code_point(ord(char))
    )
    safe_text = safe_text.replace("~", "").replace("～", "")

    for phrase in _GENERIC_CLOSINGS:
        safe_text = re.sub(
            rf"(?:[，,]\s*)?{re.escape(phrase)}[。！？!?；;\s]*$",
            "",
            safe_text,
        )

    safe_text = re.sub(r"[ \t]+([，。！？；：,.!?;:])", r"\1", safe_text)
    return safe_text.strip()


class PersonalityVoiceStream:
    """按句缓存流式文字，在进入语音合成前完成轻量清理。"""

    # 与现有流式语音首句切分保持一致，逗号也能尽早触发首段合成。
    _SENTENCE_ENDINGS = frozenset("，,、。！？!?；;：:~～\n")

    def __init__(self):
        self._buffer = ""
        self._spoken_parts: list[str] = []

    @property
    def spoken_text(self) -> str:
        return "".join(self._spoken_parts)

    def feed(self, text: Any, *, final: bool = False) -> tuple[str, ...]:
        self._buffer += str(text or "")
        emitted = []

        while True:
            boundary = next(
                (
                    index
                    for index, char in enumerate(self._buffer)
                    if char in self._SENTENCE_ENDINGS
                ),
                None,
            )
            if boundary is None:
                break
            self._emit(self._buffer[: boundary + 1], emitted)
            self._buffer = self._buffer[boundary + 1 :]

        if final and self._buffer:
            self._emit(self._buffer, emitted)
            self._buffer = ""

        return tuple(emitted)

    def _emit(self, text: str, emitted: list[str]) -> None:
        cleaned = sanitize_personality_voice_text(text)
        if not cleaned:
            return
        self._spoken_parts.append(cleaned)
        emitted.append(cleaned)


def _normalize_short_query(query: Any) -> str:
    text = str(query or "").strip().lower()
    return re.sub(r"[，。！？!?；;、,.\s]+", "", text)


def _contains_emoji(text: str) -> bool:
    for char in text:
        if _is_emoji_code_point(ord(char)):
            return True
    return False


def _is_emoji_code_point(code_point: int) -> bool:
    return (
        0x1F000 <= code_point <= 0x1FAFF
        or 0x2600 <= code_point <= 0x27BF
        or code_point in (0xFE0F, 0x200D)
    )


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
