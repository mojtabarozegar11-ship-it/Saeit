"""Verified social content is a separate, privately reviewed challenge pass gate."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import TestCase

from prop_firm.models import (
    PropTrader, PropAccount, PropExecution, PropEquityObservation,
    PropSocialEvidence,
)
from prop_firm.portal import account_projection
from prop_firm.rules import POLICY
from prop_firm.social_review_service import (
    SocialEvidenceRejected, submit_social_evidence, review_social_evidence,
)

START = datetime(2026,11,16,0,0,tzinfo=timezone.utc)
CHECKED = {
    "author_verified": True,
    "public_visible": True,
    "disclosure_verified": True,
    "content_compliant": True,
    "date_verified": True,
}


class MojPropSocialEvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.trader_user = User.objects.create_user(
            username="social_trader", password="unit-test-only"
        )
        cls.other_user = User.objects.create_user(
            username="social_other", password="unit-test-only"
        )
        cls.reviewer = User.objects.create_user(
            username="social_staff", password="unit-test-only", is_staff=True
        )
        cls.profile = PropTrader.objects.create(user=cls.trader_user)
        cls.account = PropAccount.objects.create(
            trader=cls.profile, kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            opened_at=START, policy_version=POLICY.version,
        )

    def make_trade(self, day_idx=0, pnl="1.60"):
        date_time = START + timedelta(days=day_idx)
        initial = Decimal("100.00") + Decimal(day_idx) * Decimal("1.60")
        PropEquityObservation.objects.create(
            account=self.account, external_event_id=f"open-{day_idx}",
            observed_at=date_time + timedelta(hours=8),
            is_session_open=True, equity_usd=initial,
            reconciliation_status="verified",
        )
        PropExecution.objects.create(
            account=self.account, external_event_id=f"trade-{day_idx}",
            data_source="simulator-approved", symbol="XAUUSD",
            closed_at=date_time + timedelta(hours=12),
            gross_realized_usd=Decimal(pnl), total_fees_usd=Decimal("0.00"),
            reconciliation_status="verified",
        )
        PropEquityObservation.objects.create(
            account=self.account, external_event_id=f"close-{day_idx}",
            observed_at=date_time + timedelta(hours=14),
            is_session_open=False, equity_usd=initial + Decimal(pnl),
            reconciliation_status="verified",
        )

    def stage(self, day_idx=0, platform="instagram"):
        day = (START + timedelta(days=day_idx)).date()
        post_at = START + timedelta(days=day_idx, hours=16)
        url = (
            f"https://www.instagram.com/p/unique-{day_idx}"
            if platform == "instagram"
            else f"https://www.facebook.com/trader/posts/{90000 + day_idx}"
        )
        return submit_social_evidence(
            account_id=self.account.pk, submitter=self.trader_user,
            trading_day=day, platform=platform, post_url=url, posted_at=post_at,
            explicit_consent=True,
        )

    def approve(self, row, **facts):
        return review_social_evidence(
            evidence_id=row.pk, reviewer=self.reviewer,
            audited_facts={**CHECKED, **facts},
            reviewed_at=row.posted_at + timedelta(hours=2),
        )

    def test_customer_cannot_submit_without_explicit_consent(self):
        self.make_trade()
        with self.assertRaises(PermissionDenied):
            submit_social_evidence(
                account_id=self.account.pk, submitter=self.trader_user,
                trading_day=START.date(), platform="instagram",
                post_url="https://www.instagram.com/p/test", posted_at=START + timedelta(hours=16),
            )
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_unverified_trade_day_cannot_get_proof(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_customer_cannot_submit_for_other_account(self):
        self.make_trade()
        with self.assertRaises(PermissionDenied):
            submit_social_evidence(
                account_id=self.account.pk, submitter=self.other_user,
                trading_day=START.date(), platform="instagram",
                post_url="https://www.instagram.com/p/test", posted_at=START + timedelta(hours=16),
                explicit_consent=True,
            )

    def test_one_post_per_day_platform_only(self):
        self.make_trade()
        row = self.stage()
        self.assertEqual(row.review_status, PropSocialEvidence.Review.PENDING)
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_post_date_must_match_trade_day(self):
        self.make_trade()
        with self.assertRaises(SocialEvidenceRejected):
            submit_social_evidence(
                account_id=self.account.pk, submitter=self.trader_user,
                trading_day=START.date(), platform="facebook",
                post_url="https://facebook.com/trader/posts/mismatch",
                posted_at=START + timedelta(days=1), explicit_consent=True,
            )

    def test_nonstaff_cannot_verify_social_posts(self):
        self.make_trade()
        row = self.stage()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.trader_user, audited_facts=CHECKED
            )

    def test_all_manual_checks_required_before_verified(self):
        self.make_trade()
        row = self.stage()
        approved = self.approve(row, disclosure_verified=False)
        self.assertEqual(approved.review_status, "rejected")
        self.assertFalse(approved.disclosure_verified)
        with self.assertRaises(SocialEvidenceRejected):
            self.approve(row)

    def test_approved_post_keeps_audited_reviewer(self):
        self.make_trade()
        row = self.stage()
        verified = self.approve(row)
        self.assertEqual(verified.review_status,"verified")
        self.assertEqual(verified.reviewed_by, self.reviewer)
        self.assertEqual(verified.reviewed_at, row.posted_at + timedelta(hours=2))
        self.assertTrue(verified.disclosure_verified)

    def test_review_cannot_be_replayed_after_verified(self):
        self.make_trade()
        row = self.stage()
        self.approve(row)
        with self.assertRaises(SocialEvidenceRejected):
            self.approve(row)

    def test_phase_cannot_pass_with_missing_posts(self):
        for i in range(6):
            self.make_trade(i)
        self.account.reconciled_by_operator = True
        self.account.save()
        state = account_projection(self.account)
        self.assertTrue(state["verified"])
        self.assertFalse(state["assessment"].passed)
        self.assertIn(
            "social_daily_posts_both_platforms_unverified",
            state["assessment"].reasons,
        )
        self.assertEqual(state["social_posting"].required_instagram, 6)
        self.assertEqual(state["social_posting"].required_facebook, 6)

    def test_full_six_day_both_platform_reviews_allow_trading_pass(self):
        for i in range(6):
            self.make_trade(i)
            self.approve(self.stage(i,"instagram"))
            self.approve(self.stage(i,"facebook"))
        self.account.reconciled_by_operator = True
        self.account.save()
        state = account_projection(self.account)
        self.assertTrue(state["verified"])
        self.assertTrue(state["social_posting"].satisfied)
        self.assertEqual(state["social_posting"].reviewed_instagram, 6)
        self.assertEqual(state["social_posting"].reviewed_facebook, 6)
        self.assertTrue(state["assessment"].passed)

    def test_one_missing_facebook_review_delays_pass_not_breach(self):
        for i in range(6):
            self.make_trade(i)
            self.approve(self.stage(i,"instagram"))
            if i != 5:
                self.approve(self.stage(i,"facebook"))
        self.account.reconciled_by_operator = True
        self.account.save()
        state = account_projection(self.account)
        self.assertFalse(state["assessment"].passed)
        self.assertEqual(state["social_posting"].reviewed_facebook, 5)
        self.assertEqual(self.account.status, PropAccount.Status.ACTIVE)

    def test_social_proof_cannot_change_existing_funded_account(self):
        funded = PropAccount.objects.create(
            trader=self.profile, kind=PropAccount.Kind.FUNDED,
            starting_capital_usd=Decimal("100"), reference="funded-social-test",
            opened_at=START,
        )
        row = PropSocialEvidence(
            account=funded, platform="instagram", trading_day=START.date(),
            post_url="https://instagram.com/p/no-funded", posted_at=START+timedelta(hours=16),
        )
        with self.assertRaises(ValidationError):
            row.save()

    def test_old_cohort_cannot_be_retroactively_given_social_evidence(self):
        self.account.policy_version = "2026-11-14/v1.1"
        self.account.save()
        self.make_trade()
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()
