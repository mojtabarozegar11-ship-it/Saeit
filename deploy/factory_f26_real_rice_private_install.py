#!/usr/bin/env python3
"""Private, fail-closed VPS admission of real-data F26 research pilot.

Only exact source-hashed machine research evidence; public websites, online
stores, release authorizations and historical 48 synthetic ONNX are untouched.
The native F26 technical batch is explicitly linked, not replaced.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile

SCHEMA="saeit.factory.f26.real-rice-research-pilot.v1"
ALLOWED={"rice_cultivar_real_pilot.onnx","model_card.json",
         "ATTRIBUTION_AND_LIMITS.txt","manifest.json"}
SHA=re.compile(r"[a-f0-9]{64}")
RUN=re.compile(r"[0-9]{5,18}-[0-9]{1,3}")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def parse_file(path,limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise RuntimeError("F26_ADMISSION_UNSAFE_FILE")
    return path.read_bytes()

def primary_native_batch(root):
    container=root/"native-candidate-evidence"
    if container.is_symlink() or not container.is_dir():
        raise RuntimeError("F26_ADMISSION_NO_PRIOR_NATIVE_EVIDENCE")
    candidates=[]
    for entry in container.iterdir():
        if (entry.is_dir() and not entry.is_symlink()
                and RUN.fullmatch(entry.name)
                and (entry/"verified-six-private-native.json").is_file()
                and (entry/"verified-six-private-native.json").is_symlink() is False):
            candidates.append(entry)
    for entry in sorted(candidates,key=lambda p:tuple(map(int,p.name.split("-"))),reverse=True):
        try:
            source=entry/"verified-six-private-native.json"
            value=json.loads(parse_file(source,200_000).decode("utf8"))
            rows=value.get("files",[])
            f26=next(x for x in rows if x.get("family")=="F26")
            q=root/"quality-excellence"/"six-native-rework"/entry.name/"review.json"
            if (value.get("schema")!="saeit.factory.native-six-vps-aggregate.v1"
                or value.get("six_families_verified")!=6
                or value.get("candidate_native_file_count")!=56
                or value.get("private_only") is not True
                or value.get("production_release_authorized") is not False
                or f26.get("native_candidate_files")!=48
                or f26.get("verified_on_vps") is not True
                or not SHA.fullmatch(str(f26.get("archive_sha256","")))
                or q.is_symlink() or not q.is_file()):
                continue
            qa=json.loads(parse_file(q,200_000).decode("utf8"))
            if (qa.get("source_aggregate_sha256")!=sha(parse_file(source,200_000))
                or qa.get("completed_professional_quality_1000_certifications")!=0):
                continue
            return {
                "prior_native_source_run":entry.name,
                "prior_native_f26_archive_sha256":f26["archive_sha256"],
                "prior_native_qa_review_sha256":sha(parse_file(q,200_000))}
        except (ValueError,KeyError,TypeError,StopIteration,RuntimeError,OSError):
            continue
    raise RuntimeError("F26_ADMISSION_NO_VALID_INDEPENDENT_NATIVE_SOURCE")

def run(root,run_id,source_commit,expected_bundle_sha):
    if not RUN.fullmatch(run_id) or not re.fullmatch(r"[a-f0-9]{40}",source_commit):
        raise RuntimeError("F26_ADMISSION_INVALID_RUN_OR_COMMIT")
    if not SHA.fullmatch(expected_bundle_sha):
        raise RuntimeError("F26_ADMISSION_EXPECTED_TAR_SHA_REQUIRED")
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("F26_ADMISSION_INVALID_PRIVATE_ROOT")
    area=root/"f26-real-data-research"
    if area.is_symlink() or not area.is_dir():
        raise RuntimeError("F26_ADMISSION_ROOT_NOT_PROVISIONED")
    stage=area/(".incoming-"+run_id)
    target=area/run_id
    if stage.is_symlink() or not stage.is_dir() or target.exists() or target.is_symlink():
        raise RuntimeError("F26_ADMISSION_NOT_FRESH")
    lock=area/".admission.lock"
    if lock.is_symlink():
        raise RuntimeError("F26_ADMISSION_LOCK_SYMLINK")
    with lock.open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        tar=stage/"f26-research.tar"
        raw=parse_file(tar,15_000_000)
        if sha(raw)!=expected_bundle_sha:
            raise RuntimeError("F26_ADMISSION_TAR_MISMATCH")
        with tarfile.open(tar,"r:") as pack:
            members=pack.getmembers()
            if ({m.name for m in members}!=ALLOWED or len(members)!=len(ALLOWED)
                or any(not m.isfile() or m.size<10 or m.size>9_000_000 or
                       m.islnk() or m.issym() for m in members)):
                raise RuntimeError("F26_ADMISSION_UNSAFE_TAR_MEMBERS")
            contents={m.name:pack.extractfile(m).read() for m in members}
        manifest=json.loads(contents["manifest.json"].decode("utf8"))
        card=json.loads(contents["model_card.json"].decode("utf8"))
        files=manifest.get("artifact_sha256")
        if not isinstance(files,dict) or set(files)!=ALLOWED-{"manifest.json"}:
            raise RuntimeError("F26_ADMISSION_BAD_MEMBER_RECEIPT")
        if any(not SHA.fullmatch(str(expected)) or sha(contents[name])!=expected
               for name,expected in files.items()):
            raise RuntimeError("F26_ADMISSION_TAMPERED_RESEARCH_OUTPUT")
        scores=card.get("metrics",{})
        if (card.get("schema")!=SCHEMA or card.get("family")!="F26"
            or card.get("dataset",{}).get("doi")!="https://doi.org/10.24432/C5MW4Z"
            or card.get("dataset",{}).get("license")!="Creative Commons Attribution 4.0 International (CC BY 4.0)"
            or card.get("dataset",{}).get("download_archive_sha256")!=manifest.get("source_archive_sha256")
            or card.get("onnx_model_sha256")!=files["rice_cultivar_real_pilot.onnx"]
            or card.get("research_only") is not True
            or card.get("independent_field_validation") is not False
            or card.get("independent_specialist_approval") is not False
            or card.get("quality_1000_certified") is not False
            or card.get("commercial_release_authorized") is not False
            or manifest.get("holdout_data_real_and_not_synthetic") is not True
            or manifest.get("source_verified_by_pinned_sha256") is not True
            or manifest.get("quality_1000_certified") is not False
            or manifest.get("commercial_release_authorized") is not False
            or scores.get("dataset_raw_count")!=3810
            or not isinstance(scores.get("heldout_rows"),int)
            or scores["heldout_rows"]<500
            or not isinstance(scores.get("heldout_balanced_accuracy"),(int,float))
            or scores["heldout_balanced_accuracy"]<0.8
            or scores.get("onnx_vs_sklearn_label_mismatch_count")>1):
            raise RuntimeError("F26_ADMISSION_INCOMPLETE_FIELD_OR_HOLDOUT_EVIDENCE")
        original=primary_native_batch(root)
        for name,payload in contents.items():
            destination=stage/name
            with destination.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            destination.chmod(0o600)
        receipt={
            "schema":SCHEMA+".vps-admission",
            "family_id":"F26",
            "run_id":run_id,
            "repository_commit_sha":source_commit,
            "uploaded_bundle_sha256":expected_bundle_sha,
            "research_model_sha256":files["rice_cultivar_real_pilot.onnx"],
            "model_card_sha256":files["model_card.json"],
            "uci_public_archive_sha256":manifest["source_archive_sha256"],
            "real_world_rice_rows":scores["dataset_raw_count"],
            "untouched_heldout_rows":scores["heldout_rows"],
            "balanced_accuracy_heldout":scores["heldout_balanced_accuracy"],
            "previous_f26_native_48_models_preserved":True,
            "factory_master_review_claimed":False,
            "professional_quality_1000_certified":False,
            "physical_grain_camera_tested":False,
            "rights_reviewer_signature_present":False,
            "commercial_release_allowed":False,
            "website_changes":0
        }
        receipt.update(original)
        dest=stage/"private-f26-real-data-receipt.json"
        with dest.open("xb") as output:
            output.write((json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode("utf8"))
            output.flush()
            os.fsync(output.fileno())
        dest.chmod(0o600)
        target_previous_exists=target.exists()
        if target_previous_exists:
            raise RuntimeError("F26_ADMISSION_RACE_DESTINATION_EXISTS")
        os.rename(stage,target)
        os.chmod(target,0o700)
        print("FACTORY_F26_REAL_LICENSED_RICE_DATA_PRIVATE_VPS_ADMISSION=PASS")
        print("FACTORY_F26_REAL_PILOT_ROWS="+str(receipt["real_world_rice_rows"]))
        print("FACTORY_F26_REAL_PILOT_TEST_ROWS="+str(receipt["untouched_heldout_rows"]))
        print("FACTORY_F26_REAL_PILOT_PRIOR_48_SYNTHETIC_MODELS=UNCHANGED")
        print("FACTORY_F26_REAL_PILOT_HUMAN_OR_PHYSICAL_CERTIFICATION=NOT_GRANTED")
        print("FACTORY_F26_REAL_PILOT_COMMERCIAL_PUBLISHING=DISABLED")
        print("FACTORY_F26_REAL_PILOT_RECEIPT_SHA256="+sha(parse_file(target/"private-f26-real-data-receipt.json",200_000)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--bundle-sha256",required=True)
    a=p.parse_args()
    run(a.factory_private,a.run_id,a.source_commit,a.bundle_sha256)

if __name__=="__main__":
    main()
