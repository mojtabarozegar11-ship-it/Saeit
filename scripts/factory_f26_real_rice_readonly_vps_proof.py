#!/usr/bin/env python3
"""Read-only independent private VPS F26 research-artifact acceptance proof."""
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import zipfile

SHA=re.compile(r"[a-f0-9]{64}")
RUN=re.compile(r"[0-9]{5,18}-[0-9]{1,3}")
FILES={"rice_cultivar_real_pilot.onnx","model_card.json",
       "ATTRIBUTION_AND_LIMITS.txt","manifest.json"}

def sha(b):
    return hashlib.sha256(b).hexdigest()

def filebytes(path,limit=15_000_000):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:
        raise RuntimeError("F26_READONLY_FILE_MISSING_OR_UNSAFE")
    return path.read_bytes()

def verify(root):
    root=Path(root)
    area=root/"f26-real-data-research"
    if root.is_symlink() or not root.is_dir() or area.is_symlink() or not area.is_dir():
        raise RuntimeError("F26_READONLY_PRIVATE_AREA_MISSING")
    dirs=[p for p in area.iterdir() if p.is_dir() and not p.is_symlink() and RUN.fullmatch(p.name)]
    if not dirs:
        raise RuntimeError("F26_READONLY_NO_INSTALLED_REAL_RICE_PILOT")
    version=max(dirs,key=lambda p:tuple(map(int,p.name.split("-"))))
    data=json.loads(filebytes(version/"private-f26-real-data-receipt.json",100_000))
    manifest=json.loads(filebytes(version/"manifest.json",100_000))
    card=json.loads(filebytes(version/"model_card.json",100_000))
    members=manifest.get("artifact_sha256")
    if not isinstance(members,dict) or set(members)!=FILES-{"manifest.json"}:
        raise RuntimeError("F26_READONLY_WRONG_FILES")
    actual={name:sha(filebytes(version/name)) for name in members}
    if actual!=members:
        raise RuntimeError("F26_READONLY_MODEL_CARD_OR_LICENSE_TAMPERED")
    if (data.get("schema")!="saeit.factory.f26.real-rice-research-pilot.v1.vps-admission"
        or data.get("run_id")!=version.name
        or data.get("model_card_sha256")!=actual["model_card.json"]
        or data.get("research_model_sha256")!=actual["rice_cultivar_real_pilot.onnx"]
        or data.get("uci_public_archive_sha256")!="fe94e42046b829de21b92b0ffb6a22774fde021328cae799faa802a14e8dbed9"
        or data.get("real_world_rice_rows")!=3810
        or data.get("untouched_heldout_rows")<500
        or data.get("previous_f26_native_48_models_preserved") is not True
        or data.get("professional_quality_1000_certified") is not False
        or data.get("physical_grain_camera_tested") is not False
        or data.get("rights_reviewer_signature_present") is not False
        or data.get("commercial_release_allowed") is not False
        or data.get("website_changes")!=0
        or card.get("research_only") is not True
        or card.get("independent_specialist_approval") is not False
        or card.get("commercial_release_authorized") is not False
        or card.get("quality_1000_certified") is not False
        or card.get("dataset",{}).get("license")!="Creative Commons Attribution 4.0 International (CC BY 4.0)"
        or card.get("onnx_model_sha256")!=actual["rice_cultivar_real_pilot.onnx"]
        or manifest.get("source_archive_sha256")!=data["uci_public_archive_sha256"]
        or not isinstance(card.get("metrics",{}).get("heldout_accuracy"),float)
        or card["metrics"]["heldout_accuracy"]<0.82):
        raise RuntimeError("F26_READONLY_REAL_DATA_EVIDENCE_OR_RELEASE_GATE_FAIL")
    tarblob=filebytes(version/"f26-research.tar")
    if sha(tarblob)!=data.get("uploaded_bundle_sha256"):
        raise RuntimeError("F26_READONLY_ORIGINAL_TAR_SHA_MISMATCH")
    with tarfile.open(fileobj=io.BytesIO(tarblob),mode="r:") as tar:
        info=tar.getmembers()
        if set(i.name for i in info)!=FILES or len(info)!=4 or any(not i.isfile() for i in info):
            raise RuntimeError("F26_READONLY_ORIGINAL_TAR_STRUCTURE_MISMATCH")
        for member in info:
            if tar.extractfile(member).read()!=filebytes(version/member.name):
                raise RuntimeError("F26_READONLY_ORIGINAL_TAR_BYTE_MISMATCH")
    native_run=data.get("prior_native_source_run")
    if not isinstance(native_run,str) or not RUN.fullmatch(native_run):
        raise RuntimeError("F26_READONLY_ORIGINAL_SOURCE_ID_INVALID")
    original=root/"native-candidate-evidence"/native_run
    aggregate=json.loads(filebytes(original/"verified-six-private-native.json",200_000))
    qa_bytes=filebytes(root/"quality-excellence"/"six-native-rework"/native_run/"review.json",200_000)
    qa=json.loads(qa_bytes)
    f26=next(i for i in aggregate.get("files",[]) if i.get("family")=="F26")
    if (aggregate.get("six_families_verified")!=6
        or aggregate.get("candidate_native_file_count")!=56
        or aggregate.get("private_only") is not True
        or aggregate.get("production_release_authorized") is not False
        or f26.get("verified_on_vps") is not True
        or f26.get("native_candidate_files")!=48
        or f26.get("archive_sha256")!=data.get("prior_native_f26_archive_sha256")
        or qa.get("completed_professional_quality_1000_certifications")!=0
        or sha(qa_bytes)!=data.get("prior_native_qa_review_sha256")):
        raise RuntimeError("F26_READONLY_ORIGINAL_48_MODELS_CHAIN_BROKEN")
    bundle=original/"F26"/"technical-native-candidate.zip"
    raw=filebytes(bundle,220_000_000)
    if sha(raw)!=f26["archive_sha256"]:
        raise RuntimeError("F26_READONLY_ORIGINAL_MODEL_BUNDLE_TAMPERED")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len([n for n in archive.namelist() if n.endswith(".onnx")])!=48 or archive.testzip() is not None:
            raise RuntimeError("F26_READONLY_ORIGINAL_48_ONNX_MODELS_MISSING")
    print("FACTORY_F26_REAL_RICE_VPS_INDEPENDENT_READONLY=PASS")
    print("FACTORY_F26_REAL_RICE_UNTOUCHED_HELDOUT="+str(data["untouched_heldout_rows"]))
    print("FACTORY_F26_REAL_RICE_MODEL_SHA256="+actual["rice_cultivar_real_pilot.onnx"])
    print("FACTORY_F26_REAL_RICE_VPS_RECEIPT_SHA256="+sha(filebytes(version/"private-f26-real-data-receipt.json",100_000)))
    print("FACTORY_F26_REAL_RICE_PREVIOUS_48_ONNX=VERIFIED_UNCHANGED")
    print("FACTORY_F26_REAL_RICE_EXPERT_OR_FIELD_QA=UNVERIFIED")
    print("FACTORY_F26_REAL_RICE_PUBLIC_SITES_MUTATED=0")
    print("FACTORY_F26_REAL_RICE_QUALITY_1000_CLAIM=0")

if __name__=="__main__":
    verify(Path.home()/"factory-runtime"/"private"/"autonomous-product-cycle")
