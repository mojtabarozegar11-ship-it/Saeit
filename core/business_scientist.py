"""Evidence-driven economic analysis for the Zomorod/MojPlayWin portfolio.

This module computes only quantities supported by source records. It refuses to
turn orders, payment intents, estimates, or unknown costs into realized profit.
"""
from decimal import Decimal, InvalidOperation
from typing import Mapping

from core.business_management import review_business


BUSINESS_SCIENTIST_PROFILE = {
    "code": "business-scientist-professor",
    "title": "Virtual Chief Economist and Business Scientist",
    "mandate": (
        "Allocate attention to the binding constraint on verified customer "
        "outcomes and sustainable contribution across Zomorod Melal and MojPlayWin."
    ),
    "disciplines": [
        "strategy and competitive positioning",
        "customer discovery and demand validation",
        "marketing and sales conversion",
        "product and service design",
        "production quality and delivery",
        "finance and unit economics",
        "technology and operating reliability",
        "people, roles, and incentives",
        "risk, security, and compliance",
        "measurement and organizational learning",
    ],
}


def evaluate_unit_economics(
    *, currency, settled_cash, refunds, provider_fees, fulfillment_costs,
    acquisition_cost, new_customers,
) -> dict:
    """Compute realized contribution only from a complete, single-currency ledger."""
    inputs = {
        "settled_cash": settled_cash,
        "refunds": refunds,
        "provider_fees": provider_fees,
        "fulfillment_costs": fulfillment_costs,
        "acquisition_cost": acquisition_cost,
        "new_customers": new_customers,
    }
    missing = [name for name, value in inputs.items() if value is None]
    if not currency or missing:
        return {
            "state": "not_computable",
            "currency": currency,
            "missing_inputs": missing + (["currency"] if not currency else []),
            "reason": "A reconciled same-currency cash and cost ledger is required.",
        }
    try:
        cash = _decimal(settled_cash)
        refunds_d = _decimal(refunds)
        fees = _decimal(provider_fees)
        fulfillment = _decimal(fulfillment_costs)
        acquisition = _decimal(acquisition_cost)
        customers = int(new_customers)
    except (InvalidOperation, ValueError, TypeError):
        return {"state": "invalid_input", "currency": currency, "reason": "Amounts must be numeric and customer count must be an integer."}
    if min(cash, refunds_d, fees, fulfillment, acquisition) < 0 or customers < 0:
        return {"state": "invalid_input", "currency": currency, "reason": "Amounts and customer count cannot be negative."}
    contribution = cash - refunds_d - fees - fulfillment - acquisition
    return {
        "state": "computed_from_complete_inputs",
        "currency": currency,
        "settled_cash": str(cash),
        "contribution": str(contribution),
        "contribution_margin": str(contribution / cash) if cash else None,
        "customer_acquisition_cost": str(acquisition / customers) if customers else None,
        "new_customers": customers,
        "profitable": contribution > 0,
        "formula": "settled_cash - refunds - provider_fees - fulfillment_costs - acquisition_cost",
    }


