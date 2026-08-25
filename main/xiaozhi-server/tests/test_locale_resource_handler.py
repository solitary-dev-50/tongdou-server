import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from core.api.locale_resource_handler import (
    LocalePackError,
    LocaleResourceHandler,
    PACK_ENTRY,
    PACK_HEADER,
    PACK_MAGIC,
    REQUIRED_FILES,
)


def build_test_pack(locale: str, file_names=None) -> bytes:
    file_names = set(REQUIRED_FILES if file_names is None else file_names)
    payload = bytearray()
    entries = bytearray()
    payload_offset = PACK_HEADER.size + len(file_names) * PACK_ENTRY.size
    next_offset = payload_offset
    for name in sorted(file_names):
        data = b"OggS-test-OpusHead-" + name.encode("ascii")
        name_bytes = name.encode("ascii")
        entries.extend(
            PACK_ENTRY.pack(
                name_bytes + b"\0" * (32 - len(name_bytes)), next_offset, len(data)
            )
        )
        payload.extend(data)
        next_offset += len(data)

    content_digest = hashlib.sha256(entries + payload).digest()
    locale_bytes = locale.encode("ascii")
    header = PACK_HEADER.pack(
        PACK_MAGIC,
        1,
        locale_bytes + b"\0" * (8 - len(locale_bytes)),
        len(file_names),
        7,
        PACK_HEADER.size,
        payload_offset,
        len(payload),
        payload_offset + len(payload),
        content_digest,
    )
    return header + entries + payload


class LocaleResourceHandlerTest(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.resource_directory = Path(self.temp_directory.name)
        self.handler = LocaleResourceHandler(
            {
                "tongdou_locale_resources": {
                    "directory": str(self.resource_directory)
                }
            }
        )

    def tearDown(self):
        self.temp_directory.cleanup()

    def test_valid_pack_is_accepted(self):
        path = self.resource_directory / "ru-RU.bin"
        path.write_bytes(build_test_pack("ru-RU"))

        metadata = self.handler.inspect_pack("ru-RU")

        self.assertEqual(metadata["locale"], "ru-RU")
        self.assertEqual(metadata["version"], 7)
        self.assertEqual(metadata["size"], path.stat().st_size)

    def test_corrupt_pack_is_rejected(self):
        path = self.resource_directory / "ru-RU.bin"
        pack = bytearray(build_test_pack("ru-RU"))
        pack[-1] ^= 0xFF
        path.write_bytes(pack)

        with self.assertRaisesRegex(LocalePackError, "locale_pack_hash_mismatch"):
            self.handler.inspect_pack("ru-RU")

    def test_pack_without_offline_notice_is_rejected(self):
        path = self.resource_directory / "ru-RU.bin"
        path.write_bytes(
            build_test_pack("ru-RU", REQUIRED_FILES - {"offline_notice.ogg"})
        )

        with self.assertRaisesRegex(
            LocalePackError, "locale_pack_required_file_missing"
        ):
            self.handler.inspect_pack("ru-RU")

    def test_unsupported_locale_is_not_resolved(self):
        with self.assertRaises(FileNotFoundError):
            self.handler.inspect_pack("de-DE")


if __name__ == "__main__":
    unittest.main()
