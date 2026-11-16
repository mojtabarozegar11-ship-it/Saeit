"""Offline negative-path contract for the D-only full recovery evidence gate."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import gzip
import hashlib
import hmac
import json
import os
import tempfile
import unittest

from scripts.mojprop_plan1_full_restore_review_d import (
    FILES, SCHEMA, FullRestoreEvidenceDenied, verify_full_restore_review
)

RUN_ID = "43977436859"
SHA = "7e3b67693bffecf8113f54c1f548b2e97c6efc9d"
KEY = b"d-only-independent-reviewer-test-key-40bytes!"


class TestFullRecoveryReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mojprop-d-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.case = self.root / RUN_ID
        self.case.mkdir(mode=0o700)
        self.now = datetime(2026, 11, 17, 2, 0, tzinfo=timezone.utc)
        self.backups = {}
        for kind, name in FILES.items():
            path = self.case / name
            path.write_bytes(gzip.compress(os.urandom(2048)))
            path.chmod(0o600)
            payload = path.read_bytes()
            self.backups[kind] = {
                "name": name, "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload)
            }
        self.receipt = {
            "schema": SCHEMA, "run_id": RUN_ID, "source_commit": SHA,
            "domain": "mojplaywin.com", "offsite_backup": True,
            "backup_operator": "backup_operator_1", "restore_reviewer": "independent_reviewer_2",
            "backups": self.backups,
            "restore": {
                "target": "mojprop_iso_independent01",
                "completed_at": self.now.isoformat(),
                "completed": True,
                "db_schema_verified": True, "db_rows_verified": True,
                "app_boot_verified": True, "media_files_verified": True,
                "tenant_isolation_verified": True, "production_modified": False
            }
        }
        self.write_receipt()

    def write_receipt(self, sign=True):
        content = dict(self.receipt)
        if sign:
            base = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            content["mac"] = hmac.new(KEY, base, hashlib.sha256).hexdigest()
        else:
            content["mac"] = "0" * 64
        file = self.case / "full-restore-review.json"
        file.write_text(json.dumps(content), encoding="utf-8")
        file.chmod(0o600)

    def check(self, **kwargs):
        args = dict(root=self.root, run_id=RUN_ID, source_commit=SHA,
                    reviewer_key=KEY, now=self.now)
        args.update(kwargs)
        return verify_full_restore_review(**args)

    def denied(self):
        with self.assertRaises(FullRestoreEvidenceDenied):
            self.check()

    def flip(self, field, value):
        self.receipt[field] = value
        self.write_receipt()
        self.denied()

    def restore_flip(self, field, value):
        self.receipt["restore"][field] = value
        self.write_receipt()
        self.denied()

    def test_valid_receipt_is_not_release_authority(self):
        result = self.check()
        self.assertTrue(result["all_three_backup_bytes_verified"])
        self.assertTrue(result["independent_reviewer_signature_verified"])
        self.assertFalse(result["remote_restore_independently_observed_by_this_process"])
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["payment_authorized"])

    def test_missing_database(self):
        (self.case / FILES["db"]).unlink()
        self.denied()

    def test_missing_application(self):
        (self.case / FILES["app"]).unlink()
        self.denied()

    def test_missing_media(self):
        (self.case / FILES["media"]).unlink()
        self.denied()

    def test_corrupted_backup_digest(self):
        with (self.case / FILES["db"]).open("ab") as f:
            f.write(b"altered")
        self.denied()

    def test_wrong_bytes_in_signed_manifest(self):
        self.backups["app"]["bytes"] += 1
        self.write_receipt()
        self.denied()

    def test_boolean_size_not_integer(self):
        self.backups["media"]["bytes"] = True
        self.write_receipt()
        self.denied()

    def test_forged_digest(self):
        self.backups["db"]["sha256"] = "f" * 64
        self.write_receipt()
        self.denied()

    def test_file_without_gzip_magic(self):
        path = self.case / FILES["app"]
        path.write_bytes(b"not-gzip" * 400)
        self.backups["app"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.backups["app"]["bytes"] = path.stat().st_size
        self.write_receipt()
        self.denied()

    def test_backup_symlink_rejected(self):
        path = self.case / FILES["media"]
        original = self.case / "separate-media"
        path.rename(original)
        path.symlink_to(original)
        self.denied()

    def test_hardlink_rejected(self):
        os.link(self.case / FILES["db"], self.case / "extra-hardlink")
        self.denied()

    def test_world_readable_backup_rejected(self):
        (self.case / FILES["db"]).chmod(0o644)
        self.denied()

    def test_world_readable_receipt_rejected(self):
        (self.case / "full-restore-review.json").chmod(0o644)
        self.denied()

    def test_group_readable_case_rejected(self):
        self.case.chmod(0o750)
        self.denied()

    def test_group_readable_root_rejected(self):
        self.root.chmod(0o750)
        self.denied()

    def test_wrong_run_id_rejected(self):
        with self.assertRaises(FullRestoreEvidenceDenied):
            self.check(run_id="43977436860")

    def test_wrong_sha_rejected(self):
        with self.assertRaises(FullRestoreEvidenceDenied):
            self.check(source_commit="0" * 40)

    def test_short_key_rejected(self):
        with self.assertRaises(FullRestoreEvidenceDenied):
            self.check(reviewer_key=b"short")

    def test_altered_signed_receipt_rejected(self):
        content = json.loads((self.case / "full-restore-review.json").read_text())
        content["offsite_backup"] = False
        (self.case / "full-restore-review.json").write_text(json.dumps(content))
        self.denied()

    def test_wrong_domain_rejected(self):
        self.flip("domain", "zomorodmelal.ir")

    def test_offsite_not_confirmed_rejected(self):
        self.flip("offsite_backup", False)

    def test_same_backup_and_reviewer_rejected(self):
        self.flip("restore_reviewer", self.receipt["backup_operator"])

    def test_missing_independent_identity_rejected(self):
        self.flip("restore_reviewer", "")

    def test_wrong_restore_target_rejected(self):
        self.restore_flip("target", "production")

    def test_restore_not_completed_rejected(self):
        self.restore_flip("completed", False)

    def test_schema_not_checked_rejected(self):
        self.restore_flip("db_schema_verified", False)

    def test_rows_not_checked_rejected(self):
        self.restore_flip("db_rows_verified", False)

    def test_application_not_booted_rejected(self):
        self.restore_flip("app_boot_verified", False)

    def test_media_not_verified_rejected(self):
        self.restore_flip("media_files_verified", False)

    def test_tenant_not_isolated_rejected(self):
        self.restore_flip("tenant_isolation_verified", False)

    def test_production_modified_rejected(self):
        self.restore_flip("production_modified", True)

    def test_restore_receipt_expired_rejected(self):
        self.restore_flip("completed_at", (self.now-timedelta(hours=25)).isoformat())

    def test_future_receipt_rejected(self):
        self.restore_flip("completed_at", (self.now+timedelta(seconds=1)).isoformat())

    def test_naive_time_rejected(self):
        self.restore_flip("completed_at", "2026-11-17T02:00:00")

    def test_wrong_schema_rejected(self):
        self.flip("schema", "starter30")

    def test_extra_manifest_field_rejected(self):
        self.receipt["payment_enabled"] = True
        self.write_receipt()
        self.denied()

    def test_missing_manifest_field_rejected(self):
        del self.receipt["backup_operator"]
        self.write_receipt()
        self.denied()

    def test_missing_backup_entry_rejected(self):
        del self.backups["media"]
        self.write_receipt()
        self.denied()

    def test_unknown_backup_entry_rejected(self):
        self.backups["other"] = self.backups["db"].copy()
        self.write_receipt()
        self.denied()

    def test_wrong_backup_name_rejected(self):
        self.backups["db"]["name"] = "unrelated.sql.gz"
        self.write_receipt()
        self.denied()

    def test_missing_receipt_rejected(self):
        (self.case / "full-restore-review.json").unlink()
        self.denied()

    def test_signing_key_mismatch_rejected(self):
        with self.assertRaises(FullRestoreEvidenceDenied):
            self.check(reviewer_key=b"different-independent-reviewer-test-key!")


if __name__ == "__main__":
    unittest.main()
