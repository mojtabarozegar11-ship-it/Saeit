import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model

from core.models import Agent, AgentCapability, AgentTask, ResearchProject
from core.task_runtime import TaskExecutionError, TaskRuntime


@pytest.mark.django_db
def test_complete_preserves_decimal_cost_without_float_rounding():
    user = get_user_model().objects.create_user(
        username="cost-owner", password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Cost test", objective="Validate Decimal cost", owner=user
    )
    agent = Agent.objects.create(
        code="cost-agent", name="Cost Agent", mission="Test costs", active=True
    )
    capability = AgentCapability.objects.create(
        code="cost", name="Cost", risk_level="low", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type="cost",
        capability_code="cost", risk_snapshot="low", status="running",
        execution_id="exec-cost", attempt_count=1
    )

    TaskRuntime().complete(
        task.pk, output_data={"ok": True},
        cost="0.1001", execution_id="exec-cost"
    )

    task.refresh_from_db()
    assert task.cost == Decimal("0.1001")


@pytest.mark.django_db
@pytest.mark.parametrize("bad_cost", ["NaN", "Infinity", "-Infinity"])
def test_complete_rejects_non_finite_cost(bad_cost):
    user = get_user_model().objects.create_user(
        username=f"cost-{bad_cost.replace('-', '').replace('.', '')}",
        password="pass", is_staff=True
    )
    project = ResearchProject.objects.create(
        title="Cost test", objective="Validate cost", owner=user
    )
    agent = Agent.objects.create(
        code=f"agent-{abs(hash(bad_cost))}", name="Cost Agent",
        mission="Test costs", active=True
    )
    capability = AgentCapability.objects.create(
        code=f"cap-{abs(hash(bad_cost))}", name="Cost", active=True
    )
    capability.agents.add(agent)
    task = AgentTask.objects.create(
        agent=agent, project=project, action_type=capability.code,
        capability_code=capability.code, risk_snapshot="low",
        status="running", execution_id="exec-bad", attempt_count=1
    )

    with pytest.raises(TaskExecutionError, match="finite"):
        TaskRuntime().complete(
            task.pk, output_data={}, cost=bad_cost, execution_id="exec-bad"
        )
