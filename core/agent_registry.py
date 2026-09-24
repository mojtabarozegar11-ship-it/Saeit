from .models import Agent, AgentCapability
from .services import normalize_risk


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AgentRegistry:
    """Capability-aware registry and execution-policy boundary."""

    def resolve(self, action):
        normalized = self._normalize(action)
        if not normalized:
            return None
        capability = self._capability(normalized)
        if not capability:
            for token in normalized.split("_"):
                if len(token) >= 3:
                    capability = self._capability(token)
                    if capability:
                        break
        if not capability:
            return None
        return capability.agents.filter(active=True).order_by("risk_level", "id").first()

    def capability_for(self, agent, action):
        normalized = self._normalize(action)
        if not agent or not normalized:
            return None
        return agent.capabilities.filter(active=True, code=normalized).first()

    def can_execute(self, agent, action):
        return self.capability_for(agent, action) is not None

    def effective_risk(self, capability, requested_risk="low"):
        capability_risk = normalize_risk(capability.risk_level or "low")
        requested = normalize_risk(requested_risk)
        return capability_risk if RISK_ORDER[capability_risk] >= RISK_ORDER[requested] else requested

    @staticmethod
    def _normalize(action):
        return str(action or "").strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _capability(code):
        return AgentCapability.objects.filter(active=True, code=code).first()
