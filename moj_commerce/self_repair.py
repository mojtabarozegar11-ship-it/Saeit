"""Bounded invoice scan-schedule repair. No blockchain IO or payment mutations.

Only a still-open, internally consistent checkout may regain its missing scan
state. This is not an assertion that a wallet signature or funds are valid:
the ordinary finalized-chain verifier must still run independently.
"""
from .models import Entitlement, Merchant, MerchantAddress, PaymentDiscrepancy, Purchase


def scan_repair_eligibility(purchase: Purchase, *, now):
    """Return a fixed reason code; 'eligible' is the only writeable case."""
    if purchase.status != Purchase.Status.PENDING:
        return 'not_pending'
    if (purchase.paid_at is not None or purchase.delivered_at is not None
            or purchase.confirmed_txid or purchase.fulfillment_event_id
            or purchase.delivery_id):
        return 'financial_marker_present'
    if (not purchase.created_at or not purchase.expires_at
            or purchase.created_at > now or purchase.expires_at <= now
            or purchase.expires_at <= purchase.created_at):
        return 'outside_open_invoice'
    if purchase.network != 'tron-mainnet' or purchase.amount_sun <= 0 or purchase.usd_amount <= 0:
        return 'invalid_invoice_terms'
    if purchase.merchant.status != Merchant.Status.APPROVED:
        return 'merchant_not_approved'
    if (purchase.product.merchant_id != purchase.merchant_id
            or purchase.destination.merchant_id != purchase.merchant_id):
        return 'ownership_mismatch'
    address = purchase.destination
    if (address.verified_via != MerchantAddress.ProofMethod.SIGN_V2
            or address.verified_at is None
            or address.verified_at > purchase.created_at
            or len(address.address) != 34
            or not address.address.startswith('T')):
        return 'wallet_proof_invalid'
    if (PaymentDiscrepancy.objects.filter(purchase_id=purchase.pk).exists()
            or Entitlement.objects.filter(purchase_id=purchase.pk).exists()):
        return 'manual_financial_review'
    return 'eligible'
