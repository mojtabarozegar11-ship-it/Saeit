"""Owner decisions require authenticated ownership and a valid live task.

No actual production approvals, external transactions or deployed services.
These database-only tests check the isolated decision boundary.
"""
import pytest
from django.contrib.auth import get_user_model

from core.approval import ApprovalService
from core.models import Agent, AgentTask, ApprovalRequest, AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_task(db):
    owner = get_user_model().objects.create_user(username="identity-owner", password="unusable")
    agent = Agent.objects.create(
        code="approval-owner-identity-agent", name="Approval agent",
        mission="Safe internal decision", active=True,
    )
    task = AgentTask.objects.create(
        agent=agent, action_type="deploy",
        capability_code="deploy", risk_snapshot="high", status="blocked",
    )
    request = ApprovalRequest.objects.create(
        action_type="deploy", target_type="AgentTask",
        target_id=str(task.pk), reason="Owner authorization required",
        risk="high", status="pending", requested_by=owner,
    )
    return owner, task, request


@pytest.mark.parametrize("actor_type", ["agent", "system", "worker", "", None])
def test_non_owner_actor_type_cannot_approve_or_release_task(owner_task, actor_type):
    owner, task, request = owner_task
    before = AuditLog.objects.count()
    with pytest.raises(ValueError, match="designated owner"):
        ApprovalService().decide(
            request.pk, True, actor_id=owner.pk, actor_type=actor_type,
        )
    task.refresh_from_db()
    request.refresh_from_db()
    assert task.status == "blocked" and request.status == "pending"
    assert AuditLog.objects.count() == before


def test_missing_owner_identity_cannot_approve(owner_task):
    _, task, request = owner_task
    with pytest.raises(ValueError, match="designated owner"):
        ApprovalService().decide(request.pk, True)
    task.refresh_from_db()
    request.refresh_from_db()
    assert task.status == "blocked" and request.status == "pending"


def test_missing_owner_identity_cannot_cancel_task(owner_task):
    _, task, request = owner_task
    with pytest.raises(ValueError, match="designated owner"):
        ApprovalService().decide(request.pk, False)
    task.refresh_from_db()
    request.refresh_from_db()
    assert task.status == "blocked" and request.status == "pending"


def test_disabled_owner_cannot_approve_task(owner_task):
    owner, task, request = owner_task
    owner.is_active = False
    owner.save(update_fields=["is_active"])
    with pytest.raises(ValueError, match="active designated owner"):
        ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    task.refresh_from_db()
    request.refresh_from_db()
    assert task.status == "blocked" and request.status == "pending"


def test_dangling_task_approval_is_denied_and_not_audited(owner_task):
    owner, task, request = owner_task
    task.delete()
    before = AuditLog.objects.count()
    with pytest.raises(ValueError, match="target task no longer exists"):
        ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    request.refresh_from_db()
    assert request.status == "pending"
    assert AuditLog.objects.count() == before


def test_owner_can_reject_dangling_request_without_execution(owner_task):
    owner, task, request = owner_task
    task.delete()
    result = ApprovalService().decide(request.pk, False, actor_id=owner.pk)
    assert result.status == "rejected"
    request.refresh_from_db()
    assert request.status == "rejected"
    assert AuditLog.objects.filter(
        action="approval_decision", target_id=str(request.pk),
    ).exists()


def test_owner_can_approve_bound_blocked_task(owner_task):
    owner, task, request = owner_task
    result = ApprovalService().decide(request.pk, True, actor_id=owner.pk)
    task.refresh_from_db()
    assert result.status == "approved"
    assert task.status == "queued"
    assert AuditLog.objects.filter(
        action="approval_decision", target_id=str(request.pk),
    ).exists()
