"""Operate *verified generated Gen65* on MojPlayWin private editorial evidence.

The Gen64 public-site master and its exact APIs remain unchanged. Gen65 is
activated solely as a recurring, read-only quality-recommendation worker by an
owner-approved, private on-disk flag. Each cycle executes byte-for-byte known
Gen65 Python code, never unverified dynamic generated code. No network access,
publication, financial actions, production writes, or shared Django changes.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mpw_v91_port.generation_factory import _code, TENANT, MAX_GENERATION

GENERATION = 65
EXPECTED_CODE = _code(65, 95, 2)
EXPECTED_SHA = hashlib.sha256(EXPECTED_CODE).hexdigest()
CONTROL_NAME = "gen65_operation_enabled.json"
REPORT_NAME = "gen65_operational_report.json"
MAX_INPUT_BYTES = 4500
MAX_REPORT_BYTES = 9000


def _private(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077) == 0


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise RuntimeError("gen65_invalid_private_control_or_manifest")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("gen65_invalid_private_json_object")
    return value


def _write(path: Path, value: dict) -> None:
    if path.is_symlink():
        raise RuntimeError("gen65_symlink_report_refused")
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_REPORT_BYTES:
        raise RuntimeError("gen65_report_exceeds_bound")
    fd, temp = tempfile.mkstemp(prefix=".private-gen65-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def _verified_class(folder: Path):
    if not _private(folder):
        raise RuntimeError("gen65_quarantine_not_private")
    manifest_path = folder / "generation65.json"
    source_path = folder / "generation65.py"
    manifest = _read(manifest_path)
    if (manifest.get("tenant") != TENANT
        or manifest.get("generation") != GENERATION
        or manifest.get("parent_generation") != 64
        or manifest.get("quality_threshold") != 95
        or manifest.get("minimum_sources") != 2
        or manifest.get("module") != source_path.name
        or manifest.get("code_sha256") != EXPECTED_SHA
        or manifest.get("promotion_authorized") is not False
        or manifest.get("auto_deploy") is not False
        or manifest.get("financial_authority") is not False
        or not source_path.is_file()
        or source_path.is_symlink()
        or source_path.stat().st_size != len(EXPECTED_CODE)):
        raise RuntimeError("gen65_manifest_source_attestation_failed")
    actual = source_path.read_bytes()
    if actual != EXPECTED_CODE or hashlib.sha256(actual).hexdigest() != EXPECTED_SHA:
        raise RuntimeError("gen65_source_differs_from_audited_recipe")
    # Exact fixed-recipe bytes are verified before any dynamic code is executed.
    # This is NOT an OS sandbox: it relies on integrity of the audited recipe.
    scope = {"__name__": "_private_gen65_evaluator"}
    exec(compile(actual, str(source_path), "exec"), scope)
    controller = scope["Generation65Controller"]()
    if controller.generation != 65 or controller.parent_generation != 64:
        raise RuntimeError("gen65_controller_identity_mismatch")
    return controller


def _valid_row(row: dict) -> bool:
    return (isinstance(row, dict)
        and isinstance(row.get("id"), str) and len(row["id"]) <= 128
        and row.get("kind") in ("research_digest", "product_blueprint")
        and isinstance(row.get("ready"), bool)
        and isinstance(row.get("source_count"), int)
        and not isinstance(row.get("source_count"), bool)
        and 0 <= row["source_count"] <= 30
        and isinstance(row.get("quality"), (float, int))
        and not isinstance(row.get("quality"), bool)
        and 0 <= row["quality"] <= 100)


def operate(private_root: Path, reviewed_outcomes: list[dict],
            epoch: int, timestamp: str) -> dict:
    """Run a real Gen65 classification pass; never return publication authority."""
    if not _private(private_root):
        raise RuntimeError("gen65_root_not_private")
    enable = private_root / CONTROL_NAME
    if not enable.exists():
        return {"status": "gen65_not_enabled", "generation": GENERATION,
                "private_only": True}
    config = _read(enable)
    if not (config.get("tenant") == TENANT
            and config.get("active_private_generation") == GENERATION
            and config.get("controller_sha256") == EXPECTED_SHA
            and config.get("enabled") is True
            and config.get("scope") == "private_verified_review_only"):
        raise RuntimeError("gen65_owner_enable_flag_invalid")
    controller = _verified_class(private_root / "generations")
    if (not isinstance(reviewed_outcomes, list)
        or len(reviewed_outcomes) > 300
        or any(not _valid_row(row) for row in reviewed_outcomes)
        or len({row["id"] for row in reviewed_outcomes}) != len(reviewed_outcomes)):
        raise RuntimeError("gen65_unverified_or_unbounded_reviews")
    ready, held, declined = 0, 0, 0
    for row in reviewed_outcomes:
        prediction = controller.classify(row["quality"], row["source_count"], True)
        if prediction == "candidate_ready_for_human_review":
            ready += 1
        elif prediction == "hold_for_review":
            held += 1
        else:
            declined += 1
    benchmark = controller.benchmark([
        {"quality": row["quality"], "source_count": row["source_count"],
         "ready": row["ready"], "verified": True}
        for row in reviewed_outcomes
    ])
    # Gen65 is operational as independent private, read-only evaluator. It
    # cannot promote itself or become the production master on this signal.
    result = {
        "status": "gen65_operational_private",
        "tenant": TENANT,
        "active_private_generation": GENERATION,
        "existing_public_master_generation": 64,
        "controller_sha256": EXPECTED_SHA,
        "observed_utc": str(timestamp),
        "cycle_epoch": int(epoch),
        "verified_observations": len(reviewed_outcomes),
        "ready_for_human_review": ready,
        "held_for_review": held,
        "abstained": declined,
        "confidence_precision_lower": benchmark.get("precision_lower"),
        "benchmark_reason": benchmark["reason"],
        "meets_statistical_promotion_gate": len(reviewed_outcomes) >= 12,
        "self_promoted": False,
        "public_site_changed": False,
        "auto_published": False,
        "financial_actions": 0,
        "shared_runtime_modified": False,
        "tenant_isolated": True,
    }
    _write(private_root / REPORT_NAME, result)
    return result
