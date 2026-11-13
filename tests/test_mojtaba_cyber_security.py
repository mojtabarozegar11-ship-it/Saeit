"""Regression gates for the canonical bot's internal cyber module."""
import hashlib
import hmac
import json
import unittest
from datetime import datetime, timezone

from core.mojtaba_modules import BOT_ID, MODULE_ID, registered_capabilities, review_offline_evidence
from core.mojtaba_modules.cyber_security import (
    CyberModuleError, descriptor, verify_authorization,
)


KEY = b"local-fixture-only-verification-key-32-bytes-minimum"
NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def signed(**changes):
    manifest = {
        "schema": "mojtaba.bot.ai.cyber.engagement.v1",
        "bot_id": BOT_ID, "module_id": MODULE_ID,
        "tenant_id": "tenant-1", "engagement_id": "engagement-1",
        "allowed_assets": ["owned.example.com"],
        "mode": "offline_evidence",
        "issued_at": "2026-11-13T00:00:00+00:00",
        "expires_at": "2026-11-14T00:00:00+00:00",
    }
    manifest.update(changes)
    payload = json.dumps(manifest, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode()
    manifest["signature"] = hmac.new(KEY, payload, hashlib.sha256).hexdigest()
    return manifest


def evidence(**changes):
    result = {
        "schema": "mojtaba.bot.ai.cyber.evidence.v1",
        "tenant_id": "tenant-1", "engagement_id": "engagement-1",
        "findings": [{
            "finding_id": "a-1", "asset_hostname": "owned.example.com",
            "severity": "high", "title": "Missing header",
            "evidence_summary": "Offline artifact only",
            "remediation": "Set a secure response header",
        }],
    }
    result.update(changes)
    return result


class InternalCyberModuleTests(unittest.TestCase):
    def run_review(self, auth=None, data=None):
        return review_offline_evidence(
            engagement=auth if auth is not None else signed(),
            evidence=data if data is not None else evidence(),
            verify_key=KEY, now=NOW,
        )

    def test_one_canonical_bot_only(self):
        metadata = descriptor()
        self.assertEqual(metadata["bot_id"], "mojtaba.bot.ai")
        self.assertFalse(metadata["independent_agent"])
        self.assertFalse(metadata["independent_scheduler"])
        self.assertFalse(metadata["network_access"])
        self.assertEqual(list(registered_capabilities()), ["cyber_security"])

    def test_normal_offline_review(self):
        report = self.run_review()
        self.assertEqual(report["bot_id"], BOT_ID)
        self.assertEqual(report["counts"]["high"], 1)
        self.assertEqual(report["mode"], "offline_evidence")
        self.assertEqual(len(report["audit_sha256"]), 64)

    def test_no_signature(self):
        unsigned = signed()
        unsigned.pop("signature")
        with self.assertRaises(CyberModuleError):
            self.run_review(auth=unsigned)

    def test_signature_tampered(self):
        tampered = signed()
        tampered["tenant_id"] = "tenant-2"
        with self.assertRaises(CyberModuleError):
            self.run_review(auth=tampered)

    def test_no_second_bot_identity(self):
        with self.assertRaisesRegex(CyberModuleError, "CANONICAL_IDENTITY_REQUIRED"):
            self.run_review(auth=signed(bot_id="another.bot.ai"))

    def test_active_mode_forbidden(self):
        with self.assertRaisesRegex(CyberModuleError, "LIVE_ACTIONS_FORBIDDEN"):
            self.run_review(auth=signed(mode="live_scan"))

    def test_expired_grant(self):
        with self.assertRaisesRegex(CyberModuleError, "AUTHORIZATION_EXPIRED_OR_FUTURE"):
            self.run_review(auth=signed(expires_at="2026-11-13T10:00:00+00:00"))

    def test_host_suffix_bypass_forbidden(self):
        bad = evidence(findings=[{**evidence()["findings"][0],
                                  "asset_hostname": "attackerowned.example.com"}])
        with self.assertRaisesRegex(CyberModuleError, "ASSET_OUT_OF_SCOPE"):
            self.run_review(data=bad)

    def test_cross_tenant_forbidden(self):
        with self.assertRaisesRegex(CyberModuleError, "CROSS_TENANT_EVIDENCE_FORBIDDEN"):
            self.run_review(data=evidence(tenant_id="tenant-2"))

    def test_duplicate_findings_forbidden(self):
        record = evidence()["findings"][0]
        with self.assertRaisesRegex(CyberModuleError, "FINDING_ID_INVALID"):
            self.run_review(data=evidence(findings=[record, record]))

    def test_secret_redaction(self):
        original = evidence()["findings"][0]
        data = evidence(findings=[{**original, "evidence_summary": "password=supersecret"}])
        report = self.run_review(data=data)
        self.assertIn("[REDACTED]", report["findings"][0]["evidence_summary"])
        self.assertNotIn("supersecret", str(report))

    def test_scope_cannot_be_wildcard(self):
        with self.assertRaisesRegex(CyberModuleError, "ASSET_INVALID"):
            self.run_review(auth=signed(allowed_assets=["*.example.com"]))

    def test_short_key_forbidden(self):
        with self.assertRaisesRegex(CyberModuleError, "VERIFIER_KEY_INVALID"):
            verify_authorization(signed(), b"short", now=NOW)

    def test_untrusted_findings_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "FINDINGS_INVALID"):
            self.run_review(data=evidence(findings="untrusted"))

    def test_list_severity_is_rejected_without_exception_leak(self):
        bad = evidence(findings=[{**evidence()["findings"][0], "severity": ["high"]}])
        with self.assertRaisesRegex(CyberModuleError, "SEVERITY_INVALID"):
            self.run_review(data=bad)

    def test_dict_severity_is_rejected_without_exception_leak(self):
        bad = evidence(findings=[{**evidence()["findings"][0], "severity": {"x": "high"}}])
        with self.assertRaisesRegex(CyberModuleError, "SEVERITY_INVALID"):
            self.run_review(data=bad)


    def test_long_lived_authorization_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "AUTHORIZATION_WINDOW_INVALID"):
            self.run_review(auth=signed(expires_at="2026-11-14T01:00:00+00:00"))

    def test_zero_length_authorization_rejected(self):
        with self.assertRaisesRegex(CyberModuleError, "AUTHORIZATION_WINDOW_INVALID"):
            self.run_review(auth=signed(expires_at="2026-11-13T00:00:00+00:00"))

    def test_standard_one_day_authorization_remains_accepted(self):
        report = self.run_review(auth=signed())
        self.assertEqual(report["mode"], "offline_evidence")



if __name__ == "__main__":
    unittest.main()
