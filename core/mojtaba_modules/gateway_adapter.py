"""Inactive-by-default adapters for the existing, audited Django ToolGateway.

These do not create another bot, Agent, task queue, scheduler or API.
A verified operator can *later* register the specs into the existing
canonical-bot gateway after live identity/provenance checks.
"""
from __future__ import annotations

from .cyber_security import (
    CyberModuleError, review_offline_evidence,
)
from .incident_response import plan_incident_response
from .origin_defense import plan_origin_defense

# Importing ToolSpec defines a tool *adapter*, never instantiates a worker.
from core.tool_gateway import ToolSpec

CANONICAL_AGENT_CODE = "mojtaba-bot-ai"
TOOL_ACTIONS = (
    "cyber_evidence_review",
    "cyber_origin_defense",
    "cyber_incident_response",
)


def _validated_payload(data: dict, field: str) -> tuple[dict, dict]:
    """Reject unsolicited secrets and caller-supplied clocks or commands."""
    if not isinstance(data, dict) or set(data) != {"engagement", field}:
        raise CyberModuleError("CANONICAL_GATEWAY_PAYLOAD_INVALID")
    engagement, evidence = data["engagement"], data[field]
    if not isinstance(engagement, dict) or not isinstance(evidence, dict):
        raise CyberModuleError("CANONICAL_GATEWAY_PAYLOAD_INVALID")
    return engagement, evidence


def _periodic_key(key: bytes) -> bool:
    """Reject trivial repeated short-pattern HMAC keys, not estimate entropy."""
    return any(len(key) % n == 0 and key == key[:n] * (len(key) // n)
               for n in range(1, min(8, len(key) - 1) + 1))


def build_cyber_gateway_tools(verify_key: bytes, *, enable_offline: bool = False) -> tuple[ToolSpec, ...]:
    """Provide bound handlers for ToolGateway; disabled by default.

    enable_offline=True is a deployment choice, not proof of written
    client consent. The existing task gate, signed scope, tenant isolation and
    independent provenance checks all remain mandatory.
    """
    if (not isinstance(verify_key, bytes) or len(verify_key) < 32
            or _periodic_key(verify_key)):
        raise CyberModuleError("VERIFIER_KEY_INVALID")
    if type(enable_offline) is not bool:
        raise CyberModuleError("ENABLED_FLAG_INVALID")
    key = bytes(verify_key)

    def review(payload):
        engagement, evidence = _validated_payload(payload, "evidence")
        return review_offline_evidence(
            engagement=engagement, evidence=evidence, verify_key=key,
        )

    def origin(payload):
        engagement, traffic = _validated_payload(payload, "traffic")
        return plan_origin_defense(
            engagement=engagement, traffic=traffic, verify_key=key,
        )

    def incident(payload):
        engagement, incident_data = _validated_payload(payload, "incident")
        return plan_incident_response(
            engagement=engagement, incident=incident_data, verify_key=key,
        )

    return (
        ToolSpec(code="cyber_evidence_review", handler=review, risk="medium",
                 enabled=enable_offline, required_agent_code=CANONICAL_AGENT_CODE),
        ToolSpec(code="cyber_origin_defense", handler=origin, risk="medium",
                 enabled=enable_offline, required_agent_code=CANONICAL_AGENT_CODE),
        ToolSpec(code="cyber_incident_response", handler=incident, risk="medium",
                 enabled=enable_offline, required_agent_code=CANONICAL_AGENT_CODE),
    )
