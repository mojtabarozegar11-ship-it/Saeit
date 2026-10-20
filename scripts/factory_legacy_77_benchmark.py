#!/usr/bin/env python3
"""Safe factory evaluation of historical site capabilities from a fixed Git blob set.

The historical package is NOT installed as a VPS service or a site worker.
A SHA-verified 77-module loader is executed only inside its read-only audit child.
No publication, cron, payments, credentials, changes to the user's two websites.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SCHEMA="saeit.factory.heritage-candidate-benchmark.v1"
SOURCE_COMMIT="efc14442fd9782b039088d19b50edf5cfb3ca6b2"
ROOT=Path(__file__).resolve().parents[1]
CANDIDATES=ROOT/"ops/factory-site-capabilities/legacy-candidates"


def benchmark(root=ROOT, run_child=True):
    root=Path(root)
    base=root/"ops/factory-site-capabilities/legacy-candidates"
    manifest=base/"mpw_v91_port/ORIGIN.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>75000:
        raise RuntimeError("HISTORICAL_ORIGIN_NOT_VERIFIED")
    doc=json.loads(manifest.read_text(encoding="utf-8"))
    modules=doc.get("modules")
    if doc.get("file_count")!=77 or not isinstance(modules,list) or len(modules)!=77:
        raise RuntimeError("LEGACY_77_MANIFEST_INCOMPLETE")
    import_paths=set()
    for row in modules:
        relative=row.get("destination")
        if not isinstance(relative,str) or not relative.startswith("mpw_v91_port/legacy/"):
            raise RuntimeError("UNSAFE_HISTORICAL_PATH")
        file=base/relative
        if file.is_symlink() or not file.is_file() or file.stat().st_size>31000:
            raise RuntimeError("LEGACY_SOURCE_MISSING")
        if hashlib.sha256(file.read_bytes()).hexdigest()!=row.get("sha256"):
            raise RuntimeError("LEGACY_SOURCE_HASH_CHANGED:"+relative)
        ast.parse(file.read_bytes(),filename=relative)
        import_paths.add(relative)
    if len(import_paths)!=77:
        raise RuntimeError("LEGACY_DUPLICATE_CAPABILITIES")
    names={}
    for group,filename,variable,expected in (
        ("five","mpw_main_private_execution_robots.py","ROBOTS",5),
        ("six","mpw_main_extended_robots.py","NAMES",6)):
        path=base/"scripts"/filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size>32000:
            raise RuntimeError("LEGACY_ROBOT_SOURCE_MISSING")
        parsed=ast.parse(path.read_bytes(),filename=filename)
        names[group]=None
        for node in parsed.body:
            if isinstance(node,ast.Assign) and any(
                    isinstance(t,ast.Name) and t.id==variable for t in node.targets):
                names[group]=tuple(ast.literal_eval(node.value))
                break
        if names[group] is None or len(names[group])!=expected or len(set(names[group]))!=expected:
            raise RuntimeError("LEGACY_ROBOT_REGISTRY_INVALID")
    script=base/"scripts/mpw_77_modules_private_runner.py"
    spec=importlib.util.spec_from_file_location("historical_77_loader",script)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _,inspected=module.preflight()
    if len(inspected)!=77:
        raise RuntimeError("LEGACY_PRECHECK_INCOMPLETE")
    result=None
    if run_child:
        result=module.execute()
        if (result.get("modules_hash_verified")!=77 or
                result.get("modules_import_executed")!=77 or
                result.get("functional_probes_executed",0)<14 or
                result.get("standalone_agent_processes_created")!=0 or
                result.get("public_site_modified") is not False):
            raise RuntimeError("LEGACY_IMPORT_AUDIT_NOT_SUCCESSFUL")
    return {
        "schema":SCHEMA, "origin_git_commit":SOURCE_COMMIT,
        "historical_manifest_modules":77,"historical_hash_verified":len(inspected),
        "historical_module_imports_tested":result.get("modules_import_executed") if result else 0,
        "historical_functional_probes_tested":result.get("functional_probes_executed") if result else 0,
        "historical_robot_role_names":{key:list(value) for key,value in names.items()},
        "historical_robot_roles":sum(map(len,names.values())),
        "module_code_quarantined":True,
        "factory_service_activated":False,
        "cpanel_runtime_hashes_verified":False,
        "live_vps_worker_verified":False,
        "auto_promote_gen64_or_gen65":False,
        "site_publication_authorized":False,
        "site_site_worker_replaced":False
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--syntax-only",action="store_true")
    a=p.parse_args()
    result=benchmark(run_child=not a.syntax_only)
    print("FACTORY_HISTORICAL_77_BENCHMARK="+json.dumps(result,sort_keys=True))
    print("FACTORY_LEGACY_MODULE_IMPORTS_VERIFIED="+str(result["historical_module_imports_tested"]))
    print("FACTORY_LIVE_VPS_INSTALL_STATUS=UNVERIFIED")


if __name__=="__main__":
    main()
