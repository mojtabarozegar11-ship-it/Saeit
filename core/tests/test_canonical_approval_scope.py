"""Approval decisions and claims must not cross action/owner or replay unresolved effects.

Synthetic database-only cases; no provider, production deployment or cash action.
"""
import pytest
from django.contrib.auth import get_user_model

from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, AuditLog, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.unified_bot_identity import BOT_CODE


@pytest.fixture
def protected_task(db):
    owner = get_user_model().objects.create_user(username="scope-primary-owner")
    other = get_user_model().objects.create_user(username="scope-other-owner")
    project = ResearchProject.objects.create(
        title="Scoped authorization", objective="Review only", owner=owner,
    )
    agent = Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", mission="Internal control", active=True,
    )
    capability = AgentCapability.objects.create(
        code="deploy", name="Synthetic sensitive action",
        risk_level="high", active=True,
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="deploy",
        capability_code="deploy", risk_snapshot="high", status="blocked",
    )
    return owner, other, task


def approval_for(task, requested_by, *, action="deploy", status="pending"):
    return ApprovalRequest.objects.create(
        action_type=action, target_type="AgentTask",
        target_id=str(task.pk), requested_by=requested_by,
        reason="Synthetic approval, no external execution",
        risk="high", status=status,
    )


@pytest.mark.parametrize("approved", [True, False])
def test_decision_does_not_release_or_cancel_task_for_unrelated_action(
    protected_task, approved,
):
    owner, _, task = protected_task
    request = approval_for(task, owner, action="publish")
    with pytest.raises(ValueError, match="action does not match"):
        ApprovalService().decide(request.pk, approved, actor_id=owner.pk)
    request.refresh_from_db()
    task.refresh_from_db()
    assert request.status == "pending"
    assert task.status == "blocked"
    assert not AuditLog.objects.filter(
        action="approval_decision", target_id=str(request.pk),
    ).exists()


@pytest.mark.parametrize("approved", [True, False])
def test_decision_cannot_override_project_owner(protected_task, approved):
    _, other, task = protected_task
    request = approval_for(task, other)
    with pytest.raises(ValueError, match="project owner"):
        ApprovalService().decide(request.pk, approved, actor_id=other.pk)
    request.refresh_from_db()
    task.refresh_from_db()
    assert request.status == "pending"
    assert task.status == "blocked"


@pytest.mark.parametrize("marker", [
    {"requires_review": True, "automatic_replay_allowed": False},
    {"automatic_replay_allowed": False},
])
def test_ordinary_approval_cannot_requeue_unreconciled_canonical_effect(
    protected_task, marker,
):
    owner, _, task = protected_task
    task.output_data = {**marker, "previous_execution_id": "unknown-effect"}
    task.execution_id = "unknown-effect"
    task.attempt_count = 1
    task.save(update_fields=["output_data", "execution_id", "attempt_count"])
    request = approval_for(task, owner)
    with pytest.raises(ValueError, match="external-effect reconciliation"):
        ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    request.refresh_from_db()
    task.refresh_from_db()
    assert request.status == "pending"
    assert task.status == "blocked"
    assert task.execution_id == "unknown-effect"
    assert task.output_data["automatic_replay_allowed"] is False


def test_rejected_request_retains_canonical_unknown_effect_for_reconciliation(
    protected_task,
):
    owner, _, task = protected_task
    task.output_data = {
        "requires_review": True,
        "automatic_replay_allowed": False,
        "previous_execution_id": "prior-effect",
    }
    task.save(update_fields=["output_data"])
    request = approval_for(task, owner)
    decided = ApprovalService().decide(
        request.pk, False, actor_id=owner.pk,
        note="Decline new authorization; preserve incident",
    )
    task.refresh_from_db()
    assert decided.status == "rejected"
    assert task.status == "blocked"
    assert task.output_data["previous_execution_id"] == "prior-effect"


def test_normal_clean_approval_still_releases_pre_execution_block(protected_task):
    owner, _, task = protected_task
    request = approval_for(task, owner)
    approved = ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    task.refresh_from_db()
    assert approved.status == "approved"
    assert task.status == "queued"
    claimed = TaskRuntime().claim(task.pk)
    assert claimed.status == "running"
    assert claimed.attempt_count == 1


@pytest.mark.parametrize("kind", ["wrong_action", "wrong_owner"])
def test_task_claim_requires_approved_exact_action_and_project_owner(
    protected_task, kind,
):
    owner, other, task = protected_task
    task.status = "queued"
    task.save(update_fields=["status"])
    if kind == "wrong_action":
        approval_for(task, owner, action="publish", status="approved")
    else:
        approval_for(task, other, status="approved")
    with pytest.raises(TaskExecutionError, match="Matching owner approval"):
        TaskRuntime().claim(task.pk)
    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0
    assert task.execution_id == ""
    assert not AuditLog.objects.filter(
        action="task_claimed", target_id=str(task.pk),
    ).exists()
