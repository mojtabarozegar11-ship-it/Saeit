"""Regression checks for the private PropInterest ORM review adapter."""
from unittest.mock import patch
from django.test import TestCase
from prop_firm.consent_review_bridge import BridgeClosed
from prop_firm.consent_review_orm import review_existing_interest
from prop_firm.lead_models import PropInterest

HASH = "a" * 64


class ConsentORMReviewTests(TestCase):
    def setUp(self):
        self.lead = PropInterest.objects.create(
            email="private-buyer@example.invalid", plan_code="MOJ-PROP-01",
            consent_version="moj-prop-interest-v1", status="new",
        )
        self.kw = dict(
            interest_pk=self.lead.pk,
            independently_verified_interest_pk=self.lead.pk,
            independent_buyer_link_verified=True,
            authenticated_buyer_ref="verified-private-buyer",
            signed_customer_terms_sha256=HASH,
            trusted_contract_sha256=HASH,
            trusted_gate_evidence={},
        )

    def test_missing_interest_denied(self):
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**{**self.kw, "interest_pk": 9999999})

    def test_boolean_identifier_denied(self):
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**{**self.kw, "interest_pk": True})

    def test_mismatched_binding_denied(self):
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**{**self.kw, "independently_verified_interest_pk": 12345})

    def test_unverified_binding_denied(self):
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**{**self.kw, "independent_buyer_link_verified": False})

    def test_withdrawn_denied(self):
        self.lead.status = "withdrawn"
        self.lead.save()
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**self.kw)

    def test_unknown_consent_version_denied(self):
        self.lead.consent_version = "unknown"
        self.lead.save()
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**self.kw)

    def test_wrong_sku_denied(self):
        self.lead.plan_code = "STARTER30"
        self.lead.save()
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**self.kw)

    def test_contract_mismatch_denied(self):
        with self.assertRaises(BridgeClosed):
            review_existing_interest(**{**self.kw, "trusted_contract_sha256": "b"*64})

    def test_empty_gates_remain_private_review(self):
        result = review_existing_interest(**self.kw)
        self.assertFalse(result.invoice_authorized)
        self.assertFalse(result.payment_authorized)
        self.assertFalse(result.enrollment_authorized)
        self.assertFalse(result.marketing_authorized)
        self.assertTrue(result.missing_gates)
        self.assertEqual(result.state, "private_review_only")
        self.assertNotIn("private-buyer", repr(result))
