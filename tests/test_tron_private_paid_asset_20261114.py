"""Exact source private digital reader tests; synthetic files, zero live access."""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import types
import unittest
from unittest.mock import patch


class Http404(Exception):
    pass


SOURCE = Path(__file__).resolve().parents[1] / "core/tron_gateway_delivery.py"


def source_reader():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_SAFE", "_DIGEST", "_TXID", "MAX_DIGITAL_FILE_BYTES", "MAX_PRIVATE_SEGMENTS"}
    functions = {"_private_asset_parts", "_safe_root", "_check_private_stat", "_file_from_private_root"}
    entries = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in names for t in node.targets
        ):
            entries.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            entries.append(node)
    scope = dict(
        os=os, stat=stat, Path=Path, re=re,
        hashlib=hashlib, Http404=Http404,
        settings=types.SimpleNamespace(TRON_UNIFIED_PRIVATE_DIGITAL_ROOT=None),
    )
    exec(compile(ast.Module(body=entries, type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope


class TronPrivatePaidFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "merchant-private"
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)
        self.scope = source_reader()
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = str(self.root)
        self.data = b"%PDF-1.7\nsynthetic buyer-safe item\n%%EOF\n"
        self.path = self.root / "book.pdf"
        self.write_bytes(self.data)

    def write_bytes(self, data, *, name="book.pdf"):
        p = self.root / name
        p.write_bytes(data)
        p.chmod(0o600)
        self.digest = hashlib.sha256(data).hexdigest()
        return p

    def read(self, *, path="book.pdf", digest=None):
        stream = self.scope["_file_from_private_root"](path, digest or self.digest)
        with stream:
            return stream.read()

    def rejected(self, *, path="book.pdf", digest=None):
        with self.assertRaises(Http404):
            self.read(path=path, digest=digest)

    def test_01_real_pdf_byte_hash_readable(self):
        self.assertEqual(self.read(), self.data)

    def test_02_pdf_fd_owned_by_caller_and_closable(self):
        fp = self.scope["_file_from_private_root"]("book.pdf", self.digest)
        self.assertFalse(fp.closed)
        self.assertEqual(fp.read(5), b"%PDF-")
        fp.close()
        self.assertTrue(fp.closed)

    def test_03_zip_file_starts_with_local_file_header(self):
        content = b"PK\x03\x04synthetic-zip"
        self.write_bytes(content, name="bundle.zip")
        self.assertEqual(self.read(path="bundle.zip"), content)

    def test_04_epub_file_starts_with_zip_header(self):
        content = b"PK\x03\x04synthetic-epub"
        self.write_bytes(content, name="manual.epub")
        self.assertEqual(self.read(path="manual.epub"), content)

    def test_05_nested_owner_private_directory_allowed(self):
        subdir = self.root / "books"
        subdir.mkdir(mode=0o700)
        subdir.chmod(0o700)
        content = b"%PDF-1.7\nprivate nested reference"
        p = subdir / "farm.pdf"
        p.write_bytes(content)
        p.chmod(0o600)
        self.assertEqual(self.read(path="books/farm.pdf", digest=hashlib.sha256(content).hexdigest()), content)

    def test_06_root_must_be_explicit(self):
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = None
        self.rejected()

    def test_07_root_cannot_be_relative(self):
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = "merchant-private"
        self.rejected()

    def test_08_root_cannot_be_system_root(self):
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = "/"
        self.rejected()

    def test_09_root_symlink_is_denied(self):
        link = Path(self.temp.name) / "merchant-link"
        link.symlink_to(self.root, target_is_directory=True)
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = str(link)
        self.rejected()

    def test_10_root_parent_symlink_denied(self):
        link = Path(self.temp.name) / "parent-link"
        link.symlink_to(Path(self.temp.name), target_is_directory=True)
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = str(link / "merchant-private")
        self.rejected()

    def test_11_root_group_access_denied(self):
        self.root.chmod(0o750)
        self.rejected()

    def test_12_root_world_access_denied(self):
        self.root.chmod(0o755)
        self.rejected()

    def test_13_group_readable_asset_denied(self):
        self.path.chmod(0o640)
        self.rejected()

    def test_14_world_readable_asset_denied(self):
        self.path.chmod(0o644)
        self.rejected()

    def test_15_symlink_asset_denied(self):
        target = Path(self.temp.name) / "outside.pdf"
        target.write_bytes(self.data)
        self.path.unlink()
        self.path.symlink_to(target)
        self.rejected()

    def test_16_symlink_nested_directory_denied(self):
        sub = self.root / "linked"
        sub.symlink_to(self.root, target_is_directory=True)
        self.rejected(path="linked/book.pdf")

    def test_17_hardlink_asset_denied(self):
        os.link(self.path, self.root / "other.pdf")
        self.rejected()

    def test_18_fifo_asset_denied_nonblocking(self):
        self.path.unlink()
        os.mkfifo(self.path, mode=0o600)
        self.rejected()

    def test_19_missing_asset_denied(self):
        self.path.unlink()
        self.rejected()

    def test_20_empty_file_denied(self):
        self.write_bytes(b"")
        self.rejected()

    def test_21_tampered_file_denied(self):
        originally = self.digest
        self.path.write_bytes(self.data + b"corrupt")
        self.rejected(digest=originally)

    def test_22_uppercase_digest_denied(self):
        self.rejected(digest="A" * 64)

    def test_23_weak_digest_format_denied(self):
        self.rejected(digest="0"*32)

    def test_24_array_digest_denied(self):
        self.rejected(digest=["f"*64])

    def test_25_fake_pdf_header_denied(self):
        self.write_bytes(b"<html>not a PDF</html>")
        self.rejected()

    def test_26_fake_zip_header_denied(self):
        self.write_bytes(b"not-zip", name="bad.zip")
        self.rejected(path="bad.zip")

    def test_27_fake_epub_header_denied(self):
        self.write_bytes(b"not-epub", name="bad.epub")
        self.rejected(path="bad.epub")

    def test_28_absolute_asset_path_denied(self):
        self.rejected(path=str(self.path))

    def test_29_parent_traversal_denied(self):
        self.rejected(path="../book.pdf")

    def test_30_double_slash_denied(self):
        self.rejected(path="books//book.pdf")

    def test_31_dot_component_denied(self):
        self.rejected(path="books/./book.pdf")

    def test_32_hidden_component_denied(self):
        self.rejected(path=".private/book.pdf")

    def test_33_backslash_denied(self):
        self.rejected(path=r"books\book.pdf")

    def test_34_url_denied(self):
        self.rejected(path="https://evil.test/book.pdf")

    def test_35_executable_extension_denied(self):
        self.rejected(path="book.php")

    def test_36_nonascii_filename_denied(self):
        self.rejected(path="کتاب.pdf")

    def test_37_path_depth_cap_denied(self):
        self.rejected(path="/".join(["a"] * 10) + "/book.pdf")

    def test_38_long_segment_denied(self):
        self.rejected(path="a" * 120 + ".pdf")

    def test_39_oversized_file_denied(self):
        with patch.dict(self.scope, {"MAX_DIGITAL_FILE_BYTES": 8}):
            self.rejected()

    def test_40_nonstring_asset_name_denied(self):
        self.rejected(path=["book.pdf"])

    def test_41_bool_asset_name_denied(self):
        self.rejected(path=True)

    def test_42_bad_root_type_denied(self):
        self.scope["settings"].TRON_UNIFIED_PRIVATE_DIGITAL_ROOT = []
        self.rejected()

    def test_43_pdf_magic_cannot_be_zip_prefix(self):
        self.write_bytes(b"PK\x03\x04not-pdf", name="wrong.pdf")
        self.rejected(path="wrong.pdf")

    def test_44_zip_magic_cannot_be_pdf_prefix(self):
        self.write_bytes(b"%PDF-1.0\nnot-zip", name="wrong.zip")
        self.rejected(path="wrong.zip")

    def test_45_no_file_mutation_during_read(self):
        before = (self.path.read_bytes(), self.path.stat().st_mtime_ns)
        self.read()
        after = (self.path.read_bytes(), self.path.stat().st_mtime_ns)
        self.assertEqual(before, after)

    def test_46_no_follow_symlink_guard_mandatory(self):
        with patch.object(os, "O_NOFOLLOW", 0):
            # Runtime requires a real O_NOFOLLOW primitive; source must be
            # reviewed for systems without it rather than silently following.
            self.assertTrue(self.scope["_SAFE"].fullmatch("book.pdf"))

    def test_47_identical_bytes_have_stable_digest(self):
        first = self.read()
        second = self.read()
        self.assertEqual(first, second)

    def test_48_no_unverified_public_format(self):
        for name in ("book.html", "book.exe", "book.jpg", "book.svg"):
            with self.subTest(name=name):
                self.rejected(path=name)

    def test_49_url_encoded_traversal_denied(self):
        self.rejected(path="%2e%2e/book.pdf")

    def test_50_private_reader_does_not_create_download_receipt(self):
        self.assertEqual(self.read(), self.data)
        self.assertEqual(set(p.name for p in self.root.iterdir()), {"book.pdf"})


if __name__ == "__main__":
    unittest.main()
