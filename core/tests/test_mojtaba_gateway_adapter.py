"""Database-level verification of the ONE bot's existing ToolGateway boundary."""
import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.mojtaba_modules.cyber_security import CyberModuleError
from core.mojtaba_modules.gateway_adapter import (
    CANONICAL_AGENT_CODE, TOOL_ACTIONS, build_cyber_gateway_tools,
)
from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec


KEY = b"fixture-only-offline-cyber-binding-key-2026-11-13"


def signed_manifest(**changes):
    issued = timezone.now() - timedelta(minutes=3)
    doc = {
        "schema": "mojtaba.bot.ai.cyber.engagement.v1",
        "bot_id": "mojtaba.bot.ai", "module_id": "cyber_security",
        "tenant_id": "approved-customer", "engagement_id": "approved-case",
        "allowed_assets": ["owned.example.com"],
        "mode": "offline_evidence", "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(days=1)).isoformat(),
    }
    doc.update(changes)
    content = json.dumps(doc, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    doc["signature"] = hmac.new(KEY, content, hashlib.sha256).hexdigest()
    return doc


def cyber_evidence():
    return {
        "schema": "mojtaba.bot.ai.cyber.evidence.v1",
        "tenant_id": "approved-customer", "engagement_id": "approved-case",
        "findings": [{
            "finding_id": "f1", "asset_hostname": "owned.example.com",
            "severity": "medium", "title": "Header requires review",
            "evidence_summary": "Offline fixture", "remediation": "Review settings",
        }],
    }


def origin_evidence():
    return {
        "schema": "mojtaba.bot.ai.cyber.origin-defense.v1",
        "tenant_id": "approved-customer", "engagement_id": "approved-case",
        "observations": [],
    }


def incident_evidence():
    return {
        "schema": "mojtaba.bot.ai.cyber.incident-response.v1",
        "tenant_id": "approved-customer", "engagement_id": "approved-case",
        "incident_id": "incident-1", "asset_hostname": "owned.example.com",
        "indicators": [], "backups": [],
    }


@pytest.fixture
def canonical_task(db):
    agent = Agent.objects.create(
        code=CANONICAL_AGENT_CODE,
        name="Canonical Mojtaba bot fixture",
        mission="Authorized internal offline modules only",
        risk_level="medium", active=True,
    )
    for action in TOOL_ACTIONS:
        AgentCapability.objects.create(
            code=action, name=action, risk_level="medium", active=True,
        ).agents.add(agent)
    return AgentTask.objects.create(
        agent=agent, action_type="cyber_evidence_review",
        capability_code="cyber_evidence_review",
        risk_snapshot="medium", status="running",
        execution_id="canonical-execution", attempt_count=1,
    )


def invoke(task, gateway, action, payload):
    return gateway.invoke(
        action, payload, task_id=task.pk, execution_id=task.execution_id,
    )


def test_adapter_registers_no_agent_or_worker(db):
    before = Agent.objects.count()
    specs = build_cyber_gateway_tools(KEY)
    assert Agent.objects.count() == before
    assert len(specs) == 3
    assert {spec.required_agent_code for spec in specs} == {CANONICAL_AGENT_CODE}
    assert not any(spec.enabled for spec in specs)


def test_adapter_disabled_by_default(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY))
    assert not gateway.describe()["cyber_evidence_review"]["enabled"]
    with pytest.raises(ToolGatewayError, match="disabled"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": cyber_evidence()})


def test_trusted_canonical_task_can_review_precollected_evidence(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    result = invoke(canonical_task, gateway, "cyber_evidence_review",
                    {"engagement": signed_manifest(), "evidence": cyber_evidence()})
    assert result["bot_id"] == "mojtaba.bot.ai"
    assert result["module_id"] == "cyber_security"
    assert result["counts"]["medium"] == 1
    assert AuditLog.objects.filter(action="tool_invocation_completed",
                                   target_id=str(canonical_task.pk)).exists()


@pytest.mark.parametrize("action,field,evidence,submodule", [
    ("cyber_origin_defense", "traffic", origin_evidence, "origin_defense"),
    ("cyber_incident_response", "incident", incident_evidence, "incident_response"),
])
def test_nested_defensive_functions_through_existing_gateway(
    canonical_task, action, field, evidence, submodule,
):
    canonical_task.action_type = action
    canonical_task.capability_code = action
    canonical_task.save(update_fields=["action_type", "capability_code"])
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    result = invoke(canonical_task, gateway, action,
                    {"engagement": signed_manifest(), field: evidence()})
    assert result["submodule_id"] == submodule
    assert result["bot_id"] == "mojtaba.bot.ai"
    assert result.get("executed_actions", 0) == 0


def test_other_agent_cannot_use_same_capability(canonical_task):
    outsider = Agent.objects.create(
        code="another-agent", name="Not the canonical bot",
        mission="No cyber access", active=True,
    )
    outsider.capabilities.add(AgentCapability.objects.get(code="cyber_evidence_review"))
    canonical_task.agent = outsider
    canonical_task.save(update_fields=["agent"])
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    with pytest.raises(ToolGatewayError, match="canonical agent"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": cyber_evidence()})


def test_revoked_capability_cannot_invoke(canonical_task):
    canonical_task.agent.capabilities.clear()
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    with pytest.raises(ToolGatewayError, match="revoked"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": cyber_evidence()})


def test_payload_does_not_accept_injected_key_or_clock(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    with pytest.raises(CyberModuleError, match="PAYLOAD_INVALID"):
        invoke(canonical_task, gateway, "cyber_evidence_review", {
            "engagement": signed_manifest(), "evidence": cyber_evidence(),
            "verify_key": "injected", "now": "2099-01-01T00:00:00Z",
        })


def test_wrong_tenant_evidence_fail_closed(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    bad = cyber_evidence()
    bad["tenant_id"] = "another-customer"
    with pytest.raises(CyberModuleError, match="CROSS_TENANT"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": bad})


def test_tampered_scope_signature_rejected(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    grant = signed_manifest()
    grant["allowed_assets"] = ["unapproved.example.com"]
    with pytest.raises(CyberModuleError, match="SIGNATURE_INVALID"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": grant, "evidence": cyber_evidence()})


def test_queued_task_cannot_invoke(canonical_task):
    canonical_task.status = "queued"
    canonical_task.save(update_fields=["status"])
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    with pytest.raises(ToolGatewayError, match="running task"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": cyber_evidence()})


def test_low_risk_snapshot_rejected_for_medium_capability(canonical_task):
    canonical_task.risk_snapshot = "low"
    canonical_task.save(update_fields=["risk_snapshot"])
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    with pytest.raises(ToolGatewayError, match="risk policy changed"):
        invoke(canonical_task, gateway, "cyber_evidence_review",
               {"engagement": signed_manifest(), "evidence": cyber_evidence()})


def test_empty_or_short_signing_key_rejected():
    with pytest.raises(CyberModuleError, match="VERIFIER_KEY_INVALID"):
        build_cyber_gateway_tools(b"tiny", enable_offline=True)


def test_non_boolean_activation_rejected():
    with pytest.raises(CyberModuleError, match="ENABLED_FLAG_INVALID"):
        build_cyber_gateway_tools(KEY, enable_offline="true")


def test_generic_gateway_rejects_nonexact_spec_agent_code():
    with pytest.raises(ToolGatewayError, match="exact"):
        ToolGateway([ToolSpec(
            code="restricted", handler=lambda payload: payload,
            required_agent_code=" another-agent ",
        )])


def test_no_unneeded_authorization_details_leak_to_audit(canonical_task):
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    grant = signed_manifest()
    invoke(canonical_task, gateway, "cyber_evidence_review",
           {"engagement": grant, "evidence": cyber_evidence()})
    logs = list(AuditLog.objects.filter(target_id=str(canonical_task.pk)))
    assert logs
    assert not any(grant["signature"] in json.dumps(log.after_state) for log in logs)
