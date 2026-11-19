"""Persistence boundary for the simulation-only offer; no settlement or transfer."""
import re
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import PropPlan1Invoice, PropSimulationInvoiceOwner
from .simulation_invoice_contract import SimulationInvoiceContract, COMMERCIAL_CONTRACT_VERSION
from .simulation_retry import RETRY_PREFIX, locked_retry_reference

@transaction.atomic
def persist_simulation_invoice(*, order_ref, owner, buyer_email, contract, gates,
                               buyer_terms_acceptance, retry_eligibility_verified=False, retry_account_id=None):
    if not owner.is_authenticated or not owner.is_active or owner.pk is None or owner.email != buyer_email:
        raise ValidationError("Authenticated invoice owner required")
    if not isinstance(contract, SimulationInvoiceContract):
        raise ValidationError("Simulation contract required")
    if buyer_terms_acceptance is not True:
        raise ValidationError("Terms acceptance required")
    if not isinstance(order_ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}", order_ref):
        raise ValidationError("Invalid order reference")
    if not isinstance(buyer_email, str) or len(buyer_email)>254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", buyer_email):
        raise ValidationError("Invalid buyer email")
    # Caller booleans are never evidence of retry eligibility. The old account
    # is locked and its signed ledger replayed within this invoice transaction.
    retry_verified = False
    if contract.purchase_kind == "retry":
        if contract.version != COMMERCIAL_CONTRACT_VERSION:
            raise ValidationError("Commercial retry contract required")
        expected = locked_retry_reference(account_id=retry_account_id, owner=owner)
        if order_ref != expected:
            raise ValidationError("Retry reference mismatch")
        retry_verified = True
    elif contract.purchase_kind != "first" or retry_account_id is not None or order_ref.upper().startswith(RETRY_PREFIX):
        raise ValidationError("Invalid first-purchase reference")
    snapshot = contract.release(gates, retry_eligibility_verified=retry_verified)
    defaults = {key: snapshot[key] for key in (
        "product_code", "contract_version", "network", "amount_sun",
        "recipient", "purchase_kind")}
    defaults.update(buyer_email=buyer_email, buyer_terms_acceptance=True,
                    contract_digest=contract.digest(), status="pending")
    invoice, created = PropPlan1Invoice.objects.select_for_update().get_or_create(
        order_ref=order_ref, defaults=defaults)
    if not created and any(getattr(invoice, key) != value for key, value in defaults.items() if key != "status"):
        raise ValidationError("Immutable invoice contract mismatch")
    if created:
        PropSimulationInvoiceOwner.objects.create(invoice=invoice, owner=owner)
    elif not PropSimulationInvoiceOwner.objects.filter(invoice=invoice, owner=owner).exists():
        raise ValidationError("Invoice ownership mismatch")
    return invoice
