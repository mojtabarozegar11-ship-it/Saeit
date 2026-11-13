"""The single deployable bot identity; former agents are internal work lanes.

An Agent database row records task ownership, not an independent AI product.
This module deliberately does not authorize remote deployment, spending,
trading, publishing, or automatic promotion of generated source code.
"""

BOT_CODE = "mojtaba-bot-ai"
from core.bot_identity import BOT_NAME

LEGACY_EXECUTOR_CODES = ("economic-master-agent", "moj_1ro_1")

# Historical Agent rows must not become simultaneous executable runtimes.
# Inventorying a row is not authorization to execute it.
EXECUTOR_RUNTIME_CODES = (BOT_CODE, *LEGACY_EXECUTOR_CODES)


def assert_single_executor(agent_model, expected_code):
    """Refuse a parallel or mismatched canonical/legacy worker identity.

    Called both before a task is claimed and immediately before a handler.
    This is a database-level safety gate, NOT proof that all host schedulers,
    cron jobs and external services have been consolidated.
    """
    if expected_code not in EXECUTOR_RUNTIME_CODES:
        return
    from django.core.exceptions import ImproperlyConfigured
    active = list(agent_model.objects.filter(
        active=True, code__in=EXECUTOR_RUNTIME_CODES
    ).values_list("code", flat=True).order_by("code"))
    if len(active) != 1:
        raise ImproperlyConfigured(
            "MOJTABA_RUNTIME_SINGLETON_REQUIRED"
        )
    if active[0] != expected_code:
        raise ImproperlyConfigured(
            "MOJTABA_RUNTIME_IDENTITY_MISMATCH"
        )


def unresolved_master_task_id(task_model, *, exclude_task_id=None):
    """Read-only barrier against subsequent work after an unknown effect.

    A completed source scan, owner approval, timeout, or exhausted retry
    budget does not prove that the preceding effect was rolled back.
    Keep both canonical and legacy audit records in this safety query.
    """
    # Do not let an old worker evade the safety barrier by accidentally
    # changing an uncertain task to queued/cancelled/completed. A dedicated
    # independently attested closure must explicitly clear the uncertainty.
    pending = task_model.objects.filter(
        agent__code__in=EXECUTOR_RUNTIME_CODES,
        attempt_count__gt=0,
        output_data__requires_review=True,
    )
    if exclude_task_id is not None:
        pending = pending.exclude(pk=exclude_task_id)
    return pending.order_by("pk").values_list("pk", flat=True).first()


ECONOMIC_CAPABILITY_PREFIX = "income_"
ECONOMIC_SPECIAL_CAPABILITIES = frozenset({"master_self_improvement"})
FACTORY_CAPABILITIES = frozenset({
    "factory_native_review", "factory_f41_private_build",
})
PORTFOLIO_CAPABILITIES = frozenset({"business_portfolio_review"})
CYBER_CAPABILITIES = frozenset({
    "cyber_evidence_review", "cyber_origin_defense", "cyber_incident_response",
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
    if code in PORTFOLIO_CAPABILITIES:
        return "business_portfolio"
    if code in CYBER_CAPABILITIES:
        return "cyber_security"
    if code in FACTORY_CAPABILITIES:
        return "private_factory"
    if is_economic_capability(code):
        return "economic_operations"
    return "unmapped_requires_adapter_review"
