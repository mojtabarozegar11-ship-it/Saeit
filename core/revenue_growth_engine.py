"""Fail-closed revenue-growth priorities for the Economic Master Agent.

This module plans *one* next commercial action from a measured funnel.  It
does not execute publication, outreach, payments, purchases or deployments.
Input values must come from separately audited systems; caller-supplied counts
alone never constitute evidence of settled cash.
"""

from decimal import Decimal, InvalidOperation


def _count(snapshot, field):
    value = snapshot.get(field)
    if type(value) is not int or value < 0:
        raise ValueError(f"{field}_requires_verified_nonnegative_integer")
    return value


def _money(snapshot, field):
    value = snapshot.get(field)
    if value is None or isinstance(value, bool) or isinstance(value, float):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def _decision(action, reason, *, metrics, evidence_required, external=False):
    return {
        "next_action": action,
        "reason": reason,
        "metrics": metrics,
        "evidence_required": evidence_required,
        "external_write_requires_owner_approval": external,
        "purchase_permitted": False,
        "deployment_permitted": False,
        "revenue_growth_executed": False,
    }


def prioritize_revenue_growth(snapshot):
    """Rank next work from a *measured* funnel, never assert phantom revenue.

    Required counts: sellable_offers, qualified_leads, paid_orders,
    delivered_orders.  Required booleans: checkout_verified,
    delivery_verified, settlement_evidence_verified.  Money fields are
    required only when independently settled receipts can be proven.

    ``settled_revenue`` is the reconciled period amount, not a webhook total.
    ``operating_costs``, ``committed_costs`` and ``protected_reserve`` must
    cover that same period before any available surplus is reported.
    """
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot_must_be_a_dictionary")
    counts = {name: _count(snapshot, name) for name in (
        "sellable_offers", "qualified_leads", "paid_orders", "delivered_orders",
    )}
    for name in ("checkout_verified", "delivery_verified", "settlement_evidence_verified"):
        if type(snapshot.get(name)) is not bool:
            raise ValueError(f"{name}_requires_verified_boolean")
    if counts["delivered_orders"] > counts["paid_orders"]:
        raise ValueError("delivered_orders_exceed_paid_orders")

    metrics = {
        **counts,
        "settled_revenue": None,
        "operating_surplus_after_commitments_and_reserve": None,
        "cost_coverage_verified": False,
    }
    if counts["paid_orders"] > counts["delivered_orders"]:
        return _decision(
            "fulfill_paid_orders", "paid_orders_waiting_for_verified_delivery",
            metrics=metrics, evidence_required="delivery_receipts_for_open_orders",
        )
    if not snapshot["checkout_verified"]:
        return _decision(
            "repair_and_verify_checkout", "purchase_path_not_proven_working",
            metrics=metrics, evidence_required="live_end_to_end_checkout_and_payment_server_receipt",
        )
    if counts["sellable_offers"] == 0:
        return _decision(
            "complete_sellable_offer", "no_customer_ready_offer_verified",
            metrics=metrics, evidence_required="real_product_delivery_price_and_approved_listing",
            external=True,
        )
    if not snapshot["delivery_verified"]:
        return _decision(
            "repair_and_verify_delivery", "customer_delivery_path_not_proven",
            metrics=metrics, evidence_required="delivery_receipt_and_email_recovery_check",
        )
    if counts["paid_orders"] and not snapshot["settlement_evidence_verified"]:
        return _decision(
            "reconcile_settled_receipts", "paid_order_is_not_independently_settled_cash",
            metrics=metrics, evidence_required="independent_provider_finality_and_order_match",
        )

    if snapshot["settlement_evidence_verified"]:
        cash = _money(snapshot, "settled_revenue")
        costs = _money(snapshot, "operating_costs")
        commitments = _money(snapshot, "committed_costs")
        reserve = _money(snapshot, "protected_reserve")
        if any(number is None for number in (cash, costs, commitments, reserve)):
            return _decision(
                "reconcile_operating_cashflow", "cashflow_incomplete_or_untrusted",
                metrics=metrics, evidence_required="settled_receipts_costs_commitments_and_protected_reserve",
            )
        surplus = cash - costs - commitments - reserve
        metrics.update({
            "settled_revenue": str(cash),
            "operating_surplus_after_commitments_and_reserve": str(surplus),
            "cost_coverage_verified": cash >= costs + commitments + reserve,
        })

    if counts["qualified_leads"] == 0:
        return _decision(
            "prepare_qualified_customer_acquisition", "no_qualified_customer_demand_proven",
            metrics=metrics, evidence_required="consented_lead_and_channel_conversion_records",
            external=True,
        )
    if counts["paid_orders"] == 0:
        return _decision(
            "improve_lead_to_purchase_conversion", "qualified_demand_without_paid_orders",
            metrics=metrics, evidence_required="qualified_leads_purchases_and_funnel_dropoff",
        )
    if not snapshot["settlement_evidence_verified"]:
        return _decision(
            "verify_cash_receipts", "revenue_has_no_independent_settlement_proof",
            metrics=metrics, evidence_required="independent_payment_finality_reconciliation",
        )
    if not metrics["cost_coverage_verified"]:
        return _decision(
            "increase_net_cashflow_before_expansion", "verified_cash_does_not_cover_all_commitments_and_reserve",
            metrics=metrics, evidence_required="new_reconciled_sales_and_cost_savings",
        )
    return _decision(
        "scale_proven_offer_without_new_spend", "self_funded_core_operations_verified",
        metrics=metrics, evidence_required="repeat_purchases_conversion_and_margin_by_offer",
        external=True,
    )
