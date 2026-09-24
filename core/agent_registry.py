from .models import Agent


class AgentRegistry:
    """Capability-aware agent registry used by the Master Agent."""

    def resolve(self, action):
        normalized = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        if not normalized:
            return None
        exact = Agent.objects.filter(active=True, capabilities__code=normalized).order_by("risk_level", "id").first()
        if exact:
            return exact
        for token in normalized.split("_"):
            if len(token) >= 3:
                agent = Agent.objects.filter(active=True, capabilities__code=token).order_by("risk_level", "id").first()
                if agent:
                    return agent
        return None

    def can_execute(self, agent, action):
        normalized = str(action or "").strip().lower().replace("-", "_").replace(" ", "_")
        return bool(
            agent
            and agent.active
            and agent.capabilities.filter(active=True, code=normalized).exists()
        )
