import pytest

from core.services import normalize_risk, requires_owner_approval


def test_invalid_risk_is_rejected():
    with pytest.raises(ValueError, match="Invalid risk level"):
        normalize_risk("unknown")


def test_valid_risk_is_preserved():
    assert normalize_risk(" HIGH ") == "high"


def test_sensitive_action_requires_approval_even_with_low_risk():
    assert requires_owner_approval("deploy", "low") is True
