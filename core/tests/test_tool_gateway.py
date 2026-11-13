import pytest
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, ResearchProject
from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec


@pytest.fixture
def running_task(db):
    user = get_user_model().objects.create_user(
        username="tool-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Tool test", objective="Validate gateway", owner=user
    )
    agent = Agent.objects.create(
        code="research-agent",
        name="Research Agent",
        mission="Execute research",
        risk_level="low",
        active=True,
    )
    AgentCapability.objects.create(
        code="research",
        name="Research",
        risk_level="low",
        active=True,
    ).agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="research",
        capability_code="research",
        risk_snapshot="low",
        status="running",
        execution_id="exec-123",
        attempt_count=1,
    )
    return task


def test_gateway_invokes_registered_tool(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: {"echo": payload["q"]}),
    ])

    assert gateway.invoke(
        "research", {"q": "wheat"},
        task_id=running_task.pk,
        execution_id="exec-123",
    ) == {"echo": "wheat"}


def test_gateway_rejects_unknown_tool(running_task):
    gateway = ToolGateway()

    with pytest.raises(ToolGatewayError, match="not registered"):
        gateway.invoke("research", {}, task_id=running_task.pk, execution_id="exec-123")


def test_gateway_requires_approval_for_sensitive_tool(running_task):
    AgentCapability.objects.create(
        code="deploy", name="Deployment", risk_level="high", active=True,
    ).agents.add(running_task.agent)
    running_task.action_type = "deploy"
    running_task.capability_code = "deploy"
    running_task.risk_snapshot = "high"
    running_task.save(update_fields=["action_type", "capability_code", "risk_snapshot"])
    gateway = ToolGateway([
        ToolSpec(code="deploy", handler=lambda payload: {"ok": True}, risk="high"),
    ])

    with pytest.raises(ToolGatewayError, match="approval"):
        gateway.invoke(
            "deploy", {}, task_id=running_task.pk, execution_id="exec-123"
        )

    ApprovalRequest.objects.create(
        action_type="deploy",
        target_type="AgentTask",
        target_id=str(running_task.pk),
        reason="Approved deployment test",
        risk="high",
        status="approved",
        requested_by=running_task.project.owner,
    )

    assert gateway.invoke(
        "deploy", {}, task_id=running_task.pk, execution_id="exec-123"
    ) == {"ok": True}


def test_gateway_denies_cross_capability_tool_even_with_an_approval(running_task):
    calls = []
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", handler=lambda data: calls.append(data)),
    ])
    ApprovalRequest.objects.create(
        action_type="deploy", target_type="AgentTask",
        target_id=str(running_task.pk), reason="Wrong action approval",
        risk="high", status="approved", requested_by=running_task.project.owner,
    )
    with pytest.raises(ToolGatewayError, match="not authorized"):
        gateway.invoke("deploy", {}, task_id=running_task.pk, execution_id="exec-123")
    assert calls == []


def test_gateway_denies_inactive_agent_and_revoked_capability(running_task):
    gateway = ToolGateway([ToolSpec(code="research", handler=lambda data: data)])
    running_task.agent.active = False
    running_task.agent.save(update_fields=["active"])
    with pytest.raises(ToolGatewayError, match="inactive"):
        gateway.invoke("research", {}, task_id=running_task.pk, execution_id="exec-123")
    running_task.agent.active = True
    running_task.agent.save(update_fields=["active"])
    running_task.agent.capabilities.clear()
    with pytest.raises(ToolGatewayError, match="revoked"):
        gateway.invoke("research", {}, task_id=running_task.pk, execution_id="exec-123")


def test_gateway_requires_explicit_alias_and_updated_risk_snapshot(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research_lookup", handler=lambda data: {"found": True}),
    ])
    with pytest.raises(ToolGatewayError, match="not authorized"):
        gateway.invoke("research_lookup", {}, task_id=running_task.pk, execution_id="exec-123")
    mapped = ToolGateway([
        ToolSpec(code="research_lookup", allowed_actions=("research",),
                 handler=lambda data: {"found": True}),
    ])
    assert mapped.invoke("research_lookup", {}, task_id=running_task.pk, execution_id="exec-123") == {"found": True}
    AgentCapability.objects.filter(code="research").update(risk_level="high")
    with pytest.raises(ToolGatewayError, match="risk policy changed"):
        mapped.invoke("research_lookup", {}, task_id=running_task.pk, execution_id="exec-123")


def test_gateway_refuses_high_risk_alias_from_low_risk_task(running_task):
    gateway = ToolGateway([
        ToolSpec(code="deploy", risk="high", allowed_actions=("research",),
                 handler=lambda data: {"bad": "executed"}),
    ])
    with pytest.raises(ToolGatewayError, match="risk exceeds"):
        gateway.invoke("deploy", {}, task_id=running_task.pk, execution_id="exec-123")


def test_gateway_rejects_missing_execution_context(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: payload),
    ])

    with pytest.raises(ToolGatewayError, match="running task"):
        gateway.invoke("research", {"q": "wheat"})


