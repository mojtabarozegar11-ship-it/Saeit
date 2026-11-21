"""Do not let the unreleased Starter30 0048 migration bypass live restore gates.

All tests are local, read-only and run against the real checked-out source.
The integrity exception is limited to exact-byte offline selftest.
"""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from scripts.mojprop_schema_preflight_c83 import (
    _SOURCE_ONLY_UNRELEASED, _source_only_git_blob_matches,
    check_schema_closure,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "core/migrations/0048_mojprop_starter30_order.py"


class Starter30UnreleasedMigrationGuardTests(unittest.TestCase):
    def test_01_reviewed_source_only_audit_passes(self):
        result = check_schema_closure(ROOT, ROOT, source_only_selftest=True)
        self.assertFalse(result["manual_deploy_authorized"])
        self.assertFalse(result["live_db_restored"])
        self.assertEqual(result["source_chain"][-1], "0047_mpw_guest_email_recovery")

    def test_02_live_preflight_still_rejects_unreleased_0048(self):
        with self.assertRaisesRegex(RuntimeError, "unreviewed staged core migration"):
            check_schema_closure(ROOT, ROOT)

    def test_03_selftest_must_use_one_real_repository(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError, "identical repository"):
                check_schema_closure(ROOT, Path(d), source_only_selftest=True)

    def test_04_pinned_git_blob_checks_bytes(self):
        expected = _SOURCE_ONLY_UNRELEASED[MIGRATION.stem]
        self.assertTrue(_source_only_git_blob_matches(MIGRATION, expected))
        with tempfile.TemporaryDirectory() as d:
            changed = Path(d) / MIGRATION.name
            changed.write_bytes(MIGRATION.read_bytes() + b"\n# unreviewed schema change\n")
            self.assertFalse(_source_only_git_blob_matches(changed, expected))

    def test_05_unreviewed_digest_fails_even_in_selftest(self):
        with patch.dict(_SOURCE_ONLY_UNRELEASED, {MIGRATION.stem: "0" * 40}):
            with self.assertRaisesRegex(RuntimeError, "unreviewed later"):
                check_schema_closure(ROOT, ROOT, source_only_selftest=True)

    def test_06_nonboolean_selftest_override_fails(self):
        with self.assertRaisesRegex(RuntimeError, "invalid source-only gate"):
            check_schema_closure(ROOT, ROOT, source_only_selftest="true")

    def test_07_release_installer_has_no_override(self):
        source = (ROOT / "scripts/deploy_mojplaywin_moj_prop_backend.py").read_text()
        self.assertIn("check_schema_closure(ROOT, staged_root)", source)
        self.assertIn("check_schema_closure(repo_root, repo_root, source_only_selftest=True)", source)
        self.assertEqual(source.count("source_only_selftest=True"), 1)


if __name__ == "__main__":
    unittest.main()
