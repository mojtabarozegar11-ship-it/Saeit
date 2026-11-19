"""Fail-closed independent email-control OTP receipt ↔ canonical consent tests.

Every receipt is SYNTHETIC; none is a real OTP, buyer, KYC, payment,
customer communication or production service enrollment.
"""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import hmac
import json
import unittest

from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_canonical_interest_bridge import PrivateInterestLink
from prop_firm.plan1_demo_email_interest import (
    OTP_SCHEMA, OTP_PURPOSE, OTP_FIELDS, MAX_OTP_LIFETIME_SEC,
    review_existing_demo_interest_otp,
)

OTP_KEY = b"synthetic-otp-provider-key-only-unit-tests-not-production-11111"
CONSENT_KEY = b"synthetic-consent-service-key-only-tests-not-production-22"
NOW = 1795000000
REQUEST = "REQUEST-ABCDEFGHIJKLMNOP"
DIGEST = "a"*64


def consent():
    return PrivateInterestLink(
        canonical_interest_pk=91, request_ref=REQUEST,
        inquiry_sha256=DIGEST, consent_evidence_sha256="b"*64,
    )


def receipt():
    return {
        "schema": OTP_SCHEMA, "purpose": OTP_PURPOSE,
        "interest_pk": 91, "request_ref": REQUEST,
        "inquiry_sha256": DIGEST,
        "sku": "MOJ-PROP-01",
        "terms_version": "2026-11-15/v1.2",
        "email_control_verified": True,
        "issued_at_sec": NOW-30, "expires_at_sec": NOW+60,
    }


def sign(v):
    data=json.dumps(v,ensure_ascii=True,sort_keys=True,
                    separators=(",",":"),allow_nan=False).encode("ascii")
    return hmac.new(OTP_KEY,data,sha256).hexdigest()


def review(**overrides):
    packet=receipt()
    data=dict(
        consent_link=consent(), signed_otp_receipt=packet,
        otp_tag_hex=sign(packet), trusted_otp_service_key=OTP_KEY,
        trusted_consent_service_key=CONSENT_KEY,
        declared_country="DE", age_18_self_attested=True,
        server_now_sec=NOW,
    )
    data.update(overrides)
    return review_existing_demo_interest_otp(**data)


