"""Conservative 40% development-allocation gate for Mojtaba.bot.

All figures must describe one reconciled accounting period in one currency.
This checks whether a proposed expense may be *submitted for owner approval*;
it does not authorize payment, purchase, renewal or deployment.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


MAX_DEVELOPMENT_REVENUE_SHARE = Decimal("0.40")


@dataclass(frozen=True)
class DevelopmentBudgetDecision:
    eligible_for_owner_approval: bool
    reason: str
    maximum_from_revenue: str | None
    available_surplus_before_development: str | None
    remaining_development_budget: str | None
    payment_authorized: bool = False


def _amount(value):
    if value is None or isinstance(value, (bool, float)):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def assess_development_budget(*, accounting_period, currency,
                              provider_reconciliation_verified,
                              cost_records_verified, settled_revenue,
                              operating_expenses, existing_commitments,
                              protected_reserves, development_spend_to_date,
                              proposed_development_cost):
    """Enforce min(40% of collected revenue, cash surplus) less prior spending.

    The amount proposed must include taxes, setup and binding running-cost
    commitments. Previously approved development spend in the same accounting
    period counts against the 40% cap. Income from unsettled orders, forecasts,
    simulated trades or token price changes is excluded by the reconciliation
    prerequisite; callers must separately verify the underlying evidence.
    """
    def blocked(reason, revenue_cap=None, surplus=None, remaining=None):
        return DevelopmentBudgetDecision(False, reason, revenue_cap, surplus, remaining)

    if not isinstance(accounting_period, str) or not accounting_period.strip():
        return blocked("accounting_period_required")
    if not isinstance(currency, str) or not currency.strip():
        return blocked("single_accounting_currency_required")
    if provider_reconciliation_verified is not True:
        return blocked("independent_settlement_reconciliation_required")
    if cost_records_verified is not True:
        return blocked("verified_operating_costs_and_commitments_required")

    amounts = tuple(map(_amount, (
        settled_revenue, operating_expenses, existing_commitments,
        protected_reserves, development_spend_to_date, proposed_development_cost,
    )))
    if any(value is None for value in amounts):
        return blocked("invalid_missing_or_negative_financial_amount")

    income, costs, commitments, reserve, spent, proposal = amounts
    revenue_cap = income * MAX_DEVELOPMENT_REVENUE_SHARE
    available = max(Decimal(0), income - costs - commitments - reserve)
    total_cap = min(revenue_cap, available)
    remaining = max(Decimal(0), total_cap - spent)
    cap, surplus, free = str(revenue_cap), str(available), str(remaining)

    if spent > total_cap:
        return blocked("prior_development_spend_exceeds_allowed_budget", cap, surplus, free)
    if proposal <= 0:
        return blocked("proposed_cost_must_be_positive", cap, surplus, free)
    if proposal > remaining:
        return blocked("proposed_cost_exceeds_40_percent_or_free_surplus", cap, surplus, free)
    return DevelopmentBudgetDecision(
        eligible_for_owner_approval=True,
        reason="within_self_funded_development_cap_pending_specific_owner_approval",
        maximum_from_revenue=cap,
        available_surplus_before_development=surplus,
        remaining_development_budget=free,
        payment_authorized=False,
    )
