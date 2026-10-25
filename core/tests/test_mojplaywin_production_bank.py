"""Test isolated manufacturing proposal registry and superuser-only admin."""
from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings

from core.models import AgentTask, Order, Product
from core.mojplaywin_production_admin import (
    MojPlayWinManufacturingOrderAdmin,
    MojPlayWinOpportunitySignalAdmin,
)
from core.mojplaywin_production_bank import prepare_main_site_cards
from core.mojplaywin_production_models import (
    MojPlayWinManufacturingOrder,
    MojPlayWinOpportunitySignal,
)


@override_settings(ALLOWED_HOSTS=["mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "testserver"])
class MojPlayWinProductionBankTests(TestCase):
    def test_site_card_inventory(self):
        intake, signals = prepare_main_site_cards()
        self.assertEqual(len(intake["production_proposals"]), 24)
        self.assertEqual(len(signals), 24 + intake["other_signals_total"])
        self.assertEqual(len({row["source_key"] for row in signals}), len(signals))
        self.assertTrue(all(row["source_key"].split(":")[0] in ("venture", "section", "feature") for row in signals))

    def test_dry_run_is_non_persistent(self):
        out = StringIO()
        call_command("mojplaywin_sync_production_bank", stdout=out)
        self.assertIn('"mode": "dry_run_no_database_access"', out.getvalue())
        self.assertEqual(MojPlayWinOpportunitySignal.objects.count(), 0)
        self.assertEqual(MojPlayWinManufacturingOrder.objects.count(), 0)

    def test_requires_explicit_main_site_for_any_persistence(self):
        with self.assertRaises(CommandError):
            call_command("mojplaywin_sync_production_bank", apply=True, site="zomorodmelal.ir")
        with self.assertRaises(CommandError):
            call_command("mojplaywin_sync_production_bank", apply=True)
        self.assertFalse(MojPlayWinOpportunitySignal.objects.exists())

    def test_24_briefs_from_cards_and_no_commerce_side_effects(self):
        out = StringIO()
        call_command("mojplaywin_sync_production_bank", apply=True, site="mojplaywin.com", stdout=out)
        _, rows = prepare_main_site_cards()
        self.assertEqual(MojPlayWinOpportunitySignal.objects.count(), len(rows))
        self.assertEqual(MojPlayWinManufacturingOrder.objects.count(), 24)
        self.assertTrue(all(s.source_site == "mojplaywin.com" for s in MojPlayWinOpportunitySignal.objects.all()))
        self.assertTrue(all(o.status == "proposed_for_review" for o in MojPlayWinManufacturingOrder.objects.all()))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(AgentTask.objects.count(), 0)
        self.assertIn('"customer_orders_created": 0', out.getvalue())
        self.assertIn('"public_products_created": 0', out.getvalue())
        self.assertIn('"factory_tasks_created": 0', out.getvalue())

    def test_rerun_does_not_repeat_or_override_manual_review(self):
        call_command("mojplaywin_sync_production_bank", apply=True, site="mojplaywin.com", stdout=StringIO())
        obj = MojPlayWinManufacturingOrder.objects.first()
        User = get_user_model()
        owner = User.objects.create_superuser(username="mpw_bank_owner", email="owner@example.test", password="testing-only-password")
        obj.proposed_owner = owner
        obj.status = "scoped"
        obj.review_note = "Only a scoped draft; original rights and market demand still pending."
        obj.full_clean()
        obj.save()
        signal = obj.signal
        signal.review_note = "Reviewed existing card without changing its content"
        signal.save()
        call_command("mojplaywin_sync_production_bank", apply=True, site="mojplaywin.com", stdout=StringIO())
        obj.refresh_from_db()
        signal.refresh_from_db()
        self.assertEqual(MojPlayWinManufacturingOrder.objects.count(), 24)
        self.assertEqual(obj.status, "scoped")
        self.assertEqual(obj.proposed_owner, owner)
        self.assertIn("still pending", obj.review_note)
        self.assertIn("Reviewed", signal.review_note)

    def test_scoped_brief_needs_owner_and_review_note(self):
        call_command("mojplaywin_sync_production_bank", apply=True, site="mojplaywin.com", stdout=StringIO())
        obj = MojPlayWinManufacturingOrder.objects.first()
        obj.status = "scoped"
        with self.assertRaises(ValidationError):
            obj.full_clean()
        obj.review_note = "Purpose defined"
        with self.assertRaises(ValidationError):
            obj.full_clean()

    def test_admin_does_not_show_on_other_domains(self):
        User = get_user_model()
        user = User.objects.create_superuser(username="admin_bank_test", email="admin@example.test", password="test-password")
        admin_site = AdminSite()
        request_factory = RequestFactory()
        for klass, model in (
            (MojPlayWinManufacturingOrderAdmin, MojPlayWinManufacturingOrder),
            (MojPlayWinOpportunitySignalAdmin, MojPlayWinOpportunitySignal),
        ):
            admin_view = klass(model, admin_site)
            request = request_factory.get("/admin/", HTTP_HOST="zomorodmelal.ir")
            request.user = user
            self.assertFalse(admin_view.has_module_permission(request))
            self.assertFalse(admin_view.has_view_permission(request))
            self.assertFalse(admin_view.has_change_permission(request))
            request = request_factory.get("/admin/", HTTP_HOST="mojplaywin.com")
            request.user = user
            self.assertTrue(admin_view.has_module_permission(request))
            self.assertTrue(admin_view.has_view_permission(request))
            self.assertFalse(admin_view.has_add_permission(request))
            self.assertFalse(admin_view.has_delete_permission(request))

    def test_admin_never_allows_direct_quality_approval(self):
        admin_view = MojPlayWinManufacturingOrderAdmin(MojPlayWinManufacturingOrder, AdminSite())
        self.assertIn("rights_verified", admin_view.readonly_fields)
        self.assertIn("demand_verified", admin_view.readonly_fields)
        self.assertNotIn("approved", dict(MojPlayWinManufacturingOrder.STATUSES))
        self.assertNotIn("listed", dict(MojPlayWinManufacturingOrder.STATUSES))
