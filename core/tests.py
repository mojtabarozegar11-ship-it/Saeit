from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .approval import ApprovalService
from .models import (
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    AuditLog,
    Evidence,
    ResearchProject,
    ResearchSource,
)
from .orchestrator import MasterAgent
from .task_runtime import TaskExecutionError, TaskRuntime


User = get_user_model()


class FoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="safe-pass-123")
        self.other = User.objects.create_user(username="other", password="safe-pass-123")
        self.agent = Agent.objects.create(
            code="researcher",
            name="Researcher",
            mission="research and analysis",
            risk_level="low",
            active=True,
        )
        self.capability = AgentCapability.objects.create(
            code="research",
            name="Research",
            risk_level="low",
            active=True,
        )
        self.capability.agents.add(self.agent)
        self.project = ResearchProject.objects.create(
            title="Test project",
            objective="Validate runtime",
            owner=self.owner,
        )

    def test_low_risk_plan_is_queued(self):
        task = MasterAgent().plan(self.project, "research", {"q": "test"}, risk="low")
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.capability_code, "research")
        self.assertEqual(task.risk_snapshot, "low")
        self.assertFalse(ApprovalRequest.objects.exists())

    def test_high_risk_plan_is_blocked_until_owner_approval(self):
        task = MasterAgent().plan(self.project, "research", {}, risk="high")
        self.assertEqual(task.status, "blocked")
        approval = ApprovalRequest.objects.get(target_id=str(task.pk))
        self.assertEqual(approval.status, "pending")
        self.assertEqual(approval.requested_by_id, self.owner.pk)

        with self.assertRaises(TaskExecutionError):
            TaskRuntime().claim(task.pk)

        ApprovalService().decide(
            approval.pk,
            approved=True,
            actor_id=self.owner.pk,
            note="approved for test",
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "queued")
        claimed = TaskRuntime().claim(task.pk)
        self.assertEqual(claimed.status, "running")

    def test_execution_identity_and_completion_are_enforced(self):
        task = MasterAgent().plan(self.project, "research", {}, risk="low")
        running = TaskRuntime().claim(task.pk)
        with self.assertRaises(TaskExecutionError):
            TaskRuntime().complete(
                task.pk,
                output_data={"ok": True},
                cost=Decimal("0.10"),
                execution_id="wrong",
            )

        completed = TaskRuntime().complete(
            task.pk,
            output_data={"ok": True},
            cost=Decimal("0.10"),
            execution_id=running.execution_id,
        )
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.cost, Decimal("0.1000"))
        self.assertTrue(AuditLog.objects.filter(action="task_completed").exists())

    def test_failure_requeues_until_retry_budget_is_exhausted(self):
        task = MasterAgent().plan(self.project, "research", {}, risk="low")
        task.max_attempts = 2
        task.save(update_fields=["max_attempts"])
        running = TaskRuntime().claim(task.pk)
        failed = TaskRuntime().fail(task.pk, "temporary", execution_id=running.execution_id)
        self.assertEqual(failed.status, "queued")
        self.assertEqual(failed.execution_id, "")
        running = TaskRuntime().claim(task.pk)
        failed = TaskRuntime().fail(task.pk, "permanent", execution_id=running.execution_id)
        self.assertEqual(failed.status, "failed")

    def test_stale_execution_is_recovered(self):
        task = MasterAgent().plan(self.project, "research", {}, risk="low")
        running = TaskRuntime().claim(task.pk)
        AgentTask.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(hours=1)
        )
        recovered = TaskRuntime().recover_stale(task.pk, stale_after_seconds=60)
        self.assertEqual(recovered.status, "queued")
        self.assertEqual(recovered.execution_id, "")
        self.assertTrue(AuditLog.objects.filter(action="task_recovered_stale").exists())

    def test_evidence_source_must_belong_to_project(self):
        other_project = ResearchProject.objects.create(
            title="Other", objective="Other", owner=self.owner
        )
        source = ResearchSource.objects.create(
            project=other_project, title="Other source"
        )
        evidence = Evidence(
            project=self.project, source=source, passage="invalid"
        )
        with self.assertRaises(Exception):
            evidence.full_clean()

    def test_non_owner_cannot_decide_approval(self):
        task = MasterAgent().plan(self.project, "research", {}, risk="high")
        approval = ApprovalRequest.objects.get(target_id=str(task.pk))
        with self.assertRaises(ValueError):
            ApprovalService().decide(
                approval.pk, approved=True, actor_id=self.other.pk
            )

    def test_health_endpoint_reports_database(self):
        client = APIClient()
        response = client.get("/api/health/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    @patch.dict("os.environ", {}, clear=True)
    def test_master_chat_does_not_execute_without_provider_key(self):
        from .chat_runtime import MasterAgentChat
        from .models import ChatSession

        session = ChatSession.objects.create(user=self.owner, title="test")
        reply = MasterAgentChat().respond(session, "سلام")
        self.assertIn("هیچ اقدامی اجرا نشد", reply)
