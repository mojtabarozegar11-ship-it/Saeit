"""Isolated, read-only private asset path policy checks.

No real payment accounts, payouts or network operations are involved.
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from mpw_commerce.downloads import _private_file


class PrivateAssetPathTests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "catalog").mkdir()
        self.pdf = self.root / "catalog" / "sample.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nDemo private asset\n")

    def item(self, relative_path):
        return SimpleNamespace(
            product=SimpleNamespace(
                metadata={"mpw_commerce":{"private_file":relative_path}}
            )
        )

    def test_regular_private_document_can_be_resolved(self):
        with override_settings(MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root)):
            self.assertEqual(
                _private_file(self.item("catalog/sample.pdf")),
                self.pdf,
            )

    def test_path_escape_and_nonexistent_files_fail_closed(self):
        with override_settings(MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root)):
            for name in ("../outside.pdf", "../../secrets.env",
                         "/etc/passwd", "catalog/absent.pdf"):
                with self.subTest(name=name):
                    with self.assertRaises((FileNotFoundError, ValueError)):
                        _private_file(self.item(name))

    def test_linked_files_cannot_escape_private_directory(self):
        alias=self.root / "catalog" / "alias.pdf"
        alias.symlink_to(self.pdf)
        with override_settings(MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root)):
            with self.assertRaises(FileNotFoundError):
                _private_file(self.item("catalog/alias.pdf"))

    def test_unlisted_content_type_is_never_exposed(self):
        secret=self.root / "catalog" / "private.env"
        secret.write_text("demo")
        with override_settings(MPW_COMMERCE_PRIVATE_ASSET_ROOT=str(self.root)):
            with self.assertRaises(FileNotFoundError):
                _private_file(self.item("catalog/private.env"))

    def test_missing_private_root_blocks_all_downloads(self):
        with override_settings(MPW_COMMERCE_PRIVATE_ASSET_ROOT=""):
            with self.assertRaises(FileNotFoundError):
                _private_file(self.item("catalog/sample.pdf"))
