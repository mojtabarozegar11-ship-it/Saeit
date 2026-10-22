"""Offline safety and evidence provenance tests for the private decision cycle."""
from datetime import datetime, timedelta, timezone

from scripts.business_os_private_control import decision, normalize

NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def report(node, blocked=2, queued=7, fresh=True):
    ts = NOW - (timedelta(hours=3) if not fresh else timedelta(minutes=1))
    prefix = {"vps": "vps_private_factory_sqlite:", "cpanel": "cpanel_local_django:"}[node]
    keys = ["queued_tasks", "blocked_tasks", "active_products"] if node == "vps" else [
        "queued_tasks", "blocked_tasks", "active_products", "orders", "pending_approvals"]
    metrics = {k: {"state": "observed", "value": 0, "source": prefix + "sample",
                   "captured_at": ts.isoformat()} for k in keys}
    metrics["blocked_tasks"]["value"] = blocked
    metrics["queued_tasks"]["value"] = queued
    return {"scope": ("VPS local isolated factory SQLite only" if node == "vps"
                      else "local_cpanel_django_only; excludes other stores"),
            "metrics": metrics}


def test_factory_blockers_precede_backlog():
    result = decision(vps=report("vps"), now=NOW)
    assert result["candidate"]["action"] == "classify_factory_blockers"
    assert result["agent_task_execution"] is False


def test_unobserved_cpanel_data_is_not_zero():
    result = decision(vps=report("vps", blocked=0, queued=0), now=NOW)
    assert result["observation"]["local_cpanel"]["orders"]["state"] == "unknown"
    assert result["candidate"]["action"] != "instrument_local_order_funnel"


def test_stale_data_never_drives_operational_decisions():
    result = decision(vps=report("vps", fresh=False), now=NOW)
    assert result["candidate"]["action"] == "repair_factory_observability"
    assert result["observation"]["factory_vps"]["queued_tasks"]["state"] == "unknown"


def test_source_spoofing_fails_closed():
    sample = report("vps")
    sample["metrics"]["blocked_tasks"]["source"] = "cpanel_local_django:wrong"
    result = decision(vps=sample, now=NOW)
    assert result["observation"]["factory_vps"]["blocked_tasks"]["state"] == "unknown"


def test_count_values_reject_booleans_and_negative():
    sample = report("vps")
    sample["metrics"]["blocked_tasks"]["value"] = True
    sample["metrics"]["queued_tasks"]["value"] = -1
    cleaned = normalize(sample, "vps", NOW)
    assert cleaned["blocked_tasks"]["state"] == "unknown"
    assert cleaned["queued_tasks"]["state"] == "unknown"


def test_identical_values_do_not_clone_decisions():
    first = decision(vps=report("vps"), now=NOW)
    later = report("vps")
    for val in later["metrics"].values():
        val["captured_at"] = (NOW - timedelta(seconds=10)).isoformat()
    second = decision(vps=later, now=NOW)
    assert first["fingerprint"] == second["fingerprint"]


def test_money_and_factory_release_never_auto_execute():
    result = decision(vps=report("vps"), cpanel=report("cpanel"), now=NOW)
    assert result["candidate"]["allowed_effects"] == ["private_evidence_receipt"]
    assert "payment" in result["candidate"]["forbidden_effects"]
    assert "commercial_release" in result["candidate"]["forbidden_effects"]
    assert result["commercial_result"] == "unverified"


def test_cpanel_counts_do_not_replace_independent_factory_counts():
    result = decision(cpanel=report("cpanel", blocked=55, queued=100), now=NOW)
    assert result["observation"]["factory_vps"]["queued_tasks"]["state"] == "unknown"
    assert result["candidate"]["action"] == "instrument_local_order_funnel"


def test_cpanel_local_orders_do_not_wait_for_factory_source():
    sample = report("cpanel")
    sample["metrics"]["orders"]["value"] = 3
    result = decision(cpanel=sample, now=NOW)
    assert result["candidate"]["action"] == "reconcile_payment_settlement"
    assert result["candidate"]["authority"] == "private_diagnostic_only"
    assert result["observation"]["factory_vps"]["blocked_tasks"]["state"] == "unknown"
    assert result["commercial_result"] == "unverified"


def test_cpanel_unknown_orders_are_not_silent_zero():
    sample = report("cpanel")
    sample["metrics"]["orders"]["state"] = "unknown"
    result = decision(cpanel=sample, now=NOW)
    assert result["candidate"]["action"] == "repair_local_order_observability"


def test_local_pending_approvals_trigger_diagnostic_only():
    sample = report("cpanel")
    sample["metrics"]["orders"]["value"] = 3
    sample["metrics"]["pending_approvals"]["value"] = 2
    result = decision(cpanel=sample, now=NOW)
    assert result["candidate"]["action"] == "classify_local_approval_gates"
    assert "approval" in result["candidate"]["forbidden_effects"]


def test_absent_local_snapshots_cannot_infer_sales():
    result = decision(now=NOW)
    assert result["candidate"]["action"] == "connect_private_observers"
    assert result["observation"]["local_cpanel"]["orders"]["state"] == "unknown"
