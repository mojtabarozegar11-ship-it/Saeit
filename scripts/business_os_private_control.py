"""Private Business OS decision cycle. No website, payment or AgentTask writes.

Data must remain on its originating server until an authenticated private
server-to-server channel exists. A GitHub runner receives fixed status markers.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

MAX_BYTES = 256_000
MAX_AGE_SECONDS = 7200
KEYS = {
    "vps": ("queued_tasks", "blocked_tasks", "active_products", "accepted_factory_products"),
    "cpanel": ("queued_tasks", "blocked_tasks", "active_products", "orders",
               "pending_approvals", "verified_collected_cash"),
}
PREFIX = {"vps": "vps_private_factory_sqlite:", "cpanel": "cpanel_local_django:"}


def unknown(reason):
    return {"state": "unknown", "value": None, "reason": reason}


def _metric(raw, node, now):
    if not isinstance(raw, dict) or raw.get("state") != "observed":
        return unknown("source_not_observed")
    if not str(raw.get("source", "")).startswith(PREFIX[node]):
        return unknown("invalid_source_provenance")
    try:
        captured = datetime.fromisoformat(raw["captured_at"].replace("Z", "+00:00"))
        if captured.tzinfo is None:
            raise ValueError("naive timestamp")
        age = (now - captured.astimezone(timezone.utc)).total_seconds()
    except (ValueError, KeyError, TypeError, AttributeError):
        return unknown("invalid_timestamp")
    if age < -60 or age > MAX_AGE_SECONDS:
        return unknown("stale_or_future_observation")
    value = raw.get("value")
    if type(value) is not int or value < 0:
        return unknown("invalid_count")
    return {"state": "observed", "value": value,
            "source": raw["source"], "captured_at": captured.isoformat()}


def normalize(report, node, now):
    if not isinstance(report, dict) or not isinstance(report.get("metrics"), dict):
        raise ValueError("invalid_snapshot")
    scope = str(report.get("scope", ""))
    if (node == "vps" and not scope.startswith("VPS local isolated factory SQLite")) or (
            node == "cpanel" and not scope.startswith("local_cpanel_django_only")):
        raise ValueError("unexpected_snapshot_scope")
    return {key: _metric(report["metrics"].get(key), node, now) for key in KEYS[node]}


def _value(metrics, key):
    metric = metrics.get(key, {})
    return metric.get("value") if metric.get("state") == "observed" else None


def decision(vps=None, cpanel=None, now=None):
    """Choose bounded diagnostic work; never impersonate specialist approval."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_time_required")
    factory_connected = vps is not None
    cpanel_connected = cpanel is not None
    vps = normalize(vps, "vps", now) if factory_connected else {
        key: unknown("factory_snapshot_not_connected") for key in KEYS["vps"]
    }
    cpanel = normalize(cpanel, "cpanel", now) if cpanel_connected else {
        key: unknown("private_cpanel_snapshot_not_connected") for key in KEYS["cpanel"]
    }
    blocked = _value(vps, "blocked_tasks")
    queued = _value(vps, "queued_tasks")
    orders = _value(cpanel, "orders")
    local_approvals = _value(cpanel, "pending_approvals")
    # A missing remote source is not a failure of the *local* source. Until an
    # authenticated private bridge exists, VPS and cPanel decide separately.
    if factory_connected and blocked is not None and blocked > 0:
        action, target, reason = ("classify_factory_blockers", "factory",
                                  "Observed blocked VPS tasks; measure reasons and owner/evidence gates")
    elif factory_connected and queued is not None and queued > 0:
        action, target, reason = ("measure_factory_stage_throughput", "factory",
                                  "Observed queued VPS tasks; no verified completion rate")
    elif factory_connected and (blocked is None or queued is None):
        action, target, reason = ("repair_factory_observability", "factory",
                                  "Fresh authenticated factory task counts unavailable")
    elif cpanel_connected and orders is None:
        action, target, reason = ("repair_local_order_observability", "cpanel",
                                  "Authenticated local order count unavailable; cannot infer zero sales")
    elif cpanel_connected and orders == 0:
        action, target, reason = ("instrument_local_order_funnel", "cpanel",
                                  "No orders observed in local cPanel Django; other stores unknown")
    elif cpanel_connected and local_approvals is not None and local_approvals > 0:
        action, target, reason = ("classify_local_approval_gates", "cpanel",
                                  "Observed local pending approvals; no specialist approval implied")
    elif cpanel_connected and orders is not None and orders > 0:
        action, target, reason = ("reconcile_payment_settlement", "cpanel",
                                  "Local orders exist; cash settlement, refunds and delivery unverified")
    elif factory_connected:
        action, target, reason = ("reconcile_business_evidence", "factory",
                                  "Factory readiness, independent acceptance and demand unverified")
    else:
        action, target, reason = ("connect_private_observers", "business",
                                  "No fresh authenticated local snapshots supplied")
    # Stable across identical measurements; timestamps alone never create new work.
    state = {"vps": {k: (v["state"], v.get("value"), v.get("reason")) for k, v in vps.items()},
             "cpanel": {k: (v["state"], v.get("value"), v.get("reason")) for k, v in cpanel.items()},
             "action": action}
    fingerprint = hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {
        "schema": "saeit.business-os.private-decision.v1",
        "generated_at": now.isoformat(),
        "orchestrator": "moj_1ro_1",
        "delivery_to_orchestrator": "not_connected",
        "observation": {"factory_vps": vps, "local_cpanel": cpanel},
        "candidate": {"action": action, "target": target, "reason": reason,
                      "authority": "private_diagnostic_only",
                      "allowed_effects": ["private_evidence_receipt"],
                      "forbidden_effects": ["payment", "wallet", "publish", "approval",
                                            "commercial_release", "modify_agent_tasks",
                                            "change_worker_concurrency"]},
        "fingerprint": fingerprint,
        "commercial_result": "unverified",
        "agent_task_execution": False,
    }


