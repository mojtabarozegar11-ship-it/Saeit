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
        if legacy.active or pending:
            raise RuntimeError("MOJTABA_LEGACY_HANDOFF_REQUIRED:" + legacy_code)
    return canonical