def build_business_science_plan(metrics: Mapping[str, dict]) -> dict:
    """Diagnose observed operating facts and report which economic decisions are blocked."""
    review = review_business(metrics)
    value = lambda key: _metric_value(metrics.get(key))
    blocked = value("blocked_tasks")
    queued = value("queued_tasks")
    products = value("active_products")
    orders = value("orders")
    approvals = value("pending_approvals")

    # A missing sensor is a data-collection problem, not proof of a business
    # failure. Select a diagnosis only from directly observed operating facts.
    if isinstance(blocked, int) and blocked > 0:
        diagnosis = {
            "code": "blocked_work",
            "fact": f"{blocked} tasks are recorded as blocked in the Django database.",
            "decision": "Classify the blocker and its required evidence or approval; do not bypass it or clone the task.",
            "measure": "blocked_task_count_and_age_by_action",
        }
    elif isinstance(queued, int) and queued > 0:
        diagnosis = {
            "code": "queued_work",
            "fact": f"{queued} tasks are recorded as queued; throughput and queue age must be checked by action.",
            "decision": "Compare queued, running, completed, failed, and retry counts by action before changing capacity.",
            "measure": "stage_throughput_and_oldest_queue_age_by_action",
        }
    elif isinstance(products, int) and products > 0 and orders == 0:
        diagnosis = {
            "code": "unmeasured_product_funnel",
            "fact": f"{products} active products and zero orders are recorded in this database.",
            "decision": "Instrument visits, product views, checkout starts, payment outcomes, and fulfillment before changing price or increasing traffic.",
            "measure": "timestamped_funnel_counts_by_product_and_source",
        }
    elif isinstance(approvals, int) and approvals > 0:
        diagnosis = {
            "code": "pending_owner_decisions",
            "fact": f"{approvals} approval requests are recorded as pending.",
            "decision": "Present each exact scope, evidence, risk, expiry, and rollback condition to the owner.",
            "measure": "approved_decisions_completed_within_scope",
        }
    else:
        diagnosis = {
            "code": "insufficient_operating_evidence",
            "fact": "Connected counters do not establish the binding constraint or commercial performance.",
            "decision": "Connect source-attributed funnel, factory-stage, payment reconciliation, and cost evidence before selecting a growth intervention.",
            "measure": "source_coverage_freshness_and_reconciliation_rate",
        }

    pipeline = value("order_pipeline")
    payment_intents = value("payment_intents")
    ledger_activity = value("ledger_activity")
    factory_flow = value("factory_flow")
    products_by_currency = value("product_catalog")

    paid_orders = sum(
        row["count"] for row in (pipeline or [])
        if str(row.get("status", "")).lower() in {"paid", "completed"}
    )
    pending_orders = sum(
        row["count"] for row in (pipeline or [])
        if str(row.get("status", "")).lower() in {"pending", "awaiting_payment"}
    )

    unit_economics = evaluate_unit_economics(
        currency=None, settled_cash=None, refunds=None, provider_fees=None,
        fulfillment_costs=None, acquisition_cost=None, new_customers=None,
    )

    return {
        "role": BUSINESS_SCIENTIST_PROFILE,
        "decision_method": [
            "separate source facts from estimates and missing measurements",
            "locate the binding constraint from measured process outcomes",
            "test one bounded intervention with a predeclared primary measure",
            "compare against a timestamped baseline and guardrails",
            "retain, repair, or roll back using observed results",
        ],
        "diagnosis": diagnosis,
        "observed_operating_data": {
            "order_pipeline": pipeline,
            "orders_marked_paid_or_completed_in_local_database": paid_orders,
            "orders_marked_pending_in_local_database": pending_orders,
            "payment_intent_counts_and_amounts": payment_intents,
            "ledger_activity_recorded_in_local_database": ledger_activity,
            "factory_task_flow": factory_flow,
            "active_catalog_by_currency": products_by_currency,
            "interpretation_limit": (
                "These are local application records. An order status, payment intent, "
                "or ledger row is not independent proof of settled cash, customer "
                "acceptance, or delivery."
            ),
        },
        "unit_economics": unit_economics,
        "growth_readiness": {
            "decision": "blocked_pending_evidence",
            "required_gates": [
                "named customer segment and independently attributable demand",
                "checkout-to-fulfillment funnel by product and acquisition source",
                "provider/on-chain settlement reconciled to ledger by transaction and currency",
                "refunds, fees, acquisition costs, and fulfillment costs recorded by currency",
                "independent product acceptance and repeatable delivery evidence",
                "small controlled expansion with tested rollback",
            ],
            "current_gaps": review["unknown_metrics"],
        },
        "do_not_infer": [
            "orders are revenue",
            "payment intents or internal ledger rows are settled funds",
            "zero recorded orders proves zero market demand",
            "a product flag proves independent product quality",
            "more agents, tools, or task volume means business growth",
        ],
        "review": review,
    }


def _metric_value(metric):
    if not isinstance(metric, dict) or metric.get("state") != "observed":
        return None
    if not metric.get("source") or not metric.get("captured_at"):
        return None
    return metric.get("value")


def _decimal(value):
    return Decimal(str(value))
