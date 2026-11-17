"""Synthetic buyer-specific amended-terms provenance tests, no legal signatures.

An HMAC digest cannot authenticate real-world customer identity, capital,
broker funding, marketing consent or a sale; all tests are source-only.
"""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import hmac
import json
import unittest

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_orm_consent_review import VerifiedPrivateHandoff
from prop_firm.plan1_buyer_no_social_amendment import (
    buyer_no_social_post_amendment, current_plan1_buyer_copy,
)
from prop_firm.plan1_revised_buyer_terms_link import (
    SCHEMA, PURPOSE, REQUIRED_FIELDS, bind_revised_buyer_terms,
)

ACCEPT_KEY=b"synthetic-independent-acceptance-service-key-not-production-1111"
LEGAL_KEY=b"synthetic-independent-legal-review-key-not-production-222222"
NOW=1795000000
PRIOR_DOC="a"*64
CURRENT_DOC="b"*64
CURRENT_ACCEPTANCE="c"*64


def handoff():
    return VerifiedPrivateHandoff(
        interest_pk=37, request_ref="REQUEST-ABCDEFGHIJKLMNOP",
        buyer_ref="BUYER-ABCDEFGHIJKLMNOP",seller_ref="SELLER-ABCDEFGHIJKLMNOP",
        private_review_ref="PROP1-REVIEW-"+"D"*32,
        inquiry_sha256="e"*64,contract_pdf_sha256=PRIOR_DOC,
        refund_disclosure_sha256="f"*64,buyer_signature_proof_sha256="1"*64,
        seller_signature_proof_sha256="2"*64, expires_at_sec=NOW+1800,
    )


def packet(h=None):
    h=handoff() if h is None else h
    w=buyer_no_social_post_amendment()
    c=current_plan1_buyer_copy()
    return {
        "schema":SCHEMA,"purpose":PURPOSE,
        "interest_pk":h.interest_pk,
        "request_ref":h.request_ref,"buyer_ref":h.buyer_ref,
        "seller_ref":h.seller_ref,"sku":"MOJ-PROP-01",
        "historical_terms_version":"2026-11-15/v1.2",
        "amendment_version":w.amendment_version,
        "prior_contract_pdf_sha256":h.contract_pdf_sha256,
        "accepted_buyer_contract_pdf_sha256":CURRENT_DOC,
        "buyer_acceptance_proof_sha256":CURRENT_ACCEPTANCE,
        "current_copy_sha256":c.digest_sha256,
        "no_post_waiver_sha256":w.digest_sha256,
        "fee_native_sun":30000000,"network":"TRON-mainnet",
        "demo_phase_count":2,"no_real_account_during_evaluation":True,
        "live_broker_only_after_both_verified_passes":True,
        "no_buyer_instagram_or_facebook_post":True,
        "posting_is_not_pass_condition":True,
        "legal_purchase_screening_still_applies":True,
        "accepted_at_sec":NOW-90,"expires_at_sec":NOW+300,
    }


def sign(value):
    raw=json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(",",":"),
                   allow_nan=False).encode("ascii")
    return hmac.new(ACCEPT_KEY,raw,sha256).hexdigest()


def review(**changes):
    p=packet()
    kw=dict(
        existing_private_handoff=handoff(),signed_acceptance_packet=p,
        acceptance_hmac_hex=sign(p),
        trusted_acceptance_provider_key=ACCEPT_KEY,
        trusted_independent_reviewer_key=LEGAL_KEY,
        expected_accepted_pdf_sha256=CURRENT_DOC,
        expected_buyer_signature_proof_sha256=CURRENT_ACCEPTANCE,
        server_now_sec=NOW,
    )
    kw.update(changes)
    return bind_revised_buyer_terms(**kw)


