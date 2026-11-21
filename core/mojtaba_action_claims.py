"""One authoritative Django database for durable canonical action claims.

The authenticated host must inject this store into MojtabaBot. All participating
processes must share the same authoritative writable DB and canonical Agent.
No migration, startup, task dispatch, adapter effects or automatic retries here.
A claim is NOT a payment receipt, delivery confirmation or external attestation.
Restoring an older DB snapshot requires independent external reconciliation.
"""
from hashlib import sha256

from django.db import connections, transaction

from ava_core.capabilities import ActionRequest, OperationSpec
from core.models import Agent, AuditLog
from core.unified_bot_identity import BOT_CODE

CLAIM_ACTION = "mojtaba_canonical_action_claim_v1"


class DjangoCanonicalActionClaims:
    def __init__(self, *, owner_id: str, using: str):
        if not isinstance(owner_id, str) or not owner_id.startswith("agent-"):
            raise ValueError("Canonical host owner identifier required")
        if not isinstance(using, str) or not using.strip():
            raise ValueError("Explicit authoritative database alias required")
        self.owner_id = owner_id
        self.using = using

    def reserve(self, request: ActionRequest, operation: OperationSpec) -> bool:
        if (not isinstance(request, ActionRequest) or request.owner_id != self.owner_id
                or not isinstance(operation, OperationSpec) or operation.name != request.operation
                or operation.effect == "local"):
            raise PermissionError("Canonical action claim scope mismatch")
        connection = connections[self.using]
        if not connection.features.has_select_for_update:
            raise RuntimeError("Database must support row-level locking for durable claims")
        # Global within this canonical namespace, survives Agent row replacement.
        trace = sha256(("mojtaba-action-v1:" + request.request_id).encode("utf-8")).hexdigest()
        # Require the outermost transaction AND a real DB commit before dispatch.
        if connection.in_atomic_block or not connection.get_autocommit():
            raise RuntimeError("Action reservation requires an independent committed transaction")
        with transaction.atomic(using=self.using, durable=True):
            agent = Agent.objects.using(self.using).select_for_update().filter(
                code=BOT_CODE, active=True).first()
            if agent is None or self.owner_id != "agent-" + str(agent.pk):
                raise PermissionError("Active canonical Agent identity required")
            claims = AuditLog.objects.using(self.using).select_for_update().filter(
                actor_type="system", actor_id=BOT_CODE, action=CLAIM_ACTION, trace_id=trace)
            if claims.exists():
                return False
            AuditLog.objects.using(self.using).create(
                actor_type="system", actor_id=BOT_CODE, action=CLAIM_ACTION,
                target_type="Agent", target_id=str(agent.pk), trace_id=trace,
                before_state={}, after_state={"effect": operation.effect,
                    "automatic_retry": False, "external_outcome_verified": False})
        return True
