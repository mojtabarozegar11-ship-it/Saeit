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

def require_quality_clearance(inbox,recipe,package_digest,product_manifest,package_path):
    if not isinstance(product_manifest,dict):
        raise ValueError("INVALID_PRIVATE_FACTORY_MANIFEST")
    if product_manifest.get("professional_quality_standard")!="100_groups_x_10":
        raise ValueError("QC1000_REQUIRED_FOR_FACTORY_EXIT")
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
    return {"status":"VERIFIED_SIGNED_PREMIUM_1000",
            "artifact_sha256":package_digest,
            "1000_quality_verified":True,
            "real_executions_verified":checked["real_executions_verified"],
            "independent_signed_reviewers":result["verifiable_reviewer_count"]}
