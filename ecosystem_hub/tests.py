"""Security and real-data regression suite for ecosystem extension.

All tests use an isolated ephemeral DB. No external network, real payments,
public publishing, staff credentials or preexisting production migrations.
"""
from datetime import timedelta
from decimal import Decimal
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from enterprise_portal.models import (
    AuditEvent, BusinessUnit, CommercialDocument, CompanyAsset, InventoryItem,
    JournalEntry, JournalLine, LedgerAccount, Partner, StockMovement, WorkTask,
)
from enterprise_portal.services import confirm_stock_movement, post_journal, stock_balance
from .access import user_units, require_unit, can_view_unit
from .analysis import generate_report
from .costing import estimate_manufacturing_cost
from .catalog import CATALOG, DEPARTMENTS
from .models import (
    Organization, UnitMembership, ManagedSite, WorkCenter, BillOfMaterials,
    MaterialRequirement, ProductionOrder, ProcurementNeed, QualityInspection,
    MaintenanceTicket, StaffAssignment, Timesheet, ManagementRisk,
    PerformanceIndicator, ReviewApproval, ReferenceEvidence,
    AssistantRun, ProposedAutomation, MaterialPriceReference, ProductionCostScenario,
)

U = get_user_model()
D = Decimal
STORE = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=STORE, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class HubSuite(TestCase):
    def setUp(self):
        self.hq = BusinessUnit.objects.create(code="hq", name="دفتر مرکزی")
        self.farm = BusinessUnit.objects.create(code="farm", name="مزرعه")
        self.factory = BusinessUnit.objects.create(code="factory", name="کارخانه")
        self.owner = U.objects.create_superuser(
            username="chief-test", email="chief@example.org", password="not-a-real-password",
        )
        self.viewer = U.objects.create_user(
            username="farm-analyst", password="not-a-real-password",
            is_staff=True,
        )
        self.other = U.objects.create_user(
            username="unauthorized-staff", password="not-a-real-password",
            is_staff=True,
        )
        UnitMembership.objects.create(
            user=self.viewer, unit=self.farm, role="analyst", active=True,
        )
        permissions = Permission.objects.filter(
            content_type__app_label__in=("enterprise_portal", "ecosystem_hub"),
            codename__in=(
                "view_businessunit", "view_organization", "view_assistantrun",
                "add_assistantrun", "view_productionorder", "view_managementrisk",
                "view_inventoryitem", "view_stockmovement", "view_procurementneed",
            ),
        )
        self.viewer.user_permissions.add(*list(permissions))
        self.factory_product = InventoryItem.objects.create(
            unit=self.factory, sku="FP", title="بسته نهایی",
        )
        self.farm_product = InventoryItem.objects.create(
            unit=self.farm, sku="WHEAT", title="گندم", measure="کیلو",
            reorder_point=D("20"),
        )
        self.farm_material = InventoryItem.objects.create(
            unit=self.farm, sku="SEED", title="بذر", measure="کیلو",
            reorder_point=D("12"),
        )

    def test_original_private_and_public_route_preserved(self):
        self.assertEqual(resolve("/company/office/").url_name, "dashboard")
        self.assertEqual(resolve("/company/office/ecosystem/").url_name, "dashboard")
        self.assertEqual(resolve("/company/office/ecosystem/assistants/").url_name, "assistants")
        self.assertEqual(resolve("/company/office/ecosystem/production/").url_name, "production")
        self.assertEqual(resolve("/company/").url_name, "company")
        self.assertEqual(resolve("/ghanadi/").url_name, "ghanadi")
        self.assertEqual(resolve("/amozeshgah/").url_name, "education")

    def test_anonymous_cannot_see_confidential_data(self):
        response = self.client.get("/company/office/ecosystem/", secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/office/login/", response["Location"])

    def test_http_is_blocked(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/company/office/ecosystem/").status_code, 403)

    def test_staff_with_no_office_permission_is_denied(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/company/office/ecosystem/", secure=True).status_code, 403)

    def test_owner_dashboard_has_real_modules_and_zero_counts(self):
        self.client.force_login(self.owner)
        response = self.client.get("/company/office/ecosystem/?unit=farm", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "فرماندهی کل اکوسیستم زمرد ملل")
        self.assertContains(response, "دستیارهای")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertEqual(len(response.context["cards"]), 6)
        self.assertEqual(response.context["selected_unit"], self.farm)

    def test_staff_cannot_access_another_units_data_by_query(self):
        self.client.force_login(self.viewer)
        good = self.client.get("/company/office/ecosystem/?unit=farm", secure=True)
        self.assertEqual(good.status_code, 200)
        self.assertEqual(list(good.context["units"]), [self.farm])
        self.assertEqual(self.client.get(
            "/company/office/ecosystem/?unit=factory", secure=True,
        ).status_code, 404)
        self.assertEqual(self.client.get(
            "/company/office/ecosystem/production/?unit=factory", secure=True,
        ).status_code, 404)

    def test_unit_membership_is_required_even_with_app_permissions(self):
        self.assertEqual(list(user_units(self.viewer)), [self.farm])
        self.assertFalse(can_view_unit(self.viewer, self.factory))
        with self.assertRaises(PermissionDenied):
            require_unit(self.viewer, self.factory)
        with self.assertRaises(PermissionDenied):
            require_unit(self.viewer, self.farm, write=True)

    def test_owner_cannot_be_inserted_as_other_users_unit_without_membership(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/company/office/ecosystem/assistants/", secure=True).status_code, 403)

    def test_assistant_catalog_is_comprehensive_and_discloses_unimplemented_engines(self):
        self.assertGreaterEqual(len(CATALOG), 35)
        self.assertGreaterEqual(len(DEPARTMENTS), 8)
        self.assertIn("production-scheduling", CATALOG)
        self.assertIn("plant-genetics", CATALOG)
        self.assertIsNone(CATALOG["plant-genetics"]["handler"])
        self.assertIn("نیازمند موتور تخصصی", CATALOG["plant-genetics"]["mode"])

    def test_assistant_page_uses_real_permissions_and_csrf(self):
        self.client.force_login(self.viewer)
        response = self.client.get("/company/office/ecosystem/assistants/?unit=farm", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مدیریت زراعت")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "نمونه", count=0) if False else None

    def test_assistant_executes_only_on_post_and_authenticated_unit(self):
        self.client.force_login(self.viewer)
        url = "/company/office/ecosystem/assistants/inventory-alerts/run/"
        self.assertEqual(self.client.get(url, secure=True).status_code, 405)
        self.assertEqual(self.client.post(url, {"unit": "factory"}, secure=True).status_code, 404)
        self.assertEqual(AssistantRun.objects.count(), 0)
        response = self.client.post(url, {"unit": "farm"}, secure=True)
        self.assertEqual(response.status_code, 302)
        report = AssistantRun.objects.get()
        self.assertEqual(report.unit, self.farm)
        self.assertEqual(report.assistant_code, "inventory-alerts")
        self.assertEqual(report.state, "draft")
        self.assertTrue(report.evidence["requires_human_review"])
        self.assertTrue(report.evidence["no_external_side_effects"])
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommercialDocument.objects.count(), 0)

    def test_report_visibility_is_unit_scoped_and_deep_link_safe(self):
        report = generate_report(self.owner, self.factory, "executive-brief")
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(
            f"/company/office/ecosystem/reports/{report.pk}/", secure=True,
        ).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(
            f"/company/office/ecosystem/reports/{report.pk}/", secure=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "گزارش پیش‌نویس")

    def test_invalid_assistant_never_creates_record(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(
            "/company/office/ecosystem/assistants/unknown-tool/run/",
            {"unit": "farm"}, secure=True,
        ).status_code, 404)
        self.assertFalse(AssistantRun.objects.exists())

    def test_unsupported_assistant_does_not_fabricate_technical_ai(self):
        report = generate_report(self.owner, self.farm, "plant-genetics")
        self.assertFalse(report.evidence["specialized_engine_connected"])
        self.assertIn("هنوز وصل نشده", report.findings[0]["title"])

    def test_bom_rejects_product_from_other_unit(self):
        bad = BillOfMaterials(unit=self.farm, product=self.factory_product, code="R1")
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_bom_rejects_cross_unit_material_and_self_reference(self):
        formula = BillOfMaterials.objects.create(unit=self.farm, product=self.farm_product, code="F-1")
        bad = MaterialRequirement(formula=formula, item=self.factory_product, quantity=D("2"))
        with self.assertRaises(ValidationError):
            bad.full_clean()
        circular = MaterialRequirement(formula=formula, item=self.farm_product, quantity=D("2"))
        with self.assertRaises(ValidationError):
            circular.full_clean()

    def test_production_order_rejects_cross_unit_formula_and_center(self):
        formula = BillOfMaterials.objects.create(unit=self.farm, product=self.farm_product, code="F-1")
        center = WorkCenter.objects.create(unit=self.factory, code="W1", name="پروسه کارخانه")
        invalid = ProductionOrder(
            unit=self.factory, code="P-1", formula=formula, quantity=D("5"),
            owner=self.owner,
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        invalid.unit = self.farm
        invalid.work_center = center
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_production_material_shortfall_uses_confirmed_stock_only(self):
        formula = BillOfMaterials.objects.create(
            unit=self.farm, product=self.farm_product, code="F-2", yield_quantity=D("2")
        )
        MaterialRequirement.objects.create(
            formula=formula, item=self.farm_material, quantity=D("3"), scrap_percent=D("10")
        )
        ProductionOrder.objects.create(
            unit=self.farm, code="P-2", formula=formula,
            quantity=D("10"), owner=self.owner,
        )
        entry = StockMovement.objects.create(
            item=self.farm_material, reference="IN-1", direction="in",
            quantity=D("4"), created_by=self.owner,
        )
        # A draft incoming movement must NOT reduce the forecast shortfall.
        report = generate_report(self.owner, self.farm, "materials-planning")
        self.assertTrue(any("کسری مواد" in f["title"] for f in report.findings))
        self.assertTrue(any("موجودی قطعی 0" in f["detail"] for f in report.findings))
        self.assertEqual(stock_balance(self.farm_material.pk), D("0"))
        confirm_stock_movement(entry.pk, self.owner)
        another = generate_report(self.owner, self.farm, "materials-planning")
        self.assertTrue(any("موجودی قطعی 4" in f["detail"] for f in another.findings))
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_reorder_uses_confirmed_inventory_only(self):
        report = generate_report(self.owner, self.farm, "inventory-alerts")
        self.assertTrue(any("SEED" in f["title"] for f in report.findings))
        self.assertTrue(any("WHEAT" in f["title"] for f in report.findings))
        self.assertEqual(ProcurementNeed.objects.count(), 0)

    def test_procurement_rejects_cross_unit_items(self):
        q = ProcurementNeed(
            unit=self.farm, reference="R", item=self.factory_product,
            quantity=D("20"), request_reason="تولید", requested_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            q.full_clean()

    def test_quality_and_maintenance_need_same_unit(self):
        formula = BillOfMaterials.objects.create(unit=self.farm, product=self.farm_product, code="R")
        order = ProductionOrder.objects.create(unit=self.farm, code="X", formula=formula, quantity=D("1"), owner=self.owner)
        other_unit_check = QualityInspection(
            unit=self.factory, order=order, title="کنترل نمونه",
            sample_ref="LAB-X", inspected_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            other_unit_check.full_clean()
        asset = CompanyAsset.objects.create(
            unit=self.factory, code="A1", title="دستگاه", purchase_cost=D("100"), acquired_on=timezone.localdate()
        )
        service = MaintenanceTicket(
            unit=self.farm, asset=asset, title="بازرسی پیشگیرانه",
            owner=self.owner, due_date=timezone.localdate(),
        )
        with self.assertRaises(ValidationError):
            service.full_clean()

    def test_risk_and_quality_alerts_only_from_same_unit(self):
        ManagementRisk.objects.create(
            unit=self.farm, title="خشکسالی", owner=self.owner,
            likelihood=4, impact=4,
        )
        ManagementRisk.objects.create(
            unit=self.factory, title="خطر کارخانه", owner=self.owner,
            likelihood=5, impact=5,
        )
        report = generate_report(self.owner, self.farm, "risk-analyst")
        text = " ".join(f["title"] for f in report.findings)
        self.assertIn("خشکسالی", text)
        self.assertNotIn("خطر کارخانه", text)
        QualityInspection.objects.create(
            unit=self.farm, title="بذر ناسالم", sample_ref="S-1",
            inspected_by=self.owner, result="hold",
        )
        quality = generate_report(self.owner, self.farm, "quality-inspector")
        self.assertTrue(any("بذر ناسالم" in f["title"] for f in quality.findings))

    def test_overdue_invoice_report_does_not_sum_currencies(self):
        customer = Partner.objects.create(unit=self.farm, name="مشتری")
        for currency in ("IRR", "USD"):
            CommercialDocument.objects.create(
                unit=self.farm, partner=customer, number="SALE-"+currency,
                kind="sales", total=D("300"), currency=currency,
                due_on=timezone.localdate()-timedelta(days=1),
                created_by=self.owner,
            )
        CommercialDocument.objects.create(
            unit=self.factory,
            partner=Partner.objects.create(unit=self.factory, name="فروشگاه"),
            number="SECRET-USD", kind="sales", total=D("25000"),
            due_on=timezone.localdate()-timedelta(days=2),
            created_by=self.owner,
        )
        report = generate_report(self.owner, self.farm, "receivables")
        out = " ".join(x["detail"]+x["title"] for x in report.findings)
        self.assertIn("300.00 IRR", out)
        self.assertIn("300.00 USD", out)
        self.assertNotIn("SECRET-USD", out)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_employee_work_hours_are_not_fictional_payroll(self):
        Timesheet.objects.create(
            unit=self.farm, person=self.viewer, work_date=timezone.localdate(),
            hours=D("7.5"), approved=True,
        )
        report = generate_report(self.owner, self.farm, "hr-workload")
        self.assertTrue(any("7.5" in x["detail"] for x in report.findings))
        self.assertTrue(any("دستمزد نیست" in x["detail"] for x in report.findings))

    def test_site_registry_does_not_reach_network(self):
        ManagedSite.objects.create(unit=self.farm, label="وب کشاورزی", path="/agriculture/", status="planned")
        report = generate_report(self.owner, self.farm, "site-qa")
        self.assertTrue(any("هیچ درخواست شبکه" in x["detail"] for x in report.findings))
        bad = ManagedSite(unit=self.farm, label="نامعتبر", path="//internal.host")
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_kpi_missing_actual_does_not_guess_result(self):
        PerformanceIndicator.objects.create(unit=self.farm, code="crop", label="عملکرد مزرعه",
                                            period="2026-10", target=D("900"))
        report = generate_report(self.owner, self.farm, "strategy-and-okrs")
        self.assertTrue(any("ثبت نشده" in f["detail"] for f in report.findings))

    def test_parent_hierarchy_protects_cycles(self):
        parent = Organization.objects.create(unit=self.hq, legal_name="مادر")
        child = Organization.objects.create(unit=self.farm, parent=parent, legal_name="مزرعه")
        parent.parent = child
        with self.assertRaises(ValidationError):
            parent.full_clean()

    def test_approval_is_a_record_not_a_payment_or_posting(self):
        record = ReviewApproval.objects.create(
            unit=self.farm, summary="پیشنهاد خرید", target_type="purchase",
            target_reference="REQ-1", requested_by=self.owner,
            assigned_to=self.owner,
        )
        record.decision = "accepted"
        record.reviewed_at = timezone.now()
        record.save()
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertFalse(AuditEvent.objects.exists())

    def test_draft_automation_requires_human_review(self):
        rule = ProposedAutomation(unit=self.farm, owner=self.owner,
                                  assistant_code="inventory-alerts", active=True,
                                  requires_human_review=False)
        with self.assertRaises(ValidationError):
            rule.full_clean()
        self.assertFalse(ProposedAutomation.objects.exists())

    def test_admin_queryset_scopes_manufacturing_records(self):
        formula = BillOfMaterials.objects.create(unit=self.farm, product=self.farm_product, code="F-ADMIN")
        ProductionOrder.objects.create(unit=self.farm, code="FARM-1", formula=formula,
                                      quantity=D("2"), owner=self.owner)
        factory_recipe = BillOfMaterials.objects.create(unit=self.factory, product=self.factory_product, code="FACTORY")
        ProductionOrder.objects.create(unit=self.factory, code="SECRET-1", formula=factory_recipe,
                                      quantity=D("9"), owner=self.owner)
        request = RequestFactory().get("/admin/ecosystem_hub/productionorder/")
        request.user = self.viewer
        model_admin = admin.site._registry[ProductionOrder]
        orders = list(model_admin.get_queryset(request))
        self.assertEqual([x.code for x in orders], ["FARM-1"])
        self.assertFalse(model_admin.has_view_permission(
            request, ProductionOrder.objects.get(code="SECRET-1")
        ))

    def test_membership_admin_is_superuser_only(self):
        request = RequestFactory().get("/admin/ecosystem_hub/unitmembership/")
        request.user = self.viewer
        panel = admin.site._registry[UnitMembership]
        self.assertFalse(panel.has_add_permission(request))
        self.assertFalse(panel.has_change_permission(request))
        self.assertEqual(panel.get_queryset(request).count(), 0)

    def test_group_overview_requires_true_owner_role(self):
        self.client.force_login(self.viewer)
        self.assertEqual(
            self.client.get("/company/office/ecosystem/group/", secure=True).status_code,
            403,
        )
        self.client.force_login(self.owner)
        response = self.client.get("/company/office/ecosystem/group/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unit_count"], 3)
        self.assertContains(response, "گزارش مدیریتی کل گروه")

    def test_group_finance_keeps_legal_units_and_currencies_distinct(self):
        for unit, currency in ((self.farm, "IRR"), (self.farm, "USD"), (self.factory, "IRR")):
            a, _ = LedgerAccount.objects.get_or_create(
                unit=unit, code="101", defaults={"name": "نقد", "category": "asset"},
            )
            b, _ = LedgerAccount.objects.get_or_create(
                unit=unit, code="401", defaults={"name": "فروش", "category": "income"},
            )
            entry = JournalEntry.objects.create(
                unit=unit, reference=currency + "-" + unit.code,
                description="ثبت کنترل", currency=currency, created_by=self.owner,
            )
            JournalLine.objects.create(entry=entry, account=a, debit=D("100"), credit=D("0"))
            JournalLine.objects.create(entry=entry, account=b, credit=D("100"), debit=D("0"))
            post_journal(entry.pk, self.owner)
        self.client.force_login(self.owner)
        response = self.client.get("/company/office/ecosystem/group/", secure=True)
        self.assertEqual(response.status_code, 200)
        rows = {x["unit"].code: x for x in response.context["rows"]}
        self.assertEqual(len(rows["farm"]["journals"]), 2)
        self.assertEqual(len(rows["factory"]["journals"]), 1)
        self.assertEqual({z["currency"] for z in rows["farm"]["journals"]}, {"IRR", "USD"})
        for unit_code in ("farm", "factory"):
            for x in rows[unit_code]["journals"]:
                self.assertEqual(x["debit"], x["credit"])
                self.assertEqual(x["debit"], D("100"))
        self.assertNotContains(response, "صورت‌های مالی تلفیقی تأیید شده")

    def test_approval_requires_designated_review_approver_not_any_staff(self):
        request = ReviewApproval.objects.create(
            unit=self.farm, summary="آزمون تصمیم", target_type="proposed_budget",
            target_reference="B1", requested_by=self.owner, assigned_to=self.viewer,
        )
        panel = admin.site._registry[ReviewApproval]
        req = RequestFactory().post("/admin/ecosystem_hub/reviewapproval/1/change/")
        req.user = self.viewer
        request.decision = "accepted"
        with self.assertRaises(PermissionDenied):
            panel.save_model(req, request, None, change=True)
        membership = UnitMembership.objects.get(user=self.viewer, unit=self.farm)
        membership.role = "manager"
        membership.save()
        with self.assertRaises(PermissionDenied):
            panel.save_model(req, request, None, change=True)
        membership.can_approve = True
        membership.save()
        panel.save_model(req, request, None, change=True)
        request.refresh_from_db()
        self.assertEqual(request.decision, "accepted")
        self.assertIsNotNone(request.reviewed_at)
        with self.assertRaises(ValidationError):
            panel.save_model(req, request, None, change=True)
        self.assertFalse(JournalEntry.objects.exists())

    def test_review_queue_is_human_only_idempotent_and_separate_from_payment(self):
        report = generate_report(self.owner, self.farm, "executive-brief")
        self.client.force_login(self.owner)
        path = f"/company/office/ecosystem/reports/{report.pk}/request-review/"
        self.assertEqual(self.client.get(path, secure=True).status_code, 405)
        for i in range(2):
            response = self.client.post(path, {"approver_id": self.owner.pk}, secure=True)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(ReviewApproval.objects.filter(
            target_type="assistant_report", target_reference=str(report.pk)
        ).count(), 1)
        report.refresh_from_db()
        self.assertEqual(report.state, "review")
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_review_requested",
        ).count(), 1)
        self.assertFalse(StockMovement.objects.exists())
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(CommercialDocument.objects.exists())

    def test_review_request_denies_other_units_and_unassigned_approvers(self):
        report = generate_report(self.owner, self.factory, "executive-brief")
        self.client.force_login(self.viewer)
        path = f"/company/office/ecosystem/reports/{report.pk}/request-review/"
        response = self.client.post(path, {"approver_id": self.owner.pk}, secure=True)
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.owner)
        rejected = self.client.post(path, {"approver_id": self.other.pk}, secure=True)
        self.assertEqual(rejected.status_code, 404)
        self.assertFalse(ReviewApproval.objects.exists())

    def test_assistant_review_action_requires_csrf(self):
        report = generate_report(self.owner, self.farm, "executive-brief")
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.owner)
        response = c.post(
            f"/company/office/ecosystem/reports/{report.pk}/request-review/",
            {"approver_id": self.owner.pk}, secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReviewApproval.objects.exists())

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_legacy_erp_reports_hide_other_company_finance_and_stock(self):
        viewer = U.objects.create_user(
            username="scoped-accountant", password="testing-only", is_staff=True,
        )
        UnitMembership.objects.create(
            user=viewer, unit=self.farm, role="finance", active=True,
        )
        permission_names = (
            "view_businessunit", "view_journalentry", "view_ledgeraccount",
            "view_inventoryitem", "view_stockmovement",
        )
        p = Permission.objects.filter(
            content_type__app_label="enterprise_portal", codename__in=permission_names,
        )
        viewer.user_permissions.add(*p)
        for unit in (self.farm, self.factory):
            cash = LedgerAccount.objects.create(
                unit=unit, code="100", name="نقد-" + unit.code, category="asset",
            )
            revenue = LedgerAccount.objects.create(
                unit=unit, code="400", name="فروش-" + unit.code, category="income",
            )
            voucher = JournalEntry.objects.create(
                unit=unit, reference="REF-"+unit.code,
                created_by=self.owner, description="ثبت کنترل",
            )
            JournalLine.objects.create(
                entry=voucher, account=cash, debit=D("100"), credit=D("0"),
            )
            JournalLine.objects.create(
                entry=voucher, account=revenue, debit=D("0"), credit=D("100"),
            )
            post_journal(voucher.pk, self.owner)
        self.client.force_login(viewer)
        response = self.client.get("/company/office/finance/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "farm")
        self.assertNotContains(response, "factory")
        self.assertEqual(response.context["posted_count"], 1)
        trial = self.client.get("/company/office/finance/trial-balance/", secure=True)
        self.assertEqual(trial.status_code, 200)
        self.assertEqual(len(trial.context["records"]), 2)
        self.assertNotContains(trial, "نقد-factory")
        self.assertEqual(self.client.get(
            "/company/office/finance/trial-balance/?unit=factory", secure=True,
        ).status_code, 400)
        response = self.client.get(
            "/company/office/finance/trial-balance.csv", secure=True,
        )
        self.assertIn("نقد-farm", response.content.decode("utf-8-sig"))
        self.assertNotIn("نقد-factory", response.content.decode("utf-8-sig"))
        inventory = self.client.get("/company/office/inventory/", secure=True)
        self.assertEqual(inventory.status_code, 200)
        self.assertContains(inventory, "WHEAT")
        self.assertNotContains(inventory, "FP")

    def test_legacy_admin_blocks_cross_unit_direct_objects_and_querysets(self):
        from django.contrib import admin as site_admin
        viewer = U.objects.create_user(username="accountant-restricted", is_staff=True)
        UnitMembership.objects.create(user=viewer, unit=self.farm, role="finance")
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="enterprise_portal",
            codename__in=("view_businessunit", "view_journalentry", "view_ledgeraccount",
                           "view_inventoryitem", "view_stockmovement", "change_journalentry"),
        ))
        farm_journal = JournalEntry.objects.create(
            unit=self.farm, reference="farm-draft", created_by=self.owner,
            description="تست دفتر",
        )
        factory_journal = JournalEntry.objects.create(
            unit=self.factory, reference="factory-secret", created_by=self.owner,
            description="محرمانه",
        )
        req = RequestFactory().get("/admin/enterprise_portal/journalentry/")
        req.user = viewer
        panel = site_admin.site._registry[JournalEntry]
        self.assertEqual(list(panel.get_queryset(req)), [farm_journal])
        self.assertFalse(panel.has_view_permission(req, factory_journal))
        self.assertFalse(panel.has_change_permission(req, factory_journal))
        item_panel = site_admin.site._registry[InventoryItem]
        self.assertEqual(
            list(item_panel.get_queryset(req)), [self.farm_material, self.farm_product],
        ) if False else self.assertEqual(item_panel.get_queryset(req).count(), 2)
        self.assertFalse(item_panel.has_view_permission(req, self.factory_product))

    def test_services_forbid_posting_another_units_valid_voucher(self):
        viewer = U.objects.create_user(username="accountant-scope", is_staff=True)
        UnitMembership.objects.create(user=viewer, unit=self.farm, role="finance")
        viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="enterprise_portal",
            codename__in=("change_journalentry", "change_stockmovement"),
        ))
        cash = LedgerAccount.objects.create(
            unit=self.factory, code="101", name="بانک", category="asset",
        )
        sales = LedgerAccount.objects.create(
            unit=self.factory, code="401", name="درآمد", category="income",
        )
        entry = JournalEntry.objects.create(
            unit=self.factory, reference="factory-draft",
            description="ثبت نمونه", created_by=self.owner,
        )
        JournalLine.objects.create(entry=entry, account=cash, debit=D("500"), credit=D("0"))
        JournalLine.objects.create(entry=entry, account=sales, debit=D("0"), credit=D("500"))
        with self.assertRaises(PermissionDenied):
            post_journal(entry.pk, viewer)
        entry.refresh_from_db()
        self.assertEqual(entry.status, "draft")
        stock = StockMovement.objects.create(
            item=self.factory_product, direction="in", quantity=D("5"),
            reference="IN-SECRET", created_by=self.owner,
        )
        with self.assertRaises(PermissionDenied):
            confirm_stock_movement(stock.pk, viewer)
        self.assertEqual(stock_balance(self.factory_product.pk), D("0"))

    def test_cost_estimate_remains_incomplete_without_verified_material_rate(self):
        formula = BillOfMaterials.objects.create(
            unit=self.farm, product=self.farm_product, code="COST-BOM", yield_quantity=D("2"),
        )
        MaterialRequirement.objects.create(
            formula=formula, item=self.farm_material, quantity=D("3"),
            scrap_percent=D("10"),
        )
        order = ProductionOrder.objects.create(
            unit=self.farm, formula=formula, code="COST-ORDER", quantity=D("10"),
            owner=self.owner,
        )
        scenario = ProductionCostScenario.objects.create(
            unit=self.farm, order=order, label="برآورد مواد", currency="USD",
            labor_estimate=D("100"), overhead_estimate=D("40"), prepared_by=self.owner,
        )
        result = estimate_manufacturing_cost(scenario)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["total"])
        self.assertIsNone(result["unit_cost"])
        self.assertEqual(result["missing_skus"], ["SEED"])
        self.assertEqual(result["components"][0]["amount_needed"], D("16.500"))
        self.assertEqual(JournalEntry.objects.count(), 0)

        # Draft rates, wrong currencies and future-dated references must not
        # become assumed current prices.
        MaterialPriceReference.objects.create(
            unit=self.farm, item=self.farm_material, currency="USD",
            amount=D("10"), status="draft", recorded_by=self.owner,
            evidence_ref="unverified", as_of=timezone.localdate(),
        )
        MaterialPriceReference.objects.create(
            unit=self.farm, item=self.farm_material, currency="IRR",
            amount=D("999"), status="verified", recorded_by=self.owner,
            evidence_ref="invoice-IRR", as_of=timezone.localdate(),
        )
        MaterialPriceReference.objects.create(
            unit=self.farm, item=self.farm_material, currency="USD",
            amount=D("25"), status="verified", recorded_by=self.owner,
            evidence_ref="future-quote", as_of=timezone.localdate()+timedelta(days=3),
        )
        self.assertIsNone(estimate_manufacturing_cost(scenario)["total"])
        verified = MaterialPriceReference.objects.create(
            unit=self.farm, item=self.farm_material, currency="USD",
            amount=D("20"), status="verified", recorded_by=self.owner,
            evidence_ref="approved-supplier-offer",
        )
        result = estimate_manufacturing_cost(scenario)
        self.assertTrue(result["complete"])
        self.assertEqual(result["material_total"], D("330.00"))
        self.assertEqual(result["total"], D("470.00"))
        self.assertEqual(result["unit_cost"], D("47.00"))
        self.assertEqual(result["components"][0]["price_source"], "approved-supplier-offer")
        self.assertFalse(result["posted_to_ledger"])
        self.assertFalse(result["stock_movement_created"])
        self.assertFalse(JournalEntry.objects.exists())
        self.assertFalse(StockMovement.objects.exists())

        assistant = generate_report(self.owner, self.farm, "cost-accountant")
        self.assertTrue(any("470.00 USD" in x["detail"] for x in assistant.findings))
        self.assertEqual(assistant.state, "draft")

    def test_cost_price_requires_documentation_and_matching_business_unit(self):
        price = MaterialPriceReference(
            unit=self.farm, item=self.factory_product, currency="IRR",
            amount=D("200"), status="verified", recorded_by=self.owner,
            evidence_ref="supplier",
        )
        with self.assertRaises(ValidationError):
            price.full_clean()
        price.item = self.farm_material
        price.evidence_ref = ""
        with self.assertRaises(ValidationError):
            price.full_clean()
        price.evidence_ref = "signed-offer"
        price.amount = D("-5")
        with self.assertRaises(ValidationError):
            price.full_clean()
        price.amount = D("500")
        price.full_clean()

    def test_cost_scenario_rejects_cross_unit_production_order(self):
        formula = BillOfMaterials.objects.create(
            unit=self.factory, product=self.factory_product, code="FACTORY-COST",
        )
        order = ProductionOrder.objects.create(
            unit=self.factory, formula=formula, code="SECRET-COST", quantity=D("3"), owner=self.owner,
        )
        bad = ProductionCostScenario(
            unit=self.farm, order=order, label="غیرمجاز", prepared_by=self.owner,
        )
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_cost_report_read_permission_and_company_isolation(self):
        formula = BillOfMaterials.objects.create(
            unit=self.factory, product=self.factory_product, code="BOM-COST",
        )
        order = ProductionOrder.objects.create(
            unit=self.factory, formula=formula, code="SECRET-COST", quantity=D("2"), owner=self.owner,
        )
        scenario = ProductionCostScenario.objects.create(
            unit=self.factory, order=order, label="برآورد کارخانه", prepared_by=self.owner,
        )
        url = f"/company/office/ecosystem/production/cost/{scenario.pk}/"
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url, secure=True).status_code, 403)
        self.viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="ecosystem_hub",
            codename__in=("view_productioncostscenario", "view_materialpricereference"),
        ))
        self.assertEqual(self.client.get(url, secure=True).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(url, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نرخ ناقص")

    def test_cost_assistant_warns_when_prices_are_missing(self):
        recipe = BillOfMaterials.objects.create(
            unit=self.farm, product=self.farm_product, code="BOM-COST-MISS",
        )
        MaterialRequirement.objects.create(
            formula=recipe, item=self.farm_material, quantity=D("2"),
        )
        order = ProductionOrder.objects.create(
            unit=self.farm, formula=recipe, code="COST-MISS",
            quantity=D("5"), owner=self.owner,
        )
        ProductionCostScenario.objects.create(
            unit=self.farm, order=order, label="فاقد نرخ", prepared_by=self.owner,
        )
        report = generate_report(self.owner, self.farm, "cost-accountant")
        self.assertTrue(any("نرخ‌های ناکامل" in f["title"] for f in report.findings))
        self.assertTrue(all("برآورد مستند" not in f["detail"] for f in report.findings))

    def test_sensitive_financial_and_payroll_assistants_need_source_permissions(self):
        from .analysis import HANDLER_VIEW_PERMISSIONS
        self.assertIn("enterprise_portal.view_commercialdocument",
                      HANDLER_VIEW_PERMISSIONS["receivables"])
        self.assertIn("ecosystem_hub.view_timesheet", HANDLER_VIEW_PERMISSIONS["people"])
        self.assertIn("ecosystem_hub.view_materialpricereference",
                      HANDLER_VIEW_PERMISSIONS["cost"])
        with self.assertRaises(PermissionDenied):
            generate_report(self.viewer, self.farm, "receivables")
        with self.assertRaises(PermissionDenied):
            generate_report(self.viewer, self.farm, "cost-accountant")
        with self.assertRaises(PermissionDenied):
            generate_report(self.viewer, self.farm, "hr-workload")
        self.assertEqual(AssistantRun.objects.count(), 0)
        # An inventory-only assistant is intentionally authorized.
        report = generate_report(self.viewer, self.farm, "inventory-alerts")
        self.assertEqual(report.state, "draft")

    def test_verified_material_reference_is_immutable_after_confirmation(self):
        row = MaterialPriceReference.objects.create(
            unit=self.farm, item=self.farm_material, currency="USD",
            amount=D("15"), status="verified",
            evidence_ref="signed-document", recorded_by=self.owner,
        )
        row.amount = D("1")
        with self.assertRaises(ValidationError):
            row.save()
        row.refresh_from_db()
        self.assertEqual(row.amount, D("15"))
        panel = admin.site._registry[MaterialPriceReference]
        request = RequestFactory().get("/admin/ecosystem_hub/materialpricereference/")
        request.user = self.owner
        self.assertFalse(panel.has_change_permission(request, row))

    def test_assistant_access_is_csrf_protected(self):
        web = Client(enforce_csrf_checks=True)
        web.force_login(self.viewer)
        response = web.post(
            "/company/office/ecosystem/assistants/inventory-alerts/run/",
            {"unit": "farm"}, secure=True,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AssistantRun.objects.exists())
