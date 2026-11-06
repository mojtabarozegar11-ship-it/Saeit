"""Read-only verification of an existing private factory self-upgrade dossier.

This verifies the producer's schema and internal consistency, not independent
deployment or measurable improvement of the live application.
"""

import hashlib
import json
import time
from pathlib import Path


EXPECTED_SCHEMA = "saeit.factory.code-self-upgrade.v1"
MAX_BYTES = 1_000_000
MAX_AGE_SECONDS = 48 * 3600


def inspect_isolated_proof(path, *, now=None):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("ISOLATED_UPGRADE_PROOF_MISSING_OR_UNSAFE")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("ISOLATED_UPGRADE_PROOF_TOO_LARGE")
    age = (time.time() if now is None else now) - path.stat().st_mtime
    if not (0 <= age <= MAX_AGE_SECONDS):
        raise ValueError("ISOLATED_UPGRADE_PROOF_STALE")

    raw = path.read_bytes()
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

    return {
        "proof_sha256": hashlib.sha256(raw).hexdigest(),
        "proof_age_seconds": int(age),
        "candidate_count": count,
        "preexisting_verified_repairs": existing,
        "production_code_promotions": 0,
        "verification_scope": "fresh_private_dossier_schema_and_consistency_only",
    }
