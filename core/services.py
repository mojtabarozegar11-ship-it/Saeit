SENSITIVE_ACTIONS = frozenset({
    "publish",
    "payment",
    "delete_data",
    "deploy",
    "production_change",
    "legal_action",
    "external_write",
    "credential_rotation",
    "database_migration",
})


def normalize_action(action):
    """Return a stable action key for approval-policy decisions."""
    return str(action or "").strip().lower().replace("-", "_").replace(" ", "_")


def requires_owner_approval(action, risk="low"):
    """Return True when an action must stop for explicit owner approval."""
    normalized_action = normalize_action(action)
    normalized_risk = str(risk or "low").strip().lower()
    return normalized_risk in {"high", "critical"} or normalized_action in SENSITIVE_ACTIONS
