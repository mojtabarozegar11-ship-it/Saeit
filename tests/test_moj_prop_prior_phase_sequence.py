"""P0 MOJ PROP: phase-two cannot inherit a future or unrelated phase-one pass."""
from datetime import datetime, timedelta, timezone
from django.contrib.auth import get_user_model
from django.test import TestCase
from prop_firm.models import PropTrader, PropAccount
from prop_firm.portal import completed_prior_phase_one
from prop_firm.rules import POLICY

OPENED = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)

class HistoricalPhaseOrderTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="moj_phase_owner")
        other = get_user_model().objects.create_user(username="moj_phase_other")
        self.trader = PropTrader.objects.create(user=user)
        self.other = PropTrader.objects.create(user=other)
        self.phase2 = PropAccount.objects.create(
            trader=self.trader, kind=PropAccount.Kind.PHASE_TWO,
            opened_at=OPENED, policy_version=POLICY.version,
        )

    def first(self, **changes):
        attrs = {
            "trader":self.trader,
            "kind":PropAccount.Kind.PHASE_ONE,
            "status":PropAccount.Status.PASSED,
            "reconciled_by_operator":True,
            "policy_version":POLICY.version,
            "opened_at":OPENED-timedelta(days=15),
            "closed_at":OPENED-timedelta(days=1),
        }
        attrs.update(changes)
        return PropAccount.objects.create(**attrs)

    def test_01_correct_past_completion_qualifies(self):
        self.first()
        self.assertTrue(completed_prior_phase_one(self.phase2))

    def test_02_unrelated_trader_not_qualifying(self):
        self.first(trader=self.other)
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_03_future_phase_one_completion_not_qualifying(self):
        self.first(closed_at=OPENED+timedelta(days=2))
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_04_missing_completion_timestamp_not_qualifying(self):
        self.first(closed_at=None)
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_05_unreconciled_phase_one_not_qualifying(self):
        self.first(reconciled_by_operator=False)
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_06_wrong_policy_version_not_qualifying(self):
        self.first(policy_version="retired")
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_07_phase_one_only_active_not_passed(self):
        self.first(status=PropAccount.Status.ACTIVE)
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_08_phase_two_without_open_timestamp_rejected(self):
        self.first()
        self.phase2.opened_at=None
        self.assertFalse(completed_prior_phase_one(self.phase2))

    def test_09_other_account_type_never_qualifies(self):
        self.first()
        phase_one=PropAccount.objects.filter(
            trader=self.trader,kind=PropAccount.Kind.PHASE_ONE,
        ).first()
        self.assertFalse(completed_prior_phase_one(phase_one))

    def test_10_exact_same_utc_close_and_open_boundary(self):
        self.first(closed_at=OPENED)
        self.assertTrue(completed_prior_phase_one(self.phase2))

    def test_11_a_future_and_valid_past_combination(self):
        self.first(closed_at=OPENED+timedelta(days=3))
        self.first(closed_at=OPENED-timedelta(days=5))
        self.assertTrue(completed_prior_phase_one(self.phase2))
