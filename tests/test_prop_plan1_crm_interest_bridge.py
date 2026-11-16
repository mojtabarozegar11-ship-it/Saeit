"""No database, real email, buyer identity or payment in these test fixtures."""
import json
import hmac
import unittest
from dataclasses import FrozenInstanceError

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_crm_interest_bridge import (
    CRM_SCHEMA, PROVENANCE_SCOPE, _REQUIRED, verify_private_prop_interest_link,
)
from prop_firm.plan1_private_order_draft import build_plan1_private_review_draft
from test_prop_plan1_private_order_draft import inputs, NOW
from test_prop_buyer_precontract_chain import REF, BUYER
from test_prop_plan1_intake_provenance import INTAKE_KEY, intake_tag

CRM_KEY = b"synthetic-third-party-CRM-only-test-signature-key-000000"
CRM_ID = 123
CONSENT_DIGEST = "a" * 64


def crm_row(draft):
    return {
        "schema": CRM_SCHEMA,
        "crm_record_id": CRM_ID,
        "plan_code": "MOJ-PROP-01",
        "consent_version": "moj-prop-interest-v1",
        "status": "new",
        "source_language": "fa",
        "buyer_ref": BUYER,
        "request_ref": REF,
        "inquiry_sha256": draft.inquiry_sha256,
        "contract_review_sha256": draft.reviewer_packet_sha256,
        "consent_proof_sha256": CONSENT_DIGEST,
        "consent_scope": PROVENANCE_SCOPE,
        "consent_reviewed_at_sec": NOW - 15,
    }


