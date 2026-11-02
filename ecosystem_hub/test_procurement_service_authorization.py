"""Service-level procurement authorization: no unauthorized draft or audit writes."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from enterprise_portal.models import AuditEvent, BusinessUnit, InventoryItem
from .access import require_unit
from .models import (
    BillOfMaterials, MaterialRequirement, ProcurementNeed, ProductionOrder,
    UnitMembership,
)
from .procurement import prepare_purchase_drafts


class ProcurementServiceAuthorizationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_superuser(
            username="mrp-service-owner", password="ci-only-not-real",
        )
        self.unit = BusinessUnit.objects.create(code="mrp-auth-a", name="Unit A")
        self.other_unit = BusinessUnit.objects.create(code="mrp-auth-b", name="Unit B")
        product = InventoryItem.objects.create(
            unit=self.unit, sku="MRP-A-FINAL", title="Final",
        )
        material = InventoryItem.objects.create(
            unit=self.unit, sku="MRP-A-INPUT", title="Input",
        )
        recipe = BillOfMaterials.objects.create(
            unit=self.unit, product=product, code="MRP-A-BOM",
            yield_quantity=Decimal("1"),
        )
        MaterialRequirement.objects.create(
            formula=recipe, item=material,
            quantity=Decimal("2"), scrap_percent=Decimal("0"),
        )
        self.order = ProductionOrder.objects.create(
            unit=self.unit, formula=recipe, code="MRP-A-ORDER",
            quantity=Decimal("3"), owner=self.owner,
        )
        self.staff = user_model.objects.create_user(
            username="mrp-service-staff", password="ci-only-not-real",
            is_staff=True,
        )

    def grant_planning_permissions(self):
        codenames = (
            "add_procurementneed", "view_productionorder",
            "view_billofmaterials", "view_inventoryitem",
            "view_stockmovement",
        )
        permissions = Permission.objects.filter(codename__in=codenames)
        self.assertEqual(permissions.count(), len(codenames))
        self.staff.user_permissions.add(*permissions)

    def assert_no_draft_writes(self):
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())

    def test_staff_without_permission_cannot_call_service_directly(self):
        UnitMembership.objects.create(
            user=self.staff, unit=self.unit, role="manager",
        )
        with self.assertRaises(PermissionDenied):
            prepare_purchase_drafts(self.order.pk, self.staff)
        self.assert_no_draft_writes()

    def test_viewer_with_django_permissions_cannot_write_unit(self):
        self.grant_planning_permissions()
        UnitMembership.objects.create(
            user=self.staff, unit=self.unit, role="viewer",
        )
        with self.assertRaises(PermissionDenied):
            prepare_purchase_drafts(self.order.pk, self.staff)
        self.assert_no_draft_writes()

    def test_cross_unit_manager_cannot_create_drafts(self):
        self.grant_planning_permissions()
        UnitMembership.objects.create(
            user=self.staff, unit=self.other_unit, role="manager",
        )
        with self.assertRaises(PermissionDenied):
            prepare_purchase_drafts(self.order.pk, self.staff)
        self.assert_no_draft_writes()

    def test_inactive_superuser_cannot_create_drafts(self):
        self.owner.is_active = False
        self.owner.save(update_fields=("is_active",))
        with self.assertRaises(PermissionDenied):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assert_no_draft_writes()

    def test_authorized_manager_creates_only_draft_and_remains_idempotent(self):
        self.grant_planning_permissions()
        UnitMembership.objects.create(
            user=self.staff, unit=self.unit, role="manager",
        )
        created = prepare_purchase_drafts(self.order.pk, self.staff)
        self.assertEqual(len(created), 1)
        need = ProcurementNeed.objects.get(pk=created[0])
        self.assertEqual(need.status, "draft")
        self.assertEqual(need.quantity, Decimal("6"))
        self.assertEqual(prepare_purchase_drafts(self.order.pk, self.staff), [])
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).count(), 1)
