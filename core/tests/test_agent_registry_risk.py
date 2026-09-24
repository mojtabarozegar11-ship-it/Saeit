import pytest
from types import SimpleNamespace

from core.agent_registry import AgentRegistry


def test_invalid_capability_risk_is_not_downgraded():
    capability = SimpleNamespace(risk_level="unsafe")
    with pytest.raises(ValueError, match="Invalid risk level"):
        AgentRegistry().effective_risk(capability, "low")


def test_effective_risk_keeps_highest_valid_level():
    capability = SimpleNamespace(risk_level="high")
    assert AgentRegistry().effective_risk(capability, "low") == "high"
