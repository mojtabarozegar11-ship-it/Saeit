#!/usr/bin/env python3
"""QC-only immutable handoff of proven-v003 artifacts to real scientific review.
Run independently, fail-closed; no AI, PhD, rights or commercial approval is minted.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = "saeit.factory.qc.v003.scientific-review-handoff.v1"
NAME = re.compile(r"WO-[0-9]{8}--r001\.json\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
PENDING = frozenset({
    "P0_PRIMARY_FULLTEXT_SCIENTIFIC_CHECK_PENDING",
    "P0_INDEPENDENT_SPECIALIST_REVIEW_PENDING",
    "P0_LOCAL_REGULATION_AND_FIELD_SAFETY_PENDING",
    "P0_QC1000_ALL_100_CRITERIA_UNVERIFIED",
})
REQUIRED_REVIEWS = (
    "verify_original_primary_fulltext_and_exact_cited_pages",
    "independent_claim_to_source_trace_and_retraction_check",
    "phd_level_agronomy_domain_accuracy_and_novelty",
    "iran_field_conditions_local_law_and_biosafety",
    "external_reproduction_with_raw_results_and_uncertainty",
    "copyright_data_license_and_distribution_rights",
    "1000_version_bound_distinct_execution_checks_from_trusted_runner",
    "authenticated_independent_reviewer_identity_and_signed_verdict",
)

class QCBlocked(ValueError):
    pass

def require(ok, code):
    if not ok:
        raise QCBlocked(code)

def digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()

def dependency(path, name):
    p = Path(path)
    require(p.is_file() and not p.is_symlink(), "UNSAFE_QC_DEPENDENCY")
    spec = importlib.util.spec_from_file_location(name, str(p))
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance

def packet(name, manifest, stored_qc, fresh_qc):
    require(NAME.fullmatch(name) is not None, "BAD_ORDER_ID")
    require(isinstance(manifest, dict) and isinstance(stored_qc, dict)
            and isinstance(fresh_qc, dict), "BAD_REVIEW_EVIDENCE")
    require(stored_qc == fresh_qc, "QC_RESULT_MISMATCH_ON_FRESH_REEXECUTION")
    require(manifest.get("artifact_revision") == 3
            and manifest.get("source_revision") == 1
            and manifest.get("order_file") == name,
            "MISSING_IMMUTABLE_V003_REVISION")
    require(manifest.get("quality1000_approved") is False
            and manifest.get("commercial_release") is False
            and manifest.get("public_distribution_allowed") is False,
            "FORGED_MANIFEST_RELEASE")
    require(stored_qc.get("mechanical_integrity_pass") is True
            and stored_qc.get("independent_quality1000_approved") is False
            and stored_qc.get("commercial_release") is False
            and stored_qc.get("public_distribution_allowed") is False
            and stored_qc.get("revision") == 3,
            "QC_MECHANICAL_OR_RELEASE_GUARD_INVALID")
    findings = stored_qc.get("critical_findings")
    require(isinstance(findings, list) and set(findings) == PENDING
            and len(findings) == len(PENDING),
            "UNRESOLVED_MECHANICAL_FAILURE_OR_FORGED_SCIENTIFIC_PASS")
    artifact = stored_qc.get("artifact_sha256")
    require(isinstance(artifact, str) and SHA.fullmatch(artifact)
            and artifact == manifest.get("zip_sha256"), "V003_ARCHIVE_HASH_MISMATCH")
    manifest_sha = digest(manifest)
    require(stored_qc.get("v003_manifest_sha256") == manifest_sha,
            "V003_QC_MANIFEST_BINDING_MISMATCH")
    measurements = stored_qc.get("measurements")
    require(isinstance(measurements, dict)
            and all(isinstance(measurements.get(loc), dict)
                    for loc in ("fa-IR", "en-US")), "V003_BILINGUAL_MEASUREMENTS_MISSING")
    return {
        "schema": SCHEMA, "order_file": name, "order_id": manifest.get("order_id"),
        "revision": 3, "artifact_sha256": artifact,
        "v003_manifest_sha256": manifest_sha, "reexecuted_mechanical_qc_sha256": digest(fresh_qc),
        "scientific_review_state": "PENDING_INDEPENDENT_VERIFIED_EVIDENCE",
        "mechanical_check_reexecuted_and_passed": True,
        "critical_scientific_gates": list(REQUIRED_REVIEWS),
        "scientific_findings_still_pending": sorted(PENDING),
        "independent_review_executed": False,
        "scientific_quality_certified": False,
        "quality1000_approved": False, "commercial_release": False,
        "public_distribution_allowed": False,
        "stage7_handoff_authorized": False,
        "immutable_revision_hash_binding": True,
    }

def execute(root, stage34, revised_qc, batch):
    area = Path(root).resolve() / "production-instructions"
    source = area / "stage-05/source-grounded-v003-manifests"
    qcdir = area / "stage-06/source-grounded-v003-qc"
    require(source.is_dir() and not source.is_symlink()
            and qcdir.is_dir() and not qcdir.is_symlink(), "PRIVATE_QC_INPUT_MISSING")
    inbox = area / "stage-06/scientific-review-inbox-v003"
    blocked = area / "stage-06/scientific-review-inbox-v003-blocked"
    stage34.private_dir(inbox)
    stage34.private_dir(blocked)
    lock = area / ".qc-v003-review-handoff.lock"
    require(not lock.is_symlink(), "QC_LOCK_SYMLINK")
    with lock.open("a+b") as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        names = sorted(p.name for p in source.iterdir()
                       if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
        cursor = area / "stage-06/scientific-review-handoff-cursor.json"
        require(not cursor.is_symlink(), "QC_CURSOR_LINK")
        if cursor.is_file():
            old = stage34.read(cursor)
            require(old.get("schema") == SCHEMA and type(old.get("next_index")) is int
                    and old["next_index"] >= 0, "QC_CURSOR_INVALID")
            start = old["next_index"] % len(names) if names else 0
        else:
            start = 0
        chosen = [names[(start+i) % len(names)]
                  for i in range(min(batch, len(names)))]
        counts = Counter()
        for name in chosen:
            try:
                manifest = stage34.read(source / name)
                saved = stage34.read(qcdir / name)
                # Run the complete original v003 QC again against archive bytes.
                live = revised_qc.check_one(area, name, stage34, None)
                payload = packet(name, manifest, saved, live)
                created = stage34.once(inbox / name, payload)
                counts["new_scientific_review_requests"] += int(created)
                counts["verified_existing_requests"] += int(not created)
            except (OSError, RuntimeError, QCBlocked, ValueError, TypeError,
                    KeyError, UnicodeError, json.JSONDecodeError) as error:
                counts["blocked_artifacts"] += 1
                stage34.atomic(blocked / name, {
                    "schema": SCHEMA, "order_file": name,
                    "reason": type(error).__name__ + ":" + str(error)[:140],
                    "needs_fresh_artifact_or_qc_evidence": True,
                    "quality1000_approved": False, "commercial_release": False,
                    "public_distribution_allowed": False})
        stage34.atomic(cursor, {"schema": SCHEMA,
                        "next_index": (start + len(chosen)) % len(names) if names else 0})
        total = sum(1 for p in inbox.iterdir()
                    if p.is_file() and not p.is_symlink() and NAME.fullmatch(p.name))
        report = {
            "schema": SCHEMA, "updated_utc": datetime.now(timezone.utc).isoformat(),
            "private_v003_products": len(names), "rechecked_this_tick": len(chosen),
            "mechanical_qc_reexecuted": len(chosen) - counts["blocked_artifacts"],
            "independent_scientific_review_requests_total": total,
            **dict(counts),
            "real_external_scientific_review_completed": 0,
            "trusted_1000_execution_runner_enrolled_by_this_worker": False,
            "scientific_quality1000_approvals_created": 0,
            "commercial_releases": 0, "sites_modified": False,
            "next_action": "AUTHENTIC_DOMAIN_REVIEW_AND_TRUSTED_EXECUTION_EVIDENCE",
        }
        stage34.atomic(area / "stage-06/scientific-review-handoff-health.json", report)
        return report

def selftest():
    m = {"artifact_revision":3,"source_revision":1,"order_file":"WO-00000001--r001.json",
         "order_id":"WO-00000001","zip_sha256":"a"*64,
         "quality1000_approved":False,"commercial_release":False,
         "public_distribution_allowed":False}
    q = {"revision":3,"artifact_sha256":"a"*64,"v003_manifest_sha256":digest(m),
         "mechanical_integrity_pass":True,"independent_quality1000_approved":False,
         "commercial_release":False,"public_distribution_allowed":False,
         "critical_findings":sorted(PENDING),
         "measurements":{"fa-IR":{},"en-US":{}}}
    p = packet("WO-00000001--r001.json",m,q,dict(q))
    assert p["quality1000_approved"] is False and not p["independent_review_executed"]
    q["artifact_sha256"]="b"*64
    try:
        packet("WO-00000001--r001.json",m,q,dict(q))
        raise AssertionError("tampering accepted")
    except QCBlocked:
        pass
    print("QC_V003_HANDOFF_SELFTEST=PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--factory-private")
    p.add_argument("--stage34-worker")
    p.add_argument("--v003-qc-worker")
    p.add_argument("--batch",type=int,default=25)
    a=p.parse_args()
    if a.selftest:
        selftest()
        return
    require(a.factory_private and a.stage34_worker and a.v003_qc_worker,
            "REQUIRED_QC_ARGUMENTS_MISSING")
    require(1 <= a.batch <= 250,"QC_BATCH_INVALID")
    print(json.dumps(execute(a.factory_private,
          dependency(a.stage34_worker,"qc_v003_stage34"),
          dependency(a.v003_qc_worker,"qc_v003_mechanical"),a.batch),
          ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print("QC_V003_HANDOFF_ERROR:"+type(exc).__name__+":"+str(exc)[:170],file=sys.stderr)
        raise SystemExit(1)
