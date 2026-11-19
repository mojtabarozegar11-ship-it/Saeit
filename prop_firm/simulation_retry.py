"""One durable retry invoice per proven failed commercial simulation.
No migration: the existing unique invoice.order_ref is the entitlement key.
Expiry alone is not failure. A signed event replay must prove drawdown breach.
"""
from hashlib import sha256
from django.core.exceptions import ValidationError
from .simulation_invoice_contract import COMMERCIAL_CONTRACT_VERSION

RETRY_PREFIX = "SIM-R-"

def retry_reference(account):
    # Stable across sessions and terms/key rotations, does not expose the PK.
    # The original immutable invoice reference is globally unique.
    material = ("mojprop.retry.v1:" + account.invoice.order_ref).encode("utf-8")
    return RETRY_PREFIX + sha256(material).hexdigest()

def locked_retry_reference(*, account_id, owner):
    """Caller must hold an outer atomic transaction through invoice insertion."""
    from django.db import connection
    from .simulation_event_service import _locked_account, _replay, VERSION
    if not connection.in_atomic_block:
        raise ValidationError("Retry reservation requires a transaction")
    if type(account_id) is not int or account_id <= 0:
        raise ValidationError("Invalid previous challenge")
    account = _locked_account(account_id, owner)
    if (account.invoice.contract_version != COMMERCIAL_CONTRACT_VERSION
            or account.status not in ("active", "expired_review", "failed")):
        raise ValidationError("Commercial failed challenge required")
    engine, sequence, _ = _replay(account)
    if engine.execution_version != VERSION or sequence < 1 or engine.blocked is not True:
        raise ValidationError("Verified drawdown failure required")
    return retry_reference(account)
