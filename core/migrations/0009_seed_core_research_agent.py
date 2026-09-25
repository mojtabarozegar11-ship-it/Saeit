from django.db import migrations


AGENT_CODE = "core_research"
CAPABILITY_CODE = "research"


def seed_core_research_agent(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    AgentCapability = apps.get_model("core", "AgentCapability")

    capability, _ = AgentCapability.objects.get_or_create(
        code=CAPABILITY_CODE,
        defaults={
            "name": "Research",
            "description": "Controlled research and analysis capability.",
            "risk_level": "low",
            "active": True,
        },
    )
    agent, _ = Agent.objects.get_or_create(
        code=AGENT_CODE,
        defaults={
            "name": "Core Research Agent",
            "mission": "Perform controlled research and analysis tasks.",
            "risk_level": "low",
            "active": True,
        },
    )
    agent.capabilities.add(capability)


def unseed_core_research_agent(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    AgentCapability = apps.get_model("core", "AgentCapability")
    Agent.objects.filter(code=AGENT_CODE).delete()
    AgentCapability.objects.filter(code=CAPABILITY_CODE).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0008_approval_and_runtime_hardening")]

    operations = [
        migrations.RunPython(seed_core_research_agent, unseed_core_research_agent),
    ]
