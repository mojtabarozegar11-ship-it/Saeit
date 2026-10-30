"""PICM single-owner binding inode checks; synthetic filesystem only."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from core.picm_access import owner_id


class PICMOwnerBindingInodeTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.binding = self.root / ".owner-user-id"

    def test_regular_owner_id_accepts_ascii_and_optional_newline(self):
        for value in (b"42", b"42\n", b"123456789012345678\n"):
            with self.subTest(value=value):
                self.binding.write_bytes(value)
                self.assertEqual(owner_id(self.root), value.decode("ascii").strip())

    def test_missing_invalid_and_oversized_bindings_fail_closed(self):
        self.assertIsNone(owner_id(self.root))
        for value in (b"0\n", b"01", b"42\n\n", b"42 \n", b"9" * 19,
                      b"\xff", b"42\x00", b"4" * 100):
            with self.subTest(value=value):
                self.binding.write_bytes(value)
                self.assertIsNone(owner_id(self.root))

    def test_symlink_and_hardlink_cannot_supply_owner_identity(self):
        actual = self.root / "private"
        actual.write_bytes(b"42\n")
        self.binding.symlink_to(actual)
        self.assertIsNone(owner_id(self.root))
        self.binding.unlink()
        os.link(actual, self.binding)
        self.assertIsNone(owner_id(self.root))

    def test_fifo_binding_is_rejected_without_waiting_for_writer(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO unavailable")
        os.mkfifo(self.binding)
        self.assertIsNone(owner_id(self.root))

    def test_directory_binding_is_not_accepted(self):
        self.binding.mkdir()
        self.assertIsNone(owner_id(self.root))
