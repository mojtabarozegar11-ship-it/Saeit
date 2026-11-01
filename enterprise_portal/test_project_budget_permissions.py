"""C-01 regression: project visibility must not imply financial disclosure.

Uses only Django's disposable test database. No external service or payment.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ecosystem_hub.models import UnitMembership
from enterprise_portal.models import BudgetPlan, BusinessUnit, ManagementProject

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(
    DEBUG=False,
    ALLOWED_HOSTS=["testserver"],
    COMPANY_OFFICE_REQUIRE_MFA=False,
    STORAGES=TEST_STORAGES,
)
class ProjectBudgetDisclosureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="project-budget-owner", email="owner@example.test",
            password="test-only-password",
        )
        self.viewer = User.objects.create_user(
            username="project-only-reader", password="test-only-password",
            is_staff=True,
        )
        self.unit = BusinessUnit.objects.create(code="unit-a", name="Unit A")
        self.foreign_unit = BusinessUnit.objects.create(code="unit-b", name="Unit B")
        UnitMembership.objects.create(user=self.viewer, unit=self.unit, role="viewer")
        self.viewer.user_permissions.add(*list(Permission.objects.filter(
            content_type__app_label="enterprise_portal",
            codename__in=("view_businessunit", "view_managementproject"),
        )))
        self.project = ManagementProject.objects.create(
            unit=self.unit, code="A-1", title="Visible project",
            objective="Approved operational plan", owner=self.owner,
        )
        self.foreign_project = ManagementProject.objects.create(
            unit=self.foreign_unit, code="B-1", title="Foreign project",
            objective="Other unit", owner=self.owner,
        )
        self.budget = BudgetPlan.objects.create(
            unit=self.unit, project=self.project, fiscal_year=2026,
            title="PRIVATE_BUDGET_MARKER_9", currency="USD",
            amount=Decimal("9876543.21"), status="approved",
        )
        BudgetPlan.objects.create(
            unit=self.foreign_unit, project=self.foreign_project,
            fiscal_year=2026, title="FOREIGN_BUDGET_MARKER_8",
            currency="CAD", amount=Decimal("1234567.89"), status="approved",
        )
        self.list_url = reverse("enterprise_portal:project_register")
        self.detail_url = reverse("enterprise_portal:project_detail", args=[self.project.pk])
        self.foreign_url = reverse("enterprise_portal:project_detail", args=[self.foreign_project.pk])

    def test_project_only_reader_cannot_see_financial_amount_or_title(self):
        self.client.force_login(self.viewer)
        for url in (self.list_url, self.detail_url):
            with self.subTest(url=url):
                response = self.client.get(url, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Visible project")
                self.assertNotContains(response, "PRIVATE_BUDGET_MARKER_9")
                self.assertNotContains(response, "9876543")
                self.assertNotContains(response, "FOREIGN_BUDGET_MARKER_8")
                self.assertIn("no-store", response["Cache-Control"])
                self.assertFalse(response.context["can_view_budget"])
        self.assertEqual(self.client.get(self.foreign_url, secure=True).status_code, 404)

    def test_independent_budget_permission_restores_same_unit_financial_view(self):
        self.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_budgetplan",
        ))
        self.client.force_login(self.viewer)
        for url in (self.list_url, self.detail_url):
            with self.subTest(url=url):
                response = self.client.get(url, secure=True)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["can_view_budget"])
                self.assertContains(response, "9876543")
                self.assertNotContains(response, "FOREIGN_BUDGET_MARKER_8")
        detail = self.client.get(self.detail_url, secure=True)
        self.assertContains(detail, "PRIVATE_BUDGET_MARKER_9")
        self.assertEqual(self.client.get(self.foreign_url, secure=True).status_code, 404)

    def test_budget_permission_without_project_permission_does_not_grant_project_view(self):
        self.viewer.user_permissions.remove(Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_managementproject",
        ))
        self.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="view_budgetplan",
        ))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.list_url, secure=True).status_code, 403)
        self.assertEqual(self.client.get(self.detail_url, secure=True).status_code, 403)

    def test_anonymous_is_redirected_before_any_financial_query(self):
        response = self.client.get(self.detail_url, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/company/office/secure-login/", response["Location"])
