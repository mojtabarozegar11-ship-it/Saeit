#!/usr/bin/env python3
"""F26 private dependency-free rice inference.

Export extracts precise ONNX float32 parameters, compares against all 762
genuine heldout ONNXRuntime predictions in CI, and writes a bound spec.
Run uses only Python standard library on the VPS. NO specialist certification.
"""
import argparse,hashlib,importlib.util,json,math
from pathlib import Path

SCHEMA="saeit.factory.f26.real-rice-portable-inference.v1"
OPS=("Sub","Div","MatMul","Add","Sigmoid","Greater","Cast")
HERE=Path(__file__).resolve().parent

def dependency(name):
    path=HERE/name
    if path.is_symlink() or not path.is_file():
        raise ValueError("F26_PORTABLE_DEPENDENCY_MISSING")
    spec=importlib.util.spec_from_file_location("f26_helper_"+name.replace(".","_"),str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def filehash(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>16_000_000:
        raise ValueError("F26_PORTABLE_FILE_UNSAFE")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def logistic(logit):
    if not math.isfinite(logit):
        raise ValueError("F26_PORTABLE_LOGIT_NOT_FINITE")
    if logit>=0: return 1/(1+math.exp(-logit))
    x=math.exp(logit)
    return x/(1+x)

def formula(row,p):
    score=p["bias"]
    for x,m,s,w in zip(row,p["mean"],p["scale"],p["weights"]):
        score+=((float(x)-m)/s)*w
    prob=logistic(score)
    return prob,int(prob>0.5)

def validate(spec,model_dir):
    cli=dependency("factory_f26_real_rice_cli.py")
    card=cli.verify_model(Path(model_dir))
    if (spec.get("schema")!=SCHEMA or spec.get("family_id")!="F26"
        or spec.get("model_sha256")!=card.get("onnx_model_sha256")
        or spec.get("dataset_sha256")!=card["dataset"]["download_archive_sha256"]
        or tuple(spec.get("feature_names",[]))!=cli.FIELDS
        or tuple(spec.get("classes",[]))!=cli.NAMES
        or spec.get("operators")!=list(OPS)
        or spec.get("research_only") is not True
        or spec.get("quality_1000_certified") is not False
        or spec.get("independent_field_validated") is not False
        or spec.get("commercial_release_authorized") is not False
        or spec.get("holdout_onnx_comparison_rows")!=card["metrics"]["heldout_rows"]
        or spec.get("holdout_label_mismatches")!=0
        or not isinstance(spec.get("max_probability_difference"),(float,int))
        or spec["max_probability_difference"]>0.0002):
        raise ValueError("F26_PORTABLE_UNTRUSTED_ONNX_PROVENANCE")
    p=spec.get("float32_coefficients",{})
    if (not isinstance(p,dict) or set(p)!={"mean","scale","weights","bias","threshold"}
        or len(p["mean"])!=7 or len(p["scale"])!=7 or len(p["weights"])!=7
        or p["threshold"]!=0.5 or type(p["bias"]) not in (int,float)
        or not math.isfinite(p["bias"])):
        raise ValueError("F26_PORTABLE_PARAMETER_SHAPE_INVALID")
    for key in ("mean","scale","weights"):
        if any(type(x) not in (float,int) or not math.isfinite(x)
               for x in p[key]):
            raise ValueError("F26_PORTABLE_PARAMETER_NOT_FINITE")
    if any(x<=0 for x in p["scale"]):
        raise ValueError("F26_PORTABLE_BAD_NORMALIZATION")
    return p

def export(model_dir,source_archive,out):
    import numpy as np,onnx,onnxruntime as ort
    from onnx import numpy_helper
    cli=dependency("factory_f26_real_rice_cli.py")
    card=cli.verify_model(Path(model_dir))
    model_path=Path(model_dir)/"rice_cultivar_real_pilot.onnx"
    model=onnx.load(str(model_path))
    onnx.checker.check_model(model)
    if (tuple(node.op_type for node in model.graph.node)!=OPS
        or len(model.graph.input)!=1 or model.graph.input[0].name!="input"
        or tuple(output.name for output in model.graph.output)!=("probability","class_index")):
        raise ValueError("F26_PORTABLE_UNEXPECTED_ONNX_GRAPH")
    tensors={item.name:np.asarray(numpy_helper.to_array(item),dtype=np.float32)
             for item in model.graph.initializer}
    if (set(tensors)!={"mean","scale","weights","bias","threshold"}
        or tensors["mean"].shape!=(7,) or tensors["scale"].shape!=(7,)
        or tensors["weights"].shape!=(7,1) or tensors["bias"].shape!=(1,)
        or tensors["threshold"].shape!=(1,) or float(tensors["threshold"][0])!=0.5):
        raise ValueError("F26_PORTABLE_ONNX_INIT_SHAPE_MISMATCH")
    p={name:tensors[name].flatten().astype(float).tolist()
       for name in ("mean","scale","weights")}
    p["bias"]=float(tensors["bias"][0])
    p["threshold"]=0.5
    pilot=dependency("factory_f26_real_rice_research_pilot.py")
    raw,source_sha=pilot.read_archive(Path(source_archive),card["dataset"]["download_archive_sha256"])
    rows,labels=pilot.parse_arff(raw)
    items,(_,_,test),_=pilot.split_unique(rows,labels)
    examples=[items[i][0] for i in test]
    if len(examples)!=762:
        raise ValueError("F26_PORTABLE_NOT_SAME_HOLDOUT")
    session=ort.InferenceSession(str(model_path),providers=["CPUExecutionProvider"])
    probabilities,classes=session.run(None,{"input":np.asarray(examples,dtype=np.float32)})
    errs=[]
    disagreements=0
    for row,original,label in zip(examples,probabilities.reshape(-1),classes.reshape(-1)):
        probability,pred=formula(row,p)
        errs.append(abs(probability-float(original)))
        disagreements+=int(pred!=int(label))
    if disagreements!=0 or max(errs)>0.0002:
        raise ValueError("F26_PORTABLE_ORIGINAL_ONNX_REPRODUCTION_FAILED")
    spec={
        "schema":SCHEMA,"family_id":"F26",
        "model_sha256":card["onnx_model_sha256"],
        "dataset_sha256":source_sha,
        "feature_names":list(cli.FIELDS),"classes":list(cli.NAMES),
        "operators":list(OPS),
        "float32_coefficients":p,
        "holdout_onnx_comparison_rows":len(examples),
        "holdout_label_mismatches":disagreements,
        "max_probability_difference":max(errs),
        "research_only":True,"quality_1000_certified":False,
        "independent_field_validated":False,
        "commercial_release_authorized":False
    }
    validate(spec,model_dir)
    dest=Path(out)
    if dest.exists() or dest.is_symlink():
        raise ValueError("F26_PORTABLE_SPEC_ALREADY_EXISTS")
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(spec,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    print("F26_PORTABLE_ONNX_INFERENCE_EQUIVALENCE=PASS")
    print("F26_PORTABLE_HELDOUT_SAMPLES="+str(len(examples)))
    print("F26_PORTABLE_SPEC_SHA256="+filehash(dest))

def predict(model_dir,spec_path,rows):
    spec_path=Path(spec_path)
    if spec_path.is_symlink() or not spec_path.is_file() or spec_path.stat().st_size>50000:
        raise ValueError("F26_PORTABLE_SPEC_UNSAFE")
    spec=json.loads(spec_path.read_text("utf8"))
    p=validate(spec,model_dir)
    cli=dependency("factory_f26_real_rice_cli.py")
    predictions=[]
    for i,row in enumerate(rows):
        measured=cli.numbers(row)
        prob,label=formula(measured,p)
        predictions.append({
            "index":i+1,"predicted_cultivar":cli.NAMES[label],
            "model_probability_osmancik":round(prob,7),
            "measurements":dict(zip(cli.FIELDS,measured)),
            "field_validated":False
        })
    return {
        "schema":SCHEMA+".offline-result",
        "source_onnx_sha256":spec["model_sha256"],
        "source_dataset_sha256":spec["dataset_sha256"],
        "count":len(predictions),
        "backend":"Python standard library from verified ONNX coefficients",
        "field_validated":False,"quality_1000_certified":False,
        "commercial_release_authorized":False,
        "predictions":predictions
    }

def main():
    p=argparse.ArgumentParser()
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--export",action="store_true")
    modes.add_argument("--predict",action="store_true")
    p.add_argument("--model-dir",required=True)
    p.add_argument("--source-archive")
    p.add_argument("--runtime-spec")
    choices=p.add_mutually_exclusive_group()
    choices.add_argument("--features",nargs=7)
    choices.add_argument("--csv")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:
        if a.export:
            if not a.source_archive or a.runtime_spec or a.features or a.csv:
                raise ValueError("F26_PORTABLE_EXPORT_NEEDS_ORIGINAL_UCI")
            export(a.model_dir,a.source_archive,a.out)
        else:
            if not a.runtime_spec or a.source_archive or (a.features is None and not a.csv):
                raise ValueError("F26_PORTABLE_INFERENCE_ARGS_INVALID")
            cli=dependency("factory_f26_real_rice_cli.py")
            examples=cli.read_cases(a)
            result=predict(a.model_dir,a.runtime_spec,examples)
            dest=Path(a.out)
            if dest.is_symlink() or dest.exists():
                raise ValueError("F26_PORTABLE_OUTPUT_ALREADY_EXISTS")
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open("x",encoding="utf8") as f:
                json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
                f.write("\n")
            print("F26_PORTABLE_PRIVATE_INFERENCE=PASS")
            print("F26_PORTABLE_INFERENCE_ROWS="+str(result["count"]))
    except (ValueError,KeyError,TypeError,OSError,ImportError) as exc:
        p.exit(2,"F26_PORTABLE_DENIED: "+str(exc)+"\n")

if __name__=="__main__":
    main()
