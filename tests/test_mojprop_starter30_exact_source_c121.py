"""C121 Starter30 offline source byte identity vs unsafe staging (no host)."""
from pathlib import Path
from unittest.mock import patch
import os
import tempfile
import unittest

from scripts import mojprop_starter30_static_release as rel

SOURCE = Path(__file__).resolve().parents[1] / "templates/moj-prop-v4/starter-30-trx"
COMMIT = "a" * 40


class Starter30ReviewedExactBytesC121Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.docroot = self.home / "mojplaywin.com"
        (self.docroot / "moj-prop").mkdir(parents=True)
        self.target = self.docroot / "moj-prop/starter-30-trx"
        self.stage = self.home / ".mojprop-starter30-stage-123" / "templates/moj-prop-v4/starter-30-trx"
        self.stage.mkdir(parents=True)
        for name in rel.FILES:
            (self.stage / name).write_bytes((SOURCE / name).read_bytes())
        patches = [
            patch.object(rel, "HOME", self.home),
            patch.object(rel, "ROOT", self.docroot),
            patch.object(rel, "TARGET", self.target),
            patch.object(rel, "BACKUP", self.home / "private-manifest"),
            patch.object(rel, "_host"),
        ]
        for tool in patches:
            tool.start()
            self.addCleanup(tool.stop)

    def test_01_all_three_reviewed_assets_are_exact_and_publish_only_no_payment(self):
        report = rel.preflight("123", COMMIT)
        self.assertEqual(report["scope"], "static-no-payment-no-backend")
        self.assertEqual(set(report["reviewed_source_blobs"]), set(rel.FILES))
        for name in rel.FILES:
            body = (SOURCE / name).read_bytes()
            self.assertEqual(rel.exact_git_blob(body), rel.REVIEWED_GIT_BLOBS[name])
            self.assertEqual(report["reviewed_source_blobs"][name],
                             rel.REVIEWED_GIT_BLOBS[name])
        self.assertFalse(self.target.exists())

    def test_02_benign_html_comment_append_cannot_bypass_byte_identity(self):
        item = self.stage / "index.html"
        item.write_bytes(item.read_bytes() + b"\n<!-- harmless-looking replacement -->")
        with self.assertRaisesRegex(RuntimeError, "do not match reviewed Git source"):
            rel.preflight("123", COMMIT)
        self.assertFalse(self.target.exists())

    def test_03_guide_small_text_change_cannot_fake_reviewed_content(self):
        item = self.stage / "journal-guide.txt"
        item.write_bytes(item.read_bytes().replace(b"ten-session", b"nine-session", 1))
        with self.assertRaisesRegex(RuntimeError, "do not match reviewed Git source"):
            rel.preflight("123", COMMIT)

    def test_04_sku_csv_header_valid_but_rows_tampered_denied(self):
        item = self.stage / "journal-template.csv"
        item.write_bytes(item.read_bytes().replace(b"1,,,", b"1,100.00,,", 1))
        with self.assertRaisesRegex(RuntimeError, "do not match reviewed Git source"):
            rel.preflight("123", COMMIT)

    def test_05_staged_symlink_file_never_followed(self):
        file = self.stage / "index.html"
        real = self.stage / "other.html"
        file.rename(real)
        file.symlink_to(real)
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)
        self.assertTrue(real.exists())

    def test_06_staged_hardlinked_file_denied(self):
        real = self.stage / "index.html"
        alias = self.stage / "another-hardlink"
        os.link(real, alias)
        with self.assertRaisesRegex(RuntimeError, "unsafe staged reviewed SKU asset"):
            rel.preflight("123", COMMIT)

    def test_07_staged_file_group_writable_denied(self):
        file = self.stage / "index.html"
        file.chmod(0o664)
        with self.assertRaisesRegex(RuntimeError, "unsafe staged reviewed SKU asset"):
            rel.preflight("123", COMMIT)

    def test_08_stage_directory_ancestor_redirect_denied(self):
        first = self.home / ".mojprop-starter30-stage-123"
        real = self.home / "other-stage"
        first.rename(real)
        first.symlink_to(real, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)

    def test_09_missing_staged_asset_fails_closed_without_backup_creation(self):
        (self.stage / "journal-guide.txt").unlink()
        with self.assertRaises(RuntimeError):
            rel.preflight("123", COMMIT)
        self.assertFalse((self.home / "private-manifest").exists())

    def test_10_unexpected_extra_reviewed_asset_pin_map_refused(self):
        altered = dict(rel.REVIEWED_GIT_BLOBS)
        altered["secret.html"] = "0" * 40
        with patch.object(rel, "REVIEWED_GIT_BLOBS", altered):
            with self.assertRaisesRegex(RuntimeError, "unreviewed static SKU"):
                rel.preflight("123", COMMIT)

    def test_11_invalid_git_blob_input_denied_before_hash(self):
        for bad in (None, "html", bytearray(b"abc"), b"x" * (rel.MAX_STAGE_FILE_BYTES + 1)):
            with self.subTest(value=type(bad).__name__):
                with self.assertRaises(RuntimeError):
                    rel.exact_git_blob(bad)

    def test_12_wrong_commit_cannot_write_before_source_is_checked(self):
        file = self.stage / "index.html"
        file.write_bytes(b"<html>Payment not enabled</html>")
        with patch.dict(os.environ, {"MOJPROP_STARTER30_OWNER_APPROVED": ""}):
            with self.assertRaises(RuntimeError):
                rel.preflight("123", COMMIT)
        self.assertFalse(self.target.exists())
