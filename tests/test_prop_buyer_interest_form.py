"""Synthetic Plan 1 pre-inquiry fixtures; never contact a real customer."""
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from prop_firm.buyer_interest_form import (
    _REQUIRED, InterestFormBlocked, validate_private_plan1_interest,
)


def fixture():
    a={key:True for key in _REQUIRED}
    a.update(
        request_ref="REQUEST-ABCDEFGHIJKLMNOP",
        sku="MOJ-PROP-01",
        terms_version="2026-11-15/v1.2",
        self_declared_country="DE",
    )
    return a


def apply(form=None, **kwargs):
    opts=dict(form=fixture() if form is None else form,
              server_received_at=datetime(2026,11,16,tzinfo=timezone.utc))
    opts.update(kwargs)
    return validate_private_plan1_interest(**opts)


class Plan1PrivateInterestFormTests(unittest.TestCase):
    def rejects(self, key, value):
        f=fixture()
        f[key]=value
        with self.assertRaises(InterestFormBlocked):
            apply(f)

    def test_source_only_intent_is_unverified(self):
        x=apply()
        self.assertEqual(x.state,"unverified_private_interest")

    def test_source_only_intent_cannot_contact_user(self):
        self.assertFalse(apply().allowed_to_contact)

    def test_source_only_intent_cannot_invoice(self):
        self.assertFalse(apply().payment_allowed)

    def test_source_only_intent_cannot_enroll(self):
        self.assertFalse(apply().challenge_enrollment_allowed)

    def test_self_attested_age_is_not_verified_age(self):
        self.assertFalse(apply().age_independently_verified)

    def test_self_declared_country_is_not_legal_eligibility(self):
        self.assertFalse(apply().legal_country_verified)

    def test_form_is_not_kyc(self):
        self.assertFalse(apply().kyc_verified)

    def test_form_is_not_customer_contract(self):
        self.assertFalse(apply().customer_contract_executed)

    def test_contact_request_not_marketing_optin(self):
        self.assertFalse(apply().marketing_opt_in)

    def test_draft_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            apply().sku="MOJPROP-STARTER30"

    def test_keeps_original_case_and_terms(self):
        x=apply()
        self.assertEqual((x.sku,x.terms_version,x.declared_country),
                         ("MOJ-PROP-01","2026-11-15/v1.2","DE"))

    def test_produces_digest_not_identity_document(self):
        x=apply()
        self.assertEqual(len(x.anonymous_intent_sha256),64)
        self.assertNotIn("identity_document",repr(x))

    def test_no_raw_contact_data_field_accepted(self):
        f=fixture()
        f["email"]="private@example.com"
        with self.assertRaises(InterestFormBlocked):
            apply(f)

    def test_no_unrecognized_extra_field(self):
        f=fixture()
        f["wallet"]="some-address"
        with self.assertRaises(InterestFormBlocked):
            apply(f)

    def test_cannot_remove_required_field(self):
        f=fixture()
        f.pop("ack_refund_policy_requires_legal_review")
        with self.assertRaises(InterestFormBlocked):
            apply(f)

    def test_all_comprehension_fields_independently_required(self):
        protected=set(_REQUIRED)-{
            "request_ref","sku","terms_version","self_declared_country"
        }
        self.assertGreaterEqual(len(protected),10)
        for field in sorted(protected):
            f=fixture()
            f[field]=False
            with self.subTest(field=field), self.assertRaises(InterestFormBlocked):
                apply(f)

    def test_truthy_integer_checkbox_is_not_consent(self):
        self.rejects("contact_for_this_inquiry_requested",1)

    def test_string_yes_is_not_informed_consent(self):
        self.rejects("ack_evaluation_is_simulated","yes")

    def test_wrong_product_sku_fails(self):
        self.rejects("sku","MOJPROP-STARTER30")

    def test_wrong_terms_revision_fails(self):
        self.rejects("terms_version","v1.1")

    def test_invalid_country_fails(self):
        for val in ("de","D3","DEU","",None,23):
            with self.subTest(country=repr(val)):
                self.rejects("self_declared_country",val)

    def test_noncanonical_or_spoofed_request_ref_fails(self):
        for val in ("REQUEST-1","request-ABCDEF1234567890",
                    "REQUEST-AAAA\u202e123456789","REQUEST-../../foo"):
            with self.subTest(ref=val):
                self.rejects("request_ref",val)

    def test_naive_clock_fails(self):
        with self.assertRaises(InterestFormBlocked):
            apply(server_received_at=datetime(2026,11,16))

    def test_non_datetime_clock_fails(self):
        with self.assertRaises(InterestFormBlocked):
            apply(server_received_at="2026-11-16")

    def test_intent_digest_changes_when_country_changes(self):
        f=fixture()
        a=apply(f).anonymous_intent_sha256
        f["self_declared_country"]="FR"
        self.assertNotEqual(a,apply(f).anonymous_intent_sha256)

    def test_timestamp_is_normalized_utc(self):
        x=apply()
        self.assertTrue(x.received_at.endswith("+00:00"))

    def test_no_api_or_database_dependency(self):
        x=apply()
        self.assertEqual(x.request_ref,fixture()["request_ref"])


if __name__=="__main__":
    unittest.main()
