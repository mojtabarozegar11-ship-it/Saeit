"""Read-only supplier operations signals; independent quality review remains human."""
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
    BusinessUnit, CommercialDocument, Partner, WorkTask,
)
from .analysis import generate_report
from .catalog import CATALOG
from .models import AgentFollowUp, AssistantRun, ProposedAutomation, UnitMembership


STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(DEBUG=False, STORAGES=STORAGES)
class SupplierReviewAgentTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_superuser(
            username="supplier-owner-test", password="unused-test-only",
        )
        self.analyst = users.objects.create_user(
            username="supplier-analyst-test", password="unused-test-only",
            is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="مزرعه")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        UnitMembership.objects.create(user=self.analyst, unit=self.farm, role="analyst")
        self.farm_supplier = Partner.objects.create(
            unit=self.farm, name="Farm Supplier", kind="supplier",
        )
        self.factory_supplier = Partner.objects.create(
            unit=self.factory, name="Factory Secret Supplier", kind="supplier",
        )
        self.customer = Partner.objects.create(
            unit=self.farm, name="Farm Customer", kind="customer",
        )
        yesterday = timezone.localdate() - timedelta(days=1)
        self.farm_purchase = CommercialDocument.objects.create(
            unit=self.farm, partner=self.farm_supplier,
            number="FARM-OVERDUE", kind="purchase", due_on=yesterday,
            total=Decimal("1200.00"), status="approved", created_by=self.owner,
        )
        CommercialDocument.objects.create(
            unit=self.factory, partner=self.factory_supplier,
            number="FACTORY-SECRET", kind="purchase", due_on=yesterday,
            total=Decimal("98765.00"), status="approved", created_by=self.owner,
        )
        CommercialDocument.objects.create(
            unit=self.farm, partner=self.customer,
            number="CUSTOMER-EXCLUDED", kind="purchase", due_on=yesterday,
            total=Decimal("55.00"), status="approved", created_by=self.owner,
        )
        CommercialDocument.objects.create(
            unit=self.farm, partner=self.farm_supplier,
            number="SETTLED-EXCLUDED", kind="purchase", due_on=yesterday,
            total=Decimal("40.00"), status="settled", created_by=self.owner,
        )

    def test_supplier_review_is_unit_bound_readonly_and_not_a_quality_score(self):
        self.assertEqual(CATALOG["supplier-review"]["handler"], "supplier")
        before = list(CommercialDocument.objects.values_list(
            "pk", "status", "total",
        ).order_by("pk"))
        report = generate_report(self.owner, self.farm, "supplier-review")
        self.assertEqual(report.state, "draft")
        self.assertTrue(report.evidence["specialized_engine_connected"])
        self.assertTrue(report.evidence["no_external_side_effects"])
        findings = report.findings
        self.assertTrue(any(
            f["source"] == f"CommercialDocument:{self.farm_purchase.pk}"
            and f["severity"] == "warning"
            for f in findings
        ))
        self.assertTrue(any(
            f["source"] == f"Partner:{self.farm_supplier.pk}"
            for f in findings
        ))
        combined = " ".join(f["title"] + " " + f["detail"] for f in findings)
        self.assertIn("کیفیت کالا", combined)
        self.assertNotIn("Factory Secret Supplier", combined)
        self.assertNotIn("FACTORY-SECRET", combined)
        self.assertNotIn("98765", combined)
        self.assertNotIn("CUSTOMER-EXCLUDED", combined)
        self.assertNotIn("SETTLED-EXCLUDED", combined)
        self.assertEqual(
            list(CommercialDocument.objects.values_list(
                "pk", "status", "total",
            ).order_by("pk")), before,
        )
        self.assertEqual(WorkTask.objects.count(), 0)

    def test_both_source_permissions_and_active_unit_membership_are_required(self):
        add = Permission.objects.get(
            content_type__app_label="ecosystem_hub", codename="add_assistantrun",
        )
        view_partner = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_partner",
        )
        view_document = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_commercialdocument",
        )
        self.analyst.user_permissions.add(add, view_partner)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.farm, "supplier-review")
        self.analyst.user_permissions.add(view_document)
        self.analyst = get_user_model().objects.get(pk=self.analyst.pk)
        report = generate_report(self.analyst, self.farm, "supplier-review")
        self.assertEqual(report.unit, self.farm)
        self.assertEqual(AssistantRun.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.factory, "supplier-review")
        membership = UnitMembership.objects.get(user=self.analyst, unit=self.farm)
        membership.active = False
        membership.save(update_fields=("active",))
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.farm, "supplier-review")

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_hourly_cycle_creates_deduplicated_human_task_not_purchase(self):
        rule = ProposedAutomation.objects.create(
            unit=self.farm, owner=self.owner, assistant_code="supplier-review",
            cadence="hourly", active=True, requires_human_review=True,
            auto_create_tasks=True,
        )
        before = list(CommercialDocument.objects.values_list(
            "pk", "status", "total",
        ).order_by("pk"))
        out = StringIO()
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=out,
        )
        self.assertIn("followups=1", out.getvalue())
        self.assertEqual(AgentFollowUp.objects.count(), 1)
        self.assertEqual(
            AgentFollowUp.objects.get().source_ref,
            f"CommercialDocument:{self.farm_purchase.pk}",
        )
        self.assertEqual(WorkTask.objects.count(), 1)
        task = WorkTask.objects.get()
        self.assertEqual(task.unit, self.farm)
        self.assertEqual(task.status, "todo")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.created_by, self.owner)
        self.assertNotIn("FACTORY-SECRET", task.description)
        self.assertEqual(
            list(CommercialDocument.objects.values_list(
                "pk", "status", "total",
            ).order_by("pk")), before,
        )

        rule.last_checked_at = timezone.now() - timedelta(hours=2)
        rule.save(update_fields=("last_checked_at",))
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=StringIO(),
        )
        self.assertEqual(AssistantRun.objects.count(), 2)
        self.assertEqual(AgentFollowUp.objects.count(), 1)
        self.assertEqual(WorkTask.objects.count(), 1)
