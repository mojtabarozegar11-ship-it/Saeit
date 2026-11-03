"""Budgetary manufacturing cost estimation, not a financial posting engine.

Price references must have verification and a documentary source. Every material
needs a price in the scenario's single currency and from the same company unit.
Missing prices produce total=None, never a misleading partial total.
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
from django.utils import timezone
from .models import MaterialPriceReference

MATERIAL_PRECISION = Decimal("0.001")
MONEY_PRECISION = Decimal("0.01")


def estimate_manufacturing_cost(scenario, *, as_of=None):
    order = scenario.order
    recipe = order.formula
    if not scenario.unit_id or scenario.unit_id != order.unit_id or recipe.unit_id != scenario.unit_id:
        raise ValueError("Cost scenario, production order and BOM must belong to the same unit.")
    if recipe.yield_quantity <= 0 or order.quantity <= 0:
        raise ValueError("Production quantity and recipe yield must be positive.")
    when = as_of or timezone.localdate()
    components = []
    total_material = Decimal("0.00")
    rows = list(recipe.materials.select_related("item").order_by("item__sku"))
    missing = []
    for component in rows:
        if component.item.unit_id != scenario.unit_id:
            raise ValueError("A BOM component belongs to another company unit.")
        scrap = Decimal("1") + component.scrap_percent / Decimal("100")
        needed = ((order.quantity / recipe.yield_quantity) * component.quantity * scrap).quantize(
            MATERIAL_PRECISION, rounding=ROUND_UP,
        )
        reference = MaterialPriceReference.objects.filter(
            unit=scenario.unit,
            item=component.item,
            currency=scenario.currency,
            status="verified",
            as_of__lte=when,
        ).exclude(evidence_ref="").order_by("-as_of", "-pk").first()
        if reference:
            line_total = (needed * reference.amount).quantize(
                MONEY_PRECISION, rounding=ROUND_HALF_UP,
            )
            total_material += line_total
        else:
            line_total = None
            missing.append(component.item.sku)
        components.append({
            "sku": component.item.sku,
            "title": component.item.title,
            "amount_needed": needed,
            "measure": component.item.measure,
            "rate": reference.amount if reference else None,
            "price_source": reference.evidence_ref if reference else None,
            "rate_date": reference.as_of if reference else None,
            "material_total": line_total,
        })
    complete = bool(rows) and not missing
    total = (total_material + scenario.labor_estimate + scenario.overhead_estimate).quantize(
        MONEY_PRECISION,
    ) if complete else None
    return {
        "scenario_id": scenario.pk,
        "order_code": order.code,
        "product": recipe.product.title,
        "unit": scenario.unit.code,
        "currency": scenario.currency,
        "as_of": when,
        "components": components,
        "missing_skus": missing,
        "complete": complete,
        "material_total": total_material if complete else None,
        "labor_estimate": scenario.labor_estimate,
        "overhead_estimate": scenario.overhead_estimate,
        "total": total,
        "unit_cost": ((total / order.quantity).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
                      if total is not None else None),
        "posted_to_ledger": False,
        "stock_movement_created": False,
    }
