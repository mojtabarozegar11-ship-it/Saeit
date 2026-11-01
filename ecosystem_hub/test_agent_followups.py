"""Scheduled Zomorod agents may create bounded *internal* human follow-ups only."""
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from company_marketing.models import Campaign
from enterprise_portal.models import (
    AuditEvent, BusinessUnit, JournalEntry, StockMovement, WorkTask,
)
from .followups import MAX_NEW_TASKS_PER_CYCLE, _warning_sources
from .models import AgentFollowUp, AssistantRun, ProposedAutomation, UnitMembership


STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    DEBUG=False, ALLOWED_HOSTS=["testserver"], STORAGES=STORE,
    ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True,
)
class ScheduledFollowUpTests(TestCase):
    def setUp(self):
        Users = get_user_model()
        self.owner = Users.objects.create_superuser(
            username="followup-owner", password="test-only", email="owner@example.org",
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="کشاورزی")
        self.factory = BusinessUnit.objects.create(code="factory", name="صنعت")
        self.today = timezone.localdate()

    def campaign(self, number, *, unit=None, owner=None):
        return Campaign.objects.create(
            unit=unit or self.farm, code=f"campaign-{number}",
            title=f"محرمانه کمپین شماره {number}", objective="بررسی عملکرد",
            status="active", owner=owner or self.owner,
            starts_on=self.today - timedelta(days=10),
            ends_on=self.today - timedelta(days=1),
        )

    def rule(self, *, unit=None, owner=None, auto=True):
        return ProposedAutomation.objects.create(
            unit=unit or self.farm, owner=owner or self.owner,
            assistant_code="marketing-performance",
            cadence="hourly", active=True,
            requires_human_review=True, auto_create_tasks=auto,
        )

    def run(self, *args):
        output = StringIO()
        errors = StringIO()
        call_command("run_ecosystem_assistants", *args, stdout=output, stderr=errors)
        return output.getvalue(), errors.getvalue()

    def test_preview_is_read_only_even_when_task_creation_is_opted_in(self):
        rule = self.rule()
        self.campaign(1)
        out, err = self.run()
        self.assertIn("PREVIEW", out)
        self.assertIn("auto_tasks=1", out)
        self.assertEqual(err, "")
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(WorkTask.objects.exists())
        self.assertFalse(AgentFollowUp.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
        rule.refresh_from_db()
        self.assertIsNone(rule.last_checked_at)

    def test_default_rule_never_creates_followups(self):
        self.rule(auto=False)
        self.campaign(1)
        out, errors = self.run("--commit")
        self.assertIn("DRAFT_CREATED", out)
        self.assertEqual(errors, "")
        self.assertEqual(AssistantRun.objects.count(), 1)
        self.assertFalse(WorkTask.objects.exists())
        self.assertFalse(AgentFollowUp.objects.exists())
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_authorized_warning_creates_one_traceable_task_and_no_external_action(self):
        rule = self.rule()
        campaign = self.campaign(1)
        out, errors = self.run("--commit")
        self.assertIn("followups=1", out)
        self.assertEqual(errors, "")
        linked = AgentFollowUp.objects.select_related("task", "report").get()
        task = linked.task
        self.assertEqual(linked.rule, rule)
        self.assertEqual(linked.source_ref, f"Campaign:{campaign.pk}")
        self.assertEqual(task.unit, self.farm)
        self.assertEqual(task.assigned_to, self.owner)
        self.assertEqual(task.created_by, self.owner)
        self.assertEqual(task.status, "todo")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.due_on, self.today + timedelta(days=1))
        self.assertNotIn(campaign.title, task.title)
        self.assertNotIn(campaign.title, task.description)
        self.assertTrue(linked.report.evidence["requires_human_review"])
        audit = AuditEvent.objects.get(action="ecosystem_agent_followup_created")
        self.assertEqual(audit.target, f"WorkTask:{task.pk}")
        self.assertTrue(audit.detail["no_external_side_effects"])
        self.assertEqual(AuditEvent.objects.get(action="ecosystem_scheduled_draft").detail["followups"]["created"], 1)
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

    def test_repeated_hourly_warning_does_not_duplicate_unfinished_task(self):
        rule = self.rule()
        self.campaign(1)
        self.run("--commit")
        rule.last_checked_at = timezone.now() - timedelta(hours=2)
        rule.save(update_fields=("last_checked_at",))
        self.run("--commit")
        self.assertEqual(AssistantRun.objects.count(), 2)
        self.assertEqual(AgentFollowUp.objects.count(), 1)
        self.assertEqual(WorkTask.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="ecosystem_agent_followup_created").count(), 1)
        later = AuditEvent.objects.filter(action="ecosystem_scheduled_draft").order_by("-pk").first()
        self.assertEqual(later.detail["followups"]["already_tracked"], 1)
        self.assertEqual(later.detail["followups"]["created"], 0)

    def test_task_creation_is_bounded_and_unit_scoped(self):
        self.rule()
        for i in range(12):
            self.campaign(i)
        self.campaign("secret", unit=self.factory)
        out, errors = self.run("--commit", "--unit=farm")
        self.assertEqual(errors, "")
        self.assertIn(f"followups={MAX_NEW_TASKS_PER_CYCLE}", out)
        self.assertEqual(WorkTask.objects.count(), MAX_NEW_TASKS_PER_CYCLE)
        self.assertEqual(AgentFollowUp.objects.count(), MAX_NEW_TASKS_PER_CYCLE)
        self.assertFalse(WorkTask.objects.exclude(unit=self.farm).exists())
        self.assertFalse(AgentFollowUp.objects.filter(source_ref="Campaign:13").exists())
        detail = AuditEvent.objects.get(action="ecosystem_scheduled_draft").detail
        self.assertGreater(detail["followups"]["capacity_skipped"], 0)

    def test_missing_task_permission_rolls_back_due_claim_and_report(self):
        Users = get_user_model()
        manager = Users.objects.create_user(
            username="followup-manager", password="test-only", is_staff=True,
        )
        UnitMembership.objects.create(user=manager, unit=self.farm, role="manager")
        perms = Permission.objects.filter(
            content_type__app_label__in=("ecosystem_hub", "company_marketing",
                                         "enterprise_portal"),
            codename__in=(
                "add_assistantrun", "view_campaign", "view_lead",
                "view_publication", "view_worktask", "view_businessunit",
            ),
        )
        manager.user_permissions.add(*list(perms))
        rule = self.rule(owner=manager)
        self.campaign(1, owner=manager)
        out, errors = self.run("--commit")
        self.assertIn("errors=1", out)
        self.assertIn("DENIED", errors)
        rule.refresh_from_db()
        self.assertIsNone(rule.last_checked_at)
        self.assertFalse(AssistantRun.objects.exists())
        self.assertFalse(AgentFollowUp.objects.exists())
        self.assertFalse(WorkTask.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_only_known_real_source_identifiers_are_eligible(self):
        report = SimpleNamespace(findings=[
            {"severity": "warning", "source": "Campaign:7"},
            {"severity": "warning", "source": "Campaign:7"},
            {"severity": "warning", "source": "WorkTask:100"},
            {"severity": "warning", "source": "Campaign"},
            {"severity": "info", "source": "Campaign:8"},
            {"severity": "warning", "source": "Campaign:../../etc"},
            {"severity": "warning", "source": "Campaign:0"},
            {"severity": "warning", "source": "SecretField:9"},
        ])
        self.assertEqual(list(_warning_sources(report)), [("Campaign:7", "warning")])

    def test_links_are_immutable_and_admin_is_read_only(self):
        self.rule()
        self.campaign(1)
        self.run("--commit")
        link = AgentFollowUp.objects.get()
        with self.assertRaises(ValidationError):
            link.save()
        panel = admin.site._registry[AgentFollowUp]
        self.assertFalse(panel.has_add_permission(None))
        self.assertFalse(panel.has_change_permission(None, link))
        self.assertFalse(panel.has_delete_permission(None, link))