class RevisedBuyerTermsLinkTests(unittest.TestCase):
    def denied(self,**changed):
        with self.assertRaises((Plan1OrderGateClosed,TypeError,ValueError)):
            review(**changed)

    def mutate_packet(self,key,value):
        p=packet()
        if value is None:
            p.pop(key)
        else:
            p[key]=value
        self.denied(signed_acceptance_packet=p,acceptance_hmac_hex=sign(p))

    def test_existing_private_review_bound_to_same_buyer(self):
        x=review()
        self.assertEqual(x.buyer_ref,handoff().buyer_ref)
        self.assertEqual(x.interest_pk,37)

    def test_original_contract_digest_is_bound(self):
        self.assertEqual(review().prior_contract_digest,PRIOR_DOC)

    def test_new_buyer_specific_document_digest_is_bound(self):
        self.assertEqual(review().revised_buyer_document_digest,CURRENT_DOC)

    def test_new_current_two_phase_no_social_copy_is_bound(self):
        self.assertEqual(review().current_disclosure_digest,
                         current_plan1_buyer_copy().digest_sha256)

    def test_waiver_source_digest_is_bound(self):
        self.assertEqual(review().waiver_digest,
                         buyer_no_social_post_amendment().digest_sha256)

    def test_original_terms_version_is_not_silently_changed(self):
        self.assertEqual(review().historical_terms_version,"2026-11-15/v1.2")

    def test_only_real_challenge_product(self):
        self.assertEqual(review().sku,"MOJ-PROP-01")

    def test_no_customer_invoice_created(self):
        self.assertFalse(review().invoice_created)

    def test_no_receipt_claimed(self):
        self.assertFalse(review().customer_payment_received)

    def test_no_live_broker_account_created(self):
        self.assertFalse(review().real_account_created)

    def test_no_demo_account_created(self):
        self.assertFalse(review().demo_account_created)

    def test_no_legal_signing_proven_by_hashes_alone(self):
        self.assertFalse(review().buyer_signature_legally_verified_by_this_code)

    def test_no_full_customer_kyc_proven(self):
        self.assertFalse(review().independent_purchase_kyc_verified_by_this_code)

    def test_no_merchant_license_proven(self):
        self.assertFalse(review().seller_authority_verified_by_this_code)

    def test_no_real_funding_proven(self):
        self.assertFalse(review().payer_funding_verified_by_this_code)

    def test_no_marketing_optin_proven(self):
        self.assertFalse(review().marketing_consent)

    def test_no_buyer_post_obligation(self):
        self.assertEqual(review().buyer_social_posts_required,0)

    def test_reference_output_digest_is_not_raw_signature(self):
        self.assertEqual(len(review().acceptance_reference_digest),64)
        self.assertNotIn("@",repr(review()))

    def test_result_is_immutable_and_nonpayable(self):
        with self.assertRaises(FrozenInstanceError):
            review().invoice_created=True

    def test_missing_handoff_denied(self):
        self.denied(existing_private_handoff=None)

    def test_forged_post_payment_handoff_denied(self):
        self.denied(existing_private_handoff=replace(handoff(),payment_confirmed=True))

    def test_forged_enrollment_handoff_denied(self):
        self.denied(existing_private_handoff=replace(handoff(),enrollment_created=True))

    def test_missing_original_contract_digest_denied(self):
        self.denied(existing_private_handoff=replace(handoff(),contract_pdf_sha256="0"*64))

    def test_expired_original_private_review_denied(self):
        self.denied(server_now_sec=NOW+1800)

    def test_missing_acceptance_packet_denied(self):
        self.denied(signed_acceptance_packet=None)

    def test_wrong_acceptance_hmac_denied(self):
        self.denied(acceptance_hmac_hex="f"*64)

    def test_missing_provider_key_denied(self):
        self.denied(trusted_acceptance_provider_key=b"")

    def test_reused_signer_and_reviewer_keys_denied(self):
        self.denied(trusted_independent_reviewer_key=ACCEPT_KEY)

    def test_cross_buyer_review_denied(self):
        self.denied(existing_private_handoff=replace(
            handoff(),buyer_ref="BUYER-ZYXWVUTSRQPONMLK"))

    def test_cross_seller_review_denied(self):
        self.denied(existing_private_handoff=replace(
            handoff(),seller_ref="SELLER-ZYXWVUTSRQPONMLK"))

    def test_wrong_trusted_signed_pdf_denied(self):
        self.denied(expected_accepted_pdf_sha256="9"*64)

    def test_wrong_trusted_buyer_signature_denied(self):
        self.denied(expected_buyer_signature_proof_sha256="9"*64)

    def test_expired_acceptance_denied(self):
        self.denied(server_now_sec=NOW+300)

    def test_boolean_clock_denied(self):
        self.denied(server_now_sec=True)

    def test_future_dated_acceptance_denied(self):
        self.denied(server_now_sec=NOW-91)

    def test_old_social_requirement_must_be_waived(self):
        self.mutate_packet("no_buyer_instagram_or_facebook_post",False)

    def test_old_posting_condition_must_be_waived(self):
        self.mutate_packet("posting_is_not_pass_condition",False)

    def test_no_live_account_during_evaluation(self):
        self.mutate_packet("no_real_account_during_evaluation",False)

    def test_real_broker_only_after_both_passes(self):
        self.mutate_packet("live_broker_only_after_both_verified_passes",False)

    def test_legal_purchase_screening_still_required(self):
        self.mutate_packet("legal_purchase_screening_still_applies",False)

    def test_educational_sku_forbidden(self):
        self.mutate_packet("sku","MOJPROP-STARTER30")

    def test_wrong_native_fee_forbidden(self):
        self.mutate_packet("fee_native_sun",29999999)

    def test_fake_USD_network_forbidden(self):
        self.mutate_packet("network","USD")

    def test_one_demo_phase_forbidden(self):
        self.mutate_packet("demo_phase_count",1)

    def test_old_social_waiver_digest_forbidden(self):
        self.mutate_packet("no_post_waiver_sha256","f"*64)

    def test_old_disclosure_digest_forbidden(self):
        self.mutate_packet("current_copy_sha256","f"*64)

    def test_old_contract_substitution_forbidden(self):
        self.mutate_packet("prior_contract_pdf_sha256","f"*64)

    def test_nonbuyer_specific_acceptance_forbidden(self):
        self.mutate_packet("buyer_acceptance_proof_sha256","f"*64)

    def test_wrong_accepted_pdf_hash_forbidden(self):
        self.mutate_packet("accepted_buyer_contract_pdf_sha256","f"*64)

    def test_other_request_reference_forbidden(self):
        self.mutate_packet("request_ref","REQUEST-ZYXWVUTSRQPONMLK")

    def test_missing_amendment_version_forbidden(self):
        self.mutate_packet("amendment_version",None)

    def test_missing_buyer_signature_proof_forbidden(self):
        self.mutate_packet("buyer_acceptance_proof_sha256",None)

    def test_unrecognized_paid_state_forbidden(self):
        self.mutate_packet("invoice_authorized",True)

    def test_exact_signed_terms_document_schema(self):
        self.assertEqual(set(packet()),REQUIRED_FIELDS)

    def test_end_to_end_is_only_private_provenance(self):
        self.assertEqual(review().status,"PRIVATE_BUYER_TERMS_PROVENANCE_REVIEW_ONLY")
