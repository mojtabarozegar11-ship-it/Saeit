"""Canonical site capability dispatch using the shared bot runtime.

A cycle claim precedes network access, using the existing site audit schema.
Ambiguous attempts are never automatically repeated. No Agent, scheduler,
migration, model request or private worker is created.
"""
import json

from django.db import transaction
from ava_core.capabilities import ActionRequest
from core.models import Agent, AuditLog
from core.mojtaba_host_runtime import build_canonical_runtime
from core.mojtaba_site_adapter import site_capability
from core.mojtaba_site_fleet import SiteFleetError
from core.mojtaba_site_receipts import ACTION, ACTOR, CLAIM, CYCLE_ID, record_public_cycle


class SiteCycleClaims:
    """Preserve the site receipt protocol inside the canonical claim boundary."""
    def __init__(self, agent_id, cycle_id):
        self.agent_id = agent_id
        self.cycle_id = cycle_id

    def reserve(self, request, operation):
        if (request.owner_id != "agent-" + str(self.agent_id)
                or request.request_id != self.cycle_id
                or request.capability != "site_observability"
                or request.operation != "observe_public" or request.arguments
                or operation.name != "observe_public" or operation.effect != "read"):
            raise PermissionError("SITE_CLAIM_SCOPE_MISMATCH")
        with transaction.atomic(durable=True):
            agent = Agent.objects.select_for_update().filter(
                pk=self.agent_id, code=ACTOR, active=True).first()
            if agent is None:
                raise SiteFleetError("CANONICAL_AGENT_NOT_PROVISIONED")
            if AuditLog.objects.filter(actor_type="system", actor_id=ACTOR,
                    action__in=(CLAIM, ACTION), trace_id=self.cycle_id).exists():
                raise SiteFleetError("CYCLE_ALREADY_ATTEMPTED_RECONCILE_RECEIPTS")
            AuditLog.objects.create(actor_type="system", actor_id=ACTOR,
                action=CLAIM, target_type="Agent", target_id=str(agent.pk),
                trace_id=self.cycle_id, before_state={}, after_state={
                    "canonical_identity": ACTOR, "effect": "read",
                    "automatic_retry": False,
                })
        return True


def _no_model(_messages):
    raise PermissionError("SITE_OBSERVATION_HAS_NO_MODEL_CHANNEL")


def execute_site_cycle(cycle_id, *, transport=None):
    if not isinstance(cycle_id, str) or not CYCLE_ID.fullmatch(cycle_id):
        raise SiteFleetError("INVALID_CANONICAL_CYCLE_ID")
    agent = Agent.objects.filter(code=ACTOR, active=True).first()
    if agent is None:
        raise SiteFleetError("CANONICAL_AGENT_NOT_PROVISIONED")
    owner_id = "agent-" + str(agent.pk)
    runtime = build_canonical_runtime(
        agent_id=agent.pk, using="default", brain=_no_model, propose_goals=lambda _: (),
        capabilities=(site_capability(transport=transport),),
        claim_store=SiteCycleClaims(agent.pk, cycle_id),
        authorize_action=lambda owner, req, op: (
            owner == owner_id and req.request_id == cycle_id
            and req.capability == "site_observability" and req.operation == "observe_public"
            and op.effect == "read" and not req.arguments
        ))
    result = runtime.execute_action(ActionRequest(cycle_id, owner_id,
        "site_observability", "observe_public", {}))
    report = json.loads(result.result.detail)
    receipt = record_public_cycle(report, cycle_id=cycle_id)
    return {"canonical_bot": report["canonical_bot"], "cycle_id": cycle_id,
            "public_checks_count": report["public_checks_count"],
            "http_ok_count": report["http_ok_count"], "site_receipts": receipt["site_receipts"],
            "independent_runtime_attested": False, "legacy_retirement_authorized": False}
