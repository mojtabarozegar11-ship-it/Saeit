"""Register the two-site observer as an internal capability of Mojtaba.bot.ai.
No independent agent, scheduler, publication, or financial actions are created.
Host applications must explicitly supply the capability to the existing runtime.
"""
import json
from ava_core.capabilities import AdapterResult, CapabilitySpec, OperationSpec
from core.mojtaba_site_fleet import CANONICAL_BOT, inventory, run_one_bot_public_cycle
from mojtaba_identity import BOT_ID

SITE_CAPABILITY = CapabilitySpec("site_observability", (
    OperationSpec("inventory", "local"), OperationSpec("observe_public", "read"),
))

def site_capability(*, transport=None):
    """Return one host-registerable capability; no network at registration."""
    if CANONICAL_BOT != BOT_ID:
        raise RuntimeError("canonical identity mismatch")

    def execute(request):
        if request.capability != SITE_CAPABILITY.name or request.arguments:
            raise ValueError("Only declared zero-argument site operations accepted")
        if request.operation == "inventory":
            report = inventory()
            success = True
        elif request.operation == "observe_public":
            report = run_one_bot_public_cycle(transport=transport)
            success = report["http_ok_count"] == report["public_checks_count"] == 14
        else:
            raise ValueError("Unsupported site operation")
        if report.get("canonical_bot") != BOT_ID:
            raise RuntimeError("canonical identity mismatch")
        # A report is a declared observation, not a deployment or revenue receipt.
        return AdapterResult(success, json.dumps(report, ensure_ascii=False, sort_keys=True))

    return SITE_CAPABILITY, execute
