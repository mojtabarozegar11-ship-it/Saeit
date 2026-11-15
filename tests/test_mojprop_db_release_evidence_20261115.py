"""A missing/forged DB snapshot must never authorize a live Moj Prop migration."""
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

from scripts.mojprop_db_release_evidence import (
    MissingDatabaseRestoreEvidence, verify_database_restore_evidence,
)

RUN = "202611150001"
COMMIT = "a" * 40
IDENTITY = "b" * 64
SECRET = b"this-is-only-a-local-test-secret-no-live-releases"
NOW = datetime(2026, 11, 15, 17, tzinfo=timezone.utc)


class RestoreEvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root / RUN
        self.case.mkdir(mode=0o700)
        self.sql = self.case / "full-database.sql.gz"
        with gzip.open(self.sql, "wb") as stream:
            stream.write(b"create table previous_live_data(x int);\n" * 180)
        self.sql.chmod(0o600)
        self.proof = self.case / "isolated-restore-evidence.json"
        self.data = {
            "run_id": RUN,
            "source_commit": COMMIT,
            "snapshot_sha256": hashlib.sha256(self.sql.read_bytes()).hexdigest(),
            "database_identity_sha256": IDENTITY,
            "restore_target": "mojprop_restore_nonprod_001",
            "restored_at": (NOW - timedelta(minutes=10)).isoformat(),
            "schema_check": True,
            "row_check": True,
        }
        self.write_proof()

    def write_proof(self):
        canonical = json.dumps(
            self.data, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        ).encode("ascii")
        mac = hmac.new(SECRET, canonical, hashlib.sha256).hexdigest()
        self.proof.write_text(json.dumps({**self.data, "mac": mac}), "utf-8")
        self.proof.chmod(0o600)

    def check(self, **kwargs):
        defaults = {
            "root": self.root,
            "run_id": RUN,
            "source_commit": COMMIT,
            "database_identity_sha256": IDENTITY,
            "verifier_key": SECRET,
            "now": NOW,
        }
        defaults.update(kwargs)
        return verify_database_restore_evidence(**defaults)

    def test_valid_private_snapshot_requires_verified_restore_receipt(self):
        result = self.check()
        self.assertTrue(result["rehearsal_receipt_verified"])
        self.assertEqual(result["snapshot_sha256"], self.data["snapshot_sha256"])
        self.assertNotIn("mac", result)
        self.assertNotIn("verifier_key", result)

    def test_snapshot_deleted_or_truncated_cannot_authorize(self):
        self.sql.unlink()
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()
        self.sql.write_bytes(b"short")
        self.sql.chmod(0o600)
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()

    def test_snapshot_tampering_fails_even_if_metadata_unmodified(self):
        with self.sql.open("ab") as file:
            file.write(b"\x00TAMPERED")
        with self.assertRaisesRegex(MissingDatabaseRestoreEvidence, "backup or independent"):
            self.check()

    def test_wrong_run_commit_or_database_is_denied(self):
        for change in (
            {"run_id": "123"},
            {"source_commit": "d" * 40},
            {"database_identity_sha256": "c" * 64},
        ):
            with self.subTest(change=change), self.assertRaises(MissingDatabaseRestoreEvidence):
                self.check(**change)

    def test_independent_reviewer_signature_is_mandatory(self):
        for secret in (b"", b"short", b"other-independent-key-different-from-original"):
            with self.subTest(secret=secret), self.assertRaises(MissingDatabaseRestoreEvidence):
                self.check(verifier_key=secret)

    def test_missing_or_forged_rehearsal_cannot_pass(self):
        self.proof.unlink()
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()
        self.write_proof()
        obj = json.loads(self.proof.read_text("utf-8"))
        obj["row_check"] = False
        self.proof.write_text(json.dumps(obj), "utf-8")
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()

    def test_no_future_or_expired_rehearsal(self):
        for when in (NOW + timedelta(seconds=1), NOW - timedelta(hours=25)):
            with self.subTest(when=when):
                self.data["restored_at"] = when.isoformat()
                self.write_proof()
                with self.assertRaises(MissingDatabaseRestoreEvidence):
                    self.check()

    def test_backup_or_receipt_must_not_be_world_readable(self):
        self.proof.chmod(0o644)
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()
        self.proof.chmod(0o600)
        self.sql.chmod(0o644)
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()

    def test_restore_target_cannot_be_live_database(self):
        self.data["restore_target"] = "production"
        self.write_proof()
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()

    def test_symlink_artifacts_cannot_be_used(self):
        self.proof.unlink()
        self.proof.symlink_to(self.sql)
        with self.assertRaises(MissingDatabaseRestoreEvidence):
            self.check()


if __name__ == "__main__":
    unittest.main()
