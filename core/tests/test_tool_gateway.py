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
