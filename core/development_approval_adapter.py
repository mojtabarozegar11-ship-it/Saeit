"""Read-only verification of a one-time, owner-issued development grant.

Verifying a grant does NOT consume it or authorize payment. A future trusted
payment executor must atomically consume the identical scoped grant using
ApprovalService.authorize_grant() while serializing the actual cash ledger.
"""

from decimal import Decimal, InvalidOperation


def _positive_decimal(value):
    if isinstance(value, (bool, float)):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount > 0 else None


def verify_grant_snapshot(grant, *, approval_reference, expense_type, vendor,
                          amount, currency, accounting_period, now):
    """Pure fail-closed check; accepts a Django grant or a test object."""
    if grant is None or getattr(grant, "pk", None) is None:
        return False
    if str(grant.pk) != str(approval_reference):
        return False
    approval = getattr(grant, "approval", None)
    if approval is None or getattr(approval, "status", None) != "approved":
        return False
    if (getattr(approval, "action_type", None) != "development_purchase"
            or getattr(approval, "target_type", None) != "DevelopmentPurchase"):
        return False
    if getattr(approval, "requested_by_id", None) != getattr(grant, "actor_id", None):
        return False
    if getattr(grant, "used_at", None) is not None:
        return False
    expiry = getattr(grant, "expires_at", None)
    if expiry is None or now is None:
        return False
    try:
        if expiry <= now:
            return False
    except TypeError:
        return False
    scope = getattr(grant, "scope", None)
    if not isinstance(scope, dict):
        return False
    expected = {
        "proposal_id": str(getattr(approval, "target_id", "")),
        "expense_type": expense_type,
        "vendor": vendor,
        "currency": currency,
        "accounting_period": accounting_period,
    }
    if (not expected["proposal_id"]
            or any(not isinstance(value, str) or not value.strip() for value in expected.values())
            or any(scope.get(key) != value for key, value in expected.items())):
        return False
    requested = _positive_decimal(amount)
    approved = _positive_decimal(scope.get("amount"))
    return requested is not None and approved is not None and requested == approved


def verify_owner_development_grant(*, approval_reference, expense_type, vendor,
                                   amount, currency, accounting_period):
    """Read current approved grant directly from Django; deny on all failures."""
    try:
        grant_pk = int(approval_reference)
    except (TypeError, ValueError):
        return False
    if grant_pk <= 0:
        return False
    try:
        from django.utils import timezone
        from .models import ApprovalGrant
        grant = ApprovalGrant.objects.select_related("approval").filter(pk=grant_pk).first()
        return verify_grant_snapshot(
            grant, approval_reference=approval_reference,
            expense_type=expense_type, vendor=vendor, amount=amount,
            currency=currency, accounting_period=accounting_period,
            now=timezone.now(),
        )
    except Exception:
        # Missing database, broken permissions, stale migration, invalid
        # runtime or driver error never turn into purchase permission.
        return False
