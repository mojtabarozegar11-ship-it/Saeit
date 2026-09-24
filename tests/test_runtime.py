import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from core.models import Agent, ApprovalRequest, ResearchProject
from core.approval import ApprovalService
from core.orchestrator import MasterAgent
from core.research_runtime import ResearchRuntime

pytestmark = pytest.mark.django_db


def setup_project():
    user = get_user_model().objects.create_user(username="owner")
    project = ResearchProject.objects.create(title="Research", objective="Test", owner=user)
    agent = Agent.objects.create(code="master", name="Master", mission="orchestration", active=True)
    return project, agent


def test_sensitive_action_is_blocked():
    project, _ = setup_project()
    task = MasterAgent().plan(project, "publish", {"x": 1})
    assert task.status == "blocked"


def test_low_risk_action_is_queued():
    project, _ = setup_project()
    task = MasterAgent().plan(project, "collect_source", {"x": 1})
    assert task.status == "queued"


def test_research_runtime_registers_evidence():
    project, _ = setup_project()
    runtime = ResearchRuntime()
    source = runtime.register_source(project, "Source")
    evidence = runtime.add_evidence(project, source, "passage", 0.9)
    assert evidence.project_id == project.id


def test_evidence_cannot_cross_projects():
    from django.core.exceptions import ValidationError
    from core.models import Evidence, ResearchSource

    user = get_user_model().objects.create_user(username="owner-2")
    other = ResearchProject.objects.create(title="Other", objective="Test", owner=user)
    project, _ = setup_project()
    source = ResearchSource.objects.create(project=project, title="Source")
    evidence = Evidence(project=other, source=source, passage="cross-project")
    with pytest.raises(ValidationError):
        evidence.full_clean()


def test_report_versions_are_unique_per_project():
    from core.models import Report

    project, _ = setup_project()
    Report.objects.create(project=project, title="R1", version=1)
    with pytest.raises(IntegrityError):
        Report.objects.create(project=project, title="R1 duplicate", version=1)


def test_runtime_rejects_cross_project_evidence():
    from django.core.exceptions import ValidationError
    from core.models import ResearchSource

    project, _ = setup_project()
    other_user = get_user_model().objects.create_user(username="other")
    other = ResearchProject.objects.create(title="Other", objective="Other", owner=other_user)
    source = ResearchSource.objects.create(project=other, title="Other source")
    with pytest.raises(ValidationError):
        ResearchRuntime().add_evidence(project, source, "wrong project", 0.9)


def test_runtime_rejects_cross_project_finding_evidence():
    from django.core.exceptions import ValidationError
    from core.models import Evidence, ResearchSource

    project, _ = setup_project()
    other_user = get_user_model().objects.create_user(username="other-2")
    other = ResearchProject.objects.create(title="Other", objective="Other", owner=other_user)
    source = ResearchSource.objects.create(project=other, title="Other source")
    evidence = Evidence.objects.create(project=other, source=source, passage="other")
    with pytest.raises(ValidationError):
        ResearchRuntime().add_finding(project, "Finding", "statement", [evidence], 0.9)


def test_approval_decision_preserves_reason_and_audits_actor_type():
    project, _ = setup_project()
    approval = ApprovalRequest.objects.create(
        action_type="publish",
        target_type="AgentTask",
        target_id="999999",
        reason="Original reason",
        requested_by=project.owner,
    )
    result = ApprovalService().decide(
        approval_id=approval.pk,
        approved=True,
        actor_id=project.owner.pk,
        note="Approved after review.",
        actor_type="owner",
    )
    assert result.reason == "Original reason"
    assert result.decision_note == "Approved after review."
    assert result.status == "approved"
    from core.models import AuditLog
    audit = AuditLog.objects.get(target_id=str(approval.pk), action="approval_decision")
    assert audit.actor_type == "owner"


def test_approval_cannot_be_decided_twice():
    project, _ = setup_project()
    approval = ApprovalRequest.objects.create(
        action_type="publish",
        target_type="AgentTask",
        target_id="999999",
        reason="One-time approval",
        requested_by=project.owner,
    )
    ApprovalService().decide(approval.pk, approved=False, actor_id=project.owner.pk)
    with pytest.raises(ValueError, match="no longer pending"):
        ApprovalService().decide(approval.pk, approved=True, actor_id=project.owner.pk)


def test_sensitive_action_normalizes_before_persisting():
    project, _ = setup_project()
    task = MasterAgent().plan(project, " production-change ", {"x": 1}, risk="low")
    assert task.status == "blocked"
    approval = ApprovalRequest.objects.get(target_id=str(task.pk))
    assert approval.action_type == "production_change"
    assert approval.risk == "low"
