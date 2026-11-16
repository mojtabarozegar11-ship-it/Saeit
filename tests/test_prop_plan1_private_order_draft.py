"""Plan 1 contract-bound PRIVATE review-draft regression tests.

All IDs, hashes, timing and signatures here are SYNTHETIC. Test results cannot
prove legal seller, funded cash, actual KYC, enforceable signatures or sales.
"""
from dataclasses import FrozenInstanceError
import unittest

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_private_order_draft import (
    _DOCUMENT_BINDINGS,
    build_plan1_private_review_draft,
)
from test_prop_buyer_precontract_chain import (
    NOW, REF, BUYER, SELLER, KEY, new_inquiry, new_packet, sign,
)


def inputs(inquiry=None, packet=None):
    inquiry = new_inquiry() if inquiry is None else inquiry
    packet = new_packet(inquiry) if packet is None else packet
    mapping = {
        expected: packet["proofs"][proof]
        for proof, expected in _DOCUMENT_BINDINGS.items()
    }
    return {
        "inquiry": inquiry,
        "reviewed_packet": packet,
        "reviewer_tag_hex": sign(packet),
        "trusted_reviewer_key": KEY,
        "expected_request_ref": REF,
        "expected_buyer_ref": BUYER,
        "expected_seller_ref": SELLER,
        "server_now_sec": NOW,
        **mapping,
    }


def review(**replacements):
    args = inputs()
    args.update(replacements)
    return build_plan1_private_review_draft(**args)


