#!/usr/bin/env python3
"""Live evidence-gated engineering compiler for all 40 production families.

Builds 48 distinct executable acceptance *contracts* per family, validates
real artifact signatures and digest/provenance in a private workspace, and
recounts genuine BUILD50 proofs. A contract is not a native manufacturer.
No network, payment, automatic approval, source deletion or public release.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

SCHEMA="saeit.factory.family-engineering-gates.v1"
HEX=re.compile(r"^[a-f0-9]{64}$")
FAMILY=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
EXTS={
 "PDF":(".pdf",), "EPUB":(".epub",), "HTML":(".html",".htm"),"DOCX":(".docx",),
 "XLSX":(".xlsx",),"XLS":(".xls",),"PPTX":(".pptx",),"JSON":(".json",),
 "CSV":(".csv",),"PARQUET":(".parquet",),"PNG":(".png",),"SVG":(".svg",),
 "GIF":(".gif",),"JPG":(".jpg",".jpeg"),"GLB":(".glb",),"OBJ":(".obj",),
 "WAV":(".wav",),"MP3":(".mp3",),"MP4":(".mp4",),"VTT":(".vtt",),
 "ZIP":(".zip",),"PY":(".py",),"JS":(".js",),"CSS":(".css",),
 "MD":(".md",),"XML":(".xml",),"ODT":(".odt",),"ODS":(".ods",),"ODP":(".odp",),
 "APPIMAGE":(".appimage",),"APK":(".apk",),"AAB":(".aab",),
 "EXE":(".exe",),"ONNX":(".onnx",),"PTH":(".pth",),"EXR":(".exr",),
 "STEP":(".step",".stp")
}
def require(ok,code):
    if not ok:raise ValueError("ENGINEERING_"+code)
def load(name,path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink(),"TRUSTED_CODE_MISSING")
    spec=importlib.util.spec_from_file_location(name,str(path))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(65536),b""):h.update(part)
    return h.hexdigest()
def json_bytes(x):
    return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n").encode("utf8")
def read_json(path,limit=2000000):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,"SOURCE_UNTRUSTED")
    v=json.loads(p.read_text("utf8"))
    require(isinstance(v,dict),"SOURCE_NOT_OBJECT")
    return v
def atomic(path,value):
    path=Path(path)
    require(not path.parent.is_symlink() and not path.is_symlink(),"SYMLINK_DEST")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    raw=json_bytes(value)
    fd,tmp=tempfile.mkstemp(prefix=".eng-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def expected_formats(profile):
    formats=profile.get("formats",[])
    require(isinstance(formats,list) and len(formats)>=1,"FORMATS")
    require(all(isinstance(x,str) and x in EXTS for x in formats),"UNHANDLED_FORMAT")
    return formats
def contract(profile,routes):
    fid=profile["id"]
    require(FAMILY.fullmatch(fid) is not None,"BAD_FAMILY")
    parts=routes.ROUTES[fid];phases=routes.PHASES
    require(len(parts)==8 and len(phases)==6,"ROUTE_STRUCTURE")
    tasks=[]
    for i,part in enumerate(parts):
        for phase,verb in phases:
            tasks.append({"id":"unit%02d_%s"%(i+1,phase),
                "component":part,"stage":phase,"instructions":verb+" "+part+" for "+profile["name_fa"]+
                    ". Check actual measured output; retain real input and independent reviewer evidence.",
                "status":"unexecuted","evidence_sha256":None})
    require(len(tasks)==48 and len({x["id"] for x in tasks})==48,"FORTY_EIGHT_DISTINCT")
    required=routes.INPUTS[fid]
    require(isinstance(required,list) and len(required)>0,"INPUTS_NOT_DECLARED")
    return {"schema":"saeit.factory.production-engineering-contract.v1",
       "family_id":fid,"family_slug":profile["slug"],"producer_adapter":profile["producer_adapter"],
       "formats":expected_formats(profile),"required_external_inputs":required,
       "specialist_tests":profile["specialist_tests"],
       "work_packages":tasks,"completed_work_packages":0,
       "native_maker_installed_by_contract":False,
       "commercial_release":False,"owner_approval":False}
def validate_file(path,format_name):
    """Format validator: strict header + parse where stdlib supports.
    This is structural triage, never a security scan or content-quality approval.
    """
    path=Path(path);fmt=format_name.upper()
    require(fmt in EXTS and path.suffix.lower() in EXTS[fmt],"FORMAT_EXTENSION")
    require(path.is_file() and not path.is_symlink() and 1<=path.stat().st_size<=100000000,"FORMAT_FILE")
    with path.open("rb") as f:head=f.read(64)
    signatures={"PDF":b"%PDF-","PNG":b"\x89PNG\r\n\x1a\n","GIF":b"GIF8",
        "WAV":b"RIFF","MP3":b"ID3","MP4":b"","GLB":b"glTF",
        "PARQUET":b"PAR1","EXR":b"\x76\x2f\x31\x01","APPIMAGE":b"\x7fELF",
        "EXE":b"MZ","ONNX":b"","PTH":b""}
    if fmt in signatures and signatures[fmt]:
        require(head.startswith(signatures[fmt]),"FORMAT_SIGNATURE")
    if fmt=="WAV":require(head[8:12]==b"WAVE","WAV_HEADER")
    if fmt=="MP4":require(head[4:8]==b"ftyp","MP4_HEADER")
    if fmt in ("APK","AAB","DOCX","XLSX","PPTX","EPUB","ODT","ODS","ODP","ZIP"):
        require(zipfile.is_zipfile(path),"ZIP_SIGNATURE")
        with zipfile.ZipFile(path) as archive:
            items=archive.infolist()
            require(0<len(items)<=2000 and sum(z.file_size for z in items)<=250000000,"ZIP_UNBOUNDED")
            require(all(not z.filename.startswith("/") and ".." not in Path(z.filename).parts for z in items),"ZIP_UNSAFE_MEMBER")
            require(archive.testzip() is None,"ZIP_CRC")
            names=set(archive.namelist())
            for name,required in (("DOCX","word/document.xml"),("XLSX","xl/workbook.xml"),
                                   ("PPTX","ppt/presentation.xml"),("EPUB","META-INF/container.xml")):
                if fmt==name:require(required in names,"ZIP_MISSING_INTERNAL_DOCUMENT")
    if fmt=="SVG":
        from xml.etree import ElementTree as ET
        require(path.stat().st_size<=2000000,"SVG_SIZE")
        elem=ET.parse(str(path)).getroot()
        require(elem.tag.endswith("}svg") or elem.tag=="svg","SVG_ROOT")
        require(all("script" not in node.tag.lower() and "foreignobject" not in node.tag.lower()
                  for node in elem.iter()),"SVG_SCRIPT_DISALLOWED")
    if fmt=="JSON":json.loads(path.read_text("utf8"))
    if fmt in ("HTML","VTT","PY","JS","CSS","MD","OBJ","CSV","XML"):
        require(path.stat().st_size<=5000000,"TEXT_SIZE")
        text=path.read_text("utf8")
        require(bool(text.strip()),"EMPTY_TEXT")
        if fmt=="VTT":require(text.startswith("WEBVTT"),"VTT_HEADER")
    return {"sha256":sha(path),"bytes":path.stat().st_size,"format":fmt,
            "structurally_parseable":True,"semantic_or_legal_approval":False}
def validate_manifest(family,manifest_path,artifact_root):
    doc=read_json(manifest_path)
    require(doc.get("family_id")==family and isinstance(doc.get("outputs"),list),"MANIFEST_SCHEMA")
    require(len(doc["outputs"])>=1 and len(doc["outputs"])<=100,"MANIFEST_COUNT")
    root=Path(artifact_root).resolve();rows=[]
    for row in doc["outputs"]:
        require(isinstance(row,dict) and set(row)=={"path","format","sha256"},"MANIFEST_ROW")
        name=row["path"];require(isinstance(name,str) and not Path(name).is_absolute() and
            ".." not in Path(name).parts and "\\" not in name and name,"MANIFEST_PATH")
        p=root/name
        require(p.resolve().is_relative_to(root) if hasattr(p.resolve(),"is_relative_to") else str(p.resolve()).startswith(str(root)+os.sep),"MANIFEST_ESCAPE")
        checked=validate_file(p,row["format"])
        require(HEX.fullmatch(str(row["sha256"])) is not None and checked["sha256"]==row["sha256"],"MANIFEST_HASH_MISMATCH")
        rows.append({"path":name,**checked})
    return {"family_id":family,"checked":len(rows),"files":rows,"native_maker_approved":False}
def run(root,ops,registry,module_dir):
    root=Path(root);ops=Path(ops);module_dir=Path(module_dir)
    require(root.is_dir() and not root.is_symlink() and ops.is_dir(),"PRIVATE_ROOT")
    source=read_json(registry)
    routes=load("factory_gap_routes",module_dir/"factory_product_routes.py")
    bridge=load("factory_gap_bridge",module_dir/"factory_build50_family_bridge.py")
    proto=load("factory_gap_build_protocol",module_dir/"factory_build_50.py")
    master=load("factory_gap_master",module_dir/"factory_40_family_master.py")
    profiles=master.registry_valid(source)
    ledger=bridge.inventory(root,registry,proto,master)
    evid={r["family_id"]:r for r in ledger["families"]}
    folder=root/"engineering-gaps";folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    status=[]
    for p in profiles:
        fid=p["id"];proof=evid[fid]
        spec=contract(p,routes)
        # Do not re-write stable contracts each five-minute cycle.
        dest=folder/fid/"contract.json"
        if not dest.is_file() or read_json(dest)!=spec:atomic(dest,spec)
        verified=proof["technical_50_stage_completed"]
        pilots=proof["technical_pilot_count"]
        status.append({"family_id":fid,"technical_50stage_products":verified,
          "verified_pilot_count":pilots,"native_producer_ready_for_all_custom_orders":False,
          "stage":"specific_technical_product_proven" if verified else
           "technical_pilot_only" if pilots else "unverified_or_blocked",
          "input_requirements":routes.INPUTS[fid],"output_formats":spec["formats"],
          "custom_builder_implemented_by_this_release":False,
          "contract_sha256":sha(dest)})
    missing=[x["family_id"] for x in status if x["technical_50stage_products"]==0]
    result={"schema":SCHEMA,"updated_utc":datetime.now(timezone.utc).isoformat(),
      "registered_families":len(status),"technical_product_families":40-len(missing),
      "families_without_50stage_proof":missing,
      "family_contracts_compiled":len(status),
      "technical_pilot_only_families":sum(x["stage"]=="technical_pilot_only" for x in status),
      "code_generator_is_native_manufacturer":False,
      "production_gaps_are_resolved":not missing,
      "role_specific_live_workers_proven":False,
      "commercial_products_approved":0,
      "products_manufactured_by_compiler":0,
      "rows":status}
    atomic(folder/"dashboard.json",result)
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    ap.add_argument("--ops",required=True)
    ap.add_argument("--registry",required=True)
    ap.add_argument("--module-dir",required=True)
    a=ap.parse_args()
    v=run(a.factory_private,a.ops,a.registry,a.module_dir)
    print("FACTORY_40_ENGINEERING_GATES="+json.dumps({k:v[k] for k in
      ("registered_families","technical_product_families","family_contracts_compiled",
       "technical_pilot_only_families","families_without_50stage_proof",
       "production_gaps_are_resolved")},sort_keys=True))
if __name__=="__main__":
    try:main()
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as exc:
        print("ENGINEERING_GATES_ERROR="+type(exc).__name__+":"+str(exc)[:200],file=sys.stderr)
        sys.exit(1)
