"""Read-only, unit-scoped arithmetic for the Zomorod financial reconciliation assistant."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from enterprise_portal.models import (
    BusinessUnit, JournalEntry, JournalLine, LedgerAccount, WorkTask,
)
from .analysis import generate_report
from .catalog import CATALOG
from .models import AgentFollowUp, AssistantRun, ProposedAutomation, UnitMembership


STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(DEBUG=False, STORAGES=STORAGES)
class FinancialReconciliationAgentTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_superuser(
            username="finance-owner-test", password="unused-test-only",
        )
        self.analyst = users.objects.create_user(
            username="finance-analyst-test", password="unused-test-only", is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="مزرعه")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        UnitMembership.objects.create(user=self.analyst, unit=self.farm, role="analyst")
        farm_account = LedgerAccount.objects.create(
            unit=self.farm, code="100", name="صندوق آزمایشی", category="asset",
        )
        factory_account = LedgerAccount.objects.create(
            unit=self.factory, code="200", name="حساب کارخانه", category="asset",
        )
        self.farm_entry = JournalEntry.objects.create(
            unit=self.farm, reference="FARM-UNBALANCED", description="داده آزمایشی",
            created_by=self.owner,
        )
        JournalLine.objects.create(
            entry=self.farm_entry, account=farm_account,
            debit=Decimal("100.00"), credit=Decimal("0.00"),
        )
        self.empty_entry = JournalEntry.objects.create(
            unit=self.farm, reference="FARM-EMPTY", description="سند خالی آزمایشی",
            created_by=self.owner,
        )
        self.factory_entry = JournalEntry.objects.create(
            unit=self.factory, reference="FACTORY-SECRET", description="محرمانه",
            created_by=self.owner,
        )
        JournalLine.objects.create(
            entry=self.factory_entry, account=factory_account,
            debit=Decimal("900.00"), credit=Decimal("0.00"),
        )

    def test_reconciliation_is_real_readonly_and_never_claims_bank_access(self):
        self.assertEqual(CATALOG["financial-reconciliation"]["handler"], "reconciliation")
        before = (JournalEntry.objects.count(), JournalLine.objects.count())
        report = generate_report(self.owner, self.farm, "financial-reconciliation")
        self.assertEqual(report.state, "draft")
        self.assertTrue(report.evidence["specialized_engine_connected"])
        self.assertTrue(report.evidence["no_external_side_effects"])
        findings = report.findings
        self.assertTrue(any(
            item["source"] == f"JournalEntry:{self.farm_entry.pk}"
            and item["severity"] == "warning"
            for item in findings
        ))
        self.assertTrue(any(
            item["source"] == f"JournalEntry:{self.empty_entry.pk}"
            for item in findings
        ))
        combined = " ".join(item["title"] + " " + item["detail"] for item in findings)
        self.assertIn("صورت‌حساب بانکی", combined)
        self.assertNotIn("FACTORY-SECRET", combined)
        self.assertNotIn("900.00", combined)
        self.assertEqual(
            (JournalEntry.objects.count(), JournalLine.objects.count()), before,
        )
        self.farm_entry.refresh_from_db()
        self.assertEqual(self.farm_entry.status, "draft")

    def test_journal_and_line_permissions_are_separate_and_unit_bound(self):
        add = Permission.objects.get(
            content_type__app_label="ecosystem_hub", codename="add_assistantrun",
        )
        view_journal = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_journalentry",
        )
        view_line = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_journalline",
        )
        self.analyst.user_permissions.add(add, view_journal)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.farm, "financial-reconciliation")
        self.analyst.user_permissions.add(view_line)
        self.analyst = get_user_model().objects.get(pk=self.analyst.pk)
        report = generate_report(self.analyst, self.farm, "financial-reconciliation")
        self.assertEqual(report.unit, self.farm)
        self.assertEqual(AssistantRun.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.factory, "financial-reconciliation")

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_hourly_reconciliation_creates_bounded_private_followups_only_once(self):
        rule = ProposedAutomation.objects.create(
            unit=self.farm, owner=self.owner,
            assistant_code="financial-reconciliation",
            cadence="hourly", active=True, requires_human_review=True,
            auto_create_tasks=True,
        )
        before = (JournalEntry.objects.count(), JournalLine.objects.count())
        out = StringIO()
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=out,
        )
        self.assertIn("followups=2", out.getvalue())
        self.assertEqual(AgentFollowUp.objects.count(), 2)
        self.assertEqual(WorkTask.objects.count(), 2)
        sources = set(AgentFollowUp.objects.values_list("source_ref", flat=True))
        self.assertEqual(sources, {
            f"JournalEntry:{self.farm_entry.pk}",
            f"JournalEntry:{self.empty_entry.pk}",
        })
        for task in WorkTask.objects.all():
            self.assertEqual(task.unit, self.farm)
            self.assertEqual(task.status, "todo")
            self.assertEqual(task.priority, "high")
            self.assertEqual(task.created_by, self.owner)
            self.assertNotIn("FACTORY-SECRET", task.description)
        self.assertEqual(
            (JournalEntry.objects.count(), JournalLine.objects.count()), before,
        )

        # A later eligible hourly draft must not reopen duplicate tasks.
        rule.last_checked_at = timezone.now() - timedelta(hours=2)
        rule.save(update_fields=("last_checked_at",))
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=StringIO(),
        )
        self.assertEqual(AssistantRun.objects.count(), 2)
        self.assertEqual(AgentFollowUp.objects.count(), 2)
        self.assertEqual(WorkTask.objects.count(), 2)
