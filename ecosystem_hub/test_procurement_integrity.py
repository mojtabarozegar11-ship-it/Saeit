"""Fail-closed MRP planning: no procurement or payment side effects."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from enterprise_portal.models import (
    AuditEvent, BusinessUnit, InventoryItem, JournalEntry, StockMovement,
)
from enterprise_portal.services import confirm_stock_movement
from .models import (
    BillOfMaterials, MaterialRequirement, ProcurementNeed, ProductionOrder,
)
from .procurement import material_shortages, prepare_purchase_drafts


@override_settings(COMPANY_OFFICE_REQUIRE_MFA=False, DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ProcurementIntegrityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="mrp-integrity-owner", password="not-a-real-password",
        )
        self.unit = BusinessUnit.objects.create(code="farm-mrp", name="Farm MRP")
        self.product = InventoryItem.objects.create(
            unit=self.unit, sku="FINAL-MRP", title="Final Product",
        )
        self.material = InventoryItem.objects.create(
            unit=self.unit, sku="INPUT-MRP", title="Material",
        )
        self.recipe = BillOfMaterials.objects.create(
            unit=self.unit, product=self.product, code="MRP-RECIPE",
            yield_quantity=Decimal("1"),
        )
        self.line = MaterialRequirement.objects.create(
            formula=self.recipe, item=self.material,
            quantity=Decimal("2"), scrap_percent=Decimal("0"),
        )
        self.order = ProductionOrder.objects.create(
            unit=self.unit, formula=self.recipe, code="MRP-ORDER",
            quantity=Decimal("10"), owner=self.owner,
        )

    def test_legacy_invalid_bom_never_understates_materials_or_creates_drafts(self):
        for quantity, scrap in (
            (Decimal("-2"), Decimal("0")),
            (Decimal("0"), Decimal("0")),
            (Decimal("2"), Decimal("-1")),
            (Decimal("2"), Decimal("101")),
        ):
            MaterialRequirement.objects.filter(pk=self.line.pk).update(
                quantity=quantity, scrap_percent=scrap,
            )
            with self.assertRaises(ValidationError):
                material_shortages(self.order)
            with self.assertRaises(ValidationError):
                prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())

    def test_repeated_draft_is_idempotent_until_quantity_changes(self):
        ids = prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(len(ids), 1)
        self.assertEqual(ProcurementNeed.objects.get().quantity, Decimal("20"))
        self.assertEqual(prepare_purchase_drafts(self.order.pk, self.owner), [])
        self.order.quantity = Decimal("11")
        self.order.save(update_fields=("quantity",))
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(ProcurementNeed.objects.get().quantity, Decimal("20"))
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).count(), 1)
        self.assertFalse(JournalEntry.objects.exists())

    def test_confirmed_stock_removes_shortage_but_cannot_silently_keep_old_draft(self):
        prepare_purchase_drafts(self.order.pk, self.owner)
        movement = StockMovement.objects.create(
            item=self.material, direction="in", reference="CONFIRMED-STOCK",
            quantity=Decimal("25"), created_by=self.owner,
        )
        confirm_stock_movement(movement.pk, self.owner)
        self.assertEqual(material_shortages(self.order)[0]["shortage"], Decimal("0"))
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(ProcurementNeed.objects.get().status, "draft")
        self.assertEqual(ProcurementNeed.objects.get().quantity, Decimal("20"))


    def test_invalid_bom_returns_controlled_http_400_not_server_error(self):
        MaterialRequirement.objects.filter(pk=self.line.pk).update(
            quantity=Decimal("-1"),
        )
        self.client.force_login(self.owner)
        path = f"/company/office/ecosystem/production/materials/{self.order.pk}/"
        response = self.client.get(path, secure=True)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("INPUT-MRP", response.content.decode("utf-8"))
        self.assertFalse(ProcurementNeed.objects.exists())

    def test_removed_material_does_not_leave_old_draft_as_current(self):
        prepare_purchase_drafts(self.order.pk, self.owner)
        self.line.delete()
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(ProcurementNeed.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).count(), 1)

    def test_changed_due_date_cannot_reuse_existing_purchase_draft(self):
        created = prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(len(created), 1)
        self.assertIsNone(ProcurementNeed.objects.get().required_by)
        self.order.due_date = date(2026, 11, 15)
        self.order.save(update_fields=("due_date",))
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertIsNone(ProcurementNeed.objects.get().required_by)
        self.assertEqual(ProcurementNeed.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).count(), 1)
        self.assertFalse(JournalEntry.objects.exists())

    def test_changed_order_code_cannot_keep_misleading_purchase_reason(self):
        created = prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(len(created), 1)
        original_reason = ProcurementNeed.objects.get().request_reason
        self.order.code = "MRP-ORDER-RENAMED"
        self.order.save(update_fields=("code",))
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertEqual(ProcurementNeed.objects.get().request_reason, original_reason)
        self.assertEqual(ProcurementNeed.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).count(), 1)
        self.assertFalse(JournalEntry.objects.exists())

    def test_inactive_unit_cannot_generate_purchase_draft(self):
        BusinessUnit.objects.filter(pk=self.unit.pk).update(active=False)
        self.unit.refresh_from_db()
        with self.assertRaises(ValidationError):
            material_shortages(self.order)
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())

    def test_inactive_material_cannot_generate_purchase_draft(self):
        InventoryItem.objects.filter(pk=self.material.pk).update(active=False)
        with self.assertRaises(ValidationError):
            material_shortages(self.order)
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())

    def test_inactive_finished_product_cannot_generate_purchase_draft(self):
        InventoryItem.objects.filter(pk=self.product.pk).update(active=False)
        with self.assertRaises(ValidationError):
            material_shortages(self.order)
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())

    def test_empty_bom_cannot_be_mistaken_for_zero_shortage(self):
        self.line.delete()
        with self.assertRaises(ValidationError):
            material_shortages(self.order)
        with self.assertRaises(ValidationError):
            prepare_purchase_drafts(self.order.pk, self.owner)
        self.assertFalse(ProcurementNeed.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(
            action="ecosystem_procurement_draft",
        ).exists())
