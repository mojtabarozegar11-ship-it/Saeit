import pytest

from core.services import normalize_risk, requires_owner_approval


def test_invalid_risk_is_rejected():
    with pytest.raises(ValueError, match="Invalid risk level"):
        normalize_risk("unknown")


def test_valid_risk_is_preserved():
    assert normalize_risk(" HIGH ") == "high"


def test_sensitive_action_requires_approval_even_with_low_risk():
    assert requires_owner_approval("deploy", "low") is True



@pytest.mark.parametrize("action", [
    "trade", "live-trade", "execute_trade", "broker_order", "place_order",
    "withdraw", "withdraw_money", "transfer_funds", "send_funds",
    "spend-money", "change_payment_destination",
    "token_launch", "token_mint", "fund_wallet",
    "send_sms", "send-email", "send_message",
    "delete_file", "delete_financial_records", "publish_legal_commitment",
    "sign_contract", "identity_verification", "scale_budget",
])
def test_named_real_world_effects_cannot_claim_low_risk_exemption(action):
    assert requires_owner_approval(action, "low") is True


@pytest.mark.parametrize("action", [
    "research", "income_market_research",
    "mojtrade_observation_ingest", "mojtrade_demo_audit_ingest",
    "factory_native_review",
])
def test_internal_read_only_and_review_actions_remain_available_without_owner_grant(action):
    assert requires_owner_approval(action, "low") is False
