"""Canonical site capability dispatch using the existing Django audit ledger.

A committed cycle claim precedes network access. Ambiguous attempts are never
automatically repeated. No Agent, scheduler, migration or private worker is created.
"""
import json
from django.db import transaction
from ava_core.capabilities import ActionRequest, CapabilityHub
from core.models import Agent, AuditLog
from core.mojtaba_site_adapter import site_capability
from core.mojtaba_site_fleet import SiteFleetError
from core.mojtaba_site_receipts import ACTION, ACTOR, CYCLE_ID, record_public_cycle

CLAIM = "mojtaba_site_cycle_claimed"

def execute_site_cycle(cycle_id, *, transport=None):
    if not isinstance(cycle_id, str) or not CYCLE_ID.fullmatch(cycle_id):
        raise SiteFleetError("INVALID_CANONICAL_CYCLE_ID")
    with transaction.atomic():
        agent = Agent.objects.select_for_update().filter(code=ACTOR, active=True).first()
        if agent is None:
            raise SiteFleetError("CANONICAL_AGENT_NOT_PROVISIONED")
        if AuditLog.objects.filter(actor_type="system", actor_id=ACTOR,
                    action__in=(CLAIM, ACTION), trace_id=cycle_id).exists():
            raise SiteFleetError("CYCLE_ALREADY_ATTEMPTED_RECONCILE_RECEIPTS")
        AuditLog.objects.create(actor_type="system", actor_id=ACTOR,
            action=CLAIM, target_type="Agent", target_id=str(agent.pk),
            trace_id=cycle_id, before_state={}, after_state={
                "canonical_identity": ACTOR, "effect": "read",
                "automatic_retry": False,
            })
        owner_id = "agent-" + str(agent.pk)
    # This trusted operator entrypoint authorizes precisely the claimed bounded
    # public observation. No caller-supplied target, model call or financial action.
    hub = CapabilityHub(owner_id=owner_id, authorize=lambda owner, req, op: (
        owner == owner_id and req.request_id == cycle_id
        and req.capability == "site_observability" and req.operation == "observe_public"
        and op.effect == "read" and not req.arguments
    ))
    hub.register(*site_capability(transport=transport))
    result = hub.execute(ActionRequest(cycle_id, owner_id,
        "site_observability", "observe_public", {}))
    report = json.loads(result.result.detail)
    receipt = record_public_cycle(report, cycle_id=cycle_id)
    return {"canonical_bot": report["canonical_bot"], "cycle_id": cycle_id,
            "public_checks_count": report["public_checks_count"],
            "http_ok_count": report["http_ok_count"], "site_receipts": receipt["site_receipts"],
            "independent_runtime_attested": False, "legacy_retirement_authorized": False}
