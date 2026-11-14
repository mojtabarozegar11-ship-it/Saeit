"""C22: operator can inspect two-post cohort evidence without altering money.

These checks verify the actual Django admin registration, not public access.
"""
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase

from prop_firm.models import PropChallengeEnrollment, PropSocialEvidence


class PropFourWeekAdminReadOnlyTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/prop_firm/")

    def test_paid_purchase_cohort_is_registered_for_private_review(self):
        self.assertIn(PropChallengeEnrollment, admin.site._registry)

    def test_social_post_evidence_is_registered_for_private_review(self):
        self.assertIn(PropSocialEvidence, admin.site._registry)

    def test_purchase_cohort_never_allows_admin_add(self):
        obj = admin.site._registry[PropChallengeEnrollment]
        self.assertFalse(obj.has_add_permission(self.request))
        self.assertFalse(obj.has_change_permission(self.request))
        self.assertFalse(obj.has_delete_permission(self.request))

    def test_post_evidence_never_allows_admin_add_or_edit(self):
        obj = admin.site._registry[PropSocialEvidence]
        self.assertFalse(obj.has_add_permission(self.request))
        self.assertFalse(obj.has_change_permission(self.request))
        self.assertFalse(obj.has_delete_permission(self.request))

    def test_purchase_admin_shows_provenance_not_paid_income(self):
        display = admin.site._registry[PropChallengeEnrollment].list_display
        self.assertIn("verified_invoice_ref", display)
        self.assertIn("settlement_verified", display)
        self.assertIn("terms_version", display)
        self.assertNotIn("money_received", display)

    def test_social_admin_shows_four_week_status_not_old_daily_count(self):
        display = admin.site._registry[PropSocialEvidence].list_display
        self.assertIn("enrollment_id", display)
        self.assertIn("continued_visibility_verified", display)
        self.assertNotIn("trading_day", display)

    def test_owner_personal_page_remains_non_publishable(self):
        from prop_firm.social_policy import valid_platform_post_url
        self.assertFalse(valid_platform_post_url(
            "https://facebook.com/102203064721826/posts/12345", "facebook",
        ))
        self.assertFalse(valid_platform_post_url(
            "https://instagram.com/p/dr.mojtaba.rozegar", "instagram",
        ))
