#!/usr/bin/env python3
"""Version-bound, multi-party *authenticated* approval path for 100x10 product QA.

No live commercial release is performed here. This strict release-eligibility
verification rejects self-attestation, missing identities, stale build hashes,
unresolved defects and unsigned approvals. Signing keys belong to genuinely
authorized external reviewers and the owner, never the factory.
"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA="saeit.factory.quality-1000-signed-approval.v1"
KEY_SCHEMA="saeit.factory.trusted-reviewer-keys.v1"
ROLES=("domain_specialist","independent_quality_auditor","rights_reviewer","owner")
INDEPENDENT_ROLES=ROLES[:3]
DELEGATE_ROLE="owner_delegate_agent"
TRUST_ROLES=ROLES+(DELEGATE_ROLE,)
DELEGATION_SCHEMA="saeit.factory.owner-agent-delegation.v1"
DELEGATION_SCOPE="quality-owner-operational-signoff-only"
HEX=re.compile(r"^[a-f0-9]{64}$")

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def validate_agent_delegation(entry,root_pub,at=None,require_current=True):
    """An owner-root signed, scoped, expiring grant; never a human identity."""
    grant=entry.get("owner_delegation")
    if not isinstance(grant,dict) or grant.get("schema")!=DELEGATION_SCHEMA:
        raise ValueError("OWNER_DELEGATION_MISSING")
    families=grant.get("authorized_family_ids")
    if (grant.get("scope")!=DELEGATION_SCOPE
            or grant.get("reviewer_id")!=entry.get("reviewer_id")
            or grant.get("agent_public_key_sha256")!=hashlib.sha256(entry["public_key_pem"].encode()).hexdigest()
            or grant.get("owner_root_public_key_sha256")!=hashlib.sha256(root_pub.encode()).hexdigest()
            or not isinstance(families,list) or not 1<=len(families)<=49
            or len(families)!=len(set(str(x) for x in families))
            or any(not isinstance(x,str) or not re.fullmatch(r"F(?:0[1-9]|[1-3][0-9]|4[0-9])",x) for x in families)
            or not verify_sig(root_pub,canonical(grant),entry.get("owner_delegation_signature_hex"))):
        raise ValueError("OWNER_DELEGATION_UNTRUSTED")
    try:
        start=datetime.fromisoformat(grant["not_before_utc"])
        end=datetime.fromisoformat(grant["expires_at_utc"])
    except (KeyError,ValueError,TypeError):
        raise ValueError("OWNER_DELEGATION_DATES_INVALID")
    if (start.tzinfo is None or end.tzinfo is None or end<=start
            or end-start>timedelta(days=90)):
        raise ValueError("OWNER_DELEGATION_WINDOW_INVALID")
    now=at or datetime.now(timezone.utc)
    if require_current and not start<=now<=end:
        raise ValueError("OWNER_DELEGATION_NOT_CURRENT")
    return grant

def validate_key_registry(config):
    """Only a root-signed registry anchored OUTSIDE that registry is trusted.

    The root SHA-256 is an operator-controlled environment setting on the
    actual server, not a self-declared value in the candidate JSON.
    No configured trust root => no commercial clearance.
    """
    if not isinstance(config,dict) or config.get("schema")!=KEY_SCHEMA:
        raise ValueError("TRUST_REGISTRY_INVALID")
    entries=config.get("reviewers")
    if not isinstance(entries,dict):
        raise ValueError("TRUST_KEYS_MISSING")
    root_pub=config.get("trusted_root_public_key_pem")
    root_sig=config.get("root_signature_hex")
    pinned=os.environ.get("FACTORY_QA_TRUST_ROOT_SHA256","")
    if (not isinstance(root_pub,str) or not re.fullmatch(r"[a-f0-9]{64}",pinned)
            or hashlib.sha256(root_pub.encode("utf-8")).hexdigest()!=pinned
            or not verify_sig(root_pub,canonical({"schema":KEY_SCHEMA,"reviewers":entries}),root_sig)):
        raise ValueError("UNVERIFIED_OR_UNPINNED_TRUST_REGISTRY")
    seen_signing_keys=set()
    for name,entry in entries.items():
        if (not re.fullmatch(r"[a-zA-Z0-9_.-]{4,64}",name)
            or not isinstance(entry,dict) or entry.get("role") not in TRUST_ROLES
            or not isinstance(entry.get("public_key_pem"),str)
            or "BEGIN PUBLIC KEY" not in entry["public_key_pem"]
            or not isinstance(entry.get("identity_verification_evidence_sha256"),str)
            or not HEX.fullmatch(entry["identity_verification_evidence_sha256"])
            or entry.get("active") is not True):
            raise ValueError("UNTRUSTED_REVIEWER_IDENTITY")
        key_fingerprint=hashlib.sha256(entry["public_key_pem"].encode()).hexdigest()
        if key_fingerprint in seen_signing_keys or key_fingerprint==pinned:
            raise ValueError("NON_INDEPENDENT_REVIEWER_SIGNING_KEY")
        seen_signing_keys.add(key_fingerprint)
        if entry["role"]==DELEGATE_ROLE:
            if (entry.get("externally_identity_verified") is not False
                    or entry.get("agent_identity_verified") is not True
                    or entry.get("reviewer_id")!=name):
                raise ValueError("OWNER_AGENT_MUST_NOT_IMPERSONATE_HUMAN")
            # The registry authenticates grants, but unused expired grants do
            # not disable independent human reviewers or direct-owner decisions.
            validate_agent_delegation(entry,root_pub,require_current=False)
        elif entry.get("externally_identity_verified") is not True:
            raise ValueError("INDEPENDENT_HUMAN_IDENTITY_UNVERIFIED")
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
    if data.get("gate_report_sha256")!=hashlib.sha256(canonical(report)).hexdigest():
        defect("QUALITY_REPORT_NOT_BOUND_TO_SIGNATURES")
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
        if role==DELEGATE_ROLE:
            try:
                grant=validate_agent_delegation(
                    keys[signer],trust_config["trusted_root_public_key_pem"])
            except ValueError:
                defect("OWNER_AGENT_DELEGATION_NOT_CURRENT")
                continue
            if data.get("family_id") not in grant["authorized_family_ids"]:
                defect("OWNER_AGENT_DELEGATION_SCOPE_VIOLATION")
                continue
        identities.add(signer);valid_roles.add(role)
    for role in INDEPENDENT_ROLES:
        if role not in valid_roles:defect("MISSING_INDEPENDENT_SIGNED_ROLE:"+role)
    if not ({"owner",DELEGATE_ROLE} & valid_roles):
        defect("MISSING_INDEPENDENT_SIGNED_ROLE:owner")
    return {
        "schema":"saeit.factory.signed-quality-clearance.v1",
        "artifact_sha256":build_hash,
        "catalog_sha256":catalog_hash,
        "required_roles":list(INDEPENDENT_ROLES)+["owner OR "+DELEGATE_ROLE],
        "owner_authorization_kind":("direct_owner" if "owner" in valid_roles else
                                     "verified_delegated_agent" if DELEGATE_ROLE in valid_roles else "missing"),
        "agent_not_a_human_expert":True,
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
