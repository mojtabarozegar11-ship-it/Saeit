"""C22 database-level 28-day, one-post-per-platform human-reviewed workflow.

No publishing, paid invoice creation, trading, wallet operations or broker API.
The settlement record in the test fixture is synthetic DB-only test state.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from prop_firm.models import (
    PropAccount, PropChallengeEnrollment, PropEquityObservation,
    PropExecution, PropSocialEvidence, PropTrader,
)
from prop_firm.portal import account_projection
from prop_firm.rules import POLICY
from prop_firm.social_review_service import (
    SocialEvidenceRejected, review_social_evidence, submit_social_evidence,
)

START = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
REVIEWED = START + timedelta(days=29)
FACTS = {
    "author_verified": True, "public_visible": True,
    "disclosure_verified": True, "content_compliant": True,
    "date_verified": True, "continued_visibility_verified": True,
}


class MojPropOnePostFourWeekEvidenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.trader_user = User.objects.create_user(
            username="onepost_trader", password="test-only",
        )
        cls.other_user = User.objects.create_user(
            username="onepost_other", password="test-only",
        )
        cls.reviewer = User.objects.create_user(
            username="onepost_staff", password="test-only", is_staff=True,
        )
        cls.profile = PropTrader.objects.create(user=cls.trader_user)
        cls.enrollment = PropChallengeEnrollment.objects.create(
            trader=cls.profile, terms_version=POLICY.version,
            verified_invoice_ref="FIXTURE-DB-NO-BLOCKCHAIN-SETTLEMENT",
            settlement_verified=True, confirmed_at=START,
        )
        cls.account = PropAccount.objects.create(
            trader=cls.profile, challenge_enrollment=cls.enrollment,
            kind=PropAccount.Kind.PHASE_ONE, status=PropAccount.Status.ACTIVE,
            opened_at=START, policy_version=POLICY.version,
            starting_capital_usd=Decimal("100"),
        )

    def stage(self, platform="instagram", **overrides):
        data = {
            "account_id": self.account.pk, "submitter": self.trader_user,
            "platform": platform,
            "post_url": (
                "https://instagram.com/p/onepostABC123"
                if platform == "instagram"
                else "https://facebook.com/trader/posts/123456789"
            ),
            "posted_at": START + timedelta(hours=1),
            "explicit_consent": True,
        }
        data.update(overrides)
        return submit_social_evidence(**data)

    def approve(self, row, **changes):
        return review_social_evidence(
            evidence_id=row.pk, reviewer=self.reviewer,
            audited_facts={**FACTS, **changes}, reviewed_at=REVIEWED,
        )

    def seed_verified_trading_days(self):
        # Realistic synthetic *test-only* six-day net of $12, best $2/day.
        for i in range(6):
            date = START + timedelta(days=i)
            opening = Decimal("100") + Decimal(i * 2)
            PropEquityObservation.objects.create(
                account=self.account, external_event_id=f"open-{i}",
                observed_at=date + timedelta(hours=8), is_session_open=True,
                equity_usd=opening, reconciliation_status="verified",
            )
            PropExecution.objects.create(
                account=self.account, external_event_id=f"trade-{i}",
                data_source="fixture-no-broker", symbol="XAUUSD",
                closed_at=date + timedelta(hours=12),
                gross_realized_usd=Decimal("2"),
                total_fees_usd=Decimal("0"), reconciliation_status="verified",
            )
            PropEquityObservation.objects.create(
                account=self.account, external_event_id=f"close-{i}",
                observed_at=date + timedelta(hours=14), equity_usd=opening + 2,
                reconciliation_status="verified",
            )
        self.account.reconciled_by_operator = True
        self.account.save(update_fields=["reconciled_by_operator"])

    def test_consent_is_not_inferred_from_authenticated_user(self):
        with self.assertRaises(PermissionDenied):
            self.stage(explicit_consent=False)
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_other_user_cannot_attach_evidence_to_trader(self):
        with self.assertRaises(PermissionDenied):
            self.stage(submitter=self.other_user)
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_unsettled_purchase_cannot_stage_links(self):
        self.enrollment.settlement_verified = False
        self.enrollment.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_legacy_contract_cannot_acquire_new_social_rule(self):
        self.account.policy_version = "2026-11-14/v1.1"
        self.account.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()

    def test_unrelated_enrollment_cannot_be_reused(self):
        self.enrollment.trader = PropTrader.objects.create(user=self.other_user)
        self.enrollment.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.stage()

    def test_pending_one_post_per_platform_uses_original_purchase(self):
        instagram = self.stage("instagram")
        facebook = self.stage("facebook")
        self.assertEqual(PropSocialEvidence.objects.count(), 2)
        self.assertEqual({instagram.platform, facebook.platform}, {"instagram", "facebook"})
        self.assertEqual(instagram.enrollment_id, self.enrollment.pk)
        self.assertEqual(facebook.enrollment_id, self.enrollment.pk)
        self.assertIsNone(instagram.trading_day)
        self.assertEqual(instagram.review_status, "pending")

    def test_duplicate_platform_cannot_be_submitted_twice_in_same_purchase(self):
        self.stage("instagram")
        with self.assertRaises(SocialEvidenceRejected):
            self.stage("instagram")
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_second_phase_shares_one_social_post_per_purchase(self):
        self.stage("instagram")
        another = PropAccount.objects.create(
            trader=self.profile, challenge_enrollment=self.enrollment,
            kind=PropAccount.Kind.PHASE_TWO, status=PropAccount.Status.ACTIVE,
            opened_at=START + timedelta(days=6),
            policy_version=POLICY.version,
        )
        with self.assertRaises(SocialEvidenceRejected):
            self.stage("instagram", account_id=another.pk)
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_invalid_platform_and_banned_owner_page_fail_before_save(self):
        for platform, url in (
            ("instagram", "https://instagram.com/p/dr.mojtaba.rozegar"),
            ("facebook", "https://facebook.com/102203064721826/posts/123456"),
            ("facebook", "https://facebook.com/7317306/posts/123456"),
            ("facebook", "https://facebook.com/102203064721826%2fposts/123456"),
            ("telegram", "https://telegram.com/posts/123456"),
        ):
            with self.subTest(platform=platform, url=url):
                with self.assertRaises(SocialEvidenceRejected):
                    self.stage(platform, post_url=url)
        self.assertEqual(PropSocialEvidence.objects.count(), 0)

    def test_post_before_purchase_rejected(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.stage(posted_at=START - timedelta(seconds=1))

    def test_post_after_first_24h_rejected(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.stage(posted_at=START + timedelta(hours=24, seconds=1))

    def test_submitting_later_than_today_does_not_reserve_future_post(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.stage(posted_at=datetime.now(timezone.utc) + timedelta(days=1))

    def test_unreviewed_posts_do_not_create_a_pass(self):
        self.seed_verified_trading_days()
        self.stage("instagram")
        self.stage("facebook")
        state = account_projection(self.account, as_of=REVIEWED)
        self.assertTrue(state["verified"])
        self.assertFalse(state["assessment"].passed)
        self.assertIn("social_single_post_each_platform_unverified",
                      state["assessment"].reasons)

    def test_non_staff_cannot_verify_without_independent_review(self):
        row = self.stage()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.trader_user,
                audited_facts=FACTS, reviewed_at=REVIEWED,
            )

    def test_second_authenticated_nonstaff_cannot_verify(self):
        row = self.stage()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.other_user,
                audited_facts=FACTS, reviewed_at=REVIEWED,
            )

    def test_review_before_28_full_days_is_not_authorized(self):
        row = self.stage()
        with self.assertRaises(SocialEvidenceRejected):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.reviewer,
                audited_facts=FACTS,
                reviewed_at=row.posted_at + timedelta(days=27, hours=23),
            )

    def test_missing_required_review_fact_rejected(self):
        row = self.stage()
        with self.assertRaises(SocialEvidenceRejected):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.reviewer,
                audited_facts={"public_visible": True}, reviewed_at=REVIEWED,
            )

    def test_false_visible_28day_fact_cannot_become_verified(self):
        row = self.stage()
        reviewed = self.approve(row, continued_visibility_verified=False)
        self.assertEqual(reviewed.review_status, "rejected")
        self.assertFalse(reviewed.continued_visibility_verified)

    def test_review_decision_cannot_be_overwritten_as_positive(self):
        row = self.stage()
        self.approve(row, content_compliant=False)
        with self.assertRaises(SocialEvidenceRejected):
            self.approve(row)
        self.assertEqual(PropSocialEvidence.objects.get(pk=row.pk).review_status, "rejected")

    def test_staff_review_after_28days_creates_verified_private_evidence(self):
        row = self.stage()
        verified = self.approve(row)
        self.assertEqual(verified.review_status, "verified")
        self.assertEqual(verified.reviewed_by_id, self.reviewer.pk)
        self.assertEqual(verified.reviewed_at, REVIEWED)
        self.assertTrue(verified.continued_visibility_verified)

    def test_six_trading_days_but_missing_second_platform_still_fails(self):
        self.seed_verified_trading_days()
        self.approve(self.stage("instagram"))
        state = account_projection(self.account, as_of=REVIEWED)
        self.assertFalse(state["assessment"].passed)
        self.assertEqual(state["social_posting"].reviewed_instagram, 1)
        self.assertEqual(state["social_posting"].reviewed_facebook, 0)

    def test_six_trading_days_and_two_independent_posts_allow_only_policy_pass(self):
        self.seed_verified_trading_days()
        self.approve(self.stage("instagram"))
        self.approve(self.stage("facebook"))
        state = account_projection(self.account, as_of=REVIEWED)
        self.assertTrue(state["verified"])
        self.assertTrue(state["social_posting"].satisfied)
        self.assertTrue(state["assessment"].passed)
        self.assertTrue(state["no_payout_or_trade"])
        self.assertEqual(PropSocialEvidence.objects.count(), 2)

    def test_funded_account_never_accepts_social_evidence(self):
        funded = PropAccount.objects.create(
            trader=self.profile, kind=PropAccount.Kind.FUNDED,
            status=PropAccount.Status.ACTIVE,
            reference="FAKE-TEST-BROKER-NO-LIVE-ACCOUNT",
            tier_index=0, starting_capital_usd=Decimal("100"),
        )
        with self.assertRaises(SocialEvidenceRejected):
            self.stage(account_id=funded.pk)

    def test_no_customer_account_posting_or_broker_trade_from_review(self):
        row = self.stage()
        self.approve(row)
        self.assertEqual(PropAccount.objects.count(), 1)
        self.assertEqual(PropExecution.objects.count(), 0)
        self.assertEqual(PropEquityObservation.objects.count(), 0)
