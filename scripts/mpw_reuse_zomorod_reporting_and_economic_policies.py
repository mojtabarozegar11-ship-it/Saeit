"""Private MojPlayWin operational reporting + economics policy agent.

Reuse SHA-pinned original Zomorod activity and Economic Master Agent policy,
but DO NOT import the original Django models or execute its financial actions.
Records only real MojPlayWin agent outputs and site-monitoring events.
"""
import ast
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PARENT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
ORIGINAL=PARENT/"zomorod_django_agent_sources_20261018"
WORKER=PARENT/"v91_verified_main_port_20261018"/"operator_state"
MONITORS=PARENT/"site_health_v11_port_20261018"
RESULTS=PARENT/"management_intelligence_20261018"
MAX_JSON=60000

def check(cond,msg):
    if not cond:raise RuntimeError(msg)

def private_dir(path):
    return path.is_dir() and not path.is_symlink() and (path.stat().st_mode & 0o077)==0

def parse_assignments(source,names,manifest):
    path=ORIGINAL/"reference"/source
    check(path.is_file() and not path.is_symlink(),"UNSAFE_ORIGINAL_REFERENCE")
    raw=path.read_bytes()
    check(hashlib.sha256(raw).hexdigest()==manifest["files"][source],"ORIGINAL_REFERENCE_TAMPERED")
    tree=ast.parse(raw.decode("utf8"))
    values={}
    for node in tree.body:
        if not isinstance(node,ast.Assign) or len(node.targets)!=1 or not isinstance(node.targets[0],ast.Name):
            continue
        key=node.targets[0].id
        if key not in names:continue
        expr=node.value
        if (isinstance(expr,ast.Call) and isinstance(expr.func,ast.Name)
            and expr.func.id=="frozenset" and len(expr.args)==1 and not expr.keywords):
            expr=expr.args[0]
        try:values[key]=ast.literal_eval(expr)
        except (TypeError,ValueError,SyntaxError):pass
    check(all(n in values for n in names),"EXPECTED_POLICY_CONSTANT_NOT_FOUND")
    return values

def read_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_JSON:
        return None
    try:
        value=json.loads(path.read_text("utf8"))
        return value if isinstance(value,dict) else None
    except (OSError,ValueError,UnicodeError):
        return None

def verified_draft_counts():
    result={"research_digest":0,"product_blueprint":0}
    if not private_dir(WORKER/"processed") or not private_dir(WORKER/"drafts"):
        return result
    for request_path in sorted((WORKER/"processed").glob("*.json"))[:300]:
        req=read_json(request_path)
        if not req or req.get("tenant")!="mojplaywin-main" or req.get("review_only") is not True:
            continue
        digest=hashlib.sha256(request_path.read_bytes()).hexdigest()[:24]
        draft=read_json(WORKER/"drafts"/(digest+".json"))
        if not draft or not isinstance(draft.get("draft"),dict):continue
        meta=draft["draft"]
        if meta.get("tenant")!="mojplaywin-main" or meta.get("published") is not False:
            continue
        kind=req.get("kind","research_digest")
        if kind in result:result[kind]+=1
    return result

def editorial_holds():
    result={"review_ready_not_published":0,"needs_editorial_revision":0}
    folder=WORKER/"quality_reviews"
    if not private_dir(folder):return result
    for file in sorted(folder.glob("*.json"))[:300]:
        row=read_json(file)
        if not row or row.get("tenant")!="mojplaywin-main":continue
        status=row.get("status")
        if status in result:result[status]+=1
    return result

def monitoring_snapshot():
    row=read_json(MONITORS/"last_scan.json") if private_dir(MONITORS) else None
    if not row or row.get("tenant")!="mojplaywin-main" or row.get("total_agents")!=11:
        return {"observed_checks":0,"ok":0,"warning":0,"error":0,"observed_utc":None}
    runs=row.get("runs",[])
    if not isinstance(runs,list) or len(runs)!=11 or len({r.get("code") for r in runs if isinstance(r,dict)})!=11:
        return {"observed_checks":0,"ok":0,"warning":0,"error":0,"observed_utc":None}
    return {"observed_checks":11,"ok":sum(x.get("status")=="ok" for x in runs),
            "warning":sum(x.get("status")=="warning" for x in runs),
            "error":sum(x.get("status")=="error" for x in runs),
            "observed_utc":row.get("observed_utc")}

