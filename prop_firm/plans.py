"""Ten MOJ PROP business plans over one shared, audited challenge ruleset.

Plan 1 preserves the owner-confirmed 30 TRX / 100 USD model. Plans 2..10
are proposed differentiated *starting capital tiers*, with their own quoted
TRX fees. Prices are recommendations for review, NOT published checkout quotes,
real funding promises, or verified financial return. Every plan uses the SAME
28-day two-stage evaluation, at least 50 independently verified closed
positions, and the one Instagram plus one Facebook post held 28 days.

The owner declares Plan 1 funded and operational. This assertion is NOT an
independently audited bank/broker balance or proof of live customer checkout.
Plans 2-10 are explicitly on temporary funding hold, irrespective of how many
paper attestations become true. A buyer agreement must bind plan and fee.
"""
from dataclasses import dataclass
from decimal import Decimal

from .rules import LEVELS, POLICY

PLAN_PREFIX = "MOJ-PROP-"
ALL_PLANS_SELLABLE = False
OWNER_ACTIVE_STATUS = "owner_declared_active"
FUNDING_HOLD_STATUS = "funding_in_progress_temporary_inactive"


@dataclass(frozen=True)
class ChallengePlan:
    number: int
    code: str
    entry_fee_trx: Decimal
    starting_tier_index: int
    starting_capital_usd: Decimal
    maximum_capital_usd: Decimal
    duration_days: int
    minimum_verified_closed_trades: int
    min_trading_days_per_stage: int
    stage_one_profit_target_pct: Decimal
    stage_two_profit_target_pct: Decimal
    daily_loss_limit_pct: Decimal
    total_loss_limit_pct: Decimal
    max_consistency_pct: Decimal
    max_risk_per_trade_pct: Decimal
    max_open_risk_pct: Decimal
    trader_profit_share_pct: Decimal
    company_profit_share_pct: Decimal
    instagram_posts_per_challenge: int
    facebook_posts_per_challenge: int
    trader_bots_allowed: bool
    business_status: str
    capital_funded_owner_declared: bool
    business_active_owner_declared: bool
    temporary_owner_hold: bool
    funding_independently_verified: bool = False
    broker_live_account_independently_verified: bool = False
    checkout_enabled: bool = False
    account_activation_enabled: bool = False
    prices_approved_for_public_sale: bool = False


# Numbers are provisional except plan 1's owner-specified 30 TRX. Higher fees
# are internal proposed prices. Do not turn on customer billing using them.
PROPOSED_TIERS_AND_TRX = (
    (0, "30"), (1, "45"), (2, "75"), (3, "120"), (4, "200"),
    (5, "330"), (6, "500"), (7, "800"), (8, "1250"), (9, "2000"),
)


def _make_plan(number, starting_tier_index, fee):
    return ChallengePlan(
        number=number,
        code=f"{PLAN_PREFIX}{number:02d}",
        entry_fee_trx=Decimal(fee),
        starting_tier_index=starting_tier_index,
        starting_capital_usd=LEVELS[starting_tier_index],
        maximum_capital_usd=LEVELS[-1],
        duration_days=POLICY.completion_deadline_days,
        minimum_verified_closed_trades=POLICY.min_closed_trades_per_challenge,
        min_trading_days_per_stage=POLICY.min_challenge_days,
        stage_one_profit_target_pct=POLICY.phase_one_goal_pct,
        stage_two_profit_target_pct=POLICY.phase_two_goal_pct,
        daily_loss_limit_pct=POLICY.max_daily_loss_pct,
        total_loss_limit_pct=POLICY.max_total_loss_pct,
        max_consistency_pct=POLICY.best_day_share_pct,
        max_risk_per_trade_pct=POLICY.order_risk_pct,
        max_open_risk_pct=POLICY.aggregate_risk_pct,
        trader_profit_share_pct=POLICY.trader_profit_share_pct,
        company_profit_share_pct=POLICY.company_profit_share_pct,
        instagram_posts_per_challenge=1,
        facebook_posts_per_challenge=1,
        trader_bots_allowed=POLICY.trader_bots_allowed,
        business_status=(OWNER_ACTIVE_STATUS if number == 1 else FUNDING_HOLD_STATUS),
        capital_funded_owner_declared=(number == 1),
        business_active_owner_declared=(number == 1),
        temporary_owner_hold=(number > 1),
    )


CHALLENGE_PLANS = tuple(
    _make_plan(index, tier, fee)
    for index, (tier, fee) in enumerate(PROPOSED_TIERS_AND_TRX, start=1)
)
PLAN_BY_CODE = {plan.code: plan for plan in CHALLENGE_PLANS}
DEFAULT_PLAN_CODE = CHALLENGE_PLANS[0].code

if len(CHALLENGE_PLANS) != 10 or len(PLAN_BY_CODE) != 10:
    raise RuntimeError("MOJ PROP requires exactly ten unique plans")
if len({plan.starting_tier_index for plan in CHALLENGE_PLANS}) != 10:
    raise RuntimeError("Plan starting tiers cannot duplicate")
if CHALLENGE_PLANS[0].entry_fee_trx != POLICY.entry_trx:
    raise RuntimeError("Plan 1 historical 30 TRX price cannot drift")
if (sum(plan.business_active_owner_declared for plan in CHALLENGE_PLANS) != 1
        or any(plan.temporary_owner_hold for plan in CHALLENGE_PLANS[:1])
        or any(not plan.temporary_owner_hold for plan in CHALLENGE_PLANS[1:])):
    raise RuntimeError("Exactly owner-declared Plan 1 may be active")


def plan_for_code(code):
    """Exact trusted plan lookup; do not accept blank, number or lookalike code."""
    if type(code) is not str or code not in PLAN_BY_CODE:
        raise ValueError("Unknown or unapproved MOJ PROP plan code")
    return PLAN_BY_CODE[code]


def plan_public_summary(plan):
    """Safe PRE-LAUNCH catalog, with explicit non-sale state."""
    if not isinstance(plan, ChallengePlan) or PLAN_BY_CODE.get(plan.code) != plan:
        raise ValueError("Canonical plan record required")
    return {
        "number": plan.number,
        "code": plan.code,
        "starting_capital_usd": str(plan.starting_capital_usd),
        "starting_tier_index": plan.starting_tier_index,
        "maximum_capital_usd": str(plan.maximum_capital_usd),
        "fee_trx_proposed": str(plan.entry_fee_trx),
        "fee_is_final_for_sale": False,
        "business_status": plan.business_status,
        "capital_funded_owner_declared": plan.capital_funded_owner_declared,
        "business_active_owner_declared": plan.business_active_owner_declared,
        "temporary_owner_hold": plan.temporary_owner_hold,
        "funding_independently_verified": plan.funding_independently_verified,
        "broker_live_account_independently_verified": plan.broker_live_account_independently_verified,
        "duration_days": plan.duration_days,
        "minimum_trades": plan.minimum_verified_closed_trades,
        "bots_allowed": plan.trader_bots_allowed,
        "checkout_enabled": False,
        "real_funding_guaranteed": False,
    }
