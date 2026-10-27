#!/usr/bin/env python3
"""Public release hard-stop for new 100x10 factory manufactured products.

Private staging remains legal and isolated; existing older free-edition release
is not silently republished or revoked by this adapter. Newly marked 100x10
builds require four externally identified Ed25519 signatures on exact bytes.
"""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
import zipfile

SHA=re.compile(r"^[a-f0-9]{64}$")

def _digest_file(path):
    target=Path(path)
    if not target.is_file() or target.is_symlink():
        raise ValueError("QC1000_REAL_BYTES_MISSING_OR_LINK")
    h=hashlib.sha256()
    with target.open("rb") as stream:
        for piece in iter(lambda:stream.read(1024*1024),b""):
            h.update(piece)
    return h.hexdigest()

def _verify_executed_qc1000(root,container,artifact_sha,decision):
    """Actual signed, distinct 1000-case suite + doctoral dossier.

    No self-asserted 100x10 score, manifest booleans or fabricated expert
    identities can substitute for authenticated executed test receipts.
    """
    suite=container/"real-qc1000-suite.json"
    dossier=container/"doctoral-dossier.json"
    pubkey=root/"quality-trust"/"trusted-execution-runner-rsa3072.pem"
    module_path=Path(__file__).resolve().with_name("factory_real_qc1000_live_monitor_20261023.py")
    pinned=os.environ.get("FACTORY_QC1000_TRUSTED_RUNNER_PUBKEY_SHA256","")
    if (not isinstance(decision,dict) or not SHA.fullmatch(pinned)
            or any(p.is_symlink() or not p.is_file() for p in
                   (suite,dossier,pubkey,module_path))
            or not 0<suite.stat().st_size<=2_000_000
            or not 0<dossier.stat().st_size<=200_000
            or not 0<pubkey.stat().st_size<=8192
            or _digest_file(pubkey)!=pinned):
        raise ValueError("QC1000_TRUSTED_REAL_EXECUTION_EVIDENCE_MISSING")
    suite_sha=_digest_file(suite)
    dossier_sha=_digest_file(dossier)
    if (decision.get("execution_suite_sha256")!=suite_sha or
            decision.get("doctoral_dossier_sha256")!=dossier_sha):
        raise ValueError("QC1000_SIGNED_DECISION_NOT_BOUND_TO_EXECUTED_EVIDENCE")
    spec=importlib.util.spec_from_file_location("factory_real_executions",str(module_path))
    if spec is None or spec.loader is None:
        raise ValueError("QC1000_REAL_VERIFIER_UNAVAILABLE")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        executed=module.verify_real_suite(suite,artifact_sha,pubkey)
        scientific=module.verify_doctoral_evidence(dossier,artifact_sha,suite_sha)
    except (ValueError,OSError,TypeError,KeyError) as exc:
        raise ValueError("QC1000_REAL_EXECUTION_OR_DOCTORAL_EVIDENCE_FAILED") from exc
    if (executed.get("verified_distinct_scenarios")!=1000
            or executed.get("criteria_with_ten_scenarios")!=100
            or executed.get("runner_signature_verified") is not True
            or scientific.get("artifact_and_1000_case_suite_bound") is not True):
        raise ValueError("QC1000_NOT_1000_AUTHENTIC_EXECUTED_CASES")
    return {"real_executions_verified":1000,
            "criteria_verified":100,
            "doctoral_evidence_structurally_bound":True,
            "scientific_specialist_signatures_still_mandatory":True}

CHATGPT_REVIEW_SCHEMA="saeit.factory.chatgpt-final-store-review.v1"
CHATGPT_REVIEWER="ChatGPT (Codex)"
CHATGPT_REVIEW_CHECKS=(
    "artifact_integrity",
    "functional_completeness",
    "edge_cases_and_failure_handling",
    "documentation_and_setup",
    "claims_and_limitations",
    "rights_and_attribution",
    "security_and_privacy",
    "store_listing_accuracy",
    "quality_1000_evidence",
)

