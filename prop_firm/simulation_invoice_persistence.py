"""Persistence boundary for the simulation-only offer; no settlement or transfer."""
import re
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import PropPlan1Invoice
from .simulation_invoice_contract import SimulationInvoiceContract

@transaction.atomic
def persist_simulation_invoice(*, order_ref, buyer_email, contract, gates,
                               buyer_terms_acceptance, retry_eligibility_verified=False):
    if not isinstance(contract, SimulationInvoiceContract):
        raise ValidationError("Simulation contract required")
    if buyer_terms_acceptance is not True:
        raise ValidationError("Terms acceptance required")
    if not isinstance(order_ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}", order_ref):
        raise ValidationError("Invalid order reference")
    if not isinstance(buyer_email, str) or len(buyer_email)>254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", buyer_email):
        raise ValidationError("Invalid buyer email")
    # The existing schema has no single-use retry entitlement. Do not trust
    # a caller boolean until the entitlement can be consumed transactionally.
    if contract.purchase_kind != "first":
        raise ValidationError("Retry entitlement persistence not available")
    snapshot = contract.release(gates, retry_eligibility_verified=False)
    defaults = {key: snapshot[key] for key in (
        "product_code", "contract_version", "network", "amount_sun",
        "recipient", "purchase_kind")}
    defaults.update(buyer_email=buyer_email, buyer_terms_acceptance=True,
                    contract_digest=contract.digest(), status="pending")
    invoice, created = PropPlan1Invoice.objects.select_for_update().get_or_create(
        order_ref=order_ref, defaults=defaults)
    if not created and any(getattr(invoice, key) != value for key, value in defaults.items() if key != "status"):
        raise ValidationError("Immutable invoice contract mismatch")
    return invoice
