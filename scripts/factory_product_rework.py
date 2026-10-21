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
import zipfile
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
    if path.is_symlink():
        raise RuntimeError("REWORK_LEDGER_SYMLINK_UNSAFE")
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


def record_technical_recovery(private_root, recipe, manifest, *, archive_path=None, source_digest=None):
    """Prove only technical recovery, never confuse it with commercial QA."""
    path = _ledger(private_root, recipe)
    if not path.is_file():
        return {"recipe": recipe, "status": "no_prior_failure", "new_issue": False}
    data = _load(path)
    if not data["history"]:
        return {"recipe": recipe, "status": "no_prior_failure", "new_issue": False}
    current = data["history"][-1]
    if (not isinstance(manifest, dict) or manifest.get("qa_status") != "passed"
            or manifest.get("recipe") != recipe):
        raise RuntimeError("TECHNICAL_RECOVERY_REQUIRES_RECIPE_PASS")
    artifact_hash = manifest.get("artifact_sha256")
    if not isinstance(artifact_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_hash):
        raise RuntimeError("TECHNICAL_RECOVERY_REQUIRES_SHA256")
    if (not isinstance(source_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", source_digest)
            or manifest.get("source_sha256") != source_digest):
        raise RuntimeError("TECHNICAL_RECOVERY_SOURCE_REVISION_UNVERIFIED")
    # A prior passed manifest or a checksum string alone cannot close a live defect.
    if archive_path is None:
        raise RuntimeError("TECHNICAL_RECOVERY_ARCHIVE_MISSING")
    archive = Path(archive_path)
    if archive.is_symlink() or not archive.is_file() or not 0 < archive.stat().st_size <= 25 * 1024 * 1024:
        raise RuntimeError("TECHNICAL_RECOVERY_ARCHIVE_UNSAFE")
    checksum = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    if checksum.hexdigest() != artifact_hash:
        raise RuntimeError("TECHNICAL_RECOVERY_ARCHIVE_SHA_MISMATCH")
    try:
        with zipfile.ZipFile(archive) as bundle:
            if not bundle.namelist() or bundle.testzip() is not None:
                raise RuntimeError("TECHNICAL_RECOVERY_ARCHIVE_INTEGRITY_FAILED")
    except zipfile.BadZipFile as exc:
        raise RuntimeError("TECHNICAL_RECOVERY_ARCHIVE_INTEGRITY_FAILED") from exc
    if current.get("status") == "technically_recovered":
        return {"recipe": recipe, "status": "technically_recovered", "new_issue": False}
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


RESEARCH_FIX_PLANS = {
    "FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED":
        "Research and verify independent public sources; record source URLs and direct evidence links.",
    "ONE_HUNDRED_DISTINCT_STRONG_EVIDENCE_PASSAGES_REQUIRED":
        "Collect substantive, distinct factual evidence with provenance, relevance and confidence.",
    "ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED":
        "Perform and document one authentic internal test or reproducible research action.",
    "TEN_FACTOR_VALIDATION_PASS_REQUIRED":
        "Review each missing demand, willingness-to-pay, financial, legal and execution factor.",
    "FACTORY_OWNER_OR_ACTIVE_PRODUCT_STATE_INVALID":
        "Resolve genuine ownership and project provenance with the authorized owner.",
    "PUBLISHED_KNOWLEDGE_PROVENANCE_REQUIRED":
        "Prepare and approve accurate source-linked editorial documentation.",
    "FAIR_PRICE_AND_COST_REVIEW_REQUIRED":
        "Verify actual production costs, buyer value, and pricing assumptions.",
    "HUMAN_COMMERCIAL_LICENSE_AND_FACTUAL_REVIEW_REQUIRED":
        "Obtain documented intellectual-property, factual accuracy and commercial review.",
}


def record_research_gaps(private_root, entry):
    """Create durable, actionable research-defect tickets from actual QA results."""
    product_id = entry.get("product_id") if isinstance(entry, dict) else None
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id < 1:
        raise ValueError("INVALID_RESEARCH_PRODUCT_ID")
    gate = entry.get("research_quality_gate")
    if not isinstance(gate, dict) or gate.get("schema") != "saeit.factory.research-readiness.v1":
        raise ValueError("RESEARCH_GATE_MISSING")
    blockers = gate.get("blockers")
    if not isinstance(blockers, list) or any(
        not isinstance(x, str) or x not in RESEARCH_FIX_PLANS for x in blockers
    ):
        raise ValueError("RESEARCH_BLOCKERS_UNRECOGNIZED")
    passed = gate.get("research_gate_passed") is True
    root = Path(private_root).expanduser().resolve()
    path = root / "research-rework" / ("product-" + str(product_id)) / "ledger.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        obj = {"schema": "saeit.factory.research-rework.v1", "product_id": product_id,
               "history": []}
    if obj.get("schema") != "saeit.factory.research-rework.v1" or obj.get("product_id") != product_id:
        raise RuntimeError("RESEARCH_REWORK_LEDGER_MISMATCH")
    # A research gate never supplies commercial approval; even a research PASS
    # still requires scientific, owner and legal/product signoff.
    status = "review_research_evidence" if passed else "research_correction_required"
    key = _digest({"source_sha256": entry.get("sha256"), "blockers": blockers,
                   "passed": passed})
    if obj["history"] and obj["history"][-1].get("fingerprint") == key:
        return {"product_id": product_id, "status": status, "updated": False}
    obj["history"].append({
        "revision": len(obj["history"]) + 1,
        "created_at_utc": stamp(),
        "fingerprint": key,
        "source_dossier_sha256": str(entry.get("sha256", ""))[:64],
        "status": status,
        "blocking_reasons": sorted(set(blockers)),
        "corrective_actions": [
            {"reason": code, "instruction": RESEARCH_FIX_PLANS[code]}
            for code in sorted(set(blockers))
        ],
        "research_evidence_counts": gate.get("counts", {}),
        "independent_review_required": True,
    })
    obj["current_status"] = status
    obj["public_sale_allowed"] = False
    _atomic_json(path, obj)
    return {"product_id": product_id, "status": status, "updated": True}


def summarize_research(private_root):
    root = Path(private_root).expanduser().resolve() / "research-rework"
    counts = {"research_correction_required": 0, "review_research_evidence": 0}
    if root.is_dir():
        for path in root.glob("product-*/ledger.json"):
            obj = json.loads(path.read_text(encoding="utf-8"))
            key = str(obj.get("current_status", "unknown"))
            counts[key] = counts.get(key, 0) + 1
    return counts
