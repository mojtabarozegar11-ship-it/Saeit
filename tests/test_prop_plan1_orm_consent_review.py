"""Fail-closed regression for the canonical consent-only ORM adapter."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from prop_firm.buyer_order_review import Plan1OrderGateClosed
from prop_firm.plan1_orm_consent_review import review_existing_interest


class ConsentOnlyOrmReviewTests(SimpleTestCase):
    def call(self, **overrides):
        data = dict(actor=SimpleNamespace(is_authenticated=True, is_active=True, is_staff=True),
                    interest_pk=1, inquiry=None, consent_attestation=None,
                    consent_tag_hex="", consent_key=b"", request_ref="",
                    inquiry_sha256="", consent_evidence_sha256="",
                    private_order_draft=None)
        data.update(overrides)
        return review_existing_interest(**data)

    def test_anonymous_denied_without_database_access(self):
        with patch("prop_firm.plan1_orm_consent_review.transaction.atomic") as atomic:
            with self.assertRaises(Plan1OrderGateClosed):
                self.call(actor=SimpleNamespace(is_authenticated=False, is_active=True, is_staff=True))
            atomic.assert_not_called()

    def test_non_staff_denied_without_database_access(self):
        with patch("prop_firm.plan1_orm_consent_review.transaction.atomic") as atomic:
            with self.assertRaises(Plan1OrderGateClosed):
                self.call(actor=SimpleNamespace(is_authenticated=True, is_active=True, is_staff=False))
            atomic.assert_not_called()

    def test_inactive_staff_denied_without_database_access(self):
        with patch("prop_firm.plan1_orm_consent_review.transaction.atomic") as atomic:
            with self.assertRaises(Plan1OrderGateClosed):
                self.call(actor=SimpleNamespace(is_authenticated=True, is_active=False, is_staff=True))
            atomic.assert_not_called()

    def test_invalid_pk_denied_without_database_access(self):
        with patch("prop_firm.plan1_orm_consent_review.transaction.atomic") as atomic:
            for invalid in (None, True, 0, -1, "1", 1.5):
                with self.subTest(invalid=invalid), self.assertRaises(Plan1OrderGateClosed):
                    self.call(interest_pk=invalid)
            atomic.assert_not_called()
