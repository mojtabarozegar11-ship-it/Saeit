#!/usr/bin/env python3
"""Generate one *meaningful* private factory work instruction per eligible minute.

Independent of websites, customer-order events, payment, LLM APIs and market feeds.
Reads local manufacturing research dossiers and explicitly submitted local source
snapshots; doesn't assert unknown evidence exists or certify products for sale.
Orders are input to later research, engineering, production and rework stages.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA="saeit.factory.production-instructions.v1"
# Compatibility sentinel for older callers; the queue has no total-order ceiling.
MAX_ORDERS=float("inf")
BLOCKER_ACTIONS={
 "FIVE_DISTINCT_PUBLIC_SOURCES_WITH_LINKED_EVIDENCE_REQUIRED":
  ("Document independently verifiable source",5,
   "Record one independent publication, its URL, dated access and the exact evidence it supports."),
 "ONE_HUNDRED_DISTINCT_STRONG_EVIDENCE_PASSAGES_REQUIRED":
  ("Verify ten new distinct factual evidence passages",10,
   "Collect and independently check ten distinct passages with provenance; never invent quotations."),
 "ONE_STRUCTURED_INTERNAL_RESEARCH_ACTION_REQUIRED":
  ("Design and perform reproducible internal research",1,
   "Specify hypothesis, protocol, measured inputs, actual execution, results and limitations."),
 "TEN_FACTOR_VALIDATION_PASS_REQUIRED":
  ("Resolve one missing business and technical validation factor",10,
   "Investigate and document a distinct validation factor with observable evidence and rejection criteria."),
 "FACTORY_OWNER_OR_ACTIVE_PRODUCT_STATE_INVALID":
  ("Verify product ownership and private factory state",1,
   "Confirm legitimate provenance, intellectual property permission and current non-public product state."),
 "PUBLISHED_KNOWLEDGE_PROVENANCE_REQUIRED":
  ("Trace knowledge provenance and supporting sources",1,
   "Draft a source-linked, fact-checked technical knowledge dossier for independent editorial review."),
 "FAIR_PRICE_AND_COST_REVIEW_REQUIRED":
  ("Validate production cost and value proposition",1,
   "Measure actual costs, inputs, sensitivity and buyer value; avoid unsupported price claims."),
 "HUMAN_COMMERCIAL_LICENSE_AND_FACTUAL_REVIEW_REQUIRED":
  ("Request human scientific, IP and commercial review",1,
   "Route the finished dossier to qualified reviewers; never self-authorize commercialization."),
}
SOURCES=("site-topic-snapshot","customer-intake-snapshot",
         "market-research-snapshot","factory-invention-snapshot")
ORDER_RE=re.compile(r"^WO-([0-9]+)\.json$")
HASH_RE=re.compile(r"^[a-f0-9]{64}$")

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                    separators=(",",":")).encode("utf8")).hexdigest()

def ensure_private(p):
    if p.is_symlink():raise RuntimeError("ORDERS_SYMLINK_PARENT")
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not p.is_dir() or p.is_symlink():raise RuntimeError("ORDERS_UNSAFE_DIRECTORY")
    os.chmod(str(p),0o700)

def read_json(p,max_bytes=10_000_000):
    if not p.is_file() or p.is_symlink() or p.stat().st_size>max_bytes:
        raise RuntimeError("ORDERS_SOURCE_NOT_SAFE:"+p.name)
    data=json.loads(p.read_text(encoding="utf8"))
    if not isinstance(data,dict):raise RuntimeError("ORDERS_EXPECTED_JSON_OBJECT")
    return data

def atomic_json(p,doc):
    ensure_private(p.parent)
    raw=(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    fd,tmp=tempfile.mkstemp(prefix=".instruction-",dir=str(p.parent))
    try:
        with os.fdopen(fd,"wb") as fp:
            fp.write(raw);fp.flush();os.fsync(fp.fileno())
        os.chmod(tmp,0o600)
        os.replace(tmp,str(p))
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def local_research_tasks(root):
    path=root/"research-dossiers"/"autonomous-portfolio.json"
    if not path.exists():return []
    portfolio=read_json(path)
    entries=portfolio.get("entries",[])
    if not isinstance(entries,list):raise RuntimeError("ORDERS_INVALID_RESEARCH_ENTRIES")
    tasks=[]
    for item in entries:
        if not isinstance(item,dict):raise RuntimeError("ORDERS_BAD_RESEARCH_ENTRY")
        ident=item.get("product_id")
        if not isinstance(ident,int) or isinstance(ident,bool) or ident<1:
            raise RuntimeError("ORDERS_BAD_RESEARCH_PRODUCT_ID")
        rev=item.get("sha256")
        if not isinstance(rev,str) or not HASH_RE.fullmatch(rev):
            raise RuntimeError("ORDERS_BAD_RESEARCH_REVISION")
        gate=item.get("research_quality_gate")
        if not isinstance(gate,dict) or gate.get("schema")!="saeit.factory.research-readiness.v1":
            raise RuntimeError("ORDERS_BAD_RESEARCH_GATE")
        blockers=gate.get("blockers",[])
        if not isinstance(blockers,list) or any(b not in BLOCKER_ACTIONS for b in blockers):
            raise RuntimeError("ORDERS_UNKNOWN_QA_BLOCKER")
        base={"origin":"local-factory-research", "source_product_id":ident,
              "source_sha256":rev, "technical_product_release":False}
        if gate.get("research_gate_passed") is True and not blockers:
            tasks.append(dict(base,phase="engineering",slot=1,
               subject="Design testable prototype manufacturing recipe",
               instruction="Produce an executable recipe specification, material list, reproducible tests and acceptance criteria. This instruction does not itself constitute a finished product.",
               acceptance=["Versioned real source files","Repeatable functional tests",
                           "Explicit failure and rework path","No marketing or site distribution"]))
            continue
        for blocker in sorted(set(blockers)):
            title,n,act=BLOCKER_ACTIONS[blocker]
            for slot in range(1,n+1):
                tasks.append(dict(base,phase="research_rework",
                    blocker=blocker,slot=slot,subject=title+" — part "+str(slot)+"/"+str(n),
                    instruction=act,acceptance=[
                        "Attach real independently checkable evidence",
                        "Document tested result and outstanding gaps",
                        "Do not claim research/quality approval without proof",
                        "Preserve findings for the next QA/rework pass"]))
    return tasks

def local_input_tasks(root):
    """Four user-defined demand channels; *offline snapshots only*, never queries websites."""
    incoming=root/"production-order-inputs"
    if not incoming.is_dir():return []
    if incoming.is_symlink():raise RuntimeError("ORDERS_UNSAFE_INPUT_DIR")
    result=[]
    for kind in SOURCES:
        file=incoming/(kind+".json")
        if not file.exists():continue
        snapshot=read_json(file,max_bytes=2_000_000)
        records=snapshot.get("items",[])
        if snapshot.get("schema")!=SCHEMA or not isinstance(records,list):
            raise RuntimeError("ORDERS_INVALID_OFFLINE_INPUT:"+kind)
        for item in records:
            if not isinstance(item,dict):raise RuntimeError("ORDERS_INVALID_SOURCE_ITEM")
            key=item.get("id");title=item.get("title");details=item.get("specification")
            if (not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,64}",key)
                    or not isinstance(title,str) or not 8<=len(title)<=160
                    or not isinstance(details,str) or not 30<=len(details)<=3000):
                raise RuntimeError("ORDERS_INCOMPLETE_SOURCE_ENTRY:"+kind)
            # Customer & external market assertions remain unverified snapshots.
            result.append({"origin":kind,"source_product_id":key,
                "source_sha256":checksum({"id":key,"title":title,"specification":details}),
                "phase":"engineering_specification","slot":1,"subject":title,
                "instruction":details, "technical_product_release":False,
                "acceptance":["Design and test a concrete implementable recipe",
                              "Verify all third-party facts and ownership",
                              "Record reproducible quality results",
                              "Do not transfer or publish goods automatically"]})
    return result

def fingerprint(task):
    return checksum({k:v for k,v in task.items() if k!="acceptance"})

def validate_old(p):
    record=read_json(p,max_bytes=100_000)
    if record.get("schema")!=SCHEMA or record.get("id")!=p.stem:
        raise RuntimeError("ORDERS_EXISTING_RECORD_INVALID")
    if record.get("public_distribution_allowed") is not False:
        raise RuntimeError("ORDERS_EXISTING_RECORD_UNSAFE")
    status=record.get("status")
    if status not in ("issued","in_engineering","blocked_rework","completed_verified"):
        raise RuntimeError("ORDERS_BAD_WORK_STATE")
    if not HASH_RE.fullmatch(str(record.get("fingerprint",""))):
        raise RuntimeError("ORDERS_BAD_RECORD_FINGERPRINT")
    return record

def consumes_research_capacity(item):
    """Only independently blocked research uses the research quota.

    Unknown or partially described work still consumes manufacturing capacity.
    Preserve all existing work orders and their original status.
    """
    return (item.get("phase")=="research_rework"
            and item.get("origin")=="local-factory-research"
            and isinstance(item.get("blocker"),str)
            and bool(item["blocker"].strip())
            and item.get("requesting_site") is None)

def is_owner_agri_p0(item):
    """Separately budget owner-priority bilingual booklets, preserving existing lanes."""
    return (item.get("origin")=="owner_requested_agri200_p0"
            and item.get("priority")=="P0"
            and re.fullmatch(r"AGRI-[0-9]{3}",str(item.get("source_product_id",""))) is not None)

def stage1_handed_off(area, item):
    """Only a matching stage-1 receipt frees intake quota, not downstream QA.

    This deliberately never probes stage 2's progress, capacity or availability.
    """
    name = item["id"] + "--r001.json"
    receipt = area / "stage-01" / "receipts" / name
    if not receipt.exists():
        return False
    doc = read_json(receipt, max_bytes=20_000)
    if (doc.get("schema") != "saeit.factory.stage-handoff.v1"
            or doc.get("order_id") != item["id"]
            or doc.get("revision") != 1
            or doc.get("stage_1_completed") is not True
            or doc.get("source_order_sha256") != checksum(item)
            or not HASH_RE.fullmatch(str(doc.get("stage_2_packet_sha256", "")))):
        raise RuntimeError("ORDERS_STAGE1_RECEIPT_MISMATCH:" + name)
    return True


def generate(root,max_backlog=None):
    # Keep the legacy argument for old callers; intake no longer has a backlog cap.
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError("ORDERS_FACTORY_ROOT_MISSING")
    area=root/"production-instructions"
    ensure_private(area)
    orders=area/"orders"
    ensure_private(orders)
    with (area/".orders.lock").open("a+b") as lock:
        os.chmod(str(area/".orders.lock"),0o600)
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:return {"action":"already_running","pending":0}
        old=[]
        for file in sorted(orders.iterdir()):
            if file.is_symlink() or not file.is_file() or not ORDER_RE.fullmatch(file.name):
                raise RuntimeError("ORDERS_UNEXPECTED_FILE")
            old.append(validate_old(file))
        # Keep lane counts for observability only. Intake is intentionally unbounded;
        # later stages advance work independently on their recurring cadence.
        pending=[x for x in old if x["status"]=="issued" and not stage1_handed_off(area,x)]
        research_pending=sum(consumes_research_capacity(x) for x in pending)
        owner_p0_pending=sum(is_owner_agri_p0(x) for x in pending)
        manufacturing_pending=len(pending)-research_pending-owner_p0_pending
        active=len(pending)
        downstream_count=len(old)-sum(x["status"]=="completed_verified" for x in old)-active
        # Source-originated engineering briefs take priority over speculative
        # backlog tasks. Fingerprints still enforce exactly-once issuance.
        candidates=local_input_tasks(root)+local_research_tasks(root)
        seen={x["fingerprint"] for x in old}
        selected=None
        for task in candidates:
            key=fingerprint(task)
            if key in seen:continue
            research=consumes_research_capacity(task)
            selected=(task,key,research)
            break
        action="issued" if selected else "no_new_meaningful_input"
        order_id=None
        if selected:
            task,key,is_research=selected
            serial=max((int(x["id"].split("-")[1]) for x in old),default=0)+1
            order_id="WO-"+str(serial).zfill(8)
            record=dict(task,
                schema=SCHEMA,id=order_id,fingerprint=key,created_utc=stamp(),
                status="issued",instruction_kind="private_factory_work_order",
                independent_of_websites=True,requires_customer_order=False,
                api_required=False,manufacturing_qa_passed=False,
                publication_approved=False,public_distribution_allowed=False,
                warehouse_goods_created=False)
            dest=orders/(order_id+".json")
            if dest.exists() or dest.is_symlink():raise RuntimeError("ORDERS_NUMBER_COLLISION")
            atomic_json(dest,record)
            active+=1
            if is_research:research_pending+=1
            else:manufacturing_pending+=1
        report={"schema":SCHEMA,"last_scan_utc":stamp(),"last_action":action,
                "last_order":order_id,"instructions_issued_total":len(old)+int(bool(selected)),
                "pending_instructions":active,
                "pending_stage1_instructions":active,
                "pending_downstream_or_rework_instructions":downstream_count,
                "stage1_capacity_independent_of_stage2":True,
                "pending_research_instructions":research_pending,
                "pending_manufacturing_instructions":manufacturing_pending,
                "pending_owner_agri_p0_instructions":owner_p0_pending,
                "research_capacity_available":None,
                "manufacturing_capacity_available":None,
                "unbounded_intake":True,
                "candidate_instructions":len(candidates),
                "site_connection_required":False,"customer_order_required":False,
                "distribution_enabled":False,"production_warehouse_unmodified":True}
        atomic_json(area/"order-status.json",report)
        return {"action":action,"pending":active,"id":order_id,"candidate":len(candidates)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--factory-private",required=True)
    args=ap.parse_args()
    state=generate(args.factory_private)
    print("FACTORY_PRODUCTION_INSTRUCTION_ACTION="+state["action"])
    print("FACTORY_PRODUCTION_INSTRUCTION_ID="+str(state.get("id") or "none"))
    print("FACTORY_PRODUCTION_INSTRUCTIONS_PENDING="+str(state["pending"]))
    print("FACTORY_SITE_DEPENDENCY=false")
    print("FACTORY_AUTOMATIC_DISTRIBUTION=false")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("FACTORY_INSTRUCTION_ERROR="+type(e).__name__+":"+str(e)[:260],file=sys.stderr)
        sys.exit(1)
