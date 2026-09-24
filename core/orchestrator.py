from core.models import Agent, AgentTask, ApprovalRequest
from core.services import requires_owner_approval


class MasterAgent:
    def _select_agent(self, action):
        agents = Agent.objects.filter(active=True).order_by("risk_level", "id")
        if action:
            action_lower = action.lower()
            preferred = agents.filter(mission__icontains=action_lower).first()
            if preferred:
                return preferred
        return agents.first()

    def plan(self, project, action, payload, risk="low"):
        agent = self._select_agent(action)
        if not agent:
            raise RuntimeError("No active agent")

        task = AgentTask.objects.create(
            agent=agent,
            project=project,
            input_data=payload,
            status="queued",
        )

        if requires_owner_approval(action, risk):
            ApprovalRequest.objects.create(
                action_type=action,
                target_type="AgentTask",
                target_id=str(task.pk),
                reason="Owner approval required before execution.",
                risk=risk,
                requested_by=project.owner,
            )
            task.status = "blocked"
            task.save(update_fields=["status", "updated_at"])

        return task
