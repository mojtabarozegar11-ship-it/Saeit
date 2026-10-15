#!/usr/bin/env python3
"""Read-only diagnostics of the VPS autonomous-product scheduler and its dependencies.

This script prints only redacted module/health classifications. Does not import
factory modules, create pycache, read secrets, change database, or start a cycle.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

base=Path.home()/"factory-runtime"
ops=base/"operations"
source=ops/"autonomous-product-runtime"/"scripts"
standalone=ops/"product-deploy-source"/"scripts"
stage=ops/"evidence-sidecar-candidate"/"scripts"
reports=base/"private"/"autonomous-product-cycle"
pairs=[
    ("production_quality",source/"factory_evidence_quality.py"),
    ("production_portfolio",source/"factory_autonomous_portfolio.py"),
    ("production_cycle",source/"factory_vps_product_cycle.py"),
    ("staging_quality",standalone/"factory_evidence_quality.py"),
    ("staging_portfolio",standalone/"factory_autonomous_portfolio.py"),
    ("sidecar_quality",stage/"factory_evidence_quality.py"),
]
for name,path in pairs:
    good=path.is_file() and not path.is_symlink()
    print("MODULE_"+name.upper()+"_PRESENT="+str(good),flush=True)
    if good:
        raw=path.read_bytes()
        print("MODULE_"+name.upper()+"_SHA256="+hashlib.sha256(raw).hexdigest(),flush=True)
        try:
            ast.parse(raw,filename="<private-module>")
            print("MODULE_"+name.upper()+"_SYNTAX_VALID=True",flush=True)
        except (SyntaxError,ValueError):
            print("MODULE_"+name.upper()+"_SYNTAX_VALID=False",flush=True)
if (source/"factory_autonomous_portfolio.py").is_file():
    tree=ast.parse((source/"factory_autonomous_portfolio.py").read_text(encoding="utf-8"))
    imported=False
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and node.value=="factory_evidence_quality.py":
            imported=True
            break
    print("PRODUCTION_PORTFOLIO_REQUIRES_QUALITY="+str(imported),flush=True)
cron=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=6)
if cron.returncode==0:
    for label,flag in (("AUTONOMOUS_PRODUCTS","SAEIT_AUTONOMOUS_PRODUCTS_V2"),
                       ("RESEARCH_MONITOR","SAEIT_FACTORY_RESEARCH_EVIDENCE_V1")):
        print("CRON_"+label+"_COUNT="+str(cron.stdout.count(flag)),flush=True)
else:
    print("CRON_LIST_AVAILABLE=False",flush=True)
loop=ops/"vps-only-loop.pid"
try:
    pid=int(loop.read_text().strip())
    os.kill(pid,0)
    print("MAIN_FACTORY_LOOP_ALIVE=True",flush=True)
except (ValueError,OSError):
    print("MAIN_FACTORY_LOOP_ALIVE=False",flush=True)
state=reports/"production-state.json"
if state.is_file() and not state.is_symlink():
    print("PRODUCTION_STATE_AGE_SECONDS="+str(int((datetime.now(timezone.utc)-datetime.fromtimestamp(state.stat().st_mtime,timezone.utc)).total_seconds())),flush=True)
    try:
        payload=json.loads(state.read_text(encoding="utf-8"))
        for field in ("product_candidates_processed","research_dossiers_updated","built_product_count",
                      "research_review_candidate_count","publishable_product_count",
                      "store_distribution_state","artifact_qa_passed","commercial_quality_review_completed"):
            v=payload.get(field,"not_recorded")
            if isinstance(v,(int,float,bool)) or (isinstance(v,str) and v in ("not_connected","not_recorded")):
                print("PRODUCT_STATE_"+field.upper()+"="+str(v),flush=True)
    except (ValueError,OSError,UnicodeError):
        print("PRODUCT_STATE_PARSE_INVALID",flush=True)
else:
    print("PRODUCT_STATE_MISSING=True",flush=True)
log=ops/"autonomous-product-cycle.log"
if log.is_file() and not log.is_symlink():
    print("PRODUCT_CYCLE_LOG_BYTES="+str(log.stat().st_size),flush=True)
    raw=log.read_bytes()[-15000:].decode("utf-8",errors="replace")
    # Parse only fixed tokens (no raw tracebacks, addresses, prompts or secrets).
    terms={
        "MISSING_MODULE":r"No module named|ModuleNotFoundError",
        "QUALITY_DEPENDENCY_ERROR":r"factory_evidence_quality",
        "FILE_NOT_FOUND":r"FileNotFoundError",
        "FACTORY_CYCLE_EXCEPTION":r"VPS_FACTORY_CYCLE_ERROR",
        "SUCCESS":r"VPS_FACTORY_CYCLE_STATUS=ok",
        "IMPORT_ERROR":r"ImportError",
    }
    for label,pattern in terms.items():
        print("RECENT_PRODUCT_CYCLE_"+label+"_SIGNALS="+str(len(re.findall(pattern,raw,re.IGNORECASE))),flush=True)
print("PRIVATE_DEPENDENCY_READONLY_AUDIT_DONE",flush=True)
