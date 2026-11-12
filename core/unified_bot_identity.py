"""The single deployable bot identity; former agents are internal work lanes.

An Agent database row records task ownership, not an independent AI product.
This module deliberately does not authorize remote deployment, spending,
trading, publishing, or automatic promotion of generated source code.
"""

BOT_CODE = "mojtaba-bot-ai"
from core.bot_identity import BOT_NAME

LEGACY_EXECUTOR_CODES = ("economic-master-agent", "moj_1ro_1")

ECONOMIC_CAPABILITY_PREFIX = "income_"
ECONOMIC_SPECIAL_CAPABILITIES = frozenset({"master_self_improvement"})
FACTORY_CAPABILITIES = frozenset({
    "factory_native_review", "factory_f41_private_build",
})


def is_economic_capability(code):
    return str(code).startswith(ECONOMIC_CAPABILITY_PREFIX) or code in ECONOMIC_SPECIAL_CAPABILITIES


def economic_task_scope():
    """Include unregistered income work in economic blockers, not factory work."""
    from django.db.models import Q

    return (
        Q(capability_code__startswith=ECONOMIC_CAPABILITY_PREFIX)
        | Q(capability_code__in=ECONOMIC_SPECIAL_CAPABILITIES)
        | Q(action_type__startswith=ECONOMIC_CAPABILITY_PREFIX)
        | Q(action_type__in=ECONOMIC_SPECIAL_CAPABILITIES)
    )


def non_factory_task_scope():
    """Known factory tasks are separate; unknown work must not vanish from audits."""
    from django.db.models import F, Q

    return ~(
        Q(capability_code__in=FACTORY_CAPABILITIES)
        & Q(action_type=F("capability_code"))
    )


def module_for_capability(code):
    if code in FACTORY_CAPABILITIES:
        return "private_factory"
    if is_economic_capability(code):
        return "economic_operations"
    return "unmapped_requires_adapter_review"