def _inspect_review_archive(package):
    """Hash each ZIP member with bounded memory and reject oversized archives.

    Reject from central-directory sizes before decompression, and independently
    cap streamed bytes so forged ZIP metadata cannot cause unbounded allocation.
    This is read-only; no archive member is extracted to disk.
    """
    actual={}
    total=0
    limit=150*1024*1024
    try:
        with zipfile.ZipFile(package,"r") as archive:
            members=archive.infolist()
            if not members or len(members)>2500:
                raise ValueError("CHATGPT_REVIEW_ARCHIVE_MEMBER_LIMIT")
            for item in members:
                name=item.filename
                parts=PurePosixPath(name)
                if (item.is_dir() or not name or name.startswith("/") or "\\" in name
                        or parts.as_posix()!=name or any(part in ("",".","..") for part in parts.parts)
                        or ((item.external_attr>>16)&0o170000)==0o120000
                        or name in actual):
                    raise ValueError("CHATGPT_REVIEW_ARCHIVE_MEMBER_UNSAFE")
                remaining=limit-total
                if item.file_size<0 or item.file_size>remaining:
                    raise ValueError("CHATGPT_REVIEW_ARCHIVE_SIZE_INVALID")
                digest=hashlib.sha256()
                size=0
                with archive.open(item,"r") as stream:
                    while True:
                        chunk=stream.read(min(1024*1024,remaining-size+1))
                        if not chunk:
                            break
                        size+=len(chunk)
                        if size>item.file_size or size>remaining:
                            raise ValueError("CHATGPT_REVIEW_ARCHIVE_SIZE_INVALID")
                        digest.update(chunk)
                if size!=item.file_size:
                    raise ValueError("CHATGPT_REVIEW_ARCHIVE_SIZE_INVALID")
                total+=size
                actual[name]=(digest.hexdigest(),size)
    except (zipfile.BadZipFile,OSError,EOFError,RuntimeError) as exc:
        raise ValueError("CHATGPT_REVIEW_ARCHIVE_INVALID") from exc
    return actual

