"""D independent regression: a valid passed Phase I must not unlock Phase II
using a changed, stale, swapped or future-dated synthetic paid enrollment.

All records are test-only: no blockchain settlement, real buyer, real capital,
public marketing, broker order or checkout activation.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import PropAccount, PropChallengeEnrollment, PropTrader
from prop_firm.portal import (
    account_projection, completed_paid_phase_one_before_stage_two,
    _enrollment_matches_authority,
)
from prop_firm.social_policy import NEW_CONTRACT_VERSION


class TwoPhasePaidBindingDBTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="d2_phase_prospect_only", password="no-live-account"
        )
        self.trader = PropTrader.objects.create(user=user)
        self.now = timezone.now()
        self.paid = self.now - timedelta(days=20)
        self.purchase = PropChallengeEnrollment.objects.create(
            trader=self.trader,
            verified_invoice_ref="D2-SYNTHETIC-RECEIPT-0001",
            plan_code="MOJ-PROP-01",
            settlement_verified=True,
            terms_version=NEW_CONTRACT_VERSION,
            confirmed_at=self.paid,
        )
        self.phase1 = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_ONE,
            challenge_enrollment=self.purchase,
            status=PropAccount.Status.PASSED,
            policy_version=NEW_CONTRACT_VERSION,
            reconciled_by_operator=True,
            opened_at=self.paid + timedelta(days=1),
            closed_at=self.paid + timedelta(days=9),
            tier_index=0, starting_capital_usd=Decimal("100.00"),
        )
        self.phase2 = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            challenge_enrollment=self.purchase,
            policy_version=NEW_CONTRACT_VERSION,
            opened_at=self.paid + timedelta(days=10),
            tier_index=0, starting_capital_usd=Decimal("100.00"),
        )
        # Ensure phase2's relation is cached BEFORE any direct database change.
        self.assertIs(self.phase2.challenge_enrollment, self.purchase)

    def projection(self):
        return account_projection(self.phase2)["purchase_window_valid"]

    def chronology(self):
        return completed_paid_phase_one_before_stage_two(self.phase2)

    def mutate_db(self, **changes):
        return PropChallengeEnrollment.objects.filter(
            pk=self.purchase.pk
        ).update(**changes)

    def test_01_valid_synthetic_two_stage_history_is_chronological(self):
        self.assertTrue(self.chronology())

    def test_02_valid_synthetic_two_stage_purchase_window_is_present(self):
        self.assertTrue(self.projection())

    def test_03_future_repriced_purchase_date_blocks_chronology(self):
        self.mutate_db(confirmed_at=self.now + timedelta(days=1))
        self.assertFalse(self.chronology())

    def test_04_future_purchase_date_blocks_projection(self):
        self.mutate_db(confirmed_at=self.now + timedelta(days=1))
        self.assertFalse(self.projection())

    def test_05_future_as_of_does_not_create_retroactive_chronology(self):
        self.mutate_db(confirmed_at=self.now + timedelta(days=1))
        self.assertFalse(completed_paid_phase_one_before_stage_two(
            self.phase2, as_of=self.now + timedelta(days=45)))

    def test_06_future_as_of_does_not_redeem_paid_window(self):
        self.mutate_db(confirmed_at=self.now + timedelta(days=1))
        self.assertFalse(account_projection(
            self.phase2, as_of=self.now + timedelta(days=45))["purchase_window_valid"])

    def test_07_invoice_substitution_blocks_stage_two(self):
        self.mutate_db(verified_invoice_ref="D2-SYNTHETIC-RECEIPT-0002")
        self.assertFalse(self.chronology())

    def test_08_invoice_substitution_blocks_purchase_window(self):
        self.mutate_db(verified_invoice_ref="D2-SYNTHETIC-RECEIPT-0002")
        self.assertFalse(self.projection())

    def test_09_new_plan_substitution_blocks_chronology(self):
        self.mutate_db(plan_code="MOJ-PROP-06")
        self.assertFalse(self.chronology())

    def test_10_new_plan_substitution_blocks_window(self):
        self.mutate_db(plan_code="MOJ-PROP-06")
        self.assertFalse(self.projection())

    def test_11_revoked_settlement_blocks_stage_two(self):
        self.mutate_db(settlement_verified=False)
        self.assertFalse(self.chronology())

    def test_12_revoked_settlement_blocks_purchase_window(self):
        self.mutate_db(settlement_verified=False)
        self.assertFalse(self.projection())

    def test_13_contract_version_drift_blocks_stage_two(self):
        self.mutate_db(terms_version="not-v12")
        self.assertFalse(self.chronology())

    def test_14_contract_version_drift_blocks_purchase_window(self):
        self.mutate_db(terms_version="not-v12")
        self.assertFalse(self.projection())

    def test_15_other_trader_purchase_cannot_validate_phase_two(self):
        other = PropTrader.objects.create(user=get_user_model().objects.create_user(
            username="d2_other_trader", password="never-live"
        ))
        self.mutate_db(trader=other)
        self.assertFalse(self.chronology())

    def test_16_other_trader_purchase_cannot_validate_projection(self):
        other = PropTrader.objects.create(user=get_user_model().objects.create_user(
            username="d2_other_trader", password="never-live"
        ))
        self.mutate_db(trader=other)
        self.assertFalse(self.projection())

    def test_17_inmemory_stale_invoice_reference_blocks_chronology(self):
        self.purchase.verified_invoice_ref = "D2-CHANGED-CACHE-REFERENCE"
        self.assertFalse(self.chronology())

    def test_18_inmemory_stale_invoice_reference_blocks_projection(self):
        self.purchase.verified_invoice_ref = "D2-CHANGED-CACHE-REFERENCE"
        self.assertFalse(self.projection())

    def test_19_naive_inmemory_confirmed_date_blocks_chronology(self):
        self.purchase.confirmed_at = datetime(2026, 11, 1, 0, 0)
        self.assertFalse(self.chronology())

    def test_20_naive_inmemory_confirmed_date_blocks_projection(self):
        self.purchase.confirmed_at = datetime(2026, 11, 1, 0, 0)
        self.assertFalse(self.projection())
