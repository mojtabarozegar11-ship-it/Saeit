#!/usr/bin/env python3
"""Private six-family review dossiers bound to actual factory native evidence.

No fabricated professional identities, signatures, physical device runs,
rights approval, full QA-1000 clearance or public product release.
A dossier is a REQUEST for independent review, not the review itself.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA="saeit.factory.six-expert-handoff.v1"
FAMILIES=("F12","F13","F14","F16","F17","F26")
COUNTS={"F12":2,"F13":1,"F14":2,"F16":2,"F17":1,"F26":48}
RUN=re.compile(r"^[0-9]{5,18}-[0-9]{1,3}$")
HEX=re.compile(r"^[0-9a-f]{64}$")
GATES={
  "F12":[("real_android_devices","Run on 3 independently identified physical Android devices; 48-stage navigation, crashes, accessibility and offline state"),
         ("release_signing","Verify owner-controlled production keystore and final APK/AAB certificate without revealing private keys"),
         ("gameplay_rights","Independent player/rights audit of gameplay, assets, derivative works and distribution terms")],
  "F13":[("clean_windows_install","Install signed PE on two clean customer Windows machines; execute and replay all 48 stages"),
         ("independent_malware_security","Independent signed malware and dependency assessment of actual PE SHA"),
         ("gameplay_rights","Independent IP and marketplace-gameplay quality assessment")],
  "F14":[("blind_playtesting","Third-party blind playtesting of original browser game with measurable success/defect notes"),
         ("physical_mobile_browser","Test iOS Safari and Android Chrome on physical phones, with accessibility checks"),
         ("independent_rights","Confirm assets, game mechanics, copyright and fair use or attribution")],
  "F16":[("physical_android_storage","Store, close, relaunch and check permissions on physical Android devices; privacy/backup review"),
         ("release_signing","Review distribution-signed production Android binary and keystore custody"),
         ("privacy_accessibility","Independent privacy, user data, screen reader and interaction usability report")],
  "F17":[("clean_windows_install","Test signed PE installer on a clean Windows environment including failed updates and rollback"),
         ("independent_malware_security","Signed independent malicious-code, data integrity and dependency inspection"),
         ("real_customer_workflow","Independently evaluate valid/invalid inventory CSV and end-user acceptance scenarios")],
  "F26":[("external_domain_dataset","Evaluate classifier with newly collected independent rice grains and measured morphology"),
         ("bias_shift_leakage_audit","Independent data leakage, calibration, class balance and out-of-distribution specialist audit"),
         ("data_rights_and_model_card","Expert review CC BY 4.0 provenance, citations, input limits and research-only declarations")]
}
ROLES=("domain_specialist","independent_quality_auditor","rights_reviewer","owner")
COUNTRY_FREE=True

def sha_file(path,max_bytes=230_000_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=max_bytes:
        raise RuntimeError("HANDOFF_UNSAFE_OR_MISSING_EVIDENCE")
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(131072),b""):
            h.update(part)
    return h.hexdigest()

def obj(path,max_bytes=300_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=max_bytes:
        raise RuntimeError("HANDOFF_UNSAFE_RECEIPT")
    data=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(data,dict):
        raise RuntimeError("HANDOFF_BAD_RECEIPT")
    return data

def canonical(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode("utf8")

def load_verifier(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("HANDOFF_F26_PINNED_VERIFIER_NOT_FOUND")
    spec=importlib.util.spec_from_file_location("f26_real_rice_readonly_handoff",str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def native_snapshot(root):
    base=root/"quality-excellence"/"six-native-rework"
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("HANDOFF_SIX_NATIVE_REVIEW_MISSING")
    names=sorted((p.name for p in base.iterdir()
                 if p.is_dir() and not p.is_symlink() and RUN.fullmatch(p.name)
                 and (p/"review.json").is_file()),
                 key=lambda x:tuple(map(int,x.split("-"))),reverse=True)
    for run in names:
        folder=base/run
        native=root/"native-candidate-evidence"/run
        if native.is_symlink() or not native.is_dir():
            continue
        try:
            review=obj(folder/"review.json")
            source=native/"verified-six-private-native.json"
            batch=obj(source)
            if (review.get("schema")!="saeit.factory.six-native-independent-technical-review.v1"
                or review.get("source_run")!=run
                or review.get("reviewed_families")!=6
                or review.get("verified_native_candidate_files")!=56
                or review.get("commercial_release_authorized") is not False
                or review.get("completed_professional_quality_1000_certifications")!=0
                or review.get("independent_machine_review_performed") is not True
                or review.get("source_aggregate_sha256")!=sha_file(source)
                or batch.get("schema")!="saeit.factory.native-six-vps-aggregate.v1"
                or batch.get("six_families_verified")!=6
                or batch.get("candidate_native_file_count")!=56
                or batch.get("private_only") is not True
                or batch.get("production_release_authorized") is not False):
                continue
            if (len(review.get("families",[]))!=6 or
                {f.get("family_id") for f in review["families"]}!=set(FAMILIES) or
                len(batch.get("files",[]))!=6 or
                {f.get("family") for f in batch["files"]}!=set(FAMILIES)):
                continue
            return run,review,batch,folder,native
        except (ValueError,TypeError,KeyError,RuntimeError,OSError):
            continue
    raise RuntimeError("HANDOFF_NO_VERIFIED_SIX_LINE_SNAPSHOT")

def f26_real_pilot(root,verifier):
    research=root/"f26-real-data-research"
    if not research.is_dir() or research.is_symlink():
        return {"real_uci_pilot_independently_verified":False,
                "remaining":"licensed_real_data_research_pilot_not_located"}
    # Independent recheck of original tar, CC BY attribution, prior 48 ONNX,
    # split metrics, ONNX byte hashes, and noncommercial release flags.
    load_verifier(verifier).verify(root)
    dirs=[p for p in research.iterdir()
          if p.is_dir() and not p.is_symlink() and RUN.fullmatch(p.name)]
    if not dirs:
        raise RuntimeError("HANDOFF_F26_REAL_MODEL_NO_INSTALLED_VERSION")
    latest=max(dirs,key=lambda p:tuple(map(int,p.name.split("-"))))
    receipt=latest/"private-f26-real-data-receipt.json"
    d=obj(receipt)
    if (d.get("schema")!="saeit.factory.f26.real-rice-research-pilot.v1.vps-admission"
        or d.get("real_world_rice_rows")!=3810
        or d.get("untouched_heldout_rows",0)<500
        or d.get("professional_quality_1000_certified") is not False
        or d.get("physical_grain_camera_tested") is not False
        or d.get("commercial_release_allowed") is not False):
        raise RuntimeError("HANDOFF_F26_REAL_DATA_POLICY_FAILURE")
    return {
      "real_uci_pilot_independently_verified":True,
      "source_run":latest.name,
      "receipt_sha256":sha_file(receipt),
      "model_sha256":d["research_model_sha256"],
      "dataset_source_sha256":d["uci_public_archive_sha256"],
      "real_dataset_count":3810,
      "heldout_count":d["untouched_heldout_rows"],
      "independent_field_testing_complete":False,
      "commercial_release":False,
      "quality_1000_certified":False
    }

def immutable(path,value):
    raw=canonical(value)
    if path.is_symlink():
        raise RuntimeError("HANDOFF_OUTPUT_SYMLINK")
    if path.exists():
        if sha_file(path,5_000_000)!=hashlib.sha256(raw).hexdigest():
            raise RuntimeError("HANDOFF_IMMUTABLE_RECEIPT_CHANGED")
        return hashlib.sha256(raw).hexdigest()
    fd,tmp=tempfile.mkstemp(prefix=".handoff-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return hashlib.sha256(raw).hexdigest()

def build(root,verifier,write=True):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("HANDOFF_PRIVATE_FACTORY_ROOT_REQUIRED")
    run,review,aggregate,review_dir,native_dir=native_snapshot(root)
    rice=f26_real_pilot(root,Path(verifier))
    cases=[]
    for family in FAMILIES:
        row=next(x for x in review["families"] if x["family_id"]==family)
        base=next(x for x in aggregate["files"] if x["family"]==family)
        if (row!=obj(review_dir/(family+".json"))
            or row.get("technical_native_artifact_integrity_verified") is not True
            or row.get("independent_professional_approval") is not False
            or row.get("quality_1000_certified") is not False
            or row.get("commercial_release_authorized") is not False
            or row.get("format_artifact_count")!=COUNTS[family]
            or base.get("native_candidate_files")!=COUNTS[family]
            or base.get("verified_on_vps") is not True
            or row.get("artifact_sha256")!=base.get("archive_sha256")):
            raise RuntimeError("HANDOFF_FAMILY_IDENTITY_INTEGRITY_FAILED:"+family)
        native_receipt=native_dir/family/"technical-native-receipt.json"
        receipt=obj(native_receipt)
        archive=native_dir/family/"technical-native-candidate.zip"
        if (receipt.get("family")!=family
            or receipt.get("archive_sha256")!=sha_file(archive)
            or receipt.get("quality_1000_certified") is not False
            or receipt.get("commercial_release") is not False
            or receipt.get("independent_specialist_review_verified") is not False):
            raise RuntimeError("HANDOFF_NATIVE_ARTIFACT_CHANGED:"+family)
        blocking=row.get("unverified_specialist_or_physical_gates",[])
        if not isinstance(blocking,list) or not blocking:
            raise RuntimeError("HANDOFF_FALSELY_EMPTY_EXPERT_GATES:"+family)
        tests=[{"gate_id":code,
                "independent_reviewer_required":True,
                "test_protocol":protocol,
                "external_evidence_sha256":None,
                "real_test_executed":False,
                "acceptance_status":"not_yet_verified"}
               for code,protocol in GATES[family]]
        if family=="F26" and not rice["real_uci_pilot_independently_verified"]:
            raise RuntimeError("HANDOFF_F26_RESEARCH_MODEL_NOT_PROVEN")
        case={
            "schema":SCHEMA+".case",
            "family":family,
            "source_native_run":run,
            "native_candidate_archive_sha256":row["artifact_sha256"],
            "native_candidate_receipt_sha256":sha_file(native_receipt),
            "machine_review_sha256":sha_file(review_dir/(family+".json")),
            "original_independent_review_sha256":sha_file(review_dir/"review.json"),
            "number_of_native_files":COUNTS[family],
            "machine_checks_performed":row["independent_machine_checks"],
            "machine_identified_source_defects":row["remediable_source_defects"],
            "original_pending_gates":blocking,
            "external_review_protocols":tests,
            "required_signed_roles":list(ROLES),
            "trusted_human_reviewer_identities":[],"human_approvals":[],
            "signature_verification_tool":"scripts/factory_quality_signed_approval_v1.py",
            "reviewer_invitation_console":"scripts/factory_quality_reviewer_console_v1.py",
            "research_model_evidence":rice if family=="F26" else None,
            "ready_for_external_specialist_assignment":True,
            "physical_device_testing_verified":False,
            "independent_quality_1000_certified":False,
            "commercial_release_authorized":False,
            "public_websites_mutated":False
        }
        cases.append(case)
    folder=root/"quality-excellence"/"six-expert-handoff"/run
    if folder.is_symlink() or folder.parent.is_symlink():
        raise RuntimeError("HANDOFF_UNSAFE_OUTDIR")
    index={
      "schema":SCHEMA,"native_run":run,
      "native_review_sha256":sha_file(review_dir/"review.json"),
      "native_aggregate_sha256":sha_file(native_dir/"verified-six-private-native.json"),
      "six_real_product_families_bound":6,
      "native_files_linked":56,
      "real_rice_f26_independently_reverified":rice["real_uci_pilot_independently_verified"],
      "machine_qc_receipts":6,
      "expert_packet_status":"ready_for_independent_review_not_approved",
      "third_party_approved_families":0,
      "physical_hardware_approved_families":0,
      "independent_quality_1000_certified_families":0,
      "commercial_release_allowed":False,
      "website_mutations":0,
      "families":[{"family":c["family"],"artifact_sha256":c["native_candidate_archive_sha256"],
                   "independent_review_gate_count":len(c["external_review_protocols"]),
                   "specialist_approval_status":"pending_external_evidence"}
                  for c in cases]
    }
    hashes={}
    if write:
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        lock=folder/".expert-handoff.lock"
        if lock.is_symlink():raise RuntimeError("HANDOFF_UNSAFE_LOCK")
        with lock.open("ab") as stream:
            os.fchmod(stream.fileno(),0o600)
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
            for case in cases:
                hashes[case["family"]]=immutable(folder/(case["family"]+".json"),case)
            index["case_manifest_sha256"]=hashes
            index_hash=immutable(folder/"manifest.json",index)
    else:
        index["case_manifest_sha256"]={
            c["family"]:hashlib.sha256(canonical(c)).hexdigest() for c in cases}
        index_hash=hashlib.sha256(canonical(index)).hexdigest()
    print("FACTORY_SIX_SPECIALIST_HANDOFF="+json.dumps({
        "families":6,"files":56,"external_gates_created":sum(len(GATES[c["family"]]) for c in cases),
        "uci_f26_real_data":rice["real_uci_pilot_independently_verified"],
        "human_approved":0,"physical_approved":0,"quality1000_certified":0,
        "public_release":False,"handoff_manifest_sha256":index_hash,
        "private_saved":write},sort_keys=True))
    return index

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--f26-verifier",required=True)
    p.add_argument("--dry-run",action="store_true")
    args=p.parse_args()
    build(args.factory_private,args.f26_verifier,not args.dry_run)

if __name__=="__main__":
    main()
