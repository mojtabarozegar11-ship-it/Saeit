"""Django regressions for exactly one externally reviewed social post per paid cohort.

Never publishes posts, creates a live invoice, transfers TRX or trades.
"""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from prop_firm.models import (
    PropTrader, PropAccount, PropChallengeEnrollment, PropSocialEvidence,
)
from prop_firm.rules import POLICY
from prop_firm.social_review_service import (
    SocialEvidenceRejected, submit_social_evidence, review_social_evidence,
)

START = timezone.now() - timedelta(days=32)
FACTS = {
    "author_verified": True,
    "public_visible": True,
    "disclosure_verified": True,
    "content_compliant": True,
    "date_verified": True,
    "continued_visibility_verified": True,
}


class OnePostEnrollmentDatabaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.trader = U.objects.create_user(
            username="one_post_buyer", password="test-only"
        )
        cls.other = U.objects.create_user(
            username="other_buyer", password="test-only"
        )
        cls.operator = U.objects.create_user(
            username="one_post_operator", password="test-only", is_staff=True
        )
        cls.profile = PropTrader.objects.create(user=cls.trader)
        cls.purchase = PropChallengeEnrollment.objects.create(
            trader=cls.profile, verified_invoice_ref="synthetic-test-only-invoice",
            confirmed_at=START, settlement_verified=True,
            terms_version=POLICY.version,
        )
        cls.phase1 = PropAccount.objects.create(
            trader=cls.profile, kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            opened_at=START, challenge_enrollment=cls.purchase,
            policy_version=POLICY.version,
        )
        cls.phase2 = PropAccount.objects.create(
            trader=cls.profile, kind=PropAccount.Kind.PHASE_TWO,
            status=PropAccount.Status.ACTIVE,
            opened_at=START, challenge_enrollment=cls.purchase,
            policy_version=POLICY.version,
        )

    def submit(self, *, account=None, platform="instagram", **changes):
        data = dict(
            account_id=(account or self.phase1).pk,
            submitter=self.trader,
            platform=platform,
            post_url=("https://www.instagram.com/p/one-post-example"
                      if platform == "instagram" else
                      "https://www.facebook.com/trader/posts/998877"),
            posted_at=START + timedelta(hours=1),
            explicit_consent=True,
        )
        data.update(changes)
        return submit_social_evidence(**data)

    def approve(self, row, **changes):
        return review_social_evidence(
            evidence_id=row.pk,
            reviewer=self.operator,
            audited_facts={**FACTS, **changes},
            reviewed_at=row.posted_at + timedelta(days=28, hours=1),
        )

    def test_one_instagram_post_is_stored_as_pending(self):
        row = self.submit()
        self.assertEqual(row.review_status, "pending")
        self.assertEqual(PropSocialEvidence.objects.count(), 1)
        self.assertEqual(row.enrollment_id, self.purchase.pk)

    def test_one_facebook_post_is_valid_alternative(self):
        row = self.submit(platform="facebook")
        self.assertEqual(row.platform, "facebook")
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_second_post_same_network_is_blocked(self):
        self.submit()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit()
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_second_post_different_network_is_not_required_or_allowed(self):
        self.submit()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(platform="facebook")
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_both_simulated_phases_share_single_purchase_evidence(self):
        self.submit(account=self.phase1)
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(account=self.phase2, platform="facebook")
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_post_without_explicit_consent_is_denied(self):
        with self.assertRaises(PermissionDenied):
            self.submit(explicit_consent=False)
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_post_from_different_account_owner_denied(self):
        with self.assertRaises(PermissionDenied):
            self.submit(submitter=self.other)

    def test_unsettled_purchase_never_unlocks_post(self):
        self.purchase.settlement_verified = False
        self.purchase.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit()

    def test_old_policy_account_not_retroactively_forced(self):
        self.phase1.policy_version = "2026-11-14/v1.1"
        self.phase1.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit()

    def test_post_after_24_hours_rejected(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(posted_at=START + timedelta(hours=25))

    def test_post_before_purchase_rejected(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(posted_at=START - timedelta(minutes=1))

    def test_banned_owner_profile_not_valid(self):
        with self.assertRaises(SocialEvidenceRejected):
            self.submit(post_url="https://www.instagram.com/p/dr.mojtaba.rozegar")

    def test_nonstaff_cannot_approve(self):
        row = self.submit()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.other,
                audited_facts=FACTS,
            )

    def test_buyer_cannot_approve_own_post(self):
        row = self.submit()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.trader,
                audited_facts=FACTS,
            )

    def test_review_before_full_four_weeks_fails(self):
        row = self.submit()
        with self.assertRaises(SocialEvidenceRejected):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.operator,
                audited_facts=FACTS,
                reviewed_at=row.posted_at + timedelta(days=27),
            )

    def test_independent_28_day_review_changes_status(self):
        row = self.submit()
        result = self.approve(row)
        self.assertEqual(result.review_status, "verified")
        self.assertTrue(result.continued_visibility_verified)
        self.assertEqual(result.reviewed_by_id, self.operator.pk)

    def test_missing_disclosure_is_rejected(self):
        row = self.submit()
        result = self.approve(row, disclosure_verified=False)
        self.assertEqual(result.review_status, "rejected")

    def test_rejected_review_cannot_be_replayed(self):
        row = self.submit()
        self.approve(row, content_compliant=False)
        with self.assertRaises(SocialEvidenceRejected):
            self.approve(row)

    def test_missing_manual_fact_cannot_be_reviewed(self):
        row = self.submit()
        facts = dict(FACTS)
        facts.pop("date_verified")
        with self.assertRaises(SocialEvidenceRejected):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.operator,
                audited_facts=facts,
                reviewed_at=row.posted_at + timedelta(days=28, hours=1),
            )

    def test_database_itself_rejects_duplicate_across_platforms(self):
        row = self.submit()
        competing = PropSocialEvidence(
            account=self.phase2, enrollment=self.purchase,
            platform="facebook",
            post_url="https://www.facebook.com/trader/posts/33333",
            posted_at=row.posted_at,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PropSocialEvidence.objects.bulk_create([competing])
        self.assertEqual(PropSocialEvidence.objects.count(), 1)

    def test_foreign_enrollment_is_not_accepted(self):
        other_profile = PropTrader.objects.create(user=self.other)
        other_enrollment = PropChallengeEnrollment.objects.create(
            trader=other_profile,
            verified_invoice_ref="synthetic-other-purchase",
            confirmed_at=START,
            settlement_verified=True,
            terms_version=POLICY.version,
        )
        self.phase1.challenge_enrollment = other_enrollment
        self.phase1.save()
        with self.assertRaises(SocialEvidenceRejected):
            self.submit()
