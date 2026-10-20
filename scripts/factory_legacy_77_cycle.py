#!/usr/bin/env python3
"""Private once-per-cycle factory heritage evaluation: source, import, safe probes.

This runner never starts the original site scheduler, robot main(), publishing,
network calls, payments, arbitrary generated source or background agent workers.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile

SCHEMA="saeit.factory.heritage-evaluation-cycle.v1"


def evaluate(repo):
    base=Path(repo).resolve()
    source=base/"scripts/factory_legacy_77_benchmark.py"
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("HERITAGE_BENCHMARK_UNAVAILABLE")
    spec=importlib.util.spec_from_file_location("factory_legacy_77_benchmark",source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    summary=module.benchmark(root=base,run_child=True)
    if (summary["historical_hash_verified"]!=77
            or summary["historical_module_imports_tested"]!=77
            or summary["historical_functional_probes_tested"]<14
            or summary["historical_robot_roles"]!=11
            or summary["factory_service_activated"]):
        raise RuntimeError("HERITAGE_BENCHMARK_INCOMPLETE")
    return {
        "schema":SCHEMA,"observed_utc":datetime.now(timezone.utc).isoformat(),
        "vps_local_evaluation_success":True,
        "source_modules_77":77,
        "real_read_only_imports":77,
        "real_pure_function_probes":summary["historical_functional_probes_tested"],
        "robot_source_roles_verified":11,
        "separate_agents_executed":0,
        "original_cpanel_source_match":False,
        "customer_product_published":False,
        "site_workers_modified":False,
        "agent_generation_auto_promoted":False,
        "factory_prod_agents_replaced":False,
        "all_77_capabilities_quarantined_for_comparison":True
    }


def safe_write(output,result):
    path=Path(output)
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("HERITAGE_INVALID_OUTPUT")
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(path.parent,0o700)
    payload=(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode()
    if len(payload)>16000:
        raise RuntimeError("HERITAGE_REPORT_TOO_LARGE")
    fd,tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".heritage-")
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    data=evaluate(args.repo)
    safe_write(args.output,data)
    print("HERITAGE_VPS_77_IMPORTED_WITH_REAL_PROBES=true")
    print("HERITAGE_11_ROBOT_SOURCE_ROLES_PRESENT=true")
    print("HERITAGE_PRODUCTION_SITE_AGENTS_REPLACED=false")
    print("HERITAGE_G64_G65_AUTO_PROMOTED=false")


if __name__=="__main__":
    main()
