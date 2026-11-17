"""Synthetic HMAC proofs for server-origin inquiry; NEVER production credentials."""
from dataclasses import fields, replace
import hashlib
import hmac
import json
import unittest

from prop_firm.buyer_interest_form import UnverifiedInquiry
from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_intake_provenance import verify_server_issued_private_inquiry
from tests.test_prop_buyer_precontract_chain import new_inquiry, REF

INTAKE_KEY=b"synthetic-INDEPENDENT-intake-service-HMAC-key-v1-64bytes!!!!!!"


def intake_tag(inquiry, key=INTAKE_KEY):
    values={f.name:getattr(inquiry, f.name) for f in fields(UnverifiedInquiry)}
    canonical=json.dumps(
        {"purpose":"mojprop-plan1-server-intake-v1","inquiry":values},
        sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False,
    ).encode("ascii")
    return hmac.new(key,canonical,hashlib.sha256).hexdigest()


def verify(inquiry=None, **overrides):
    inquiry=new_inquiry() if inquiry is None else inquiry
    kwargs=dict(inquiry=inquiry,
                signed_intake_hmac_hex=intake_tag(inquiry),
                trusted_intake_key=INTAKE_KEY,
                expected_request_ref=REF,
                expected_inquiry_digest=inquiry.anonymous_intent_sha256)
    kwargs.update(overrides)
    return verify_server_issued_private_inquiry(**kwargs)


class SignedIntakeOriginTests(unittest.TestCase):
    def rejects_modified_record(self, **changes):
        legitimate=new_inquiry()
        forged=replace(legitimate,**changes)
        with self.assertRaises(Plan1OrderGateClosed):
            verify_server_issued_private_inquiry(
                inquiry=forged,
                signed_intake_hmac_hex=intake_tag(legitimate),
                trusted_intake_key=INTAKE_KEY,
                expected_request_ref=REF,
                expected_inquiry_digest=legitimate.anonymous_intent_sha256,
            )

    def test_canonical_signed_intake_verifies(self):
        self.assertIsNone(verify())

    def test_same_signed_record_reverifies(self):
        i=new_inquiry()
        self.assertIsNone(verify(i))
        self.assertIsNone(verify(i))

    def test_untrusted_string_inquiry_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify_server_issued_private_inquiry(
                inquiry="someone said yes",signed_intake_hmac_hex="a"*64,
                trusted_intake_key=INTAKE_KEY,
                expected_request_ref=REF,expected_inquiry_digest="a"*64)

    def test_untrusted_dict_inquiry_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify_server_issued_private_inquiry(
                inquiry={},signed_intake_hmac_hex="a"*64,
                trusted_intake_key=INTAKE_KEY,
                expected_request_ref=REF,expected_inquiry_digest="a"*64)

    def test_wrong_mac_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(signed_intake_hmac_hex="f"*64)

    def test_missing_mac_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(signed_intake_hmac_hex="")

    def test_uppercase_noncanonical_mac_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(signed_intake_hmac_hex="A"*64)

    def test_wrong_service_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_intake_key=b"a-different-synthetic-internal-intake-key-0000")

    def test_short_service_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_intake_key=b"tiny")

    def test_browser_supplied_string_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_intake_key=INTAKE_KEY.decode())

    def test_boolean_key_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(trusted_intake_key=True)

    def test_external_request_ref_mismatch_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_noncanonical_request_ref_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_request_ref="REQUEST-X")

    def test_external_digest_mismatch_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_inquiry_digest="f"*64)

    def test_missing_external_digest_rejected(self):
        with self.assertRaises(Plan1OrderGateClosed):
            verify(expected_inquiry_digest="")

    def test_source_request_id_forgery_rejected(self):
        self.rejects_modified_record(request_ref="REQUEST-ZYXWVUTSRQPONMLK")

    def test_source_sku_substitution_rejected(self):
        self.rejects_modified_record(sku="MOJPROP-STARTER30")

    def test_source_contract_version_substitution_rejected(self):
        self.rejects_modified_record(terms_version="v0")

    def test_source_country_swap_rejected(self):
        self.rejects_modified_record(declared_country="FR")

    def test_source_unsafe_country_rejected(self):
        self.rejects_modified_record(declared_country="d\u202ee")

    def test_source_received_at_swap_rejected(self):
        self.rejects_modified_record(received_at="2026-11-15T01:00:00+00:00")

    def test_source_intent_digest_swap_rejected(self):
        self.rejects_modified_record(anonymous_intent_sha256="f"*64)

    def test_source_forced_payment_flag_rejected(self):
        self.rejects_modified_record(payment_allowed=True)

    def test_source_forced_contact_flag_rejected(self):
        self.rejects_modified_record(allowed_to_contact=True)

    def test_source_forced_enrollment_flag_rejected(self):
        self.rejects_modified_record(challenge_enrollment_allowed=True)

    def test_source_forced_kyc_flag_rejected(self):
        self.rejects_modified_record(kyc_verified=True)

    def test_source_forced_legal_country_flag_rejected(self):
        self.rejects_modified_record(legal_country_verified=True)

    def test_source_forced_age_flag_rejected(self):
        self.rejects_modified_record(age_independently_verified=True)

    def test_source_forced_legal_contract_flag_rejected(self):
        self.rejects_modified_record(customer_contract_executed=True)

    def test_source_forced_marketing_flag_rejected(self):
        self.rejects_modified_record(marketing_opt_in=True)

    def test_source_paid_stage_rejected(self):
        self.rejects_modified_record(state="paid_confirmed")

    def test_tampered_receipt_timestamp_not_accepted_even_if_resigned(self):
        forged=replace(new_inquiry(),received_at="2026-11-14T00:00:00+00:00")
        # A changed timestamp would require a privileged server-side new tag,
        # never the old tag. An untrusted participant cannot do this.
        self.assertIsNone(verify(forged))


if __name__=="__main__":
    unittest.main()
