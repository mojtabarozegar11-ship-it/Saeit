#!/usr/bin/env python3
"""Research-only guard for the existing F26 real rice classifier.

A high model score never means field validity. Fail closed on unfamiliar
morphology or low confidence; never promise QA1000 or allow commercial release.
Training-only feature bounds, SHA-bound ONNX and portable model coefficients.
Uses no third-party packages at prediction time (Python standard library).
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

SCHEMA="saeit.factory.f26.rice-domain-abstention.v1"
FIELDS=("Area","Perimeter","Major_Axis_Length","Minor_Axis_Length",
        "Eccentricity","Convex_Area","Extent")
HEX=re.compile(r"^[a-f0-9]{64}$")
MIN_CONFIDENCE=0.80

def sha(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<16_000_000:
        raise ValueError("GUARD_UNSAFE_OR_MISSING_SOURCE")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path, limit=150_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
        raise ValueError("GUARD_UNSAFE_JSON")
    obj=json.loads(path.read_text("utf8"))
    if not isinstance(obj,dict):
        raise ValueError("GUARD_SCHEMA_NOT_OBJECT")
    return obj

def load(path, name):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.suffix!=".py":
        raise ValueError("GUARD_PINNED_MODULE_MISSING")
    spec=importlib.util.spec_from_file_location(name,str(path))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def q(sorted_values, fract):
    n=len(sorted_values)
    if n<20 or not 0<=fract<=1:
        raise ValueError("GUARD_BAD_QUANTILE_SAMPLE")
    pos=(n-1)*fract
    lo=int(pos)
    hi=min(lo+1,n-1)
    return sorted_values[lo]+(pos-lo)*(sorted_values[hi]-sorted_values[lo])

def bounds(training_rows):
    if len(training_rows)<200:
        raise ValueError("GUARD_NOT_ENOUGH_TRAINING_ROWS")
    return [
        {"min":q(sorted(row[i] for row in training_rows),0.005),
         "max":q(sorted(row[i] for row in training_rows),0.995)}
        for i in range(7)
    ]

def decision(row, probability, envelope, confidence=MIN_CONFIDENCE):
    if len(row)!=7 or len(envelope)!=7 or not math.isfinite(probability):
        raise ValueError("GUARD_INVALID_INPUT")
    ood=[FIELDS[index] for index,(value,item) in enumerate(zip(row,envelope))
         if not math.isfinite(float(value)) or
         float(value)<item["min"] or float(value)>item["max"]]
    uncertain=max(probability,1-probability)<confidence
    reasons=[]
    if ood:reasons.append("outside_training_distribution")
    if uncertain:reasons.append("model_probability_below_research_threshold")
    return {"accepted_for_research_only":not reasons,
            "requires_independent_review":True,
            "abstention_reasons":reasons,
            "out_of_bounds_features":ood}

def verify(guard,model_dir,portable_spec):
    card=read(Path(model_dir)/"model_card.json")
    spec=read(portable_spec)
    if (guard.get("schema")!=SCHEMA or guard.get("family")!="F26"
        or guard.get("research_only") is not True
        or guard.get("quality_1000_certified") is not False
        or guard.get("independent_field_validated") is not False
        or guard.get("commercial_release_authorized") is not False
        or guard.get("source_dataset_sha256")!=card.get("dataset",{}).get("download_archive_sha256")
        or guard.get("model_onnx_sha256")!=card.get("onnx_model_sha256")
        or guard.get("portable_spec_sha256")!=sha(portable_spec)
        or guard.get("model_onnx_sha256")!=spec.get("model_sha256")
        or tuple(guard.get("features",[]))!=FIELDS
        or guard.get("min_model_confidence")!=MIN_CONFIDENCE
        or guard.get("domain_bounds_derived_from_training_only") is not True
        or guard.get("heldout_test_not_used_to_tune_bounds") is not True
        or guard.get("raw_image_input_supported") is not False
        or guard.get("source_train_count",0)<200
        or guard.get("source_validation_count",0)<100
        or guard.get("source_test_count",0)<100):
        raise ValueError("GUARD_UNVERIFIED_PROVENANCE_OR_QUALITY_POLICY")
    envelope=guard.get("feature_bounds")
    if (not isinstance(envelope,list) or len(envelope)!=7 or
        any(not isinstance(v,dict) or set(v)!={"min","max"}
            or type(v["min"]) not in (float,int) or type(v["max"]) not in (float,int)
            or not math.isfinite(v["min"]) or not math.isfinite(v["max"])
            or v["min"]>=v["max"] for v in envelope)):
        raise ValueError("GUARD_MALFORMED_ENVELOPE")
    return guard

def evaluate(model_dir,portable_spec,guard,rows,portable_script):
    portable=load(portable_script,"f26_guard_portable_runtime")
    coefficients=portable.validate(read(portable_spec),Path(model_dir))
    cli=portable.dependency("factory_f26_real_rice_cli.py")
    results=[]
    for i,row in enumerate(rows):
        measured=cli.numbers(row)
        probability,label=portable.formula(measured,coefficients)
        judgement=decision(measured,probability,guard["feature_bounds"],
                           guard["min_model_confidence"])
        results.append({
            "row":i+1,
            "status":("research_prediction_available" if judgement["accepted_for_research_only"]
                      else "abstained_requires_additional_review"),
            "research_prediction":(cli.NAMES[label]
                    if judgement["accepted_for_research_only"] else None),
            "uncalibrated_model_probability":round(probability,7),
            "abstention_reasons":judgement["abstention_reasons"],
            "out_of_bounds_features":judgement["out_of_bounds_features"],
            "field_validation_done":False,
            "quality_1000_certified":False,
            "commercial_release_authorized":False
        })
    return results

def export(archive,expected_hash,model_dir,portable_spec,portable_script,out):
    research=load(Path(__file__).resolve().parent/"factory_f26_real_rice_research_pilot.py",
                  "f26_guard_original_uci_parser")
    raw,_=research.read_archive(archive,expected_hash)
    rows,labels=research.parse_arff(raw)
    if len(rows)!=3810:
        raise ValueError("GUARD_PINNED_3810_SOURCE_REQUIRED")
    examples,(train,valid,test),duplicates=research.split_unique(rows,labels)
    training=[examples[i][0] for i in train]
    envelope=bounds(training)
    card=read(Path(model_dir)/"model_card.json")
    if (card.get("dataset",{}).get("download_archive_sha256")!=expected_hash
        or card.get("metrics",{}).get("train_rows")!=len(train)
        or card.get("metrics",{}).get("validation_rows")!=len(valid)
        or card.get("metrics",{}).get("heldout_rows")!=len(test)
        or card.get("metrics",{}).get("exact_feature_duplicates_removed")!=duplicates):
        raise ValueError("GUARD_TRAIN_SPLIT_NOT_MODEL_MATCHING")
    guard={
      "schema":SCHEMA,"family":"F26",
      "dataset_doi":"https://doi.org/10.24432/C5MW4Z",
      "dataset_license":"CC BY 4.0",
      "source_dataset_sha256":expected_hash,
      "model_onnx_sha256":card["onnx_model_sha256"],
      "portable_spec_sha256":sha(portable_spec),
      "features":list(FIELDS),
      "feature_bounds":envelope,
      "min_model_confidence":MIN_CONFIDENCE,
      "bounds_quantiles":[0.005,0.995],
      "source_train_count":len(train),
      "source_validation_count":len(valid),
      "source_test_count":len(test),
      "domain_bounds_derived_from_training_only":True,
      "heldout_test_not_used_to_tune_bounds":True,
      "raw_image_input_supported":False,
      "model_probability_is_field_calibrated":False,
      "research_only":True,
      "quality_1000_certified":False,
      "independent_field_validated":False,
      "commercial_release_authorized":False,
    }
    verify(guard,model_dir,portable_spec)
    validated=evaluate(model_dir,portable_spec,guard,
                       [examples[i][0] for i in valid],portable_script)
    heldout=evaluate(model_dir,portable_spec,guard,
                     [examples[i][0] for i in test],portable_script)
    def measure(values,indices):
        accepted=[(v,indices[i]) for i,v in enumerate(values)
                  if v["status"]=="research_prediction_available"]
        acc=(sum(int(v["research_prediction"]==("Osmancik" if examples[index][1]
                   else "Cammeo")) for v,index in accepted)/len(accepted)
             if accepted else 0)
        return {"samples":len(values),
                "research_prediction_coverage":len(accepted)/len(values),
                "accepted_prediction_accuracy_on_public_dataset":acc,
                "abstentions":len(values)-len(accepted)}
    guard["validation"]=measure(validated,valid)
    guard["holdout"]=measure(heldout,test)
    if (guard["validation"]["research_prediction_coverage"]<0.35
        or guard["holdout"]["research_prediction_coverage"]<0.35):
        raise RuntimeError("GUARD_REJECTS_TOO_MUCH_RESEARCH_DATA")
    path=Path(out)
    if path.is_symlink() or path.exists():
        raise ValueError("GUARD_OUTPUT_MUST_BE_NEW")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf8") as f:
        json.dump(guard,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    print("F26_TRAIN_ONLY_DISTRIBUTION_GUARD=PASS")
    print("F26_GUARD_TEST_RESULTS="+json.dumps(guard["holdout"],sort_keys=True))
    print("F26_GUARD_SPEC_SHA256="+sha(path))

def predict(args):
    model=Path(args.model_dir)
    guard_path=Path(args.guard_spec)
    spec_path=Path(args.portable_spec)
    portable_script=Path(args.portable_script)
    guard=verify(read(guard_path),model,spec_path)
    portable=load(portable_script,"f26_guard_input_tools")
    cli=portable.dependency("factory_f26_real_rice_cli.py")
    cases=cli.read_cases(args)
    predictions=evaluate(model,spec_path,guard,cases,portable_script)
    result={
        "schema":SCHEMA+".private-inference",
        "family":"F26",
        "real_dataset_doi":guard["dataset_doi"],
        "original_model_sha256":guard["model_onnx_sha256"],
        "guard_spec_sha256":sha(guard_path),
        "rows":len(predictions),
        "abstentions":sum(v["research_prediction"] is None for v in predictions),
        "research_only":True,
        "field_validation_done":False,
        "quality_1000_certified":False,
        "commercial_release_authorized":False,
        "predictions":predictions
    }
    target=Path(args.out)
    if target.is_symlink() or target.exists():
        raise ValueError("GUARD_OUTPUT_MUST_BE_NEW")
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    print("F26_GUARDED_OFFLINE_PREDICTIONS="+str(result["rows"]))
    print("F26_GUARDED_ABSTENTIONS="+str(result["abstentions"]))
    print("F26_GUARDED_COMMERCIAL_RELEASE=false")

def main():
    p=argparse.ArgumentParser()
    choices=p.add_mutually_exclusive_group(required=True)
    choices.add_argument("--export",action="store_true")
    choices.add_argument("--predict",action="store_true")
    p.add_argument("--model-dir",required=True)
    p.add_argument("--portable-spec",required=True)
    p.add_argument("--portable-script",required=True)
    p.add_argument("--archive")
    p.add_argument("--expected-archive-sha256")
    p.add_argument("--guard-spec")
    p.add_argument("--csv")
    p.add_argument("--features",nargs=7)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    try:
        if args.export:
            if (not args.archive or not args.expected_archive_sha256
                or args.guard_spec or args.csv or args.features):
                raise ValueError("GUARD_EXPORT_PINNED_UCI_REQUIRED")
            export(Path(args.archive),args.expected_archive_sha256,
                   Path(args.model_dir),Path(args.portable_spec),
                   Path(args.portable_script),Path(args.out))
        else:
            if (not args.guard_spec or args.archive or args.expected_archive_sha256
                or ((args.csv is None)==(args.features is None))):
                raise ValueError("GUARD_INFERENCE_ARGS_INVALID")
            predict(args)
    except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
        p.exit(2,"F26_RESEARCH_GUARD_DENIED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