def require_chatgpt_final_review(inbox,recipe,artifact_sha,product_manifest,package_path):
    """Require ChatGPT's substantive, exact-artifact review before store entry.

    The receipt is authored only after the assistant inspects every packaged
    file. This validator checks identity, review scope, timestamps and byte
    coverage; it never creates or grants a review decision itself.
    """
    if (not isinstance(recipe,str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}",recipe)
            or not isinstance(artifact_sha,str) or not SHA.fullmatch(artifact_sha)
            or not isinstance(product_manifest,dict)):
        raise ValueError("CHATGPT_REVIEW_PRODUCT_IDENTITY_INVALID")
    package=Path(package_path)
    if (not package.is_file() or package.is_symlink()
            or _digest_file(package)!=artifact_sha):
        raise ValueError("CHATGPT_REVIEW_ARTIFACT_HASH_MISMATCH")
    container=Path(inbox)/"quality-clearance"/recipe/artifact_sha
    receipt_path=container/"chatgpt-final-review.json"
    if (receipt_path.is_symlink() or not receipt_path.is_file()
            or not 0<receipt_path.stat().st_size<=500_000):
        raise ValueError("CHATGPT_FINAL_REVIEW_MISSING")
    try:
        review=json.loads(receipt_path.read_text(encoding="utf8"))
    except (ValueError,OSError,UnicodeError) as exc:
        raise ValueError("CHATGPT_FINAL_REVIEW_INVALID_JSON") from exc
    if not isinstance(review,dict):
        raise ValueError("CHATGPT_FINAL_REVIEW_INVALID")
    manifest_bytes=json.dumps(product_manifest,ensure_ascii=False,sort_keys=True,
                              separators=(",",":")).encode("utf8")
    manifest_sha=hashlib.sha256(manifest_bytes).hexdigest()
    if (review.get("schema")!=CHATGPT_REVIEW_SCHEMA
            or review.get("reviewer")!=CHATGPT_REVIEWER
            or review.get("reviewer_role")!="owner-delegated final product quality reviewer"
            or review.get("decision")!="approved_for_store"
            or review.get("recipe")!=recipe
            or review.get("artifact_sha256")!=artifact_sha
            or review.get("manifest_sha256")!=manifest_sha):
        raise ValueError("CHATGPT_FINAL_REVIEW_NOT_BOUND_TO_PRODUCT")
    stamp=review.get("reviewed_at_utc")
    if not isinstance(stamp,str):
        raise ValueError("CHATGPT_FINAL_REVIEW_TIMESTAMP_INVALID")
    try:
        parsed=datetime.fromisoformat(stamp.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("CHATGPT_FINAL_REVIEW_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset()!=timezone.utc.utcoffset(parsed):
        raise ValueError("CHATGPT_FINAL_REVIEW_TIMESTAMP_NOT_UTC")
    summary=review.get("review_summary")
    if not isinstance(summary,str) or len(summary.strip())<300:
        raise ValueError("CHATGPT_FINAL_REVIEW_SUMMARY_TOO_SHALLOW")
    if review.get("unresolved_findings")!=[]:
        raise ValueError("CHATGPT_FINAL_REVIEW_HAS_UNRESOLVED_FINDINGS")
    checks=review.get("checklist")
    if (not isinstance(checks,dict) or set(checks)!=set(CHATGPT_REVIEW_CHECKS)
            or any(value is not True for value in checks.values())):
        raise ValueError("CHATGPT_FINAL_REVIEW_CHECKLIST_INCOMPLETE")
    files=review.get("reviewed_files")
    if not isinstance(files,list) or not files or len(files)>2500:
        raise ValueError("CHATGPT_FINAL_REVIEW_FILE_COVERAGE_INVALID")
    reviewed={}
    for row in files:
        if (not isinstance(row,dict) or set(row)!={"path","sha256","size"}
                or not isinstance(row.get("path"),str)
                or not isinstance(row.get("sha256"),str)
                or not SHA.fullmatch(row["sha256"])
                or type(row.get("size")) is not int or row["size"]<0):
            raise ValueError("CHATGPT_FINAL_REVIEW_FILE_RECORD_INVALID")
        name=row["path"]
        parts=PurePosixPath(name)
        if (not name or name.startswith("/") or "\\" in name
                or parts.as_posix()!=name or any(part in ("",".","..") for part in parts.parts)
                or name in reviewed):
            raise ValueError("CHATGPT_FINAL_REVIEW_FILE_PATH_INVALID")
        reviewed[name]=(row["sha256"],row["size"])
    actual=_inspect_review_archive(package)
    if reviewed!=actual:
        raise ValueError("CHATGPT_FINAL_REVIEW_FILE_COVERAGE_MISMATCH")
    return {"status":"CHATGPT_FINAL_REVIEW_VERIFIED",
            "reviewer":CHATGPT_REVIEWER,
            "artifact_sha256":artifact_sha,
            "reviewed_files":len(actual)}

def require_quality_clearance(inbox,recipe,package_digest,product_manifest,package_path):
    if not isinstance(product_manifest,dict):
        raise ValueError("INVALID_PRIVATE_FACTORY_MANIFEST")
    if product_manifest.get("professional_quality_standard")!="100_groups_x_10":
        # Preserve the guard contract while making the absence explicit.
        # Publication callers must reject this unverified status.
        return {"status":"LEGACY_UNASSESSED_REQUIRES_MIGRATION",
                "1000_quality_verified":False}
    if (not isinstance(recipe,str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}",recipe)
            or not isinstance(package_digest,str) or not SHA.fullmatch(package_digest)):
        raise ValueError("UNSAFE_FACTORY_VERSION_IDENTITY")
    root=Path(inbox)
    container=root/"quality-clearance"/recipe/package_digest
    signature=container/"signed-1000.json"
    report=container/"global-premium-report.json"
    catalog=container/"quality-100-groups.json"
    registry=root/"quality-trust"/"trusted-reviewers.json"
    script=Path(__file__).resolve().with_name("factory_quality_signed_approval_v1.py")
    for file in (signature,report,catalog,registry,script,Path(package_path)):
        if not file.is_file() or file.is_symlink():
            raise ValueError("SIGNED_1000_QUALITY_GATE_EVIDENCE_MISSING")
    spec=importlib.util.spec_from_file_location("factory_verifiable_approvals",str(script))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    approval=json.loads(signature.read_text(encoding="utf8"))
    real_report=json.loads(report.read_text(encoding="utf8"))
    trust=json.loads(registry.read_text(encoding="utf8"))
    result=module.inspect_approval(approval,real_report,package_path,catalog,trust)
    if result.get("eligible") is not True or result.get("artifact_sha256")!=package_digest:
        raise ValueError("SIGNED_1000_QUALITY_APPROVAL_NOT_VALID")
    # A score plus human signatures alone is insufficient: re-execute the
    # trusted verifier on the exact 1000 test receipts and research dossier.
    checked=_verify_executed_qc1000(root,container,package_digest,
                                   approval.get("decision"))
    chatgpt_review=require_chatgpt_final_review(
        root,recipe,package_digest,product_manifest,package_path
    )
    return {"status":"VERIFIED_SIGNED_PREMIUM_1000",
            "artifact_sha256":package_digest,
            "1000_quality_verified":True,
            "real_executions_verified":checked["real_executions_verified"],
            "independent_signed_reviewers":result["verifiable_reviewer_count"],
            "chatgpt_final_review":chatgpt_review["status"]}
