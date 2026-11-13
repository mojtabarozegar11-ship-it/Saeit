"""Internal capabilities of the ONLY bot: mojtaba.bot.ai.

This is a Python module registry, not an Agent/worker/scheduler registry.
The central control plane must explicitly call a capability and provide trusted
authorization before any evidence can be reviewed.
"""
from .cyber_security import BOT_ID, MODULE_ID, descriptor, review_offline_evidence


def registered_capabilities() -> dict:
    """Static read-only catalogue owned by the canonical bot."""
    return {MODULE_ID: descriptor()}


__all__ = ["BOT_ID", "MODULE_ID", "descriptor", "registered_capabilities",
           "review_offline_evidence"]
