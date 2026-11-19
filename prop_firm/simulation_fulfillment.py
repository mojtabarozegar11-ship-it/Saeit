"""Read-only fulfillment eligibility; never issue a broker account."""
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import PropPlan1Invoice, PropPlan1Receipt, PropRewardReserveAllocation
from .simulation_invoice_contract import PRODUCT_CODE, CONTRACT_VERSION, NETWORK, FEES_SUN

@transaction.atomic
def verified_simulation_purchase(*, invoice_id, buyer_email):
    invoice = PropPlan1Invoice.objects.select_for_update().get(pk=invoice_id)
    if (invoice.product_code != PRODUCT_CODE or invoice.contract_version != CONTRACT_VERSION
            or invoice.network != NETWORK or invoice.status != "paid"
            or invoice.buyer_email != buyer_email or invoice.buyer_terms_acceptance is not True
            or invoice.amount_sun != FEES_SUN.get(invoice.purchase_kind)):
        raise ValidationError("Simulation purchase not eligible")
    receipt = PropPlan1Receipt.objects.select_for_update().select_related("ledger").filter(invoice=invoice).first()
    if receipt is None:
        raise ValidationError("Receipt required")
    ledger = receipt.ledger
    if (ledger.network != NETWORK or ledger.amount_sun != invoice.amount_sun
            or ledger.trusted_reconciler_attestation is not True):
        raise ValidationError("Trusted settlement required")
    allocation = PropRewardReserveAllocation.objects.select_for_update().filter(invoice=invoice, settlement=ledger).first()
    if allocation is None or allocation.fee_sun != invoice.amount_sun:
        raise ValidationError("Reward reserve allocation required")
    return {"invoice_id": invoice.pk, "order_ref": invoice.order_ref,
            "account_mode": "simulated", "starting_balance_usd": 1000,
            "challenge_days": 60, "data_mode": "synthetic_replay"}


@transaction.atomic
def provision_simulation_account(*, invoice_id, owner):
    from .models import PropSimulationAccount
    if not owner.is_authenticated or not owner.is_active or not owner.email:
        raise ValidationError("Active authenticated owner required")
    verified_simulation_purchase(invoice_id=invoice_id, buyer_email=owner.email)
    account, _ = PropSimulationAccount.objects.get_or_create(
        invoice_id=invoice_id, defaults={"owner": owner})
    if account.owner_id != owner.pk:
        raise ValidationError("Invoice already bound to another owner")
    return account
