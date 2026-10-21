#!/usr/bin/env python3
"""Produce REAL data collection work-orders from private QA, never fake 1000 pts.

Each product has 100 separate criterion obligations plus domain-specific work.
This is an operational queue for specialists and engineering, not AI-written
evidence: criterion points stay zero unless measured, peer reviewed and signed.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):
    spec=importlib.util.spec_from_file_location("factory_100_criteria_gate",str(path))
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def work_orders(root,quality_file,catalog_file,run_id,limit=300):
    base=Path(root)
    source=base/"quality-excellence"/"rework"
    assert base.is_dir() and source.is_dir() and not source.is_symlink()
    module=load(quality_file)
    catalog=module.catalog()
    assert len(catalog)==100
    output=base/"quality-excellence"/"production-workorders"
    assert not output.is_symlink()
    output.mkdir(parents=True,mode=0o700,exist_ok=True)
    jobs=[]
    for folder in sorted(source.iterdir()):
        if len(jobs)>=limit:break
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"[a-z][a-z0-9_]{1,65}",folder.name):
            continue
        current=folder/"current.json"
        if not current.is_file() or current.is_symlink():continue
        snapshot=json.loads(current.read_text(encoding="utf8"))
        score=snapshot.get("quality_1000_scorecard",{})
        rows=score.get("criteria",{})
        findings=[]
        for number,policy in catalog.items():
            item=rows.get(number,{})
            status=item.get("evidence_status")
            if item.get("documentary_points")==10:continue
            findings.append({
                "group_id":number,
                "criterion":policy["name"],
                "max_points":10,
                "observed_evidence_status":status or "NO_EVIDENCE",
                "state":"AWAITING_REAL_MEASUREMENT_AND_REVIEW",
                "action":"Produce reproducible test or specialist assessment, attach original source bytes with SHA256, and request independent fact/quality review.",
            })
        rest=sorted(set(snapshot.get("defects",[])))
        content={
          "schema":"saeit.factory.production-rework-order.v1",
          "recipe":folder.name,
          "source_quality_receipt_sha256":sha(current),
          "artifact_sha256":snapshot.get("artifact_sha256"),
          "quality_score_required":1000,
          "group_count":100,"points_per_group":10,
          "status":"NEEDS_REWORK" if findings or rest else "WAITING_SIGNED_INDEPENDENT_APPROVAL",
          "missing_documentary_group_count":len(findings),
          "unresolved_technical_or_domain_defects":rest,
          "rework_actions":snapshot.get("rework_actions",[]),
          "required_criterion_work":findings,
          "never_auto_sign_off":True,
          "signed_external_quality_approval_required":True,
          "owner_release_approval_required":True,
          "commercial_publish_allowed":False,
        }
        dest=output/folder.name
        assert not dest.is_symlink()
        dest.mkdir(parents=True,exist_ok=True,mode=0o700)
        bytes_=json.dumps(content,ensure_ascii=False,sort_keys=True,indent=2).encode()+b"\n"
        key=hashlib.sha256(bytes_).hexdigest()
        persistent=dest/("order-"+key[:20]+".json")
        if persistent.exists():
            assert not persistent.is_symlink() and persistent.read_bytes()==bytes_
        else:
            with persistent.open("xb") as out:
                out.write(bytes_);out.flush()
            persistent.chmod(0o600)
        current_order=dest/"current.json"
        tmp=dest/(".stage-"+re.sub(r"[^0-9A-Za-z]","",str(run_id))[:20])
        with tmp.open("wb") as out:out.write(bytes_)
        tmp.chmod(0o600);tmp.replace(current_order)
        jobs.append({"recipe":folder.name,"groups_pending":len(findings),
                     "unresolved_defect_count":len(rest),
                     "source_receipt_sha256":sha(current),
                     "workorder_sha256":key})
    overview={"schema":"saeit.factory.workorder-index.v1",
              "products":len(jobs),"pending_groups_total":sum(x["groups_pending"] for x in jobs),
              "workorder_count":len(jobs),
              "commercially_approved":0,"generated_by":"measured_evidence_intake_only",
              "items":jobs}
    manifest=output/("index-"+re.sub(r"[^0-9A-Za-z]","",str(run_id))[:40]+".json")
    if manifest.exists():assert json.loads(manifest.read_text())==overview
    else:
        with manifest.open("x",encoding="utf8") as f:
            json.dump(overview,f,ensure_ascii=False,sort_keys=True,indent=2);f.write("\n")
        manifest.chmod(0o600)
    print("FACTORY_PRODUCTION_WORKORDERS_WRITTEN="+str(len(jobs)))
    print("FACTORY_MISSING_VERIFIABLE_QUALITY_GROUPS="+str(overview["pending_groups_total"]))
    print("FACTORY_COMMERCIAL_APPROVALS_CREATED=0")
    return overview
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("private-root","quality-module","catalog","run-id"):
        p.add_argument("--"+key,required=True)
    a=p.parse_args()
    work_orders(a.private_root,Path(a.quality_module),Path(a.catalog),a.run_id)