class NonPayablePlanOneReviewTests(unittest.TestCase):
    def test_only_canonical_challenge_product(self):
        self.assertEqual(review().sku, "MOJ-PROP-01")

    def test_native_exact_sun_amount_not_usd(self):
        self.assertEqual(review().amount_sun, 30_000_000)

    def test_native_trx_only(self):
        self.assertEqual((review().token_symbol, review().chain),
                         ("TRX", "TRON-mainnet"))

    def test_v12_contract_remains_locked(self):
        self.assertEqual(review().terms_version, "2026-11-15/v1.2")

    def test_private_review_has_no_payable_invoice(self):
        self.assertFalse(review().live_invoice_created)

    def test_never_payable(self):
        self.assertFalse(review().payable)

    def test_never_outputs_payment_instructions(self):
        self.assertFalse(review().payment_instructions_present)

    def test_never_claims_confirmed_settlement(self):
        self.assertFalse(review().settlement_verified)

    def test_never_creates_a_challenge_enrollment(self):
        self.assertFalse(review().enrollment_created)

    def test_never_authorizes_contact(self):
        self.assertFalse(review().buyer_contact_authorized)

    def test_never_authorizes_marketing(self):
        self.assertFalse(review().marketing_authorized)

    def test_does_not_claim_kyc_independently_verified(self):
        self.assertFalse(review().has_verified_KYC_by_this_code)

    def test_does_not_claim_legal_signatures(self):
        self.assertFalse(review().has_authentic_legal_signature_by_this_code)

    def test_does_not_claim_seller_legal_status(self):
        self.assertFalse(review().has_merchant_legal_clearance_by_this_code)

    def test_does_not_claim_funded_cash(self):
        self.assertFalse(review().has_unencumbered_capital_by_this_code)

    def test_requires_durable_unique_order_database(self):
        self.assertTrue(review().independent_database_uniqueness_still_required)

    def test_requires_external_legal_review(self):
        self.assertTrue(review().external_legal_review_still_required)

    def test_exact_request_is_preserved(self):
        self.assertEqual(review().original_request_ref, REF)

    def test_case_reference_never_looks_like_an_invoice(self):
        r=review().private_review_ref
        self.assertTrue(r.startswith("PROP1-REVIEW-"))
        self.assertEqual(len(r), 45)

    def test_case_reference_is_deterministic(self):
        self.assertEqual(review().private_review_ref,
                         review().private_review_ref)

    def test_signature_and_refund_evidence_is_bound(self):
        p=new_packet(new_inquiry())
        r=review()
        self.assertEqual(r.contract_pdf_sha256,
                         p["proofs"]["contract_pdf_sha256"])
        self.assertEqual(r.refund_disclosure_sha256,
                         p["proofs"]["refund_rights_disclosure_sha256"])
        self.assertEqual(r.buyer_signature_proof_sha256,
                         p["proofs"]["buyer_signature_proof_sha256"])
        self.assertEqual(r.seller_signature_proof_sha256,
                         p["proofs"]["seller_signature_proof_sha256"])

    def test_review_has_same_expiry_as_signed_envelope(self):
        p=new_packet(new_inquiry())
        self.assertEqual(review().expires_at_sec, p["expires_at_sec"])

    def test_draft_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            review().payable=True

    def test_each_external_document_digest_must_match_signed_review(self):
        for proof, trusted_name in _DOCUMENT_BINDINGS.items():
            args=inputs()
            args[trusted_name]="f"*64
            with self.subTest(proof=proof), self.assertRaises(Plan1OrderGateClosed):
                build_plan1_private_review_draft(**args)

    def test_each_external_document_digest_cannot_be_missing(self):
        for _, trusted_name in _DOCUMENT_BINDINGS.items():
            args=inputs()
            args[trusted_name]=""
            with self.subTest(proof=trusted_name), self.assertRaises(Plan1OrderGateClosed):
                build_plan1_private_review_draft(**args)

    def test_each_external_document_digest_rejects_boolean(self):
        for _, trusted_name in _DOCUMENT_BINDINGS.items():
            args=inputs()
            args[trusted_name]=True
            with self.subTest(proof=trusted_name), self.assertRaises(Plan1OrderGateClosed):
                build_plan1_private_review_draft(**args)

    def test_each_external_document_digest_rejects_placeholder(self):
        for _, trusted_name in _DOCUMENT_BINDINGS.items():
            args=inputs()
            args[trusted_name]="0"*64
            with self.subTest(proof=trusted_name), self.assertRaises(Plan1OrderGateClosed):
                build_plan1_private_review_draft(**args)

    def test_stale_signed_review_is_not_resurrected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(server_now_sec=NOW+3600)

    def test_missing_signer_key_is_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(trusted_reviewer_key=b"")

    def test_wrong_signer_key_is_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(trusted_reviewer_key=b"other-synthetic-reviewer-key-mismatch-1234")

    def test_buyer_cross_use_is_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(expected_buyer_ref="BUYER-ZYXWVUTSRQPONMLK")

    def test_seller_cross_use_is_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(expected_seller_ref="SELLER-ZYXWVUTSRQPONM")

    def test_request_cross_use_is_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            review(expected_request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_new_consent_digest_requires_new_attested_review(self):
        args=inputs()
        p=dict(args["reviewed_packet"])
        p["inquiry_intent_sha256"]="e"*64
        args["reviewed_packet"]=p
        with self.assertRaises(Plan1OrderGateClosed):
            build_plan1_private_review_draft(**args)

    def test_contract_substitution_breaks_attestation(self):
        args=inputs()
        p=dict(args["reviewed_packet"])
        p["proofs"]=dict(p["proofs"])
        p["proofs"]["contract_pdf_sha256"]="e"*64
        args["reviewed_packet"]=p
        with self.assertRaises(Plan1OrderGateClosed):
            build_plan1_private_review_draft(**args)

    def test_expiry_cannot_be_extended_after_review(self):
        args=inputs()
        p=dict(args["reviewed_packet"])
        p["expires_at_sec"]+=100000
        args["reviewed_packet"]=p
        with self.assertRaises(Plan1OrderGateClosed):
            build_plan1_private_review_draft(**args)

    def test_payment_cannot_be_inferred_from_private_status(self):
        x=review()
        self.assertEqual(x.state,"PRIVATE_NONPAYABLE_CONTRACT_REVIEW")
        self.assertFalse(x.settlement_verified)

    def test_no_customer_names_emails_wallet_or_kyc_in_repr(self):
        r=repr(review()).lower()
        for needle in ("@example.com", "passport", "tron_wallet_address",
                       "tax_id", "mnemonic", "private_key"):
            self.assertNotIn(needle,r)


if __name__ == "__main__":
    unittest.main()
