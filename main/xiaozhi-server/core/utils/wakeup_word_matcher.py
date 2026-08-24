import unicodedata
from collections.abc import Iterable


def normalize_wakeup_word(text) -> str:
    """将显示写法统一成可稳定比较的唤醒词文本。"""
    if text is None:
        return ""

    normalized = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(
        char
        for char in normalized
        if not char.isspace()
        and not unicodedata.category(char).startswith("P")
    )


def matches_wakeup_word(text, configured_words) -> bool:
    """输入文本和配置别名使用同一套规则后再比较。"""
    normalized_text = normalize_wakeup_word(text)
    if not normalized_text or configured_words is None:
        return False

    if isinstance(configured_words, str):
        words: Iterable = configured_words.split(";")
    else:
        words = configured_words

    return any(
        normalize_wakeup_word(word) == normalized_text
        for word in words
    )
