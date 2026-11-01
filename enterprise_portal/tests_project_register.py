"""Regression tests for the read-only, scoped project register."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ecosystem_hub.models import UnitMembership
from .models import AuditEvent, BudgetPlan, BusinessUnit, ManagementProject


@override_settings(
    DEBUG=False, ALLOWED_HOSTS=["testserver"],
    COMPANY_OFFICE_REQUIRE_MFA=False,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class ProjectRegisterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.viewer = User.objects.create_user(username="project-viewer", is_staff=True)
        self.other = User.objects.create_user(username="project-other", is_staff=True)
        self.farm = BusinessUnit.objects.create(code="farm", name="Farm")
        self.factory = BusinessUnit.objects.create(code="factory", name="Factory")
        UnitMembership.objects.create(user=self.viewer, unit=self.farm, role="analyst")
        UnitMembership.objects.create(user=self.other, unit=self.factory, role="analyst")
        view_business = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_businessunit")
        view_project = Permission.objects.get(
            content_type__app_label="enterprise_portal", codename="view_managementproject")
        self.viewer.user_permissions.add(view_business, view_project)
        self.other.user_permissions.add(view_business)
        self.visible = ManagementProject.objects.create(
            unit=self.farm, code="P-001", title="Farm project",
            objective="Verified project objective", owner=self.viewer, status="idea",
        )
        self.hidden = ManagementProject.objects.create(
            unit=self.factory, code="P-999", title="Secret factory project",
            objective="Not authorized", owner=self.other, status="active",
        )
        for title, amount, currency, status in [
            ("IRR approved", "150", "IRR", "approved"),
            ("USD approved", "25", "USD", "approved"),
            ("IRR draft", "500", "IRR", "draft"),
        ]:
            BudgetPlan.objects.create(
                unit=self.farm, project=self.visible, title=title, fiscal_year=1405,
                amount=Decimal(amount), currency=currency, status=status,
            )

    def test_anonymous_redirects_and_plain_http_is_rejected(self):
        url = reverse("enterprise_portal:project_register")
        self.assertEqual(self.client.get(url, secure=True).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_project_permission_is_required_even_with_unit_membership(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(
            reverse("enterprise_portal:project_register"), secure=True
        ).status_code, 403)

    def test_list_is_scoped_and_budget_currencies_not_aggregated(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("enterprise_portal:project_register"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Farm project")
        self.assertNotContains(response, "Secret factory project")
        self.assertContains(response, "150 IRR")
        self.assertContains(response, "25 USD")
        self.assertNotContains(response, "500 IRR")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("noindex", response["X-Robots-Tag"])

    def test_detail_is_unit_scoped_and_does_not_fabricate_profit(self):
        self.client.force_login(self.viewer)
        path = reverse("enterprise_portal:project_detail", args=[self.visible.pk])
        response = self.client.get(path, secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verified project objective")
        self.assertContains(response, "IRR draft")
        self.assertContains(response, "NPV")
        self.assertContains(response, "IRR")
        hidden_path = reverse("enterprise_portal:project_detail", args=[self.hidden.pk])
        self.assertEqual(self.client.get(hidden_path, secure=True).status_code, 404)

    def test_dashboard_links_to_real_register_without_writes(self):
        self.client.force_login(self.viewer)
        before = (ManagementProject.objects.count(), BudgetPlan.objects.count(),
                  AuditEvent.objects.count())
        response = self.client.get(reverse("enterprise_portal:dashboard"), secure=True)
        self.assertContains(response, reverse("enterprise_portal:project_register"))
        self.client.get(reverse("enterprise_portal:project_register"), secure=True)
        self.assertEqual(before, (ManagementProject.objects.count(),
                                  BudgetPlan.objects.count(), AuditEvent.objects.count()))

    def test_new_project_requires_write_role_and_is_audited_idea_only(self):
        add_perm = Permission.objects.get(
            content_type__app_label="enterprise_portal",
            codename="add_managementproject",
        )
        self.viewer.user_permissions.add(add_perm)
        self.client.force_login(self.viewer)
        url = reverse("enterprise_portal:new_project")
        payload = {
            "unit": self.farm.pk, "code": "P-002",
            "title": "New project", "objective": "Feasibility first",
        }
        # A read-only unit analyst cannot create or approve.
        self.assertEqual(self.client.post(url, payload, secure=True).status_code, 403)
        self.assertFalse(ManagementProject.objects.filter(code="P-002").exists())
        UnitMembership.objects.filter(user=self.viewer, unit=self.farm).update(role="manager")
        # Cross-unit IDs are not accepted even for an authorized manager.
        self.assertEqual(self.client.post(
            url, {**payload, "unit": self.factory.pk}, secure=True
        ).status_code, 200)
        self.assertFalse(ManagementProject.objects.filter(code="P-002").exists())
        response = self.client.post(url, payload, secure=True)
        self.assertEqual(response.status_code, 302)
        project = ManagementProject.objects.get(code="P-002")
        self.assertEqual(project.status, "idea")
        self.assertEqual(project.owner, self.viewer)
        self.assertEqual(project.unit, self.farm)
        self.assertEqual(BudgetPlan.objects.filter(project=project).count(), 0)
        self.assertTrue(AuditEvent.objects.filter(
            action="office_project_created", target=f"ManagementProject:{project.pk}"
        ).exists())

    def test_post_cannot_mutate_project_register(self):
        self.client.force_login(self.viewer)
        url = reverse("enterprise_portal:project_register")
        self.assertEqual(self.client.post(url, {"status": "approved"}, secure=True).status_code, 405)
        self.visible.refresh_from_db()
        self.assertEqual(self.visible.status, "idea")
