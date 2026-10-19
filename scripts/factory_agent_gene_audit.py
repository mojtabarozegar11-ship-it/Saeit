#!/usr/bin/env python3
"""Factory agent/module capability audit: evidence-backed 'advanced genes'.

"Genes" here means testable control contracts, NOT biological genes and NOT
self-modifying AI code. Audit is read-only and marks unsupported features
as gaps rather than pretending every agent and module is operating.
No network/API, secrets, customer orders or site publication.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA="saeit.factory.genetic-capability-audit.v1"
SCOPE={
    "factory_workers":[
        "factory_12_stage_governance.py",
        "factory_40_family_master.py",
        "factory_autonomous_portfolio.py",
        "factory_continuous_production_orders.py",
        "factory_evidence_quality.py",
        "factory_first_product_pilot.py",
        "factory_product_maker.py",
        "factory_product_rework.py",
        "factory_production_warehouse.py",
        "factory_research_sidecar.py",
        "factory_vps_product_cycle.py",
        "vps_master_evolution_cycle.py",
    ],
    "django_agents":[
        "agent_registry.py",
        "autonomous_brain.py",
        "master_agent_capability_pack.py",
        "economic_master_agent.py",
        "knowledge_agent.py",
        "company_activity_agent.py",
        "research_runtime.py",
    ],
}
# Contracts grounded in actual, testable source. "present_in_source" does not
# certify quality or live behavior; a live VPS smoke is a separate gate.
CONTRACTS=[
    ("independent_source_of_demand","scripts/factory_autonomous_portfolio.py",("select_product_ids","build")),
    ("minute_work_order_queue","scripts/factory_continuous_production_orders.py",("generate","fingerprint")),
    ("documented_qa","scripts/factory_12_stage_governance.py",("valid_approval","verify_evidence_files")),
    ("specialist_reviewer_integrity","scripts/factory_12_stage_governance.py",("verify_reviewer_signature","verify_persisted_approvals")),
    ("real_product_build","scripts/factory_product_maker.py",("manufacture","verify_recipe")),
    ("repair_without_discard","scripts/factory_product_rework.py",("record_failure","record_technical_recovery")),
    ("immutable_production_warehouse","scripts/factory_production_warehouse.py",("stock_one","verify_stored")),
    ("independent_commercial_stock_gate","scripts/factory_12_stage_governance.py",("final_admit","verify_final_package_zip")),
    ("resource_observation","scripts/factory_40_family_master.py",("cpu_mem_snapshot","run")),
    ("bounded_master_evolution","scripts/vps_master_evolution_cycle.py",("evaluate",)),
    ("agent_risk_registry","core/agent_registry.py",("can_execute","effective_risk")),
    ("autonomous_decision_trace","core/autonomous_brain.py",("observe","decide")),
    ("market_evidence_quality","scripts/factory_evidence_quality.py",("assess",)),
]
BLOCKERS=[
    ("missing_generic_work_order_executor",
     "factory_vps_product_cycle.py",r"selected = sorted\(maker\.RECIPES\)",
     "The manufacture loop still uses a static recipe allowlist."),
    ("family_dispatch_not_authorized",
     "factory_40_family_master.py",r"production_job_slots_authorized.?[\"']?\s*:\s*0",
     "The 40-family master monitors capacity but intentionally cannot dispatch untested adapters."),
    ("missing_lifecycle_passports",
     "factory_12_stage_governance.py",r"missing_product_passport",
     "Missing real product passports must be remedied before promoting orders."),
]
def parse_module(path):
    src=path.read_text(encoding="utf8")
    compile(src,str(path),"exec")
    tree=ast.parse(src,filename=str(path))
    symbols=set()
    for item in ast.walk(tree):
        if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            symbols.add(item.name)
    return src,symbols
def audit(root):
    base=Path(root).resolve()
    if not (base/"scripts").is_dir() or not (base/"core").is_dir():
        raise RuntimeError("GENE_AUDIT_EXPECTS_FACTORY_REPOSITORY")
    files=[]
    for name in SCOPE["factory_workers"]:
        files.append("scripts/"+name)
    for name in SCOPE["django_agents"]:
        files.append("core/"+name)
    # Include installed adjacent factory modules, not all unrelated sites.
    for path in (base/"scripts").glob("factory_*.py"):
        relative=path.relative_to(base).as_posix()
        if relative not in files:files.append(relative)
    for path in (base/"core"/"management"/"commands").glob("*agent*.py"):
        relative=path.relative_to(base).as_posix()
        if relative not in files:files.append(relative)
    records={};errors=[]
    for name in sorted(files):
        path=base/name
        if not path.is_file() or path.is_symlink():
            errors.append({"module":name,"error":"missing_or_symlink"})
            continue
        try:
            source,symbols=parse_module(path)
        except (SyntaxError,UnicodeError,OSError) as exc:
            errors.append({"module":name,"error":type(exc).__name__})
            continue
        records[name]={"sha256":hashlib.sha256(source.encode("utf8")).hexdigest(),
                       "function_or_class_count":len(symbols),"symbols":symbols}
    gene_results=[]
    for code,name,needed in CONTRACTS:
        rec=records.get(name,{})
        found=[symbol for symbol in needed if symbol in rec.get("symbols",set())]
        gene_results.append({"gene":code,"source":name,
            "expected_symbols":list(needed),"found_symbols":found,
            "source_contract_status":"present_in_source" if len(found)==len(needed) else "missing",
            "live_runtime_verified":False})
    blockers=[]
    for code,filename,pattern,description in BLOCKERS:
        data=records.get("scripts/"+filename)
        if data:
            original=(base/"scripts"/filename).read_text(encoding="utf8")
            if re.search(pattern,original):
                blockers.append({"id":code,"explanation":description,
                                 "status":"still_unresolved"})
    return {"schema":SCHEMA,"module_count":len(files),
            "verified_syntax_modules":len(records),"syntax_or_missing_errors":errors,
            "advanced_control_genes":gene_results,
            "source_contract_genes_present":sum(x["source_contract_status"]=="present_in_source" for x in gene_results),
            "source_contract_genes_total":len(gene_results),
            "known_execution_blockers":blockers,
            "runtime_verified_production_genes":0,
            "self_modifying_code":False,
            "commercial_release_granted":False,
            "site_transfer_authorized":False,
            "audit_scope":"factory workers and named related master/agents only; other site agents unmodified"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    a=p.parse_args()
    result=audit(a.repo)
    # Don't export private source file contents, only hashes and contract status.
    safe=dict(result)
    safe.pop("ignored",None)
    print("FACTORY_AGENT_GENE_AUDIT="+json.dumps(safe,ensure_ascii=True,sort_keys=True,
           default=lambda value:sorted(value) if isinstance(value,set) else str(value)))
    print("FACTORY_MODULES_SYNTAX_VERIFIED="+str(result["verified_syntax_modules"]))
    print("FACTORY_AUDIT_SOURCE_CONTRACTS_PRESENT="+str(result["source_contract_genes_present"]))
    print("FACTORY_AUDIT_LIVE_PRODUCT_CLAIMS=0")
    return 1 if result["syntax_or_missing_errors"] or result["source_contract_genes_present"]!=len(CONTRACTS) else 0
if __name__=="__main__":
    try:sys.exit(main())
    except Exception as error:
        print("FACTORY_AGENT_GENE_AUDIT_ERROR="+type(error).__name__+":"+str(error)[:150],file=sys.stderr)
        sys.exit(1)
