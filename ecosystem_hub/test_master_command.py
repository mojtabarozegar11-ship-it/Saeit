"""Private master-command authorization, unit privacy and idempotency checks."""
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from enterprise_portal.models import AuditEvent, BusinessUnit, JournalEntry, StockMovement, WorkTask
from company_marketing.models import Campaign
from .models import AssistantRun, MasterCommand, UnitMembership
from .unified import snapshot_for_unit


STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PATH = "/company/office/ecosystem/master/"


@override_settings(STORAGES=STORE, DEBUG=False, ALLOWED_HOSTS=["testserver"])
@override_settings(COMPANY_OFFICE_REQUIRE_MFA=False)
class MasterCommandSecurityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_superuser(
            username="master-owner", email="owner@example.org", password="not-real",
        )
        self.manager = user_model.objects.create_user(
            username="master-manager", password="not-real", is_staff=True,
        )
        self.analyst = user_model.objects.create_user(
            username="master-analyst", password="not-real", is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        UnitMembership.objects.create(user=self.manager, unit=self.farm, role="manager")
        UnitMembership.objects.create(user=self.analyst, unit=self.farm, role="analyst")
        grants = Permission.objects.filter(
            content_type__app_label__in=("enterprise_portal", "ecosystem_hub"),
            codename__in=(
                "view_businessunit", "view_organization", "view_mastercommand",
                "add_mastercommand", "view_assistantrun", "add_assistantrun",
                "view_managementrisk",
            ),
        )
        self.manager.user_permissions.add(*grants)
        self.analyst.user_permissions.add(*grants)

    def command(self, *, key=None, unit="farm", code="risk-analyst",
                instruction="ریسک‌های ثبت‌شده این واحد را بررسی کن"):
        return {
            "unit": unit,
            "request_key": str(key or uuid4()),
            "assistant_code": code,
            "instruction": instruction,
        }

    def test_owner_can_record_a_real_unit_scoped_command_and_draft(self):
        self.client.force_login(self.owner)
        response = self.client.post(PATH, self.command(), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MasterCommand.objects.count(), 1)
        recorded = MasterCommand.objects.select_related("report").get()
        self.assertEqual(recorded.unit, self.farm)
        self.assertEqual(recorded.status, "draft_ready")
        self.assertEqual(recorded.report.unit, self.farm)
        self.assertEqual(recorded.report.state, "draft")
        self.assertTrue(recorded.report.evidence["requires_human_review"])
        self.assertEqual(AuditEvent.objects.get().action, "ecosystem_master_command_draft")
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_repeat_submit_is_idempotent_and_tampered_key_is_rejected(self):
        self.client.force_login(self.manager)
        key = uuid4()
        payload = self.command(key=key)
        first = self.client.post(PATH, payload, secure=True)
        second = self.client.post(PATH, payload, secure=True)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(MasterCommand.objects.count(), 1)
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        tampered = self.client.post(
            PATH, {**payload, "instruction": "متن دیگر"}, secure=True,
        )
        self.assertEqual(tampered.status_code, 409)
        self.assertEqual(AssistantRun.objects.count(), 1)

    def test_automatic_marketing_command_reads_only_selected_business_unit(self):
        Campaign.objects.create(
            unit=self.farm, code="farm-ads", title="کمپین کشاورزی",
            objective="فروش", status="active", owner=self.owner,
        )
        for number in range(3):
            Campaign.objects.create(
                unit=self.factory, code=f"private-factory-{number}",
                title=f"محرمانه کارخانه {number}",
                objective="تولید", status="active", owner=self.owner,
            )
        self.client.force_login(self.owner)
        result = self.client.post(
            PATH,
            self.command(
                code="auto",
                instruction="کمپین‌های تبلیغات و سرنخ فروش این واحد را بررسی کن",
            ),
            secure=True,
        )
        self.assertEqual(result.status_code, 302)
        record = MasterCommand.objects.select_related("report").get()
        self.assertEqual(record.assistant_code, "marketing-performance")
        self.assertEqual(record.report.unit, self.farm)
        findings = record.report.findings
        self.assertTrue(any(
            item["source"] == "Campaign" and "1 فعال" in item["detail"]
            for item in findings
        ))
        self.assertNotIn("محرمانه کارخانه", str(findings))
        self.assertEqual(AuditEvent.objects.get().detail["routing_mode"], "keyword-scope-v1")

    def test_ambiguous_or_unknown_auto_command_creates_nothing(self):
        self.client.force_login(self.owner)
        for instruction in (
            "ریسک و بودجه را با هم ارزیابی کن",
            "لطفاً یک بررسی انجام بده",
        ):
            response = self.client.post(
                PATH,
                self.command(code="auto", instruction=instruction),
                secure=True,
            )
            self.assertEqual(response.status_code, 422)
            self.assertContains(response, "انتخاب", status_code=422)
        self.assertFalse(MasterCommand.objects.exists())
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_automatic_route_cannot_bypass_marketing_source_permissions(self):
        self.client.force_login(self.manager)
        result = self.client.post(
            PATH, self.command(code="auto", instruction="بازاریابی و کمپین"),
            secure=True,
        )
        self.assertEqual(result.status_code, 403)
        self.assertFalse(MasterCommand.objects.exists())
        self.assertFalse(AssistantRun.objects.exists())

    def test_marketing_permissions_can_authorize_manager_auto_analysis(self):
        allowed = Permission.objects.filter(
            content_type__app_label="company_marketing",
            codename__in=("view_campaign", "view_lead", "view_publication"),
        )
        self.manager.user_permissions.add(*allowed)
        self.client.force_login(self.manager)
        response = self.client.post(
            PATH, self.command(code="auto", instruction="بازاریابی این واحد"),
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(MasterCommand.objects.get().assistant_code, "marketing-performance")

    def test_explicit_command_creates_real_scoped_calendar_task(self):
        self.client.force_login(self.owner)
        due = timezone.localdate() + timedelta(days=1)
        payload = {
            **self.command(instruction="مأموریت محرمانه بررسی ریسک شرکت"),
            "create_task": "1", "due_on": due.isoformat(), "priority": "high",
        }
        response = self.client.post(PATH, payload, secure=True)
        self.assertEqual(response.status_code, 302)
        command = MasterCommand.objects.select_related("task", "report").get()
        task = WorkTask.objects.get()
        self.assertEqual(command.task, task)
        self.assertEqual(task.unit, self.farm)
        self.assertEqual(task.created_by, self.owner)
        self.assertEqual(task.assigned_to, self.owner)
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.due_on, due)
        self.assertEqual(task.status, "todo")
        metrics = {item["label"]: item["count"] for section in snapshot_for_unit(self.owner, self.farm) for item in section["metrics"]}
        self.assertEqual(metrics["کارهای باز"], 1)
        self.assertIn(str(command.pk), task.description)
        self.assertIn(str(command.report_id), task.description)
        self.assertNotIn("محرمانه بررسی ریسک شرکت", task.description)
        self.assertNotIn("محرمانه", task.title)
        self.assertEqual(AuditEvent.objects.get().detail["task_id"], task.pk)

    def test_calendar_task_requires_separate_enterprise_permission(self):
        self.client.force_login(self.manager)
        payload = {
            **self.command(),
            "create_task": "1",
            "priority": "normal",
            "due_on": (timezone.localdate() + timedelta(days=1)).isoformat(),
        }
        result = self.client.post(PATH, payload, secure=True)
        self.assertEqual(result.status_code, 403)
        self.assertFalse(MasterCommand.objects.exists())
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(WorkTask.objects.exists())

    def test_calendar_task_and_report_are_idempotent_on_replay(self):
        self.client.force_login(self.owner)
        key = uuid4()
        payload = {
            **self.command(key=key),
            "create_task": "1",
            "priority": "urgent",
            "due_on": timezone.localdate().isoformat(),
        }
        self.assertEqual(self.client.post(PATH, payload, secure=True).status_code, 302)
        self.assertEqual(self.client.post(PATH, payload, secure=True).status_code, 302)
        self.assertEqual(WorkTask.objects.count(), 1)
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        changed = self.client.post(
            PATH, {**payload, "priority": "normal"}, secure=True,
        )
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(WorkTask.objects.count(), 1)

    def test_invalid_calendar_inputs_never_create_report_or_task(self):
        self.client.force_login(self.owner)
        for priority, due in (
            ("critical", timezone.localdate().isoformat()),
            ("normal", "not-a-date"),
            ("normal", (timezone.localdate() - timedelta(days=1)).isoformat()),
        ):
            response = self.client.post(
                PATH, {
                    **self.command(), "create_task": "1",
                    "priority": priority, "due_on": due,
                }, secure=True,
            )
            self.assertEqual(response.status_code, 400)
        self.assertFalse(MasterCommand.objects.exists())
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(WorkTask.objects.exists())

    def test_linked_calendar_task_cannot_be_swapped_after_recording(self):
        self.client.force_login(self.owner)
        payload = {
            **self.command(), "create_task": "1", "priority": "normal",
            "due_on": timezone.localdate().isoformat(),
        }
        self.assertEqual(self.client.post(PATH, payload, secure=True).status_code, 302)
        command = MasterCommand.objects.get()
        replacement = WorkTask.objects.create(
            unit=self.farm, title="جایگزین غیرمجاز",
            assigned_to=self.owner, created_by=self.owner,
        )
        command.task = replacement
        with self.assertRaises(ValidationError):
            command.save()
        command.refresh_from_db()
        self.assertNotEqual(command.task, replacement)

    def test_recorded_command_instruction_cannot_be_rewritten(self):
        self.client.force_login(self.owner)
        response = self.client.post(PATH, self.command(), secure=True)
        self.assertEqual(response.status_code, 302)
        command = MasterCommand.objects.get()
        command.instruction = "تغییر متن پس از ثبت"
        with self.assertRaises(ValidationError):
            command.save()
        command.refresh_from_db()
        self.assertNotEqual(command.instruction, "تغییر متن پس از ثبت")

    def test_cross_unit_access_and_analyst_commands_are_denied(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(PATH + "?unit=factory", secure=True).status_code, 404)
        self.assertEqual(self.client.post(PATH, self.command(unit="factory"), secure=True).status_code, 404)
        self.assertEqual(MasterCommand.objects.count(), 0)
        self.client.force_login(self.analyst)
        self.assertEqual(self.client.get(PATH + "?unit=farm", secure=True).status_code, 403)
        self.assertEqual(self.client.post(PATH, self.command(), secure=True).status_code, 403)
        self.assertEqual(MasterCommand.objects.count(), 0)

    def test_missing_specialist_engine_is_not_claimed_as_executed(self):
        self.client.force_login(self.owner)
        result = self.client.post(
            PATH, self.command(code="plant-genetics"), secure=True,
        )
        self.assertEqual(result.status_code, 403)
        self.assertFalse(MasterCommand.objects.exists())
        self.assertFalse(AssistantRun.objects.exists())

    def test_get_is_read_only_and_scheduled_or_financial_writes_are_not_triggered(self):
        self.client.force_login(self.owner)
        page = self.client.get(PATH + "?unit=farm", secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "مسترایجنت")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(MasterCommand.objects.count(), 0)
        self.assertEqual(AssistantRun.objects.count(), 0)
        self.assertFalse(AuditEvent.objects.exists())

    def test_csrf_required_for_post_even_from_logged_in_manager(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.owner)
        response = browser.post(PATH, self.command(), secure=True)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MasterCommand.objects.exists())
