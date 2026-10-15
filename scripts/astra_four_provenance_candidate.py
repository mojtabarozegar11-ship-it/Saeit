#!/usr/bin/env python3
"""Private provenance and copyright packaging for four owner-attested Astra ZIPs.

This is a reproducible QA candidate, NOT a public product or legal clearance.
No website, database, invoice, payment, factory queue, or original ZIP changes.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

from astra_mpw_four_draft_import import verify_store_bundle

PREFIX = "ASTRA-"
DIST_DIR = "commercial-review-v2"
SAFE_EXTENSIONS = frozenset({".py",".js",".html",".css",".json",".md",".txt"})
PY_LOCAL = frozenset({"decision_audit","water_margin_audit",
                      "procurement_audit","render_report"})
NODE_BUILTINS = frozenset({"assert","node:assert","fs","node:fs","path","node:path",
                           "vm","node:vm","url","node:url"})
NAME_RX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,130}$")
REMOTE_RX = re.compile(
    r"(?:https?://|//)[A-Za-z0-9.-]+|(?:@import\s*|src=|href=)",re.IGNORECASE
)
JS_IMPORT_RX = re.compile(r"(?:require\s*\(\s*['\"]([^'\"]+)['\"]|"
                          r"\bimport\s+[^;]*?\sfrom\s+['\"]([^'\"]+)['\"])")
INSECURE_RX = re.compile(r"(?<![\w])(?:eval|exec)\s*\(")

OWNER_NOTICE = (
    "ASTRA SPECIALIST PRODUCT — COPYRIGHT AND RIGHTS STATEMENT\n"
    "Copyright (c) 2026 Mojtaba Rozegar. All rights reserved.\n\n"
    "The owner declared 100% exclusive ownership on 2026-10-15. "
    "This is an owner declaration, not independent legal verification.\n"
    "No sale, resale, redistribution, sublicensing or source-sharing rights "
    "are granted by this notice. A future customer license must specify "
    "the rights granted on a completed purchase before commercial release.\n"
    "Dependencies, embedded materials, and applicable third-party rights "
    "require separate review; this notice does not override such rights.\n"
)
SUPPLEMENT = (
    "ASTRA CANDIDATE EDITION — NOT FOR SALE\n"
    "This is a privately staged product candidate for technical and legal review.\n"
    "The existing source package is included unchanged, byte for byte.\n"
    "Proposed prices are not validated market value. Example files are synthetic.\n"
    "Before any customer payment: complete independent usability/accessibility, "
    "third-party/license clearance, commercial terms and refund policy, "
    "factory release approval, and a real verified crypto payment-to-download test.\n"
)


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def audit_zip(path, expected_sha):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>25_000_000:
        raise ValueError("Original package missing or unsafe")
    if hash_bytes(path.read_bytes())!=expected_sha:
        raise ValueError("Original SHA-256 mismatch")
    files={}
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if not 3<=len(infos)<=40 or archive.testzip() is not None:
            raise ValueError("Missing, corrupt or suspicious ZIP entries")
        roots=set()
        for info in infos:
            parts=PurePosixPath(info.filename).parts
            if (info.is_dir() or len(parts)!=2 or any(p in ("","..",".") for p in parts)
                    or any(not NAME_RX.fullmatch(p) for p in parts)
                    or info.flag_bits&1 or (info.external_attr>>16)&0o170000==stat.S_IFLNK
                    or info.file_size>2_000_000
                    or PurePosixPath(info.filename).suffix.lower() not in SAFE_EXTENSIONS):
                raise ValueError("Unsafe source entry "+info.filename)
            roots.add(parts[0])
            if info.filename in files:
                raise ValueError("Duplicate source ZIP member")
            files[info.filename]=archive.read(info)
        if len(roots)!=1 or sum(map(len,files.values()))>7_000_000:
            raise ValueError("Invalid directory layout or zip bomb")
    return files, next(iter(roots))


def _runtime_dependency_evidence(files):
    findings=[]
    py_imports=set()
    js_imports=set()
    external_refs=[]
    exec_like=[]
    for name,body in sorted(files.items()):
        suffix=PurePosixPath(name).suffix.lower()
        if suffix not in (".py",".js",".html",".css"):
            continue
        content=body.decode("utf-8")
        if suffix==".py":
            tree=ast.parse(content, filename=name)
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    py_imports.update(n.name.split(".")[0] for n in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:
                    py_imports.add(node.module.split(".")[0])
            if INSECURE_RX.search(content):
                exec_like.append(name)
        elif suffix==".js":
            for match in JS_IMPORT_RX.finditer(content):
                js_imports.add(match.group(1) or match.group(2))
            if INSECURE_RX.search(content):
                exec_like.append(name)
        # Do not confuse quoted external research/competitor links in README
        # with requests made by packaged programs.
        for m in REMOTE_RX.finditer(content):
            matched=m.group(0).lower()
            if matched.startswith(("http://","https://","//","@import")):
                external_refs.append({"file":name,"indicator":matched[:100]})
    py_external=sorted(p for p in py_imports if p not in sys.stdlib_module_names
                       and p not in PY_LOCAL and p!="__future__")
    js_external=sorted(x for x in js_imports if x not in NODE_BUILTINS
                       and not x.startswith(("./","../")))
    for x in py_external:
        findings.append("Unresolved Python import: "+x)
    for x in js_external:
        findings.append("Unresolved JavaScript import: "+x)
    if external_refs:
        findings.append("Possible runtime network/CDN reference requires manual review")
    if exec_like:
        findings.append("Runtime dynamic evaluation requires manual review")
    return {
        "python_imports":sorted(py_imports),
        "unresolved_python_imports":py_external,
        "javascript_imports":sorted(js_imports),
        "unresolved_javascript_imports":js_external,
        "runtime_external_refs":external_refs,
        "dynamic_eval_files":sorted(exec_like),
        "static_scan_warnings":findings,
        "independent_license_review_complete":False,
        "independent_customer_usability_passed":False,
        "paid_release_authorized":False,
    }


def make_candidate(item, source):
    src_files,top=audit_zip(source,item["sha256"])
    evidence=_runtime_dependency_evidence(src_files)
    provenance={
        "schema":1,
        "sku":item["sku"],
        "original_sha256":item["sha256"],
        "original_file_count":len(src_files),
        "original_file_sha256":{n:hash_bytes(b) for n,b in sorted(src_files.items())},
        "owner_exclusive_rights_declared":True,
        "legal_verification_completed":False,
        "candidate_status":"PRIVATE_QA_NOT_FOR_SALE",
        "dependency_review":evidence,
    }
    additions={
        top+"/COPYRIGHT-OWNER-DECLARATION.txt":OWNER_NOTICE.encode("utf-8"),
        top+"/RELEASE-CANDIDATE-READ-ME.txt":SUPPLEMENT.encode("utf-8"),
        top+"/SOURCE-PROVENANCE.json":(json.dumps(provenance,indent=2,sort_keys=True)+"\n").encode(),
    }
    memory=io.BytesIO()
    with zipfile.ZipFile(memory,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for name,data in sorted({**src_files,**additions}.items()):
            if name in src_files and name in additions:
                raise ValueError("Supplement conflicts with source file")
            info=zipfile.ZipInfo(name,date_time=(2026,10,15,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o600<<16
            output.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    binary=memory.getvalue()
    with zipfile.ZipFile(io.BytesIO(binary)) as review:
        if review.testzip() is not None or set(review.namelist())!=set(src_files)|set(additions):
            raise ValueError("Commercial candidate verification failed")
        for name,data in src_files.items():
            if review.read(name)!=data:
                raise ValueError("Original source was modified")
    record={
        "sku":item["sku"],
        "original_sha256":item["sha256"],
        "candidate_sha256":hash_bytes(binary),
        "candidate_bytes":len(binary),
        "original_files_preserved":len(src_files),
        "supplemental_files":len(additions),
        "unresolved_dependencies":evidence["static_scan_warnings"],
        "release_ready":False,
        "checkout_enabled":False,
    }
    return binary,record


def store_unique(folder,name,data,*,apply):
    dest=folder/name
    if dest.is_symlink():
        raise ValueError("Unsafe output symlink")
    if dest.exists():
        if not dest.is_file() or hash_bytes(dest.read_bytes())!=hash_bytes(data):
            raise ValueError("Existing review candidate differs")
        return False
    if not apply:
        return False
    flags=os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW
    fd=os.open(dest,flags,0o600)
    with os.fdopen(fd,"wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    return True


def run(catalog,inbox,output,*,apply):
    entries=verify_store_bundle(catalog,inbox)
    folder=Path(output)
    source=Path(inbox)
    if (not folder.is_absolute() or folder.is_symlink() or
            not source.is_absolute() or source.is_symlink() or folder==source
            or source in folder.parents or folder in source.parents):
        raise ValueError("Review target must be a separate private directory")
    results=[]
    for item in entries:
        original=source/(item["sku"]+"-"+item["sha256"]+".zip")
        blob,summary=make_candidate(item,original)
        results.append((blob,summary))
    # Validate all four before creating/modifying any private output file.
    if apply:
        folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.chmod(folder,0o700)
    if not folder.is_dir() and not apply:
        pass
    elif folder.is_dir():
        for blob,summary in results:
            name=summary["sku"]+"-"+summary["candidate_sha256"]+".zip"
            if (folder/name).exists() and hash_bytes((folder/name).read_bytes())!=summary["candidate_sha256"]:
                raise ValueError("Commercial candidate conflict")
    for blob,summary in results:
        name=summary["sku"]+"-"+summary["candidate_sha256"]+".zip"
        summary["newly_written"]=store_unique(folder,name,blob,apply=apply) if folder.is_dir() else False
    report={
        "status":"PRIVATE_CANDIDATES_CREATED" if apply else "DRY_RUN",
        "paid_release_authorized":False,
        "current_store_products_mutated":0,
        "existing_private_archives_mutated":0,
        "items":[summary for _,summary in results],
    }
    if apply:
        stable=dict(report)
        stable["items"]=[{k:v for k,v in item.items() if k!="newly_written"} for item in report["items"]]
        raw=(json.dumps(stable,sort_keys=True,indent=2)+"\n").encode()
        report_name="astra-commercial-review-"+hash_bytes(raw)[:20]+".json"
        store_unique(folder,report_name,raw,apply=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog",required=True)
    parser.add_argument("--inbox",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    result=run(args.catalog,args.inbox,args.output,apply=args.apply)
    for item in result["items"]:
        print("ASTRA_PROVENANCE_SKU="+item["sku"])
        print("ASTRA_PROVENANCE_SOURCE_FILES_PRESERVED="+str(item["original_files_preserved"]))
        print("ASTRA_PROVENANCE_CANDIDATE_SHA="+item["candidate_sha256"])
        print("ASTRA_PROVENANCE_STATIC_WARNINGS="+str(len(item["unresolved_dependencies"])))
    print("ASTRA_PROVENANCE_REPORT_STATUS="+result["status"])
    print("ASTRA_PROVENANCE_SALES_ENABLED=false")
    print("ASTRA_PROVENANCE_PRODUCTION_ASSET_MUTATIONS=0")


if __name__=="__main__":
    main()
