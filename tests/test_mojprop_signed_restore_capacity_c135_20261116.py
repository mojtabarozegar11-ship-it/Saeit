"""Offline evidence integrity tests. Never generate a real restore attestation.

The HMAC test vector is deterministic, test-only and not a production key.
Files are written only inside an isolated local temporary directory.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.mojprop_restore_capacity_admission import (
    CapacityAdmissionDenied, CapacityEvidence,
    require_signed_capacity_receipt,
)

RUN = "123456"
COMMIT = "a" * 40
DB_ID = "b" * 64
SNAP = "c" * 64
KEY = b"test-only-never-deploy-capacity-key-" * 2


class SignedCompleteRestoreCapacityEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / "independent-restore-capacity.json"
        self.evidence = CapacityEvidence(
            source_database_bytes=9_000_000_000,
            source_application_bytes=500_000_000,
            source_media_bytes=500_000_000,
            destination_free_bytes=40_000_000_000,
            destination_total_bytes=50_000_000_000,
            independent_destination=True,
            encrypted_at_rest=True,
            owner_authorized=True,
            measured_at_epoch=1_790_000_000,
            now_epoch=1_790_000_001,
            tenant_quota_free_bytes=40_000_000_000,
            tenant_quota_total_bytes=50_000_000_000,
            destination_free_inodes=500_000,
            required_restore_inodes=100_000,
            tenant_quota_free_inodes=500_000,
            tenant_quota_total_inodes=1_000_000,
        )
        self.payload = {
            "schema": "mojprop.independent.capacity.v1",
            "run_id": RUN,
            "source_commit": COMMIT,
            "database_identity_sha256": DB_ID,
            "snapshot_sha256": SNAP,
            "offhost_database_sha256": SNAP,
            "offhost_application_sha256": "d" * 64,
            "offhost_media_sha256": "e" * 64,
            "isolated_db_restore_verified": True,
            "isolated_app_restore_verified": True,
            "isolated_media_restore_verified": True,
            "capacity": {k: v for k, v in asdict(self.evidence).items()
                         if k != "now_epoch"},
        }
        self.write()

    def write(self, *, sign=True):
        p = dict(self.payload)
        p.pop("mac", None)
        if sign:
            canonical = json.dumps(
                p, sort_keys=True, ensure_ascii=True,
                separators=(",", ":"),
            ).encode("ascii")
            p["mac"] = hmac.new(KEY, canonical, hashlib.sha256).hexdigest()
        self.path.write_text(json.dumps(p, sort_keys=True), encoding="utf-8")
        os.chmod(self.path, 0o600)

    def check(self, **overrides):
        return require_signed_capacity_receipt(
            path=overrides.pop("path", self.path),
            run_id=overrides.pop("run_id", RUN),
            source_commit=overrides.pop("source_commit", COMMIT),
            database_identity_sha256=overrides.pop("database_identity_sha256", DB_ID),
            snapshot_sha256=overrides.pop("snapshot_sha256", SNAP),
            verifier_key=overrides.pop("verifier_key", KEY),
            now_epoch=overrides.pop("now_epoch", 1_790_000_001),
            **overrides,
        )

    def deny(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check()

    def test_accepts_fresh_complete_signed_statement_as_statement_only(self):
        proof = self.check()
        self.assertEqual(proof["required_restore_bytes"], 22_500_000_000)
        self.assertTrue(proof["capacity_receipt_verified"])
        self.assertFalse(proof["actual_remote_restore_independently_observed_by_this_code"])
        self.assertFalse(proof["release_authorized"])

    def test_rejects_tampered_measurement_with_old_mac(self):
        old = json.loads(self.path.read_text(encoding="utf-8"))
        old["capacity"]["tenant_quota_free_bytes"] = 1
        # Keep the legitimate HMAC: only the capacity claim is tampered.
        self.path.write_text(json.dumps(old, sort_keys=True), encoding="utf-8")
        os.chmod(self.path, 0o600)
        self.deny()

    def test_rejects_bad_hmac_even_when_inventory_is_consistent(self):
        self.write()
        raw = json.loads(self.path.read_text())
        raw["mac"] = "0" * 64
        self.path.write_text(json.dumps(raw))
        os.chmod(self.path, 0o600)
        self.deny()

    def test_rejects_wrong_owner_secret(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(verifier_key=b"another-untrusted-test-only-very-long-key")

    def test_rejects_wrong_source_commit(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(source_commit="f" * 40)

    def test_rejects_wrong_database_identity(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(database_identity_sha256="f" * 64)

    def test_rejects_wrong_database_snapshot(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(snapshot_sha256="f" * 64)

    def test_rejects_wrong_run_id(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(run_id="123457")

    def test_rejects_unsigned_statement(self):
        self.write(sign=False)
        self.deny()

    def test_rejects_missing_media_content_digest(self):
        self.payload["offhost_media_sha256"] = ""
        self.write()
        self.deny()

    def test_rejects_zero_application_digest(self):
        self.payload["offhost_application_sha256"] = "0" * 64
        self.write()
        self.deny()

    def test_rejects_non_database_snapshot_claim(self):
        self.payload["offhost_database_sha256"] = "f" * 64
        self.write()
        self.deny()

    def test_rejects_any_missing_restore_attestation(self):
        for field in ("isolated_db_restore_verified",
                      "isolated_app_restore_verified",
                      "isolated_media_restore_verified"):
            with self.subTest(field=field):
                self.payload[field] = False
                self.write()
                self.deny()
                self.payload[field] = True

    def test_rejects_stale_capacity_measurement(self):
        self.payload["capacity"]["measured_at_epoch"] = 1_789_990_000
        self.write()
        self.deny()

    def test_rejects_future_capacity_measurement(self):
        self.payload["capacity"]["measured_at_epoch"] = 1_790_000_100
        self.write()
        self.deny()

    def test_rejects_insufficient_tenant_inodes_with_valid_signature(self):
        self.payload["capacity"]["tenant_quota_free_inodes"] = 100
        self.write()
        self.deny()

    def test_rejects_insufficient_tenant_bytes_with_valid_signature(self):
        self.payload["capacity"]["tenant_quota_free_bytes"] = 5_000_000_000
        self.write()
        self.deny()

    def test_rejects_missing_quota_field(self):
        del self.payload["capacity"]["tenant_quota_total_inodes"]
        self.write()
        self.deny()

    def test_rejects_unexpected_capacity_field(self):
        self.payload["capacity"]["unapproved_bypass"] = True
        self.write()
        self.deny()

    def test_rejects_unexpected_outer_field(self):
        self.payload["manual_release_approved"] = True
        self.write()
        self.deny()

    def test_rejects_duplicate_json_keys(self):
        self.path.write_text(
            '{"run_id":"123456","run_id":"123457","mac":"' + "a"*64 + '"}'
        )
        os.chmod(self.path, 0o600)
        self.deny()

    def test_rejects_symlinked_receipt(self):
        alternative = self.root / "alternative.json"
        self.path.rename(alternative)
        self.path.symlink_to(alternative)
        self.deny()

    def test_rejects_world_readable_proof(self):
        os.chmod(self.path, 0o644)
        self.deny()

    def test_rejects_hardlinked_proof(self):
        os.link(self.path, self.root / "other-link.json")
        self.deny()

    def test_rejects_wrong_file_name(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(path=self.path.with_name("capacity-unverified.json"))

    def test_rejects_oversize_data(self):
        self.path.write_bytes(b" " * 8193)
        os.chmod(self.path, 0o600)
        self.deny()

    def test_rejects_missing_receipt(self):
        self.path.unlink()
        self.deny()

    def test_rejects_wrong_clock_type(self):
        with self.assertRaises(CapacityAdmissionDenied):
            self.check(now_epoch=True)

    def test_rejects_boolean_destination_byte_budget(self):
        self.payload["capacity"]["destination_free_bytes"] = True
        self.write()
        self.deny()


if __name__ == "__main__":
    unittest.main()
