"""Marketing dashboard read-access isolation across business modules."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ecosystem_hub.models import UnitMembership
from enterprise_portal.models import BusinessUnit
from company_messaging.models import Contact
from .models import Campaign, ChannelAccount, Lead, PerformanceMetric, Publication


@override_settings(DEBUG=True, COMPANY_OFFICE_REQUIRE_MFA=False)
class MarketingDashboardPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="limited-marketing-reader", password="offline-only", is_staff=True,
        )
        self.unit = BusinessUnit.objects.create(code="marketing-limited", name="واحد مجاز")
        UnitMembership.objects.create(user=self.owner, unit=self.unit, role="analyst")
        self.campaign = Campaign.objects.create(
            unit=self.unit, code="campaign-limited", title="کمپین مجاز",
            objective="Offline test", owner=self.owner,
        )
        self.channel = ChannelAccount.objects.create(
            unit=self.unit, platform="bale", title="PRIVATE-CHANNEL-TITLE",
            destination="PRIVATE-CHANNEL-DESTINATION",
        )
        self.publication = Publication.objects.create(
            campaign=self.campaign, channel=self.channel,
            title="PRIVATE-PUBLICATION-TITLE", content="offline content",
            created_by=self.owner,
        )
        contact = Contact.objects.create(unit=self.unit, name="Private CRM Contact")
        Lead.objects.create(
            unit=self.unit, contact=contact, owner=self.owner, source="offline",
            stage="won", verified_sale_irr=8675309,
            sale_evidence_reference="OFFLINE-EVIDENCE-REF",
        )
        PerformanceMetric.objects.create(
            publication=self.publication, recorded_by=self.owner,
            impressions=17, clicks=3, leads=2, cost_irr=3456789,
            evidence_reference="OFFLINE-METRIC-REF",
        )
        self._grant("view_campaign")
        self.client.force_login(self.owner)

    def _grant(self, *codenames):
        permissions = Permission.objects.filter(
            content_type__app_label="company_marketing", codename__in=codenames,
        )
        self.owner.user_permissions.add(*permissions)
        self.owner = get_user_model().objects.get(pk=self.owner.pk)

    def _page(self):
        return self.client.get(reverse("company_marketing:dashboard"), secure=True)

    def test_campaign_reader_cannot_view_unrelated_private_modules(self):
        response = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "کمپین مجاز")
        for secret in (
            "PRIVATE-CHANNEL-TITLE", "PRIVATE-CHANNEL-DESTINATION",
            "PRIVATE-PUBLICATION-TITLE", "8675309", "3456789",
            "OFFLINE-EVIDENCE-REF",
        ):
            self.assertNotContains(response, secret)
        self.assertContains(response, "نیازمند مجوز مشاهده سرنخ")
        self.assertContains(response, "نیازمند مجوز مشاهده عملکرد")
        self.assertIn("no-store", response["Cache-Control"])

    def test_lead_permission_does_not_expose_cost_or_channel(self):
        self._grant("view_lead")
        response = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "8675309")
        self.assertNotContains(response, "3456789")
        self.assertNotContains(response, "PRIVATE-CHANNEL-DESTINATION")
        self.assertNotContains(response, "PRIVATE-PUBLICATION-TITLE")

    def test_all_read_permissions_restore_scoped_business_view(self):
        self._grant(
            "view_lead", "view_performancemetric",
            "view_publication", "view_channelaccount",
        )
        response = self._page()
        self.assertEqual(response.status_code, 200)
        for expected in (
            "کمپین مجاز", "8675309", "3456789",
            "PRIVATE-CHANNEL-DESTINATION", "PRIVATE-PUBLICATION-TITLE",
        ):
            self.assertContains(response, expected)
