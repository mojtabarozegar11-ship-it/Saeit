"""Internal capabilities of the ONLY bot: mojtaba.bot.ai.

This is a Python capability registry, not an Agent/worker/scheduler registry.
The central control plane explicitly invokes approved capabilities.
"""
from .cyber_security import BOT_ID, MODULE_ID, descriptor, review_offline_evidence
from .origin_defense import plan_origin_defense
from .incident_response import plan_incident_response


def registered_capabilities() -> dict:
    """One canonical bot, one cyber capability, multiple internal functions."""
    cyber = descriptor()
    cyber["submodules"] = {
        "origin_defense": {
            "mode": "offline_recommendations_only",
            "network_access": False,
            "automatic_blocking": False,
            "hack_back": False,
            "requires_canonical_authorization": True,
        },
        "incident_response": {
            "mode": "offline_plan_only",
            "network_access": False,
            "automatic_destructive_actions": False,
            "data_export": False,
            "backup_restore_execution": False,
            "requires_canonical_authorization": True,
        },
    }
    return {MODULE_ID: cyber}


__all__ = ["BOT_ID", "MODULE_ID", "descriptor", "registered_capabilities",
           "review_offline_evidence", "plan_origin_defense", "plan_incident_response"]
