#!/usr/bin/env python3
"""Evidence-gated, private, runnable intake for every factory family.

ALL 40 are active for authenticated-local-side preparation/intake; NOT a claim
of 40 ready factories, customer sales, live payments or public pages. No direct
network, shell, credentials, automatic commerce, third-party contact or LLM.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA="saeit.factory.all40-operational-intake.v1"
REQUEST_SCHEMA="saeit.factory.private-family-request.v1"
RECEIPT_SCHEMA="saeit.factory.private-family-task-receipt.v1"
FAMILY=re.compile(r"^F(?:0[1-9]|[1-3][0-9]|40)$")
REQUEST_ID=re.compile(r"^[a-zA-Z0-9_-]{6,60}$")
INTENTS={"technical_evaluation","custom_specification","commercial_enquiry"}
MAX_PER_TICK=3

def require(value,reason):
    if not value:raise ValueError("INTAKE40_"+reason)
def digest(value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8")
    return hashlib.sha256(raw).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def private(path):
    path=Path(path)
    require(not path.is_symlink(),"SYMLINK_DIRECTORY")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    require(path.is_dir() and not path.is_symlink(),"BAD_DIRECTORY")
    os.chmod(str(path),0o700)
    return path
def read(path,limit=200000):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and 0<p.stat().st_size<=limit,"UNTRUSTED_INPUT")
    obj=json.loads(p.read_text(encoding="utf8"))
    require(isinstance(obj,dict),"NOT_OBJECT")
    return obj
def save(path,obj):
    p=Path(path)
    private(p.parent)
    require(not p.is_symlink(),"SYMLINK_OUTPUT")
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode("utf8")
    fd,temp=tempfile.mkstemp(prefix=".intake40-",dir=str(p.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o600)
        os.replace(temp,str(p))
    finally:
        if os.path.exists(temp):os.unlink(temp)
def source_offers(root):
    root=Path(root)
    require(root.is_dir() and not root.is_symlink(),"UNSAFE_PRIVATE_ROOT")
    offers=root/"commercial40/offers"
    require(offers.is_dir() and not offers.is_symlink(),"COMMERCE_OFFERS_MISSING")
    result={}
    for number in range(1,41):
        fid="F%02d"%number
        item=read(offers/(fid+".json"))
        require(item.get("family_id")==fid and item.get("offer_status")==
            "commercial_preparation_private_only","FAMILY_PROPOSAL_INVALID")
        require(item.get("public_sale_allowed") is False and
                item.get("payment_enabled") is False and
                item.get("published") is False,"UNVERIFIED_SALES_FLAG")
        qty=item.get("technical_products_with_verified_archive")
        require(type(qty) is int and qty>=0,"BAD_TECHNICAL_COUNT")
        require(isinstance(item.get("commercial_blockers"),list) and
                bool(item["commercial_blockers"]),"MISSING_ADMISSION_BLOCKERS")
        result[fid]=item
    return result
def classify(fid,offer):
    qty=offer["technical_products_with_verified_archive"]
    return {"family_id":fid,"operational_intake_enabled":True,
      "intake_channels":["private_owner_work_queue"],
      "technical_portfolio_present":qty>0,
      "real_technical_packages":qty,
      "workflow_lane":"product_admission_review" if qty else "native_builder_gap_engineering",
      "available_actions":["technical_evaluation","custom_specification","commercial_enquiry"],
      "commercial_sales_enabled":False,
      "client_payment_acceptance_enabled":False,
      "public_site_listed_by_activation":False,
      "human_approval_required":True,
      "remaining_commercial_blockers":offer["commercial_blockers"]}
def validate_request(req,offers):
    require(req.get("schema")==REQUEST_SCHEMA,"REQUEST_SCHEMA")
    ident=req.get("request_id");fid=req.get("family_id");intent=req.get("intent")
    require(isinstance(ident,str) and REQUEST_ID.fullmatch(ident),"REQUEST_ID")
    require(isinstance(fid,str) and FAMILY.fullmatch(fid) and fid in offers,"FAMILY_ID")
    require(intent in INTENTS,"REQUEST_INTENT")
    name=req.get("title");details=req.get("specification")
    require(isinstance(name,str) and 8<=len(name.strip())<=160,"TITLE")
    require(isinstance(details,str) and 30<=len(details.strip())<=3000,"SPECIFICATION")
    require(set(req)=={"schema","request_id","family_id","intent","title","specification"},"REQUEST_EXTRA_FIELDS")
    for value in (name,details):
        require("\0" not in value,"NULL_BYTE")
    return {"schema":REQUEST_SCHEMA,"request_id":ident,"family_id":fid,
       "intent":intent,"title":name.strip(),"specification":details.strip()}
def task_for_request(req,offers,probe=False):
    clean=validate_request(req,offers);fid=clean["family_id"]
    state=classify(fid,offers[fid])
    lane=state["workflow_lane"]
    route=("verify existing physical sample, ownership, commercial license and human quality approval"
        if lane=="product_admission_review" else
        "implement and independently verify a native maker and physical 50-stage product")
    return {"schema":RECEIPT_SCHEMA,"request_id":clean["request_id"],
       "family_id":fid,"requested_intent":clean["intent"],
       "origin":"internal_controlled_probe" if probe else "local_private_request",
       "task_source_sha256":digest(clean),
       "dispatch_lane":lane,"technical_portfolio_present":state["technical_portfolio_present"],
       "task_title":clean["title"],"engineering_specification":clean["specification"],
       "next_action":route,
       "status":"probe_only_not_dispatched" if probe else "queued_for_specialist_review",
       "payment_created":False,"commercial_release_authorized":False,
       "native_product_manufactured_by_intake":False,
       "public_site_mutated":False}
def probe_40(offers):
    proofs=[]
    for i,fid in enumerate(sorted(offers)):
        request={"schema":REQUEST_SCHEMA,"request_id":"probeall40_%02d"%(i+1),
          "family_id":fid,"intent":"technical_evaluation",
          "title":"Internal family intake routing check %s"%fid,
          "specification":"Verify actual internal family-specific route, QA blockers, receipts and strict no-sale controls."}
        result=task_for_request(request,offers,probe=True)
        require(result["family_id"]==fid and result["payment_created"] is False and
             result["origin"]=="internal_controlled_probe" and
             result["status"]=="probe_only_not_dispatched","PROBE_FAIL")
        proofs.append({"family_id":fid,"lane":result["dispatch_lane"],
          "evidence_hash":digest(result)})
    require(len(proofs)==40 and len({r["evidence_hash"] for r in proofs})==40,
            "FORTY_ROUTING_PROBES")
    return proofs
def tick(root,max_per_tick=MAX_PER_TICK):
    root=Path(root)
    require(1<=max_per_tick<=3,"TICK_CAP")
    offers=source_offers(root)
    area=private(root/"activation40")
    with (area/".intake.lock").open("a+b") as f:
        os.fchmod(f.fileno(),0o600)
        try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"busy","processed":0}
        inbox=private(area/"requests")
        tasks=private(area/"tasks")
        receipts=private(area/"receipts")
        rejected=private(area/"rejected")
        processed=private(area/"processed")
        report={"schema":SCHEMA,"observed_utc":now(),
          "registered_intake_families":len(offers),
          "families_available_for_private_intake":40,
          "technical_product_families":sum(v["technical_products_with_verified_archive"]>0 for v in offers.values()),
          "families_needing_a_native_maker":sum(v["technical_products_with_verified_archive"]==0 for v in offers.values()),
          "commercial_families_sellable":0,
          "live_checkout_sessions_started":0,"sales_and_payments_processed":0,
          "genuine_live_agent_emission_proven":False,
          "all_40_native_builders_proven":False,
          "families":[classify(fid,offer) for fid,offer in offers.items()]}
        # SHA-bound, distinct controlled tests; probes are not real orders.
        proofs=probe_40(offers)
        report["synthetic_local_route_probes_verified"]=len(proofs)
        report["synthetic_probe_manifest_sha256"]=digest(proofs)
        save(area/"dashboard.json",report)
        names=sorted(inbox.iterdir())
        require(len(names)<=500,"QUEUE_LIMIT")
        processed_count=rejected_count=0
        for path in names:
            if processed_count+rejected_count>=max_per_tick:break
            require(path.is_file() and not path.is_symlink() and path.suffix==".json" and
                REQUEST_ID.fullmatch(path.stem),"QUEUE_UNSAFE_FILENAME")
            ident=path.stem
            try:
                request=read(path,8192)
                require(request.get("request_id")==ident,"REQUEST_FILE_ID")
                result=task_for_request(request,offers,probe=False)
                if (tasks/(ident+".json")).exists() or (receipts/(ident+".json")).exists():
                    raise ValueError("INTAKE40_DUPLICATE_ID")
                task={**result,"observed_utc":now()}
                save(tasks/(ident+".json"),task)
                save(receipts/(ident+".json"),{"request_id":ident,
                  "family_id":result["family_id"],"queue_status":"received_pending_engineer",
                  "task_sha256":digest(task),"public_sale_allowed":False,
                  "customer_charged":False})
                os.replace(path,processed/path.name)
                processed_count+=1
            except (ValueError,KeyError,TypeError,json.JSONDecodeError) as err:
                # No corrupt customer data is allowed into the work queue.
                if (rejected/path.name).exists():raise ValueError("INTAKE40_REJECT_ID_COLLISION")
                os.replace(path,rejected/path.name)
                save(rejected/(ident+".reject.json"),{"request_id":ident,
                    "error_code":str(err)[:120],"payment_attempted":False})
                rejected_count+=1
        counters={"queued_requests_accepted":processed_count,
          "queued_requests_rejected":rejected_count,
          "pending_specialist_tasks":len(list(tasks.glob("*.json")))}
        save(area/"last_tick.json",{"schema":SCHEMA,"observed_utc":now(),
         **counters,"real_payment_handled":False})
        print("FACTORY_ALL40_PRIVATE_ACTIVATION="+json.dumps({**counters,
          "families_available_for_private_intake":40,
          "technical_product_families":report["technical_product_families"],
          "families_needing_native_maker":report["families_needing_a_native_maker"],
          "commercial_sellable_families":0,
          "synthetic_probe_routes_tested":len(proofs)},sort_keys=True))
        return {"report":report,**counters}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    ap.add_argument("--max-per-tick",type=int,default=3)
    args=ap.parse_args()
    tick(args.factory_private,args.max_per_tick)
if __name__=="__main__":
    try:main()
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
        print("FACTORY_ALL40_INTAKE_ERROR="+type(error).__name__+":"+str(error)[:160])
        raise SystemExit(1)
