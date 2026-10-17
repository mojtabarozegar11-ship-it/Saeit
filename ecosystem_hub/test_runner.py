"""No false 24/7-agent claims: opt-in, unit-safe, audited deterministic drafts."""
from datetime import datetime, timedelta, timezone as utc_timezone
from io import StringIO
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, RequestFactory, override_settings
from django.utils import timezone

from enterprise_portal.models import AuditEvent, BusinessUnit, JournalEntry, StockMovement
from .management.commands.run_ecosystem_assistants import is_due
from .models import AssistantRun, ProposedAutomation, UnitMembership


class CalendarDueRulesTests(SimpleTestCase):
    def test_weekly_requires_seven_elapsed_calendar_days(self):
        now = datetime(2026, 10, 17, 14, tzinfo=utc_timezone.utc)
        rule = SimpleNamespace(
            assistant_code="risk-analyst", active=True,
            requires_human_review=True, cadence="weekly",
            last_checked_at=now - timedelta(days=6),
        )
        with override_settings(TIME_ZONE="UTC"):
            self.assertFalse(is_due(rule, now=now))
            rule.last_checked_at = now - timedelta(days=7)
            self.assertTrue(is_due(rule, now=now))

    def test_monthly_uses_next_calendar_month_and_shorter_months(self):
        with override_settings(TIME_ZONE="UTC"):
            rule = SimpleNamespace(
                assistant_code="risk-analyst", active=True,
                requires_human_review=True, cadence="monthly",
                last_checked_at=datetime(2026, 1, 31, 12, tzinfo=utc_timezone.utc),
            )
            self.assertFalse(is_due(
                rule, now=datetime(2026, 2, 27, 15, tzinfo=utc_timezone.utc),
            ))
            self.assertTrue(is_due(
                rule, now=datetime(2026, 2, 28, 15, tzinfo=utc_timezone.utc),
            ))

    def test_unsupported_agent_and_inactive_rule_never_due(self):
        now = datetime(2026, 10, 17, 14, tzinfo=utc_timezone.utc)
        rule = SimpleNamespace(
            assistant_code="plant-genetics", active=True,
            requires_human_review=True, cadence="daily", last_checked_at=None,
        )
        self.assertFalse(is_due(rule, now=now))
        rule.assistant_code = "risk-analyst"
        rule.active = False
        self.assertFalse(is_due(rule, now=now))
        rule.active = True
        rule.requires_human_review = False
        self.assertFalse(is_due(rule, now=now))


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
    DEBUG=False,
    ALLOWED_HOSTS=["testserver"],
)
class AssistantRunnerIsolationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_superuser(
            username="scheduled-owner-test", password="unused-test-password",
            email="owner@example.org",
        )
        self.alice = users.objects.create_user(
            username="analyst-runner-test", password="unused-test-password",
            is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        UnitMembership.objects.create(user=self.alice, unit=self.farm, role="analyst")

    def rule(self, unit=None, owner=None, *, code="risk-analyst", cadence="daily", active=True):
        return ProposedAutomation.objects.create(
            unit=unit or self.farm, owner=owner or self.owner,
            assistant_code=code, cadence=cadence, active=active,
            requires_human_review=True,
        )

    def test_default_invocation_is_preview_only_and_never_writes(self):
        rule = self.rule()
        out = StringIO()
        call_command("run_ecosystem_assistants", stdout=out)
        self.assertIn("PREVIEW", out.getvalue())
        self.assertIn("commit=0", out.getvalue())
        self.assertEqual(AssistantRun.objects.count(), 0)
        self.assertFalse(AuditEvent.objects.exists())
        rule.refresh_from_db()
        self.assertIsNone(rule.last_checked_at)

    def test_live_execution_is_disabled_without_explicit_kill_switch(self):
        self.rule()
        with override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=False):
            with self.assertRaises(CommandError):
                call_command("run_ecosystem_assistants", "--commit", stdout=StringIO())
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_authorized_execution_generates_one_audited_draft_only(self):
        rule = self.rule()
        out = StringIO()
        call_command("run_ecosystem_assistants", "--commit", stdout=out)
        self.assertIn("DRAFT_CREATED", out.getvalue())
        report = AssistantRun.objects.get()
        self.assertEqual(report.unit, self.farm)
        self.assertEqual(report.state, "draft")
        self.assertTrue(report.evidence["no_external_side_effects"])
        rule.refresh_from_db()
        self.assertIsNotNone(rule.last_checked_at)
        audit = AuditEvent.objects.get()
        self.assertEqual(audit.action, "ecosystem_scheduled_draft")
        self.assertTrue(audit.detail["no_external_side_effects"])
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

        call_command("run_ecosystem_assistants", "--commit", stdout=StringIO())
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_unit_filter_and_invalid_batch_size_are_enforced(self):
        farm = self.rule()
        factory = self.rule(unit=self.factory)
        call_command(
            "run_ecosystem_assistants", "--commit", "--unit=farm", stdout=StringIO(),
        )
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertEqual(AssistantRun.objects.get().unit, self.farm)
        factory.refresh_from_db()
        self.assertIsNone(factory.last_checked_at)
        with self.assertRaises(CommandError):
            call_command("run_ecosystem_assistants", "--commit", "--limit=1000", stdout=StringIO())

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_invalid_user_permissions_do_not_consume_due_schedule(self):
        rule = self.rule(owner=self.alice, unit=self.factory)
        errors = StringIO()
        out = StringIO()
        call_command("run_ecosystem_assistants", "--commit", stdout=out, stderr=errors)
        self.assertIn("errors=1", out.getvalue())
        self.assertIn("DENIED", errors.getvalue())
        rule.refresh_from_db()
        self.assertIsNone(rule.last_checked_at)
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_unsupported_specialist_is_not_misreported_as_running(self):
        unknown = self.rule(code="plant-genetics")
        call_command("run_ecosystem_assistants", "--commit", stdout=StringIO())
        self.assertFalse(AssistantRun.objects.exists())
        unknown.refresh_from_db()
        self.assertIsNone(unknown.last_checked_at)

    def test_manager_cannot_schedule_runner_under_owner_identity(self):
        panel = admin.site._registry[ProposedAutomation]
        request = RequestFactory().post("/admin/ecosystem_hub/proposedautomation/add/")
        request.user = self.alice
        obj = ProposedAutomation(
            unit=self.farm, owner=self.owner, assistant_code="risk-analyst",
            active=True, requires_human_review=True,
        )
        with self.assertRaises(PermissionDenied):
            panel.save_model(request, obj, None, change=False)
        self.assertFalse(ProposedAutomation.objects.exists())

    def test_admin_cannot_publish_schedule_for_missing_specialist_engine(self):
        panel = admin.site._registry[ProposedAutomation]
        request = RequestFactory().post("/admin/ecosystem_hub/proposedautomation/add/")
        request.user = self.owner
        obj = ProposedAutomation(
            unit=self.farm, owner=self.owner, assistant_code="plant-genetics",
            active=True, requires_human_review=True,
        )
        with self.assertRaises(ValidationError):
            panel.save_model(request, obj, None, change=False)
        self.assertFalse(ProposedAutomation.objects.exists())
