"""Private assistant operations reporting never means autonomous execution."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone

from enterprise_portal.models import BusinessUnit, JournalEntry, StockMovement
from .models import AssistantRun, ProposedAutomation, UnitMembership
from .analysis import generate_report

STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(DEBUG=False, STORAGES=STORE, ALLOWED_HOSTS=["testserver"])
class AssistantOperationsTests(TestCase):
    def setUp(self):
        Users = get_user_model()
        self.owner = Users.objects.create_superuser(
            username="ecosystem-owner", password="only-in-test", email="owner@example.org",
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        self.analyst = Users.objects.create_user(
            username="farm-analyst", password="only-in-test", is_staff=True,
        )
        self.factory_reader = Users.objects.create_user(
            username="factory-reader", password="only-in-test", is_staff=True,
        )
        UnitMembership.objects.create(user=self.analyst, unit=self.farm, role="analyst")
        UnitMembership.objects.create(user=self.factory_reader, unit=self.factory, role="analyst")
        perms = Permission.objects.filter(
            content_type__app_label__in=("ecosystem_hub", "enterprise_portal"),
            codename__in=("view_organization", "view_assistantrun",
                           "view_proposedautomation", "view_businessunit"),
        )
        for user in (self.analyst, self.factory_reader):
            user.user_permissions.add(*list(perms))

    def test_control_room_blocks_anonymous_and_insecure_http(self):
        url = "/company/office/ecosystem/assistants/operations/"
        self.assertEqual(self.client.get(url, secure=True).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_control_room_is_read_only_and_never_claims_24_hour_worker(self):
        rule = ProposedAutomation.objects.create(
            unit=self.farm, assistant_code="risk-analyst", owner=self.owner,
            cadence="daily", active=True,
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            "/company/office/ecosystem/assistants/operations/?unit=farm", secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "وضعیت موتور اجرا: تأیید نشده")
        self.assertContains(response, "فعال در تنظیمات")
        self.assertContains(response, "موعد بررسی رسیده")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())
        rule.refresh_from_db()
        self.assertIsNone(rule.last_checked_at)

    def test_scoped_staff_sees_only_own_schedule_and_reports(self):
        ProposedAutomation.objects.create(
            unit=self.farm, assistant_code="risk-analyst", owner=self.owner, active=True,
        )
        ProposedAutomation.objects.create(
            unit=self.farm, assistant_code="agent-supervisor", owner=self.analyst, active=True,
        )
        ProposedAutomation.objects.create(
            unit=self.factory, assistant_code="risk-analyst",
            owner=self.factory_reader, active=True,
        )
        AssistantRun.objects.create(
            unit=self.farm, assistant_code="risk-analyst",
            requested_by=self.owner, findings=[{"title": "محرمانه صاحب واحد"}],
        )
        AssistantRun.objects.create(
            unit=self.farm, assistant_code="agent-supervisor", requested_by=self.analyst,
            findings=[{"title": "گزارش مخصوص تحلیلگر"}],
        )
        self.client.force_login(self.analyst)
        response = self.client.get(
            "/company/office/ecosystem/assistants/operations/?unit=farm", secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["schedule_count"], 1)
        self.assertEqual(response.context["report_count"], 1)
        self.assertContains(response, "گزارش مخصوص تحلیلگر", count=0)
        self.assertNotContains(response, "محرمانه صاحب واحد")
        self.assertNotContains(response, "factory-reader")
        self.assertEqual(self.client.get(
            "/company/office/ecosystem/assistants/operations/?unit=factory", secure=True,
        ).status_code, 404)

    def test_staff_without_source_read_permission_cannot_see_sensitive_archives(self):
        finance = generate_report(self.owner, self.farm, "receivables")
        independent = AssistantRun.objects.create(
            unit=self.farm, assistant_code="agent-supervisor", requested_by=self.analyst,
            findings=[{"title": "تنظیمات داخلی"}],
        )
        self.client.force_login(self.analyst)
        response = self.client.get(
            "/company/office/ecosystem/assistants/operations/?unit=farm", secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report_count"], 1)
        self.assertNotContains(response, f"/reports/{finance.pk}/")
        self.assertContains(response, f"/reports/{independent.pk}/")

    def test_finance_report_revocation_takes_effect_in_operations_dashboard(self):
        perms = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_commercialdocument",
        )
        self.analyst.user_permissions.add(perms)
        report = generate_report(self.analyst, self.farm, "receivables")
        self.client.force_login(self.analyst)
        url = "/company/office/ecosystem/assistants/operations/?unit=farm"
        self.assertContains(self.client.get(url, secure=True), f"/reports/{report.pk}/")
        self.analyst.user_permissions.remove(perms)
        response = self.client.get(url, secure=True)
        self.assertNotContains(response, f"/reports/{report.pk}/")

    def test_combined_permission_required_for_monitoring(self):
        perm = Permission.objects.get(
            content_type__app_label="ecosystem_hub",
            codename="view_proposedautomation",
        )
        self.analyst.user_permissions.remove(perm)
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(
            "/company/office/ecosystem/assistants/operations/", secure=True,
        ).status_code, 403)
