#!/usr/bin/env python3
"""Bind real 100x10 private factory workorders to bounded specialist rework queues.

Never modifies product sources, reviewer records, stores or commercial state.
Persistent receipts are immutable and hash-bound to the actual QA assessment.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from quality1000_evidence_gate import inspect
from factory_quality_1000_v2 import CRITERIA

FAMILY = re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
RECIPE = re.compile(r"^[a-z][a-z0-9_]{1,65}$")
DOMAIN_ADAPTERS = {
    "global_comparative_advantage": "benchmark_research",
    "originality_and_non_derivativeness": "ip_novelty_review",
    "verified_innovation": "independent_innovation_test",
    "technology_and_technical_excellence": "specialist_builder",
    "domain_depth_and_accuracy": "domain_evidence_research",
    "user_customer_value": "user_testing",
    "real_world_performance_accessibility": "accessibility_device_qa",
    "independent_adversarial_testing": "independent_regression_qa",
    "security_ethics_regulatory_safety": "security_review",
    "legal_rights_and_provenance": "rights_review",
    "distribution_support_reliability": "delivery_reliability_qa",
    "independent_expert_review": "authenticated_external_reviewer",
}
SIX = {"F12", "F13", "F14", "F16", "F17", "F26"}

def read_file(path, max_bytes=3_000_000):
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= max_bytes):
        raise ValueError("ROUTER_INVALID_OR_UNSAFE_INPUT")
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf8"))
    if not isinstance(value, dict):
        raise ValueError("ROUTER_EXPECTED_JSON_OBJECT")
    return raw, value

def quarantine_ticket(assessment, raw, order):
    """Preserve audit-error records as explicit repair, never 100-group proof."""
    name = assessment.get("recipe")
    defects = assessment.get("defects")
    if (assessment.get("schema") != "saeit.factory.quality-rework.v2"
            or assessment.get("quality_status") != "QUARANTINE_AUDIT_ERROR"
            or not isinstance(name, str) or not RECIPE.fullmatch(name)
            or order.get("schema") != "saeit.factory.production-rework-order.v1"
            or order.get("recipe") != name
            or order.get("source_quality_receipt_sha256") != hashlib.sha256(raw).hexdigest()
            or order.get("commercial_publish_allowed") is not False
            or order.get("owner_release_approval_required") is not True
            or order.get("signed_external_quality_approval_required") is not True
            or assessment.get("commercial_release_allowed") is not False
            or assessment.get("premium_quality_approved") is not False
            or assessment.get("quality_points_verified") is not None
            or not isinstance(defects, list)
            or not defects
            or not all(isinstance(c, str) and c.startswith("P0_AUDIT_ERROR_")
                       for c in defects)
            or sorted(order.get("unresolved_technical_or_domain_defects", []))
                != sorted(defects)):
        raise ValueError("ROUTER_QUARANTINE_SOURCE_NOT_BOUND")
    jobs = [{"criterion": None, "name": "recover_original_sources_and_rerun_triage",
             "adapter": "specialist_builder",
             "action": "restore_authentic_build_and_complete_quality_scorecard",
             "type": "source_integrity_quarantine", "status": "OPEN"}]
    return {
        "schema": "saeit.quality1000.specialist-route.v2",
        "recipe": name, "family_id": assessment.get("family_id"),
        "source_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_sha256": None, "producer_module": "factory_product_maker.py",
        "criteria_total": 100, "documentary_points": None,
        "task_count": len(jobs), "tasks": jobs,
        "external_signed_review_required": True,
        "master_task_dispatch_verified": False, "certified_quality_points": None,
        "quality_1000_certified": False, "publication_allowed": False,
        "payment_activation_allowed": False, "disposition": "QUARANTINED_NEEDS_ORIGINAL_SOURCE",
    }

def ticket(assessment, raw, order):
    if assessment.get("quality_status") == "QUARANTINE_AUDIT_ERROR":
        return quarantine_ticket(assessment, raw, order)
    state = inspect(assessment, raw, order)
    family = state["family_id"]
    if not isinstance(family, str) or not FAMILY.fullmatch(family):
        jobs=[{"criterion": None, "name": "P0_UNMAPPED_PRODUCT_FAMILY",
               "adapter": "family_classification_specialist",
               "action": "prove_original_family_identity_and_regrade_then_requeue",
               "type": "family_identity_quarantine", "status": "OPEN"}]
        return {
            "schema": "saeit.quality1000.specialist-route.v2",
            "recipe": state["recipe"], "family_id": None,
            "source_receipt_sha256": state["assessment_sha256"],
            "artifact_sha256": state["artifact_sha256"],
            "producer_module": None,
            "criteria_total": 100, "documentary_points": state["documentary_points"],
            "task_count": 1, "tasks": jobs,
            "external_signed_review_required": True,
            "master_task_dispatch_verified": False, "certified_quality_points": None,
            "quality_1000_certified": False, "publication_allowed": False,
            "payment_activation_allowed": False, "disposition": "QUARANTINED_UNMAPPED_FAMILY",
        }
    pending = set(state["missing_documentary_groups"])
    order_rows = order.get("required_criterion_work")
    if not isinstance(order_rows, list) or len(order_rows) != len(pending):
        raise ValueError("ROUTER_WORKORDER_CRITERIA_MISMATCH")
    found = set()
    for item in order_rows:
        if not isinstance(item, dict) or item.get("group_id") not in pending:
            raise ValueError("ROUTER_WORKORDER_CRITERIA_INVALID")
        found.add(item["group_id"])
    if found != pending:
        raise ValueError("ROUTER_WORKORDER_GROUPS_NOT_BOUND")
    if sorted(order.get("unresolved_technical_or_domain_defects", [])) != state["unresolved_defects"]:
        raise ValueError("ROUTER_WORKORDER_DEFECTS_MISMATCH")
    tasks = []
    for code in sorted(pending):
        policy = CRITERIA[code]
        dimensions = policy["quality_dimensions"]
        adapter = next((DOMAIN_ADAPTERS[x] for x in dimensions if x in DOMAIN_ADAPTERS), None)
        if not adapter:
            raise ValueError("ROUTER_NO_SPECIALIST_ROUTE")
        tasks.append({
            "criterion": code, "name": policy["name"], "adapter": adapter,
            "action": "collect_real_evidence_repair_retest_and_independent_review",
            "type": "documentary_evidence_missing",
            "status": "OPEN",
        })
    for code in state["unresolved_defects"]:
        tasks.append({"criterion": None, "name": code, "adapter": "specialist_builder",
                      "action": "diagnose_source_fix_rebuild_and_retest",
                      "type": "observed_quality_defect", "status": "OPEN"})
    return {
        "schema": "saeit.quality1000.specialist-route.v2",
        "recipe": state["recipe"], "family_id": family,
        "source_receipt_sha256": state["assessment_sha256"],
        "artifact_sha256": state["artifact_sha256"],
        "producer_module": ("factory_six_specialist_executors.py" if family in SIX
                            else "factory_product_maker.py"),
        "criteria_total": 100, "documentary_points": state["documentary_points"],
        "task_count": len(tasks), "tasks": tasks,
        "external_signed_review_required": True,
        "master_task_dispatch_verified": False,
        "certified_quality_points": None,
        "quality_1000_certified": False,
        "publication_allowed": False,
        "payment_activation_allowed": False,
        "disposition": ("REWORK_PENDING" if tasks else "INDEPENDENT_REVIEW_PENDING"),
    }

def atomic_json(path, value):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("ROUTER_OUTPUT_SYMLINK_REJECTED")
    payload = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    fd, tmp = tempfile.mkstemp(prefix=".route-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return hashlib.sha256(payload).hexdigest()

def route(root, limit=6):
    root = Path(root)
    if root.is_symlink() or not root.is_dir() or not 1 <= limit <= 40:
        raise ValueError("ROUTER_UNSAFE_ROOT_OR_LIMIT")
    base = root / "quality-excellence"
    orders = base / "production-workorders"
    assessments = base / "rework"
    output = base / "specialist-routed-rework"
    if any(x.is_symlink() or not x.is_dir() for x in (base, orders, assessments)):
        raise ValueError("ROUTER_REAL_QA_SOURCE_REQUIRED")
    if output.is_symlink():
        raise ValueError("ROUTER_OUTPUT_DIRECTORY_UNSAFE")
    output.mkdir(mode=0o700, exist_ok=True)
    lock = output / ".router.lock"
    if lock.is_symlink():
        raise ValueError("ROUTER_LOCK_UNSAFE")
    completed = []
    rejected = []
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(), 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        count = 0
        for folder in sorted(orders.iterdir()):
            if count >= limit:
                break
            if folder.is_symlink() or not folder.is_dir() or not RECIPE.fullmatch(folder.name):
                continue
            count += 1
            try:
                raw, assessment = read_file(assessments / folder.name / "current.json")
                _, order = read_file(folder / "current.json")
                result = ticket(assessment, raw, order)
                destination = output / folder.name
                if destination.is_symlink():
                    raise ValueError("ROUTER_RECIPE_TARGET_SYMLINK")
                destination.mkdir(mode=0o700, exist_ok=True)
                payload = (json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2)+"\n").encode()
                token = hashlib.sha256(payload).hexdigest()
                receipt = destination / ("route-" + token[:24] + ".json")
                if receipt.exists():
                    if receipt.is_symlink() or receipt.read_bytes() != payload:
                        raise ValueError("ROUTER_IMMUTABLE_RECEIPT_CHANGED")
                else:
                    atomic_json(receipt, result)
                atomic_json(destination / "current.json", result)
                completed.append({"recipe": folder.name, "tasks": result["task_count"],
                                  "receipt_sha256": token})
            except (ValueError, OSError, KeyError, TypeError, RuntimeError, json.JSONDecodeError) as error:
                reason = str(error)
                if not (reason.startswith("QUALITY1000_") or reason.startswith("ROUTER_")):
                    reason = type(error).__name__
                rejected.append({"recipe": folder.name, "failure_code": reason[:100]})
    return {"schema": "saeit.quality1000.specialist-route-summary.v2",
            "routed_products": len(completed), "queued_issues": sum(i["tasks"] for i in completed),
            "rejected_products": rejected, "receipts": completed,
            "professional_quality_certifications": 0, "sites_modified": 0}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--limit", type=int, default=6)
    a = p.parse_args()
    result = route(a.private_root, a.limit)
    print("QUALITY1000_PRIVATE_REWORK=" + json.dumps(result, ensure_ascii=False, sort_keys=True))
    raise SystemExit(2 if result["rejected_products"] else 0)

if __name__ == "__main__":
    main()
