"""CRM privacy and unit partition regression for Zomorod executive office."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ecosystem_hub.models import UnitMembership
from enterprise_portal.models import BusinessUnit
from company_messaging.models import Contact
from .models import Lead


@override_settings(DEBUG=True, COMPANY_OFFICE_REQUIRE_MFA=False)
class PrivateCRMTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            username="crm_staff", password="OnlyTest!12345", is_staff=True,
        )
        allowed = Permission.objects.filter(
            content_type__app_label__in=("enterprise_portal", "company_marketing"),
            codename__in=("view_businessunit", "view_lead"),
        )
        self.staff.user_permissions.add(*allowed)
        self.unit = BusinessUnit.objects.create(code="zm-crm-owner", name="مالک سرنخ")
        self.unrelated = BusinessUnit.objects.create(code="zm-crm-hidden", name="واحد دیگر")
        UnitMembership.objects.create(user=self.staff, unit=self.unit, role="manager")
        contact = Contact.objects.create(unit=self.unit, name="مشتری محرمانه الف")
        hidden = Contact.objects.create(unit=self.unrelated, name="مشتری محرمانه ب")
        Lead.objects.create(
            unit=self.unit, contact=contact, owner=self.staff, source="web",
            stage="won", estimated_value_irr=2000000, verified_sale_irr=1500000,
            sale_evidence_reference="internal-evidence-20261101",
        )
        Lead.objects.create(
            unit=self.unrelated, contact=hidden, owner=self.staff,
            source="hidden-office", stage="new",
        )
        self.client.force_login(self.staff)

    def test_crm_does_not_disclose_outside_unit_or_contact_without_permission(self):
        response = self.client.get(reverse("company_marketing:crm"), secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مالک سرنخ")
        self.assertContains(response, "مخاطب محرمانه")
        self.assertNotContains(response, "مشتری محرمانه الف")
        self.assertNotContains(response, "مشتری محرمانه ب")
        self.assertNotContains(response, "hidden-office")
        self.assertContains(response, "1500000")
        self.assertIn("no-store", response["Cache-Control"])

    def test_bad_stage_is_rejected(self):
        response = self.client.get(reverse("company_marketing:crm"), {"stage": "unknown"}, secure=True)
        self.assertEqual(response.status_code, 400)

    def test_no_crm_permission_returns_403(self):
        self.staff.user_permissions.clear()
        self.assertEqual(self.client.get(reverse("company_marketing:crm"), secure=True).status_code, 403)

    def test_anonymous_crm_redirects_to_secure_office_login(self):
        self.client.logout()
        response = self.client.get(reverse("company_marketing:crm"), secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertIn("secure-login", response["Location"])
