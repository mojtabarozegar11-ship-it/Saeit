import pytest
from django.contrib.auth import get_user_model

from core.approval import ApprovalService
from core.models import Agent, AgentCapability, AgentTask, ApprovalRequest, ResearchProject


@pytest.mark.django_db
def test_owner_approval_releases_blocked_task():
    User = get_user_model()
    owner = User.objects.create_user(username="approval-owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Approval", objective="Release", owner=owner)
    agent = Agent.objects.create(code="deploy_agent", name="Deploy", mission="deploy", active=True)
    AgentCapability.objects.create(code="deploy", name="Deploy", risk_level="high", active=True, agents=[agent]) if False else None
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="deploy",
        capability_code="deploy",
        risk_snapshot="high",
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="deploy",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Production deployment requires owner approval",
        risk="high",
        requested_by=owner,
    )

    result = ApprovalService().decide(approval.pk, True, actor_id=owner.pk)

    task.refresh_from_db()
    approval.refresh_from_db()
    assert result.status == "approved"
    assert approval.status == "approved"
    assert task.status == "queued"


@pytest.mark.django_db
def test_non_owner_cannot_decide_owner_approval():
    User = get_user_model()
    owner = User.objects.create_user(username="designated-owner", password="pass", is_staff=True)
    other = User.objects.create_user(username="other-user", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Approval", objective="Security", owner=owner)
    agent = Agent.objects.create(code="secure_agent", name="Secure", mission="secure", active=True)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="secure",
        capability_code="secure",
        risk_snapshot="high",
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="secure",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Owner decision required",
        risk="high",
        requested_by=owner,
    )

    with pytest.raises(ValueError, match="designated owner"):
        ApprovalService().decide(approval.pk, True, actor_id=other.pk)

    approval.refresh_from_db()
    task.refresh_from_db()
    assert approval.status == "pending"
    assert task.status == "blocked"
