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


def test_constant_byte_verifier_key_rejected():
    """Long but predictable keys must not authorize tenant-scoped actions."""
    with pytest.raises(CyberModuleError, match="VERIFIER_KEY_INVALID"):
        build_cyber_gateway_tools(b"\\x00" * 32, enable_offline=True)
    with pytest.raises(CyberModuleError, match="VERIFIER_KEY_INVALID"):
        build_cyber_gateway_tools(b"A" * 64, enable_offline=True)


def test_short_period_repeated_verifier_keys_rejected():
    """Two- through eight-byte periodic keys are not acceptable HMAC secrets."""
    for pattern in (b"AB", b"ABC", b"ABCDEFGH"):
        key = pattern * (48 // len(pattern))
        with pytest.raises(CyberModuleError, match="VERIFIER_KEY_INVALID"):
            build_cyber_gateway_tools(key, enable_offline=True)


def test_genuine_nonperiodic_verifier_key_accepted():
    assert len(build_cyber_gateway_tools(KEY)) == 3


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


# Full, database-backed lifecycle proves the cyber module can reuse the
# EXISTING MasterAgent/TaskRuntime/WorkerRunner and doesn't need a second worker.
from django.contrib.auth import get_user_model
from core.models import ResearchProject
from core.orchestrator import MasterAgent
from core.agent_registry import AgentRegistry
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.worker_runner import WorkerRunner


@pytest.fixture
def cyber_planning(db):
    owner = get_user_model().objects.create_user(
        username="cyber-planning-owner", password="unused-local-test-only",
    )
    project = ResearchProject.objects.create(
        title="Cyber review fixture", objective="Authorized offline evidence",
        owner=owner,
    )
    canonical = Agent.objects.create(
        code=CANONICAL_AGENT_CODE,
        name="Mojtaba.bot.ai", mission="One canonical runtime",
        active=True, risk_level="medium",
    )
    for action in TOOL_ACTIONS:
        AgentCapability.objects.create(
            code=action, name=action, risk_level="medium", active=True,
        ).agents.add(canonical)
    return project, canonical


def _plan_cyber(project, action="cyber_evidence_review", payload=None):
    if payload is None:
        payload = {"engagement": signed_manifest(), "evidence": cyber_evidence()}
    return MasterAgent().plan(project, action, payload, risk="medium")


def test_full_canonical_lifecycle_from_planning_to_audit(cyber_planning):
    project, canonical = cyber_planning
    initial_agents = Agent.objects.count()
    task = _plan_cyber(project)
    assert task.status == "queued"
    assert task.agent_id == canonical.pk
    assert task.risk_snapshot == "medium"
    gateway = ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    result = WorkerRunner(gateway).run(task.pk)
    assert result.status == "completed"
    assert result.output_data["bot_id"] == "mojtaba.bot.ai"
    assert result.output_data["counts"]["medium"] == 1
    assert result.cost == 0  # Decimal("0") is a zero-cost offline operation
    assert Agent.objects.count() == initial_agents
    events = set(AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(task.pk),
    ).values_list("action", flat=True))
    assert {"task_claimed", "tool_invocation_started",
            "tool_invocation_completed", "task_completed"}.issubset(events)


@pytest.mark.parametrize("action,field,fixture,expected", [
    ("cyber_origin_defense", "traffic", origin_evidence, "origin_defense"),
    ("cyber_incident_response", "incident", incident_evidence, "incident_response"),
])
def test_nested_cyber_workflows_use_same_worker(
    cyber_planning, action, field, fixture, expected,
):
    project, canonical = cyber_planning
    task = _plan_cyber(project, action, {
        "engagement": signed_manifest(), field: fixture(),
    })
    output = WorkerRunner(
        ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
    ).run(task.pk).output_data
    assert task.agent_id == canonical.pk
    assert output["submodule_id"] == expected
    assert output["bot_id"] == "mojtaba.bot.ai"


def test_agent_selection_ignores_noncanonical_lower_risk_peer(cyber_planning):
    project, canonical = cyber_planning
    peer = Agent.objects.create(
        code="independent-security-bot", name="Forbidden parallel agent",
        mission="Must not receive cyber task", active=True, risk_level="low",
    )
    for action in TOOL_ACTIONS:
        AgentCapability.objects.get(code=action).agents.add(peer)
    task = _plan_cyber(project)
    assert task.agent_id == canonical.pk
    assert AgentRegistry().capability_for(peer, "cyber_evidence_review") is None


