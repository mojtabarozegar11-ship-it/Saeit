"""Read-only verification of an existing private factory self-upgrade dossier.

This verifies the producer's schema and internal consistency, not independent
deployment or measurable improvement of the live application.
"""

import hashlib
import json
import re
import time
from pathlib import Path


EXPECTED_SCHEMA = "saeit.factory.code-self-upgrade.v1"
MAX_BYTES = 1_000_000
MAX_AGE_SECONDS = 48 * 3600
MAX_CANDIDATE_BYTES = 1_000_000
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_REPAIR_PATHS = frozenset((
    "scripts/factory_research_triage.py",
    "scripts/factory_specialist_pilots.py",
    "scripts/factory_first_product_pilot.py",
    "scripts/factory_public_library_adapter.py",
))


def _symlink_in_path(path):
    return any(component.is_symlink() for component in (path, *path.parents))


def _safe_source_path(value):
    if (type(value) is not str or not value.endswith(".py") or "\\" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or not value.startswith(("scripts/", "ops/factory-toolchain/"))):
        raise ValueError("ISOLATED_UPGRADE_PROOF_UNSAFE_SOURCE_PATH")
    return value


def _hash(value):
    if type(value) is not str or not SHA256.fullmatch(value):
        raise ValueError("ISOLATED_UPGRADE_PROOF_INVALID_SOURCE_HASH")
    return value


def _verify_candidate_artifact(dossier_path, index, item):
    candidate_path = (
        dossier_path.parent / ("candidate-" + str(index))
        / item["path"].rsplit("/", 1)[-1]
    )
    if _symlink_in_path(candidate_path) or not candidate_path.is_file():
        raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_MISSING_OR_UNSAFE")
    if candidate_path.stat().st_size > MAX_CANDIDATE_BYTES:
        raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_TOO_LARGE")
    raw = candidate_path.read_bytes()
    if (len(raw) > MAX_CANDIDATE_BYTES
            or hashlib.sha256(raw).hexdigest() != item["candidate_sha256"]):
        raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_HASH_MISMATCH")


