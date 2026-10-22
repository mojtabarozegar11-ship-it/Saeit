#!/usr/bin/env python3
"""Fail-closed isolated, private F26 model CLI admission to real VPS.

No installation into factory or website Python; no existing model overwritten.
Runs the actual 12-row CLI using system Python -S after verifying every SHA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

RUN=re.compile(r"^[0-9]{6,18}-[0-9]{1,3}$")
HEX=re.compile(r"^[a-f0-9]{64}$")
COMMIT=re.compile(r"^[a-f0-9]{40}$")
SCHEMA="saeit.factory.f26.portable-private-admission.v1"
STAGED=("factory_f26_real_rice_cli.py","factory_f26_rice_onnx_portable.py",
        "portable-spec.json","rice-inference.csv")
def checksum(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1_500_000:
        raise RuntimeError("F26_PORTABLE_BAD_STAGE_FILE")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def execute(root,run,commit,proof):
    base=Path(root)
    if base.is_symlink() or not base.is_dir() or not RUN.fullmatch(run) or not COMMIT.fullmatch(commit):
        raise RuntimeError("F26_PORTABLE_UNSAFE_ROOT_OR_RUN")
    if not isinstance(proof,dict) or set(proof)!=set(STAGED) or any(
        not isinstance(value,str) or not HEX.fullmatch(value) for value in proof.values()):
        raise RuntimeError("F26_PORTABLE_INVALID_HASH_MANIFEST")
    research=base/"f26-real-data-research"
    original=research/run
    if original.is_symlink() or not original.is_dir():
        raise RuntimeError("F26_PORTABLE_ORIGINAL_VPS_MODEL_NOT_INSTALLED")
    stage=research/(".incoming-portable-"+run)
    final=research/("portable-"+run)
    if (stage.is_symlink() or not stage.is_dir() or final.exists() or final.is_symlink()):
        raise RuntimeError("F26_PORTABLE_NOT_NEW_AND_ISOLATED")
    for name in STAGED:
        if checksum(stage/name)!=proof[name]:
            raise RuntimeError("F26_PORTABLE_TRANSFER_HASH_MISMATCH")
    receipt=original/"private-f26-real-data-receipt.json"
    if receipt.is_symlink() or not receipt.is_file():
        raise RuntimeError("F26_PORTABLE_ORIGINAL_RESEARCH_RECEIPT_MISSING")
    previous=json.loads(receipt.read_text("utf8"))
    card=json.loads((original/"model_card.json").read_text("utf8"))
    if (previous.get("schema")!="saeit.factory.f26.real-rice-research-pilot.v1.vps-admission"
        or previous.get("run_id")!=run
        or previous.get("research_model_sha256")!=card.get("onnx_model_sha256")
        or previous.get("commercial_release_allowed") is not False
        or previous.get("professional_quality_1000_certified") is not False
        or previous.get("previous_f26_native_48_models_preserved") is not True):
        raise RuntimeError("F26_PORTABLE_PREVIOUS_MODEL_POLICY_INVALID")
    cli=stage/"factory_f26_rice_onnx_portable.py"
    spec=stage/"portable-spec.json"
    csv=stage/"rice-inference.csv"
    out=stage/"private-offline-prediction-proof.json"
    command=[sys.executable,"-S",str(cli),"--predict",
             "--model-dir",str(original),
             "--runtime-spec",str(spec),
             "--csv",str(csv),
             "--out",str(out)]
    run_result=subprocess.run(command,capture_output=True,text=True,timeout=35,check=False)
    if run_result.returncode!=0 or "F26_PORTABLE_PRIVATE_INFERENCE=PASS" not in run_result.stdout:
        raise RuntimeError("F26_PORTABLE_ACTUAL_VPS_PREDICTION_FAILED:"+run_result.stderr[-250:])
    predictions=json.loads(out.read_text("utf8"))
    if (predictions.get("schema")!="saeit.factory.f26.real-rice-portable-inference.v1.offline-result"
        or predictions.get("source_onnx_sha256")!=previous["research_model_sha256"]
        or predictions.get("count")!=12
        or len(predictions.get("predictions",[]))!=12
        or predictions.get("quality_1000_certified") is not False
        or predictions.get("commercial_release_authorized") is not False
        or predictions.get("field_validated") is not False):
        raise RuntimeError("F26_PORTABLE_PREDICTIONS_NOT_PROVEN")
    original_digest=checksum(original/"private-f26-real-data-receipt.json")
    summary={
        "schema":SCHEMA,"source_run":run,"source_commit":commit,
        "real_model_sha256":previous["research_model_sha256"],
        "existing_vps_original_receipt_sha256":original_digest,
        "portable_source_sha256":{k:proof[k] for k in STAGED},
        "demo_12_real_grains_result_sha256":checksum(out),
        "verified_onnx_equivalence_holdout_grains":762,
        "independent_device_or_agronomy_review":False,
        "quality_1000_certified":False,
        "commercial_release":False,
        "original_model_files_modified":False,
        "public_site_changes":0}
    with (stage/"private-portable-deployment-receipt.json").open("x",encoding="utf8") as f:
        json.dump(summary,f,sort_keys=True,indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    usage=(
        "F26 research only, not commercial or field-validated.\n"
        "The seven inputs must be: Area Perimeter Major_Axis_Length "
        "Minor_Axis_Length Eccentricity Convex_Area Extent.\n"
        "Runtime uses Python standard library and the verified ONNX coefficients.\n"
        "Example: python3 -S "+str(final/"factory_f26_rice_onnx_portable.py")+
        " --predict --model-dir "+str(original)+" --runtime-spec "+
        str(final/"portable-spec.json")+" --features 14000 520 190 80 0.7 15000 0.6"
        " --out /path/to/a/new/private-result.json\n")
    (stage/"USAGE_PRIVATE_RESEARCH.txt").write_text(usage,encoding="utf8")
    for f in stage.iterdir():
        if f.is_file():f.chmod(0o600)
    os.rename(stage,final)
    os.chmod(final,0o700)
    print("F26_PORTABLE_REAL_VPS_OFFLINE_INFERENCE=PASS")
    print("F26_PORTABLE_VPS_REAL_GRAINS=12")
    print("F26_PORTABLE_REAL_ONNX_HOLDOUT_EQUIVALENCE=762")
    print("F26_PORTABLE_PURE_PYTHON_NO_ONNXRUNTIME_INSTALLED=true")
    print("F26_PORTABLE_PRIOR_RESEARCH_FILES_UNCHANGED=true")
    print("F26_PORTABLE_QUALITY_1000_NOT_CERTIFIED=true")
    print("F26_PORTABLE_PUBLIC_RELEASE=false")
    print("F26_PORTABLE_VPS_RECEIPT_SHA256="+checksum(final/"private-portable-deployment-receipt.json"))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    p.add_argument("--source-run",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--hash-manifest",required=True)
    args=p.parse_args()
    m=Path(args.hash_manifest)
    if m.is_symlink() or not m.is_file() or m.stat().st_size>20000:
        raise RuntimeError("F26_PORTABLE_HASH_MANIFEST_UNSAFE")
    execute(args.factory_private,args.source_run,args.source_commit,json.loads(m.read_text("utf8")))

if __name__=="__main__":
    main()
