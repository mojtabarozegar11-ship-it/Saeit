import pytest
from django.contrib.auth import get_user_model
from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, ResearchProject

pytestmark = pytest.mark.django_db


def setup_blocked_task():
    owner = get_user_model().objects.create_user(username="real-owner")
    other = get_user_model().objects.create_user(username="other-user")
    project = ResearchProject.objects.create(title="Approval", objective="Test", owner=owner)
    agent = Agent.objects.create(code="approval-agent", name="Approval Agent", active=True)
    capability = AgentCapability.objects.create(code="publish", name="Publish", risk_level="high")
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="publish", status="blocked"
    )
    approval = ApprovalRequest.objects.create(
        action_type="publish", target_type="AgentTask", target_id=str(task.pk),
        reason="Owner approval required", risk="high", requested_by=owner
    )
    return owner, other, task, approval


def test_non_owner_cannot_decide_as_owner():
    owner, other, _, approval = setup_blocked_task()
    with pytest.raises(ValueError, match="designated owner"):
        ApprovalService().decide(approval.pk, True, actor_id=other.pk, actor_type="owner")
    approval.refresh_from_db()
    assert approval.status == "pending"


def test_owner_approval_releases_only_blocked_task():
    owner, _, task, approval = setup_blocked_task()
    result = ApprovalService().decide(
        approval.pk, True, actor_id=owner.pk, actor_type="owner", note="Approved"
    )
    task.refresh_from_db()
    assert result.status == "approved"
    assert task.status == "queued"


def test_approved_task_cannot_be_released_twice():
    owner, _, task, approval = setup_blocked_task()
    ApprovalService().decide(approval.pk, True, actor_id=owner.pk, actor_type="owner")
    with pytest.raises(ValueError, match="no longer pending"):
        ApprovalService().decide(approval.pk, True, actor_id=owner.pk, actor_type="owner")
