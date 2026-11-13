"""Single-runtime identity gate for Mojtaba.bot.ai.

Legacy database rows may remain during a verified handoff, but two active
runtime identities are never accepted by a worker.
"""
from django.core.exceptions import ImproperlyConfigured

CANONICAL_BOT_ID = "mojtaba.bot.ai"
CANONICAL_BOT_CODE = "mojtaba-bot-ai"
LEGACY_RUNTIME_ALIASES = ("economic-master-agent",)
KNOWN_NONCANONICAL_CODES = (
    "economic-master-agent",
    "moj_1ro_1",
    "content-director",
    "knowledge-content-director",
    "core_research",
    "newsletter-specialist",
    "newsletter-company-news",
    "newsletter-world-watch",
    "newsletter-unit-reports",
    "company-activity-intelligence",
    "content-research",
)
RUNTIME_CODES = (CANONICAL_BOT_CODE, *LEGACY_RUNTIME_ALIASES)
AUDIT_CODES = (CANONICAL_BOT_CODE, *KNOWN_NONCANONICAL_CODES)


def resolve_single_active_agent(agent_model):
    """Return the sole active canonical/legacy runtime row, or fail closed."""
    rows = list(
        agent_model.objects.filter(
            code__in=RUNTIME_CODES,
            active=True,
        ).order_by("code")
    )
    if len(rows) > 1:
        raise ImproperlyConfigured("CANONICAL_BOT_MULTIPLE_ACTIVE")
    return rows[0] if rows else None

def audit_identity_rows(agent_model):
    """Return a read-only identity census; never authorizes mutation."""
    rows = list(
        agent_model.objects.filter(code__in=AUDIT_CODES).order_by("code")
    )
    active = [row.code for row in rows if row.active]
    if len(active) == 0:
        status = "no_known_active_runtime_identity"
    elif active == [CANONICAL_BOT_CODE]:
        status = "canonical_only"
    elif len(active) == 1 and active[0] in KNOWN_NONCANONICAL_CODES:
        status = "single_legacy_identity_requires_handoff"
    else:
        status = "parallel_identities_blocked"
    return {
        "canonical_bot_id": CANONICAL_BOT_ID,
        "canonical_bot_code": CANONICAL_BOT_CODE,
        "known_codes": list(AUDIT_CODES),
        "registered_rows": [
            {"code": row.code, "active": bool(row.active)} for row in rows
        ],
        "active_codes": active,
        "active_count": len(active),
        "status": status,
        "live_scheduler_attested": False,
        "retirement_authorized": False,
    }
