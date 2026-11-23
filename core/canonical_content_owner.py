"""Single canonical content ownership: no legacy worker self-activation.

Weather and newsroom workers are capabilities of Mojtaba.bot.ai, not independent
Agent identities. A missing/disabled canonical owner must hold work rather
than silently creating or reviving a legacy agent.
"""
from __future__ import annotations

CANONICAL_AGENT_CODE = "mojtaba-bot-ai"


def require_canonical_content_owner():
    from .models import Agent

    owner = Agent.objects.filter(code=CANONICAL_AGENT_CODE, active=True).first()
    if owner is None:
        raise RuntimeError("CANONICAL_CONTENT_OWNER_NOT_ACTIVE")
    return owner
