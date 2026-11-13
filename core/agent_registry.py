from .models import Agent, AgentCapability
from .services import normalize_risk
from .unified_bot_identity import BOT_CODE


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AgentRegistry:
    """Capability-aware registry and execution-policy boundary."""

    def resolve(self, action):
        normalized = self._normalize(action)
        if not normalized:
            return None
        # Dispatch only on a capability that the execution gate will accept.
        # Matching an arbitrary token can select an agent that cannot run the
        # requested action, leaving the task unplanned.
        capability = self._capability(normalized) or self._capability(f"core_{normalized}")
        if not capability:
            return None

        # One bot, with many modules: EVERY newly planned task has exactly
        # one eligible execution owner, even when a capability has not yet
        # been mapped to a reviewed module. Never fall back to a legacy row
        # because of a low risk score, earlier PK or matching mission.
        #
        # Absence of a canonical capability assignment is a migration
        # blocker, not permission to dispatch work to a second bot.
        return capability.agents.filter(code=BOT_CODE, active=True).first()

    def capability_for(self, agent, action):
        normalized = self._normalize(action)
        if not agent or not normalized:
            return None
        capability = agent.capabilities.filter(active=True, code=normalized).first()
        if capability:
            return capability
        return agent.capabilities.filter(active=True, code=f"core_{normalized}").first()

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
