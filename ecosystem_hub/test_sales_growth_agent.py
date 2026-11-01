"""Verified CRM funnel semantics and opt-in, deduplicated sales follow-ups."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from company_marketing.models import Lead
from company_messaging.models import Contact, Message
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
class SalesGrowthAgentTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_superuser(
            username="growth-owner-test", password="unused-test-only",
        )
        self.analyst = users.objects.create_user(
            username="growth-analyst-test", password="unused-test-only",
            is_staff=True,
        )
        self.farm = BusinessUnit.objects.create(code="farm", name="مزرعه")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        UnitMembership.objects.create(
            user=self.analyst, unit=self.farm, role="analyst",
        )
        farm_contact = Contact.objects.create(unit=self.farm, name="Farm Private")
        factory_contact = Contact.objects.create(
            unit=self.factory, name="Factory Secret Contact",
        )
        self.old_new = Lead.objects.create(
            unit=self.farm, contact=farm_contact,
            stage="new", source="internal", owner=self.owner,
        )
        Lead.objects.filter(pk=self.old_new.pk).update(
            created_at=timezone.now() - timedelta(days=9),
        )
        self.qualified = Lead.objects.create(
            unit=self.farm, contact=farm_contact, stage="qualified",
            source="internal", estimated_value_irr=Decimal("9999999"),
            owner=self.owner,
        )
        self.won = Lead.objects.create(
            unit=self.farm, contact=farm_contact, stage="won",
            source="internal", verified_sale_irr=Decimal("1200"),
            sale_evidence_reference="TEST-CRM-REFERENCE", owner=self.owner,
        )
        Lead.objects.create(
            unit=self.factory, contact=factory_contact, stage="won",
            source="factory-private", verified_sale_irr=Decimal("8888888"),
            sale_evidence_reference="SECRET-FACTORY-REFERENCE",
            owner=self.owner,
        )
        farm_partner = Partner.objects.create(
            unit=self.farm, kind="customer", name="Farm Business",
        )
        factory_partner = Partner.objects.create(
            unit=self.factory, kind="customer", name="Factory Hidden Partner",
        )
        yesterday = timezone.localdate() - timedelta(days=1)
        self.farm_invoice = CommercialDocument.objects.create(
            unit=self.farm, partner=farm_partner, number="FARM-SALE-DUE",
            kind="sales", status="approved", due_on=yesterday,
            total=Decimal("4200.00"), created_by=self.owner,
        )
        CommercialDocument.objects.create(
            unit=self.factory, partner=factory_partner, number="FACTORY-SECRET-INVOICE",
            kind="sales", status="approved", due_on=yesterday,
            total=Decimal("8888888.00"), created_by=self.owner,
        )

    def test_crm_and_sales_use_real_unit_data_without_claiming_bank_receipts(self):
        self.assertEqual(CATALOG["crm-service"]["handler"], "crm")
        self.assertEqual(CATALOG["sales-pipeline"]["handler"], "sales")
        before = list(Lead.objects.values_list(
            "pk", "stage", "verified_sale_irr",
        ).order_by("pk"))
        crm = generate_report(self.owner, self.farm, "crm-service")
        sales = generate_report(self.owner, self.farm, "sales-pipeline")
        self.assertTrue(crm.evidence["specialized_engine_connected"])
        self.assertTrue(sales.evidence["specialized_engine_connected"])
        self.assertTrue(crm.evidence["no_external_side_effects"])
        self.assertTrue(any(
            item["source"] == f"Lead:{self.old_new.pk}"
            and item["severity"] == "warning"
            for item in crm.findings
        ))
        self.assertFalse(any(
            item["source"] == f"Lead:{self.won.pk}"
            and item["severity"] == "warning"
            for item in crm.findings
        ))
        sales_text = " ".join(
            item["title"] + " " + item["detail"]
            for item in sales.findings
        )
        self.assertIn("1200", sales_text)
        self.assertIn("بانکی", sales_text)
        self.assertIn("فاکتور", sales_text)
        self.assertNotIn("9999999", sales_text)
        self.assertNotIn("8888888", sales_text)
        self.assertNotIn("FACTORY-SECRET", sales_text)
        self.assertNotIn("Factory Secret", sales_text)
        self.assertEqual(
            list(Lead.objects.values_list(
                "pk", "stage", "verified_sale_irr",
            ).order_by("pk")), before,
        )
        self.farm_invoice.refresh_from_db()
        self.assertEqual(self.farm_invoice.status, "approved")
        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(WorkTask.objects.count(), 0)

    def test_sales_documents_and_crm_leads_have_separate_permissions(self):
        add = Permission.objects.get(
            content_type__app_label="ecosystem_hub", codename="add_assistantrun",
        )
        view_lead = Permission.objects.get(
            content_type__app_label="company_marketing", codename="view_lead",
        )
        view_document = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_commercialdocument",
        )
        self.analyst.user_permissions.add(add, view_lead)
        crm = generate_report(self.analyst, self.farm, "crm-service")
        self.assertEqual(crm.unit, self.farm)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.farm, "sales-pipeline")
        self.analyst.user_permissions.add(view_document)
        self.analyst = get_user_model().objects.get(pk=self.analyst.pk)
        sales = generate_report(self.analyst, self.farm, "sales-pipeline")
        self.assertEqual(sales.unit, self.farm)
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.factory, "crm-service")
        with self.assertRaises(PermissionDenied):
            generate_report(self.analyst, self.factory, "sales-pipeline")

    @override_settings(ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True)
    def test_hourly_crm_creates_only_private_deduplicated_human_followup(self):
        rule = ProposedAutomation.objects.create(
            unit=self.farm, owner=self.owner, assistant_code="crm-service",
            cadence="hourly", active=True, requires_human_review=True,
            auto_create_tasks=True,
        )
        out = StringIO()
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=out,
        )
        self.assertIn("followups=1", out.getvalue())
        self.assertEqual(AgentFollowUp.objects.count(), 1)
        self.assertEqual(
            AgentFollowUp.objects.get().source_ref, f"Lead:{self.old_new.pk}",
        )
        self.assertEqual(WorkTask.objects.count(), 1)
        task = WorkTask.objects.get()
        self.assertEqual(task.unit, self.farm)
        self.assertEqual(task.status, "todo")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.created_by, self.owner)
        self.assertNotIn("Factory Secret", task.description)
        self.assertEqual(Message.objects.count(), 0)

        rule.last_checked_at = timezone.now() - timedelta(hours=2)
        rule.save(update_fields=("last_checked_at",))
        call_command(
            "run_ecosystem_assistants", "--commit", "--strict",
            "--json-receipt", "--unit=farm", stdout=StringIO(),
        )
        self.assertEqual(AssistantRun.objects.count(), 2)
        self.assertEqual(AgentFollowUp.objects.count(), 1)
        self.assertEqual(WorkTask.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 0)
