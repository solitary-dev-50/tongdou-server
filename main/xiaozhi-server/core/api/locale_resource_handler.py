import hashlib
import struct
from pathlib import Path

from aiohttp import web
from config.config_loader import get_project_dir
from loguru import logger


TAG = __name__
PACK_MAGIC = b"TDLPACK1"
PACK_FORMAT_VERSION = 1
PACK_HEADER = struct.Struct("<8sH8sHIIIII32s")
PACK_ENTRY = struct.Struct("<32sII")
MAX_FILES = 32
SUPPORTED_LOCALES = {
    "en-CA",
    "en-GB",
    "en-US",
    "fr-CA",
    "fr-FR",
    "nl-NL",
    "ru-RU",
    "zh-CN",
}
REQUIRED_FILES = {
    "welcome.ogg",
    "wifi_config.ogg",
    "upgrade.ogg",
    "activation_code.ogg",
    "activation_error.ogg",
    "pin_error.ogg",
    "offline_notice.ogg",
    *(f"digit_{digit}.ogg" for digit in range(10)),
}


class LocalePackError(ValueError):
    pass


class LocaleResourceHandler:
    """只负责校验并发送铜豆单语言资源包。"""

    def __init__(self, config: dict):
        self.logger = logger
        resource_config = config.get("tongdou_locale_resources", {})
        configured_directory = resource_config.get(
            "directory", "config/assets/tongdou_locale_packs"
        )
        resource_directory = Path(configured_directory)
        if not resource_directory.is_absolute():
            resource_directory = Path(get_project_dir()) / resource_directory
        self.resource_directory = resource_directory.resolve()

    def inspect_pack(self, locale: str) -> dict:
        if locale not in SUPPORTED_LOCALES:
            raise FileNotFoundError("unsupported_locale")

        path = (self.resource_directory / f"{locale}.bin").resolve()
        if path.parent != self.resource_directory or not path.is_file():
            raise FileNotFoundError("locale_pack_missing")

        data = path.read_bytes()
        if len(data) < PACK_HEADER.size:
            raise LocalePackError("locale_pack_header_missing")

        (
            magic,
            format_version,
            locale_field,
            file_count,
            resource_version,
            directory_offset,
            payload_offset,
            payload_size,
            total_size,
            content_digest,
        ) = PACK_HEADER.unpack_from(data)

        pack_locale = locale_field.split(b"\0", 1)[0].decode("ascii", errors="strict")
        if magic != PACK_MAGIC or format_version != PACK_FORMAT_VERSION:
            raise LocalePackError("locale_pack_format_invalid")
        if pack_locale != locale:
            raise LocalePackError("locale_pack_locale_mismatch")
        if file_count == 0 or file_count > MAX_FILES:
            raise LocalePackError("locale_pack_file_count_invalid")
        if (
            directory_offset != PACK_HEADER.size
            or payload_offset != PACK_HEADER.size + file_count * PACK_ENTRY.size
            or payload_size == 0
            or total_size != payload_offset + payload_size
            or total_size != len(data)
        ):
            raise LocalePackError("locale_pack_bounds_invalid")

        names = set()
        for index in range(file_count):
            entry_offset = directory_offset + index * PACK_ENTRY.size
            name_field, file_offset, file_size = PACK_ENTRY.unpack_from(data, entry_offset)
            name = name_field.split(b"\0", 1)[0].decode("ascii", errors="strict")
            if (
                not name
                or file_size == 0
                or file_offset < payload_offset
                or file_offset > total_size
                or file_size > total_size - file_offset
            ):
                raise LocalePackError("locale_pack_entry_invalid")
            names.add(name)

        if not REQUIRED_FILES.issubset(names):
            raise LocalePackError("locale_pack_required_file_missing")

        calculated_digest = hashlib.sha256(data[directory_offset:total_size]).digest()
        if calculated_digest != content_digest:
            raise LocalePackError("locale_pack_hash_mismatch")

        return {
            "path": path,
            "locale": pack_locale,
            "version": resource_version,
            "size": total_size,
            "content_sha256": content_digest.hex(),
            "pack_sha256": hashlib.sha256(data).hexdigest(),
        }

    async def handle_get(self, request):
        locale = request.match_info.get("locale", "")
        try:
            metadata = self.inspect_pack(locale)
        except FileNotFoundError as error:
            return web.Response(status=404, text=str(error))
        except (LocalePackError, UnicodeError) as error:
            self.logger.bind(tag=TAG).error(
                f"语言资源包拒绝发送 locale={locale} error={error}"
            )
            return web.Response(status=500, text=str(error))

        response = web.FileResponse(metadata["path"])
        response.content_type = "application/octet-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["ETag"] = f'"{metadata["pack_sha256"]}"'
        response.headers["X-TongDou-Locale"] = metadata["locale"]
        response.headers["X-TongDou-Resource-Version"] = str(metadata["version"])
        response.headers["X-TongDou-Content-SHA256"] = metadata["content_sha256"]
        return response
