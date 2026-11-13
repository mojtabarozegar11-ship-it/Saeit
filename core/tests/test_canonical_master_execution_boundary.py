"""Master economic capability authority at planning, claim and tool invocation.

These are database-only tests: no network, external orders or live runtime calls.
"""
import pytest
from django.core.exceptions import ImproperlyConfigured

from core.agent_registry import AgentRegistry
from core.canonical_bot_identity import RUNTIME_CODES, is_master_only_action
from core.models import Agent, AgentCapability, AgentTask, AuditLog
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec

pytestmark = pytest.mark.django_db
ACTION = "income_mojtrade_forward_audit"


@pytest.fixture
def capability(db):
    Agent.objects.filter(code__in=RUNTIME_CODES).delete()
    cap, _ = AgentCapability.objects.update_or_create(
        code=ACTION,
        defaults={"name": "Private research model", "risk_level": "low", "active": True},
    )
    return cap


def agent(code, cap, *, active=True):
    instance = Agent.objects.create(
        code=code, name=code, mission="No live orders", active=active,
        risk_level="low",
    )
    instance.capabilities.add(cap)
    return instance


def task_for(owner, *, status="queued", action=ACTION, capability_code=ACTION):
    return AgentTask.objects.create(
        agent=owner, action_type=action, capability_code=capability_code,
        risk_snapshot="low", status=status, execution_id="master-boundary-test",
        attempt_count=0,
    )


def test_master_action_classifier_does_not_claim_unrelated_capabilities():
    assert is_master_only_action(ACTION)
    assert is_master_only_action("master_self_improvement")
    assert not is_master_only_action("factory_f41_private_build")
    assert not is_master_only_action("research")
    assert not is_master_only_action("incomes")


def test_registry_prefers_sole_legacy_runtime_over_specialist(capability):
    specialist = agent("unrelated-specialist", capability)
    master = agent("economic-master-agent", capability)
    assert AgentRegistry().resolve(ACTION) == master
    assert AgentRegistry().resolve(ACTION) != specialist


def test_registry_prefers_canonical_after_handoff(capability):
    old = agent("economic-master-agent", capability, active=False)
    current = agent("mojtaba-bot-ai", capability)
    agent("unrelated-specialist", capability)
    assert AgentRegistry().resolve(ACTION) == current
    assert old.active is False


def test_registry_refuses_master_action_when_no_master_exists(capability):
    agent("unrelated-specialist", capability)
    assert AgentRegistry().resolve(ACTION) is None


def test_registry_parallel_master_rows_fail_closed(capability):
    agent("economic-master-agent", capability)
    agent("mojtaba-bot-ai", capability)
    with pytest.raises(ImproperlyConfigured, match="CANONICAL_BOT_MULTIPLE_ACTIVE"):
        AgentRegistry().resolve(ACTION)


def test_task_claim_rejects_nonmaster_even_if_capability_was_granted(capability):
    agent("economic-master-agent", capability)
    imposter = agent("unrelated-specialist", capability)
    task = task_for(imposter)
    before = AuditLog.objects.count()
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_NOT_OWNED_BY_ACTIVE_RUNTIME"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0
    assert AuditLog.objects.count() == before


def test_task_claim_allows_current_canonical_runtime(capability):
    agent("economic-master-agent", capability, active=False)
    master = agent("mojtaba-bot-ai", capability)
    task = task_for(master)
    claimed = TaskRuntime().claim(task.pk)
    assert claimed.agent_id == master.pk
    assert claimed.status == "running"
    assert claimed.attempt_count == 1


def test_task_claim_fails_closed_for_parallel_masters_without_attempt(capability):
    old = agent("economic-master-agent", capability)
    agent("mojtaba-bot-ai", capability)
    task = task_for(old)
    before = AuditLog.objects.count()
    with pytest.raises(TaskExecutionError, match="MASTER_TASK_MULTIPLE_ACTIVE_RUNTIMES"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0
    assert AuditLog.objects.count() == before


def test_direct_tool_invocation_cannot_impersonate_master(capability):
    agent("economic-master-agent", capability)
    imposter = agent("unrelated-specialist", capability)
    task = task_for(imposter, status="running")
    calls = []
    gateway = ToolGateway([ToolSpec(
        code=ACTION, handler=lambda data: calls.append(data), risk="low",
    )])
    before = AuditLog.objects.count()
    with pytest.raises(ToolGatewayError, match="MASTER_GATEWAY_NONCANONICAL_AGENT_BLOCKED"):
        gateway.invoke(ACTION, {}, task_id=task.pk, execution_id=task.execution_id)
    assert calls == []
    assert AuditLog.objects.count() == before


def test_direct_gateway_rejects_master_tool_smuggled_through_alias(capability):
    agent("economic-master-agent", capability)
    specialist = agent("unrelated-specialist", capability)
    research, _ = AgentCapability.objects.update_or_create(
        code="research", defaults={"name": "Research", "risk_level": "low", "active": True},
    )
    specialist.capabilities.add(research)
    task = task_for(specialist, status="running", action="research",
                    capability_code="research")
    calls = []
    gateway = ToolGateway([ToolSpec(
        code=ACTION, allowed_actions=("research",),
        handler=lambda payload: calls.append(payload), risk="low",
    )])
    with pytest.raises(ToolGatewayError, match="MASTER_GATEWAY_NONCANONICAL_AGENT_BLOCKED"):
        gateway.invoke(ACTION, {}, task_id=task.pk, execution_id=task.execution_id)
    assert calls == []


def test_direct_gateway_allows_canonical_runtime_with_legitimate_capability(capability):
    agent("economic-master-agent", capability, active=False)
    master = agent("mojtaba-bot-ai", capability)
    task = task_for(master, status="running")
    gateway = ToolGateway([ToolSpec(
        code=ACTION, handler=lambda data: {"private_only": True}, risk="low",
    )])
    assert gateway.invoke(ACTION, {}, task_id=task.pk,
                          execution_id=task.execution_id) == {"private_only": True}


def test_direct_gateway_parallel_identity_fails_before_handler_or_audit(capability):
    old = agent("economic-master-agent", capability)
    agent("mojtaba-bot-ai", capability)
    task = task_for(old, status="running")
    invoked = []
    gateway = ToolGateway([ToolSpec(code=ACTION, handler=lambda _: invoked.append(True))])
    before = AuditLog.objects.count()
    with pytest.raises(ToolGatewayError, match="MASTER_GATEWAY_MULTIPLE_ACTIVE_RUNTIMES"):
        gateway.invoke(ACTION, {}, task_id=task.pk, execution_id=task.execution_id)
    assert not invoked
    assert AuditLog.objects.count() == before
