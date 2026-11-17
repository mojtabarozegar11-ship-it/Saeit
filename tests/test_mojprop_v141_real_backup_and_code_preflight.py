"""Regression checks for read-only private MojPlayWin release diagnostics.

These do not contact live VPS or cPanel. Real site observation is a separate
fingerprint-pinned GitHub Actions job; no test here implies backup readiness.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest

from scripts import mojprop_v141_offhost_pair_metadata_readonly as backup
from scripts import mojprop_v141_live_code_presence_readonly as live


NOW = datetime(2026, 11, 17, 20, 0, tzinfo=timezone.utc).timestamp()
STEM = "mojplaywin_20261117T180000Z_aabbccddeeff0011"


class BackupInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / backup.BACKUP_SUBDIR
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o700)

    def write_private(self, name, data=b"ciphertext"):
        target = self.root / name
        target.write_bytes(data)
        target.chmod(0o600)
        os.utime(target, (NOW-3600, NOW-3600))
        return target

    def pair(self, *, stem=STEM, manifest_mutation=None, missing=None):
        files = []
        for kind in ("mysql", "files"):
            archive = f"{stem}_{kind}_gpgv2.gpg"
            manifest = f"{stem}_{kind}_gpgv2.manifest.json"
            obj = {
                "format": "OpenPGP-AES256-GPGv2", "kind": kind,
                "backup_set_stem": stem,
                "explicit_backup_set_id": True,
                "source_completion_footer_verified": True,
                "ciphertext_roundtrip_integrity_verified": True,
                "release_permitted": False,
                "archive_name": archive,
                "encrypted_bytes": len(b"ciphertext"),
                "plaintext_bytes": 4000,
                "plaintext_sha256": "a" * 64,
            }
            if manifest_mutation:
                manifest_mutation(obj, kind)
            if archive != missing:
                files.append(self.write_private(archive))
            if manifest != missing:
                files.append(self.write_private(manifest, json.dumps(obj).encode()))
        return files

    def inspect(self):
        return backup.inspect(self.home, uid=os.getuid(), now=NOW)

    def test_01_missing_directory_is_not_a_backup(self):
        self.root.rmdir()
        data = self.inspect()
        self.assertFalse(data["private_backup_directory_verified"])
        self.assertFalse(data["isolated_restore_verified"])

    def test_02_private_empty_directory_is_not_a_restorable_backup(self):
        data = self.inspect()
        self.assertTrue(data["private_backup_directory_verified"])
        self.assertTrue(data["inventory_complete"])
        self.assertEqual(data["complete_pair_with_consistent_manifest_count"], 0)

    def test_03_publicly_readable_backup_directory_rejected(self):
        self.root.chmod(0o755)
        self.assertFalse(self.inspect()["private_backup_directory_verified"])

    def test_04_symlink_backup_directory_rejected(self):
        self.root.rmdir()
        other = self.home / "external"
        other.mkdir()
        self.root.symlink_to(other, target_is_directory=True)
        self.assertFalse(self.inspect()["private_backup_directory_verified"])

    def test_05_orphan_encrypted_mysql_cannot_be_a_pair(self):
        self.write_private(f"{STEM}_mysql_gpgv2.gpg")
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_06_matching_manifest_pair_is_metadata_candidate_only(self):
        self.pair()
        observed = self.inspect()
        self.assertEqual(observed["regular_file_count"], 4)
        self.assertEqual(observed["candidate_backup_set_count"], 1)
        self.assertEqual(observed["complete_pair_with_consistent_manifest_count"], 1)
        self.assertEqual(observed["fresh_pair_metadata_count"], 1)
        self.assertFalse(observed["isolated_restore_verified"])
        self.assertFalse(observed["paid_release_authorized"])

    def test_07_old_pair_metadata_does_not_count_as_fresh(self):
        files = self.pair()
        for target in files:
            os.utime(target, (NOW-10*86400, NOW-10*86400))
        self.assertEqual(self.inspect()["fresh_pair_metadata_count"], 0)

    def test_08_false_source_completion_footer_is_rejected(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(
            source_completion_footer_verified=False))
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_09_wrong_ciphertext_length_is_rejected(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(encrypted_bytes=9))
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_10_missing_files_archive_is_rejected(self):
        self.pair(missing=f"{STEM}_files_gpgv2.gpg")
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_11_symlink_ciphertext_is_rejected_without_following(self):
        self.pair()
        target = self.root / f"{STEM}_mysql_gpgv2.gpg"
        target.unlink()
        outside = self.home / "external.gpg"
        outside.write_bytes(b"ciphertext")
        target.symlink_to(outside)
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_12_group_readable_ciphertext_is_rejected(self):
        self.pair()
        target = self.root / f"{STEM}_mysql_gpgv2.gpg"
        target.chmod(0o640)
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"], 0)

    def test_13_manifest_with_secret_style_unknown_field_not_emitted(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(
            arbitrary_private_value="NEVER_ECHO_THIS_SECRET"))
        text = json.dumps(self.inspect())
        self.assertNotIn("NEVER_ECHO_THIS_SECRET",text)

    def test_14_recovery_key_and_backup_contents_never_validated_by_stat(self):
        self.pair()
        x = self.inspect()
        self.assertFalse(x["recovery_key_bytes_read"])
        self.assertFalse(x["ciphertext_bytes_read"])
        self.assertFalse(x["ciphertext_authenticated_independently"])

    def test_15_partial_file_is_reported_but_not_counted_as_pair(self):
        self.write_private(f"{STEM}_mysql_gpgv2.gpg.partial")
        x = self.inspect()
        self.assertEqual(x["partial_file_count"],1)
        self.assertEqual(x["complete_pair_with_consistent_manifest_count"],0)

    def test_16_invalid_plaintext_length_rejected(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(plaintext_bytes=50*1024**3))
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"],0)

    def test_17_invalid_manifest_fingerprint_rejected(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(plaintext_sha256="not-a-sha"))
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"],0)

    def test_18_owner_approval_flag_must_not_be_true(self):
        self.pair(manifest_mutation=lambda obj,kind: obj.update(release_permitted=True))
        self.assertEqual(self.inspect()["complete_pair_with_consistent_manifest_count"],0)


class CandidateSourceInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        self.app=self.home/"Saeit-staging"
        self.site=self.home/"mojplaywin.com"
        self.app.mkdir(mode=0o700);self.site.mkdir(mode=0o700)
        self.app.chmod(0o700);self.site.chmod(0o700)

    def test_19_missing_code_never_claims_live_route(self):
        x=live.inspect(self.home,uid=os.getuid())
        self.assertFalse(x["all_expected_files_present"])
        self.assertFalse(x["effective_passenger_code_mapping_verified"])

    def test_20_current_source_fingerprints_only_known_small_files(self):
        for key,path in live.CANDIDATE.items():
            p=self.app/path
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text("known-source",encoding="utf-8")
            p.chmod(0o600)
        (self.site/"passenger_wsgi.py").write_text("candidate",encoding="utf-8")
        x=live.inspect(self.home,uid=os.getuid())
        self.assertTrue(x["all_expected_files_present"])
        self.assertTrue(x["candidate_passenger_entry_regular"])
        self.assertTrue(all(n==hashlib.sha256(b"known-source").hexdigest()
                            for n in x["candidate_code_sha256"].values()))
        self.assertFalse(x["live_http_route_verified"])
        self.assertFalse(x["production_schema_verified"])

    def test_21_symlink_source_not_followed(self):
        p=self.app/live.CANDIDATE["private_html_view"]
        p.parent.mkdir(parents=True)
        external=self.home/"outside"
        external.write_text("SECRET-CONTENT")
        p.symlink_to(external)
        self.assertIsNone(live.inspect(self.home,uid=os.getuid())["candidate_code_sha256"]["private_html_view"])

    def test_22_world_writable_parent_is_not_trusted(self):
        p=self.app/live.CANDIDATE["private_html_view"]
        p.parent.mkdir(parents=True)
        p.write_text("hello",encoding="utf-8")
        p.parent.chmod(0o777)
        self.assertIsNone(live.inspect(self.home,uid=os.getuid())["candidate_code_sha256"]["private_html_view"])

    def test_23_file_over_512k_is_not_hashed(self):
        p=self.app/live.CANDIDATE["private_html_view"]
        p.parent.mkdir(parents=True)
        p.write_bytes(b"X"*(live.MAX_CODE_FILE_BYTES+1))
        self.assertIsNone(live.inspect(self.home,uid=os.getuid())["candidate_code_sha256"]["private_html_view"])

    def test_24_all_checks_always_refuse_release_without_verification(self):
        self.assertFalse(live.inspect(self.home,uid=os.getuid())["release_permitted"])
        self.assertFalse(backup.inspect(self.home,uid=os.getuid())["paid_release_authorized"])

if __name__ == "__main__":
    unittest.main()
