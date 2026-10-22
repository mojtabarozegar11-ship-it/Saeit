"""Contract tests for the evidence-led virtual business scientist."""
from core.business_management import observed, unknown
from core.business_scientist import BUSINESS_SCIENTIST_PROFILE, build_business_science_plan


def _metrics():
    ts = "2026-10-22T00:00:00Z"
    return {
        "blocked_tasks": observed(0, "test", ts),
        "queued_tasks": observed(0, "test", ts),
        "active_products": observed(1, "test", ts),
        "orders": observed(0, "test", ts),
        "pending_approvals": observed(0, "test", ts),
        "independently_validated_market": unknown("not connected"),
        "verified_collected_cash": unknown("not connected"),
        "accepted_factory_products": unknown("not connected"),
        "site_health": unknown("not connected"),
    }


def test_role_is_a_scoped_virtual_business_scientist():
    assert BUSINESS_SCIENTIST_PROFILE["code"] == "business-scientist-professor"
    assert len(BUSINESS_SCIENTIST_PROFILE["disciplines"]) == 10
    assert "approval_required" in BUSINESS_SCIENTIST_PROFILE["authority"]


def test_plan_prioritizes_unknown_cash_and_never_calls_orders_revenue():
    plan = build_business_science_plan(_metrics())
    experiment = plan["next_experiment"]
    assert experiment["constraint"] == "cash_unverified"
    assert experiment["primary_measure"] == "reconciled_net_contribution_by_currency"
    assert "Never count orders or intents as settled cash." in experiment["guardrail"]
    assert "verified_collected_cash" in plan["evidence_gaps"]


def test_growth_requires_customer_evidence_and_positive_unit_economics():
    gates = {gate["gate"] for gate in build_business_science_plan(_metrics())["portfolio_growth_gates"]}
    assert {"customer_problem", "willingness_to_pay", "reliable_delivery",
            "positive_unit_economics", "repeatable_acquisition",
            "controlled_expansion"} <= gates


def test_blocked_work_is_never_authorized_automatically():
    metrics = _metrics()
    metrics["blocked_tasks"] = observed(3, "test", "2026-10-22T00:00:00Z")
    plan = build_business_science_plan(metrics)
    assert plan["next_experiment"]["constraint"] == "blocked_work"
    assert plan["next_experiment"]["execution"] == "autonomous_diagnostic"
    assert any("unresolved approval" in x for x in plan["do_not_scale"])