def inspect_isolated_proof(path, *, now=None, source_root=None):
    path = Path(path)
    if _symlink_in_path(path) or not path.is_file():
        raise ValueError("ISOLATED_UPGRADE_PROOF_MISSING_OR_UNSAFE")
    if path.stat().st_mode & 0o077:
        raise ValueError("ISOLATED_UPGRADE_PROOF_PERMISSIONS_UNSAFE")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("ISOLATED_UPGRADE_PROOF_TOO_LARGE")
    age = (time.time() if now is None else now) - path.stat().st_mtime
    if not (0 <= age <= MAX_AGE_SECONDS):
        raise ValueError("ISOLATED_UPGRADE_PROOF_STALE")

    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError("ISOLATED_UPGRADE_PROOF_TOO_LARGE")
    try:
        proof = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("ISOLATED_UPGRADE_PROOF_INVALID_JSON") from exc
    if not isinstance(proof, dict) or proof.get("schema") != EXPECTED_SCHEMA:
        raise ValueError("ISOLATED_UPGRADE_PROOF_SCHEMA_MISMATCH")

    fields = (
        "candidate_count", "candidates_with_measured_improvement",
        "preexisting_verified_repairs", "validated_repair_rule_coverage",
        "unresolved_known_security_regressions", "production_code_promotions",
    )
    if any(type(proof.get(field)) is not int or proof[field] < 0 for field in fields):
        raise ValueError("ISOLATED_UPGRADE_PROOF_COUNTER_INVALID")
    count = proof["candidate_count"]
    existing = proof["preexisting_verified_repairs"]
    if (
        proof["candidates_with_measured_improvement"] != count
        or proof["validated_repair_rule_coverage"] != count + existing
        or proof["unresolved_known_security_regressions"] != 0
        or proof["production_code_promotions"] != 0
        or proof.get("whole_code_autonomous_evolution_complete") is not False
    ):
        raise ValueError("ISOLATED_UPGRADE_PROOF_CLAIMS_INCONSISTENT")
    if (
        not isinstance(proof.get("candidates"), list)
        or len(proof["candidates"]) != count
        or not isinstance(proof.get("already_protected_source_modules"), list)
        or len(proof["already_protected_source_modules"]) != existing
    ):
        raise ValueError("ISOLATED_UPGRADE_PROOF_ENTRIES_INCONSISTENT")

    # A counter-only dossier can be forged accidentally or deliberately. Check
    # manifest membership, unique repaired paths, the before/after observations,
    # and the actual quarantined candidate bytes before accepting its claims.
    scanned = proof.get("factory_python_files_scanned")
    remaining = proof.get("modules_without_proven_repair")
    if (type(scanned) is not int or scanned < count + existing
            or type(remaining) is not int or remaining != scanned - count - existing
            or proof.get("private_verified_code_edits") != count):
        raise ValueError("ISOLATED_UPGRADE_PROOF_SCAN_COUNTS_INCONSISTENT")
    inventory = proof.get("module_sha256_inventory")
    if not isinstance(inventory, list) or len(inventory) != scanned:
        raise ValueError("ISOLATED_UPGRADE_PROOF_INVENTORY_INCONSISTENT")
    inventory_hashes = {}
    inventory_sizes = {}
    for entry in inventory:
        if not isinstance(entry, dict):
            raise ValueError("ISOLATED_UPGRADE_PROOF_INVENTORY_INVALID")
        source = _safe_source_path(entry.get("path"))
        digest = _hash(entry.get("source_sha256"))
        size = entry.get("source_bytes")
        if (source in inventory_hashes or type(size) is not int
                or not 0 <= size <= MAX_CANDIDATE_BYTES):
            raise ValueError("ISOLATED_UPGRADE_PROOF_INVENTORY_INVALID")
        inventory_hashes[source] = digest
        inventory_sizes[source] = size

    # Optional independent anchoring against the actual private source snapshot.
    # A dossier and its inventory hashes alone do not prove the source bytes.
    source_files_hash_verified = 0
    if source_root is not None:
        root = Path(source_root).expanduser().absolute()
        if _symlink_in_path(root) or not root.is_dir():
            raise ValueError("ISOLATED_UPGRADE_PROOF_SOURCE_ROOT_UNSAFE")
        for source, expected_hash in inventory_hashes.items():
            actual = root / source
            if _symlink_in_path(actual) or not actual.is_file():
                raise ValueError("ISOLATED_UPGRADE_PROOF_SOURCE_FILE_MISSING_OR_UNSAFE")
            stat = actual.stat()
            if stat.st_size != inventory_sizes[source] or stat.st_size > MAX_CANDIDATE_BYTES:
                raise ValueError("ISOLATED_UPGRADE_PROOF_SOURCE_SIZE_MISMATCH")
            raw_source = actual.read_bytes()
            if (len(raw_source) != inventory_sizes[source]
                    or hashlib.sha256(raw_source).hexdigest() != expected_hash):
                raise ValueError("ISOLATED_UPGRADE_PROOF_SOURCE_HASH_MISMATCH")
            source_files_hash_verified += 1

    checked = set()
    for index, item in enumerate(proof["candidates"], start=1):
        if not isinstance(item, dict):
            raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_INVALID")
        source = _safe_source_path(item.get("path"))
        baseline_sha = _hash(item.get("baseline_sha256"))
        _hash(item.get("candidate_sha256"))
        if (source in checked or inventory_hashes.get(source) != baseline_sha
                or item.get("changed_source") is not True
                or item.get("private_only") is not True
                or item.get("negative_case_reproduced") is not True
                or item.get("security_regression_prevented") is not True
                or item.get("measured_quality_improvement") is not True
                or item.get("baseline") != {"blocked": False, "escaped": True}
                or item.get("candidate") != {"blocked": True, "escaped": False}):
            raise ValueError("ISOLATED_UPGRADE_PROOF_CANDIDATE_CLAIMS_INVALID")
        checked.add(source)
        _verify_candidate_artifact(path, index, item)
    for item in proof["already_protected_source_modules"]:
        if not isinstance(item, dict):
            raise ValueError("ISOLATED_UPGRADE_PROOF_EXISTING_REPAIR_INVALID")
        source = _safe_source_path(item.get("path"))
        source_sha = _hash(item.get("source_sha256"))
        if (source in checked or inventory_hashes.get(source) != source_sha
                or item.get("negative_case_blocked") is not True
                or item.get("new_code_edit_performed") is not False):
            raise ValueError("ISOLATED_UPGRADE_PROOF_EXISTING_REPAIR_INVALID")
        checked.add(source)

    # This contract is intentionally exact: a fabricated unrelated source
    # inventory may not substitute for the four reviewed security repairs.
    if checked != EXPECTED_REPAIR_PATHS:
        raise ValueError("ISOLATED_UPGRADE_PROOF_REPAIR_ALLOWLIST_MISMATCH")

    return {
        "source_files_hash_verified": source_files_hash_verified,
        "source_verification_scope": (
            "staged_source_snapshot_hashes_only" if source_root is not None
            else "source_root_not_provided"
        ),
        "candidate_artifacts_hash_verified": count,
        "source_manifest_entries_checked": scanned,
        "verification_scope": (
            "private_dossier_internal_consistency_and_candidate_hashes_only"
        ),
        "proof_sha256": hashlib.sha256(raw).hexdigest(),
        "proof_age_seconds": int(age),
        "candidate_count": count,
        "preexisting_verified_repairs": existing,
        "production_code_promotions": 0,
     }
