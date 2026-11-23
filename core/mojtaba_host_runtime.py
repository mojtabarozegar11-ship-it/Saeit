"""Composition boundary for the single canonical Django-hosted bot.

Only trusted host code constructs this runtime. The caller supplies an already
authenticated canonical agent identifier, explicit database alias, and adapter
authorization. No model request, scheduler, grant, task or service is started
by constructing the runtime. Host authentication and shared database topology
remain deployment responsibilities.
"""
from ava_core import MojtabaBot
from core.models import Agent
from core.mojtaba_action_claims import DjangoCanonicalActionClaims
from core.unified_bot_identity import BOT_CODE


def build_canonical_runtime(*, agent_id, using, brain, propose_goals,
                            capabilities, authorize_action, claim_store=None,
                            enable_android_security_lab=False):
    if not isinstance(using, str) or not using.strip():
        raise ValueError("Explicit authoritative database alias required")
    if not callable(authorize_action):
        raise TypeError("Independent host action authorization required")
    if not Agent.objects.using(using).filter(pk=agent_id, code=BOT_CODE, active=True).exists():
        raise PermissionError("CANONICAL_AGENT_NOT_PROVISIONED")
    owner_id = "agent-" + str(agent_id)

    def authorize(owner, request, operation):
        return (owner == owner_id and request.owner_id == owner_id
                and Agent.objects.using(using).filter(
                    pk=agent_id, code=BOT_CODE, active=True).exists()
                and authorize_action(owner, request, operation) is True)

    # Explicit host-side opt-in only: public requests cannot register modules.
    if type(enable_android_security_lab) is not bool:
        raise TypeError("Security lab opt-in must be a host boolean")
    if enable_android_security_lab:
        from ava_core.android_security_lab import NAME, security_lab_capability
        if not isinstance(capabilities, tuple):
            raise TypeError("Capabilities must be a trusted tuple")
        if any(spec.name == NAME for spec, _ in capabilities):
            raise ValueError("Security lab already registered")
        capabilities = capabilities + (security_lab_capability(),)

    # Alternate claim stores are injected only by trusted host code, not by
    # a model or request. Existing site receipt protocol has its own store.
    store = (DjangoCanonicalActionClaims(owner_id=owner_id, using=using)
             if claim_store is None else claim_store)
    return MojtabaBot(owner_id=owner_id, brain=brain, propose_goals=propose_goals,
        capabilities=capabilities, authorize_action=authorize, action_claim_store=store)
