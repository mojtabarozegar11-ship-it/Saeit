"""C145 — A buyer's pending order is not an independently settled payment.

No chain transaction, private wallet, actual customer or invoice is created:
only isolated Django test fixtures. The payment gateway must insert a single
confirmed enrollment after independently verified settlement, never toggle an
arbitrary pending record through Model.save().
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import PropTrader, PropChallengeEnrollment


class EnrollmentSettlementImmutabilityTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="c145_offline_buyer", password="CI-only"
        )
        self.trader = PropTrader.objects.create(user=user)
        self.paid_at = timezone.now()-timedelta(days=1)

    def enrollment(self, *, paid, invoice):
        return PropChallengeEnrollment.objects.create(
            trader=self.trader, verified_invoice_ref=invoice,
            plan_code="MOJ-PROP-01", confirmed_at=self.paid_at,
            settlement_verified=paid,
        )

    def db_paid_state(self, enrollment):
        return PropChallengeEnrollment.objects.values_list(
            "settlement_verified", flat=True
        ).get(pk=enrollment.pk)

    def test_01_pending_enrollment_cannot_be_upgraded_by_model_save(self):
        order = self.enrollment(paid=False, invoice="C145-PENDING-NO-CHAIN")
        order.settlement_verified = True
        with self.assertRaises(ValidationError):
            order.save()
        self.assertIs(self.db_paid_state(order), False)

    def test_02_pending_enrollment_update_fields_cannot_claim_payment(self):
        order = self.enrollment(paid=False, invoice="C145-PENDING-UPDATE")
        order.settlement_verified = True
        with self.assertRaises(ValidationError):
            order.save(update_fields=["settlement_verified"])
        self.assertIs(self.db_paid_state(order), False)

    def test_03_paid_enrollment_cannot_be_downgraded_by_model_save(self):
        order = self.enrollment(paid=True, invoice="C145-SYNTHETIC-PAID")
        order.settlement_verified = False
        with self.assertRaises(ValidationError):
            order.save()
        self.assertIs(self.db_paid_state(order), True)

    def test_04_paid_enrollment_cannot_be_reversed_with_update_fields(self):
        order = self.enrollment(paid=True, invoice="C145-SYNTHETIC-REVERSAL")
        order.settlement_verified = False
        with self.assertRaises(ValidationError):
            order.save(update_fields=["settlement_verified"])
        self.assertIs(self.db_paid_state(order), True)

    def test_05_full_clean_alone_rejects_post_create_settlement_flip(self):
        order = self.enrollment(paid=False, invoice="C145-PENDING-CLEAN")
        order.settlement_verified = True
        with self.assertRaises(ValidationError):
            order.full_clean()
        self.assertIs(self.db_paid_state(order), False)

    def test_06_identical_saved_state_is_not_rejected(self):
        order = self.enrollment(paid=True, invoice="C145-NOOP-PAID")
        order.save(update_fields=["settlement_verified"])
        self.assertIs(self.db_paid_state(order), True)

    def test_07_terms_switch_cannot_rewrite_paid_contract(self):
        order = self.enrollment(paid=True, invoice="C145-FROZEN-TERMS")
        order.terms_version = "2026-11-14/v1.1"
        with self.assertRaises(ValidationError):
            order.save(update_fields=["terms_version"])
        order.refresh_from_db()
        self.assertEqual(order.terms_version, "2026-11-15/v1.2")
