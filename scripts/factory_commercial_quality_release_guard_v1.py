#!/usr/bin/env python3
"""Public release hard-stop for new 100x10 factory manufactured products.

Private staging remains legal and isolated; existing older free-edition release
is not silently republished or revoked by this adapter. Newly marked 100x10
builds require four externally identified Ed25519 signatures on exact bytes.
"""
import importlib.util
import json
from pathlib import Path
import re

SHA=re.compile(r"^[a-f0-9]{64}$")
def require_quality_clearance(inbox,recipe,package_digest,product_manifest,package_path):
    if not isinstance(product_manifest,dict):
        raise ValueError("INVALID_PRIVATE_FACTORY_MANIFEST")
    if product_manifest.get("professional_quality_standard")!="100_groups_x_10":
        # Older already-distributed free assets need a separate migration.
        # They are NOT certified 1000/1000 by this function.
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
    return {"status":"VERIFIED_SIGNED_PREMIUM_1000",
            "artifact_sha256":package_digest,
            "1000_quality_verified":True,
            "independent_signed_reviewers":result["verifiable_reviewer_count"]}
