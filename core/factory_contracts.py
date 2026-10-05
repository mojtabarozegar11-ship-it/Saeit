"""Strict intent and output contracts for the existing Factory task pipeline."""
from dataclasses import dataclass
import hashlib
import json


OUTPUT_KEYS = {
    "product_research": {"title", "sources", "product_type", "currency", "market", "evidence", "research_project_id", "research_report_id", "research_provider", "real_research", "research_plan"},
    "product_opportunity_score": {"score", "rationale", "rubric", "status"},
    "product_validation": {"validation"},
    "product_spec": {"spec"},
    "product_build_record": {"artifact"},
    "product_test": {"tests"},
    "product_security": {"security"},
    "product_localize": {"localization"},
    "product_market_eligibility": {"markets"},
    "product_qa": {"qa"},
    "product_launch_candidate": {"launch_candidate"},
}
INTENT_KEYS = {"goal", "run_id", "product_id", "constraints"}
OUTPUT_INTENT_NAMES = {"sources", "score", "spec", "artifact", "tests", "security", "evidence"}
REQUIRED_OUTPUT_KEYS = {
    "product_research": ["title", "sources"],
    "product_opportunity_score": ["score", "rationale", "rubric"],
    "product_validation": ["validation"],
    "product_spec": ["spec"],
    "product_build_record": ["artifact"],
    "product_test": ["tests"],
    "product_security": ["security"],
    "product_localize": ["localization"],
    "product_market_eligibility": ["markets"],
    "product_qa": ["qa"],
    "product_launch_candidate": ["launch_candidate"],
}
EXPECTED_OUTPUT_STATE = {
    "product_research": "researched",
    "product_opportunity_score": "scored",
    "product_validation": "validated",
    "product_spec": "specified",
    "product_build_record": "built",
    "product_test": "tested",
    "product_security": "security_verified",
    "product_localize": "localized",
    "product_market_eligibility": "eligible",
    "product_qa": "qa_passed",
    "product_launch_candidate": "launch_candidate",
}


class FactoryContractError(ValueError):
    pass


def _walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child)


def validate_task_intent(value):
    if not isinstance(value, dict) or set(value) - INTENT_KEYS:
        raise FactoryContractError("Factory Task accepts only goal, run_id, product_id, and constraints intent.")
    for key in _walk(value):
        if key.startswith("__") or key in OUTPUT_INTENT_NAMES:
            raise FactoryContractError(f"Factory Task intent contains output-only field: {key}")
    if not isinstance(value.get("goal"), str) or not value["goal"].strip():
        raise FactoryContractError("Factory Task intent requires a non-empty goal.")
    return value


@dataclass(frozen=True)
class GatewayAuthorization:
    task_id: int
    agent_id: int
    execution_id: str
    tool_code: str
    resource: str
    environment: str
    prerequisite_digest: str
    nonce: object


@dataclass(frozen=True)
class GatewayAdapterReceipt:
    """One-use proof that the registered FactoryAgentRuntime produced output."""
    task_id: int
    agent_id: int
    execution_id: str
    action: str
    resource: str
    environment: str
    prerequisite_digest: str
    output_digest: str
    values: dict
    nonce: object


@dataclass(frozen=True)
class GatewayInvocation:
    task_id: int
    execution_id: str
    tool_code: str
    nonce: object


@dataclass(frozen=True)
class GatewayToolAttestation:
    task_id: int
    execution_id: str
    tool_code: str
    nonce: object


@dataclass(frozen=True)
class GatewayToolResult:
    result: object
    attestation: GatewayToolAttestation


def canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class FactoryAgentOutput:
    action: str
    values: dict

    @classmethod
    def validate(cls, action, values):
        allowed = OUTPUT_KEYS.get(action)
        if allowed is None or not isinstance(values, dict):
            raise FactoryContractError("No typed Factory output contract is registered for this action.")
        if set(values) - allowed:
            raise FactoryContractError("Factory Agent output contains fields outside its action contract.")
        required = set(REQUIRED_OUTPUT_KEYS[action])
        if not required.issubset(values):
            raise FactoryContractError("Factory Agent output is missing required action fields.")
        return cls(action=action, values=dict(values))
