#!/usr/bin/env python3
"""Fail-closed QC1000 readiness evaluator and actionable rework queue."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

PLAN = Path(__file__).resolve().parents[1] / "factory_config" / "rework" / "farm_enterprise_economics_qc1000_v1.json"
FACTORY_CYCLE = Path(__file__).resolve().with_name("factory_vps_product_cycle.py")


def _authenticated_independent_signatures(clearance, roles):
    """Verify detached signatures against the factory's root-owned trust store.

    A JSON ``valid_signed_roles`` claim is not an independent approval. Share
    the production exit verifier's cryptographic trust path; if unavailable,
    keep the rework queue on HOLD instead of publishing a false PASS.
    """
    try:
        spec = importlib.util.spec_from_file_location("saeit_factory_signature_verifier", FACTORY_CYCLE)
        if spec is None or spec.loader is None:
            return False
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._verified_clearance_signatures(clearance, set(roles))
    except (OSError, ValueError, ImportError, AttributeError, RuntimeError):
        return False


def _rework_queue(plan):
    return [
        {
            "gate_id": gate["id"],
            "name": gate["name"],
            "required_evidence": list(gate["evidence"]),
            "required_checks": list(gate["must_be_true"]),
        }
        for gate in plan["gates"]
    ]


def evaluate(root, recipe="farm_enterprise_economics"):
    root = Path(root)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    result = {
        "schema": "saeit.factory.qc1000-readiness.v2",
        "product_id": recipe,
        "required_score": plan["required_score"],
        "status": "HOLD",
        "rework_queue": _rework_queue(plan),
    }
    reasons = []
    clearance = root / "quality-excellence" / "signed-clearances" / recipe / "current.json"
    if not clearance.is_file() or clearance.is_symlink():
        reasons.append("SIGNED_CLEARANCE_MISSING")
        result["reasons"] = reasons
        return result
    try:
        data = json.loads(clearance.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        reasons.append("SIGNED_CLEARANCE_UNREADABLE")
        data = {}
    if not isinstance(data, dict):
        reasons.append("SIGNED_CLEARANCE_SCHEMA_INVALID")
        data = {}
    if data.get("schema") != "saeit.factory.signed-quality-clearance.v1":
        reasons.append("SIGNED_CLEARANCE_SCHEMA_INVALID")
    if data.get("verified_grade_total") != plan["required_score"]:
        reasons.append("QC1000_SCORE_NOT_VERIFIED")
    roles = data.get("valid_signed_roles")
    required_roles = set(plan["independent_signatures"])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles) or not required_roles.issubset(roles):
        reasons.append("INDEPENDENT_SIGNATURES_INCOMPLETE")
    if not _authenticated_independent_signatures(clearance, required_roles):
        reasons.append("INDEPENDENT_SIGNATURES_NOT_AUTHENTICATED")
    if data.get("eligible") is not True:
        reasons.append("PRODUCT_NOT_ELIGIBLE")
    if data.get("owner_authorization_kind") not in ("direct_owner", "verified_delegated_agent"):
        reasons.append("OWNER_AUTHORIZATION_NOT_VERIFIED")
    if data.get("publication_executed") is not False:
        reasons.append("PUBLICATION_NOT_LOCKED")
    if data.get("payment_activated") is not False:
        reasons.append("PAYMENT_NOT_LOCKED")
    result["reasons"] = reasons
    if not reasons:
        result["status"] = "PASS"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private", required=True)
    parser.add_argument("--recipe", default="farm_enterprise_economics")
    args = parser.parse_args()
    result = evaluate(args.factory_private, args.recipe)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
