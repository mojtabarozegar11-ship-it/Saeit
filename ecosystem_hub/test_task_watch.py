"""Smart calendar is unit-scoped, auditable, and only drafts follow-ups."""
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from enterprise_portal.models import AuditEvent, BusinessUnit, JournalEntry, StockMovement, WorkTask
from .analysis import generate_report
from .models import AssistantRun, ProposedAutomation, UnitMembership
from .task_watch import watch_for_unit


STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
ROOM = "/company/office/ecosystem/master/"


@override_settings(
    DEBUG=False, ALLOWED_HOSTS=["testserver"], STORAGES=STORE,
    COMPANY_OFFICE_REQUIRE_MFA=False,
)
class SmartCalendarWatchTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_superuser(
            username="watch-owner", email="watch@example.org", password="not-a-secret",
        )
        self.manager = users.objects.create_user(
            username="watch-manager", password="not-a-secret", is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        self.today = timezone.localdate()
        UnitMembership.objects.create(user=self.manager, unit=self.farm, role="manager")
        perms = Permission.objects.filter(
            content_type__app_label__in=("ecosystem_hub", "enterprise_portal"),
            codename__in=(
                "view_businessunit", "view_organization", "view_mastercommand",
                "add_mastercommand", "view_assistantrun", "add_assistantrun",
                "view_managementrisk",
            ),
        )
        self.manager.user_permissions.add(*perms)

    def task(self, title, *, unit=None, due=None, status="todo", priority="normal"):
        return WorkTask.objects.create(
            unit=unit or self.farm, title=title, description="داخلی",
            assigned_to=self.manager, created_by=self.owner,
            due_on=due, status=status, priority=priority,
        )

    def test_counts_are_unit_scoped_and_exclude_completed_tasks(self):
        self.task("عقب‌افتاده", due=self.today - timedelta(days=2), priority="urgent")
        self.task("امروز", due=self.today)
        self.task("سه روز آینده", due=self.today + timedelta(days=3))
        self.task("ده روز آینده", due=self.today + timedelta(days=10))
        self.task("بدون سررسید")
        self.task("انجام شده", due=self.today - timedelta(days=3), status="done")
        self.task("نام دیگر محرمانه", unit=self.factory, due=self.today - timedelta(days=3))
        snapshot = watch_for_unit(self.farm, today=self.today)
        self.assertEqual(snapshot["counts"], {
            "open": 5, "overdue": 1, "due_today": 1,
            "due_soon": 1, "urgent": 1, "no_due": 1,
        })
        selected = [task.title for task in snapshot["tasks"]]
        self.assertEqual(selected, ["عقب‌افتاده", "امروز", "سه روز آینده"])
        self.assertNotIn("نام دیگر محرمانه", selected)

    def test_far_off_urgent_tasks_still_enter_priority_queue_and_limit_is_bounded(self):
        self.task("فوری بدون موعد", priority="urgent")
        self.task("فوری آینده دور", due=self.today + timedelta(days=60), priority="urgent")
        for i in range(20):
            self.task(f"کار پیگیری {i:02d}", due=self.today)
        snapshot = watch_for_unit(self.farm, today=self.today, limit=1000)
        self.assertEqual(len(snapshot["tasks"]), 12)
        self.assertIn("فوری بدون موعد", [task.title for task in snapshot["tasks"]])
        self.assertIn("فوری آینده دور", [task.title for task in snapshot["tasks"]])
        self.assertEqual(snapshot["counts"]["open"], 22)
        urgent_only = watch_for_unit(self.farm, today=self.today, limit=30)
        self.assertEqual(urgent_only["counts"]["urgent"], 2)

    def test_authorized_agent_report_contains_actionable_task_sources_not_other_unit(self):
        mine = self.task("گزارش فروش امروز", due=self.today - timedelta(days=1))
        self.task("محرمانه واحد دیگر", unit=self.factory, due=self.today - timedelta(days=1))
        report = generate_report(self.owner, self.farm, "performance-coach")
        self.assertEqual(report.state, "draft")
        self.assertTrue(report.evidence["requires_human_review"])
        self.assertTrue(any(
            finding["source"] == f"WorkTask:{mine.pk}"
            and "گزارش فروش امروز" in finding["title"]
            for finding in report.findings
        ))
        self.assertNotIn("محرمانه واحد دیگر", str(report.findings))

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_hourly_cycle_records_audited_snapshot_without_duplicate_or_task_mutation(self):
        old = self.task("وظیفه معوق", due=self.today - timedelta(days=1))
        ProposedAutomation.objects.create(
            unit=self.farm, owner=self.owner, assistant_code="performance-coach",
            cadence="hourly", active=True, requires_human_review=True,
        )
        call_command("run_ecosystem_assistants", "--commit", stdout=StringIO())
        self.assertEqual(AssistantRun.objects.count(), 1)
        audit = AuditEvent.objects.get()
        self.assertEqual(audit.action, "ecosystem_scheduled_draft")
        self.assertEqual(audit.detail["task_watch"]["overdue"], 1)
        self.assertTrue(audit.detail["no_external_side_effects"])
        call_command("run_ecosystem_assistants", "--commit", stdout=StringIO())
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        old.refresh_from_db()
        self.assertEqual(old.status, "todo")
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_manager_without_view_task_permission_cannot_see_private_task_watch(self):
        self.task("یادداشت اختصاصی کشاورزی", due=self.today)
        self.task("محرمانه کارخانه", unit=self.factory, due=self.today)
        self.client.force_login(self.manager)
        denied = self.client.get(ROOM + "?unit=farm", secure=True)
        self.assertEqual(denied.status_code, 200)
        self.assertNotContains(denied, "تقویم هوشمند پیگیری")
        self.assertNotContains(denied, "یادداشت اختصاصی کشاورزی")
        self.manager.user_permissions.add(Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_worktask",
        ))
        # Django may cache permission grants on the original user object.
        self.manager = get_user_model().objects.get(pk=self.manager.pk)
        self.client.force_login(self.manager)
        permitted = self.client.get(ROOM + "?unit=farm", secure=True)
        self.assertEqual(permitted.status_code, 200)
        self.assertContains(permitted, "تقویم هوشمند پیگیری")
        self.assertContains(permitted, "یادداشت اختصاصی کشاورزی")
        self.assertNotContains(permitted, "محرمانه کارخانه")
