"""Read-only, fail-closed ownership resolver for legacy Django agent modules.

Existing legacy rows, tasks, story receipts and schedulers MUST be reconciled
before operational cutover. This module neither migrates nor deletes records.
It only authorizes new work under the already provisioned canonical owner.
"""
from core.models import Agent, AgentTask
from core.unified_bot_identity import BOT_CODE

PENDING = ("queued", "running", "blocked")


def canonical_owner_for(legacy_code: str) -> Agent:
    if not legacy_code or legacy_code == BOT_CODE:
        raise ValueError("canonical handoff requires a distinct legacy module code")
    canonical = Agent.objects.filter(code=BOT_CODE, active=True).first()
    if canonical is None:
        raise RuntimeError("MOJTABA_CANONICAL_AGENT_NOT_PROVISIONED")
    legacy = Agent.objects.filter(code=legacy_code).first()
    if legacy is not None:
        pending = AgentTask.objects.filter(agent=legacy, status__in=PENDING).exists()
        # A retired newsletter agent may still own drafts, scheduled posts or
        # distribution retries. Preserve and reconcile those records before
        # routing new editorial work to the canonical bot.
        open_stories = legacy.newsletter_stories.filter(
            status__in=("draft", "review", "approved", "scheduled", "queued", "processing")
        ).exists()
        pending_delivery = legacy.newsletter_stories.filter(
            publications__status__in=("queued", "blocked")
        ).exists()
        if legacy.active or pending or open_stories or pending_delivery:
            raise RuntimeError("MOJTABA_LEGACY_HANDOFF_REQUIRED:" + legacy_code)
    return canonical

# Compatibility routing during migration. Old active roles remain operational
# until their exact handoff is evidenced; no new legacy identity is provisioned
# once canonical identity exists.
SPECIALIST_CODES = frozenset({
    "company-activity-intelligence", "knowledge-content-director",
    "content-director", "content-research", "core_research",
    "newsletter-specialist", "newsletter-company-news",
    "newsletter-world-watch", "newsletter-unit-reports",
})

def specialist_owner(legacy_code, *, defaults=None):
    from core.models import AuditLog
    if legacy_code not in SPECIALIST_CODES:
        raise ValueError("UNREGISTERED_SPECIALIST_LANE")
    canonical = Agent.objects.filter(code=BOT_CODE).first()
    legacy = Agent.objects.filter(code=legacy_code).first()
    receipt = None
    if legacy is not None:
        receipt = AuditLog.objects.filter(
            action="single_bot_live_handoff_verified", target_type="Agent",
            target_id=str(legacy.pk)
        ).order_by("-pk").first()
    if receipt is not None:
        state = receipt.after_state
        if (not isinstance(state, dict) or state.get("legacy_code") != legacy_code
                or state.get("canonical_bot_code") != BOT_CODE
                or any(state.get(k) is not True for k in (
                    "canonical_successor_runtime_verified", "external_legacy_schedulers_stopped",
                    "all_pending_tasks_reconciled", "historical_data_preserved", "rollback_ready"))
                or any(not isinstance(state.get(k), str) or not state[k].strip()
                       for k in ("live_inventory_receipt_id", "canonical_successor_receipt_id"))):
            raise RuntimeError("SPECIALIST_HANDOFF_RECEIPT_INVALID:" + legacy_code)
        owner = canonical_owner_for(legacy_code)
        if legacy_code == "knowledge-content-director" and not owner.capabilities.filter(
                code="research-write-review", active=True, risk_level="high").exists():
            raise RuntimeError("CANONICAL_KNOWLEDGE_CAPABILITY_REQUIRED")
        return owner
    if legacy is not None and legacy.active:
        return legacy
    if canonical is not None:
        raise RuntimeError("SPECIALIST_HANDOFF_REQUIRED_NO_LEGACY_REACTIVATION:" + legacy_code)
    if legacy is not None:
        return legacy
    if defaults is None:
        raise Agent.DoesNotExist("SPECIALIST_OWNER_NOT_PROVISIONED:" + legacy_code)
    legacy, _ = Agent.objects.get_or_create(code=legacy_code, defaults=defaults)
    return legacy
