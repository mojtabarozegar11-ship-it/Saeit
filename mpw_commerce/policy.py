"""Shared, fail-closed price and fulfillment policy for every configured product.

Products opt in ONCE in their server-managed metadata. Buyers can never enable
an otherwise inactive product, alter a price, or select a fulfillment handler.
No merchant approval is requested for any individual paid order.
"""
from decimal import Decimal
from django.db.models import Prefetch
from core.models import Order, OrderItem

KINDS={"digital", "subscription", "service", "physical"}
MAX_ITEMS=100
MAX_QUANTITY=1000


class CommercePolicyError(ValueError):
    pass


def order_snapshot(order):
    if order.status != "pending" or order.currency != "USD":
        raise CommercePolicyError("Order is not payable using USD crypto quote")
    if not order.customer_id or not order.customer.is_active:
        raise CommercePolicyError("No active buyer for order")
    items=list(order.items.select_related("product"))
    if not items or len(items)>MAX_ITEMS:
        raise CommercePolicyError("Order line count unsupported")
    total=Decimal("0.00")
    fulfillment=[]
    for item in items:
        product=item.product
        settings=product.metadata.get("mpw_commerce") if isinstance(product.metadata,dict) else None
        if (not isinstance(settings,dict) or settings.get("enabled") is not True
            or settings.get("fulfillment") not in KINDS
            or not product.active or product.currency!="USD"
            or item.currency!="USD" or item.quantity<1 or item.quantity>MAX_QUANTITY
            or item.unit_price<=0 or item.unit_price!=product.price):
            raise CommercePolicyError("Inactive, unconfigured or repriced item")
        total+=item.unit_price*item.quantity
        fulfillment.append((item, settings["fulfillment"]))
    if total<=0 or total!=order.total:
        raise CommercePolicyError("Order does not equal its trusted item subtotal")
    return total, fulfillment


def order_ready_for_invoice(order_id,customer_id):
    if type(order_id) is not int or type(customer_id) is not int:
        return False
    order=Order.objects.filter(pk=order_id,customer_id=customer_id).first()
    if order is None:
        return False
    try:
        order_snapshot(order)
    except CommercePolicyError:
        return False
    return True