class EmailVerifiedDemoOnlyInterestTests(unittest.TestCase):
    def denied(self, **overrides):
        with self.assertRaises((Plan1OrderGateClosed, TypeError)):
            review(**overrides)

    def modified_receipt_denied(self, key, value):
        v=receipt()
        if value is None:
            v.pop(key)
        else:
            v[key]=value
        with self.assertRaises((Plan1OrderGateClosed, TypeError)):
            review(signed_otp_receipt=v,otp_tag_hex=sign(v))

    def test_valid_signed_otp_yields_private_review_only(self):
        self.assertEqual(review().stage,"PRIVATE_EMAIL_VERIFIED_INTEREST_ONLY")

    def test_correct_only_plan1_sku(self):
        self.assertEqual(review().sku,"MOJ-PROP-01")

    def test_correct_historical_version_binding(self):
        self.assertEqual(review().terms_version,"2026-11-15/v1.2")

    def test_existing_consent_identity_preserved(self):
        self.assertEqual((review().interest_pk,review().request_ref),(91,REQUEST))

    def test_otp_content_digest_recorded_without_raw_email(self):
        self.assertEqual(len(review().email_otp_receipt_digest),64)
        self.assertNotIn("@",repr(review()))

    def test_otp_service_attests_control_not_identity(self):
        self.assertTrue(review().email_control_attested_by_trusted_otp_service)
        self.assertFalse(review().actual_kyc_verified)

    def test_age_only_self_attested(self):
        self.assertTrue(review().age_18_self_attested_not_verified)
        self.assertFalse(review().buyer_legal_age_verified)

    def test_country_only_self_declared(self):
        self.assertTrue(review().country_self_declared_not_verified)
        self.assertFalse(review().buyer_country_legally_permitted)

    def test_two_demo_phases_without_live_account(self):
        self.assertTrue(review().two_challenge_phases_simulated)
        self.assertFalse(review().live_litefinance_account_required_for_demo)

    def test_live_broker_kyc_not_required_to_register_demo_interest(self):
        self.assertFalse(review().live_broker_kyc_required_for_demo_as_such)

    def test_no_payable_invoice(self):
        self.assertFalse(review().payable_invoice)

    def test_no_payment_authorization(self):
        self.assertFalse(review().payment_authorized)

    def test_no_demo_activation(self):
        self.assertFalse(review().demo_account_activated)

    def test_no_real_activation(self):
        self.assertFalse(review().real_account_activated)

    def test_no_full_buyer_contract_signed(self):
        self.assertFalse(review().buyer_signed_contract_verified)

    def test_no_treasury_funding_proven(self):
        self.assertFalse(review().merchant_funding_verified)

    def test_no_merchant_legality_proven(self):
        self.assertFalse(review().purchase_legality_verified)

    def test_no_marketing_inferred(self):
        self.assertFalse(review().marketing_consent)

    def test_no_contact_permission_inferred(self):
        self.assertFalse(review().contact_permission_created)

    def test_private_record_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            review().payable_invoice=True

    def test_missing_consent_denied(self):
        self.denied(consent_link=None)

    def test_consent_wrong_sku_denied(self):
        self.denied(consent_link=replace(consent(),sku="MOJPROP-STARTER30"))

    def test_consent_wrong_terms_denied(self):
        self.denied(consent_link=replace(consent(),terms_version="old-version"))

    def test_consent_forged_paid_denied(self):
        self.denied(consent_link=replace(consent(),payable=True))

    def test_consent_forged_contact_denied(self):
        self.denied(consent_link=replace(consent(),buyer_contact_authorized_by_this_module=True))

    def test_consent_forged_kyc_denied(self):
        self.denied(consent_link=replace(consent(),kyc_proven=True))

    def test_consent_forged_enrollment_denied(self):
        self.denied(consent_link=replace(consent(),enrollment_created=True))

    def test_consent_email_disclosed_denied(self):
        self.denied(consent_link=replace(consent(),email_disclosed=True))

    def test_wrong_country_code_denied(self):
        for c in ("de","D1","DEU","",None,True):
            with self.subTest(country=c):
                self.denied(declared_country=c)

    def test_non_true_age_denied(self):
        for v in (False,1,"yes",None):
            with self.subTest(value=v):
                self.denied(age_18_self_attested=v)

    def test_missing_otp_packet_denied(self):
        self.denied(signed_otp_receipt=None)

    def test_wrong_otp_signature_denied(self):
        self.denied(otp_tag_hex="f"*64)

    def test_missing_otp_signature_denied(self):
        self.denied(otp_tag_hex="")

    def test_wrong_otp_provider_key_denied(self):
        self.denied(trusted_otp_service_key=b"another-test-only-fake-otp-provider-32-byte-key")

    def test_missing_otp_provider_key_denied(self):
        self.denied(trusted_otp_service_key=b"")

    def test_reused_otp_and_consent_key_denied(self):
        self.denied(trusted_consent_service_key=OTP_KEY)

    def test_nonbytes_otp_key_denied(self):
        self.denied(trusted_otp_service_key=OTP_KEY.decode())

    def test_nonbytes_consent_key_denied(self):
        self.denied(trusted_consent_service_key=CONSENT_KEY.decode())

    def test_otp_only_10_minutes_maximum(self):
        self.assertEqual(MAX_OTP_LIFETIME_SEC,600)

    def test_expired_otp_denied(self):
        self.denied(server_now_sec=NOW+60)

    def test_otp_from_future_denied(self):
        self.denied(server_now_sec=NOW-31)

    def test_boolean_now_denied(self):
        self.denied(server_now_sec=True)

    def test_otp_lifetime_over_ten_minutes_denied(self):
        v=receipt();v["expires_at_sec"]=v["issued_at_sec"]+601
        self.denied(signed_otp_receipt=v,otp_tag_hex=sign(v))

    def test_otp_receipt_extra_invoice_flag_denied(self):
        self.modified_receipt_denied("payable_invoice",True)

    def test_otp_receipt_missing_purpose_denied(self):
        self.modified_receipt_denied("purpose",None)

    def test_otp_receipt_wrong_purpose_denied(self):
        self.modified_receipt_denied("purpose","mass_email_marketing")

    def test_otp_receipt_other_interest_denied(self):
        self.modified_receipt_denied("interest_pk",92)

    def test_otp_receipt_other_request_denied(self):
        self.modified_receipt_denied("request_ref","REQUEST-ZYXWVUTSRQPONMLK")

    def test_otp_receipt_other_digest_denied(self):
        self.modified_receipt_denied("inquiry_sha256","f"*64)

    def test_otp_receipt_educational_sku_denied(self):
        self.modified_receipt_denied("sku","MOJPROP-STARTER30")

    def test_otp_receipt_wrong_terms_denied(self):
        self.modified_receipt_denied("terms_version","v1.1")

    def test_otp_receipt_false_control_denied(self):
        self.modified_receipt_denied("email_control_verified",False)

    def test_otp_receipt_string_true_denied(self):
        self.modified_receipt_denied("email_control_verified","true")

    def test_otp_receipt_zero_issued_time_denied(self):
        self.modified_receipt_denied("issued_at_sec",0)

    def test_otp_receipt_boolean_issued_time_denied(self):
        self.modified_receipt_denied("issued_at_sec",True)

    def test_otp_receipt_boolean_expiry_denied(self):
        self.modified_receipt_denied("expires_at_sec",True)

    def test_otp_receipt_schema_drift_denied(self):
        self.modified_receipt_denied("schema","unreviewed-v0")

    def test_ref_from_other_customer_denied(self):
        self.denied(consent_link=replace(consent(),canonical_interest_pk=93))

    def test_forged_nonsha_intent_denied(self):
        self.denied(consent_link=replace(consent(),inquiry_sha256="unknown"))

    def test_otp_receipt_has_only_intended_fields(self):
        self.assertEqual(set(receipt()),OTP_FIELDS)

    def test_initial_synthetic_receipt_remains_without_raw_email(self):
        self.assertNotIn("email",receipt())
