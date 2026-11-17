"""C150: no silently resurrected buyer contact consent during admin follow-up.

All records are synthetic and live only in the ephemeral Django test database.
No buyer mail, real payment, cPanel DB write, site deploy or broker action.
"""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models.query import QuerySet
from django.test import TestCase

from prop_firm.lead_models import PropInterest


class PropInterestTerminalConsentRowLockTests(TestCase):
    def setUp(self):
        self.lead = PropInterest.objects.create(
            email="c150-verified-test@farmco.org",
            plan_code="MOJ-PROP-01", source_language="fa",
            consent_version="moj-prop-interest-v1", status="new",
        )

    def test_new_and_contacted_can_transition_only_by_validated_save(self):
        self.lead.status = "contacted"
        self.lead.save(update_fields=["status", "updated_at"])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, "contacted")
        self.assertEqual(self.lead.source_language, "fa")

    def test_existing_save_calls_select_for_update_while_atomic(self):
        real_select = QuerySet.select_for_update
        calls = []
        def traced_select(qs, *args, **kwargs):
            if qs.model is PropInterest:
                calls.append(connection.in_atomic_block)
            return real_select(qs, *args, **kwargs)
        with patch.object(QuerySet, "select_for_update", traced_select):
            self.lead.status = "contacted"
            self.lead.save(update_fields=["status"])
        self.assertEqual(calls, [True], "row read must be locked until save finishes")

    def test_existing_save_starts_a_transaction_inside_its_own_method(self):
        with patch("prop_firm.lead_models.transaction.atomic", wraps=transaction.atomic) as observed:
            self.lead.status = "contacted"
            self.lead.save(update_fields=["status"])
        observed.assert_called_once_with()

    def test_withdrawn_is_terminal_even_with_stale_loaded_instance(self):
        stale = PropInterest.objects.get(pk=self.lead.pk)
        PropInterest.objects.filter(pk=self.lead.pk).update(status="withdrawn")
        stale.status = "contacted"
        with self.assertRaises(ValidationError):
            stale.save(update_fields=["status"])
        self.assertEqual(PropInterest.objects.get(pk=self.lead.pk).status, "withdrawn")

    def test_owner_can_withdraw_after_contacted_and_cannot_revive(self):
        self.lead.status = "contacted"
        self.lead.save(update_fields=["status"])
        self.lead.status = "withdrawn"
        self.lead.save(update_fields=["status"])
        self.lead.status = "new"
        with self.assertRaises(ValidationError):
            self.lead.save(update_fields=["status"])
        self.assertEqual(PropInterest.objects.get(pk=self.lead.pk).status, "withdrawn")

    def test_withdrawn_identical_status_save_is_allowed_without_reactivation(self):
        self.lead.status = "withdrawn"
        self.lead.save(update_fields=["status"])
        self.lead.save(update_fields=["status", "updated_at"])
        self.assertEqual(PropInterest.objects.get(pk=self.lead.pk).status, "withdrawn")

    def test_contact_origin_cannot_be_reassigned_by_model_save(self):
        for field, altered in (
            ("email", "other-real@farmco.org"),
            ("plan_code", "MOJPROP-STARTER30"),
            ("source_language", "en"),
            ("consent_version", "different-version"),
        ):
            fresh = PropInterest.objects.get(pk=self.lead.pk)
            setattr(fresh, field, altered)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                fresh.save(update_fields=[field])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.email, "c150-verified-test@farmco.org")
        self.assertEqual(self.lead.plan_code, "MOJ-PROP-01")

    def test_withdrawn_get_or_create_can_never_count_as_new_qualified_buyer(self):
        self.lead.status = "withdrawn"
        self.lead.save(update_fields=["status"])
        found, created = PropInterest.objects.get_or_create(
            email="c150-verified-test@farmco.org",
            defaults={"status": "new", "plan_code": "MOJ-PROP-01"},
        )
        self.assertFalse(created)
        self.assertEqual(found.status, "withdrawn")
        self.assertEqual(PropInterest.objects.count(), 1)

    def test_bulk_status_promotion_remains_blocked_and_withdrawal_is_allowed(self):
        with self.assertRaises(ValidationError):
            PropInterest.objects.filter(pk=self.lead.pk).update(status="contacted")
        self.assertEqual(
            PropInterest.objects.filter(pk=self.lead.pk).update(status="withdrawn"), 1,
        )
        self.assertEqual(PropInterest.objects.get(pk=self.lead.pk).status, "withdrawn")

    def test_new_record_save_does_not_require_existing_row_lock(self):
        calls = []
        real_select = QuerySet.select_for_update
        def traced_select(qs, *args, **kwargs):
            if qs.model is PropInterest:
                calls.append(True)
            return real_select(qs, *args, **kwargs)
        with patch.object(QuerySet, "select_for_update", traced_select):
            lead = PropInterest(
                email="second-real-buyer@farmco.org", plan_code="MOJ-PROP-01",
                source_language="en",
            )
            lead.save()
        self.assertEqual(calls, [])
        self.assertEqual(PropInterest.objects.count(), 2)

    def test_review_repr_redacts_authenticated_buyer_and_provenance(self):
        from prop_firm.consent_review_orm import review_existing_interest
        lead = self.lead
        result = review_existing_interest(
            interest_pk=lead.pk, authenticated_buyer_ref="verified-private-buyer-123",
            independently_verified_interest_pk=lead.pk,
            independent_buyer_link_verified=True,
            signed_customer_terms_sha256="a" * 64,
            trusted_contract_sha256="a" * 64,
            trusted_gate_evidence={},
        )
        self.assertEqual(result.buyer_ref, "verified-private-buyer-123")
        rendered = repr(result)
        self.assertNotIn("verified-private-buyer-123", rendered)
        self.assertNotIn(result.interest_digest, rendered)
        self.assertNotIn(result.interest_ref, rendered)
        self.assertNotIn(result.contract_sha256, rendered)
        self.assertIn("private_review_only", rendered)
        self.assertFalse(result.payment_authorized)
        self.assertFalse(result.enrollment_authorized)

    def test_lock_never_modifies_identifiers_or_creates_financial_artifact(self):
        from prop_firm.models import PropAccount, PropChallengeEnrollment
        self.lead.status = "contacted"
        self.lead.save(update_fields=["status"])
        self.assertEqual(PropAccount.objects.count(), 0)
        self.assertEqual(PropChallengeEnrollment.objects.count(), 0)
        self.assertEqual(PropInterest.objects.get().plan_code, "MOJ-PROP-01")
