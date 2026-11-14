"""Exact owner-approval scope at decision, task claim and tool invocation.

Uses the isolated Django test database only; no external payments, trading,
deployment or owner actions are performed.
"""
import pytest
from django.contrib.auth import get_user_model

from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, AuditLog
from core.task_approval_scope import approval_covers_task
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.tool_gateway import ToolGateway, ToolGatewayError, ToolSpec

pytestmark = pytest.mark.django_db


@pytest.fixture
def sensitive_task(db):
    owner = get_user_model().objects.create_user(username="scoped-owner", password="unused")
    agent = Agent.objects.create(code="scoped-deploy-agent", name="Private", mission="Only with approval", active=True)
    capability = AgentCapability.objects.create(
        code="deploy", name="Deployment", risk_level="high", active=True,
    )
    agent.capabilities.add(capability)
    task = AgentTask.objects.create(
        agent=agent, action_type="deploy", capability_code="deploy",
        risk_snapshot="high", status="blocked",
    )
    return owner, task


def approval_for(owner, task, *, action="deploy", risk="high", status="pending"):
    return ApprovalRequest.objects.create(
        action_type=action, risk=risk, target_type="AgentTask",
        target_id=str(task.pk), reason="Test-only owner approval",
        status=status, requested_by=owner,
    )


def test_approval_decision_rejects_mismatched_action_without_queuing(sensitive_task):
    owner, task = sensitive_task
    wrong = approval_for(owner, task, action="payment")
    before = AuditLog.objects.count()
    with pytest.raises(ValueError, match="action or risk"):
        ApprovalService().decide(wrong.pk, True, actor_id=owner.pk)
    wrong.refresh_from_db()
    task.refresh_from_db()
    assert wrong.status == "pending"
    assert task.status == "blocked"
    assert AuditLog.objects.count() == before


def test_approval_decision_rejects_lower_risk_without_queuing(sensitive_task):
    owner, task = sensitive_task
    weak = approval_for(owner, task, risk="low")
    with pytest.raises(ValueError, match="action or risk"):
        ApprovalService().decide(weak.pk, True, actor_id=owner.pk)
    weak.refresh_from_db()
    task.refresh_from_db()
    assert weak.status == "pending" and task.status == "blocked"


def test_wrong_action_rejection_cannot_cancel_task(sensitive_task):
    owner, task = sensitive_task
    wrong = approval_for(owner, task, action="delete_data")
    with pytest.raises(ValueError, match="action or risk"):
        ApprovalService().decide(wrong.pk, False, actor_id=owner.pk)
    task.refresh_from_db()
    wrong.refresh_from_db()
    assert task.status == "blocked"
    assert wrong.status == "pending"


def test_high_risk_task_cannot_claim_with_approval_for_another_action(sensitive_task):
    owner, task = sensitive_task
    approval_for(owner, task, action="payment", status="approved")
    task.status = "queued"
    task.save(update_fields=["status"])
    before = AuditLog.objects.count()
    with pytest.raises(TaskExecutionError, match="Owner approval"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0
    assert AuditLog.objects.count() == before


def test_high_risk_task_cannot_claim_with_under_risk_approval(sensitive_task):
    owner, task = sensitive_task
    approval_for(owner, task, risk="low", status="approved")
    task.status = "queued"
    task.save(update_fields=["status"])
    with pytest.raises(TaskExecutionError, match="Owner approval"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.attempt_count == 0 and task.status == "queued"


def test_critical_risk_task_refuses_high_only_approval(sensitive_task):
    owner, task = sensitive_task
    AgentCapability.objects.filter(code="deploy").update(risk_level="critical")
    task.risk_snapshot = "critical"
    task.status = "queued"
    task.save(update_fields=["risk_snapshot", "status"])
    approval_for(owner, task, risk="high", status="approved")
    with pytest.raises(TaskExecutionError, match="Owner approval"):
        TaskRuntime().claim(task.pk)
    assert AgentTask.objects.get(pk=task.pk).attempt_count == 0


def test_gateway_cannot_execute_with_under_risk_approval(sensitive_task):
    owner, task = sensitive_task
    approval_for(owner, task, risk="low", status="approved")
    task.status, task.execution_id, task.attempt_count = "running", "private-run", 1
    task.save(update_fields=["status", "execution_id", "attempt_count"])
    calls = []
    gw = ToolGateway([ToolSpec(code="deploy", risk="high",
                               handler=lambda data: calls.append(data))])
    before = AuditLog.objects.count()
    with pytest.raises(ToolGatewayError, match="Owner approval"):
        gw.invoke("deploy", {}, task_id=task.pk, execution_id="private-run")
    assert not calls
    assert AuditLog.objects.count() == before


def test_valid_scoped_approval_allows_owner_decision_claim_and_tool_gate(sensitive_task):
    owner, task = sensitive_task
    approval = approval_for(owner, task)
    assert approval_covers_task(approval, task)
    approved = ApprovalService().decide(approval.pk, True, actor_id=owner.pk)
    task.refresh_from_db()
    assert approved.status == "approved" and task.status == "queued"
    claimed = TaskRuntime().claim(task.pk)
    called = []
    result = ToolGateway([ToolSpec(
        code="deploy", risk="high",
        handler=lambda data: called.append(data) or {"private_only": True},
    )]).invoke("deploy", {}, task_id=task.pk, execution_id=claimed.execution_id)
    assert result == {"private_only": True}
    assert called == [{}]


def test_invalid_approval_risk_is_treated_as_no_authority(sensitive_task):
    owner, task = sensitive_task
    bad = approval_for(owner, task, risk="not-a-risk", status="approved")
    task.status = "queued"
    task.save(update_fields=["status"])
    assert approval_covers_task(bad, task) is False
    with pytest.raises(TaskExecutionError, match="Owner approval"):
        TaskRuntime().claim(task.pk)


def test_higher_risk_approval_may_cover_lower_risk_task(sensitive_task):
    owner, task = sensitive_task
    approved = approval_for(owner, task, risk="critical", status="approved")
    task.status = "queued"
    task.save(update_fields=["status"])
    assert approval_covers_task(approved, task)
    assert TaskRuntime().claim(task.pk).status == "running"