def test_no_canonical_agent_means_no_task_instead_of_rogue_dispatch(
    cyber_planning,
):
    project, canonical = cyber_planning
    peer = Agent.objects.create(
        code="independent-security-bot", name="Forbidden parallel agent",
        mission="Do not dispatch", active=True, risk_level="low",
    )
    AgentCapability.objects.get(
        code="cyber_evidence_review"
    ).agents.add(peer)
    canonical.active = False
    canonical.save(update_fields=["active"])
    with pytest.raises(RuntimeError, match="No active agent"):
        _plan_cyber(project)
    assert AgentTask.objects.count() == 0


def test_noncanonical_queued_task_cannot_be_claimed(cyber_planning):
    project, _ = cyber_planning
    peer = Agent.objects.create(
        code="independent-security-bot", name="Peer fixture",
        mission="Wrong actor", active=True, risk_level="low",
    )
    AgentCapability.objects.get(
        code="cyber_evidence_review"
    ).agents.add(peer)
    forged = AgentTask.objects.create(
        agent=peer, project=project, action_type="cyber_evidence_review",
        capability_code="cyber_evidence_review", risk_snapshot="medium",
        status="queued", input_data={
            "engagement": signed_manifest(), "evidence": cyber_evidence(),
        },
    )
    with pytest.raises(TaskExecutionError, match="no longer has"):
        TaskRuntime().claim(forged.pk)
    forged.refresh_from_db()
    assert forged.status == "queued"


def test_automated_worker_remains_off_when_not_approved(cyber_planning):
    project, _ = cyber_planning
    task = _plan_cyber(project)
    disabled = ToolGateway(build_cyber_gateway_tools(KEY))
    with pytest.raises(ToolGatewayError, match="disabled"):
        WorkerRunner(disabled).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert not AuditLog.objects.filter(
        target_id=str(task.pk), action="tool_invocation_completed",
    ).exists()


def test_invalid_signed_scope_fails_without_completed_task(cyber_planning):
    project, _ = cyber_planning
    forged = signed_manifest()
    forged["allowed_assets"] = ["wrong.example.com"]
    task = _plan_cyber(project, payload={
        "engagement": forged, "evidence": cyber_evidence(),
    })
    with pytest.raises(CyberModuleError, match="SIGNATURE_INVALID"):
        WorkerRunner(
            ToolGateway(build_cyber_gateway_tools(KEY, enable_offline=True))
        ).run(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert not AuditLog.objects.filter(
        target_id=str(task.pk), action="tool_invocation_completed",
    ).exists()


def test_cyber_core_alias_cannot_route_to_other_agent(cyber_planning):
    project, _ = cyber_planning
    outsider = Agent.objects.create(
        code="parallel-cyber-agent", name="Unapproved identity",
        mission="Should not receive any cyber task", risk_level="low", active=True,
    )
    cap = AgentCapability.objects.create(
        code="core_cyber_evidence_review", name="Forbidden alias",
        risk_level="low", active=True,
    )
    cap.agents.add(outsider)
    assert AgentRegistry().resolve("core_cyber_evidence_review") is None
    assert AgentRegistry().capability_for(outsider, "core_cyber_evidence_review") is None
    with pytest.raises(RuntimeError, match="No active agent"):
        _plan_cyber(project, "core_cyber_evidence_review")
    assert AgentTask.objects.count() == 0


def test_unknown_cyber_namespace_cannot_be_self_registered(cyber_planning):
    project, canonical = cyber_planning
    cap = AgentCapability.objects.create(
        code="cyber_unreviewed_new_action", name="Unreviewed cyber action",
        risk_level="medium", active=True,
    )
    cap.agents.add(canonical)
    assert AgentRegistry().resolve("cyber_unreviewed_new_action") is None
    assert AgentRegistry().capability_for(canonical, "cyber_unreviewed_new_action") is None
    with pytest.raises(RuntimeError, match="No active agent"):
        _plan_cyber(project, "cyber_unreviewed_new_action")
    assert AgentTask.objects.count() == 0


def test_cyber_noncanonical_claim_using_core_alias_is_denied(cyber_planning):
    project, _ = cyber_planning
    outsider = Agent.objects.create(
        code="parallel-cyber-agent", name="Unapproved identity",
        mission="Must not claim", risk_level="low", active=True,
    )
    cap = AgentCapability.objects.create(
        code="core_cyber_evidence_review", name="Unapproved alias",
        risk_level="medium", active=True,
    )
    cap.agents.add(outsider)
    task = AgentTask.objects.create(
        agent=outsider, project=project,
        action_type="core_cyber_evidence_review",
        capability_code="core_cyber_evidence_review", risk_snapshot="medium",
        status="queued",
    )
    with pytest.raises(TaskExecutionError, match="no longer has"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"


def test_cyber_canonical_original_actions_still_route(cyber_planning):
    _, canonical = cyber_planning
    for action in TOOL_ACTIONS:
        assert AgentRegistry().resolve(action).pk == canonical.pk
        assert AgentRegistry().capability_for(canonical, action).code == action
