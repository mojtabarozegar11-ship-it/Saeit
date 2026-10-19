"""Regression tests for actual SHA-attested, every-minute private Gen65 runtime."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from mpw_v91_port import gen65_runtime as rt
from mpw_v91_port.generation_factory import produce


def examples():
    return [
        {"id": "a", "kind": "research_digest", "quality": 97,
         "source_count": 3, "ready": True},
        {"id": "b", "kind": "product_blueprint", "quality": 88,
         "source_count": 1, "ready": False},
    ]


def enabled(root):
    (root / rt.CONTROL_NAME).write_text(json.dumps({
        "tenant": rt.TENANT, "active_private_generation": 65,
        "controller_sha256": rt.EXPECTED_SHA,
        "enabled": True, "scope": "private_verified_review_only"}))


class Gen65OperationalTests(unittest.TestCase):
    def test_disabled_does_not_execute_generated_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            result=rt.operate(root, examples(), 9, "2026-10-18T12:00:00Z")
            self.assertEqual(result["status"], "gen65_not_enabled")
            self.assertFalse((root / rt.REPORT_NAME).exists())

    def test_operates_new_gen65_code_and_writes_bounded_private_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            enabled(root)
            report=rt.operate(root, examples(), 10, "2026-10-18T12:01:00Z")
            self.assertEqual(report["status"], "gen65_operational_private")
            self.assertEqual(report["active_private_generation"], 65)
            self.assertEqual(report["existing_public_master_generation"], 64)
            self.assertEqual(report["ready_for_human_review"], 1)
            self.assertEqual(report["held_for_review"], 1)
            self.assertEqual(report["verified_observations"], 2)
            self.assertFalse(report["meets_statistical_promotion_gate"])
            self.assertFalse(report["auto_published"])
            self.assertFalse(report["public_site_changed"])
            self.assertFalse(report["self_promoted"])
            self.assertEqual(report["financial_actions"], 0)
            saved=json.loads((root / rt.REPORT_NAME).read_text())
            self.assertEqual(saved["controller_sha256"], rt.EXPECTED_SHA)
            self.assertEqual((root / rt.REPORT_NAME).stat().st_mode & 0o077, 0)

    def test_repeat_minute_cycle_updates_epoch_but_not_public_master(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            enabled(root)
            rt.operate(root, examples(), 10, "2026-10-18T12:01:00Z")
            current=rt.operate(root, examples(), 11, "2026-10-18T12:02:00Z")
            self.assertEqual(current["cycle_epoch"], 11)
            self.assertEqual(current["existing_public_master_generation"], 64)
            self.assertEqual(len(list((root / "generations").glob("generation*.py"))), 1)

    def test_tampered_generated_code_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            enabled(root)
            module=root/"generations/generation65.py"
            module.write_text(module.read_text()+"\n# unverified")
            with self.assertRaisesRegex(RuntimeError, "source_attestation_failed|differs_from"):
                rt.operate(root, examples(), 10, "2026-10-18T12:01:00Z")
            self.assertFalse((root / rt.REPORT_NAME).exists())

    def test_tampered_manifest_sha_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            enabled(root)
            manifest=root/"generations/generation65.json"
            row=json.loads(manifest.read_text())
            row["code_sha256"]="0"*64
            manifest.write_text(json.dumps(row))
            with self.assertRaisesRegex(RuntimeError, "attestation_failed"):
                rt.operate(root, examples(), 10, "2026-10-18T12:01:00Z")

    def test_invalid_owner_flag_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            (root/rt.CONTROL_NAME).write_text(json.dumps({
                "tenant":"zomorodmelal", "active_private_generation": 65,
                "controller_sha256": rt.EXPECTED_SHA, "enabled": True,
                "scope": "private_verified_review_only"}))
            with self.assertRaisesRegex(RuntimeError, "owner_enable_flag_invalid"):
                rt.operate(root, examples(), 10, "2026-10-18T12:01:00Z")

    def test_unverified_duplicated_or_malformed_records_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            enabled(root)
            with self.assertRaisesRegex(RuntimeError, "unverified_or_unbounded"):
                rt.operate(root, [examples()[0]]*2, 10, "x")
            bad=examples()
            bad[0]["quality"]=True
            with self.assertRaisesRegex(RuntimeError, "unverified_or_unbounded"):
                rt.operate(root, bad, 10, "x")

    def test_control_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            produce(root, examples())
            owner=root/"flag.json"
            owner.write_text(json.dumps({
                "tenant":rt.TENANT, "active_private_generation": 65,
                "controller_sha256":rt.EXPECTED_SHA, "enabled": True,
                "scope":"private_verified_review_only"}))
            (root/rt.CONTROL_NAME).symlink_to(owner)
            with self.assertRaisesRegex(RuntimeError, "invalid_private_control"):
                rt.operate(root, examples(), 10, "x")


if __name__=="__main__":
    unittest.main()
