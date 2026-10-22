#!/usr/bin/env python3
"""New immutable private VPS F26 domain guard; preserves installed research model."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

RUN=re.compile(r"^[0-9]{6,18}-[0-9]{1,3}$")
SHA=re.compile(r"^[a-f0-9]{64}$")
SCHEMA="saeit.factory.f26.rice-domain-abstention.v1"
FILES=("factory_f26_rice_research_guard.py","guard-spec.json","rice-samples.csv")
MAX_BYTES=200_000

def digest(path,limit=1_000_000):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=limit:
        raise RuntimeError("F26_GUARD_VPS_FILE_UNSAFE")
    return hashlib.sha256(p.read_bytes()).hexdigest()

def document(p, limit=150_000):
    p=Path(p)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>limit:
        raise RuntimeError("F26_GUARD_VPS_UNSAFE_JSON")
    v=json.loads(p.read_text("utf8"))
    if not isinstance(v,dict):
        raise RuntimeError("F26_GUARD_VPS_EXPECTED_DOCUMENT")
    return v

def locate(root, guard):
    root=root/"f26-real-data-research"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("F26_GUARD_NO_ORIGINAL_RESEARCH")
    original=[]
    for folder in root.iterdir():
        if not folder.is_dir() or folder.is_symlink() or not RUN.fullmatch(folder.name):
            continue
        try:
            receipt=document(folder/"private-f26-real-data-receipt.json")
            card=document(folder/"model_card.json")
            if (receipt.get("schema")!="saeit.factory.f26.real-rice-research-pilot.v1.vps-admission"
                 or receipt.get("run_id")!=folder.name
                 or receipt.get("research_model_sha256")!=guard["model_onnx_sha256"]
                 or receipt.get("commercial_release_allowed") is not False
                 or receipt.get("professional_quality_1000_certified") is not False
                 or receipt.get("previous_f26_native_48_models_preserved") is not True
                 or card.get("onnx_model_sha256")!=guard["model_onnx_sha256"]
                 or digest(folder/"rice_cultivar_real_pilot.onnx",16_000_000)!=guard["model_onnx_sha256"]
                 or card.get("dataset",{}).get("download_archive_sha256")!=guard["source_dataset_sha256"]
                 or card.get("quality_1000_certified") is not False):
                continue
            portable=root/("portable-"+folder.name)
            proof=document(portable/"private-portable-deployment-receipt.json")
            spec=portable/"portable-spec.json"
            specdoc=document(spec)
            if (portable.is_symlink() or
                  proof.get("schema")!="saeit.factory.f26.portable-private-admission.v1"
                  or proof.get("source_run")!=folder.name
                  or proof.get("real_model_sha256")!=guard["model_onnx_sha256"]
                  or proof.get("quality_1000_certified") is not False
                  or proof.get("commercial_release") is not False
                  or proof.get("public_site_changes")!=0
                  or specdoc.get("model_sha256")!=guard["model_onnx_sha256"]
                  or digest(spec)!=guard["portable_spec_sha256"]):
                continue
            for name in ("factory_f26_rice_onnx_portable.py","factory_f26_real_rice_cli.py"):
                if digest(portable/name)!=proof.get("portable_source_sha256",{}).get(name):
                    raise RuntimeError("F26_GUARD_EXISTING_PORTABLE_SCRIPT_HASH_FAIL")
            original.append((folder.name,folder,portable))
        except (RuntimeError,ValueError,KeyError,TypeError,OSError):
            continue
    if not original:
        raise RuntimeError("F26_GUARD_NO_MODEL_AND_RUNTIME_SAME_PROVENANCE")
    return max(original,key=lambda entry:tuple(map(int,entry[0].split("-"))))

def install(private,run,sha_manifest,source_commit):
    if not RUN.fullmatch(run) or not re.fullmatch(r"[a-f0-9]{40}",source_commit):
        raise RuntimeError("F26_GUARD_INVALID_DEPLOY_IDENTITY")
    base=Path(private)
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("F26_GUARD_PRIVATE_ROOT_MISSING")
    repo=base/"f26-real-data-research"
    stage=repo/(".incoming-guard-"+run)
    destination=repo/("guard-"+run)
    if (repo.is_symlink() or stage.is_symlink() or not stage.is_dir()
        or destination.exists() or destination.is_symlink()):
        raise RuntimeError("F26_GUARD_STAGE_EXISTS_OR_UNSAFE")
    manifest=document(sha_manifest,10_000)
    if (set(manifest)!=set(FILES)
        or any(not isinstance(v,str) or not SHA.fullmatch(v) for v in manifest.values())
        or any(digest(stage/name)!=manifest[name] for name in FILES)):
        raise RuntimeError("F26_GUARD_STAGE_SHA_MISMATCH")
    guard=document(stage/"guard-spec.json")
    if (guard.get("schema")!=SCHEMA
        or guard.get("family")!="F26"
        or guard.get("research_only") is not True
        or guard.get("commercial_release_authorized") is not False
        or guard.get("quality_1000_certified") is not False
        or guard.get("independent_field_validated") is not False
        or guard.get("domain_bounds_derived_from_training_only") is not True
        or guard.get("heldout_test_not_used_to_tune_bounds") is not True
        or guard.get("raw_image_input_supported") is not False
        or guard.get("source_test_count")!=762
        or guard.get("holdout",{}).get("samples")!=762):
        raise RuntimeError("F26_GUARD_UNPROVEN_RESEARCH_SPEC")
    lock=repo/".f26-domain-guard.lock"
    if lock.is_symlink():
        raise RuntimeError("F26_GUARD_LOCK_UNSAFE")
    with lock.open("a+") as mutex:
        fcntl.flock(mutex,fcntl.LOCK_EX)
        source_id,original,portable=locate(base,guard)
        python=Path(sys.executable)
        expected=("--model-dir",str(original),
                  "--portable-spec",str(portable/"portable-spec.json"),
                  "--portable-script",str(portable/"factory_f26_rice_onnx_portable.py"),
                  "--guard-spec",str(stage/"guard-spec.json"))
        pilot=stage/"factory_f26_rice_research_guard.py"
        def execute(extra,out):
            command=[str(python),"-S",str(pilot),"--predict",*expected,
                     *extra,"--out",str(out)]
            p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             text=True,timeout=45,check=False)
            if p.returncode:
                raise RuntimeError("F26_GUARD_OFFLINE_FUNCTIONAL_FAILURE:"+p.stderr[-240:])
            return document(out)
        real=execute(("--csv",str(stage/"rice-samples.csv")),
                     stage/"private-real-rice-guard-proof.json")
        if (real.get("schema")!=SCHEMA+".private-inference"
            or real.get("rows")!=12 or real.get("quality_1000_certified") is not False
            or real.get("commercial_release_authorized") is not False
            or real.get("original_model_sha256")!=guard["model_onnx_sha256"]
            or real.get("guard_spec_sha256")!=manifest["guard-spec.json"]):
            raise RuntimeError("F26_GUARD_REAL_RICE_PROOF_INVALID")
        strange=execute(("--features","1000000","8000","1000","900",
                         "0.8","1000200","0.6"),
                        stage/"private-unfamiliar-grain-guard-proof.json")
        if (strange.get("rows")!=1 or strange.get("abstentions")!=1
            or strange["predictions"][0].get("research_prediction") is not None
            or "outside_training_distribution" not in
                strange["predictions"][0].get("abstention_reasons",[])):
            raise RuntimeError("F26_GUARD_FAILS_TO_ABSTAIN_ON_UNFAMILIAR_INPUT")
        record={
            "schema":SCHEMA+".vps-admission",
            "family":"F26", "run":run,"source_commit_sha":source_commit,
            "previous_research_run":source_id,
            "previous_model_sha256":guard["model_onnx_sha256"],
            "previous_48_onnx_models_preserved":True,
            "original_research_files_modified":False,
            "portable_runtime_files_modified":False,
            "source_uci_archive_sha256":guard["source_dataset_sha256"],
            "guard_spec_sha256":manifest["guard-spec.json"],
            "real_uci_grains_trialled":12,
            "real_uci_grains_abstained":real["abstentions"],
            "unfamiliar_input_abstained":True,
            "real_uci_proof_sha256":digest(stage/"private-real-rice-guard-proof.json"),
            "ood_proof_sha256":digest(stage/"private-unfamiliar-grain-guard-proof.json"),
            "independent_field_validation":False,
            "independent_specialist_review":False,
            "quality_1000_certified":False,
            "commercial_release_authorized":False,"public_site_changes":0
        }
        receipt=stage/"private-domain-guard-receipt.json"
        with receipt.open("x",encoding="utf8") as f:
            json.dump(record,f,indent=2,sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        for p in stage.iterdir():
            if p.is_file():p.chmod(0o600)
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("F26_GUARD_ALREADY_DEPLOYED")
        os.rename(stage,destination)
        destination.chmod(0o700)
        print("F26_RESEARCH_DOMAIN_GUARD_PRIVATE_VPS=PASS")
        print("F26_RESEARCH_GUARD_12_REAL_GRAINS=PASS")
        print("F26_RESEARCH_GUARD_OUT_OF_DISTRIBUTION_ABSTENTION=PASS")
        print("F26_RESEARCH_GUARD_ORIGINAL_MODEL_UNCHANGED=PASS")
        print("F26_RESEARCH_GUARD_FIELD_SPECIALIST_SIGNOFF=NOT_GRANTED")
        print("F26_RESEARCH_GUARD_QUALITY_1000=NOT_GRANTED")
        print("F26_RESEARCH_GUARD_PUBLICATION=DISABLED")
        print("F26_RESEARCH_GUARD_RECEIPT_SHA256="+digest(destination/"private-domain-guard-receipt.json"))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--sha-manifest",required=True)
    args=p.parse_args()
    install(args.factory_private,args.run_id,args.sha_manifest,args.source_commit)

if __name__=="__main__":
    main()
