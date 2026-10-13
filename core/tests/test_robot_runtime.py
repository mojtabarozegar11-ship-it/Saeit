import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.approval import ApprovalService
from core.models import (
    Agent,
    AgentCapability,
    AgentTask,
    ApprovalRequest,
    ResearchProject,
    Robot,
)
from core.task_runtime import TaskExecutionError, TaskRuntime
from core.tool_gateway import ToolGateway, ToolSpec
from core.worker_runner import WorkerRunner


@pytest.fixture
def robot_setup(db):
    owner = get_user_model().objects.create_user(
        username="robot-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Robot runtime", objective="Controlled robot task", owner=owner
    )
    agent = Agent.objects.create(
        code="robot-research-agent",
        name="Robot Research Agent",
        mission="research",
        active=True,
    )
    capability = AgentCapability.objects.create(
        code="research",
        name="Research",
        risk_level="low",
        active=True,
    )
    capability.agents.add(agent)
    robot = Robot.objects.create(
        code="research-robot",
        name="Research Robot",
        agent=agent,
        mission="Research through allowlisted tools",
        connector="research_lookup",
        autonomy_level="sandbox",
        deployment_status="sandbox",
        requires_owner_approval=True,
        budget_limit="2.00",
    )
    return owner, project, agent, capability, robot


@pytest.mark.django_db
def test_robot_must_be_qualified_before_claim(robot_setup):
    owner, project, agent, capability, robot = robot_setup
    robot.deployment_status = "draft"
    robot.save(update_fields=["deployment_status", "updated_at"])
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        robot=robot,
        action_type="research",
        capability_code=capability.code,
        risk_snapshot="low",
    )

    with pytest.raises(TaskExecutionError, match="not qualified"):
        TaskRuntime().claim(task.pk)

    task.refresh_from_db()
    assert task.status == "queued"
    assert task.attempt_count == 0


@pytest.mark.django_db
def test_master_planning_links_robot_and_requires_owner_approval(robot_setup):
    owner, project, agent, capability, robot = robot_setup
    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/api/master-chat/plan/",
        {
            "project_id": project.pk,
            "action_type": "research",
            "payload": {"topic": "soil"},
            "risk": "low",
            "robot_id": robot.pk,
        },
        format="json",
    )

    assert response.status_code == 201
    task = AgentTask.objects.get(pk=response.json()["id"])
    assert task.robot_id == robot.pk
    assert task.agent_id == agent.pk
    assert task.status == "blocked"
    approval = ApprovalRequest.objects.get(target_type="AgentTask", target_id=str(task.pk))
    assert approval.status == "pending"

    ApprovalService().decide(
        approval.pk, approved=True, actor_id=owner.pk, actor_type="owner"
    )
    task.refresh_from_db()
    assert task.status == "queued"


@pytest.mark.django_db
def test_robot_task_uses_registered_connector_and_respects_budget(robot_setup):
    owner, project, agent, capability, robot = robot_setup
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        robot=robot,
        action_type="research",
        capability_code=capability.code,
        risk_snapshot="low",
        input_data={"topic": "soil"},
        status="blocked",
    )
    approval = ApprovalRequest.objects.create(
        action_type="research",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Robot execution requires owner approval.",
        risk="low",
        status="approved",
        requested_by=owner,
    )
    task.status = "queued"
    task.save(update_fields=["status", "updated_at"])
    invoked = []
    gateway = ToolGateway([
        ToolSpec(
            code="research_lookup",
            handler=lambda payload: invoked.append(payload) or {
                "summary": "soil study",
                "__cost": "1.25",
            },
        ),
    ])

    completed = WorkerRunner(gateway).run(task.pk)

    assert completed.status == "completed"
    assert completed.robot_id == robot.pk
    assert invoked == [{"topic": "soil"}]
    assert str(completed.cost) == "1.2500"


@pytest.mark.django_db
def test_robot_budget_cannot_be_exceeded(robot_setup):
    owner, project, agent, capability, robot = robot_setup
    task = AgentTask.objects.create(
        agent=agent,
        project=project,
        robot=robot,
        action_type="research",
        capability_code=capability.code,
        risk_snapshot="low",
        status="running",
        execution_id="robot-budget-execution",
        attempt_count=1,
    )
    ApprovalRequest.objects.create(
        action_type="research",
        target_type="AgentTask",
        target_id=str(task.pk),
        reason="Robot execution requires owner approval.",
        risk="low",
        status="approved",
        requested_by=owner,
    )

    with pytest.raises(TaskExecutionError, match="budget limit"):
        TaskRuntime().complete(
            task.pk,
            output_data={"summary": "done"},
            cost="2.01",
            execution_id=task.execution_id,
        )

    task.refresh_from_db()
    assert task.status == "running"
    assert task.cost == 0
