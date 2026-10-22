#!/usr/bin/env python3
"""Private, offline prediction from the real-data F26 UCI rice ONNX research pilot.

Seven numeric morphology features are REQUIRED, not a photograph.
This helper does not establish field validity, expert review or QA-1000.
Fails closed on changed model SHA, invalid rows, oversize files, NaN and inf.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

SCHEMA="saeit.factory.f26.real-rice-research-pilot.v1"
FIELDS=("Area","Perimeter","Major_Axis_Length","Minor_Axis_Length",
        "Eccentricity","Convex_Area","Extent")
NAMES=("Cammeo","Osmancik")
HEX=re.compile(r"^[a-f0-9]{64}$")
MAX_ROWS=1000
MAX_INPUT_BYTES=2_000_000

def digest(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>15_000_000:
        raise ValueError("F26_INPUT_OR_MODEL_UNSAFE")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>160_000:
        raise ValueError("F26_RESEARCH_PROVENANCE_MISSING")
    return json.loads(path.read_text(encoding="utf8"))

def verify_model(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("F26_MODEL_DIRECTORY_UNSAFE")
    manifest=read_json(root/"manifest.json")
    card=read_json(root/"model_card.json")
    required={"rice_cultivar_real_pilot.onnx","model_card.json","ATTRIBUTION_AND_LIMITS.txt"}
    files=manifest.get("artifact_sha256")
    if (manifest.get("schema")!=SCHEMA+".artifact-manifest"
        or not isinstance(files,dict) or set(files)!=required
        or manifest.get("family_id")!="F26"
        or manifest.get("holdout_data_real_and_not_synthetic") is not True
        or manifest.get("independent_specialist_approved") is not False
        or manifest.get("quality_1000_certified") is not False
        or manifest.get("commercial_release_authorized") is not False
        or card.get("schema")!=SCHEMA
        or card.get("family")!="F26"
        or card.get("research_only") is not True
        or card.get("independent_specialist_approval") is not False
        or card.get("independent_field_validation") is not False
        or card.get("quality_1000_certified") is not False
        or card.get("commercial_release_authorized") is not False
        or tuple(card.get("target_classes",[]))!=NAMES
        or tuple(card.get("input_features",[]))!=FIELDS
        or card.get("onnx_model_sha256")!=files.get("rice_cultivar_real_pilot.onnx")
        or card.get("dataset",{}).get("doi")!="https://doi.org/10.24432/C5MW4Z"
        or card.get("dataset",{}).get("download_archive_sha256")!=manifest.get("source_archive_sha256")):
        raise ValueError("F26_MODEL_INVALID_RESEARCH_PROVENANCE")
    for name,claimed in files.items():
        if not isinstance(claimed,str) or not HEX.fullmatch(claimed) or digest(root/name)!=claimed:
            raise ValueError("F26_MODEL_OR_ATTRIBUTION_HASH_CHANGED")
    metrics=card.get("metrics",{})
    if (metrics.get("dataset_raw_count")!=3810 or
        metrics.get("heldout_rows",0)<500 or
        metrics.get("heldout_onnx_runtime_prediction_count")!=metrics.get("heldout_rows") or
        metrics.get("onnx_vs_sklearn_label_mismatch_count")!=0):
        raise ValueError("F26_MODEL_HOLDOUT_PROOF_INCOMPLETE")
    return card

def numbers(values):
    if len(values)!=7:
        raise ValueError("F26_REQUIRES_SEVEN_MEASURED_FEATURES")
    try:
        result=[float(v) for v in values]
    except (ValueError,TypeError) as exc:
        raise ValueError("F26_NON_NUMERIC_MEASUREMENT") from exc
    if not all(math.isfinite(v) for v in result):
        raise ValueError("F26_NON_FINITE_MEASUREMENT")
    a,p,major,minor,ecc,convex,extent=result
    if not (a>0 and p>0 and major>0 and minor>0 and convex>0
            and major>=minor and 0<=ecc<1 and 0<extent<=1
            and convex>=a):
        raise ValueError("F26_MORPHOLOGY_OUTSIDE_PHYSICAL_CONSTRAINTS")
    if max(result)>1e9:
        raise ValueError("F26_MEASUREMENT_TOO_LARGE")
    return result

def read_cases(args):
    if args.features is not None:
        return [numbers(args.features)]
    csvpath=Path(args.csv)
    if (csvpath.is_symlink() or not csvpath.is_file() or
            not 0<csvpath.stat().st_size<=MAX_INPUT_BYTES):
        raise ValueError("F26_CSV_MISSING_OR_OVERSIZED")
    with csvpath.open("r",encoding="utf-8-sig",newline="") as source:
        reader=csv.reader(source,strict=True)
        try:
            columns=next(reader)
        except StopIteration as exc:
            raise ValueError("F26_CSV_EMPTY") from exc
        if tuple(columns)!=FIELDS:
            raise ValueError("F26_CSV_HEADER_MUST_MATCH_EXACT_SEVEN_FEATURE_NAMES")
        rows=[]
        for row in reader:
            if len(rows)>=MAX_ROWS:
                raise ValueError("F26_CSV_TOO_MANY_GRAINS")
            rows.append(numbers(row))
    if not rows:
        raise ValueError("F26_CSV_NO_ROWS")
    return rows

def predict(root,cases):
    import numpy as np
    import onnxruntime as ort
    import onnx
    card=verify_model(root)
    model=root/"rice_cultivar_real_pilot.onnx"
    onnx.checker.check_model(onnx.load(str(model)))
    settings=ort.SessionOptions()
    settings.intra_op_num_threads=1
    settings.inter_op_num_threads=1
    session=ort.InferenceSession(str(model),sess_options=settings,
                                 providers=["CPUExecutionProvider"])
    inputs=session.get_inputs()
    if len(inputs)!=1 or inputs[0].name!="input" or inputs[0].shape[-1]!=7:
        raise ValueError("F26_ONNX_MODEL_INPUT_CONTRACT_CHANGED")
    arr=np.asarray(cases,dtype=np.float32)
    if not np.all(np.isfinite(arr)):
        raise ValueError("F26_INPUT_FLOAT32_OVERFLOW")
    out=session.run(None,{"input":arr})
    if len(out)!=2:
        raise ValueError("F26_MODEL_OUTPUT_CONTRACT_INVALID")
    prob=np.asarray(out[0],dtype=np.float64).reshape(-1)
    labels=np.asarray(out[1]).reshape(-1)
    if (len(prob)!=len(cases) or len(labels)!=len(cases) or
            not np.all(np.isfinite(prob)) or
            np.any((prob<0)|(prob>1)) or
            np.any((labels!=0)&(labels!=1)) or
            np.any((prob>0.5).astype(int)!=labels)):
        raise ValueError("F26_RESEARCH_ONNX_INVALID_PREDICTION")
    predictions=[]
    for index,(row,p,label) in enumerate(zip(cases,prob,labels)):
        predictions.append({
            "row":index+1,
            "predicted_cultivar":NAMES[int(label)],
            "model_probability_osmancik":round(float(p),7),
            "measurements":dict(zip(FIELDS,row)),
            "independent_field_validation":False,
            "out_of_distribution_safety_verified":False
        })
    return {
        "schema":SCHEMA+".offline-inference.v1",
        "family_id":"F26",
        "model_sha256":card["onnx_model_sha256"],
        "dataset_doi":"https://doi.org/10.24432/C5MW4Z",
        "count":len(predictions),
        "purpose":"research_demonstration_only",
        "source_is_morphological_measurements_not_raw_images":True,
        "no_external_service_called":True,
        "probabilities_are_model_estimates_not_calibrated_field_certainty":True,
        "human_expert_quality_1000_certified":False,
        "physical_field_validation_completed":False,
        "commercial_release_authorized":False,
        "predictions":predictions
    }

def main():
    p=argparse.ArgumentParser(description="F26 offline real-data rice morphology inference (research-only)")
    p.add_argument("--model-dir",required=True)
    inputs=p.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--features",nargs=7,metavar=FIELDS)
    inputs.add_argument("--csv")
    p.add_argument("--out",help="new private JSON file; output does not overwrite existing files")
    args=p.parse_args()
    try:
        rows=read_cases(args)
        result=predict(Path(args.model_dir),rows)
        serialized=json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+"\n"
        if args.out:
            target=Path(args.out)
            if target.is_symlink() or target.exists():
                raise ValueError("F26_OUTPUT_ALREADY_EXISTS")
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open("x",encoding="utf8") as f:
                f.write(serialized)
        else:
            sys.stdout.write(serialized)
    except (ValueError,RuntimeError,KeyError,OSError,ImportError) as exc:
        p.exit(2,"F26_INFERENCE_DENIED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
