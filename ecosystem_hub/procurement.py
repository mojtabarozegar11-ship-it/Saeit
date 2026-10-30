"""Unit-safe planning of BOM shortages and idempotent draft procurement requests.

Nothing sends a purchase order, settles an invoice or confirms inventory.
"""
from decimal import Decimal, ROUND_UP
from django.core.exceptions import ValidationError
from django.db import transaction
from enterprise_portal.models import AuditEvent
from enterprise_portal.services import stock_balance
from .models import MaterialRequirement, ProcurementNeed, ProductionOrder


def material_shortages(order):
    recipe = order.formula
    if order.unit_id != recipe.unit_id:
        raise ValidationError("فرمول سفارش متعلق به واحد دیگری است.")
    if order.quantity <= 0 or recipe.yield_quantity <= 0:
        raise ValidationError("مقدار تولید و بازده فرمول باید مثبت باشند.")
    items = []
    for row in recipe.materials.select_related("item").order_by("item__sku"):
        if row.item.unit_id != order.unit_id:
            raise ValidationError("ماده اولیه متعلق به واحد تولید نیست.")
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
    return items


@transaction.atomic
def prepare_purchase_drafts(order_id, actor):
    """Operates only on a user-confirmed draft action, never as a bot side-effect.

    Authorization is enforced in the HTTP handler, and repeated calls are
    idempotent by unit+MRP<order id>-<material id> unique reference.
    """
    order = ProductionOrder.objects.select_for_update().select_related(
        "unit", "formula",
    ).get(pk=order_id)
    if order.state not in ("draft", "review", "approved"):
        raise ValidationError("برای سفارش مختومه یا لغوشده درخواست تأمین ساخته نمی‌شود.")
    new_ids = []
    for row in material_shortages(order):
        if row["shortage"] <= 0:
            continue
        item = row["item"]
        reference = f"MRP-{order.pk}-{item.pk}"
        item_record, created = ProcurementNeed.objects.get_or_create(
            unit=order.unit,
            reference=reference,
            defaults={
                "item": item,
                "quantity": row["shortage"],
                "request_reason": f"پیشنهاد کسری مواد سفارش تولید {order.code}؛ خرید واقعی انجام نشده است.",
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
