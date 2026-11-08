"""Buyer-safe copy for native TRX purchase history; never changes payment state."""


def buyer_invoice_action(intent_id, intent_status, proof, expires_at, now):
    """Return safe HTML after authoritative buyer ownership and payment checks."""
    if type(intent_id) is not int or intent_id <= 0 or type(proof) is not dict:
        raise ValueError("Untrusted purchase status context")
    if (intent_status == "paid" and proof.get("can_download") is True
            and proof.get("status") == "paid"):
        return (
            f'<a class="button" href="/commerce/trx-easy/download/{intent_id}/">'
            'Download purchase</a>'
        )
    if proof.get("status") == "review" or intent_status == "paid":
        return (
            "Payment or download requires verification. Do not pay again; "
            "contact support with your order number."
        )
    if intent_status == "awaiting_chain":
        if expires_at > now:
            return f'<a href="/commerce/trx-easy/invoice/{intent_id}/">View payment invoice</a>'
        return (
            "Invoice expired and is no longer payable. If you already sent TRX, "
            "do not pay again; contact support with your order number and transaction hash."
        )
    return (
        "Invoice is not available for payment. If you already sent TRX, "
        "do not pay again; contact support with your order number."
    )