# Change in an observed count is not proof that our diagnosis caused it.
# Each release compares only its own local, permission-restricted receipts.
PROGRESS_SIGNALS = {
    "classify_factory_blockers": ("factory_vps", "blocked_tasks", "decrease"),
    "measure_factory_stage_throughput": ("factory_vps", "queued_tasks", "decrease"),
    "instrument_local_order_funnel": ("local_cpanel", "orders", "increase"),
    "classify_local_approval_gates": ("local_cpanel", "pending_approvals", "decrease"),
}


def assess_previous_cycle(previous, current, node):
    baseline = {
        "state": "baseline_required",
        "causal_effect_proven": False,
        "commercial_success_proven": False,
    }
    if not isinstance(previous, dict) or previous.get("schema") != current["schema"]:
        return baseline
    try:
        recent = datetime.fromisoformat(previous["generated_at"].replace("Z", "+00:00"))
        present = datetime.fromisoformat(current["generated_at"].replace("Z", "+00:00"))
        age = (present - recent).total_seconds()
    except (ValueError, KeyError, TypeError, AttributeError):
        return baseline
    if recent.tzinfo is None or not (0 <= age <= MAX_AGE_SECONDS):
        return baseline
    action = previous.get("candidate", {}).get("action")
    signal = PROGRESS_SIGNALS.get(action)
    if signal is None or signal[0] != ("factory_vps" if node == "vps" else "local_cpanel"):
        return {
            **baseline, "state": "no_applicable_local_outcome_metric",
            "prior_action": action if isinstance(action, str) else "unknown",
        }
    scope, name, target_direction = signal
    first = previous.get("observation", {}).get(scope, {}).get(name, {})
    last = current.get("observation", {}).get(scope, {}).get(name, {})
    if (not isinstance(first, dict) or not isinstance(last, dict)
            or first.get("state") != "observed" or last.get("state") != "observed"
            or not first.get("source") or first.get("source") != last.get("source")
            or type(first.get("value")) is not int or type(last.get("value")) is not int
            or first["value"] < 0 or last["value"] < 0):
        return {**baseline, "state": "not_comparable", "prior_action": action}
    change = last["value"] - first["value"]
    return {
        "state": "observed_count_delta_only",
        "prior_action": action,
        "metric": name,
        "delta": change,
        "trend": "increase" if change > 0 else "decrease" if change < 0 else "unchanged",
        "directional_signal": (
            "aligned" if (change > 0 and target_direction == "increase")
            or (change < 0 and target_direction == "decrease")
            else "unchanged" if change == 0 else "opposite"
        ),
        "causal_effect_proven": False,
        "commercial_success_proven": False,
    }


def _read_private(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("missing_or_linked_snapshot")
    st = path.stat()
    if st.st_size > MAX_BYTES or st.st_size == 0 or st.st_mode & 0o077:
        raise ValueError("unsafe_snapshot_permissions_or_size")
    if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
        raise ValueError("snapshot_owner_mismatch")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_private(path, report):
    directory = path.parent
    if directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
        raise ValueError("unsafe_private_directory")
    filename = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory,
                                         prefix=".decision-", suffix=".json", delete=False) as output:
            filename = Path(output.name)
            os.fchmod(output.fileno(), 0o600)
            json.dump(report, output, sort_keys=True, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(filename, path)
    finally:
        if filename is not None:
            filename.unlink(missing_ok=True)


def run_stage(node, root):
    root = Path(root).resolve()
    if node == "vps":
        expected = Path.home().resolve() / "saeit-business-os-staging" / "releases"
        input_name = "factory-review.json"
    elif node == "cpanel":
        expected = Path("/home/zomorod2/Saeit-staging/releases")
        input_name = "business-review.json"
    else:
        raise ValueError("unknown_node")
    if expected not in root.parents:
        raise ValueError("not_private_staging")
    private = root / "private"
    source = _read_private(private / input_name)
    result = decision(vps=source if node == "vps" else None,
                      cpanel=source if node == "cpanel" else None)
    old_path = private / "decision.json"
    previous = _read_private(old_path) if old_path.is_file() else None
    result["unchanged_from_previous"] = bool(
        previous and previous.get("fingerprint") == result["fingerprint"])
    result["execution"] = "deduplicated_diagnostic_receipt_only"
    result["previous_cycle_assessment"] = assess_previous_cycle(previous, result, node)
    _write_private(old_path, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", required=True, choices=("vps", "cpanel"))
    args = parser.parse_args()
    try:
        run_stage(args.node, Path(__file__).resolve().parent.parent)
    except Exception:
        raise SystemExit("BUSINESS_OS_PRIVATE_DECISION_UNAVAILABLE")
    print("BUSINESS_OS_PRIVATE_DECISION_RECORDED")


if __name__ == "__main__":
    main()
