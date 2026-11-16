"""C141: phase-two chronology cannot be approved by later or unrelated PASSED flags.

All settlement flags here belong to synthetic isolated Django test fixtures.
This suite does not represent actual on-chain payment, broker evidence or sale.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from prop_firm.models import PropAccount, PropChallengeEnrollment, PropTrader
from prop_firm.portal import completed_paid_phase_one_before_stage_two
from prop_firm.social_policy import NEW_CONTRACT_VERSION

START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


class CompletedPhaseOneChronologyTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="c141_owner_synthetic", password="ci-only-not-production"
        )
        self.trader = PropTrader.objects.create(user=user)
        self.purchase = PropChallengeEnrollment.objects.create(
            trader=self.trader,
            verified_invoice_ref="synthetic-C141-purchase-A",
            plan_code="MOJ-PROP-01",
            confirmed_at=START,
            settlement_verified=True,
            terms_version=NEW_CONTRACT_VERSION,
        )
        self.phase1 = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.PASSED,
            reconciled_by_operator=True,
            challenge_enrollment=self.purchase,
            opened_at=START+DAY,
            closed_at=START+timedelta(days=7),
            policy_version=NEW_CONTRACT_VERSION,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
        )
        self.phase2 = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            status=PropAccount.Status.ACTIVE,
            reconciled_by_operator=True,
            challenge_enrollment=self.purchase,
            opened_at=START+timedelta(days=8),
            policy_version=NEW_CONTRACT_VERSION,
            tier_index=0, starting_capital_usd=Decimal("100.00"),
        )

    def accepted(self):
        return completed_paid_phase_one_before_stage_two(self.phase2)

    def mutate(self, model, **changes):
        type(model).objects.filter(pk=model.pk).update(**changes)
        model.refresh_from_db()

    def test_01_prior_reconciled_completed_same_purchase_is_eligible(self):
        self.assertTrue(self.accepted())

    def test_02_prior_closed_after_stage_two_started_denied(self):
        self.mutate(self.phase1, closed_at=self.phase2.opened_at+DAY)
        self.assertFalse(self.accepted())

    def test_03_prior_not_closed_denied(self):
        self.mutate(self.phase1, closed_at=None)
        self.assertFalse(self.accepted())

    def test_04_prior_not_opened_denied(self):
        self.mutate(self.phase1, opened_at=None)
        self.assertFalse(self.accepted())

    def test_05_prior_opened_after_closed_denied(self):
        self.mutate(self.phase1, opened_at=self.phase1.closed_at+DAY)
        self.assertFalse(self.accepted())

    def test_06_prior_reconciliation_flag_required(self):
        self.mutate(self.phase1, reconciled_by_operator=False)
        self.assertFalse(self.accepted())

    def test_07_prior_status_must_be_passed(self):
        self.mutate(self.phase1, status=PropAccount.Status.ACTIVE)
        self.assertFalse(self.accepted())

    def test_08_different_purchase_does_not_qualify(self):
        other_purchase = PropChallengeEnrollment.objects.create(
            trader=self.trader,
            verified_invoice_ref="synthetic-C141-purchase-B",
            plan_code="MOJ-PROP-01", confirmed_at=START,
            settlement_verified=True, terms_version=NEW_CONTRACT_VERSION,
        )
        self.mutate(self.phase1, challenge_enrollment=other_purchase)
        self.assertFalse(self.accepted())

    def test_09_unsettled_purchase_denied(self):
        self.mutate(self.purchase, settlement_verified=False)
        self.assertFalse(self.accepted())

    def test_10_stage_two_opened_after_day_28_denied(self):
        self.mutate(self.phase2, opened_at=START+timedelta(days=28))
        self.assertFalse(self.accepted())

    def test_11_first_stage_opened_before_purchase_denied(self):
        self.mutate(self.phase1, opened_at=START-DAY)
        self.assertFalse(self.accepted())

    def test_12_second_stage_without_opened_at_denied(self):
        self.mutate(self.phase2, opened_at=None)
        self.assertFalse(self.accepted())

    def test_13_another_traders_passed_stage_does_not_qualify(self):
        second_user = get_user_model().objects.create_user(
            username="c141_other_synthetic", password="ci-only"
        )
        other = PropTrader.objects.create(user=second_user)
        self.mutate(self.phase1, trader=other)
        self.assertFalse(self.accepted())

    def test_14_mismatched_stage_capital_denied(self):
        self.mutate(self.phase1, starting_capital_usd=Decimal("200.00"))
        self.assertFalse(self.accepted())

    def test_15_mismatched_stage_tier_denied(self):
        self.mutate(self.phase1, tier_index=1)
        self.assertFalse(self.accepted())

    def test_16_stage_two_started_before_purchase_denied(self):
        self.mutate(self.phase2, opened_at=START-DAY)
        self.assertFalse(self.accepted())

    def test_17_untrusted_naive_opened_at_denied(self):
        self.phase2.opened_at = datetime(2026, 11, 9)
        self.assertFalse(self.accepted())

    def test_18_future_evidence_cutoff_denies_retroactive_stage(self):
        cutoff = START+timedelta(days=5)
        self.assertFalse(completed_paid_phase_one_before_stage_two(
            self.phase2, as_of=cutoff
        ))

    def test_19_valid_evidence_cutoff_accepts_prior_complete_stage(self):
        cutoff = START+timedelta(days=10)
        self.assertTrue(completed_paid_phase_one_before_stage_two(
            self.phase2, as_of=cutoff
        ))

    def test_20_naive_evidence_cutoff_denied(self):
        self.assertFalse(completed_paid_phase_one_before_stage_two(
            self.phase2, as_of=datetime(2026, 11, 11)
        ))

    def test_21_phase_one_self_never_authorizes_phase_two(self):
        self.assertFalse(completed_paid_phase_one_before_stage_two(self.phase1))

    def test_22_missing_stage_pk_never_authorizes(self):
        self.phase2.pk = None
        self.assertFalse(self.accepted())

    def test_23_breached_prior_stage_not_eligible(self):
        self.mutate(self.phase1, status=PropAccount.Status.BREACHED)
        self.assertFalse(self.accepted())

    def test_24_close_exactly_at_phase_two_start_is_allowed(self):
        self.mutate(self.phase1, closed_at=self.phase2.opened_at)
        self.assertTrue(self.accepted())


if __name__ == "__main__":
    import unittest
    unittest.main()
