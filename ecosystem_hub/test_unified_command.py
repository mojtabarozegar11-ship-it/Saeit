"""Regression checks for Zomorod Melal's read-only unified command desk."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone

from company_marketing.models import Campaign
from enterprise_portal.models import BusinessUnit, JournalEntry, WorkTask
from .models import UnitMembership
from .unified import snapshot_for_unit


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PATH = "/company/office/ecosystem/command/"


def counts(sections):
    """Flatten labels only after model- and unit-level permissions are checked."""
    return {metric["label"]: metric["count"]
            for section in sections for metric in section["metrics"]}


@override_settings(STORAGES=TEST_STORAGES, DEBUG=False, ALLOWED_HOSTS=["testserver"])
@override_settings(COMPANY_OFFICE_REQUIRE_MFA=False)
class UnifiedBusinessCommandTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.farm = BusinessUnit.objects.create(code="farm", name="واحد کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="واحد کارخانه")
        self.owner = users.objects.create_superuser(
            username="business-owner", email="owner@example.org", password="unrelated",
        )
        self.analyst = users.objects.create_user(
            username="business-analyst", password="unrelated", is_staff=True,
        )
        UnitMembership.objects.create(user=self.analyst, unit=self.farm, role="analyst")
        permissions = Permission.objects.filter(
            content_type__app_label__in=("enterprise_portal", "company_marketing", "ecosystem_hub"),
            codename__in=("view_organization", "view_worktask", "view_campaign"),
        )
        self.analyst.user_permissions.add(*permissions)

        WorkTask.objects.create(
            title="پیگیری مزرعه", unit=self.farm, assigned_to=self.analyst,
            created_by=self.owner, due_on=timezone.localdate() - timedelta(days=1),
        )
        for n in range(3):
            WorkTask.objects.create(
                title=f"سند کارخانه محرمانه {n}", unit=self.factory, assigned_to=self.owner,
                created_by=self.owner, due_on=timezone.localdate() - timedelta(days=1),
            )
        Campaign.objects.create(
            unit=self.farm, code="farm-campaign", title="آگهی مزرعه",
            objective="توسعه فروش", owner=self.owner, status="active",
        )
        for n in range(2):
            Campaign.objects.create(
                unit=self.factory, code=f"factory-campaign-{n}",
                title=f"تبلیغ کارخانه محرمانه {n}", objective="توسعه فروش",
                owner=self.owner, status="active",
            )
        JournalEntry.objects.create(
            unit=self.farm, reference="J-F", description="پیش‌نویس مزرعه",
            created_by=self.owner,
        )

    def test_superuser_dashboard_counts_only_selected_unit(self):
        farm = counts(snapshot_for_unit(self.owner, self.farm))
        factory = counts(snapshot_for_unit(self.owner, self.factory))
        self.assertEqual(farm["کارهای باز"], 1)
        self.assertEqual(factory["کارهای باز"], 3)
        self.assertEqual(farm["کمپین‌های فعال"], 1)
        self.assertEqual(factory["کمپین‌های فعال"], 2)
        self.assertEqual(farm["اسناد حسابداری پیش‌نویس"], 1)
        self.assertEqual(factory["اسناد حسابداری پیش‌نویس"], 0)
        self.assertEqual(farm["کارهای عقب‌افتاده"], 1)
        self.assertEqual(factory["کارهای عقب‌افتاده"], 3)

    def test_analyst_sees_only_authorized_unit_and_permitted_modules(self):
        self.client.force_login(self.analyst)
        response = self.client.get(PATH + "?unit=farm", secure=True)
        self.assertEqual(response.status_code, 200)
        shown = counts(response.context["sections"])
        self.assertEqual(shown["کارهای باز"], 1)
        self.assertEqual(shown["کمپین‌های فعال"], 1)
        self.assertNotIn("اسناد حسابداری پیش‌نویس", shown)
        self.assertNotIn("پیام‌های منتظر ارسال", shown)
        self.assertNotContains(response, "کارخانه محرمانه")
        self.assertIn("no-store", response.get("Cache-Control", ""))

    def test_other_unit_cannot_be_selected_by_query_parameter(self):
        self.client.force_login(self.analyst)
        response = self.client.get(PATH + "?unit=factory", secure=True)
        self.assertEqual(response.status_code, 404)

    def test_view_is_get_only_and_does_not_mutate_business_records(self):
        self.client.force_login(self.owner)
        before = (WorkTask.objects.count(), Campaign.objects.count(), JournalEntry.objects.count())
        response = self.client.post(PATH + "?unit=farm", {"action": "execute"}, secure=True)
        self.assertEqual(response.status_code, 405)
        self.client.get(PATH + "?unit=farm", secure=True)
        after = (WorkTask.objects.count(), Campaign.objects.count(), JournalEntry.objects.count())
        self.assertEqual(before, after)

    def test_hub_permission_is_required(self):
        self.analyst.user_permissions.remove(*Permission.objects.filter(
            content_type__app_label="ecosystem_hub", codename="view_organization",
        ))
        self.client.force_login(self.analyst)
        response = self.client.get(PATH + "?unit=farm", secure=True)
        self.assertEqual(response.status_code, 403)
