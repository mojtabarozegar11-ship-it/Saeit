"""Unit-safe planning of BOM shortages and idempotent draft procurement requests.

Nothing sends a purchase order, settles an invoice or confirms inventory.
"""
from decimal import Decimal, ROUND_UP
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from enterprise_portal.models import AuditEvent
from enterprise_portal.services import stock_balance
from .access import require_unit
from .models import MaterialRequirement, ProcurementNeed, ProductionOrder


def material_shortages(order):
    recipe = order.formula
    if order.unit_id != recipe.unit_id:
        raise ValidationError("فرمول سفارش متعلق به واحد دیگری است.")
    if recipe.product.unit_id != order.unit_id:
        raise ValidationError("محصول نهایی فرمول متعلق به واحد دیگری است.")
    if not order.unit.active:
        raise ValidationError("برنامه‌ریزی تأمین برای واحد غیرفعال مجاز نیست.")
    if not recipe.product.active:
        raise ValidationError("محصول نهایی غیرفعال است؛ فرمول تولید باید بازبینی شود.")
    if order.quantity <= 0 or recipe.yield_quantity <= 0:
        raise ValidationError("مقدار تولید و بازده فرمول باید مثبت باشند.")
    items = []
    for row in recipe.materials.select_related("item").order_by("item__sku"):
        if row.item.unit_id != order.unit_id:
            raise ValidationError("ماده اولیه متعلق به واحد تولید نیست.")
        if not row.item.active:
            raise ValidationError("ماده اولیه غیرفعال است؛ درخواست تأمین جدید مجاز نیست.")
        # Legacy imports and QuerySet.update bypass model validators.
        # Never turn malformed BOM inputs into understated procurement needs.
        if row.quantity <= 0 or not Decimal("0") <= row.scrap_percent <= Decimal("100"):
            raise ValidationError("مقدار یا درصد ضایعات مواد فرمول نامعتبر است.")
        required = (
            (order.quantity / recipe.yield_quantity)
            * row.quantity
            * (Decimal("1") + row.scrap_percent / Decimal("100"))
        ).quantize(Decimal("0.001"), rounding=ROUND_UP)
        available = stock_balance(row.item_id)
        missing = max(Decimal("0"), required - available)
        items.append({
            "item": row.item, "required": required,
            "available": available, "shortage": missing,
            "measure": row.item.measure,
        })
    if not items:
        raise ValidationError("فرمول تولید فاقد مواد اولیه است؛ نتیجه صفر به معنای آمادگی تأمین نیست.")
    return items


@transaction.atomic
def prepare_purchase_drafts(order_id, actor):
    """Operates only on a user-confirmed draft action, never as a bot side-effect.

    Enforce the same permissions inside the service, not only in HTTP views.
    This also protects management commands and future internal callers.
    Repeated calls are idempotent by unit+MRP<order id>-<material id>.
    """
    if not (actor and actor.is_authenticated and actor.is_active and actor.is_staff):
        raise PermissionDenied("ثبت پیش‌نویس تأمین به کاربر فعال و مجاز نیاز دارد.")
    required_permissions = (
        "ecosystem_hub.add_procurementneed",
        "ecosystem_hub.view_productionorder",
        "ecosystem_hub.view_billofmaterials",
        "enterprise_portal.view_inventoryitem",
        "enterprise_portal.view_stockmovement",
    )
    if not (actor.is_superuser or all(actor.has_perm(p) for p in required_permissions)):
        raise PermissionDenied("مجوز کامل برنامه‌ریزی مواد و ثبت پیش‌نویس تأمین لازم است.")
    order = ProductionOrder.objects.select_for_update().select_related(
        "unit", "formula",
    ).get(pk=order_id)
    require_unit(actor, order.unit, write=True)
    if order.state not in ("draft", "review", "approved"):
        raise ValidationError("برای سفارش مختومه یا لغوشده درخواست تأمین ساخته نمی‌شود.")
    # A repeated POST is idempotent only while the original shortage is still
    # current. A changed BOM, order quantity or confirmed stock must not leave
    # an obsolete draft silently masquerading as a fresh recommendation.
    shortage_rows = material_shortages(order)
    expected = {
        f"MRP-{order.pk}-{row['item'].pk}": row for row in shortage_rows
    }
    existing = {
        need.reference: need for need in ProcurementNeed.objects.select_for_update().filter(
            unit=order.unit, reference__startswith=f"MRP-{order.pk}-",
        )
    }
    # Preflight before any insertion; atomicity covers all materials.
    # An unchanged shortage is not enough: due date and source order code
    # must still match the draft that a human is being asked to review.
    expected_reason = (
        f"پیشنهاد کسری مواد سفارش تولید {order.code}؛ خرید واقعی انجام نشده است."
    )
    for reference, need in existing.items():
        row = expected.get(reference)
        if (row is None or need.item_id != row["item"].pk
                or need.status != "draft" or row["shortage"] <= 0
                or need.quantity != row["shortage"]
                or need.required_by != order.due_date
                or need.request_reason != expected_reason):
            raise ValidationError(
                "درخواست تأمین قبلی با کسری فعلی تطابق ندارد؛ بازبینی انسانی لازم است."
            )
    new_ids = []
    for reference, row in expected.items():
        if row["shortage"] <= 0 or reference in existing:
            continue
        item = row["item"]
        item_record, created = ProcurementNeed.objects.get_or_create(
            unit=order.unit,
            reference=reference,
            defaults={
                "item": item,
                "quantity": row["shortage"],
                "request_reason": expected_reason,
                "required_by": order.due_date,
                "status": "draft",
                "requested_by": actor,
            },
        )
        if created:
            item_record.full_clean()
            new_ids.append(item_record.pk)
            AuditEvent.objects.create(
                actor=actor, action="ecosystem_procurement_draft",
                target=f"ProcurementNeed:{item_record.pk}",
                detail={"unit_id": order.unit_id, "production_order_id": order.pk,
                        "inventory_item_id": item.pk,
                        "shortage": str(row["shortage"]),
                        "no_payment_or_supplier_order": True},
            )
    return new_ids
