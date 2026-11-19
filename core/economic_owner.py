"""Single economic execution owner after a verified, recorded cutover.

Historical tasks retain their original agent foreign key. This routing layer
never grants capabilities or retires agents. A maintenance-window handoff
must record the exact transfer before canonical economic work can run.
"""
from django.db.models import Q
from core.models import Agent, AgentTask, AuditLog
from core.unified_bot_identity import BOT_CODE, economic_task_scope, non_factory_task_scope

LEGACY = "economic-master-agent"
CUTOVER = "canonical_economic_owner_transferred"
TERMINAL = ("completed", "failed", "cancelled")
ECONOMIC_CODES = frozenset({
    "income_market_research", "income_opportunity_score", "income_offer_design",
    "income_mvp_build", "income_growth_experiment", "income_revenue_verify",
    "income_profit_optimize", "master_self_improvement",
})

def economic_owner_code():
    old = Agent.objects.filter(code=LEGACY).first()
    bot = Agent.objects.filter(code=BOT_CODE, active=True).first()
    if old is None:
        return LEGACY
    receipt = AuditLog.objects.filter(
        action=CUTOVER, target_type="Agent", target_id=str(old.pk)
    ).order_by("-pk").first()
    if receipt is None:
        return LEGACY
    state = receipt.after_state
    if (bot is None or old.active or not isinstance(state, dict)
            or state.get("legacy_code") != LEGACY
            or state.get("canonical_code") != BOT_CODE
            or state.get("canonical_agent_id") != bot.pk
            or state.get("legacy_schedulers_stopped") is not True
            or AgentTask.objects.filter(agent=old).exclude(status__in=TERMINAL).exists()
            or not ECONOMIC_CODES.issubset(set(bot.capabilities.filter(active=True).values_list("code", flat=True)))):
        # An observed cutover with contradictory current state is not a reason
        # to silently resume the old executor or route work to a different bot.
        raise RuntimeError("ECONOMIC_CUTOVER_STATE_REQUIRES_RECONCILIATION")
    return BOT_CODE

def economic_queue(owner_code=None):
    code = economic_owner_code() if owner_code is None else owner_code
    rows = AgentTask.objects.filter(agent__code=code, agent__active=True)
    if code == BOT_CODE:
        rows = rows.filter(non_factory_task_scope())
    return rows

def economic_history(owner_code=None):
    code = economic_owner_code() if owner_code is None else owner_code
    if code == LEGACY:
        return AgentTask.objects.filter(agent__code=LEGACY)
    return AgentTask.objects.filter(Q(agent__code=BOT_CODE) |
        Q(agent__code=LEGACY, status__in=TERMINAL)).filter(economic_task_scope())
