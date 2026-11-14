"""Isolation and non-destructive incident response tests for Mojtaba.bot.ai."""
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone

from core.mojtaba_modules.cyber_security import CyberModuleError
from core.mojtaba_modules.incident_response import plan_incident_response

NOW = datetime(2026, 11, 13, 13, tzinfo=timezone.utc)
KEY = b"fixture-only-not-a-production-key-20261113-123456789"


def grant(**changes):
    result = {
        "schema": "mojtaba.bot.ai.cyber.engagement.v1",
        "bot_id": "mojtaba.bot.ai", "module_id": "cyber_security",
        "tenant_id": "tenant-1", "engagement_id": "engagement-1",
        "allowed_assets": ["owned.example.com"],
        "mode": "offline_evidence",
        "issued_at": "2026-11-13T10:00:00+00:00",
        "expires_at": "2026-11-14T10:00:00+00:00",
    }
    result.update(changes)
    source = json.dumps(result, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":"), allow_nan=False).encode("utf-8")
    result["signature"] = hmac.new(KEY, source, hashlib.sha256).hexdigest()
    return result


def indicator(**changes):
    result = {
        "id": "i-1", "kind": "suspected_destructive_activity",
        "confidence": "high", "observed_at": "2026-11-13T12:40:00+00:00",
    }
    result.update(changes)
    return result


def backup(**changes):
    result = {
        "backup_id": "b-1", "integrity_status": "verified_claim",
        "immutable": True, "sha256": "a" * 64,
        "captured_at": "2026-11-13T11:30:00+00:00",
    }
    result.update(changes)
    return result


def incident(**changes):
    result = {
        "schema": "mojtaba.bot.ai.cyber.incident-response.v1",
        "tenant_id": "tenant-1", "engagement_id": "engagement-1",
        "incident_id": "incident-1", "asset_hostname": "owned.example.com",
        "indicators": [indicator()], "backups": [backup()],
    }
    result.update(changes)
    return result


