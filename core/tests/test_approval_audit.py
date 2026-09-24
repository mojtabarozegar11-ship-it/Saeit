import pytest
from django.contrib.auth import get_user_model

from core.approval import ApprovalService
from core.models import Agent, AgentTask, ApprovalRequest, AuditLog, ResearchProject


@pytest.mark.django_db
def test_approval_decision_writes_required_audit_trace():
    User = get_user_model()
    owner = User.objects.create_user(username="audit-owner", password="pass", is_staff=True)
    project = ResearchProject.objects.create(title="Audit", objective="Trace", owner=owner)
    agent = Agent.objects.create(code="audit_agent", name="Audit Agent", mission="audit", active=True)
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        action_type="audit",
        capability_code="audit",
        risk_snapshot="high",
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="audit",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Audit trace test",
        risk="high",
        requested_by=owner,
    )

    ApprovalService().decide(approval.pk, True, actor_id=owner.pk)

    log = AuditLog.objects.get(action="approval_decision", target_id=str(approval.pk))
    assert log.trace_id == f"approval-{approval.pk}"
