import pytest
from django.contrib.auth import get_user_model
from core.models import Agent, ResearchProject
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
