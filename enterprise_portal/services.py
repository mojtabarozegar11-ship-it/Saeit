"""Verified, atomic posting for append-only double-entry journals and stock."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import AuditEvent, InventoryItem, JournalEntry, JournalLine, StockMovement
from ecosystem_hub.access import require_unit


def _can(actor, permission):
    if not (actor and actor.is_authenticated and actor.is_active and actor.is_staff):
        raise PermissionDenied("دسترسی حسابداری یا انبار مجاز نیست.")
    if not (actor.is_superuser or actor.has_perm(permission)):
        raise PermissionDenied("برای تأیید قطعی این سند مجوز لازم است.")


@transaction.atomic
def post_journal(entry_id, actor):
    """Only post a balanced and internally consistent draft. Never silently edit."""
    _can(actor, "enterprise_portal.change_journalentry")
    entry = JournalEntry.objects.select_for_update().select_related("unit").get(pk=entry_id)
    require_unit(actor, entry.unit, write=True)
    if entry.status != "draft":
        raise ValidationError("این سند قبلاً قطعی شده است.")
    rows = list(JournalLine.objects.select_related("account").filter(entry=entry))
    if len(rows) < 2:
        raise ValidationError("برای سند قطعی دست‌کم دو آرتیکل لازم است.")
    debit = Decimal("0.00")
    credit = Decimal("0.00")
    for row in rows:
        row.full_clean()
        if row.account.unit_id != entry.unit_id or not row.account.active:
            raise ValidationError("حساب یا واحد مالی نامعتبر است.")
        debit += row.debit
        credit += row.credit
    if debit <= 0 or debit != credit:
        raise ValidationError(f"سند تراز نیست؛ بدهکار {debit} و بستانکار {credit}.")
    # Safe only after all validations; .save() deliberately refuses to edit a posted entry.
    JournalEntry.objects.filter(pk=entry.pk, status="draft").update(
        status="posted", posted_at=timezone.now()
    )
    AuditEvent.objects.create(
        actor=actor, action="journal_posted",
        target=f"JournalEntry:{entry.pk}",
        detail={"reference": entry.reference, "unit": entry.unit.code,
                "currency": entry.currency, "balanced_total": str(debit)}
    )
    return entry


def stock_balance(item_id):
    result = StockMovement.objects.filter(item_id=item_id, status="confirmed")
    incoming = result.filter(direction="in").aggregate(t=Sum("quantity"))["t"] or Decimal("0")
    outgoing = result.filter(direction="out").aggregate(t=Sum("quantity"))["t"] or Decimal("0")
    return incoming - outgoing


@transaction.atomic
def confirm_stock_movement(movement_id, actor):
    """Serializes movements on an item to avoid confirming negative stock."""
    _can(actor, "enterprise_portal.change_stockmovement")
    # Read item's id before acquiring its lock. It cannot be changed after confirmation.
    initial = StockMovement.objects.select_related("item__unit").get(pk=movement_id)
    require_unit(actor, initial.item.unit, write=True)
    InventoryItem.objects.select_for_update().get(pk=initial.item_id)
    movement = StockMovement.objects.select_for_update().get(pk=movement_id)
    if movement.status != "draft":
        raise ValidationError("گردش کالا قبلاً قطعی شده است.")
    if movement.quantity <= 0:
        raise ValidationError("تعداد باید مثبت باشد.")
    if movement.direction == "out" and stock_balance(movement.item_id) < movement.quantity:
        raise ValidationError("موجودی کافی برای خروج این مقدار وجود ندارد.")
    StockMovement.objects.filter(pk=movement.pk, status="draft").update(
        status="confirmed", confirmed_at=timezone.now()
    )
    AuditEvent.objects.create(
        actor=actor, action="stock_confirmed",
        target=f"StockMovement:{movement.pk}",
        detail={"sku": movement.item.sku, "direction": movement.direction,
                "quantity": str(movement.quantity), "reference": movement.reference}
    )
    return movement
