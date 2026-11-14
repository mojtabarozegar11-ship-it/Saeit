"""C22 incremental adversarial checks beyond parent PR's 28-day contract tests.

The test purchase/settlement is an isolated synthetic DB fixture, never TRX.
No social provider API, message, real broker, wallet or deployment is used.
"""
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase

from prop_firm.models import (
    PropAccount, PropChallengeEnrollment, PropSocialEvidence, PropTrader,
)
from prop_firm.rules import POLICY
from prop_firm.social_policy import valid_platform_post_url
from prop_firm.social_review_service import (
    SocialEvidenceRejected, submit_social_evidence, review_social_evidence,
)

START = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
REVIEWED = START + timedelta(days=29)
FACTS = {
    "author_verified": True,
    "public_visible": True,
    "disclosure_verified": True,
    "content_compliant": True,
    "date_verified": True,
    "continued_visibility_verified": True,
}


class ForbiddenPersonalSocialAliasTests(SimpleTestCase):
    def test_linked_facebook_page_id_is_never_qualifying_proof(self):
        self.assertFalse(valid_platform_post_url(
            "https://facebook.com/102203064721826/posts/123456", "facebook",
        ))

    def test_connected_metricool_brand_id_is_never_qualifying_proof(self):
        self.assertFalse(valid_platform_post_url(
            "https://www.facebook.com/7317306/posts/123456", "facebook",
        ))

    def test_personal_handle_in_facebook_or_instagram_path_is_blocked(self):
        for url, kind in (
            ("https://instagram.com/p/dr.mojtaba.rozegar", "instagram"),
            ("https://facebook.com/dr.mojtaba.rozegar/posts/12345", "facebook"),
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, kind))

    def test_percent_encoded_personal_page_id_cannot_bypass_ban(self):
        self.assertFalse(valid_platform_post_url(
            "https://facebook.com/%31%30%32%32%30%33%30%36%34%37%32%31%38%32%36/posts/12345",
            "facebook",
        ))

    def test_unicode_and_encoded_path_cannot_override_exact_platform(self):
        self.assertFalse(valid_platform_post_url(
            "https://instagram.com/p/abc\u200b123", "instagram",
        ))
        self.assertFalse(valid_platform_post_url(
            "https://instagram.com/p/abc123%2fextra", "instagram",
        ))

    def test_nested_post_path_and_spoof_host_fail_closed(self):
        for url in (
            "https://facebook.com/trader/posts/12345/extra",
            "https://facebook.com.evil.net/trader/posts/12345",
            "https://name@facebook.com/trader/posts/12345",
        ):
            with self.subTest(url=url):
                self.assertFalse(valid_platform_post_url(url, "facebook"))


class C22ImmutableHumanReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.user = U.objects.create_user(
            username="c22_customer", password="synthetic",
        )
        cls.staff = U.objects.create_user(
            username="c22_reviewer", password="synthetic", is_staff=True,
        )
        cls.outsider = U.objects.create_user(
            username="c22_outsider", password="synthetic",
        )
        cls.profile = PropTrader.objects.create(user=cls.user)
        cls.purchase = PropChallengeEnrollment.objects.create(
            trader=cls.profile,
            verified_invoice_ref="C22-SYNTHETIC-NOT-ONCHAIN",
            settlement_verified=True,
            terms_version=POLICY.version,
            confirmed_at=START,
        )
        cls.account = PropAccount.objects.create(
            trader=cls.profile,
            challenge_enrollment=cls.purchase,
            kind=PropAccount.Kind.PHASE_ONE,
            status=PropAccount.Status.ACTIVE,
            opened_at=START,
            policy_version=POLICY.version,
        )

    def pending(self):
        return submit_social_evidence(
            account_id=self.account.pk, submitter=self.user,
            platform="instagram",
            post_url="https://instagram.com/p/c22ValidPost99",
            posted_at=START + timedelta(hours=1),
            explicit_consent=True,
        )

    def approved(self):
        row = self.pending()
        return review_social_evidence(
            evidence_id=row.pk, reviewer=self.staff,
            audited_facts=FACTS,
            reviewed_at=REVIEWED,
        )

    def test_owner_page_id_rejected_before_creating_a_record(self):
        with self.assertRaises(SocialEvidenceRejected):
            submit_social_evidence(
                account_id=self.account.pk, submitter=self.user,
                platform="facebook",
                post_url="https://facebook.com/102203064721826/posts/98765",
                posted_at=START + timedelta(hours=1),
                explicit_consent=True,
            )
        self.assertFalse(PropSocialEvidence.objects.exists())

    def test_pending_original_post_link_cannot_be_reassigned(self):
        row = self.pending()
        row.post_url = "https://instagram.com/p/swapPost12345"
        with self.assertRaisesRegex(ValidationError, "immutable"):
            row.save()
        row.refresh_from_db()
        self.assertEqual(row.post_url, "https://instagram.com/p/c22ValidPost99")

    def test_pending_post_cannot_be_moved_to_other_purchase(self):
        row = self.pending()
        row.enrollment_id = None
        with self.assertRaisesRegex(ValidationError, "immutable"):
            row.save()

    def test_final_verification_cannot_be_reverted_to_pending(self):
        row = self.approved()
        row.review_status = "pending"
        with self.assertRaisesRegex(ValidationError, "cannot be rewritten"):
            row.save()
        self.assertEqual(
            PropSocialEvidence.objects.get(pk=row.pk).review_status, "verified",
        )

    def test_final_visibility_evidence_is_immutable(self):
        row = self.approved()
        row.continued_visibility_verified = False
        with self.assertRaisesRegex(ValidationError, "cannot be rewritten"):
            row.save()

    def test_nonstaff_cannot_force_django_model_to_verified(self):
        row = self.pending()
        row.review_status = "verified"
        row.reviewed_by = self.outsider
        row.reviewed_at = REVIEWED
        for key in FACTS:
            setattr(row, key, True)
        with self.assertRaises(ValidationError):
            row.save()

    def test_future_review_timestamp_cannot_be_saved_by_staff(self):
        row = self.pending()
        row.review_status = "verified"
        row.reviewed_by = self.staff
        row.reviewed_at = datetime.now(timezone.utc) + timedelta(days=1)
        for key in FACTS:
            setattr(row, key, True)
        with self.assertRaises(ValidationError):
            row.save()

    def test_customer_cannot_review_own_social_evidence(self):
        row = self.pending()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.user,
                audited_facts=FACTS, reviewed_at=REVIEWED,
            )

    def test_nonstaff_cannot_review_trader_post(self):
        row = self.pending()
        with self.assertRaises(PermissionDenied):
            review_social_evidence(
                evidence_id=row.pk, reviewer=self.outsider,
                audited_facts=FACTS, reviewed_at=REVIEWED,
            )

    def test_approved_review_is_still_only_proof_not_a_customer_order(self):
        self.approved()
        self.assertEqual(PropAccount.objects.count(), 1)
        self.assertEqual(PropSocialEvidence.objects.count(), 1)
        # No money/transfers/email or broker connections are called by this API.