def write_atomic(path,payload):
    data=json.dumps(payload,ensure_ascii=False,sort_keys=True).encode("utf8")
    check(len(data)<30000,"REPORT_TOO_LARGE")
    fd,temp=tempfile.mkstemp(prefix=".tmp-agent-",dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def execute():
    check(private_dir(PARENT) and private_dir(ORIGINAL),"PRIVATE_COPIED_AGENT_SOURCES_MISSING")
    check(private_dir(WORKER) and private_dir(MONITORS),"MOJPLAYWIN_PRIVATE_AGENT_DATA_MISSING")
    manifest=read_json(ORIGINAL/"manifest.json")
    check(manifest and manifest.get("tenant")=="mojplaywin-main","INVALID_COPIED_ORIGIN")
    company=parse_assignments("core/company_activity_agent.py",
        ("REPORT_TYPES","REPORT_TITLES"),manifest)
    economic=parse_assignments("core/economic_master_agent.py",
        ("MISSION","AUTONOMOUS_ACTIONS","FINANCIAL_ACTIONS","FORBIDDEN_EXECUTION","ECONOMIC_CONSTITUTION"),manifest)
    check("EXECUTIVE_BRIEF" in company["REPORT_TYPES"],"MISSING_COMPANY_REPORT_CONTRACT")
    check(economic["ECONOMIC_CONSTITUTION"].get("audit_every_action") is True,"MISSING_ECONOMIC_AUDIT_POLICY")
    check("payment" in economic["FINANCIAL_ACTIONS"],"MISSING_FINANCIAL_ACTION_POLICY")
    # Explicitly prohibit any use of finance actions even if original site policy
    # permits them with further approval. This project performs NO transactions.
    safe_actions={"report","fact_check","quality_check","research","analyze"}
    check(safe_actions.issubset(economic["AUTONOMOUS_ACTIONS"]),"UNSAFE_ACTION_CONTRACT")
    forbidden=set(economic["FORBIDDEN_EXECUTION"])|set(economic["FINANCIAL_ACTIONS"])
    check(not safe_actions & forbidden,"ACTION_POLICY_CONFLICT")

    drafts=verified_draft_counts()
    holds=editorial_holds()
    monitoring=monitoring_snapshot()
    evidence={
        "tenant":"mojplaywin-main","observed_utc":datetime.now(timezone.utc).isoformat(),
        "private_reviewed_drafts":drafts,"real_editorial_reviews":holds,
        "last_monitors":monitoring,"human_company_activities_consulted":0,
        "financial_account_data_consulted":0,"factory_connected":False,
    }
    report={
        "id":"company_activity_intelligence","status":"private_report_completed",
        "report_type":"EXECUTIVE_BRIEF","source_of_truth":"MojPlayWin private worker + monitoring evidence",
        "report_title":"گزارش عملیاتی واقعی ایجنت‌های MojPlayWin، نه فعالیت شرکت زمرد ملل",
        "monitored_site_routes":monitoring["observed_checks"],
        "monitored_site_ok":monitoring["ok"],
        "private_drafts_total":sum(drafts.values()),
        "private_drafts_requiring_revision":holds["needs_editorial_revision"],
        "company_revenue_claims":None,
        "requires_owner_review":True,"published":False,
        "source_policy_sha256":manifest["files"]["core/company_activity_agent.py"]
    }
    econ={
        "id":"economic_master_policy","status":"policy_validated_no_financial_execution",
        "source_policy_sha256":manifest["files"]["core/economic_master_agent.py"],
        "permitted_actions_used":["report","analyze","quality_check"],
        "blocked_financial_actions":sorted(economic["FINANCIAL_ACTIONS"]),
        "unverified_revenue_counted":False,"trades_or_payments_executed":0,
        "recommended_next_safe_step":(
            "review_and_improve_private_drafts" if holds["needs_editorial_revision"]
            else "continue_verified_health_monitoring"),
        "published":False,"requires_owner_approval_for_binding_actions":True,
    }
    if RESULTS.exists():
        check(private_dir(RESULTS),"PRIVATE_RESULT_DIR_UNSAFE")
    else:
        RESULTS.mkdir(mode=0o700)
    write_atomic(RESULTS/"latest_company_operations.json",{**evidence,"report":report})
    write_atomic(RESULTS/"latest_economic_policy.json",{**evidence,"report":econ})
    print(json.dumps({
        "status":"MPW_ZOMOROD_REPORTING_AND_ECONOMIC_POLICIES_IN_USE",
        "source_modules_hash_verified":2,
        "new_private_agent_roles":["company_activity_intelligence","economic_master_policy"],
        "validated_private_drafts":sum(drafts.values()),
        "monitored_main_site_routes":monitoring["observed_checks"],
        "financial_actions_executed":0,"public_content_published":0,
        "zomorod_or_factory_modified":False,"shared_Django_changed":False,
        "report_dir":str(RESULTS)
    },ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    execute()