def test_gateway_rejects_stale_execution_identity(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: payload),
    ])

    with pytest.raises(ToolGatewayError, match="Execution identity"):
        gateway.invoke(
            "research", {"q": "wheat"},
            task_id=running_task.pk,
            execution_id="stale-execution",
        )


def test_gateway_rejects_invalid_payload(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: payload),
    ])

    with pytest.raises(ToolGatewayError, match="payload"):
        gateway.invoke(
            "research", ["invalid"],
            task_id=running_task.pk,
            execution_id="exec-123",
        )


def test_gateway_audits_successful_invocation(running_task):
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda payload: {"ok": True}),
    ])

    gateway.invoke(
        "research", {},
        task_id=running_task.pk,
        execution_id="exec-123",
    )

    from core.models import AuditLog
    actions = list(
        AuditLog.objects.filter(target_id=str(running_task.pk))
        .values_list("action", flat=True)
    )
    assert "tool_invocation_started" in actions
    assert "tool_invocation_completed" in actions


def test_gateway_audits_failed_invocation(running_task):
    def explode(payload):
        raise RuntimeError("tool failure")

    gateway = ToolGateway([ToolSpec(code="research", handler=explode)])

    with pytest.raises(RuntimeError, match="tool failure"):
        gateway.invoke(
            "research", {},
            task_id=running_task.pk,
            execution_id="exec-123",
        )

    from core.models import AuditLog
    assert AuditLog.objects.filter(
        target_id=str(running_task.pk),
        action="tool_invocation_failed",
    ).exists()



def test_gateway_reserves_one_call_even_while_task_remains_running(running_task):
    """One execution token authorizes one dispatch, not repeated provider calls."""
    from core.models import AuditLog

    calls = []
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda p: calls.append(p) or {"ok": True}),
    ])
    assert gateway.invoke(
        "research", {"request": "first"},
        task_id=running_task.pk, execution_id="exec-123",
    ) == {"ok": True}
    with pytest.raises(ToolGatewayError, match="already reserved"):
        gateway.invoke(
            "research", {"request": "duplicate"},
            task_id=running_task.pk, execution_id="exec-123",
        )
    assert calls == [{"request": "first"}]
    assert AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(running_task.pk),
        action="tool_invocation_started",
    ).count() == 1
    assert AuditLog.objects.filter(
        target_type="AgentTask", target_id=str(running_task.pk),
        action="tool_invocation_completed",
    ).count() == 1


def test_gateway_lost_acknowledgement_reservation_survives_handler_error(running_task):
    from core.models import AuditLog

    calls = []

    def no_receipt(payload):
        calls.append(payload)
        raise RuntimeError("provider acknowledgement lost")

    gateway = ToolGateway([ToolSpec(code="research", handler=no_receipt)])
    with pytest.raises(RuntimeError, match="acknowledgement lost"):
        gateway.invoke(
            "research", {"request": 1},
            task_id=running_task.pk, execution_id="exec-123",
        )
    with pytest.raises(ToolGatewayError, match="receipt reconciliation"):
        gateway.invoke(
            "research", {"request": 2},
            task_id=running_task.pk, execution_id="exec-123",
        )
    assert len(calls) == 1
    assert AuditLog.objects.filter(
        target_id=str(running_task.pk), action="tool_invocation_started",
    ).count() == 1
    assert AuditLog.objects.filter(
        target_id=str(running_task.pk), action="tool_invocation_failed",
    ).count() == 1


def test_gateway_second_alias_cannot_bypass_single_dispatch_reservation(running_task):
    calls = []
    gateway = ToolGateway([
        ToolSpec(
            code="research_lookup", allowed_actions=("research",),
            handler=lambda p: calls.append("alias") or {"ok": True},
        ),
        ToolSpec(
            code="research", handler=lambda p: calls.append("direct") or {"ok": True},
        ),
    ])
    gateway.invoke(
        "research_lookup", {}, task_id=running_task.pk,
        execution_id="exec-123",
    )
    with pytest.raises(ToolGatewayError, match="already reserved"):
        gateway.invoke(
            "research", {}, task_id=running_task.pk,
            execution_id="exec-123",
        )
    assert calls == ["alias"]


def test_gateway_new_legacy_execution_gets_new_reservation_not_old_token(running_task):
    """An explicitly re-claimed legacy task has a distinct execution token."""
    from core.models import AuditLog
    from core.task_runtime import TaskRuntime

    calls = []
    gateway = ToolGateway([
        ToolSpec(code="research", handler=lambda p: calls.append(p) or {"ok": True}),
    ])
    gateway.invoke("research", {"attempt": 1}, task_id=running_task.pk, execution_id="exec-123")
    runtime = TaskRuntime()
    requeued = runtime.fail(
        running_task.pk, "external receipt unreconciled in legacy fixture",
        execution_id="exec-123",
    )
    assert requeued.status == "queued"
    claimed = runtime.claim(running_task.pk)
    assert claimed.execution_id != "exec-123"
    gateway.invoke(
        "research", {"attempt": 2},
        task_id=running_task.pk, execution_id=claimed.execution_id,
    )
    assert calls == [{"attempt": 1}, {"attempt": 2}]
    assert AuditLog.objects.filter(
        target_id=str(running_task.pk), action="tool_invocation_started",
    ).count() == 2
