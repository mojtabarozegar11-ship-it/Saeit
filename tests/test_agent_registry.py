import pytest
from django.contrib.auth import get_user_model
from core.agent_registry import AgentRegistry
from core.models import Agent, AgentCapability, ResearchProject
from core.orchestrator import MasterAgent

pytestmark = pytest.mark.django_db


def test_registry_resolves_exact_capability():
    user = get_user_model().objects.create_user(username="registry-owner")
    ResearchProject.objects.create(title="P", objective="O", owner=user)
    agent = Agent.objects.create(code="researcher", name="Researcher", mission="research", active=True)
    capability = AgentCapability.objects.create(code="collect_source", name="Collect source")
    capability.agents.add(agent)
    assert AgentRegistry().resolve("collect_source") == agent


def test_registry_rejects_inactive_capability():
    user = get_user_model().objects.create_user(username="registry-owner-2")
    ResearchProject.objects.create(title="P2", objective="O", owner=user)
    agent = Agent.objects.create(code="researcher-2", name="Researcher", mission="research", active=True)
    capability = AgentCapability.objects.create(code="publish", name="Publish", active=False)
    capability.agents.add(agent)
    assert AgentRegistry().resolve("publish") is None


def test_master_agent_uses_capability_registry_before_mission_fallback():
    user = get_user_model().objects.create_user(username="registry-owner-3")
    project = ResearchProject.objects.create(title="P3", objective="O", owner=user)
    generic = Agent.objects.create(code="generic", name="Generic", mission="publish", active=True)
    specialist = Agent.objects.create(code="specialist", name="Specialist", mission="research", active=True)
    capability = AgentCapability.objects.create(code="publish", name="Publish")
    capability.agents.add(specialist)
    task = MasterAgent().plan(project, "publish", {})
    assert task.agent_id == specialist.id


def test_registry_does_not_route_compound_action_to_unrelated_token_capability():
    agent = Agent.objects.create(code="news-token-agent", name="News", mission="news", active=True)
    capability = AgentCapability.objects.create(code="news", name="News")
    capability.agents.add(agent)

    assert AgentRegistry().resolve("news_publish") is None


def test_master_agent_rejects_mission_only_match_before_enqueuing():
    user = get_user_model().objects.create_user(username="mission-only-owner")
    project = ResearchProject.objects.create(title="Mission only", objective="No phantom task", owner=user)
    Agent.objects.create(
        code="mission-only-agent", name="Mission", mission="news_publish", active=True
    )

    with pytest.raises(RuntimeError, match="No active agent"):
        MasterAgent().plan(project, "news_publish", {})


def test_registry_supports_core_prefixed_capability_accepted_by_runtime():
    agent = Agent.objects.create(code="research-core-agent", name="Core", mission="research", active=True)
    capability = AgentCapability.objects.create(code="core_collect_source", name="Collect")
    capability.agents.add(agent)

    assert AgentRegistry().resolve("collect_source") == agent
    assert AgentRegistry().capability_for(agent, "collect_source") == capability


def test_registry_prefers_low_risk_agent_before_critical_risk_agent():
    critical = Agent.objects.create(
        code="critical-agent", name="Critical", mission="publish", risk_level="critical", active=True
    )
    low = Agent.objects.create(
        code="low-agent", name="Low", mission="publish", risk_level="low", active=True
    )
    capability = AgentCapability.objects.create(code="publish", name="Publish")
    capability.agents.add(critical, low)

    assert AgentRegistry().resolve("publish") == low



@pytest.mark.parametrize("code", [
    "income_market_research",
    "factory_native_review",
    "mojtrade_observation_ingest",
    "mojtrade_demo_audit_ingest",
    "master_self_improvement",
])
def test_canonical_module_owner_beats_legacy_lower_risk(code):
    """Old row ID and cheaper risk must not route new work to old bots."""
    from core.unified_bot_identity import BOT_CODE

    legacy = Agent.objects.create(
        code="economic-master-agent", name="Old", mission="Old executor",
        risk_level="low", active=True,
    )
    canonical = Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", mission="Single bot",
        risk_level="high", active=True,
    )
    cap = AgentCapability.objects.create(
        code=code, name=code, risk_level="low", active=True,
    )
    cap.agents.add(legacy, canonical)
    assert AgentRegistry().resolve(code).pk == canonical.pk


@pytest.mark.parametrize("state", ["missing", "inactive", "capability_missing"])
def test_canonical_module_cannot_fall_back_to_old_executor(state):
    from core.models import AgentTask
    from core.unified_bot_identity import BOT_CODE

    owner = get_user_model().objects.create_user(username=f"single-owner-{state}")
    project = ResearchProject.objects.create(
        title="Canonical routing", objective="No legacy fallback", owner=owner,
    )
    old = Agent.objects.create(
        code="economic-master-agent", name="Old income master", active=True,
    )
    cap = AgentCapability.objects.create(
        code="income_market_research", name="Revenue research", active=True,
        risk_level="low",
    )
    cap.agents.add(old)
    if state != "missing":
        canonical = Agent.objects.create(
            code=BOT_CODE, name="Mojtaba.bot.ai",
            active=state != "inactive",
        )
        if state != "capability_missing":
            cap.agents.add(canonical)
    assert AgentRegistry().resolve("income_market_research") is None
    before = AgentTask.objects.count()
    with pytest.raises(RuntimeError, match="No active agent"):
        MasterAgent().plan(project, "income_market_research", {"private": True})
    assert AgentTask.objects.count() == before


def test_master_agent_plans_economic_work_only_for_canonical_owner():
    from core.models import AgentTask
    from core.unified_bot_identity import BOT_CODE

    owner = get_user_model().objects.create_user(username="canonical-plan-owner")
    project = ResearchProject.objects.create(
        title="Single worker", objective="Canonical only", owner=owner,
    )
    old = Agent.objects.create(
        code="economic-master-agent", name="Old", active=True, risk_level="low",
    )
    canonical = Agent.objects.create(
        code=BOT_CODE, name="Mojtaba.bot.ai", active=True, risk_level="high",
    )
    cap = AgentCapability.objects.create(
        code="income_market_research", name="Research", active=True, risk_level="low",
    )
    cap.agents.add(old, canonical)
    task = MasterAgent().plan(project, "income_market_research", {"private": True})
    assert task.agent_id == canonical.pk
    assert task.status == "queued"
    assert AgentTask.objects.filter(agent=old).count() == 0


def test_noncanonical_unmapped_specialist_remains_routable_until_handoff():
    old = Agent.objects.create(
        code="independent-legacy-specialist", name="Unmapped specialist",
        active=True, risk_level="low",
    )
    cap = AgentCapability.objects.create(
        code="unknown_legacy_private_job", name="Not yet mapped", active=True,
    )
    cap.agents.add(old)
    assert AgentRegistry().resolve("unknown_legacy_private_job") == old
