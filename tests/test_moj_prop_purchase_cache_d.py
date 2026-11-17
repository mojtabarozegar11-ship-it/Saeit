"""D: sale/qualification must not trust a stale enrollment relation cache.

Synthetic database-only fixtures: no real payment, trader, broker or chain.
All mutable critical fields are independently reread before phase eligibility.
"""
from datetime import timedelta, datetime
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from prop_firm.models import PropAccount, PropChallengeEnrollment, PropTrader
from prop_firm.portal import account_projection, _enrollment_matches_authority, completed_paid_phase_one_before_stage_two


class PurchaseBindingFreshnessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username="mojprop_d_cached_invoice", password="synthetic-test-only"
        )
        cls.trader = PropTrader.objects.create(user=user)

    def make(self):
        now = timezone.now()
        purchase = PropChallengeEnrollment.objects.create(
            trader=self.trader, verified_invoice_ref="D-SYNTHETIC-INVOICE-00001",
            plan_code="MOJ-PROP-01", settlement_verified=True,
            confirmed_at=now - timedelta(days=2),
        )
        account = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=purchase,
        )
        return account, purchase, now

    def test_01_normal_fixture_matches_persisted_purchase(self):
        account, purchase, _ = self.make()
        self.assertTrue(_enrollment_matches_authority(purchase))
        self.assertTrue(account_projection(account)["purchase_window_valid"])

    def test_02_future_confirmation_update_invalidates_cached_purchase(self):
        account, purchase, now = self.make()
        self.assertIs(account.challenge_enrollment, purchase)
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            confirmed_at=now + timedelta(days=2))
        result = account_projection(account)
        self.assertFalse(result["purchase_window_valid"])
        self.assertIsNone(result["social_posting"])
        self.assertFalse(result["verified"])

    def test_03_future_as_of_does_not_resurrect_mutated_purchase(self):
        account, purchase, now = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            confirmed_at=now + timedelta(days=2))
        result = account_projection(account, as_of=now+timedelta(days=90))
        self.assertFalse(result["purchase_window_valid"])

    def test_04_legacy_cache_cannot_hide_settlement_revocation(self):
        account, purchase, _ = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            settlement_verified=False)
        result = account_projection(account)
        self.assertFalse(result["purchase_window_valid"])
        self.assertFalse(result["verified"])

    def test_05_changed_invoice_reference_is_not_accepted(self):
        account, purchase, _ = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            verified_invoice_ref="D-SYNTHETIC-INVOICE-00002")
        self.assertFalse(_enrollment_matches_authority(purchase))
        self.assertFalse(account_projection(account)["purchase_window_valid"])

    def test_06_changed_plan_is_not_silently_paid_under_old_sku(self):
        account, purchase, _ = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            plan_code="MOJ-PROP-02")
        self.assertFalse(account_projection(account)["purchase_window_valid"])

    def test_07_changed_contract_version_is_not_equivalent_to_v12(self):
        account, purchase, _ = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            terms_version="superseded-nine-tier-v0")
        self.assertFalse(account_projection(account)["purchase_window_valid"])

    def test_08_inmemory_naive_datetime_cannot_override_db_date(self):
        account, purchase, _ = self.make()
        purchase.confirmed_at = datetime(2026, 11, 16)
        self.assertFalse(account_projection(account)["purchase_window_valid"])

    def test_09_inmemory_invoice_mutation_is_rejected(self):
        account, purchase, _ = self.make()
        purchase.verified_invoice_ref = "FORGED-INVOICE"
        self.assertFalse(_enrollment_matches_authority(purchase))
        self.assertFalse(account_projection(account)["purchase_window_valid"])

    def test_10_stale_phase_two_relation_cannot_claim_prior_phase_pass(self):
        account, purchase, now = self.make()
        PropChallengeEnrollment.objects.filter(pk=purchase.pk).update(
            confirmed_at=now + timedelta(days=1))
        self.assertFalse(completed_paid_phase_one_before_stage_two(account))

    def test_11_unsaved_purchase_is_never_an_authoritative_invoice(self):
        _, purchase, _ = self.make()
        purchase.pk = None
        self.assertFalse(_enrollment_matches_authority(purchase))

    def test_12_false_payment_input_with_truthy_string_does_not_verify(self):
        account, purchase, _ = self.make()
        purchase.settlement_verified = "true"
        self.assertFalse(_enrollment_matches_authority(purchase))
        self.assertFalse(account_projection(account)["purchase_window_valid"])
