"""Offline-only package provenance and integrity tests."""

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.mpw_header_static_bundle import MEMBERS, build_bundle
from scripts.mpw_header_static_manifest_repair import git_blob_sha


class HeaderBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.repo = root / "repo"
        self.image = self.repo / "core/static/site/mojplaywin-header-emblem.jpg"
        self.script = self.repo / "scripts/mpw_header_static_manifest_repair.py"
        self.image.parent.mkdir(parents=True)
        self.script.parent.mkdir(parents=True)
        self.raw = b"\xff\xd8" + bytes(range(256)) * 6 + b"\xff\xd9"
        self.image.write_bytes(self.raw)
        self.script.write_bytes(b"EXPECTED_GIT_BLOB = 'x'\ndef rollback(): pass\n")
        self.blob = git_blob_sha(self.raw)
        self.output = root / "handoff.tar.gz"

    def test_package_is_allowlisted_and_matches_both_sources(self):
        result = build_bundle(self.repo, self.output, self.blob)
        self.assertEqual(result["status"], "prepared_only")
        self.assertTrue(result["manual_release_required"])
        self.assertFalse(result["production_mutated"])
        with tarfile.open(self.output, "r:gz") as archive:
            self.assertEqual(archive.getnames(), list(MEMBERS))
            self.assertEqual(archive.extractfile(MEMBERS[0]).read(), self.raw)
            self.assertEqual(archive.extractfile(MEMBERS[1]).read(), self.script.read_bytes())
            details = json.load(archive.extractfile(MEMBERS[2]))
            self.assertEqual(details["image_git_blob"], self.blob)
            self.assertEqual(details["image_sha256"], hashlib.sha256(self.raw).hexdigest())
            self.assertEqual(details["release_mode"], "manual-only")
            self.assertTrue(all(m.isfile() and not m.issym() for m in archive.getmembers()))

    def test_source_mismatch_fails_without_archive(self):
        with self.assertRaisesRegex(RuntimeError, "pinned Git source"):
            build_bundle(self.repo, self.output, "0" * 40)
        self.assertFalse(self.output.exists())

    def test_existing_archive_never_overwritten(self):
        self.output.write_bytes(b"keep existing owner archive")
        with self.assertRaisesRegex(RuntimeError, "occupied"):
            build_bundle(self.repo, self.output, self.blob)
        self.assertEqual(self.output.read_bytes(), b"keep existing owner archive")

    def test_source_symlink_refused(self):
        self.image.unlink()
        self.image.symlink_to(self.script)
        with self.assertRaisesRegex(RuntimeError, "Unsafe or missing bundle source"):
            build_bundle(self.repo, self.output, self.blob)
        self.assertFalse(self.output.exists())

    def test_missing_repair_entrypoint_refused(self):
        self.script.write_bytes(b"print('no rollback')\n")
        with self.assertRaisesRegex(RuntimeError, "incomplete"):
            build_bundle(self.repo, self.output, self.blob)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
