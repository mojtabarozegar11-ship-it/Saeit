from django.db.models import Case, IntegerField, Value, When

from .models import Agent, AgentCapability
from .services import normalize_risk


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# The sole cybersecurity execution owner; these remain internal capabilities
# of Mojtaba.bot.ai, never independently routable bots.
CANONICAL_CYBER_AGENT = "mojtaba-bot-ai"
CANONICAL_CYBER_ACTIONS = frozenset({
    "cyber_evidence_review",
    "cyber_origin_defense",
    "cyber_incident_response",
})


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
        # String ordering puts "critical" before "low". Use policy risk order.
        risk_priority = Case(
            *(When(risk_level=name, then=Value(priority)) for name, priority in RISK_ORDER.items()),
            default=Value(len(RISK_ORDER)),
            output_field=IntegerField(),
        )
        agents = capability.agents.filter(active=True)
        if normalized in CANONICAL_CYBER_ACTIONS:
            # Fail closed rather than selecting a lower-risk, noncanonical Agent.
            agents = agents.filter(code=CANONICAL_CYBER_AGENT)
        return (
            agents.annotate(_risk_priority=risk_priority)
            .order_by("_risk_priority", "id")
            .first()
        )

    def capability_for(self, agent, action):
        normalized = self._normalize(action)
        if not agent or not normalized:
            return None
        if normalized in CANONICAL_CYBER_ACTIONS and agent.code != CANONICAL_CYBER_AGENT:
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
