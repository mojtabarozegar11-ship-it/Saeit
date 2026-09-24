from django.db import transaction

from core.models import Agent, AgentTask, ApprovalRequest
from core.agent_registry import AgentRegistry
from core.services import normalize_action, normalize_risk, requires_owner_approval


class MasterAgent:
    """Create deterministic tasks and stop sensitive work at the approval gate."""

    def _select_agent(self, action):
        normalized_action = normalize_action(action)
        registered = AgentRegistry().resolve(normalized_action)
        if registered:
            return registered
        agents = Agent.objects.filter(active=True).order_by("risk_level", "id")
        if normalized_action:
            preferred = agents.filter(mission__icontains=normalized_action).first()
            if preferred:
                return preferred
            # Fall back to individual capability words for missions written as prose.
            for token in normalized_action.split("_"):
                if len(token) >= 3:
                    preferred = agents.filter(mission__icontains=token).first()
                    if preferred:
                        return preferred
        return agents.first()

    @transaction.atomic
    def plan(self, project, action, payload, risk="low"):
        normalized_action = normalize_action(action)
        normalized_risk = normalize_risk(risk)
        agent = self._select_agent(normalized_action)
        if not agent:
            raise RuntimeError("No active agent")

        capability = AgentRegistry().capability_for(agent, normalized_action)
        if not capability:
            raise RuntimeError("Selected agent lacks an active capability for this action")
        effective_risk = AgentRegistry().effective_risk(capability, normalized_risk)
        requires_approval = requires_owner_approval(normalized_action, effective_risk)
        task = AgentTask.objects.create(
            agent=agent,
            project=project,
            action_type=normalized_action,
            capability_code=capability.code,
            risk_snapshot=effective_risk,
            input_data=payload or {},
            status="blocked" if requires_approval else "queued",
        )

        if requires_approval:
            ApprovalRequest.objects.create(
                action_type=normalized_action,
                target_type="AgentTask",
                target_id=str(task.pk),
                reason="Owner approval required before execution.",
                risk=effective_risk,
                requested_by=project.owner,
            )

        return task
