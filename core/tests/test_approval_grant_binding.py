"""Fail-closed one-use approval grants; isolated test DB only."""
import pytest
from django.contrib.auth import get_user_model
from core.approval import ApprovalService
from core.models import Agent, AgentTask, ApprovalRequest, ApprovalGrant

pytestmark = pytest.mark.django_db

@pytest.fixture
def verified_grant_case(db):
    owner = get_user_model().objects.create_user(username="grant-binding-owner")
    agent = Agent.objects.create(code="grant-binding-agent", name="Private", mission="Test", active=True)
    task = AgentTask.objects.create(agent=agent, action_type="deploy",
                                    capability_code="deploy", risk_snapshot="high", status="blocked")
    approval = ApprovalRequest.objects.create(
        action_type="deploy", target_type="AgentTask", target_id=str(task.pk),
        risk="high", status="approved", requested_by=owner, reason="Private approval")
    return owner, task, approval

@pytest.mark.parametrize("action", ["payment", "external_write", "publish"])
def test_other_action_cannot_use_approved_deploy(verified_grant_case, action):
    owner, task, approval = verified_grant_case
    with pytest.raises(ValueError, match="action must match"):
        ApprovalService().issue_grant(approval.pk, owner.pk,
                                      {"action": action, "task_id": task.pk})
    assert ApprovalGrant.objects.count() == 0

def test_wrong_task_or_target_blocks_grant(verified_grant_case):
    owner, task, approval = verified_grant_case
    for scope, expected in [
        ({"action": "deploy", "task_id": task.pk + 1}, "task scope mismatch"),
        ({"action": "deploy", "target": "order:123"}, "target scope mismatch"),
    ]:
        with pytest.raises(ValueError, match=expected):
            ApprovalService().issue_grant(approval.pk, owner.pk, scope)

def test_deleted_task_cannot_issue_grant(verified_grant_case):
    owner, task, approval = verified_grant_case
    task.delete()
    with pytest.raises(ValueError, match="task is missing or changed"):
        ApprovalService().issue_grant(approval.pk, owner.pk, {"action": "deploy"})

def test_revocation_and_task_mutation_invalidate_issued_grant(verified_grant_case):
    owner, task, approval = verified_grant_case
    service = ApprovalService()
    scope = {"action": "deploy", "task_id": task.pk}
    grant = service.issue_grant(approval.pk, owner.pk, scope)
    task.action_type = "payment"
    task.save(update_fields=["action_type"])
    with pytest.raises(ValueError, match="task is missing or changed"):
        service.authorize_grant(grant.pk, scope)
    task.action_type = "deploy"
    task.save(update_fields=["action_type"])
    approval.status = "rejected"
    approval.save(update_fields=["status"])
    with pytest.raises(ValueError, match="no longer approved"):
        service.authorize_grant(grant.pk, scope)
    grant.refresh_from_db()
    assert grant.used_at is None

def test_inactive_owner_cannot_issue_or_consume(verified_grant_case):
    owner, task, approval = verified_grant_case
    service = ApprovalService()
    scope = {"action": "deploy", "task_id": task.pk}
    grant = service.issue_grant(approval.pk, owner.pk, scope)
    owner.is_active = False
    owner.save(update_fields=["is_active"])
    with pytest.raises(ValueError, match="active designated owner"):
        service.issue_grant(approval.pk, owner.pk, scope)
    with pytest.raises(ValueError, match="owner is inactive"):
        service.authorize_grant(grant.pk, scope)

def test_paid_model_grant_requires_same_run_id(verified_grant_case):
    owner, task, approval = verified_grant_case
    task.input_data = {"run_id": 7}
    task.save(update_fields=["input_data"])
    with pytest.raises(ValueError, match="run scope mismatch"):
        ApprovalService().issue_grant(
            approval.pk, owner.pk, {"action": "deploy", "paid_model": True, "run_id": 8})
    with pytest.raises(ValueError, match="bound run_id"):
        ApprovalService().issue_grant(
            approval.pk, owner.pk, {"action": "deploy", "paid_model": True})

@pytest.mark.parametrize("target_type,action,target_id,bad,good,error", [
    ("Order", "payment", "7", "order:8", "order:7", "order target mismatch"),
    ("TradeMailbox", "external_write", "company-trade", "other", "company-trade", "mailbox target mismatch"),
])
def test_target_type_enforces_approved_target(db,target_type,action,target_id,bad,good,error):
    owner = get_user_model().objects.create_user(username=f"grant-target-{target_type}")
    approval = ApprovalRequest.objects.create(
        action_type=action, target_type=target_type, target_id=target_id,
        status="approved", requested_by=owner, reason="Target-bound approval", risk="high")
    with pytest.raises(ValueError, match=error):
        ApprovalService().issue_grant(approval.pk, owner.pk, {"action": action, "target": bad})
    grant = ApprovalService().issue_grant(approval.pk, owner.pk, {"action": action, "target": good})
    assert grant.scope["target"] == good
