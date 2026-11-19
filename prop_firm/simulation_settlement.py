"""Internal settlement boundary; caller must be an independently authenticated reconciler."""
import re
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from .models import PropPlan1Invoice, PropPlan1Receipt, TronSettlementLedger, PropSimulationInvoiceOwner
from .reward_reserve_persistence import allocate_reward_reserve_after_settlement
from .simulation_fulfillment import provision_simulation_account
from .simulation_invoice_contract import PRODUCT_CODE, CONTRACT_VERSION, NETWORK

@transaction.atomic
def settle_and_provision(*, invoice_id, owner, tx_hash, observed_network,
                         observed_asset, observed_recipient, observed_amount_sun,
                         independently_finalized, evidence_digest,
                         verified_owner_email):
    invoice = PropPlan1Invoice.objects.select_for_update().get(pk=invoice_id)
    if invoice.product_code != PRODUCT_CODE or invoice.contract_version != CONTRACT_VERSION:
        raise ValidationError("Simulation invoice required")
    if not owner.is_authenticated or not owner.is_active or owner.email != invoice.buyer_email or verified_owner_email != owner.email:
        raise ValidationError("Verified owner mismatch")
    if not PropSimulationInvoiceOwner.objects.filter(invoice=invoice, owner=owner).exists():
        raise ValidationError("Invoice ownership mismatch")
    if (independently_finalized is not True or observed_network != NETWORK
            or observed_asset != "TRX" or observed_recipient != invoice.recipient
            or type(observed_amount_sun) is not int or observed_amount_sun != invoice.amount_sun):
        raise ValidationError("Observed settlement does not match invoice")
    if not isinstance(tx_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", tx_hash):
        raise ValidationError("Canonical TRON transaction hash required")
    if not isinstance(evidence_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", evidence_digest):
        raise ValidationError("Canonical evidence digest required")
    if invoice.status == "paid":
        receipt = invoice.receipt
        if receipt.ledger.tx_hash != tx_hash or receipt.ledger.evidence_digest != evidence_digest:
            raise ValidationError("Existing settlement mismatch")
    else:
        if invoice.status != "pending":
            raise ValidationError("Invoice is not pending")
        try:
            with transaction.atomic():
                ledger = TronSettlementLedger.objects.create(
                    network=NETWORK, tx_hash=tx_hash, amount_sun=observed_amount_sun,
                    evidence_digest=evidence_digest, trusted_reconciler_attestation=True)
        except IntegrityError as exc:
            raise ValidationError("Transaction already settled") from exc
        invoice.status = "paid"
        invoice.save(update_fields=["status"])
        receipt = PropPlan1Receipt.objects.create(invoice=invoice, ledger=ledger)
        allocate_reward_reserve_after_settlement(invoice_id=invoice.pk)
    account = provision_simulation_account(invoice_id=invoice.pk, owner=owner)
    return receipt, account
