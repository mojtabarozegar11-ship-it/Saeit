"""MojPlayWin commercial release gate; fail closed and never deploys.

The gate separates technical completeness from owner-approved production
activation. It only evaluates supplied evidence and performs no migration,
payment, email, chain query, or file delivery.
"""
REQUIRED_GATES = (
    "source_closure_verified",
    "migrations_verified",
    "merchant_registry_verified",
    "buyer_email_owned",
    "receipt_finality_verified",
    "fulfillment_asset_verified",
    "runtime_preflight_verified",
)

def evaluate_commercial_release(checks):
    if type(checks) is not dict:
        raise TypeError("release checks must be a mapping")
    normalized = {name: checks.get(name) is True for name in REQUIRED_GATES}
    missing = [name for name in REQUIRED_GATES if not normalized[name]]
    return {
        "schema": "mpw.commercial-release-gate.v1",
        "technical_gate_passed": not missing,
        "missing_gates": missing,
        "payment_enabled": False,
        "production_activation_allowed": False,
        "requires_owner_confirmation": True,
        "revenue_proven": False,
        "checks": normalized,
    }
