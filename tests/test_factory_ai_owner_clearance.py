"""Fail-closed integration tests for AI-assisted review and genuine owner approval.

Cryptographic keys here are disposable local test fixtures, never production
reviewer/owner identities or signatures.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "saeit_cycle_for_ai_release", ROOT / "scripts/factory_vps_product_cycle.py")
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


class AIOwnerQualityExitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "factory"
        self.recipe = "farm_enterprise_economics"
        self.artifact = b"immutable-product-fixture"
        self.sha = hashlib.sha256(self.artifact).hexdigest()
        product = self.root / "digital-products" / self.recipe
        product.mkdir(parents=True)
        (product / (self.recipe + "-internal-qa.zip")).write_bytes(self.artifact)
        (product / "manufacturing_manifest.json").write_text(json.dumps({
            "recipe": self.recipe, "qa_status": "passed",
            "artifact_sha256": self.sha}), encoding="utf8")
        self.review_dir = self.root / "quality-excellence/ai-reviews" / self.recipe
        self.review_dir.mkdir(parents=True)
        self.review_path = self.review_dir / "current.json"
        self.review = {
            "schema": cycle.AI_REVIEW_SCHEMA,
            "reviewer_kind": "chatgpt_ai_assisted_internal",
            "independent_human_review": False,
            "artifact_sha256": self.sha,
            "review_status": "completed",
            "verified_grade_total": 1000,
            "evidence_checks": [
                {"check_id": check, "status": "passed",
                 "evidence_sha256": hashlib.sha256(check.encode()).hexdigest()}
                for check in sorted(cycle.MANDATORY_AI_CHECKS)],
        }
        self.review_path.write_text(json.dumps(self.review), encoding="utf8")
        self.clear_dir = (self.root / "quality-excellence/signed-clearances"
                          / self.recipe)
        self.clear_dir.mkdir(parents=True)
        self.clear_path = self.clear_dir / "current.json"
        self.clearance = {
            "schema": cycle.OWNER_CLEARANCE_SCHEMA,
            "reviewer_kind": "chatgpt_ai_assisted_internal",
            "independent_human_review": False,
            "ai_review_sha256": hashlib.sha256(
                self.review_path.read_bytes()).hexdigest(),
            "eligible": True, "verified_grade_total": 1000,
            "artifact_sha256": self.sha,
            "owner_authorization_kind": "direct_owner",
            "owner_rights_attestation": True,
            "publication_executed": False, "payment_activated": False,
        }
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.private = self.home / "owner.private.pem"
        self.public = self.home / "owner.public.pem"
        subprocess.run(["openssl", "ecparam", "-name", "prime256v1",
                        "-genkey", "-noout", "-out", str(self.private)],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(self.private),
                        "-pubout", "-out", str(self.public)],
                       check=True, capture_output=True)
        patch = mock.patch.object(
            cycle, "_trusted_owner_public_key", return_value=self.public)
        patch.start()
        self.addCleanup(patch.stop)

    def sign(self):
        subprocess.run(["openssl", "dgst", "-sha256",
                        "-sign", str(self.private),
                        "-out", str(self.clear_dir / "owner.sig"),
                        str(self.clear_path)],
                       check=True, capture_output=True)

    def prepare_receiver_handoff(self, status="accepted_by_receiver"):
        self.sign()
        approved = cycle._verified_quality_exit(self.root, self.recipe)
        self.assertIsNotNone(approved)
        trust_parent = self.home / "admin-trust"
        trust_parent.mkdir(mode=0o700)
        trust = trust_parent / "receivers"
        trust.mkdir(mode=0o700)
        receiver_private = self.home / "receiver.private.pem"
        receiver_public = trust / "R-01.pem"
        subprocess.run(["openssl", "ecparam", "-name", "prime256v1",
                        "-genkey", "-noout", "-out", str(receiver_private)],
                       check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(receiver_private),
                        "-pubout", "-out", str(receiver_public)],
                       check=True, capture_output=True)
        inbox = (self.root / "product-lifecycle/hourly-cycle-handoffs"
                 / "R-01" / self.recipe)
        inbox.mkdir(parents=True)
        (inbox / "product.zip").write_bytes(self.artifact)
        receipt = inbox / "receipt.json"
        self.write_receiver_receipt(receipt, approved, status=status)
        subprocess.run(["openssl", "dgst", "-sha256",
                        "-sign", str(receiver_private),
                        "-out", str(inbox / "receipt.sig"), str(receipt)],
                       check=True, capture_output=True)
        return approved, trust, receipt

    def write_receiver_receipt(self, path, approved, *, status):
        path.write_text(json.dumps({
            "schema": cycle.HOURLY_HANDOFF_SCHEMA,
            "product_id": self.recipe,
            "receiver_cycle": "R-01",
            "status": status,
            "artifact_sha256": approved["artifact_sha256"],
            "clearance_sha256": approved["clearance_sha256"],
            "acceptance_evidence": "Private receiver inspection confirmed"
        }), encoding="utf8")

    def test_genuine_owner_signature_and_evidence_bound_ai_review(self):
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))
        self.sign()
        approved = cycle._verified_quality_exit(self.root, self.recipe)
        self.assertEqual(approved["artifact_sha256"], self.sha)
        self.assertEqual(approved["review_type"],
                         "internal_ai_assisted_owner_signed")
        self.assertFalse(cycle._accepted_hourly_handoff(
            self.root, self.recipe, approved))

    def test_fake_legacy_independent_claim_never_authorizes_exit(self):
        self.clearance["schema"] = "saeit.factory.signed-quality-clearance.v1"
        self.clearance["valid_signed_roles"] = [
            "domain_specialist", "independent_quality_auditor", "rights_reviewer"]
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.sign()
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_tampering_with_signed_clearance_or_review_fails_closed(self):
        self.sign()
        self.assertIsNotNone(cycle._verified_quality_exit(self.root, self.recipe))
        self.clearance["owner_rights_attestation"] = False
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))
        self.clearance["owner_rights_attestation"] = True
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.sign()
        self.review["review_status"] = "altered"
        self.review_path.write_text(json.dumps(self.review), encoding="utf8")
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_missing_or_duplicate_evidence_is_rejected(self):
        self.review["evidence_checks"][1]["check_id"] = (
            self.review["evidence_checks"][0]["check_id"])
        self.review_path.write_text(json.dumps(self.review), encoding="utf8")
        self.clearance["ai_review_sha256"] = hashlib.sha256(
            self.review_path.read_bytes()).hexdigest()
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.sign()
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_claiming_external_independence_is_rejected(self):
        self.clearance["independent_human_review"] = True
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.sign()
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_no_administrator_trust_anchor_means_no_exit(self):
        self.sign()
        with mock.patch.object(cycle, "_trusted_owner_public_key",
                               return_value=None):
            self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_corrupt_ai_check_identifier_is_rejected_not_crash(self):
        self.review["evidence_checks"][0]["check_id"] = ["unhashable"]
        self.review_path.write_text(json.dumps(self.review), encoding="utf8")
        self.clearance["ai_review_sha256"] = hashlib.sha256(
            self.review_path.read_bytes()).hexdigest()
        self.clear_path.write_text(json.dumps(self.clearance), encoding="utf8")
        self.sign()
        self.assertIsNone(cycle._verified_quality_exit(self.root, self.recipe))

    def test_real_receiver_signature_accepts_exact_artifact(self):
        approved, trust, _receipt = self.prepare_receiver_handoff()
        with mock.patch.object(cycle, "RECEIVER_TRUST_ROOT", trust):
            self.assertTrue(cycle._accepted_hourly_handoff(
                self.root, self.recipe, approved))

    def test_receiver_trust_directory_requires_admin_protection(self):
        approved, trust, _receipt = self.prepare_receiver_handoff()
        trust.parent.chmod(0o777)
        with mock.patch.object(cycle, "RECEIVER_TRUST_ROOT", trust):
            self.assertFalse(cycle._accepted_hourly_handoff(
                self.root, self.recipe, approved))

    def test_unsigned_swap_after_signature_check_cannot_fake_acceptance(self):
        approved, trust, receipt = self.prepare_receiver_handoff(
            status="rejected_by_receiver")
        original_run = subprocess.run
        changed = [False]

        def swap_after_crypto_check(command, *args, **kwargs):
            result = original_run(command, *args, **kwargs)
            if "-verify" in command and "-signature" in command:
                self.write_receiver_receipt(
                    receipt, approved, status="accepted_by_receiver")
                changed[0] = True
            return result

        with mock.patch.object(cycle, "RECEIVER_TRUST_ROOT", trust), \
                mock.patch.object(cycle.subprocess, "run",
                                  side_effect=swap_after_crypto_check):
            self.assertFalse(cycle._accepted_hourly_handoff(
                self.root, self.recipe, approved))
        self.assertTrue(changed[0])


if __name__ == "__main__":
    unittest.main()
