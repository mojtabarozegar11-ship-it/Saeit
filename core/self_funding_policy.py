"""Fail-closed gate for funding the agent's own operating costs.

This authorizes a decision only; a separately configured payment executor must
perform the transaction and return settlement evidence. No credentials or
payment destination are stored here.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class ExpenseDecision:
    allowed: bool
    reason: str


def _money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def authorize_operating_expense(*, settled_cash, protected_reserves,
                                monthly_budget, month_to_date_spend,
                                amount, vendor, approved_vendors,
                                expense_type, subscription_active=True,
                                usage_evidence=False, roi_evidence=False):
    """Authorize only budgeted spend from collected cash, with a reserve intact."""
    cash, reserves, budget, spent, cost = map(_money, (
        settled_cash, protected_reserves, monthly_budget,
        month_to_date_spend, amount,
    ))
    if any(value is None for value in (cash, reserves, budget, spent, cost)):
        return ExpenseDecision(False, "invalid_or_negative_money_value")
    if not vendor or vendor not in set(approved_vendors or ()):
        return ExpenseDecision(False, "vendor_not_allowlisted")
    if expense_type not in {"infrastructure", "business_software", "subscription"}:
        return ExpenseDecision(False, "expense_type_out_of_scope")
    if cost <= 0:
        return ExpenseDecision(False, "amount_must_be_positive")
    if cash - cost < reserves:
        return ExpenseDecision(False, "would_spend_protected_reserve_or_unsettled_cash")
    if spent + cost > budget:
        return ExpenseDecision(False, "monthly_budget_exceeded")
    if expense_type == "subscription" and not (subscription_active and usage_evidence and roi_evidence):
        return ExpenseDecision(False, "subscription_requires_active_use_and_roi_evidence")
    return ExpenseDecision(True, "within_preapproved_self_funding_policy")
