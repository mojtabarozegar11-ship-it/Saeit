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

# Both roles are internal modules of the one canonical bot, not economic
# handlers. In particular, paid knowledge generation remains approval-gated.
EDITORIAL_CAPABILITIES = frozenset({
    "research-write-review", "content-editorial-draft",
})
KNOWLEDGE_TASK = ("knowledge_content_generation", "research-write-review")
# Private offline research ingestion is a module, NEVER an order-execution tool.
MOJTRADE_RESEARCH_CAPABILITY = "mojtrade_observation_ingest"
MOJTRADE_DEMO_AUDIT_CAPABILITY = "mojtrade_demo_audit_ingest"



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
    """Economic or unknown tasks; exclude only *known exact* specialist pairs.

    An unexpected/mismatched task still reaches the economic review blocker,
    rather than being silently hidden behind a broad editorial prefix.
    """
    from django.db.models import F, Q

    factory = (
        Q(capability_code__in=FACTORY_CAPABILITIES)
        & Q(action_type=F("capability_code"))
    )
    editorial = Q(
        action_type=KNOWLEDGE_TASK[0], capability_code=KNOWLEDGE_TASK[1],
    )
    mojtrade_research = Q(
        action_type=MOJTRADE_RESEARCH_CAPABILITY,
        capability_code=MOJTRADE_RESEARCH_CAPABILITY,
    )
    mojtrade_demo_audit = Q(
        action_type=MOJTRADE_DEMO_AUDIT_CAPABILITY,
        capability_code=MOJTRADE_DEMO_AUDIT_CAPABILITY,
    )
    return ~(factory | editorial | mojtrade_research | mojtrade_demo_audit)


def module_for_capability(code):
    if code == MOJTRADE_DEMO_AUDIT_CAPABILITY:
        return "mojtrade_demo_execution_evidence"
    if code == MOJTRADE_RESEARCH_CAPABILITY:
        return "mojtrade_private_research"
    if code == "research-write-review":
        return "knowledge_library"
    if code == "content-editorial-draft":
        return "content_editorial"
    if code in FACTORY_CAPABILITIES:
        return "private_factory"
    if is_economic_capability(code):
        return "economic_operations"
    return "unmapped_requires_adapter_review"
