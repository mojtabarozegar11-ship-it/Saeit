"""Economic computation and decision-boundary tests for the business scientist."""
from decimal import Decimal

from core.business_management import observed, unknown
from core.business_scientist import (
    BUSINESS_SCIENTIST_PROFILE,
    build_business_science_plan,
    evaluate_unit_economics,
)


def _metrics():
    ts = "2026-10-22T00:00:00Z"
    return {
        "blocked_tasks": observed(0, "test", ts),
        "queued_tasks": observed(0, "test", ts),
        "active_products": observed(1, "test", ts),
        "orders": observed(0, "test", ts),
        "pending_approvals": observed(0, "test", ts),
        "order_pipeline": observed([], "test:Order", ts),
        "payment_intents": observed([], "test:PaymentIntent", ts),
        "ledger_activity": observed([], "test:LedgerEntry", ts),
        "factory_flow": observed([], "test:AgentTask", ts),
        "product_catalog": observed([{"currency": "USD", "count": 1}], "test:Product", ts),
        "independently_validated_market": unknown("not connected"),
        "verified_collected_cash": unknown("not connected"),
        "accepted_factory_products": unknown("not connected"),
        "site_health": unknown("not connected"),
        "attributable_costs": unknown("not connected"),
    }


def test_professional_scope_covers_the_business_system():
    assert BUSINESS_SCIENTIST_PROFILE["code"] == "business-scientist-professor"
    assert len(BUSINESS_SCIENTIST_PROFILE["disciplines"]) == 10


def test_unit_economics_uses_settled_cash_and_complete_costs():
    result = evaluate_unit_economics(
        currency="USD", settled_cash="1000", refunds="100",
        provider_fees="30", fulfillment_costs="300",
        acquisition_cost="200", new_customers=10,
    )
    assert result["state"] == "computed_from_complete_inputs"
    assert Decimal(result["contribution"]) == Decimal("370")
    assert Decimal(result["contribution_margin"]) == Decimal("0.37")
    assert Decimal(result["customer_acquisition_cost"]) == Decimal("20")
    assert result["profitable"] is True


def test_missing_cash_or_costs_refuses_to_estimate_profit():
    result = evaluate_unit_economics(
        currency=None, settled_cash=None, refunds=None,
        provider_fees=None, fulfillment_costs=None,
        acquisition_cost=None, new_customers=None,
    )
    assert result["state"] == "not_computable"
    assert "settled_cash" in result["missing_inputs"]


def test_database_orders_without_sales_funnel_do_not_prove_market_failure():
    plan = build_business_science_plan(_metrics())
    assert plan["diagnosis"]["code"] == "unmeasured_product_funnel"
    assert "before changing price" in plan["diagnosis"]["decision"]
    assert plan["unit_economics"]["state"] == "not_computable"
    assert plan["growth_readiness"]["decision"] == "blocked_pending_evidence"


def test_real_blocked_work_precedes_generic_growth_work():
    metrics = _metrics()
    metrics["blocked_tasks"] = observed(3, "test", "2026-10-22T00:00:00Z")
    plan = build_business_science_plan(metrics)
    assert plan["diagnosis"]["code"] == "blocked_work"
    assert "do not bypass" in plan["diagnosis"]["decision"]


def test_order_and_internal_ledger_records_are_not_called_settled_cash():
    plan = build_business_science_plan(_metrics())
    assert "not independent proof" in plan["observed_operating_data"]["interpretation_limit"]
    assert "orders are revenue" in plan["do_not_infer"]
