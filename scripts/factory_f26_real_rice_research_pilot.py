#!/usr/bin/env python3
"""Real-data F26 research pilot: two rice cultivars, public UCI DOI C5MW4Z.

Train/validation/test are disjoint *after feature-level deduplication*.
Exports executable ONNX, checks every held-out prediction against sklearn.
Strict source archive SHA provided by invoking CI, never claims real farm QA,
independent human review, product commercialization, or 1000 quality.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import tempfile
import zipfile

DATASET="Rice (Cammeo and Osmancik), UCI repository, 2019"
DOI="https://doi.org/10.24432/C5MW4Z"
SOURCE="https://archive.ics.uci.edu/static/public/545/rice%2Bcammeo%2Band%2Bosmancik.zip"
FIELDS=("Area","Perimeter","Major_Axis_Length","Minor_Axis_Length",
        "Eccentricity","Convex_Area","Extent")
CLASSES=("Cammeo","Osmancik")
SCHEMA="saeit.factory.f26.real-rice-research-pilot.v1"
HEX=re.compile(r"[0-9a-f]{64}")

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(data):
    return (json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+"\n").encode("utf8")

def read_archive(path,expected_sha256):
    path=Path(path)
    if not HEX.fullmatch(str(expected_sha256)):
        raise RuntimeError("F26_RICE_PINNED_SHA_REQUIRED")
    if path.is_symlink() or not path.is_file() or not 1000<path.stat().st_size<2_000_000:
        raise RuntimeError("F26_RICE_UNSAFE_SOURCE_ZIP")
    raw=path.read_bytes()
    if digest(raw)!=expected_sha256:
        raise RuntimeError("F26_RICE_ARCHIVE_SHA_PIN_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=archive.infolist()
        if (len(members)<1 or len(members)>8 or
            any(n.is_dir() or n.flag_bits & 1 or n.file_size>950_000 or
                ((n.external_attr>>16)&0o170000)==0o120000
                for n in members) or
            sum(n.file_size for n in members)>1_500_000 or
            archive.testzip() is not None):
            raise RuntimeError("F26_RICE_ZIP_STRUCTURE_UNSAFE")
        arff=[n for n in members if n.filename.rsplit("/",1)[-1]=="Rice_Cammeo_Osmancik.arff"]
        if len(arff)!=1:
            raise RuntimeError("F26_RICE_REAL_ARFF_FILE_MISSING")
        text=archive.read(arff[0]).decode("utf-8-sig")
    return text, digest(raw)

def parse_arff(source):
    headers=[]
    rows=[]
    labels=[]
    body=False
    for line in source.splitlines():
        line=line.strip()
        if not line or line.startswith("%"):
            continue
        if not body and line.lower().startswith("@attribute"):
            tokens=line.split(None,2)
            if len(tokens)!=3:
                raise RuntimeError("F26_RICE_ARFF_INVALID_COLUMN")
            headers.append(tokens[1].strip("'\""))
            continue
        if line.lower()=="@data":
            body=True
            continue
        if line.startswith("@"):
            if body:raise RuntimeError("F26_RICE_INVALID_DATA_METADATA")
            continue
        if not body:
            continue
        parts=[v.strip(" '\"\t") for v in line.split(",")]
        if len(parts)!=8 or parts[7] not in CLASSES:
            raise RuntimeError("F26_RICE_BAD_ROW_OR_LABEL")
        try:
            features=tuple(float(value) for value in parts[:7])
        except ValueError as exc:
            raise RuntimeError("F26_RICE_NONNUMERIC_FEATURE") from exc
        if not all(math.isfinite(v) for v in features):
            raise RuntimeError("F26_RICE_NONFINITE_FEATURE")
        if features[0]<=0 or features[1]<=0 or features[5]<=0:
            raise RuntimeError("F26_RICE_INVALID_GRAIN_GEOMETRY")
        rows.append(features)
        labels.append(int(parts[7]=="Osmancik"))
    if tuple(headers)!=FIELDS+("Class",):
        raise RuntimeError("F26_RICE_UNEXPECTED_DATASET_SCHEMA "+repr(headers))
    if not body or len(rows)<200:
        raise RuntimeError("F26_RICE_NOT_REAL_DATASET")
    return rows,labels

def split_unique(rows,labels):
    from sklearn.model_selection import train_test_split
    seen={}
    contradictory=0
    for x,y in zip(rows,labels):
        if x in seen and seen[x]!=y:
            contradictory+=1
        else:
            seen[x]=y
    if contradictory:
        raise RuntimeError("F26_RICE_CONTRADICTORY_DUPLICATE_FEATURES")
    examples=list(seen.items())
    if len(examples)<200:
        raise RuntimeError("F26_RICE_TOO_FEW_DISTINCT_ROWS")
    indices=list(range(len(examples)))
    y=[value for _,value in examples]
    trainval,test=train_test_split(indices,test_size=0.2,random_state=1457,stratify=y)
    train,valid=train_test_split(trainval,test_size=0.25,random_state=1458,
                                stratify=[y[i] for i in trainval])
    groups=(train,valid,test)
    for one in groups:
        if not one or {y[i] for i in one}!={0,1}:
            raise RuntimeError("F26_RICE_UNBALANCED_SPLIT")
    if any(set(a).intersection(b) for a,b in ((train,valid),(train,test),(valid,test))):
        raise RuntimeError("F26_RICE_SPLIT_DATA_LEAKAGE")
    return examples,groups,len(rows)-len(examples)

def train(archive,out,source_sha):
    import numpy as np
    import onnx
    from onnx import TensorProto,helper,checker
    import onnxruntime as ort
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (accuracy_score,balanced_accuracy_score,
                                 f1_score,confusion_matrix)
    from sklearn.preprocessing import StandardScaler
    from sklearn.dummy import DummyClassifier

    text,archive_sha=read_archive(archive,source_sha)
    rows,labels=parse_arff(text)
    # A real 3810-sample source is mandatory for the production CI path.
    if len(rows)!=3810 or {0,1}!={int(v) for v in labels}:
        raise RuntimeError("F26_RICE_UCI_3810_ROWS_EXPECTED")
    items,(train_idx,val_idx,test_idx),dups=split_unique(rows,labels)
    x=np.asarray([p[0] for p in items],dtype=np.float64)
    y=np.asarray([p[1] for p in items],dtype=np.int64)
    scaler=StandardScaler().fit(x[train_idx])
    xtrain=scaler.transform(x[train_idx])
    xvalid=scaler.transform(x[val_idx])
    xtest=scaler.transform(x[test_idx])
    model=LogisticRegression(class_weight="balanced",random_state=1459,max_iter=1500)
    model.fit(xtrain,y[train_idx])
    baseline=DummyClassifier(strategy="most_frequent").fit(xtrain,y[train_idx])
    pred=model.predict(xtest)
    base=baseline.predict(xtest)
    acc=float(accuracy_score(y[test_idx],pred))
    balanced=float(balanced_accuracy_score(y[test_idx],pred))
    f1=float(f1_score(y[test_idx],pred))
    baseline_accuracy=float(accuracy_score(y[test_idx],base))
    valid_accuracy=float(accuracy_score(y[val_idx],model.predict(xvalid)))
    if acc<0.82 or balanced<0.8 or acc-baseline_accuracy<0.08:
        raise RuntimeError("F26_RICE_PILOT_BELOW_REAL_HOLDOUT_ACCEPTANCE")
    if out.exists() or out.is_symlink():
        raise RuntimeError("F26_RICE_OUTPUT_MUST_BE_NEW")
    out.mkdir(parents=True,mode=0o700)
    # The exact fitted *train-only* normalizer is embedded in the ONNX graph.
    mean=np.asarray(scaler.mean_,dtype=np.float32)
    scale=np.asarray(scaler.scale_,dtype=np.float32)
    weights=np.asarray(model.coef_.reshape((7,1)),dtype=np.float32)
    bias=np.asarray(model.intercept_,dtype=np.float32)
    graph=helper.make_graph(
        [helper.make_node("Sub",["input","mean"],["shift"]),
         helper.make_node("Div",["shift","scale"],["normalized"]),
         helper.make_node("MatMul",["normalized","weights"],["scores"]),
         helper.make_node("Add",["scores","bias"],["logits"]),
         helper.make_node("Sigmoid",["logits"],["probability"]),
         helper.make_node("Greater",["probability","threshold"],["chosen"]),
         helper.make_node("Cast",["chosen"],["class_index"],to=TensorProto.INT64)],
        "F26RiceCammeoOsmancikRealDataPilot",
        [helper.make_tensor_value_info("input",TensorProto.FLOAT,[None,7])],
        [helper.make_tensor_value_info("probability",TensorProto.FLOAT,[None,1]),
         helper.make_tensor_value_info("class_index",TensorProto.INT64,[None,1])],
        initializer=[
            helper.make_tensor("mean",TensorProto.FLOAT,[7],mean),
            helper.make_tensor("scale",TensorProto.FLOAT,[7],scale),
            helper.make_tensor("weights",TensorProto.FLOAT,[7,1],weights.flatten()),
            helper.make_tensor("bias",TensorProto.FLOAT,[1],bias),
            helper.make_tensor("threshold",TensorProto.FLOAT,[1],[0.5])])
    converted=helper.make_model(graph,opset_imports=[helper.make_opsetid("",13)])
    converted.ir_version=9
    checker.check_model(converted)
    model_path=out/"rice_cultivar_real_pilot.onnx"
    onnx.save(converted,str(model_path))
    session=ort.InferenceSession(str(model_path),providers=["CPUExecutionProvider"])
    ort_prob,ort_label=session.run(None,{"input":x[test_idx].astype("float32")})
    sk_prob=model.predict_proba(xtest)[:,1]
    max_difference=float(np.max(np.abs(ort_prob.flatten()-sk_prob)))
    label_mismatches=int(np.sum(ort_label.flatten()!=pred))
    if max_difference>0.0002 or label_mismatches>1:
        raise RuntimeError("F26_RICE_ONNX_NOT_EQUIVALENT_TO_FITTED_ESTIMATOR")
    norm_x=scaler.transform(x[test_idx]).astype("float32")
    # Baseline and model evaluated on same untouched test indices.
    if not np.all(np.isfinite(norm_x)):
        raise RuntimeError("F26_RICE_INVALID_NORMALIZATION")
    counts=confusion_matrix(y[test_idx],pred,labels=[0,1]).tolist()
    metrics={
      "dataset_raw_count":len(rows),"deduplicated_count":len(items),
      "exact_feature_duplicates_removed":dups,
      "train_rows":len(train_idx),"validation_rows":len(val_idx),
      "heldout_rows":len(test_idx),
      "train_only_scaler_fitted":True,
      "disjoint_train_validation_test":True,
      "stratified_holdout":True,
      "validation_accuracy":valid_accuracy,
      "heldout_accuracy":acc,
      "heldout_balanced_accuracy":balanced,
      "heldout_f1_positive_osmancik":f1,
      "heldout_majority_baseline_accuracy":baseline_accuracy,
      "heldout_confusion_matrix_cam_osm":counts,
      "heldout_onnx_runtime_prediction_count":len(test_idx),
      "max_onnx_vs_sklearn_probability_error":max_difference,
      "onnx_vs_sklearn_label_mismatch_count":label_mismatches
    }
    card={
        "schema":SCHEMA,
        "family":"F26",
        "product":"Rice grain cultivar classifier — public research data pilot",
        "version_status":"technical_research_candidate_not_commercial",
        "dataset":{"name":DATASET,"doi":DOI,"download_url":SOURCE,
                   "download_archive_sha256":archive_sha,
                   "license":"Creative Commons Attribution 4.0 International (CC BY 4.0)",
                   "origin":"real rice grain images, 7 pre-extracted morphological measurements",
                   "source_citation":"Cinar, Ilkay and Koklu, M. Rice (Cammeo and Osmancik). UCI Machine Learning Repository (2019), DOI:10.24432/C5MW4Z"},
        "target_classes":list(CLASSES),
        "input_features":list(FIELDS),
        "feature_extraction_from_raw_images_included":False,
        "geographic_scope":"original Turkish cultivar samples; out-of-distribution untested",
        "research_only":True,
        "not_for_use_as_crop_yield_or_food_safety_tool":True,
        "independent_specialist_approval":False,
        "independent_field_validation":False,
        "bias_and_domain_shift_audit":False,
        "human_identity_or_rights_review_completed":False,
        "quality_1000_certified":False,
        "commercial_release_authorized":False,
        "onnx_model_sha256":digest(model_path.read_bytes()),
        "metrics":metrics
    }
    (out/"model_card.json").write_bytes(canonical(card))
    notice=("RESEARCH PILOT ONLY. NO COMMERCIAL RELEASE OR QUALITY 1000.\n"
      "Dataset: Rice (Cammeo and Osmancik), UCI ML Repository (2019), "
      "https://doi.org/10.24432/C5MW4Z\n"
      "Dataset license: CC BY 4.0. Attribution: Ilkay Cinar, M. Koklu. "
      "Source: "+SOURCE+"\n"
      "Model derived from published morphological features. "
      "Not an image classifier, field-validated agronomy tool, "
      "or safety-critical inference system.\n")
    (out/"ATTRIBUTION_AND_LIMITS.txt").write_text(notice,encoding="utf8")
    outputs={p.name:digest(p.read_bytes()) for p in out.iterdir() if p.is_file()}
    receipt={"schema":SCHEMA+".artifact-manifest",
             "family_id":"F26",
             "source_archive_sha256":archive_sha,
             "dataset_license":"CC BY 4.0",
             "artifact_sha256":outputs,
             "holdout_data_real_and_not_synthetic":True,
             "source_verified_by_pinned_sha256":True,
             "independent_external_data_validation":False,
             "independent_specialist_approved":False,
             "quality_1000_certified":False,
             "commercial_release_authorized":False}
    (out/"manifest.json").write_bytes(canonical(receipt))
    print("F26_REAL_RICE_SHA256="+archive_sha)
    print("F26_REAL_RICE_MACHINE_HOLDOUT="+json.dumps(
       {"rows":len(rows),"train":len(train_idx),"validation":len(val_idx),
        "holdout":len(test_idx),"accuracy":round(acc,5),
        "balanced":round(balanced,5),"baseline":round(baseline_accuracy,5),
        "onnx_mismatches":label_mismatches,
        "commercial_release":False},sort_keys=True))
    return receipt

def verify(folder):
    import onnx
    root=Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("F26_RICE_INVALID_VERIFY_FOLDER")
    manifest=json.loads((root/"manifest.json").read_text("utf8"))
    if manifest.get("schema")!=SCHEMA+".artifact-manifest":
        raise RuntimeError("F26_RICE_WRONG_MANIFEST")
    files=manifest.get("artifact_sha256")
    if not isinstance(files,dict) or set(files)!={
        "rice_cultivar_real_pilot.onnx","model_card.json","ATTRIBUTION_AND_LIMITS.txt"}:
        raise RuntimeError("F26_RICE_UNEXPECTED_ARTIFACTS")
    for name,hashval in files.items():
        path=root/name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes())!=hashval:
            raise RuntimeError("F26_RICE_REPRODUCIBILITY_HASH_FAIL")
    card=json.loads((root/"model_card.json").read_text())
    if (card.get("family")!="F26" or card.get("quality_1000_certified") is not False
        or card.get("commercial_release_authorized") is not False
        or card.get("dataset",{}).get("download_archive_sha256")!=manifest["source_archive_sha256"]
        or card.get("onnx_model_sha256")!=files["rice_cultivar_real_pilot.onnx"]
        or not card.get("metrics",{}).get("heldout_onnx_runtime_prediction_count")):
        raise RuntimeError("F26_RICE_CARD_PROVENANCE_OR_POLICY_INVALID")
    onnx.checker.check_model(onnx.load(str(root/"rice_cultivar_real_pilot.onnx")))
    print("F26_REAL_RICE_INDEPENDENT_ARTIFACT_VERIFICATION=PASS")
    return True

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive")
    p.add_argument("--expected-archive-sha256")
    p.add_argument("--out")
    p.add_argument("--verify")
    a=p.parse_args()
    if a.verify:
        if a.archive or a.out or a.expected_archive_sha256:
            p.error("verify is read-only and cannot also train")
        verify(a.verify)
    elif a.archive and a.out and a.expected_archive_sha256:
        train(Path(a.archive),Path(a.out),a.expected_archive_sha256)
        verify(a.out)
    else:
        p.error("train requires pinned --archive, --expected-archive-sha256, --out")

if __name__=="__main__":
    main()
