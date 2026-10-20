#!/usr/bin/env python3
"""Private, evidence-gated router connecting the 3000 factory support bindings.
One entry point for scheduler, 40 families and authorized LOCAL worker callers.
It does not install manufacturing engines, access the network, run user code,
publish products, or grant commercial approval. Python 3.8+, stdlib only.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA="saeit.factory.tool-router.v1"
REQUEST_SCHEMA="saeit.factory.local-tool-request.v1"
ROLES={"planner","controller","quality","inventory","delivery","research","support_tools","site_bridge"}
FILE_ID=re.compile(r"^[A-Za-z0-9_-]{1,64}\.json$")
TOOL_ID=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)-T(?:0[1-9]|[1-6][0-9]|7[0-5])$")
def require(ok,code):
    if not ok:raise ValueError("ROUTER_"+code)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def json_bytes(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
def read_bytes(p,max_size=2_000_000):
    p=Path(p)
    require(p.is_file() and not p.is_symlink() and p.stat().st_size<=max_size,"UNTRUSTED_FILE")
    return p.read_bytes()
def load(path):
    require(Path(path).is_file() and not Path(path).is_symlink(),"RUNTIME_MISSING")
    spec=importlib.util.spec_from_file_location("saeit_factory_live_tool_router_workbench",str(path))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def private_dir(path):
    p=Path(path)
    require(not p.is_symlink(),"SYMLINK_DIRECTORY")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    require(p.is_dir() and not p.is_symlink(),"PRIVATE_DIRECTORY")
    os.chmod(str(p),0o700)
    return p
def atomic_json(path,data):
    path=Path(path);private_dir(path.parent)
    require(not path.is_symlink(),"SYMLINK_OUTPUT")
    fd,tmp=tempfile.mkstemp(dir=str(path.parent),prefix=".router-")
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(json_bytes(data)+b"\n");f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o600);os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def verified(ops,root,registry):
    ops=Path(ops);root=Path(root);reg=Path(registry)
    require(ops.is_dir() and not ops.is_symlink() and root.is_dir() and not root.is_symlink(),"UNSAFE_ROOT")
    runner=ops/"production-workbench-3000/runner.py"
    origin=runner.with_name("factory_1000_workbench.py")
    catfile=root/"production-toolkit-3000/catalog.json"
    receiptfile=root/"production-toolkit-3000/verification.json"
    receipt=json.loads(read_bytes(receiptfile))
    require(receipt.get("schema")=="saeit.factory.workbench-verification.v2","RECEIPT_SCHEMA")
    require(receipt.get("synthetic_test_invocations_passed")==3000 and receipt.get("new_bindings_added")==2000,"RECEIPT_COUNT")
    require(digest(read_bytes(runner,1_000_000))==receipt.get("runtime_sha256"),"RUNTIME_SHA")
    require(digest(read_bytes(origin,1_000_000))==receipt.get("base_runtime_sha256"),"BASE_SHA")
    catraw=read_bytes(catfile,2_000_000)
    require(digest(catraw)==receipt.get("catalog_sha256"),"CATALOG_SHA")
    regraw=read_bytes(reg,2_000_000)
    profiles=json.loads(regraw)
    catalogue=json.loads(catraw)
    wb=load(runner)
    expected=wb.catalog(profiles)
    require(catalogue.get("schema")=="saeit.factory.production-workbench.v2","CATALOG_SCHEMA")
    require(expected==catalogue and catalogue.get("tools_count")==3000,"CATALOG_CONTENT")
    ids={t["id"] for t in catalogue["tools"]}
    require(len(ids)==3000 and all(t["commercial_publication_allowed"] is False for t in catalogue["tools"]),"CATALOG_POLICY")
    require([x["id"] for x in profiles["profiles"]]==["F%02d"%x for x in range(1,41)],"FAMILY_REGISTRY")
    return wb,catalogue,profiles,digest(regraw),digest(catraw)
def selected_payloads(p):
    tests=p.get("specialist_tests",[])
    steps=["scope","research","design","implement","test","review","archive"]
    return {
      14:{"object":p,"required":["producer_adapter","formats","specialist_tests","resource_policy"]},
      22:{"requirements":[{"id":str(x),"verified":False} for x in tests[:100]]},
      23:{"risks":[{"name":"native-producer-activation-not-verified","likelihood":5 if not p.get("production_activation_allowed") else 3,"impact":4}]},
      25:{"deliverables":p["deliverables"][:40]},
      26:{"numbers":[len(p["deliverables"]),len(p["formats"]),len(tests)]},
      36:{"text":p["name_fa"]},
      60:{"object":{"family_id":p["id"],"producer_adapter":p["producer_adapter"],"formats":p["formats"]}},
      61:{"object":p,"sensitive_keys":["password","secret","token"]},
      68:{"text":p["name_fa"]},
      74:{"nodes":steps,"edges":[[a,b] for a,b in zip(steps,steps[1:])]}
    }
def execute(wb,cat,tool_id,payload):
    require(isinstance(tool_id,str) and TOOL_ID.fullmatch(tool_id),"TOOL_ID")
    require(len(json_bytes(payload))<=200000,"INPUT_SIZE")
    result=wb.invoke(cat,tool_id,payload)
    require(result.get("noncommercial") is True and result["tool_id"]==tool_id,"INVOCATION_CONTRACT")
    return result
def routes_for_family(wb,cat,profile):
    outputs=[]
    for number,payload in selected_payloads(profile).items():
        tool_id=profile["id"]+"-T%02d"%number
        result=execute(wb,cat,tool_id,payload)
        outputs.append({"tool_id":tool_id,"result_sha256":digest(json_bytes(result)),
                        "key":result["operation"]})
    require(len(outputs)==10,"TEN_REAL_CALLS")
    return {"family_id":profile["id"],"adapter":profile["producer_adapter"],
            "support_tools":75,"actual_invocations":len(outputs),"receipts":outputs,
            "native_manufacturer_proven_by_this_router":False}
def name_only(folder,name):
    require(isinstance(name,str) and bool(FILE_ID.fullmatch(name)),"REQUEST_FILENAME")
    path=Path(folder)/name
    require(not path.is_symlink(),"SYMLINK_REQUEST")
    return path
def handle_request(wb,cat,area,request):
    require(isinstance(request,dict) and request.get("schema")==REQUEST_SCHEMA,"REQUEST_SCHEMA")
    require(set(request)=={"schema","request_id","role","tool_id","payload"},"REQUEST_FIELDS")
    ident=request["request_id"]
    require(isinstance(ident,str) and bool(FILE_ID.fullmatch(ident+".json")),"REQUEST_ID")
    role=request["role"]
    require(role in ROLES,"UNKNOWN_ROLE")
    result=execute(wb,cat,request["tool_id"],request["payload"])
    return {"schema":"saeit.factory.local-tool-response.v1",
        "request_id":ident,"role_claimed_by_local_caller":role,
        "tool_id":result["tool_id"],"result":result["result"],"commercial_release":False}
def pending(wb,cat,area,max_jobs):
    inbox=private_dir(area/"requests")
    result_dir=private_dir(area/"results")
    archive=private_dir(area/"processed")
    rejected=private_dir(area/"rejected")
    processed=0;failed=0
    for requestfile in sorted(inbox.iterdir(),key=lambda p:p.name):
        if processed+failed>=max_jobs:break
        if not requestfile.is_file() or requestfile.is_symlink() or not FILE_ID.fullmatch(requestfile.name):
            continue
        if requestfile.stat().st_size>200000:continue
        try:
            request=json.loads(read_bytes(requestfile,200000))
            require(request.get("request_id")+".json"==requestfile.name,"REQUEST_ID_MISMATCH")
            response=handle_request(wb,cat,area,request)
            dest=name_only(result_dir,requestfile.name)
            atomic_json(dest,response)
            target=name_only(archive,requestfile.name)
            require(not target.exists(),"DUPLICATE_ARCHIVE")
            requestfile.rename(target)
            processed+=1
        except (ValueError,KeyError,TypeError,json.JSONDecodeError,OSError):
            # Do not leak sensitive payload or exception detail into public logs.
            target=name_only(rejected,requestfile.name)
            if target.exists():break
            requestfile.rename(target);failed+=1
    return {"completed":processed,"rejected":failed,"maximum_per_tick":max_jobs}
def tick(ops,root,registry,max_jobs=10):
    root=Path(root);area=private_dir(root/"tool-router")
    lock=area/".router.lock";require(not lock.is_symlink(),"SYMLINK_LOCK")
    with lock.open("a+b") as f:
        os.fchmod(f.fileno(),0o600)
        try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"busy"}
        wb,cat,reg,regsha,catsha=verified(ops,root,registry)
        rows=[routes_for_family(wb,cat,p) for p in reg["profiles"]]
        count=sum(x["actual_invocations"] for x in rows)
        require(len(rows)==40 and count==400,"FAMILY_COVERAGE")
        jobs=pending(wb,cat,area,max_jobs)
        report={"schema":SCHEMA,
            "observed_utc":datetime.now(timezone.utc).isoformat(),
            "verified_catalog_sha256":catsha,"family_registry_sha256":regsha,
            "registered_tool_bindings":3000,"new_tool_bindings":2000,
            "existing_tool_bindings_retained":1000,"families_connected":40,
            "operations_per_family_available":75,"unique_underlying_implementations":75,
            "support_invocations_this_tick":count,"family_readbacks":rows,
            "worker_access_roles":sorted(ROLES),"queued_requests":jobs,
            "scheduler_integration":"five_minute_existing_factory_cron",
            "native_manufacturing_engines_added":0,"published_products":0,
            "commercial_release":False,"payments_touched":False,"sites_touched":False,
            "agent_workers_confirmed_online":0,
            "note":"Executable local offline interface. Agent-specific live adoption is not inferred from a queue endpoint."}
        atomic_json(area/"dashboard.json",report)
        return report
def direct(ops,root,registry,role,tool_id,src,dst):
    require(role in ROLES,"UNKNOWN_ROLE")
    area=private_dir(Path(root)/"tool-router/jobs")
    source=name_only(area,src);target=name_only(area,dst)
    require(source!=target and target.parent==source.parent,"SAME_FILE")
    wb,cat,_,_,_=verified(ops,root,registry)
    response=handle_request(wb,cat,area,{"schema":REQUEST_SCHEMA,"request_id":src[:-5],
       "role":role,"tool_id":tool_id,"payload":json.loads(read_bytes(source,200000))})
    atomic_json(target,response)
    return response
def selftest(ops,root,registry):
    wb,cat,_,_,_=verified(ops,root,registry)
    for item in cat["tools"]:
        out=execute(wb,cat,item["id"],wb.fixture(item["operation"]))
        require(out["tool_id"]==item["id"],"SELFTEST_FAILURE")
    return {"routed":3000,"new":2000,"failed":0}
def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True);p.add_argument("--ops",required=True);p.add_argument("--registry",required=True)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--cycle",action="store_true")
    mode.add_argument("--verify-only",action="store_true")
    mode.add_argument("--selftest-all",action="store_true")
    mode.add_argument("--tool-id")
    p.add_argument("--role",default="support_tools");p.add_argument("--input-file");p.add_argument("--output-file")
    a=p.parse_args(argv)
    if a.cycle:
        report=tick(a.ops,a.factory_private,a.registry)
        print("FACTORY_TOOL_ROUTER_TICK="+json.dumps({k:report.get(k) for k in
            ("status","families_connected","registered_tool_bindings","support_invocations_this_tick","queued_requests")},sort_keys=True))
    elif a.verify_only:
        _,cat,reg,_,_=verified(a.ops,a.factory_private,a.registry)
        print("FACTORY_TOOL_ROUTER_VERIFIED="+str(len(cat["tools"]))+";FAMILIES="+str(len(reg["profiles"])))
    elif a.selftest_all:
        print("FACTORY_TOOL_ROUTER_SELFTEST="+json.dumps(selftest(a.ops,a.factory_private,a.registry),sort_keys=True))
    else:
        require(a.input_file and a.output_file,"DIRECT_IO_REQUIRED")
        response=direct(a.ops,a.factory_private,a.registry,a.role,a.tool_id,a.input_file,a.output_file)
        print("FACTORY_TOOL_ROUTER_INVOKED="+response["tool_id"])
    return 0
if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,ValueError,TypeError,KeyError,OverflowError) as exc:
        print(type(exc).__name__+":"+str(exc)[:180],file=sys.stderr);sys.exit(1)
