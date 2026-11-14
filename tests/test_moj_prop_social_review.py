"""Two purchase-linked four-week posts shared across both simulated phases."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from prop_firm.models import (
    PropAccount, PropTrader, PropChallengeEnrollment,
    PropExecution, PropEquityObservation, PropSocialEvidence,
)
from prop_firm.portal import account_projection
from prop_firm.rules import POLICY
from prop_firm.social_review_service import (
    SocialEvidenceRejected, submit_social_evidence, review_social_evidence,
)

START = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
CHECKED = {
    "author_verified": True, "public_visible": True,
    "disclosure_verified": True, "content_compliant": True,
    "date_verified": True, "continued_visibility_verified": True,
}


class FourWeekProofTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="prop_social_buyer",password="ci-only")
        cls.other = User.objects.create_user(username="prop_social_stranger",password="ci-only")
        cls.staff = User.objects.create_user(username="prop_social_reviewer",password="ci-only",is_staff=True)
        cls.profile = PropTrader.objects.create(user=cls.user)
        cls.enrollment = PropChallengeEnrollment.objects.create(
            trader=cls.profile, verified_invoice_ref="mock-confirmed-order-001",
            confirmed_at=START, settlement_verified=True,
        )
        cls.phase1 = PropAccount.objects.create(
            trader=cls.profile,kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            opened_at=START, challenge_enrollment=cls.enrollment,
        )
        cls.phase2 = PropAccount.objects.create(
            trader=cls.profile,kind=PropAccount.Kind.PHASE_TWO,
            status=PropAccount.Status.ACTIVE,
            opened_at=START+timedelta(days=7),
            challenge_enrollment=cls.enrollment,
        )

    def url(self,platform):
        return ("https://www.instagram.com/p/my-challenge"
                if platform=="instagram"
                else "https://www.facebook.com/trader/posts/123456")

    def submit(self, platform="instagram", phase=None, posted_at=None, consent=True):
        return submit_social_evidence(
            account_id=(phase or self.phase1).pk, submitter=self.user,
            platform=platform,post_url=self.url(platform),
            posted_at=posted_at or START+timedelta(hours=2),
            explicit_consent=consent,
        )

    def review(self,row,**facts):
        return review_social_evidence(
            evidence_id=row.pk,reviewer=self.staff,
            audited_facts={**CHECKED,**facts},
            reviewed_at=row.posted_at+timedelta(days=28),
        )

    def trades(self,account,first_day,pnl):
        for i in range(6):
            at=START+timedelta(days=first_day+i)
            initial=Decimal("100")+Decimal(i)*Decimal(pnl)
            PropEquityObservation.objects.create(
                account=account, external_event_id=f"open-{first_day+i}",
                observed_at=at+timedelta(hours=8), is_session_open=True,
                equity_usd=initial, reconciliation_status="verified",
            )
            PropExecution.objects.create(
                account=account, external_event_id=f"trade-{first_day+i}",
                closed_at=at+timedelta(hours=12), data_source="verified-ci",
                symbol="XAUUSD",gross_realized_usd=Decimal(pnl),
                total_fees_usd=0,reconciliation_status="verified",
            )
            PropEquityObservation.objects.create(
                account=account, external_event_id=f"close-{first_day+i}",
                observed_at=at+timedelta(hours=15), is_session_open=False,
                equity_usd=initial+Decimal(pnl),
                reconciliation_status="verified",
            )
        account.reconciled_by_operator=True
        account.save()

    def test_one_post_per_platform_for_entire_purchase(self):
        self.submit("instagram")
        self.submit("facebook",phase=self.phase2)
        self.assertEqual(PropSocialEvidence.objects.count(),2)
        with self.assertRaises(SocialEvidenceRejected):
            self.submit("instagram",phase=self.phase2)

    def test_purchase_identity_must_be_trusted(self):
        self.enrollment.settlement_verified=False
        self.enrollment.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit()

    def test_consent_required(self):
        with self.assertRaises(PermissionDenied):
            self.submit(consent=False)

    def test_stranger_cannot_submit(self):
        with self.assertRaises(PermissionDenied):
            submit_social_evidence(
                account_id=self.phase1.pk,submitter=self.other,
                platform="instagram",post_url=self.url("instagram"),
                posted_at=START+timedelta(hours=2),explicit_consent=True,
            )

    def test_post_after_first_24_hours_is_disallowed(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(posted_at=START+timedelta(hours=25))

    def test_early_review_denied_until_full_28_day_lifetime(self):
        row=self.submit()
        with self.assertRaises(SocialEvidenceRejected):
            review_social_evidence(
                evidence_id=row.pk,reviewer=self.staff,audited_facts=CHECKED,
                reviewed_at=row.posted_at+timedelta(days=27),
            )

    def test_reviewer_must_be_staff(self):
        row=self.submit()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk,reviewer=self.user,
                audited_facts=CHECKED,reviewed_at=row.posted_at+timedelta(days=28),
            )

    def test_missing_visibility_review_is_rejected(self):
        row=self.submit()
        verified=self.review(row,continued_visibility_verified=False)
        self.assertEqual(verified.review_status,"rejected")

    def test_good_two_posts_survive_28_days(self):
        first=self.review(self.submit("instagram"))
        second=self.review(self.submit("facebook"))
        self.assertEqual(first.review_status,"verified")
        self.assertEqual(second.review_status,"verified")
        self.assertEqual(PropSocialEvidence.objects.filter(review_status="verified").count(),2)

    def test_cannot_reverify_same_post_twice(self):
        row=self.submit()
        self.review(row)
        with self.assertRaises(SocialEvidenceRejected):
            self.review(row)

    def test_six_trading_days_no_posts_cannot_pass(self):
        self.trades(self.phase1,0,"1.60")
        result=account_projection(self.phase1)
        self.assertFalse(result["assessment"].passed)
        self.assertEqual(result["social_posting"].reviewed_instagram,0)
        self.assertEqual(result["social_posting"].required_instagram,1)

    def test_two_posts_once_unlock_phase_one_and_phase_two(self):
        self.trades(self.phase1,0,"1.60")
        self.trades(self.phase2,7,"1.00")
        self.review(self.submit("instagram"))
        self.review(self.submit("facebook"))
        phase_one=account_projection(self.phase1)
        self.assertTrue(phase_one["social_posting"].satisfied)
        self.assertTrue(phase_one["assessment"].passed)
        self.phase1.status=PropAccount.Status.PASSED
        self.phase1.save()
        phase_two=account_projection(self.phase2)
        self.assertTrue(phase_two["social_posting"].satisfied)
        self.assertTrue(phase_two["assessment"].passed)
        self.assertEqual(PropSocialEvidence.objects.count(),2)

    def test_trade_after_day_28_cannot_qualify(self):
        self.trades(self.phase1,26,"1.60")
        # Day 28/29 fall after the purchase's strict 28-day trading deadline.
        self.review(self.submit("instagram"))
        self.review(self.submit("facebook"))
        result=account_projection(self.phase1)
        self.assertFalse(result["assessment"].passed)
        self.assertFalse(result["purchase_window_valid"])

    def test_legacy_cohort_exempt_from_new_terms(self):
        self.phase1.policy_version="2026-11-14/v1.1"
        self.phase1.challenge_enrollment=None
        self.phase1.save()
        self.trades(self.phase1,0,"1.60")
        result=account_projection(self.phase1)
        self.assertTrue(result["assessment"].passed)

    def test_missing_purchase_blocks_pass_even_with_good_trades(self):
        self.phase1.challenge_enrollment=None
        self.phase1.save()
        self.trades(self.phase1,0,"1.60")
        result=account_projection(self.phase1)
        self.assertFalse(result["assessment"].passed)
        self.assertFalse(result["purchase_window_valid"])
