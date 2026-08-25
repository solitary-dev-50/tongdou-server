"""把提醒正文预渲染成铜豆 OLED 可直接显示的单色位图。"""

import base64
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BITMAP_WIDTH = 128
BITMAP_HEIGHT = 48
BITMAP_SIZE = BITMAP_WIDTH * BITMAP_HEIGHT // 8
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 16

_FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


class ReminderBitmapError(RuntimeError):
    """提醒正文不能可靠渲染。"""


def _contains_cjk(text: str) -> bool:
    return any(
        "\u3400" <= character <= "\u9fff"
        or "\u3040" <= character <= "\u30ff"
        or "\uac00" <= character <= "\ud7af"
        for character in text
    )


def _font_path(text: str) -> str:
    configured = os.environ.get("TONGDOU_REMINDER_FONT", "").strip()
    if configured:
        if Path(configured).is_file():
            return configured
        raise ReminderBitmapError("reminder_configured_font_missing")

    candidates = _FONT_CANDIDATES
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            if _contains_cjk(text) and "NotoSansCJK" not in Path(candidate).name:
                continue
            return candidate
    if _contains_cjk(text):
        raise ReminderBitmapError("reminder_cjk_font_missing")
    raise ReminderBitmapError("reminder_font_missing")


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    if not text:
        return 0
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def _wrap_line(draw: ImageDraw.ImageDraw, text: str, font) -> list[str]:
    remaining = text.strip()
    lines = []
    while remaining:
        end = 1
        while end <= len(remaining) and _text_width(draw, remaining[:end], font) <= BITMAP_WIDTH:
            end += 1
        end = min(len(remaining), max(1, end - 1))
        if end < len(remaining):
            space = remaining.rfind(" ", 0, end + 1)
            if space >= max(1, end // 2):
                end = space
        line = remaining[:end].rstrip()
        if not line:
            line = remaining[:1]
            end = 1
        lines.append(line)
        remaining = remaining[end:].lstrip()
    return lines


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font) -> list[str]:
    lines = []
    for paragraph in text.splitlines() or [text]:
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(_wrap_line(draw, paragraph, font))
    return lines


def _fit_layout(draw: ImageDraw.ImageDraw, text: str, font_path: str):
    for font_size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -1):
        font = ImageFont.truetype(font_path, font_size)
        top, bottom = font.getbbox("铜Ag")[1], font.getbbox("铜Ag")[3]
        line_height = max(1, bottom - top + 1)
        lines = _wrap_text(draw, text, font)
        if lines and len(lines) * line_height <= BITMAP_HEIGHT:
            return font, lines, line_height
    raise ReminderBitmapError("reminder_text_does_not_fit")


def _to_ssd1306_pages(image: Image.Image) -> bytes:
    result = bytearray(BITMAP_SIZE)
    for page in range(BITMAP_HEIGHT // 8):
        for x in range(BITMAP_WIDTH):
            value = 0
            for bit in range(8):
                if image.getpixel((x, page * 8 + bit)):
                    value |= 1 << bit
            result[page * BITMAP_WIDTH + x] = value
    return bytes(result)


def render_reminder_bitmap(text: str) -> bytes:
    clean_text = " ".join(str(text).strip().split())
    if not clean_text:
        raise ReminderBitmapError("reminder_text_empty")

    image = Image.new("1", (BITMAP_WIDTH, BITMAP_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    font, lines, line_height = _fit_layout(draw, clean_text, _font_path(clean_text))
    y = max(0, (BITMAP_HEIGHT - len(lines) * line_height) // 2)
    for line in lines:
        width = _text_width(draw, line, font)
        x = max(0, (BITMAP_WIDTH - width) // 2)
        draw.text((x, y), line, font=font, fill=1)
        y += line_height

    bitmap = _to_ssd1306_pages(image)
    if len(bitmap) != BITMAP_SIZE or not any(bitmap):
        raise ReminderBitmapError("reminder_bitmap_empty")
    return bitmap


def render_reminder_bitmap_base64(text: str) -> str:
    return base64.b64encode(render_reminder_bitmap(text)).decode("ascii")
