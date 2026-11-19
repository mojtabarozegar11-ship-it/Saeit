"""Read-only per-item access validation for paid orders across the store.

This authorizes a buyer's entitlement; a separate authenticated endpoint must
serve private files securely. Physical shipping / service activations are
queued and are not represented as automatically delivered here.
"""
from core.models import LedgerEntry, OrderItem
from .models import CommerceFulfillment, CommerceInvoice, CommerceReceipt


def can_access_purchased_digital_item(item_id,customer_id):
    if type(item_id) is not int or type(customer_id) is not int:
        return False
    item=(OrderItem.objects.select_related("order","product")
          .filter(pk=item_id,order__customer_id=customer_id,
                  order__status="paid").first())
    if item is None:
        return False
    # Native walletless TRX uses PaymentIntent + finalized event + credit,
    # not the signed CommerceInvoice receipt format. Keep both paths separate.
    from core.models import PaymentIntent
    from core.crown_tron_receipts import verified_walletless_credit
    intent = PaymentIntent.objects.filter(order=item.order, provider="mpw_walletless_trx_v1").first()
    if intent is not None:
        if CommerceInvoice.objects.filter(order=item.order).exists():
            return False
        if not verified_walletless_credit(item.order, intent):
            return False
        return CommerceFulfillment.objects.filter(
            item=item, kind=CommerceFulfillment.Kind.DIGITAL,
            status__in=(CommerceFulfillment.Status.READY, CommerceFulfillment.Status.COMPLETE),
        ).exists()
    # Existing paid buyer rights are keyed to the durable grant; unpublishing
    # a product afterwards does not silently revoke an already-paid download.
    try:
        invoice=item.order.mpw_commerce_invoice
        grant=item.mpw_fulfillment
        receipt=invoice.payment_receipt
    except (CommerceInvoice.DoesNotExist,CommerceFulfillment.DoesNotExist,
            CommerceReceipt.DoesNotExist):
        return False
    if (invoice.status!=CommerceInvoice.Status.PAID
        or invoice.total_usd!=item.order.total
        or grant.kind!="digital"
        or grant.status not in (CommerceFulfillment.Status.READY,
                                CommerceFulfillment.Status.COMPLETE)
        or receipt.network!=invoice.network
        or receipt.recipient.lower()!=invoice.recipient.lower()
        or receipt.amount_atomic!=invoice.amount_atomic):
        return False
    return LedgerEntry.objects.filter(
        order=item.order,entry_type="payment",
        payment_intent__isnull=True,amount=invoice.total_usd,
        currency="USD",reference="mpw-commerce:"+receipt.network+":"+receipt.tx_hash,
        metadata__commerce_invoice_id=invoice.pk,
        metadata__evidence_digest=receipt.evidence_digest,
    ).exists()
