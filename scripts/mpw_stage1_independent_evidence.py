#!/usr/bin/env python3
"""Produce genuine per-version independent technical prescreens and OPEN human review dossiers.

Never impersonates a reviewer or releases a product. Reads the actual
MojPlayWin Stage-1 returns plus cryptographically verified immutable stock.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

SCHEMA="mpw.factory.stage1-review-dossier.v1"
SUMMARY="mpw.factory.stage1-review-dossier-summary.v1"
REVIEW_CODES={
 "INDEPENDENT_CONTENT_QUALITY_REVIEW_REQUIRED":{
   "role":"qualified_independent_domain_reviewer",
   "evidence_needed":["identified reviewer credentials and conflict disclosure",
                      "dated evaluation of real product contents and real consumer use",
                      "recorded sample results, severity and signed acceptance decision"]},
 "OWNERSHIP_AND_ASSET_LICENSE_REVIEW_REQUIRED":{
   "role":"authorized_ip_and_licensing_reviewer",
   "evidence_needed":["authentic origin/ownership for each source asset",
                      "terms and grants for all third-party components",
                      "rights for exact product version and intended commercial territory"]},
 "COMMERCIAL_PUBLICATION_APPROVAL_REQUIRED":{
   "role":"authenticated_company_owner_or_delegated_release_manager",
   "evidence_needed":["approved version and final price/currency",
                      "actual checkout payment settlement and refund delivery tests",
                      "dated owner authorization scoped to the exact digest/version"]}}
def require(ok,msg):
 if not ok:raise ValueError("MPW_REVIEW_"+msg)
def read(path):
 path=Path(path)
 require(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=1000000,"BAD_FILE")
 return json.loads(path.read_text("utf8"))
def save(path,obj):
 path=Path(path)
 require(not path.is_symlink(),"UNSAFE_WRITE")
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 require(not path.parent.is_symlink(),"UNSAFE_DIR")
 os.chmod(path.parent,0o700)
 data=(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
 if path.is_file() and path.read_bytes()==data:return False
 fd,name=tempfile.mkstemp(prefix=".independent-evidence-",dir=str(path.parent))
 try:
  with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(name,0o600);os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
 return True
def module(name):
 path=Path(__file__).with_name(name+".py")
 require(path.is_file() and not path.is_symlink(),"MISSING_TRUSTED_MODULE")
 sp=importlib.util.spec_from_file_location("review_"+name,str(path))
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def one(root,path,row,courier,worker):
 product,version,manifest,raw=worker.validate_original(root,path.name,row,courier)
 audit=courier.native_format_census(raw)
 candidate=courier.customer_companion(root,product,version,manifest["artifact_sha256"])
 if candidate:
  report,_=candidate
  package_type="private_native_structure_preview" if report.get("schema")==courier.NATIVE_PREVIEW_SCHEMA else "actual_executable_buyer_review_bundle"
  pack_sha=report["package_sha256"]
 else:
  package_type="missing"
  pack_sha=None
 needs=[]
 for code in row["issues"]:
  require(code in REVIEW_CODES,"UNEXPECTED_QA_CODE")
  role=REVIEW_CODES[code]
  needs.append({"issue_code":code,"assigned_role":role["role"],
   "required_authentic_documents":role["evidence_needed"],
   "reviewer_identity":None,"signed_at_utc":None,
   "real_evidence_received":False,"independent_review_passed":False})
 return {"schema":SCHEMA,"tenant":courier.TENANT,"product_id":product,
  "source_sha256":version,"artifact_sha256":manifest["artifact_sha256"],
  "return_record_sha256":courier.digest(courier.json_blob(row)),
  "source_artifact_integrity_verified":True,
  "source_native_format_counts":audit["format_counts"],
  "source_native_members_inspected":audit["inspected_members"],
  "technical_delivery_state":package_type,
  "technical_companion_sha256":pack_sha,
  "human_qa_open_issues":needs,
  "required_real_reviewer_decisions":3,
  "actual_reviewer_decisions_verified":0,
  "content_rights_owner_approval_verified":False,
  "customer_sale_and_site_publication_permitted":False,
  "source_rebuilt_in_this_review":False,
  "release_gate":"denied_until_authentic_three_party_evidence_on_exact_version",
  "next_action":"obtain_independent_human_content_rights_and_owner_signoff_not_fabricatable_by_automation"}
def run(root):
 root=Path(root)
 require(root.is_dir() and not root.is_symlink(),"BAD_ROOT")
 courier=module("mpw_vps_warehouse_courier")
 worker=module("mpw_factory_stage1_technical_repair")
 entries=worker.stage1(root,courier)
 output=root/"design-state/mojplaywin-independent-evidence"
 dossiers=output/"open"
 rows=[];created=0;existing=0;counts=Counter()
 for path,row in entries:
  doc=one(root,path,row,courier,worker)
  target=dossiers/path.name
  if save(target,doc):created+=1
  else:existing+=1
  counts[doc["technical_delivery_state"]]+=1
  rows.append({"product_id":doc["product_id"],"source_sha256":doc["source_sha256"],
   "source_archive_sha256":doc["artifact_sha256"],
   "technical_delivery_state":doc["technical_delivery_state"],
   "human_approvals_verified":0,"open_issues":3})
 require(len(rows)<=50,"TOO_MANY_DOSSIERS")
 report={"schema":SUMMARY,"observed_at_utc":datetime.now(timezone.utc).isoformat(),
   "validated_stage1_returns":len(rows),"independent_evidence_dossiers_created_this_run":created,
   "existing_unaltered_dossiers_verified":existing,
   "native_structure_only":counts["private_native_structure_preview"],
   "executable_buyer_review_bundles":counts["actual_executable_buyer_review_bundle"],
   "missing_technical_companions":counts["missing"],
   "original_zips_integrity_verified":len(rows),
   "independent_human_signoffs_verified":0,
   "products_commercially_authorized":0,
   "products_still_returned_for_human_qa":len(rows),
   "site_and_payment_mutations":0,"owner_approvals_fabricated":0,
   "rows":rows}
 save(output/"dashboard.json",report)
 print("MPW_INDEPENDENT_STAGE1_EVIDENCE="+json.dumps({
  k:report[k] for k in ("validated_stage1_returns",
   "native_structure_only","executable_buyer_review_bundles",
   "missing_technical_companions","independent_evidence_dossiers_created_this_run",
   "existing_unaltered_dossiers_verified","products_still_returned_for_human_qa",
   "products_commercially_authorized")},sort_keys=True))
 return report
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--factory-private",required=True)
 a=p.parse_args();run(a.factory_private)
