#!/usr/bin/env python3
"""Private, durable QA defect/rework ledger for VPS-produced digital goods.

This module does not accept orders, publish, sell, authorize, or modify the DB.
Every detected defect remains documented, with repair instructions and versions.
No retry storm: unchanged source+defect fingerprints never trigger automated
build attempts beyond the scheduled once-per-cycle check.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone


CODES = {
    "PRODUCT_QA_FAILED": (
        "Product unit or integration tests failed",
        "Inspect failing test assertions and source changes, correct the recipe, "
        "then rerun the complete deterministic test suite."),
    "PRODUCT_PACKAGE_QA_FAILED": (
        "Product ZIP archive integrity or contents failed",
        "Recheck required files, safe archive members, checksums and packaging, "
        "rebuild with the corrected recipe, then rerun packaging QA."),
    "RECIPE_FILE_MISSING_OR_UNSAFE": (
        "Required original recipe file missing or unsafe",
        "Restore or re-author the required file from verified sources and rerun "
        "source validation and complete product tests."),
    "OTHER_PRODUCTION_ERROR": (
        "Unexpected product manufacturing error",
        "Inspect the bounded error trace privately, identify a reproducible "
        "root cause, correct the source and rerun product and package QA."),
}


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _atomic_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    fd, temp = tempfile.mkstemp(prefix=".qa-ledger-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(document, file, sort_keys=True, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _load(path):
    if not path.is_file():
        return {"schema": "saeit.factory.qa-rework.v1", "history": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "saeit.factory.qa-rework.v1":
        raise RuntimeError("REWORK_LEDGER_SCHEMA_MISMATCH")
    if not isinstance(data.get("history"), list):
        raise RuntimeError("REWORK_LEDGER_HISTORY_INVALID")
    return data


def _safe_recipe(recipe):
    if not isinstance(recipe, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}", recipe):
        raise ValueError("INVALID_RECIPE_SLUG")
    return recipe


def _ledger(private_root, recipe):
    recipe = _safe_recipe(recipe)
    return Path(private_root).expanduser().resolve() / "qa-rework" / recipe / "ledger.json"


def classify_error(error):
    raw = str(error)
    for code in ("PRODUCT_QA_FAILED", "PRODUCT_PACKAGE_QA_FAILED", "RECIPE_FILE_MISSING_OR_UNSAFE"):
        if raw.startswith(code):
            return code
    return "OTHER_PRODUCTION_ERROR"


def record_failure(private_root, recipe, error, source_reference):
    """Keep failed product and all previous revisions, never discard."""
    path = _ledger(private_root, recipe)
    data = _load(path)
    code = classify_error(error)
    source = str(source_reference or "unknown")[:150]
    detail = str(error)[:650]
    symptom_hash = _digest({"code": code, "source": source, "detail": detail})
    prior = data["history"][-1] if data["history"] else None
    if (prior and prior.get("fingerprint") == symptom_hash
            and prior.get("status") in ("needs_rework", "expert_review")):
        return {"recipe": recipe, "status": prior["status"], "new_issue": False,
                "issue_round": prior["round"], "code": code}
    number = 1 + max((int(entry.get("round", 0)) for entry in data["history"]), default=0)
    issue = {
        "round": number,
        "code": code,
        "diagnosis": CODES[code][0],
        "actual_error_excerpt": detail,
        "required_correction": CODES[code][1],
        "source_reference": source,
        "fingerprint": symptom_hash,
        "created_at_utc": stamp(),
        "status": "expert_review" if number >= 3 else "needs_rework",
        "correction_evidence": None,
        "fixed_artifact_sha256": None,
    }
    data["history"].append(issue)
    data["recipe"] = recipe
    data["current_status"] = issue["status"]
    data["public_sale_allowed"] = False
    _atomic_json(path, data)
    return {"recipe": recipe, "status": issue["status"], "new_issue": True,
            "issue_round": number, "code": code}


def record_technical_recovery(private_root, recipe, manifest):
    """Prove only technical recovery, never confuse it with commercial QA."""
    path = _ledger(private_root, recipe)
    if not path.is_file():
        return {"recipe": recipe, "status": "no_prior_failure", "new_issue": False}
    data = _load(path)
    if not data["history"]:
        return {"recipe": recipe, "status": "no_prior_failure", "new_issue": False}
    current = data["history"][-1]
    if current.get("status") == "technically_recovered":
        return {"recipe": recipe, "status": "technically_recovered", "new_issue": False}
    if not isinstance(manifest, dict) or manifest.get("qa_status") != "passed":
        raise RuntimeError("TECHNICAL_RECOVERY_REQUIRES_PASS")
    artifact_hash = manifest.get("artifact_sha256")
    if not isinstance(artifact_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_hash):
        raise RuntimeError("TECHNICAL_RECOVERY_REQUIRES_SHA256")
    current["status"] = "technically_recovered"
    current["fixed_artifact_sha256"] = artifact_hash
    current["correction_evidence"] = "Recipe QA passed and package integrity verified"
    current["recovered_at_utc"] = stamp()
    data["current_status"] = "technical_qa_pass_only_owner_and_content_review_pending"
    data["public_sale_allowed"] = False
    _atomic_json(path, data)
    return {"recipe": recipe, "status": data["current_status"], "new_issue": False}


def summarize(private_root):
    """Private dashboard counts without exposure of paths or source content."""
    directory = Path(private_root).expanduser().resolve() / "qa-rework"
    counts = {"needs_rework": 0, "expert_review": 0,
              "technical_qa_pass_only_owner_and_content_review_pending": 0}
    if directory.is_dir():
        for path in directory.glob("*/ledger.json"):
            data = _load(path)
            status = data.get("current_status", "needs_rework")
            counts[status] = counts.get(status, 0) + 1
    return counts
