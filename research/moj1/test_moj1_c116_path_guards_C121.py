#!/usr/bin/env python3
"""Offline regression tests for R-01 MOJ1 C116 input path guards.

Synthetic temporary files only; no chain, factory, VPS, signing or deployment.
Run: python3 -m unittest research/moj1/test_moj1_c116_path_guards_C121.py
"""
import hashlib
import importlib.util
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).with_name("moj1_c116_auditor_input_root_symlink_guard_candidate.py")
spec = importlib.util.spec_from_file_location("moj1_c116_guard", MODULE)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PathGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "checkout"
        self.root.mkdir()
        self.payload = self.root / "safe.txt"
        self.payload.write_bytes(b"offline-fixture")
        self.sha = hashlib.sha256(b"offline-fixture").hexdigest()

    def entry(self, path="safe.txt", digest=None):
        return {"path": path, "sha256": self.sha if digest is None else digest}

    def test_regular_file_with_exact_hash(self):
        self.assertEqual(guard.checked_file(self.root, self.entry()), "safe.txt")

    def test_mismatched_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            guard.checked_file(self.root, self.entry(digest="0" * 64))

    def test_path_traversal_fails_closed(self):
        with self.assertRaises(ValueError):
            guard.checked_file(self.root, self.entry("../outside.txt"))

    def test_backslash_and_absolute_path_fail_closed(self):
        for path in ("..\\safe.txt", "/etc/passwd"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                guard.checked_file(self.root, self.entry(path))

    def test_symlink_file_fails_closed(self):
        alias = self.root / "alias.txt"
        try:
            alias.symlink_to(self.payload)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symlink"):
            guard.checked_file(self.root, self.entry("alias.txt"))

    def test_symlink_parent_fails_closed(self):
        (self.root / "folder").mkdir()
        (self.root / "folder" / "safe.txt").write_bytes(b"offline-fixture")
        alias = self.root / "linkdir"
        try:
            alias.symlink_to(self.root / "folder", target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symlink"):
            guard.checked_file(self.root, self.entry("linkdir/safe.txt"))

    def test_symlink_checkout_root_fails_closed(self):
        alias = pathlib.Path(self.tmp.name) / "checkout-link"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symlink"):
            guard.checked_root_path(alias)

    def test_symlink_ancestor_fails_closed(self):
        ancestor = pathlib.Path(self.tmp.name) / "ancestor-link"
        try:
            ancestor.symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        with self.assertRaisesRegex(ValueError, "symlink"):
            guard.checked_root_path(ancestor / "subdirectory")


if __name__ == "__main__":
    unittest.main()
