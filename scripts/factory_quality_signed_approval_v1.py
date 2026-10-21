#!/usr/bin/env python3
"""Version-bound, multi-party *authenticated* approval path for 100x10 product QA.

No live commercial release is performed here. This strict release-eligibility
verification rejects self-attestation, missing identities, stale build hashes,
unresolved defects and unsigned approvals. Signing keys belong to genuinely
authorized external reviewers and the owner, never the factory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA="saeit.factory.quality-1000-signed-approval.v1"
KEY_SCHEMA="saeit.factory.trusted-reviewer-keys.v1"
ROLES=("domain_specialist","independent_quality_auditor","rights_reviewer","owner")
HEX=re.compile(r"^[a-f0-9]{64}$")

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def validate_key_registry(config):
    if not isinstance(config,dict) or config.get("schema")!=KEY_SCHEMA:
        raise ValueError("TRUST_REGISTRY_INVALID")
    entries=config.get("reviewers")
    if not isinstance(entries,dict):raise ValueError("TRUST_KEYS_MISSING")
    for name,entry in entries.items():
        if (not re.fullmatch(r"[a-zA-Z0-9_.-]{4,64}",name)
            or not isinstance(entry,dict) or entry.get("role") not in ROLES
            or not isinstance(entry.get("public_key_pem"),str)
            or "BEGIN PUBLIC KEY" not in entry["public_key_pem"]
            or not entry.get("externally_identity_verified") is True):
            raise ValueError("UNTRUSTED_REVIEWER_IDENTITY")
    return entries

def verify_sig(key_pem,payload,signature_hex):
    if not isinstance(signature_hex,str) or not re.fullmatch(r"[a-f0-9]{128}",signature_hex):
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="factory-approval-") as directory:
            base=Path(directory)
            (base/"public.pem").write_text(key_pem,encoding="utf8")
            (base/"signed.bin").write_bytes(payload)
            (base/"sig.bin").write_bytes(bytes.fromhex(signature_hex))
            proc=subprocess.run([
                "openssl","pkeyutl","-verify","-pubin","-rawin",
                "-inkey",str(base/"public.pem"),
                "-in",str(base/"signed.bin"),
                "-sigfile",str(base/"sig.bin"),
            ],capture_output=True,timeout=12)
            return proc.returncode==0
    except (OSError,subprocess.TimeoutExpired,ValueError):
        return False

def inspect_approval(receipt, report, artifact_path, catalog_path, trust_config):
    problems=[]
    def defect(code):
        if code not in problems:problems.append(code)
    if not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA:
        return {"eligible":False,"blocking_reasons":["UNSUPPORTED_SIGNED_APPROVAL_SCHEMA"]}
    if not isinstance(report,dict) or report.get("schema")!="saeit.factory.global-premium-quality.v1":
        defect("UNTRUSTED_QUALITY_GATE_REPORT")
        report={}
    build=Path(artifact_path)
    catalog=Path(catalog_path)
    if not build.is_file() or build.is_symlink() or not catalog.is_file() or catalog.is_symlink():
        defect("REAL_BUILD_OR_CATALOG_MISSING")
        return {"eligible":False,"blocking_reasons":problems}
    build_hash=digest(build)
    catalog_hash=digest(catalog)
    data=receipt.get("decision")
    if not isinstance(data,dict):
        defect("SIGNED_DECISION_MISSING");data={}
    if data.get("artifact_sha256")!=build_hash or not HEX.fullmatch(str(data.get("artifact_sha256",""))):
        defect("DECISION_WRONG_BUILD_VERSION")
    if data.get("quality_catalog_sha256")!=catalog_hash:
        defect("DECISION_STALE_CRITERIA_CATALOG")
    if data.get("family_id")!=report.get("family_id") or not re.fullmatch(r"F[0-4][0-9]",str(data.get("family_id",""))):
        defect("DECISION_WRONG_FAMILY")
    if report.get("technical_test_passed") is not True:
        defect("TECHNICAL_QA_NOT_VERIFIED")
    blockers=report.get("blockers")
    if not isinstance(blockers,list):
        defect("NO_ITEMIZED_QUALITY_REPORT");blockers=[]
    ignore={"P0_INDEPENDENT_ATTESTATION_NOT_AUTHENTICATED","P0_WORLD_NUMBER_ONE_CLAIM_UNVERIFIED"}
    if any(not isinstance(x,dict) or not isinstance(x.get("code"),str) for x in blockers):
        defect("INVALID_QUALITY_ISSUES")
    if any(isinstance(x,dict) and x.get("code") not in ignore for x in blockers):
        defect("SUBSTANTIVE_QUALITY_GAPS_REMAIN")
    grades=data.get("100_groups")
    ids=["Q%03d"%i for i in range(1,101)]
    if not isinstance(grades,dict) or list(sorted(grades))!=ids or any(type(grades[k]) is not int or grades[k]!=10 for k in ids if k in grades):
        defect("NOT_ALL_100_GROUPS_INDEPENDENTLY_GRADED_TEN")
    if data.get("unresolved_critical_defects")!=0:
        defect("CRITICAL_DEFECTS_NOT_CLOSED")
    if data.get("claim_world_number_one") is True:
        defect("UNSUPPORTED_WORLD_RANK_CLAIM")
    if not isinstance(data.get("evidence_manifest_sha256"),str) or not HEX.fullmatch(data["evidence_manifest_sha256"]):
        defect("EVIDENCE_MANIFEST_UNBOUND")
    signatures=receipt.get("approvals")
    signatures=signatures if isinstance(signatures,list) else []
    try:keys=validate_key_registry(trust_config)
    except (ValueError,TypeError):
        defect("TRUST_REGISTRY_INVALID");keys={}
    identities=set();valid_roles=set()
    payload=canonical(data)
    for s in signatures:
        if not isinstance(s,dict):continue
        signer=s.get("reviewer_id")
        if signer in identities:
            defect("DUPLICATED_REVIEWER_IDENTITY")
            continue
        if not isinstance(signer,str) or signer not in keys:
            defect("UNTRUSTED_SIGNER");continue
        role=keys[signer]["role"]
        if s.get("role")!=role:
            defect("SIGNER_ROLE_MISMATCH");continue
        if not verify_sig(keys[signer]["public_key_pem"],payload,s.get("signature_hex")):
            defect("INVALID_APPROVAL_SIGNATURE");continue
        identities.add(signer);valid_roles.add(role)
    for role in ROLES:
        if role not in valid_roles:defect("MISSING_INDEPENDENT_SIGNED_ROLE:"+role)
    return {
        "schema":"saeit.factory.signed-quality-clearance.v1",
        "artifact_sha256":build_hash,
        "catalog_sha256":catalog_hash,
        "required_roles":list(ROLES),
        "valid_signed_roles":sorted(valid_roles),
        "verifiable_reviewer_count":len(identities),
        "verified_grade_total":1000 if not problems else None,
        "eligible":not problems,
        "blocking_reasons":problems,
        "publication_executed":False,
        "payment_activated":False,
    }

def main():
    p=argparse.ArgumentParser()
    for arg in ("decision","gate-report","artifact","catalog","trusted-reviewers","output"):
        p.add_argument("--"+arg,required=True)
    a=p.parse_args()
    receipt=json.loads(Path(a.decision).read_text(encoding="utf8"))
    gate=json.loads(Path(a.gate_report).read_text(encoding="utf8"))
    keys=json.loads(Path(a.trusted_reviewers).read_text(encoding="utf8"))
    result=inspect_approval(receipt,gate,a.artifact,a.catalog,keys)
    target=Path(a.output)
    if target.exists() or target.is_symlink():raise ValueError("QUALITY_CLEARANCE_OVERWRITE_REFUSED")
    target.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8")
    print("FACTORY_VERIFIABLE_SIGNED_QUALITY_ELIGIBLE="+str(result["eligible"]).lower())
    print("FACTORY_EXPERT_APPROVAL_BLOCKERS="+str(len(result["blocking_reasons"])))
    return 0 if result["eligible"] else 2

if __name__=="__main__":raise SystemExit(main())
