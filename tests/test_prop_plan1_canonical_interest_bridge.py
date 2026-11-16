"""Synthetic private CRM consent lineage tests; no real customer PII or DB."""
from dataclasses import replace
import hashlib
import hmac
import json
import unittest

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_canonical_interest_bridge import bind_canonical_interest_to_private_inquiry
from test_prop_buyer_precontract_chain import new_inquiry, REF

KEY=b"synthetic-consent-registry-key-NEVER-USE-PRODUCTION-000000"
CONSENT_DIGEST="a"*64


def args():
    inquiry=new_inquiry()
    att={
        "purpose":"mojprop-plan1-optin-lineage-v1",
        "interest_pk":17,"request_ref":REF,
        "inquiry_sha256":inquiry.anonymous_intent_sha256,
        "consent_evidence_sha256":CONSENT_DIGEST,
        "sku":"MOJ-PROP-01","terms_version":"2026-11-15/v1.2",
        "consent_version":"moj-prop-interest-v1",
        "contact_scope":"buyer_requested_one_to_one_plan1_review_only",
        "withdrawn":False,
    }
    return dict(
        canonical_interest=dict(id=17,email="synthetic@example.invalid",
                                plan_code="MOJ-PROP-01",
                                consent_version="moj-prop-interest-v1",
                                source_language="en",status="new"),
        inquiry=inquiry,
        trusted_consent_attestation=att,
        signed_consent_tag_hex=sign(att),
        trusted_consent_key=KEY,
        expected_request_ref=REF,
        expected_interest_pk=17,
        expected_inquiry_sha256=inquiry.anonymous_intent_sha256,
        expected_consent_evidence_sha256=CONSENT_DIGEST,
    )


def sign(att):
    body=json.dumps(att,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    return hmac.new(KEY,body,hashlib.sha256).hexdigest()


def bind(**changes):
    kw=args()
    kw.update(changes)
    return bind_canonical_interest_to_private_inquiry(**kw)


class CanonicalConsentLineageTests(unittest.TestCase):
    def denied(self, **changes):
        with self.assertRaises(Plan1OrderGateClosed):
            bind(**changes)

    def test_canonical_interest_link(self):
        x=bind()
        self.assertEqual((x.canonical_interest_pk,x.request_ref),(17,REF))

    def test_no_personal_email_in_output(self):
        x=bind()
        self.assertNotIn("synthetic@example.invalid",repr(x))

    def test_no_invoice_from_optin(self):
        self.assertFalse(bind().payable)

    def test_no_enrollment_from_optin(self):
        self.assertFalse(bind().enrollment_created)

    def test_no_kyc_claim_from_optin(self):
        self.assertFalse(bind().kyc_proven)

    def test_no_automatic_contact_from_optin(self):
        self.assertFalse(bind().buyer_contact_authorized_by_this_module)

    def test_no_email_disclosure(self):
        self.assertFalse(bind().email_disclosed)

    def test_wrong_interest_pk(self):
        self.denied(expected_interest_pk=18)

    def test_boolean_interest_pk(self):
        self.denied(expected_interest_pk=True)

    def test_zero_interest_pk(self):
        self.denied(expected_interest_pk=0)

    def test_other_request(self):
        self.denied(expected_request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_other_inquiry_digest(self):
        self.denied(expected_inquiry_sha256="f"*64)

    def test_missing_consent_digest(self):
        self.denied(expected_consent_evidence_sha256="0"*64)

    def test_consent_digest_mismatch(self):
        self.denied(expected_consent_evidence_sha256="f"*64)

    def test_wrong_signature(self):
        self.denied(signed_consent_tag_hex="f"*64)

    def test_missing_signature(self):
        self.denied(signed_consent_tag_hex="")

    def test_wrong_key(self):
        self.denied(trusted_consent_key=b"wrong-but-long-independent-consent-key-0000000")

    def test_short_key(self):
        self.denied(trusted_consent_key=b"short")

    def test_string_key(self):
        self.denied(trusted_consent_key=KEY.decode())

    def test_no_canonical_record(self):
        self.denied(canonical_interest=None)

    def test_no_inquiry(self):
        self.denied(inquiry=None)

    def test_missing_canonical_email(self):
        row=args()["canonical_interest"]
        row["email"]=""
        self.denied(canonical_interest=row)

    def test_no_real_email_in_private_output(self):
        row=args()["canonical_interest"]
        row["email"]="another.synthetic@example.invalid"
        x=bind(canonical_interest=row)
        self.assertNotIn(row["email"],repr(x))

    def test_wrong_product_educational_starter(self):
        row=args()["canonical_interest"]
        row["plan_code"]="MOJPROP-STARTER30"
        self.denied(canonical_interest=row)

    def test_wrong_consent_version(self):
        row=args()["canonical_interest"]
        row["consent_version"]="legacy"
        self.denied(canonical_interest=row)

    def test_withdrawn_consent(self):
        row=args()["canonical_interest"]
        row["status"]="withdrawn"
        self.denied(canonical_interest=row)

    def test_already_contacted_requires_new_review(self):
        row=args()["canonical_interest"]
        row["status"]="contacted"
        self.denied(canonical_interest=row)

    def test_unrecognized_status(self):
        row=args()["canonical_interest"]
        row["status"]="paid"
        self.denied(canonical_interest=row)

    def test_unrecognized_language(self):
        row=args()["canonical_interest"]
        row["source_language"]="xx"
        self.denied(canonical_interest=row)

    def test_extra_untrusted_row_field(self):
        row=args()["canonical_interest"]
        row["approved"]=True
        self.denied(canonical_interest=row)

    def test_missing_row_field(self):
        row=args()["canonical_interest"]
        del row["status"]
        self.denied(canonical_interest=row)

    def test_marketing_scope_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["contact_scope"]="marketing"
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_withdrawn_attestation_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["withdrawn"]=True
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_other_interest_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["interest_pk"]=18
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_other_product_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["sku"]="MOJPROP-STARTER30"
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_other_terms_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["terms_version"]="v1.1"
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_other_digest_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["consent_evidence_sha256"]="f"*64
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_other_request_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["request_ref"]="REQUEST-ZYXWVUTSRQPONMLK"
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_attestation_extra_authorization_not_accepted(self):
        att=args()["trusted_consent_attestation"]
        att["invoice_allowed"]=True
        self.denied(trusted_consent_attestation=att,
                    signed_consent_tag_hex=sign(att))

    def test_modified_inquiry_product_not_accepted(self):
        self.denied(inquiry=replace(new_inquiry(),sku="MOJPROP-STARTER30"))

    def test_modified_inquiry_contact_flag_not_accepted(self):
        self.denied(inquiry=replace(new_inquiry(),allowed_to_contact=True))

    def test_modified_inquiry_payment_flag_not_accepted(self):
        self.denied(inquiry=replace(new_inquiry(),payment_allowed=True))

    def test_modified_inquiry_kyc_flag_not_accepted(self):
        self.denied(inquiry=replace(new_inquiry(),kyc_verified=True))

    def test_missing_attestation(self):
        self.denied(trusted_consent_attestation=None)


if __name__=="__main__":
    unittest.main()
