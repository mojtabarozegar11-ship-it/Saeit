"""Standard-library tests for passive incident triage and evidence integrity."""

from datetime import datetime, timedelta, timezone
import unittest

from core.cyber_defense import (
    GENESIS_HASH, defensive_response_plan, identity_assessment,
    make_security_event, seal_evidence, triage_security_events,
    verify_evidence_chain,
)


NOW = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)


class CyberDefenseTests(unittest.TestCase):
    def event(self, kind="authentication_failed", **kwargs):
        kwargs.setdefault("observed_at", NOW)
        return make_security_event(kind, "managed-vps", **kwargs)

    def test_event_allowlist_rejects_secret_or_raw_payload(self):
        with self.assertRaises(ValueError):
            self.event(indicators={"api_key": "secret"})

    def test_forged_event_cannot_be_sealed(self):
        forged = self.event()
        forged["indicators"]["password"] = "leak"
        with self.assertRaises(ValueError):
            seal_evidence(forged)

    def test_triage_rejects_untrusted_telemetry(self):
        with self.assertRaises(ValueError):
            triage_security_events([{"kind": "malware_indicator"}], now=NOW)

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValueError):
            self.event("execute_shell")

    def test_invalid_ip_rejected(self):
        with self.assertRaises(ValueError):
            self.event(source_ip="not-an-ip")

    def test_ipv6_normalization(self):
        self.assertEqual(self.event(source_ip="2001:0db8::1")["source_ip"], "2001:db8::1")

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            self.event(observed_at=datetime(2026, 11, 10))

    def test_boolean_indicator_rejects_integer(self):
        with self.assertRaises(ValueError):
            self.event(indicators={"known_device": 1})

    def test_chain_integrity(self):
        first = seal_evidence(self.event(), previous_hash=GENESIS_HASH)
        second = seal_evidence(self.event("mfa_failed"), previous_hash=first["record_hash"])
        self.assertTrue(verify_evidence_chain([first, second]))

    def test_chain_detects_tampering(self):
        first = seal_evidence(self.event())
        first["event"]["asset"] = "attacker-modified"
        self.assertFalse(verify_evidence_chain([first]))

    def test_chain_detects_missing_link(self):
        first = seal_evidence(self.event())
        second = seal_evidence(self.event("mfa_failed"), previous_hash=first["record_hash"])
        self.assertFalse(verify_evidence_chain([second]))

    def test_authentication_burst(self):
        events = [self.event(source_ip="192.0.2.1") for _ in range(5)]
        result = triage_security_events(events, now=NOW)
        self.assertEqual(result["severity"], "high")
        self.assertIn("authentication_burst", result["findings"])

    def test_expired_activity_ignored(self):
        older = make_security_event("mfa_failed", "managed-vps", observed_at=NOW - timedelta(hours=1))
        self.assertEqual(triage_security_events([older], now=NOW)["events_examined"], 0)

    def test_exfiltration_signal_critical_but_not_confirmed(self):
        event = self.event("unexpected_data_transfer", indicators={"bytes_out": 9000000, "baseline_bytes_out": 100000})
        result = triage_security_events([event], now=NOW)
        self.assertEqual(result["severity"], "critical")
        self.assertIn("possible_exfiltration", result["findings"])
        self.assertEqual(result["identity_status"], "unverified")

    def test_unknown_identity_by_default(self):
        self.assertEqual(identity_assessment(), "unknown")
        self.assertEqual(identity_assessment(account_match=True), "technical_lead_unverified")

    def test_identity_requires_three_independent_flags(self):
        self.assertEqual(identity_assessment(account_match=True, device_match=True), "technical_lead_unverified")
        self.assertEqual(identity_assessment(account_match=True, device_match=True,
                                             independently_verified=True), "corroborated_for_authorized_review")

    def test_plan_never_hacks_back_or_claims_remote_delete(self):
        plan = defensive_response_plan({"severity": "critical"})
        self.assertTrue(plan["requires_owner_approval"])
        self.assertFalse(plan["remote_deletion_guarantee"])
        self.assertFalse(plan["data_return_guarantee"])
        self.assertEqual(plan["automatic_actions_taken"], [])
        self.assertNotIn("delete_attacker_files", plan["steps_for_authorized_review"])


if __name__ == "__main__":
    unittest.main()
