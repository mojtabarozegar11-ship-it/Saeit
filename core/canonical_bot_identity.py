"""Single-runtime identity gate for Mojtaba.bot.ai.

Legacy database rows may remain during a verified handoff, but two active
runtime identities are never accepted by a worker.
"""
from django.core.exceptions import ImproperlyConfigured

CANONICAL_BOT_ID = "mojtaba.bot.ai"
CANONICAL_BOT_CODE = "mojtaba-bot-ai"
LEGACY_RUNTIME_ALIASES = ("economic-master-agent",)
RUNTIME_CODES = (CANONICAL_BOT_CODE, *LEGACY_RUNTIME_ALIASES)


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
