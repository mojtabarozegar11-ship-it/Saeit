"""Bounded, deterministic new-generation CODE factory for private MojPlayWin.

Produces actual, SHA-verified Gen65+ Python candidate modules in a PRIVATE
quarantine directory from fixed audited recipes and bounded numeric metrics.
Generated code is NOT imported, executed, installed, promoted or published.
No external dependencies, untrusted source interpolation, network, subprocess,
payments, customer data, shared runtime or cross-tenant access.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile

TENANT = "mojplaywin-main"
MIN_PROMOTION_SAMPLES = 12
MIN_NEW_OUTCOMES = 6
MAX_GENERATION = 72
MAX_OUTCOMES = 300
MAX_CODE_BYTES = 9500
MAX_MANIFEST_BYTES = 4500
MAX_FACTORY_FILES = 20

# These are deliberately executable new algorithms, not a renamed Gen64.
# Only bounded integer parameters from verified private reviews interpolate here.
CODE_TEMPLATE = '''"""Private, quarantined {generation} evolutionary candidate; never production-authorized.

Origin: MojPlayWin verified fixed-recipe generation factory.
Includes Wilson confidence lower bound, source-verification abstention,
and asymmetric false-acceptance penalty (unlike base Gen64).
"""
from __future__ import annotations
from math import sqrt

GENERATION = {generation}
PARENT_GENERATION = {parent}
QUALITY_MIN = {quality}
SOURCES_MIN = {sources}
EVIDENCE_MIN = 12
TENANT = "mojplaywin-main"


def wilson_precision_lower(successes: int, total: int) -> float:
    if not isinstance(successes, int) or not isinstance(total, int) or total < 1:
        return 0.0
    if successes < 0 or successes > total:
        return 0.0
    z = 1.96
    p = successes / total
    denominator = 1 + z*z/total
    center = p + z*z/(2*total)
    uncertainty = z*sqrt((p*(1-p) + z*z/(4*total))/total)
    return max(0.0, (center - uncertainty)/denominator)


class Generation{generation}Controller:
    """Evidence-and-confidence-gated classification. Not connected to publishing."""
    generation = GENERATION
    parent_generation = PARENT_GENERATION

    def classify(self, quality, source_count, evidence_verified=False):
        if evidence_verified is not True:
            return "abstain_unverified"
        if isinstance(quality, bool) or not isinstance(quality, (int, float)):
            return "abstain_invalid_quality"
        if not isinstance(source_count, int) or isinstance(source_count, bool):
            return "abstain_invalid_sources"
        if not (0 <= quality <= 100 and 0 <= source_count <= 30):
            return "abstain_out_of_bounds"
        return "hold_for_review" if quality < QUALITY_MIN or source_count < SOURCES_MIN else "candidate_ready_for_human_review"

    def benchmark(self, outcomes):
        rows = list(outcomes)
        if len(rows) < EVIDENCE_MIN or len(rows) > 300:
            return dict(generation=GENERATION, approved=False, reason="insufficient_or_unbounded_evidence")
        tp = tn = fp = fn = 0
        for row in rows:
            decision = self.classify(row["quality"], row["source_count"], row.get("verified") is True)
            guess = decision == "candidate_ready_for_human_review"
            actual = row["ready"] is True
            if guess and actual:
                tp += 1
            elif guess and not actual:
                fp += 1
            elif not guess and actual:
                fn += 1
            else:
                tn += 1
        confidence = wilson_precision_lower(tp, tp+fp)
        utility = (tp + tn - 4*fp - fn)/len(rows)
        # A low-confidence policy is not granted independent publishing rights.
        return dict(generation=GENERATION, approved=False, reason="human_review_and_external_promotion_required",
                    precision_lower=round(confidence, 6), utility=round(utility, 6),
                    true_positive=tp, true_negative=tn,
                    false_positive=fp, false_negative=fn, sample_size=len(rows))
'''


def private(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and not (path.stat().st_mode & 0o077)


def _atomic(path: Path, raw: bytes) -> None:
    if len(raw) > MAX_CODE_BYTES or path.is_symlink():
        raise RuntimeError("unsafe_generated_artifact")
    fd, temp = tempfile.mkstemp(prefix=".mpwgen-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)


def _read_json(path: Path):
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise RuntimeError("unsafe_generation_manifest")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict) or value.get("tenant") != TENANT:
        raise RuntimeError("invalid_generation_tenant")
    return value


def _code(generation: int, quality: int, sources: int) -> bytes:
    if not (65 <= generation <= MAX_GENERATION and 90 <= quality <= 99 and 1 <= sources <= 5):
        raise ValueError("unapproved_generation_parameters")
    src = CODE_TEMPLATE.format(generation=generation, parent=generation-1,
                               quality=quality, sources=sources)
    raw = src.encode("utf-8")
    if len(raw) > MAX_CODE_BYTES:
        raise RuntimeError("generated_module_too_large")
    compile(src, "generated_gen_candidate.py", "exec")
    return raw


def _candidate_manifest(generation, quality, sources, code, outcomes):
    digest = hashlib.sha256(code).hexdigest()
    record_ids = sorted({row["id"] for row in outcomes})
    return {"tenant": TENANT,
            "generation": generation, "parent_generation": generation-1,
            "module": f"generation{generation}.py", "code_sha256": digest,
            "capability_gene": "wilson_confidence_source_verified_asymmetric_safety_gate",
            "quality_threshold": quality, "minimum_sources": sources,
            "verified_outcome_count": len(record_ids),
            "evidence_fingerprint": hashlib.sha256("|".join(record_ids).encode()).hexdigest(),
            "mode": "quarantined_experimental_candidate",
            "promotion_authorized": False, "executed_in_production": False,
            "auto_deploy": False, "financial_authority": False,
            "requires_benchmark_and_human_approval": True}


def _evidence(rows):
    if not isinstance(rows, list) or len(rows) > MAX_OUTCOMES:
        raise ValueError("unbounded_evidence")
    result = []
    ids = set()
    for row in rows:
        if (not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or len(row["id"]) > 128
            or row["id"] in ids
            or row.get("kind") not in ("research_digest", "product_blueprint")
            or isinstance(row.get("quality"), bool)
            or not isinstance(row.get("quality"), (int, float))
            or not 0 <= row["quality"] <= 100
            or not isinstance(row.get("source_count"), int)
            or isinstance(row.get("source_count"), bool)
            or not 0 <= row["source_count"] <= 30
            or not isinstance(row.get("ready"), bool)):
            raise ValueError("unverified_generation_evidence")
        ids.add(row["id"])
        result.append(row)
    return result


def produce(private_root: Path, reviewed_outcomes: list[dict],
            demonstrated_policy_improvement: bool = False) -> dict:
    """Create Gen65 once, and future candidates ONLY when materially justified.

    Every later candidate requires >=12 verified outcomes, 6 unseen outcomes
    and a separately established private policy improvement signal.
    A candidate is never activated by the factory.
    """
    if not private(private_root):
        raise RuntimeError("private_evolution_root_unverified")
    outcomes = _evidence(reviewed_outcomes)
    folder = private_root / "generations"
    if folder.exists():
        if not private(folder):
            raise RuntimeError("generation_quarantine_not_private")
    else:
        folder.mkdir(mode=0o700)
    if len(list(folder.iterdir())) > MAX_FACTORY_FILES:
        raise RuntimeError("generation_factory_storage_cap")
    manifests = sorted(folder.glob("generation*.json"))
    latest = None
    for item in manifests:
        manifest = _read_json(item)
        generation = manifest.get("generation")
        if (not isinstance(generation, int) or isinstance(generation, bool)
            or not 65 <= generation <= MAX_GENERATION
            or item.name != f"generation{generation}.json"):
            raise RuntimeError("generation_manifest_name_invalid")
        source = folder / f"generation{generation}.py"
        if (source.is_symlink() or not source.is_file()
            or source.stat().st_size > MAX_CODE_BYTES
            or hashlib.sha256(source.read_bytes()).hexdigest() != manifest.get("code_sha256")):
            raise RuntimeError("generation_code_provenance_mismatch")
        if latest is None or generation > latest["generation"]:
            latest = manifest
    if latest is not None:
        next_generation = latest["generation"] + 1
        if next_generation > MAX_GENERATION:
            return {"status": "generation_limit_reached", "generation": latest["generation"]}
        old_count = int(latest.get("verified_outcome_count", 0))
        if (len(outcomes) < MIN_PROMOTION_SAMPLES
            or len(outcomes) - old_count < MIN_NEW_OUTCOMES
            or demonstrated_policy_improvement is not True):
            return {"status": "current_candidate_retained_pending_evidence",
                    "generation": latest["generation"],
                    "verified_outcomes": len(outcomes),
                    "requires_new_evidence": max(0, old_count+MIN_NEW_OUTCOMES-len(outcomes)),
                    "candidate_code_verified": True,
                    "promoted": False}
        # New and distinct safe numeric recipe, based ONLY on bounded quality evidence.
        false_acceptance = sum(1 for row in outcomes
                               if row["quality"] >= 95 and row["source_count"] >= 2 and not row["ready"])
        quality = min(99, 95 + (1 if false_acceptance else 0)
                     + (next_generation-66) % 2)
        sources = min(5, 2 + (next_generation-65) // 3)
    else:
        next_generation = 65
        quality, sources = 95, 2
    source = _code(next_generation, quality, sources)
    manifest = _candidate_manifest(next_generation, quality, sources, source, outcomes)
    code_path = folder / manifest["module"]
    manifest_path = folder / f"generation{next_generation}.json"
    if code_path.exists() or manifest_path.exists():
        raise RuntimeError("candidate_generation_conflict")
    _atomic(code_path, source)
    try:
        _atomic(manifest_path, json.dumps(manifest, sort_keys=True).encode("utf-8"))
    except Exception:
        if code_path.is_file() and not code_path.is_symlink():
            code_path.unlink()
        raise
    return {"status": "generated_new_quarantined_python_generation",
            "generation": next_generation,
            "parent_generation": next_generation-1,
            "code_sha256": manifest["code_sha256"],
            "source_file": manifest["module"],
            "verified_outcomes": len(outcomes),
            "new_capability_gene": manifest["capability_gene"],
            "promoted": False, "production_changed": False}
