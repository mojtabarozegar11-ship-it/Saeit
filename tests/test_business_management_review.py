"""Evidence and decision-policy contract tests (no external services)."""

from core.business_management import observed, review_business, unknown


def _metrics():
    return {
        "blocked_tasks": observed(0, "unit:test", "2026-10-22T00:00:00Z"),
        "queued_tasks": observed(0, "unit:test", "2026-10-22T00:00:00Z"),
        "active_products": observed(2, "unit:test", "2026-10-22T00:00:00Z"),
        "orders": observed(0, "unit:test", "2026-10-22T00:00:00Z"),
        "pending_approvals": observed(0, "unit:test", "2026-10-22T00:00:00Z"),
        "independently_validated_market": unknown("not connected"),
        "verified_collected_cash": unknown("not connected"),
        "accepted_factory_products": unknown("not connected"),
        "site_health": unknown("not connected"),
    }


def test_observed_values_require_traceable_source():
    try:
        observed(10, "", "2026-10-22")
    except ValueError:
        pass
    else:
        raise AssertionError("Unattributed measurements must not be accepted")


def test_missing_cash_is_unknown_and_never_zero_success():
    report = review_business(_metrics())
    assert "verified_collected_cash" in report["unknown_metrics"]
    assert report["next_constraint"] == "cash_unverified"
    assert any(item["code"] == "no_recorded_orders" for item in report["findings"])


def test_blocked_tasks_become_first_constraint_without_auto_approval():
    metrics = _metrics()
    metrics["blocked_tasks"] = observed(5, "unit:test", "2026-10-22")
    report = review_business(metrics)
    assert report["next_constraint"] == "blocked_work"
    assert "do not release approvals automatically" in report["findings"][0]["action"]


def test_pending_approvals_have_owner_gate():
    metrics = _metrics()
    metrics["pending_approvals"] = observed(2, "unit:test", "2026-10-22")
    item = next(x for x in review_business(metrics)["findings"] if x["code"] == "owner_decisions")
    assert item["execution"] == "owner_approval"


def test_unattributed_metric_must_not_be_taken_as_observation():
    metrics = _metrics()
    metrics["orders"] = {"state": "observed", "value": 0}
    report = review_business(metrics)
    assert "orders" in report["unknown_metrics"]
    assert all(x["code"] != "no_recorded_orders" for x in report["findings"])