def signed(row):
    payload = json.dumps(row, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return hmac.new(CRM_KEY, payload, "sha256").hexdigest()


def case():
    args = inputs()
    return args["inquiry"], build_plan1_private_review_draft(**args)


def prepared():
    inquiry, draft = case()
    row = crm_row(draft)
    return {
        "inquiry": inquiry,
        "draft": draft,
        "crm_attestation": row,
        "signed_crm_hmac_hex": signed(row),
        "trusted_crm_key": CRM_KEY,
        "intake_hmac_hex": intake_tag(inquiry),
        "trusted_intake_key": INTAKE_KEY,
        "expected_crm_record_id": CRM_ID,
        "expected_request_ref": REF,
        "expected_buyer_ref": BUYER,
        "server_now_sec": NOW,
    }


def verify(**overrides):
    args = prepared()
    args.update(overrides)
    return verify_private_prop_interest_link(**args)


class PrivatePropInterestAdapterTests(unittest.TestCase):
    def rejects_signed_change(self, **fields):
        kwargs = prepared()
        row = dict(kwargs["crm_attestation"])
        row.update(fields)
        kwargs["crm_attestation"] = row
        kwargs["signed_crm_hmac_hex"] = signed(row)
        with self.assertRaises(Plan1OrderGateClosed):
            verify_private_prop_interest_link(**kwargs)

    def test_canonical_private_link(self):
        self.assertEqual(verify().state, "PRIVATE_CRM_REVIEW_ONLY")

    def test_exact_plan_one_only(self):
        self.assertEqual(verify().sku, "MOJ-PROP-01")

    def test_original_specific_request_preserved(self):
        self.assertEqual(verify().request_ref, REF)

    def test_original_consent_evidence_digest_preserved(self):
        self.assertEqual(verify().consent_proof_sha256, CONSENT_DIGEST)

    def test_unsigned_email_never_leaks(self):
        self.assertNotIn("@", repr(verify()))

    def test_contract_review_digest_preserved(self):
        _, draft = case()
        self.assertEqual(verify().contract_review_sha256,
                         draft.reviewer_packet_sha256)

    def test_hmac_verified_snapshot_has_deterministic_digest(self):
        self.assertEqual(verify().record_digest, verify().record_digest)
        self.assertEqual(len(verify().record_digest), 64)

    def test_canonical_consent_version(self):
        self.assertEqual(verify().consent_version, "moj-prop-interest-v1")

    def test_source_only_does_not_prove_orm_row_exists(self):
        self.assertFalse(verify().crm_row_exists_in_database_proven_by_this_code)

    def test_source_only_does_not_prove_age_kyc(self):
        self.assertFalse(verify().legal_kyc_approved_by_this_code)

    def test_source_only_does_not_prove_buyer_identity(self):
        self.assertFalse(verify().subject_identity_independently_proven_by_this_code)

    def test_source_only_does_not_infer_contact_permission(self):
        self.assertFalse(verify().contact_allowed)

    def test_source_only_does_not_infer_marketing_permission(self):
        self.assertFalse(verify().marketing_allowed)

    def test_source_only_does_not_invoice(self):
        self.assertFalse(verify().invoice_issued)

    def test_source_only_does_not_allow_trx_payment(self):
        self.assertFalse(verify().payment_allowed)

    def test_source_only_does_not_create_enrollment(self):
        self.assertFalse(verify().challenge_enrollment_created)

    def test_source_only_does_not_validate_underlying_consent(self):
        self.assertFalse(verify().separate_opt_in_evidence_has_been_authenticated_by_code)

    def test_result_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            verify().invoice_issued = True

    def test_withdrawn_consent_never_reused(self):
        self.rejects_signed_change(status="withdrawn")

    def test_contacted_status_never_silently_reused(self):
        self.rejects_signed_change(status="contacted")

    def test_unrecognized_status_refused(self):
        self.rejects_signed_change(status="paid")

    def test_starter30_sku_refused(self):
        self.rejects_signed_change(plan_code="MOJPROP-STARTER30")

    def test_wrong_consent_version_refused(self):
        self.rejects_signed_change(consent_version="v0")

    def test_wrong_consent_scope_refused(self):
        self.rejects_signed_change(consent_scope="newsletter")

    def test_wrong_buyer_for_same_request_refused(self):
        self.rejects_signed_change(buyer_ref="BUYER-ZYXWVUTSRQPONMLK")

    def test_wrong_request_for_same_buyer_refused(self):
        self.rejects_signed_change(request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_crm_row_identity_is_unique_and_server_pinned(self):
        self.rejects_signed_change(crm_record_id=124)

    def test_wrong_inquiry_digest_refused(self):
        self.rejects_signed_change(inquiry_sha256="f" * 64)

    def test_wrong_review_digest_refused(self):
        self.rejects_signed_change(contract_review_sha256="f" * 64)

    def test_missing_consent_proof_refused(self):
        self.rejects_signed_change(consent_proof_sha256="")

    def test_placeholder_consent_proof_refused(self):
        self.rejects_signed_change(consent_proof_sha256="0" * 64)

    def test_invalid_language_refused(self):
        self.rejects_signed_change(source_language="XX")

    def test_supported_languages(self):
        for code in ("fa", "en", "ar"):
            args = prepared()
            row = dict(args["crm_attestation"], source_language=code)
            args["crm_attestation"] = row
            args["signed_crm_hmac_hex"] = signed(row)
            with self.subTest(code=code):
                self.assertEqual(verify_private_prop_interest_link(**args).state,
                                 "PRIVATE_CRM_REVIEW_ONLY")

    def test_expired_crm_consent_review_refused(self):
        self.rejects_signed_change(consent_reviewed_at_sec=NOW - 86_401)

    def test_future_crm_consent_review_refused(self):
        self.rejects_signed_change(consent_reviewed_at_sec=NOW + 1)

    def test_boolean_verified_timestamp_refused(self):
        self.rejects_signed_change(consent_reviewed_at_sec=True)

    def test_stale_private_order_review_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(server_now_sec=NOW + 3600)

    def test_signed_snapshot_tamper_rejected(self):
        args = prepared()
        args["crm_attestation"]["status"] = "withdrawn"
        with self.assertRaises(Plan1OrderGateClosed):
            verify_private_prop_interest_link(**args)

    def test_wrong_crm_signing_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_crm_key=b"wrong-private-CRM-reviewer-test-only-key-00000")

    def test_same_key_for_crm_and_intake_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_crm_key=INTAKE_KEY)

    def test_browser_string_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_crm_key=CRM_KEY.decode())

    def test_empty_crm_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_crm_key=b"")

    def test_malformed_mac_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(signed_crm_hmac_hex="bad")

    def test_missing_crm_attribute_rejected(self):
        args = prepared()
        row = args["crm_attestation"]
        del row["consent_scope"]
        args["signed_crm_hmac_hex"] = signed(row)
        with self.assertRaises(Plan1OrderGateClosed):
            verify_private_prop_interest_link(**args)

    def test_extra_personal_email_rejected(self):
        args = prepared()
        row = args["crm_attestation"]
        row["email"] = "none@example.invalid"
        args["signed_crm_hmac_hex"] = signed(row)
        with self.assertRaises(Plan1OrderGateClosed):
            verify_private_prop_interest_link(**args)

    def test_external_expected_record_id_refused_if_changed(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_crm_record_id=99)

    def test_boolean_record_id_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_crm_record_id=True)

    def test_untrusted_request_ref_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_request_ref="REQUEST-NOTCANONICAL")

    def test_buyer_ref_untrusted_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_buyer_ref="BUYER-NOTCANONICAL")

    def test_intake_signature_incorrect_refused(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(intake_hmac_hex="f" * 64)

    def test_crm_record_id_is_integer_not_raw_email(self):
        self.assertEqual(verify().crm_record_id, CRM_ID)


if __name__ == "__main__":
    unittest.main()
