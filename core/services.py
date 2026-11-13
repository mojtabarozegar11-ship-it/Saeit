from .general_manager_policy import OWNER_APPROVAL_ACTIONS


# Explicit action names at the agent task/gateway boundary. A tool's claimed
# "low" risk is never sufficient to authorize a real-world financial,
# trading, communication, publishing, deleting or production-changing effect.
# Reuse the general-manager list to prevent policy divergence.
SENSITIVE_ACTIONS = frozenset({
    "publish", "publish_article", "public_release", "external_post",
    "payment", "pay", "purchase", "purchase_token",
    "trade", "live_trade", "execute_trade", "submit_trade",
    "broker_order", "broker_trade", "place_order",
    "withdraw", "withdrawal", "withdraw_funds",
    "transfer", "transfer_funds", "send_funds",
    "fund_account", "fund_wallet", "token_launch", "token_mint",
    "send_email", "send_sms", "send_message",
    "delete_data", "delete_file", "delete_record", "delete_account",
    "deploy", "production_change", "legal_action", "external_write",
    "credential_rotation", "database_migration",
}) | OWNER_APPROVAL_ACTIONS


def normalize_action(action):
    """Return a stable action key for approval-policy decisions."""
    return str(action or "").strip().lower().replace("-", "_").replace(" ", "_")


VALID_RISKS = frozenset({"low", "medium", "high", "critical"})


def normalize_risk(risk="low"):
    """Return a validated risk level; never silently downgrade invalid input."""
    normalized = str(risk or "low").strip().lower()
    if normalized not in VALID_RISKS:
        raise ValueError(f"Invalid risk level: {normalized}")
    return normalized


def requires_owner_approval(action, risk="low"):
    """Return True when an action must stop for explicit owner approval."""
    normalized_action = normalize_action(action)
    normalized_risk = normalize_risk(risk)
    return normalized_risk in {"high", "critical"} or normalized_action in SENSITIVE_ACTIONS
