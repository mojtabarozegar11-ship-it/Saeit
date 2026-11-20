"""Transfer the economic lane only after independent live handoff and exact owner grant.
No new spending, task executions, factory commands or destructive record deletion.
Requires a stopped legacy scheduler and drained predecessor before DB transition.
"""
import json
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from core.approval import ApprovalService
from core.chat_operation_security import is_authorized_chat_operator
from core.models import Agent, AgentTask, AuditLog, ApprovalGrant
from core.economic_owner import LEGACY, CUTOVER, ECONOMIC_CODES, TERMINAL
from core.unified_bot_identity import BOT_CODE

HANDOFF = "single_bot_live_handoff_verified"
REQUIRED = ("canonical_successor_runtime_verified", "external_legacy_schedulers_stopped",
            "all_pending_tasks_reconciled", "historical_data_preserved", "rollback_ready")

def transfer(grant_id, receipt_id):
    with transaction.atomic(durable=True):
        agents = {a.code:a for a in Agent.objects.select_for_update().filter(
            code__in=(LEGACY,BOT_CODE)).order_by("pk")}
        old, bot = agents.get(LEGACY), agents.get(BOT_CODE)
        if not old or not bot or not old.active or not bot.active:
            raise CommandError("ECONOMIC_HANDOFF_REQUIRES_ACTIVE_PREDECESSOR_AND_SUCCESSOR")
        if AuditLog.objects.filter(action=CUTOVER,target_type="Agent",target_id=str(old.pk)).exists():
            raise CommandError("ECONOMIC_HANDOFF_ALREADY_RECORDED")
        receipt = AuditLog.objects.filter(pk=receipt_id, action=HANDOFF,
            target_type="Agent",target_id=str(old.pk),
            created_at__gte=timezone.now()-timedelta(hours=24)).first()
        state = receipt.after_state if receipt else {}
        if (not isinstance(state,dict) or state.get("legacy_code") != LEGACY
                or state.get("canonical_bot_code") != BOT_CODE
                or any(state.get(k) is not True for k in REQUIRED)
                or any(not isinstance(state.get(k),str) or not state[k].strip()
                       for k in ("live_inventory_receipt_id","canonical_successor_receipt_id"))):
            raise CommandError("ECONOMIC_HANDOFF_LIVE_EVIDENCE_REQUIRED")
        grants = ApprovalGrant.objects.select_for_update().select_related("approval","actor")
        grant = grants.filter(pk=grant_id).first()
        if (not grant or not is_authorized_chat_operator(grant.actor)
                or grant.actor_id != grant.approval.requested_by_id
                or grant.approval.status != "approved"
                or grant.approval.action_type != "merge_legacy_executor"
                or grant.approval.target_type != "Agent"
                or grant.approval.target_id != str(old.pk)):
            raise CommandError("ECONOMIC_HANDOFF_EXACT_OWNER_GRANT_REQUIRED")
        if AgentTask.objects.filter(agent=old).exclude(status__in=TERMINAL).exists():
            raise CommandError("ECONOMIC_HANDOFF_PENDING_TASKS_MUST_BE_RECONCILED")
        if old.newsletter_stories.exclude(status__in=("published","rejected","cancelled")).exists() or (
            old.newsletter_stories.filter(publications__status__in=("queued","blocked")).exists()):
            raise CommandError("ECONOMIC_HANDOFF_PENDING_PUBLICATION")
        caps = list(old.capabilities.filter(active=True))
        if {c.code for c in caps} != ECONOMIC_CODES:
            raise CommandError("ECONOMIC_HANDOFF_CAPABILITY_SET_MISMATCH")
        try:
            ApprovalService().authorize_grant(grant_id, {"action":"merge_legacy_executor",
                "agent_code":LEGACY,"canonical_bot_code":BOT_CODE,
                "live_handoff_receipt":receipt.trace_id})
        except ValueError as exc:
            raise CommandError("ECONOMIC_HANDOFF_GRANT_REJECTED") from exc
        bot.capabilities.add(*caps)
        old.active = False
        old.save(update_fields=["active","updated_at"])
        audit = AuditLog.objects.create(actor_type="system",actor_id=BOT_CODE,
            action=CUTOVER,target_type="Agent",target_id=str(old.pk),
            trace_id="economic-handoff-"+str(grant.pk),
            before_state={"legacy_active":True},after_state={
                "legacy_code":LEGACY,"canonical_code":BOT_CODE,
                "canonical_agent_id":bot.pk,"legacy_schedulers_stopped":True,
                "live_handoff_receipt":receipt.trace_id,"grant_id":grant.pk,
                "historical_tasks_preserved":AgentTask.objects.filter(agent=old).count(),
                "capabilities":sorted(ECONOMIC_CODES)})
    return {"canonical_code":BOT_CODE,"retired_database_record":LEGACY,
            "audit_id":audit.pk,"tasks_deleted":0,"factory_started":False,
            "live_runtime_independently_verified_by_command":False}

class Command(BaseCommand):
    help = "Explicitly transfer the drained economic lane on a verified maintenance-window handoff."
    def add_arguments(self,parser):
        parser.add_argument("--approval-grant-id",type=int,required=True)
        parser.add_argument("--handoff-receipt-id",type=int,required=True)
        parser.add_argument("--confirm-maintenance-window",action="store_true")
    def handle(self,*args,**options):
        if not options["confirm_maintenance_window"]:
            raise CommandError("ECONOMIC_HANDOFF_MAINTENANCE_WINDOW_REQUIRED")
        self.stdout.write(json.dumps(transfer(options["approval_grant_id"],options["handoff_receipt_id"]),sort_keys=True))
