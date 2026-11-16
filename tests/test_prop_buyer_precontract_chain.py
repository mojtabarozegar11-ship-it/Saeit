"""Source-only synthetic chain tests; no real customer identities or payments."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hmac
import json
import unittest

from prop_firm.buyer_interest_form import (
    _REQUIRED, validate_private_plan1_interest,
)
from prop_firm.buyer_order_review import (
    FIXED, REQUIRED_PROOFS, Plan1OrderGateClosed,
)
from prop_firm.buyer_precontract_chain import bind_private_inquiry_to_signed_review
from prop_firm.order_readiness import REQUIRED

KEY=b"synthetic-64byte-reviewer-test-key-never-use-as-live-secret-0000"
NOW=1_795_000_000
REF="REQUEST-ABCDEFGHIJKLMNOP"
BUYER="BUYER-ABCDEFGHIJKLMNOP"
SELLER="SELLER-ABCDEFGHIJKLMNOP"


def new_form():
    f={name:True for name in _REQUIRED}
    f.update(request_ref=REF,sku="MOJ-PROP-01",
             terms_version="2026-11-15/v1.2",self_declared_country="DE")
    return f


def new_inquiry():
    return validate_private_plan1_interest(
        form=new_form(),
        server_received_at=datetime.fromtimestamp(NOW-120, timezone.utc),
    )


def new_packet(inquiry):
    p=dict(FIXED)
    p.update(
        request_ref=REF,buyer_ref=BUYER,seller_ref=SELLER,
        inquiry_intent_sha256=inquiry.anonymous_intent_sha256,
        facts={key:True for key in REQUIRED},
        proofs={key:format(i+1,"x")*64 for i,key in enumerate(REQUIRED_PROOFS)},
        requested_at_sec=NOW-120,
        reviewed_at_sec=NOW-30,
        expires_at_sec=NOW+3600,
    )
    return p


def sign(p):
    body=json.dumps(p,sort_keys=True,separators=(",",":"),
                    ensure_ascii=True,allow_nan=False).encode("ascii")
    return hmac.new(KEY,body,"sha256").hexdigest()


def evaluate(inquiry=None, packet=None, **overrides):
    inquiry=new_inquiry() if inquiry is None else inquiry
    packet=new_packet(inquiry) if packet is None else packet
    args=dict(inquiry=inquiry,reviewed_packet=packet,reviewer_tag_hex=sign(packet),
              trusted_reviewer_key=KEY,expected_request_ref=REF,
              expected_buyer_ref=BUYER,expected_seller_ref=SELLER,
              server_now_sec=NOW)
    args.update(overrides)
    return bind_private_inquiry_to_signed_review(**args)


class PrivatePlan1PrecontractChainTests(unittest.TestCase):
    def test_original_inquiry_to_review_chain_preserves_ref(self):
        self.assertEqual(evaluate().request_ref,REF)

    def test_chain_preserves_original_intent_digest(self):
        inquiry=new_inquiry()
        self.assertEqual(evaluate(inquiry).inquiry_digest,
                         inquiry.anonymous_intent_sha256)

    def test_has_review_digest_not_raw_kyc_material(self):
        o=evaluate()
        self.assertEqual(len(o.review_digest),64)
        self.assertNotIn("passport",repr(o))

    def test_plan_one_only(self):
        o=evaluate()
        self.assertEqual((o.sku,o.terms_version),
                         ("MOJ-PROP-01","2026-11-15/v1.2"))

    def test_no_payable_invoice(self):
        self.assertFalse(evaluate().live_invoice_authorized)

    def test_no_settlement_receipt(self):
        self.assertFalse(evaluate().native_trx_settlement_confirmed)

    def test_no_challenge_enrollment(self):
        self.assertFalse(evaluate().enrollment_created)

    def test_no_marketing_permission(self):
        self.assertFalse(evaluate().marketing_allowed)

    def test_no_false_buyer_kyc_proof(self):
        self.assertFalse(evaluate().actual_buyer_identity_verified_by_this_module)

    def test_no_false_seller_license_proof(self):
        self.assertFalse(evaluate().actual_seller_legal_status_verified_by_this_module)

    def test_no_false_signature_authenticity_proof(self):
        self.assertFalse(evaluate().signed_customer_contract_proven_by_this_module)

    def test_handoff_is_immutable(self):
        o=evaluate()
        with self.assertRaises(FrozenInstanceError):
            o.enrollment_created=True

    def test_forged_or_missing_inquiry_rejected(self):
        # Build the packet from a known-good inquiry BEFORE passing the
        # malformed inquiry to the production gate. The test helper must not
        # dereference fake inputs or silently replace explicit None.
        valid_packet=new_packet(new_inquiry())
        for item in (object(),[],{},"buyer approved",None):
            with self.subTest(kind=type(item).__name__):
                with self.assertRaises(Plan1OrderGateClosed):
                    bind_private_inquiry_to_signed_review(
                        inquiry=item, reviewed_packet=valid_packet,
                        reviewer_tag_hex=sign(valid_packet),
                        trusted_reviewer_key=KEY,
                        expected_request_ref=REF,
                        expected_buyer_ref=BUYER,
                        expected_seller_ref=SELLER,
                        server_now_sec=NOW,
                    )

    def test_foreign_request_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(expected_request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_inquiry_sku_switch_rejected(self):
        inquiry=replace(new_inquiry(),sku="MOJPROP-STARTER30")
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_inquiry_terms_switch_rejected(self):
        inquiry=replace(new_inquiry(),terms_version="v1.1")
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_inquiry_state_pretending_approved_rejected(self):
        inquiry=replace(new_inquiry(),state="verified_paid")
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_inquiry_contact_pretending_authorized_rejected(self):
        inquiry=replace(new_inquiry(),allowed_to_contact=True)
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_inquiry_payment_pretending_authorized_rejected(self):
        inquiry=replace(new_inquiry(),payment_allowed=True)
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_inquiry_enrollment_pretending_authorized_rejected(self):
        inquiry=replace(new_inquiry(),challenge_enrollment_allowed=True)
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_missing_inquiry_receipt_timestamp_rejected(self):
        inquiry=replace(new_inquiry(),received_at="not-a-date")
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_forged_inquiry_receipt_time_rejected(self):
        inquiry=replace(new_inquiry(),received_at="2026-11-18T00:00:00+00:00")
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(inquiry)

    def test_signed_time_different_from_receipt_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["requested_at_sec"]+=1
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)

    def test_signed_inquiry_digest_mismatch_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["inquiry_intent_sha256"]="9"*64
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)

    def test_modified_form_digest_rejected_even_with_same_reference(self):
        inquiry=new_inquiry()
        newform=new_form()
        newform["self_declared_country"]="FR"
        changed=validate_private_plan1_interest(
            form=newform,
            server_received_at=datetime.fromtimestamp(NOW-120,timezone.utc),
        )
        p=new_packet(inquiry)
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(changed,p)

    def test_different_buyer_for_same_inquiry_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(expected_buyer_ref="BUYER-ZYXWVUTSRQPONMLK")

    def test_different_seller_for_same_inquiry_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(expected_seller_ref="SELLER-ZYXWVUTSRQPONML")

    def test_attestation_wrong_signer_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(trusted_reviewer_key=b"not-original-reviewer-key-64+synthetic-bytes")

    def test_review_false_legal_evidence_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["facts"]["entity_legal_clearance"]=False
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)

    def test_review_false_funding_evidence_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["facts"]["independent_funding_proof"]=False
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)

    def test_review_incorrect_native_fee_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["native_fee_sun"]=29_999_999
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)

    def test_stale_review_expires_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(server_now_sec=NOW+3600)

    def test_review_future_time_rejected(self):
        i=new_inquiry()
        p=new_packet(i)
        p["reviewed_at_sec"]=NOW+10
        with self.assertRaises(Plan1OrderGateClosed):
            evaluate(i,p)


if __name__=="__main__":
    unittest.main()
