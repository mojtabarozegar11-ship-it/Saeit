from django.db import transaction

from core.models import Agent, AgentTask, ApprovalRequest
from core.chat_operation_security import is_authorized_chat_operator
from core.unified_bot_identity import (
    BOT_CODE, assert_single_executor, unresolved_master_task_id,
)
from core.agent_registry import AgentRegistry
from core.services import normalize_action, normalize_risk, requires_owner_approval


class MasterAgent:
    """Create deterministic tasks and stop sensitive work at the approval gate."""

    def _select_agent(self, action):
        # Never select legacy or specialist Agent rows by a global
        # lowest-risk sort: all master tasks have one canonical owner.
        normalized_action = normalize_action(action)
        assert_single_executor(Agent, BOT_CODE)
        master = Agent.objects.select_for_update().filter(
            code=BOT_CODE, active=True,
        ).first()
        if master is None:
            return None
        if not AgentRegistry().capability_for(master, normalized_action):
            return None
        return master

    @transaction.atomic
    def plan(self, project, action, payload, risk="low", *, requester=None):
        # A requested approval is not permission. The caller must first
        # authenticate the owner if this is a human-originated command.
        if requester is not None:
            if not is_authorized_chat_operator(requester):
                raise PermissionError("MASTER_PLAN_REQUIRES_AUTHENTICATED_OWNER")
            if project is None or requester.pk != project.owner_id:
                raise PermissionError("MASTER_PROJECT_OWNER_MISMATCH")
        if not isinstance(payload, dict):
            raise ValueError("Master task payload must be a JSON object")
        normalized_action = normalize_action(action)
        normalized_risk = normalize_risk(risk)
        agent = self._select_agent(normalized_action)
        if not agent:
            raise RuntimeError("No active agent")
        unresolved = unresolved_master_task_id(AgentTask)
        if unresolved is not None:
            raise RuntimeError(
                f"MASTER_PLAN_BLOCKED_PENDING_RECONCILIATION:{unresolved}"
            )

        capability = AgentRegistry().capability_for(agent, normalized_action)
        if not capability:
            raise RuntimeError("Selected agent lacks an active capability for this action")
        effective_risk = AgentRegistry().effective_risk(capability, normalized_risk)
        requires_approval = requires_owner_approval(normalized_action, effective_risk)
        approver = requester if requester is not None else project.owner
        if requires_approval and not is_authorized_chat_operator(approver):
            raise PermissionError("MASTER_SENSITIVE_TASK_REQUIRES_DESIGNATED_OWNER")
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
                requested_by=approver,
            )

        return task
