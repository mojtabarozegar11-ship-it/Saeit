"""Tests for signed, independent Moj Prop readiness evidence."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from core.commercialization_readiness import SECTORS
from core.tron_tenant_policy import (
    CANONICAL_ASSET, CANONICAL_CHAIN, REQUIRED_ATTESTATIONS,
    registered_scope,
)
from prop_firm.challenge_commerce import REQUIRED
from prop_firm.independent_attestation import (
    AttestationRejected, assess_independent_attestations, verify_attestation,
)
from prop_firm.release_gate import assess_moj_prop_release


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
KEYS = {
    "capital-registry": "capital-secret-that-is-at-least-32-bytes-long",
    "broker-registry": "broker-secret-that-is-at-least-32-bytes-long",
}
TRON_REGISTRY = {
    ("mojplaywin.com", "moj_prop"): {
        "tenant_id": "moj-prop-merchant",
        "network": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        **{name: True for name in REQUIRED_ATTESTATIONS},
    },
}


def signed_packet(kind, *, key_id=None, issued=NOW - timedelta(minutes=5),
                  expires=NOW + timedelta(hours=1), digest=None):
    key_id = key_id or f"{kind}-registry"
    packet = {
        "attestation_id": f"{kind}-attestation-001",
        "kind": kind,
        "subject_id": f"moj-prop:MOJ-PROP-01:{kind}",
        "source": f"{kind}-reconciliation",
        "key_id": key_id,
        "issued_at": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_digest": digest or hashlib.sha256(
            f"{kind}-evidence".encode()
        ).hexdigest(),
    }
    body = json.dumps(
        packet, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    key = KEYS.get(key_id, "owner-secret-that-must-not-pass")
    packet["signature"] = hmac.new(
        key.encode("utf-8"),
        b"MOJPROP-ATTESTATION-v1\n" + body,
        hashlib.sha256,
    ).hexdigest()
    return packet


class IndependentAttestationTests(SimpleTestCase):
    def tenant(self):
        return registered_scope(
            host="mojplaywin.com", brand="moj_prop",
            registry=TRON_REGISTRY,
        )

    def review(self, **changes):
        values = {
            "merchant_tenant": self.tenant(),
            "free_treasury_usd": "1000",
            "protected_reserves_usd": "100",
            "existing_commitments_usd": "0",
            "required_first_tier_accounts": 1,
            "challenge_attestations": {key: True for key in REQUIRED},
            "sector_attestations": {
                key: True for key in SECTORS["moj_prop"]
            },
            "trusted_merchant_registry": TRON_REGISTRY,
            "independent_attestations": [
                signed_packet("capital"), signed_packet("broker")
            ],
            "trusted_attestation_keys": KEYS,
            "attestation_now": NOW,
        }
        values.update(changes)
        return assess_moj_prop_release(**values)

    def test_two_valid_independent_attestations_unlock_review_only(self):
        decision = self.review()
        self.assertTrue(decision.independent_capital_proof_on_record)
        self.assertTrue(decision.independent_broker_proof_on_record)
        self.assertTrue(decision.eligible_for_commercial_review)
        self.assertEqual(decision.outcome, "reviewable_not_authorized")
        self.assertEqual(
            (decision.checkout_enabled, decision.invoice_created,
             decision.trading_enabled, decision.release_authorized),
            (False, False, False, False),
        )

    def test_missing_broker_does_not_unlock_commercial_review(self):
        decision = self.review(
            independent_attestations=[signed_packet("capital")]
        )
        self.assertTrue(decision.independent_capital_proof_on_record)
        self.assertFalse(decision.independent_broker_proof_on_record)
        self.assertIn("independent_broker_proof_required", decision.blockers)
        self.assertFalse(decision.eligible_for_commercial_review)

    def test_expired_attestation_fails_closed(self):
        packet = signed_packet(
            "capital",
            issued=NOW - timedelta(days=2),
            expires=NOW - timedelta(minutes=1),
        )
        assessment = assess_independent_attestations(
            [packet, signed_packet("broker")], KEYS, now=NOW
        )
        self.assertIsNone(assessment.capital)
        self.assertTrue(any("expired" in error for error in assessment.errors))
        decision = self.review(independent_attestations=[packet, signed_packet("broker")])
        self.assertIn("independent_capital_proof_required", decision.blockers)

    def test_owner_key_cannot_be_independent(self):
        packet = signed_packet("capital", key_id="owner")
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, {"owner": KEYS["capital-registry"]}, now=NOW)

    def test_tampered_digest_or_signature_is_rejected(self):
        packet = signed_packet("capital")
        packet["evidence_digest"] = "0" * 64
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, KEYS, now=NOW)

    def test_duplicate_kind_cannot_complete_assessment(self):
        first = signed_packet("capital")
        second = signed_packet("capital")
        second["attestation_id"] = "capital-attestation-002"
        body = json.dumps(
            {key: second[key] for key in sorted(second) if key != "signature"},
            ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        second["signature"] = hmac.new(
            KEYS["capital-registry"].encode("utf-8"),
            b"MOJPROP-ATTESTATION-v1\n" + body,
            hashlib.sha256,
        ).hexdigest()
        assessment = assess_independent_attestations(
            [first, second], KEYS, now=NOW
        )
        self.assertFalse(assessment.complete)
        self.assertIn("duplicate_capital_attestation", assessment.errors)

    def test_attestation_lifetime_is_bounded(self):
        packet = signed_packet(
            "capital", issued=NOW - timedelta(days=31),
            expires=NOW + timedelta(days=1),
        )
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, KEYS, now=NOW)

    def test_future_attestation_is_rejected(self):
        packet = signed_packet(
            "capital", issued=NOW + timedelta(minutes=1),
            expires=NOW + timedelta(hours=1),
        )
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, KEYS, now=NOW)

    def test_malformed_packets_never_raise_from_assessment(self):
        assessment = assess_independent_attestations(
            [{"kind": "capital"}], KEYS, now=NOW
        )
        self.assertFalse(assessment.complete)
        self.assertEqual(len(assessment.errors), 1)

    def test_non_list_input_stays_fail_closed(self):
        assessment = assess_independent_attestations(
            {"capital": signed_packet("capital")}, KEYS, now=NOW
        )
        self.assertFalse(assessment.complete)
        self.assertEqual(assessment.errors, ("packet_list_required",))

    def test_key_registry_is_required(self):
        packet = signed_packet("capital")
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, None, now=NOW)

    def test_validly_signed_attestation_for_other_plan_is_not_our_proof(self):
        packet = signed_packet("capital")
        packet["subject_id"] = "moj-prop:MOJ-PROP-09:capital"
        self.resign(packet)
        decision = self.review(
            independent_attestations=[packet, signed_packet("broker")]
        )
        self.assertFalse(decision.independent_capital_proof_on_record)
        self.assertIn("independent_capital_proof_required", decision.blockers)
        self.assertFalse(decision.eligible_for_commercial_review)

    def test_valid_plan_one_certificates_do_not_transfer_to_plan_two(self):
        decision = self.review(
            plan_code="MOJ-PROP-02",
            independent_attestations=[signed_packet("capital"), signed_packet("broker")],
        )
        self.assertFalse(decision.independent_capital_proof_on_record)
        self.assertFalse(decision.independent_broker_proof_on_record)

    def test_reused_attestation_identifier_is_rejected(self):
        capital = signed_packet("capital")
        broker = signed_packet("broker")
        broker["attestation_id"] = capital["attestation_id"]
        self.resign(broker)
        result = assess_independent_attestations([capital, broker], KEYS, now=NOW)
        self.assertIn("duplicate_attestation_id", result.errors)
        self.assertFalse(result.complete)

    def test_same_upstream_source_cannot_sign_both_independent_claims(self):
        capital = signed_packet("capital")
        broker = signed_packet("broker")
        broker["source"] = capital["source"]
        self.resign(broker)
        result = assess_independent_attestations([capital, broker], KEYS, now=NOW)
        self.assertIn("capital_broker_must_have_distinct_sources", result.errors)
        self.assertFalse(result.complete)

    def test_evidence_digest_must_differ_between_claim_types(self):
        capital = signed_packet("capital")
        broker = signed_packet("broker")
        broker["evidence_digest"] = capital["evidence_digest"]
        self.resign(broker)
        result = assess_independent_attestations([capital, broker], KEYS, now=NOW)
        self.assertIn("capital_broker_must_have_distinct_evidence", result.errors)
        self.assertFalse(result.complete)

    def test_distinct_registry_names_with_same_key_material_are_not_independent(self):
        keys = dict(KEYS)
        keys["broker-registry"] = keys["capital-registry"]
        broker = signed_packet("broker")
        self.resign(broker, key=keys["broker-registry"])
        result = assess_independent_attestations(
            [signed_packet("capital"), broker], keys, now=NOW
        )
        self.assertIn("capital_broker_share_key_material", result.errors)
        self.assertFalse(result.complete)

    def test_single_key_cannot_support_two_categories(self):
        broker = signed_packet("broker")
        broker["key_id"] = "capital-registry"
        self.resign(broker)
        result = assess_independent_attestations(
            [signed_packet("capital"), broker], KEYS, now=NOW
        )
        self.assertIn("capital_broker_must_have_distinct_keys", result.errors)
        self.assertFalse(result.complete)

    def test_oversized_attestation_batch_fails_closed(self):
        result = assess_independent_attestations(
            [signed_packet("capital")] * 9, KEYS, now=NOW
        )
        self.assertEqual(result.errors, ("too_many_attestations",))
        self.assertFalse(result.complete)

    def test_placeholder_digest_is_not_a_capital_receipt(self):
        with self.assertRaises(AttestationRejected):
            verify_attestation(signed_packet("capital", digest="0" * 64), KEYS, now=NOW)

    def test_unhashable_claim_kind_is_rejected_without_typeerror(self):
        packet = signed_packet("capital")
        packet["kind"] = []
        with self.assertRaises(AttestationRejected):
            verify_attestation(packet, KEYS, now=NOW)

    def test_invalid_clock_object_is_rejected_without_attributeerror(self):
        with self.assertRaises(AttestationRejected):
            verify_attestation(signed_packet("capital"), KEYS, now=object())

    @staticmethod
    def resign(packet, key=None):
        body = json.dumps(
            {name: packet[name] for name in sorted(packet) if name != "signature"},
            ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        secret = key if key is not None else KEYS[packet["key_id"]]
        packet["signature"] = hmac.new(
            secret.encode("utf-8"), b"MOJPROP-ATTESTATION-v1\n" + body,
            hashlib.sha256,
        ).hexdigest()