class IncidentResponseTests(unittest.TestCase):
    def plan(self, data=None, auth=None):
        return plan_incident_response(
            engagement=auth if auth is not None else grant(),
            incident=data if data is not None else incident(),
            verify_key=KEY, now=NOW,
        )

    def test_canonical_identity_and_no_actions(self):
        result = self.plan()
        self.assertEqual(result["bot_id"], "mojtaba.bot.ai")
        self.assertEqual(result["module_id"], "cyber_security")
        self.assertEqual(result["submodule_id"], "incident_response")
        self.assertEqual(result["mode"], "offline_plan_only")
        self.assertEqual(result["executed_actions"], 0)
        self.assertTrue(result["counterattack_prohibited"])
        self.assertFalse(result["data_export_executed"])

    def test_destructive_indicator_proposes_containment_not_destruction(self):
        result = self.plan()
        self.assertEqual(result["risk"], "critical")
        self.assertIn("review_isolation_of_affected_authorized_assets", result["proposed_steps"])
        self.assertIn("preserve_evidence_and_access_logs", result["proposed_steps"])
        self.assertNotIn("delete_target_files", result["proposed_steps"])

    def test_suspected_data_exposure_proposes_legal_review(self):
        data = incident(indicators=[indicator(kind="suspected_data_exposure")])
        result = self.plan(data)
        self.assertIn("request_privacy_and_legal_notification_assessment", result["proposed_steps"])
        self.assertTrue(result["requires_human_authorization"])

    def test_but_backup_claim_is_not_restoration_proof(self):
        result = self.plan()
        self.assertFalse(result["backup_restore_proven"])
        self.assertFalse(result["backup_assessments"][0]["restore_test_verified"])

    def test_backup_identifier_not_disclosed(self):
        result = self.plan()
        self.assertNotIn('"b-1"', json.dumps(result))
        self.assertEqual(len(result["backup_assessments"][0]["backup_tag"]), 16)

    def test_unknown_backup_downgrades_recovery(self):
        data = incident(backups=[backup(integrity_status="unknown", immutable=False)])
        result = self.plan(data)
        self.assertIn("investigate_unverified_or_mutable_backup", result["proposed_steps"])

    def test_no_backup_generates_restore_check(self):
        result = self.plan(incident(backups=[]))
        self.assertIn("verify_immutable_backup_restore_plan", result["proposed_steps"])

    def test_cross_tenant_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "CROSS_TENANT_EVIDENCE_FORBIDDEN"):
            self.plan(incident(tenant_id="another-tenant"))

    def test_cross_engagement_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "CROSS_TENANT_EVIDENCE_FORBIDDEN"):
            self.plan(incident(engagement_id="another-engagement"))

    def test_asset_scope_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "ASSET_OUT_OF_SCOPE"):
            self.plan(incident(asset_hostname="outside.example.com"))

    def test_expired_authorization_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "AUTHORIZATION_EXPIRED_OR_FUTURE"):
            self.plan(auth=grant(expires_at="2026-11-13T12:00:00+00:00"))

    def test_wrong_canonical_bot_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "CANONICAL_IDENTITY_REQUIRED"):
            self.plan(auth=grant(bot_id="malicious.agent.ai"))

    def test_unknown_indicator_type_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_CLASS_INVALID"):
            self.plan(incident(indicators=[indicator(kind="steal_data")]))

    def test_unknown_confidence_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_CLASS_INVALID"):
            self.plan(incident(indicators=[indicator(confidence="certain")]))

    def test_duplicate_indicator_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_ID_DUPLICATED"):
            self.plan(incident(indicators=[indicator(), indicator()]))

    def test_duplicate_backup_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "BACKUP_ID_DUPLICATED"):
            self.plan(incident(backups=[backup(), backup()]))

    def test_future_indicator_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_OUTSIDE_WINDOW"):
            self.plan(incident(indicators=[indicator(observed_at="2026-11-13T13:01:00+00:00")]))

    def test_before_signed_scope_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_OUTSIDE_WINDOW"):
            self.plan(incident(indicators=[indicator(observed_at="2026-11-13T09:59:00+00:00")]))

    def test_future_backup_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "BACKUP_TIMESTAMP_INVALID"):
            self.plan(incident(backups=[backup(captured_at="2026-11-14T13:00:00+00:00")]))

    def test_bad_digest_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "BACKUP_ATTESTATION_INVALID"):
            self.plan(incident(backups=[backup(sha256="INVALID")]))

    def test_boolean_immutability_required(self):
        with self.assertRaisesRegex(CyberModuleError, "BACKUP_ATTESTATION_INVALID"):
            self.plan(incident(backups=[backup(immutable="yes")]))

    def test_empty_incident_readonly(self):
        result = self.plan(incident(indicators=[], backups=[]))
        self.assertEqual(result["risk"], "informational")
        self.assertEqual(result["executed_actions"], 0)

    def test_list_payload_not_valid_indicator_kind(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_CLASS_INVALID"):
            self.plan(incident(indicators=[indicator(kind=["suspected_ransomware"])]))

    def test_list_payload_not_valid_indicator_confidence(self):
        with self.assertRaisesRegex(CyberModuleError, "INDICATOR_CLASS_INVALID"):
            self.plan(incident(indicators=[indicator(confidence=["high"])]))

    def test_list_payload_not_valid_backup_integrity(self):
        with self.assertRaisesRegex(CyberModuleError, "BACKUP_ATTESTATION_INVALID"):
            self.plan(incident(backups=[backup(integrity_status=["verified_claim"])]))

    def test_deterministic_audit_digest(self):
        first = self.plan()["audit_sha256"]
        second = self.plan()["audit_sha256"]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_backup_tags_are_tenant_isolated_even_for_same_engagement(self):
        original = self.plan()["backup_assessments"][0]["backup_tag"]
        other = self.plan(
            incident(tenant_id="tenant-2"),
            grant(tenant_id="tenant-2"),
        )["backup_assessments"][0]["backup_tag"]
        self.assertNotEqual(original, other)

    def test_backup_tag_framing_prevents_separator_collision(self):
        left = self.plan(
            incident(tenant_id="tenant|x", engagement_id="case"),
            grant(tenant_id="tenant|x", engagement_id="case"),
        )["backup_assessments"][0]["backup_tag"]
        right = self.plan(
            incident(tenant_id="tenant", engagement_id="x|case"),
            grant(tenant_id="tenant", engagement_id="x|case"),
        )["backup_assessments"][0]["backup_tag"]
        self.assertNotEqual(left, right)

    def test_backup_tag_not_plain_dictionary_hash(self):
        tag = self.plan()["backup_assessments"][0]["backup_tag"]
        unsalted = hashlib.sha256(b"engagement-1|b-1").hexdigest()[:16]
        self.assertNotEqual(tag, unsalted)


if __name__ == "__main__":
    unittest.main()
