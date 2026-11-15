"""Real DB/admin permission contract for Moj Prop's buyer requests."""
from types import SimpleNamespace
from django.contrib.admin.sites import site
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, RequestFactory
from core.models import MojPropRequest


class MojPropCustomerWorkbenchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.model = MojPropRequest.objects.create(
            request_id="MOJPROP-ADMIN-001",
            name="Customer Name", email="customer@example.org",
            route="brief", horizon="month",
            notes="Please prepare an educational market research brief.",
            consent=True, source="moj-prop-public",
        )

    def setUp(self):
        self.admin = site._registry[MojPropRequest]
        self.request = RequestFactory().get("/admin/core/mojproprequest/")
        self.owner=SimpleNamespace(is_authenticated=True,is_superuser=True)
        self.staff=SimpleNamespace(is_authenticated=True,is_superuser=False)

    def test_anonymous_never_sees_customer_information(self):
        self.request.user=AnonymousUser()
        self.assertFalse(self.admin.has_module_permission(self.request))
        self.assertFalse(self.admin.has_view_permission(self.request))
        self.assertFalse(self.admin.has_change_permission(self.request))

    def test_regular_staff_never_sees_customer_email(self):
        self.request.user=self.staff
        self.assertFalse(self.admin.has_module_permission(self.request))
        self.assertFalse(self.admin.has_view_permission(self.request))
        self.assertFalse(self.admin.has_change_permission(self.request))

    def test_owner_may_read_and_review_existing_lead(self):
        self.request.user=self.owner
        self.assertTrue(self.admin.has_module_permission(self.request))
        self.assertTrue(self.admin.has_view_permission(self.request))
        self.assertTrue(self.admin.has_change_permission(self.request,self.model))

    def test_no_manual_lead_insertion_by_owner(self):
        self.request.user=self.owner
        self.assertFalse(self.admin.has_add_permission(self.request))

    def test_no_admin_deletion_of_consent_evidence(self):
        self.request.user=self.owner
        self.assertFalse(self.admin.has_delete_permission(self.request,self.model))

    def test_customer_facts_and_ip_digest_are_immutable_in_admin(self):
        ro=set(self.admin.readonly_fields)
        for name in ("name","email","request_id","notes","consent","route",
                     "horizon","ip_hash","created_at","updated_at","source"):
            self.assertIn(name,ro)
        self.assertNotIn("status",ro)
        self.assertNotIn("internal_note",ro)

    def test_first_manual_review_stamps_reviewed_at(self):
        self.request.user=self.owner
        self.assertIsNone(self.model.reviewed_at)
        self.model.status="reviewing"
        self.model.internal_note="Owner reviewed scope; no offer or payment yet."
        self.admin.save_model(self.request,self.model,None,True)
        self.model.refresh_from_db()
        self.assertIsNotNone(self.model.reviewed_at)
        self.assertEqual(self.model.status,"reviewing")
        self.assertIn("no offer",self.model.internal_note)

    def test_repeated_owner_review_keeps_first_review_timestamp(self):
        self.request.user=self.owner
        self.model.status="reviewing"
        self.admin.save_model(self.request,self.model,None,True)
        first=self.model.reviewed_at
        self.model.status="closed"
        self.admin.save_model(self.request,self.model,None,True)
        self.model.refresh_from_db()
        self.assertEqual(self.model.reviewed_at,first)

    def test_non_owner_cannot_save_even_if_called_outside_admin(self):
        self.request.user=self.staff
        self.model.status="approved"
        with self.assertRaises(PermissionError):
            self.admin.save_model(self.request,self.model,None,True)
        self.model.refresh_from_db()
        self.assertEqual(self.model.status,"new")

    def test_admin_cannot_create_fake_buyer_record_even_as_owner(self):
        self.request.user=self.owner
        with self.assertRaises(PermissionError):
            self.admin.save_model(self.request,self.model,None,False)

    def test_customer_email_not_exposed_in_list_display(self):
        self.assertNotIn("email",self.admin.list_display)
        self.assertNotIn("name",self.admin.list_display)

    def test_manual_review_does_not_mark_a_buyer_as_paid(self):
        self.request.user=self.owner
        self.model.status="reviewing"
        self.admin.save_model(self.request,self.model,None,True)
        self.model.refresh_from_db()
        self.assertNotEqual(self.model.status,"approved")
        self.assertNotEqual(self.model.status,"delivered")
