"""MOJ PROP four-week challenge: no retroactive or cross-purchase phase two.

Real Django database tests; synthetic traders only; no invoices, TRX,
social posts, external brokers, real funds or customer effects.
"""
from datetime import datetime, timedelta, timezone
from django.contrib.auth import get_user_model
from django.test import TestCase
from prop_firm.models import PropTrader, PropAccount, PropChallengeEnrollment
from prop_firm.portal import completed_prior_phase_one, account_projection
from prop_firm.social_policy import NEW_CONTRACT_VERSION, LEGACY_CONTRACT_VERSION
from prop_firm.rules import POLICY

START = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)

class PaidChallengePhaseCausalityTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username="c28phase_owner")
        self.other_user = U.objects.create_user(username="c28phase_other")
        self.trader = PropTrader.objects.create(user=self.user)
        self.other = PropTrader.objects.create(user=self.other_user)
        self.enroll = self.enrollment(self.trader, "paid-ref-c28")
        self.phase_two = self.account(
            self.trader, PropAccount.Kind.PHASE_TWO,
            enrollment=self.enroll, opened=START+timedelta(days=12),
        )

    def enrollment(self, trader, invoice):
        return PropChallengeEnrollment.objects.create(
            trader=trader, verified_invoice_ref=invoice,
            confirmed_at=START, settlement_verified=True,
            terms_version=NEW_CONTRACT_VERSION,
        )

    def account(self, trader, kind, *, enrollment=None,
                opened=None, closed=None, status=None,
                reconciled=True, version=NEW_CONTRACT_VERSION):
        return PropAccount.objects.create(
            trader=trader, kind=kind, challenge_enrollment=enrollment,
            opened_at=opened or START+timedelta(hours=1),
            closed_at=closed,
            status=status or PropAccount.Status.PASSED,
            reconciled_by_operator=reconciled,
            policy_version=version,
        )

    def first(self, **overrides):
        params={
            "trader":self.trader,
            "kind":PropAccount.Kind.PHASE_ONE,
            "enrollment":self.enroll,
            "opened":START+timedelta(hours=1),
            "closed":START+timedelta(days=10),
            "status":PropAccount.Status.PASSED,
            "reconciled":True,
        }
        params.update(overrides)
        return self.account(**params)

    def test_01_matched_completed_first_stage_qualifies(self):
        self.first()
        self.assertTrue(completed_prior_phase_one(self.phase_two))

    def test_02_first_stage_closed_after_phase_two_opened_denied(self):
        self.first(closed=START+timedelta(days=13))
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_03_first_stage_missing_completion_denied(self):
        self.first(closed=None)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_04_first_stage_not_independently_reconciled_denied(self):
        self.first(reconciled=False)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_05_first_stage_not_passed_denied(self):
        self.first(status=PropAccount.Status.ACTIVE)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_06_other_trader_cannot_qualify(self):
        other_enrollment=self.enrollment(self.other,"paid-ref-other-c28")
        self.first(trader=self.other,enrollment=other_enrollment)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_07_other_paid_purchase_cannot_qualify(self):
        another=self.enrollment(self.trader,"paid-ref-other-order")
        self.first(enrollment=another)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_08_prior_first_stage_started_before_payment_denied(self):
        self.first(opened=START-timedelta(days=1))
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_09_first_stage_completed_after_28_day_term_denied(self):
        self.phase_two.opened_at=START+timedelta(days=40)
        self.first(closed=START+timedelta(days=29))
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_10_phase_two_opens_after_expiry_denied(self):
        self.phase_two.opened_at=START+timedelta(days=28)
        self.first()
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_11_unsettled_purchase_denied(self):
        self.first()
        self.enroll.settlement_verified=False
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_12_missing_enrollment_denied_new_contract(self):
        self.first()
        self.phase_two.challenge_enrollment=None
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_13_nonphase_two_never_qualifies(self):
        one=self.first()
        self.assertFalse(completed_prior_phase_one(one))

    def test_14_first_stage_start_after_close_denied(self):
        self.first(opened=START+timedelta(days=11),closed=START+timedelta(days=10))
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_15_old_contract_does_not_borrow_new_contract_pass(self):
        self.first()
        self.phase_two.policy_version=LEGACY_CONTRACT_VERSION
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_16_incomplete_phase_one_does_not_qualify_even_if_other_passed(self):
        self.first(status=PropAccount.Status.ACTIVE)
        self.first(reconciled=False)
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_17_two_correct_prior_phases_still_require_one_same_enrollment(self):
        self.first()
        different=self.enrollment(self.trader, "paid-ref-yet-another")
        self.first(enrollment=different)
        self.assertTrue(completed_prior_phase_one(self.phase_two))

    def test_18_account_window_rejects_opening_after_28_days(self):
        self.phase_two.opened_at=START+timedelta(days=30)
        projection=account_projection(self.phase_two,as_of=START+timedelta(days=31))
        self.assertFalse(projection["purchase_window_valid"])
        self.assertFalse(projection["no_payout_or_trade"] is False)

    def test_19_account_window_rejects_opening_before_payment(self):
        self.phase_two.opened_at=START-timedelta(seconds=1)
        self.assertFalse(account_projection(self.phase_two)["purchase_window_valid"])

    def test_20_stage_closed_after_window_denied(self):
        self.phase_two.closed_at=START+timedelta(days=29)
        self.assertFalse(account_projection(self.phase_two)["purchase_window_valid"])

    def test_21_phase_one_equal_phase_two_start_boundary(self):
        self.first(closed=self.phase_two.opened_at)
        self.assertTrue(completed_prior_phase_one(self.phase_two))

    def test_22_missing_phase_two_start_denied(self):
        self.first()
        self.phase_two.opened_at=None
        self.assertFalse(completed_prior_phase_one(self.phase_two))

    def test_23_versioned_paid_contract_is_never_live_trade_authorization(self):
        self.first()
        p=account_projection(self.phase_two)
        self.assertTrue(p["no_payout_or_trade"])
        self.assertFalse(POLICY.real_orders_enabled)
        self.assertFalse(POLICY.trx_checkout_enabled)
