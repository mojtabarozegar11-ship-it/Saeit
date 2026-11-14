import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from core.approval import ApprovalService
from core.models import Agent, AgentTask, ApprovalGrant, ApprovalRequest


@pytest.mark.django_db
def test_approved_request_can_issue_and_consume_scoped_one_time_grant():
    owner = get_user_model().objects.create_user(username="grant-owner", password="pass", is_staff=True)
    agent = Agent.objects.create(code="grant-publish-agent", name="Grant fixture", mission="Private", active=True)
    task = AgentTask.objects.create(agent=agent, action_type="publish",
                                    capability_code="publish", risk_snapshot="high", status="blocked")
    approval = ApprovalRequest.objects.create(
        action_type="publish", target_type="AgentTask", target_id=str(task.pk),
        reason="owner grant test", risk="high", status="approved", requested_by=owner,
    )
    service = ApprovalService()
    scope = {"action": "publish", "task_id": task.pk}
    grant = service.issue_grant(approval.pk, owner.pk, scope, ttl_seconds=300)
    assert grant.used_at is None
    assert service.authorize_grant(grant.pk, scope).used_at is not None
    with pytest.raises(ValueError, match="already been used"):
        service.authorize_grant(grant.pk, scope)

@pytest.mark.django_db
def test_grant_rejects_scope_mismatch_and_expiry():
    User = get_user_model()
    owner = User.objects.create_user(username="grant-owner-2", password="pass", is_staff=True)
    approval = ApprovalRequest.objects.create(
        action_type="payment",
        target_type="Order",
        target_id="7",
        reason="scope test",
        risk="critical",
        status="approved",
        requested_by=owner,
    )
    service = ApprovalService()
    grant = service.issue_grant(approval.pk, owner.pk, {"action": "payment", "target": "order:7"}, ttl_seconds=300)

    with pytest.raises(ValueError, match="scope mismatch"):
        service.authorize_grant(grant.pk, {"action": "payment", "target": "order:8"})

    grant.expires_at = timezone.now() - timedelta(seconds=1)
    grant.save(update_fields=["expires_at", "updated_at"])
    with pytest.raises(ValueError, match="expired"):
        service.authorize_grant(grant.pk, {"action": "payment", "target": "order:7"})
