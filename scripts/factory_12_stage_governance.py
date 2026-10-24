# Accept unbounded factory work-order serials throughout governance intake.
#!/usr/bin/env python3
"""VPS-local 12-stage digital factory governance and release gate.

No network, customer checkout, automated human attestations or storefront write.
Existing technical QA goods remain preserved; they are NOT final goods.
Each approved stage needs an actual evidence file and independently verifiable
review record. This is a control plane, not an LLM pretending to make products.
Python 3.8+ stdlib.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
import zipfile

SCHEMA="saeit.factory.lifecycle.v1"
REVIEW_SCHEMA="saeit.factory.stage-review.v1"
SPEC_SCHEMA="saeit.factory.product-passport.v1"
ORDER_RE=re.compile(r"^WO-[0-9]+$")
SHA_RE=re.compile(r"^[0-9a-f]{64}$")
STAGES=(
    "idea_assessment","research","design","prototype","complete_manufacture",
    "expert_review","practical_test","correction","packaging","final_quality_approval",
    "finished_goods_warehouse","distribution",
)
TYPES={
    "book_report_article":("source_authenticity","coherence","originality","examples","editing","layout"),
    "course":("learning_objectives","sequence","exercises","answers","learning_assessment"),
    "software":("real_execution","correctness","security","error_handling","documentation"),
    "website_template_plugin":("responsive","accessibility","compatibility","performance","install_guide"),
    "game":("full_playthrough","rules","levels","asset_rights","progress_persistence_if_applicable"),
    "graphics":("actual_dimensions","visual_review","image_defects","format","asset_license"),
    "audiovisual":("complete_playback","audio_quality","visual_quality","synchronization","caption_if_applicable","rights"),
    "dataset":("provenance","license","schema","accuracy","duplicates","privacy","data_dictionary"),
    "spreadsheet":("formula_accuracy","units","invalid_input","examples","instructions"),
    "ai_workflow":("diverse_examples","dependencies","output_limitations","reproducibility"),
    "three_dimensional":("opens","mesh","textures","scale","software_compatibility"),
}
REQUIRED_SPEC={
    "work_order","title","product_type","version","origin","target_audience",
    "problem_solved","deliverables","file_formats","language","scope",
    "prerequisites","acceptance_criteria","sources","asset_licenses",
    "technical_dependencies","stages_and_owners","resource_budget",
    "sensitivity","producer_id","independent_reviewer_id","human_review_required",
}
REQUIRED_PACKAGE=(
    "product/","guide/","preview/","license/","requirements/",
    "qa/","description/","images/",
)
MAX_DEFECT_ROUNDS=3
MAX_UPLOAD=80*1024*1024
MAX_ZIP_ENTRIES=1000
MAX_ZIP_UNCOMPRESSED_BYTES=240*1024*1024
MAX_ZIP_RATIO=120

def signed_review_message(review):
    payload={key:value for key,value in review.items() if key!="reviewer_signature"}
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,
                      separators=(",",":")).encode("utf8")

def verify_reviewer_signature(root, review):
    """Independent reviewers must possess an out-of-band provisioned secret.

    This HMAC does not prove a person's professional qualifications: the
    identity-to-key assignment must be verified by a separate trusted operator.
    An arbitrary JSON `human_attestation:true` can no longer self-authorize.
    """
    keys=root/"product-lifecycle"/"reviewer-keys.json"
    if not keys.is_file() or keys.is_symlink() or (keys.stat().st_mode & 0o077):
        raise RuntimeError("REVIEWER_SECRET_STORE_MISSING_OR_INSECURE")
    mapping=json_read(keys,100000)
    if mapping.get("schema")!="saeit.factory.reviewer-keys.v1":
        raise RuntimeError("REVIEWER_SECRET_SCHEMA_INVALID")
    key=mapping.get("reviewers",{}).get(review.get("reviewer_id"))
    sig=review.get("reviewer_signature")
    if not isinstance(key,str) or not re.fullmatch(r"[a-f0-9]{64,128}",key):
        raise RuntimeError("REVIEWER_NOT_ENROLLED")
    if not isinstance(sig,str) or not SHA_RE.fullmatch(sig):
        raise RuntimeError("REVIEWER_SIGNATURE_REQUIRED")
    expected=hmac.new(bytes.fromhex(key),signed_review_message(review),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,sig):
        raise RuntimeError("REVIEWER_SIGNATURE_MISMATCH")

def verify_final_package_zip(artifact):
    """Reject zip bombs, duplicates, symlinks and traversal before decompression."""
    with zipfile.ZipFile(artifact,"r") as archive:
        members=archive.infolist()
        if not members or len(members)>MAX_ZIP_ENTRIES:
            raise RuntimeError("FINAL_ZIP_TOO_MANY_ENTRIES")
        names=set()
        unpacked=0
        for entry in members:
            name=entry.filename
            path=PurePosixPath(name)
            if (not name or name in names or "\\" in name or path.is_absolute()
                    or ".." in path.parts or name.startswith(".") or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or entry.flag_bits & 1):
                raise RuntimeError("FINAL_WAREHOUSE_UNSAFE_ZIP")
            names.add(name)
            unpacked+=entry.file_size
            if (entry.file_size<0 or unpacked>MAX_ZIP_UNCOMPRESSED_BYTES
                    or (entry.file_size>1024*1024 and
                        entry.file_size/max(entry.compress_size,1)>MAX_ZIP_RATIO)):
                raise RuntimeError("FINAL_ZIP_DECOMPRESSION_LIMIT")
        for required in REQUIRED_PACKAGE:
            if not any(x.startswith(required) and len(x)>len(required)
                       and not x.endswith("/") for x in names):
                raise RuntimeError("FINAL_WAREHOUSE_MISSING_SECTION:"+required)
        if archive.testzip() is not None:
            raise RuntimeError("FINAL_ZIP_CRC_FAILED")

def verify_persisted_approvals(root, order, record):
    """Revalidate all ten saved review hashes and specialist authorizations."""
    receipts=record.get("review_receipts",[])
    if not isinstance(receipts,list) or len(receipts)!=10:
        raise RuntimeError("FINAL_REVIEW_RECEIPT_COUNT_INVALID")
    for stage in range(1,11):
        receipt=receipts[stage-1]
        if not isinstance(receipt,dict) or receipt.get("stage")!=stage or receipt.get("decision")!="pass":
            raise RuntimeError("FINAL_STAGE_APPROVAL_MISSING")
        digest=receipt.get("sha256")
        if not isinstance(digest,str) or not SHA_RE.fullmatch(digest):
            raise RuntimeError("FINAL_REVIEW_HASH_INVALID")
        file=area(root)/"review-receipts"/order/("stage-"+str(stage)+"-"+digest+".json")
        if sha(file)!=digest:
            raise RuntimeError("FINAL_REVIEW_RECEIPT_TAMPERED")
        saved=json_read(file)
        if saved.get("order")!=order or saved.get("stage")!=stage or saved.get("decision")!="pass":
            raise RuntimeError("FINAL_REVIEW_RECEIPT_WRONG_STAGE")
        if stage in (6,10):
            verify_reviewer_signature(root,saved)

MAX_ORDERS=15000

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
def hash_bytes(blob):
    return hashlib.sha256(blob).hexdigest()
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()
def dirs(path):
    if path.is_symlink():raise RuntimeError("LIFECYCLE_SYMLINK_DIRECTORY")
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not path.is_dir() or path.is_symlink():raise RuntimeError("LIFECYCLE_UNSAFE_DIRECTORY")
    os.chmod(str(path),0o700)
def json_read(path,size=3*1024*1024):
    if not path.is_file() or path.is_symlink() or path.stat().st_size>size:
        raise RuntimeError("LIFECYCLE_BAD_SOURCE:"+path.name)
    obj=json.loads(path.read_text(encoding="utf8"))
    if not isinstance(obj,dict):raise RuntimeError("LIFECYCLE_EXPECTED_OBJECT")
    return obj
def atomic(path,obj):
    dirs(path.parent)
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    fd,stage=tempfile.mkstemp(prefix=".lifecycle-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.chmod(stage,0o600)
        os.replace(stage,str(path))
    finally:
        if os.path.exists(stage):os.unlink(stage)
def under(root, relative):
    if not isinstance(relative,str) or not relative or relative.startswith("/") or "\\" in relative:
        raise RuntimeError("LIFECYCLE_UNSAFE_RELATIVE_PATH")
    bits=PurePosixPath(relative)
    if ".." in bits.parts or bits.is_absolute() or "." in bits.parts:
        raise RuntimeError("LIFECYCLE_UNSAFE_RELATIVE_PATH")
    path=root.joinpath(*bits.parts)
    # No symlink in any component; don't use resolve to silently follow one.
    item=root
    for part in bits.parts:
        item=item/part
        if item.is_symlink():raise RuntimeError("LIFECYCLE_SYMLINK_SOURCE")
    return path
def verify_evidence_files(root, evidence):
    if not isinstance(evidence,list) or not evidence or len(evidence)>20:
        raise RuntimeError("LIFECYCLE_MISSING_REAL_EVIDENCE")
    for ref in evidence:
        if not isinstance(ref,dict) or not SHA_RE.fullmatch(str(ref.get("sha256",""))):
            raise RuntimeError("LIFECYCLE_EVIDENCE_SHA_REQUIRED")
        path=under(root,ref.get("path"))
        if not path.is_file() or path.stat().st_size==0 or path.stat().st_size>MAX_UPLOAD:
            raise RuntimeError("LIFECYCLE_EVIDENCE_NOT_REAL")
        if sha(path)!=ref["sha256"]:
            raise RuntimeError("LIFECYCLE_EVIDENCE_HASH_MISMATCH")
def passport_validate(p,work_id):
    if p.get("schema")!=SPEC_SCHEMA or p.get("work_order")!=work_id:
        raise RuntimeError("PASSPORT_WRONG_SCHEMA_OR_ID")
    if any(k not in p or p[k] is None or p[k]=="" for k in REQUIRED_SPEC):
        raise RuntimeError("PASSPORT_FIELDS_INCOMPLETE")
    if p["product_type"] not in TYPES:
        raise RuntimeError("PASSPORT_UNKNOWN_TYPE_DEFINE_QA_FIRST")
    if p["origin"] not in ("site_need","customer_request","market_demand","factory_invention","local_factory_research"):
        raise RuntimeError("PASSPORT_UNKNOWN_ORIGIN")
    for key in ("title","version","target_audience","problem_solved","language",
                "scope","resource_budget","sensitivity","producer_id","independent_reviewer_id"):
        if not isinstance(p[key],str) or len(p[key].strip())<2 or len(p[key])>1500:
            raise RuntimeError("PASSPORT_BAD_FIELD:"+key)
    for key in ("deliverables","file_formats","prerequisites","acceptance_criteria","sources",
                "asset_licenses","technical_dependencies","stages_and_owners"):
        if not isinstance(p[key],list) or not p[key] or len(p[key])>100:
            raise RuntimeError("PASSPORT_LIST_REQUIRED:"+key)
        if any(not isinstance(x,str) or not x.strip() or len(x)>1500 for x in p[key]):
            raise RuntimeError("PASSPORT_BAD_LIST:"+key)
    if p["producer_id"]==p["independent_reviewer_id"] or p["human_review_required"] is not True:
        raise RuntimeError("PASSPORT_INDEPENDENT_HUMAN_REVIEW_REQUIRED")
    if any(str(k).lower().startswith("example_placeholder") for k in p):
        raise RuntimeError("PASSPORT_PLACEHOLDER_FORBIDDEN")
    return True
def blank_order(work_id,source):
    return {"schema":SCHEMA,"id":work_id,"created_utc":now(),
            "source_instruction_fingerprint":source["fingerprint"],
            "source_instruction_status":source["status"],
            "stage_status":{str(i):"pending" for i in range(1,13)},
            "current_stage":1,"status":"awaiting_complete_passport",
            "review_receipts":[],"defects":[],"revision":1,
            "commercial_release":False,"distribution_enabled":False,
            "final_warehouse_id":None,"last_checked_utc":now(),"stage_entered_utc":now()}
def area(root):return root/"product-lifecycle"
def record_path(root,order):return area(root)/"records"/(order+".json")
def spec_path(root,order):return area(root)/"passports"/(order+".json")
def safe_order(order):
    if not isinstance(order,str) or not ORDER_RE.fullmatch(order):
        raise RuntimeError("LIFECYCLE_INVALID_ORDER")
    return order
def load_order(root,order):
    safe_order(order)
    d=json_read(record_path(root,order))
    if d.get("schema")!=SCHEMA or d.get("id")!=order:
        raise RuntimeError("LIFECYCLE_CORRUPT_ORDER")
    return d
def count_stages(record):
    done=record["stage_status"]
    return len([x for x in range(1,11) if done.get(str(x))=="passed"])
def unresolved(record):
    return [d for d in record.get("defects",[]) if d["status"]!="resolved"]
def valid_approval(root,order,review,record):
    if review.get("schema")!=REVIEW_SCHEMA or review.get("order")!=order:
        raise RuntimeError("REVIEW_BAD_SCHEMA")
    stage=review.get("stage")
    if isinstance(stage,bool) or not isinstance(stage,int) or stage not in range(1,11):
        raise RuntimeError("REVIEW_INVALID_STAGE")
    if review.get("decision") not in ("pass","fail"):
        raise RuntimeError("REVIEW_BAD_DECISION")
    current=record["current_stage"]
    if stage!=current:
        raise RuntimeError("REVIEW_OUT_OF_SEQUENCE")
    passport=json_read(spec_path(root,order))
    passport_validate(passport,order)
    if review.get("passport_sha256")!=sha(spec_path(root,order)):
        raise RuntimeError("REVIEW_PASSPORT_VERSION_CHANGED")
    if not isinstance(review.get("reviewer_id"),str) or not review["reviewer_id"].strip():
        raise RuntimeError("REVIEWER_REQUIRED")
    if not isinstance(review.get("producer_id"),str) or review["producer_id"]!=passport["producer_id"]:
        raise RuntimeError("REVIEW_PRODUCER_MISMATCH")
    if stage in (6,10):
        if (review.get("reviewer_id")!=passport["independent_reviewer_id"]
                or review.get("reviewer_id")==passport["producer_id"]
                or review.get("reviewer_role") not in ("qualified_specialist","human_approver")):
            raise RuntimeError("REVIEW_INDEPENDENT_PERSON_REQUIRED")
        if review.get("human_attestation") is not True:
            raise RuntimeError("REVIEW_HUMAN_ATTESTATION_REQUIRED")
    checks=review.get("checks",[])
    if not isinstance(checks,list) or not checks or any(
            not isinstance(item,dict) or item.get("status") not in ("passed","failed")
            or not isinstance(item.get("id"),str) or not item["id"] for item in checks):
        raise RuntimeError("REVIEW_REAL_CHECKS_REQUIRED")
    if stage in (6,7,9,10) and review["decision"]=="pass":
        required=set(TYPES[passport["product_type"]])
        done={item["id"] for item in checks if item["status"]=="passed"}
        if not required.issubset(done):
            raise RuntimeError("REVIEW_FAMILY_QA_CHECKS_MISSING")
    evidence=review.get("evidence_files")
    verify_evidence_files(root,evidence)
    if stage in (6,10) and review["decision"]=="pass":
        verify_reviewer_signature(root,review)
    if review["decision"]=="pass":
        if any(x["status"]!="passed" for x in checks):
            raise RuntimeError("REVIEW_FAILED_CHECK_CANNOT_PASS")
        if unresolved(record):
            raise RuntimeError("REVIEW_OPEN_DEFECTS")
    else:
        defect=review.get("defect")
        if not isinstance(defect,dict) or any(
            not isinstance(defect.get(key),str) or len(defect[key].strip())<3
            for key in ("description","severity","likely_cause","corrective_action","retest_criteria")):
            raise RuntimeError("REVIEW_DEFECT_DETAILS_REQUIRED")
        if defect["severity"] not in ("low","medium","high","critical"):
            raise RuntimeError("REVIEW_DEFECT_SEVERITY_INVALID")
    return stage
def tick(root):
    root=Path(root).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():raise RuntimeError("LIFECYCLE_PRIVATE_ROOT_MISSING")
    base=area(root)
    dirs(base);dirs(base/"records");dirs(base/"passports");dirs(base/"review-receipts")
    with (base/".lifecycle.lock").open("a+b") as lock:
        os.chmod(str(base/".lifecycle.lock"),0o600)
        try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:return {"status":"already_running"}
        source=root/"production-instructions"/"orders"
        if not source.is_dir() or source.is_symlink():
            raise RuntimeError("LIFECYCLE_NO_INSTRUCTIONS")
        counts=Counter()
        count=0
        new=0
        blockers=Counter()
        stage_counts=Counter()
        origin_counts=Counter()
        defect_count=0
        stalled_over_day=0
        research_only_orders=0
        for filename in sorted(source.iterdir()):
            if filename.is_symlink() or not filename.is_file() or not ORDER_RE.fullmatch(filename.stem) or filename.suffix!=".json":
                raise RuntimeError("LIFECYCLE_UNEXPECTED_INSTRUCTION")
            count+=1
            if count>MAX_ORDERS:raise RuntimeError("LIFECYCLE_TOO_MANY_INSTRUCTIONS")
            item=json_read(filename)
            wid=safe_order(filename.stem)
            if item.get("id")!=wid or item.get("status") not in ("issued","in_engineering","blocked_rework","completed_verified"):
                raise RuntimeError("LIFECYCLE_UNRECOGNIZED_INSTRUCTION")
            record=record_path(root,wid)
            if not record.exists():
                atomic(record,blank_order(wid,item))
                new+=1
            state=load_order(root,wid)
            passfile=spec_path(root,wid)
            origin_counts[str(item.get("origin","unclassified"))]+=1
            stage_counts[str(state.get("current_stage",1))]+=1
            defect_count+=sum(d.get("status")!="resolved" for d in state.get("defects",[]))
            try:
                entered=datetime.fromisoformat(state.get("stage_entered_utc",state["created_utc"]))
                stalled_over_day+=int((datetime.now(timezone.utc)-entered).total_seconds()>86400
                                      and state["status"]!="in_finished_goods_warehouse_not_distributed")
            except (ValueError,TypeError,KeyError):pass
            # Research rework instructions describe evidence collection, not
            # manufacturable goods. Do not mislabel them as missing passports
            # or promote them into the product manufacturing pipeline.
            if item.get("phase")=="research_rework":
                if (item.get("origin")!="local-factory-research"
                        or not isinstance(item.get("blocker"),str)
                        or not item.get("blocker")):
                    raise RuntimeError("LIFECYCLE_RESEARCH_TASK_PROVENANCE_INVALID")
                research_only_orders+=1
                blockers["research_evidence_not_verified"]+=1
                counts["research_rework_pending_evidence"]+=1
                continue
            if not passfile.exists():
                blockers["missing_product_passport"]+=1
                counts["awaiting_complete_passport"]+=1
            else:
                try:
                    passport_validate(json_read(passfile),wid)
                except (RuntimeError,KeyError,ValueError):
                    blockers["invalid_product_passport"]+=1
                    counts["awaiting_complete_passport"]+=1
                    continue
                counts[state["status"]]+=1
        # Old technical-QA packages have NOT been released into this final stockroom.
        technical=root/"production-warehouse"/"stock-register.json"
        tech_versions=0
        if technical.exists():
            legacy=json_read(technical,size=10_000_000)
            tech_versions=legacy.get("finished_goods_versions",0)
            if not isinstance(tech_versions,int) or tech_versions<0:
                raise RuntimeError("LIFECYCLE_BAD_TECH_STOCK_COUNT")
        final=base/"approved-finished-goods"
        dirs(final)
        ready=sum(1 for f in final.iterdir() if f.is_dir() and not f.is_symlink())
        report={"schema":SCHEMA,"as_of_utc":now(),
                "stages":[{"number":i,"name":name,"description":(
                    "manual distribution disabled" if i==12 else "evidence and independent QA required")}
                    for i,name in enumerate(STAGES,1)],
                "instructions_seen":count,"newly_tracked":new,
                "research_only_work_orders":research_only_orders,
                "manufacturing_related_work_orders":count-research_only_orders,
                "research_tasks_not_automatically_manufacturable":True,
                "workorder_status":dict(counts),"blocked_reasons":dict(blockers),
                "by_production_origin":dict(origin_counts),
                "orders_by_stage":dict(stage_counts),
                "open_defects":defect_count,
                "orders_stalled_over_24h":stalled_over_day,
                "per_order_resource_metrics_available":False,
                "old_technical_QA_stock_pending_final_review":tech_versions,
                "final_commercially_verified_stock":ready,
                "site_distribution_enabled":False,"sites_contacted":0,
                "manufacturing_order_automation_complete":False,
                "independent_quality_gate_enforced":True,
                "automatic_research_claims":False}
        atomic(base/"dashboard.json",report)
        return report
def import_passport(root,work_id,source):
    wid=safe_order(work_id);root=Path(root).expanduser().resolve()
    data=json_read(Path(source))
    passport_validate(data,wid)
    path=spec_path(root,wid)
    if path.exists():raise RuntimeError("PASSPORT_IMMUTABLE_USE_NEW_PRODUCT_REVISION")
    if not record_path(root,wid).is_file():
        raise RuntimeError("PASSPORT_UNKNOWN_WORK_ORDER")
    atomic(path,data)
    state=load_order(root,wid)
    state["status"]="waiting_stage_1_evidence"
    state["stage_entered_utc"]=now()
    atomic(record_path(root,wid),state)
    return path
def review(root,order,evidence_input):
    root=Path(root).expanduser().resolve()
    wid=safe_order(order)
    state=load_order(root,wid)
    input_file=Path(evidence_input)
    receipt=json_read(input_file)
    stage=valid_approval(root,wid,receipt,state)
    # Hash the exact canonical bytes persisted by atomic() rather than the
    # differently formatted external input receipt: otherwise final verification
    # always reports false tampering even for legitimately approved stages.
    canonical=(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    evidence_hash=hash_bytes(canonical)
    receipt_dir=area(root)/"review-receipts"/wid
    dirs(receipt_dir)
    dest=receipt_dir/("stage-"+str(stage)+"-"+evidence_hash+".json")
    if dest.exists():raise RuntimeError("REVIEW_RECEIPT_ALREADY_RECORDED")
    if receipt["decision"]=="fail":
        existing=[d for d in state["defects"] if d["stage"]==stage]
        new_defect=dict(receipt["defect"],stage=stage,round=len(existing)+1,
                        status="expert_review" if len(existing)+1>=MAX_DEFECT_ROUNDS else "open",
                        created_utc=now(),evidence_hash=evidence_hash)
        state["defects"].append(new_defect)
        state["status"]="expert_review" if new_defect["status"]=="expert_review" else "rework_required"
        state["stage_status"][str(stage)]="failed"
        state["stage_entered_utc"]=now()
    else:
        state["stage_status"][str(stage)]="passed"
        state["current_stage"]=stage+1
        state["stage_entered_utc"]=now()
        state["status"]="waiting_stage_"+str(stage+1)+"_evidence" if stage<10 else "awaiting_final_warehouse_admission"
    state["review_receipts"].append({"stage":stage,"decision":receipt["decision"],
                                    "sha256":evidence_hash,"reviewer":receipt["reviewer_id"],
                                    "recorded_utc":now()})
    atomic(dest,receipt)
    atomic(record_path(root,wid),state)
    return state
def resolve_defect(root,order,source):
    root=Path(root).expanduser().resolve()
    state=load_order(root,safe_order(order))
    if state["status"]=="expert_review":
        raise RuntimeError("DEFECT_EXPERT_REVIEW_REQUIRED")
    outstanding=unresolved(state)
    if not outstanding:raise RuntimeError("DEFECT_NONE_OPEN")
    latest=outstanding[-1]
    doc=json_read(Path(source))
    if doc.get("schema")!=REVIEW_SCHEMA or doc.get("order")!=order or doc.get("stage")!=latest["stage"]:
        raise RuntimeError("DEFECT_WRONG_RESOLUTION")
    if doc.get("corrective_action_completed") is not True or doc.get("affected_area_regression_passed") is not True:
        raise RuntimeError("DEFECT_RETEST_NOT_COMPLETED")
    verify_evidence_files(root,doc.get("evidence_files"))
    latest["status"]="resolved"
    latest["resolved_utc"]=now()
    latest["resolution_sha256"]=sha(Path(source))
    state["status"]="waiting_stage_"+str(state["current_stage"])+"_retest"
    state["stage_status"][str(state["current_stage"])]="pending_retest"
    atomic(record_path(root,order),state)
    return state
def final_admit(root,order,package):
    root=Path(root).expanduser().resolve()
    wid=safe_order(order)
    data=load_order(root,wid)
    passport=json_read(spec_path(root,wid))
    passport_validate(passport,wid)
    if any(data["stage_status"][str(i)]!="passed" for i in range(1,11)):
        raise RuntimeError("FINAL_WAREHOUSE_TEN_GATES_NOT_PASSED")
    if unresolved(data) or data["status"]!="awaiting_final_warehouse_admission":
        raise RuntimeError("FINAL_WAREHOUSE_OPEN_DEFECT_OR_WRONG_STATE")
    if passport["human_review_required"] is not True:
        raise RuntimeError("FINAL_WAREHOUSE_HUMAN_REVIEW_REQUIRED")
    verify_persisted_approvals(root,wid,data)
    # Live archive must be under factory private root and include all distinct
    # required categories, e.g. docs, preview and QA report (not empty folders).
    artifact=under(root,package)
    if not artifact.is_file() or artifact.stat().st_size>MAX_UPLOAD or artifact.suffix!=".zip":
        raise RuntimeError("FINAL_WAREHOUSE_ARTIFACT_INVALID")
    verify_final_package_zip(artifact)
    house=area(root)/"approved-finished-goods"/wid
    if house.exists():raise RuntimeError("FINAL_WAREHOUSE_EXISTING_VERSION")
    dirs(house.parent)
    temp=Path(tempfile.mkdtemp(prefix=".final-stock-",dir=str(house.parent)))
    try:
        os.chmod(temp,0o700)
        dest=temp/"product.zip"
        with artifact.open("rb") as sf,dest.open("xb") as df:
            shutil.copyfileobj(sf,df,1024*1024)
            df.flush();os.fsync(df.fileno())
        if sha(dest)!=sha(artifact):raise RuntimeError("FINAL_WAREHOUSE_COPY_HASH_MISMATCH")
        os.chmod(dest,0o400)
        atomic(temp/"receipt.json",{"schema":SCHEMA,"order":wid,
              "passport_sha256":sha(spec_path(root,wid)),
              "artifact_sha256":sha(artifact),"bytes":artifact.stat().st_size,
              "stage_gates_passed":10,
              "human_reviewer":passport["independent_reviewer_id"],
              "commercial_review_documented":True,"distributed":False,
              "sites_contacted":0,"approved_utc":now()})
        temp.rename(house)
        data["stage_status"]["11"]="passed"
        data["status"]="in_finished_goods_warehouse_not_distributed"
        data["final_warehouse_id"]=wid
        atomic(record_path(root,wid),data)
        return house
    finally:
        if temp.exists():shutil.rmtree(temp)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--factory-private",required=True)
    q=p.add_mutually_exclusive_group()
    q.add_argument("--tick",action="store_true")
    q.add_argument("--import-passport",metavar="FILE")
    q.add_argument("--record-review",metavar="FILE")
    q.add_argument("--resolve-defect",metavar="FILE")
    q.add_argument("--admit-final",metavar="RELATIVE_ZIP")
    p.add_argument("--order")
    v=p.parse_args()
    if v.import_passport:result={"passport_path":str(import_passport(v.factory_private,v.order,v.import_passport))}
    elif v.record_review:result={"status":review(v.factory_private,v.order,v.record_review)["status"]}
    elif v.resolve_defect:result={"status":resolve_defect(v.factory_private,v.order,v.resolve_defect)["status"]}
    elif v.admit_final:result={"final_path":str(final_admit(v.factory_private,v.order,v.admit_final))}
    else:result=tick(v.factory_private)
    print("FACTORY_12_STAGE_RESULT="+json.dumps(result,ensure_ascii=False,sort_keys=True))
    print("FACTORY_WEBSITE_TRANSFER_ENABLED=false")
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("FACTORY_12_STAGE_ERROR="+str(exc)[:400],file=sys.stderr)
        sys.exit(1)
