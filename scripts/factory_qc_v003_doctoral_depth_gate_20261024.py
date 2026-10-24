#!/usr/bin/env python3
"""QC-only doctoral depth rejection of v003 educational editions.

This is a reproducible negative-content screen on real ZIP bytes; it does NOT
claim to be a professor, fulltext source verifier, field trial, or QC1000.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import zipfile

SCHEMA="saeit.factory.qc.v003.doctoral-depth-rework.v1"
ORDER=re.compile(r"WO-[0-9]{8}--r001\.json\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
SEVERE={
 "P0_PRIMARY_FULLTEXT_UNVERIFIED",
 "P0_UNFILLED_CLAIM_TO_MEASUREMENT_WORKSHEETS",
 "P0_MISSING_COMPLETE_PRIMARY_SOURCE_PROVENANCE",
 "P0_LOCAL_FIELD_AND_BIOSAFETY_EVIDENCE_MISSING",
 "P0_INDEPENDENT_SCIENTIFIC_VERDICT_MISSING",
 "P0_TRUSTED_QC1000_EXECUTION_EVIDENCE_MISSING",
}

def require(ok,code):
    if not ok: raise ValueError(code)

def canonical(data):
    return json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf8")

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def dependency(path,label):
    path=Path(path)
    require(path.is_file() and not path.is_symlink(),"UNSAFE_QC_DEPENDENCY")
    spec=importlib.util.spec_from_file_location(label,str(path))
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def analyse(name,manifest,qc,manuscripts,sources):
    require(ORDER.fullmatch(name) and manifest.get("order_file")==name,
            "BAD_ORDER_BINDING")
    require(qc.get("artifact_sha256")==manifest.get("zip_sha256") and
            isinstance(qc.get("artifact_sha256"),str) and
            SHA.fullmatch(qc["artifact_sha256"]),"UNBOUND_QC_ARCHIVE")
    require(qc.get("mechanical_integrity_pass") is True and
            qc.get("independent_quality1000_approved") is False and
            manifest.get("quality1000_approved") is False and
            manifest.get("commercial_release") is False,
            "MECHANICAL_GATE_OR_RELEASE_INCONSISTENCY")
    require(set(manuscripts)=={"fa-IR","en-US"} and
            all(isinstance(v,str) and len(v)>1000 for v in manuscripts.values()),
            "BILINGUAL_EDITION_INVALID")
    require(isinstance(sources,list) and len(sources)>=4,"SOURCES_MISSING")
    source_ids={s.get("id") for s in sources if isinstance(s,dict)}
    require(len(source_ids)==len(sources) and all(isinstance(s,str) for s in source_ids),
            "SOURCE_IDENTITIES_INVALID")

    flags=set()
    metrics={}
    for loc,body in manuscripts.items():
        for sid in source_ids:
            require(sid in body,"MANUSCRIPT_SOURCE_ID_MISSING")
        is_fa=loc=="fa-IR"
        # Only completed data rows count. Template headers/directions are excluded.
        table_lines=[line.strip() for line in body.splitlines() if line.strip().startswith("|")]
        filled=[line for line in table_lines
                if line.count("|")>=6 and not any(x in line for x in
                    ("---","To verify","To record","Unknown","Needs primary-text check",
                     "تکمیل شود","نامعلوم","در انتظار بررسی","شاخص مربوط","Measure relevant"))]
        placeholders=sum(any(x in line for x in
                    ("To verify","To record","Unknown","Needs primary-text check",
                     "تکمیل شود","نامعلوم","در انتظار بررسی"))
                         for line in table_lines)
        chapters=len(re.findall(r"(?m)^## (?:فصل|Chapter)\s+\d+",body))
        repeated_scaffold=body.count("### Reusable source-to-observation worksheet") if not is_fa else body.count("### برگهٔ کار آماده برای استفاده")
        primary_disclaimer=("Read the full primary studies" in body if not is_fa else
                            "متن کامل مقاله و شرایط محلی باید مستقل بررسی شوند" in body)
        field_disclaimer=("actual field testing" in body if not is_fa else
                          "آزمون میدانی" in body)
        metrics[loc]={
            "chapters":chapters,"worksheet_placeholder_rows":placeholders,
            "completed_measurement_rows":len(filled),
            "reused_scaffold_sections":repeated_scaffold,
            "explicit_primary_fulltext_disclaimer":primary_disclaimer,
            "explicit_field_validation_disclaimer":field_disclaimer,
            "source_id_coverage":len(source_ids),
        }
        if primary_disclaimer: flags.add("P0_PRIMARY_FULLTEXT_UNVERIFIED")
        if placeholders and not filled: flags.add("P0_UNFILLED_CLAIM_TO_MEASUREMENT_WORKSHEETS")
        if field_disclaimer: flags.add("P0_LOCAL_FIELD_AND_BIOSAFETY_EVIDENCE_MISSING")
        if repeated_scaffold>=5 and not filled:
            flags.add("P0_REPEATED_METHOD_TEMPLATE_WITHOUT_COMPLETED_CASE_STUDIES")
    # The export contains metadata but no verified fulltext, authorship chain,
    # sampled location, journal pagination, retraction record or publication rights.
    absent=sorted(k for k in ("authors","journal","volume","pages","fulltext_sha256",
                              "retraction_checked_at","license_evidence")
                  if not all(isinstance(s,dict) and bool(s.get(k)) for s in sources))
    if absent: flags.add("P0_MISSING_COMPLETE_PRIMARY_SOURCE_PROVENANCE")
    if manifest.get("independent_scientific_review") is not True:
        flags.add("P0_INDEPENDENT_SCIENTIFIC_VERDICT_MISSING")
    if qc.get("independent_quality1000_approved") is not True:
        flags.add("P0_TRUSTED_QC1000_EXECUTION_EVIDENCE_MISSING")
    return {
      "schema":SCHEMA,"order_file":name,"revision":3,
      "v003_artifact_sha256":manifest["zip_sha256"],
      "v003_manifest_sha256":sha(canonical(manifest)),
      "mechanical_qc_sha256":sha(canonical(qc)),
      "discipline_review_screen":"ACTUAL_BYTES_NEGATIVE_EVIDENCE_SCREEN",
      "analysis_scope":"structural_and_explicit_evidence_gaps_only",
      "bibliographic_missing_fields":absent,
      "metrics":metrics,"critical_findings":sorted(flags),
      "disposition":"RETURN_FOR_SUBSTANTIVE_SCIENTIFIC_REWORK",
      "rework_requirements":[
        "Complete independent fulltext, exact page-and-claim trace, retraction screening.",
        "Replace unfilled templates with verifiable, source-specific worked examples and measured evidence or explicitly scoped desk research.",
        "Provide complete bibliographic provenance, licenses, methods, limits and uncertainty.",
        "Obtain authentic agriculture-domain and Iran field/regulatory/biosafety specialist verdict.",
        "Run 1000 distinct version-bound tests via an independently trusted runner where criteria are executable.",
        "Resubmit new immutable artifact hash; rerun all quality gates from its actual bytes."
      ],
      "independent_human_peer_review_executed":False,
      "doctoral_quality_certified":False,
      "quality1000_approved":False,
      "commercial_release":False,"public_distribution_allowed":False,
      "existing_storefront_products_modified":False,
    }

def execute(root,stage34,v003qc,batch):
    area=Path(root).resolve()/"production-instructions"
    manifests=area/"stage-05/source-grounded-v003-manifests"
    qcdir=area/"stage-06/source-grounded-v003-qc"
    require(manifests.is_dir() and qcdir.is_dir() and not manifests.is_symlink()
            and not qcdir.is_symlink(),"QC_REAL_INPUTS_UNAVAILABLE")
    inbox=area/"stage-06/doctoral-depth-rework-v003"
    blocked=area/"stage-06/doctoral-depth-blocked-v003"
    stage34.private_dir(inbox)
    stage34.private_dir(blocked)
    lock=area/".qc-v003-doctoral-depth.lock"
    require(not lock.is_symlink(),"QC_DEPTH_LOCK_UNSAFE")
    with lock.open("a+b") as fd:
        os.fchmod(fd.fileno(),0o600)
        fcntl.flock(fd.fileno(),fcntl.LOCK_EX)
        names=sorted(p.name for p in manifests.iterdir()
                     if p.is_file() and not p.is_symlink() and ORDER.fullmatch(p.name))
        cursor=area/"stage-06/doctoral-depth-cursor.json"
        require(not cursor.is_symlink(),"QC_DEPTH_CURSOR_UNSAFE")
        old=stage34.read(cursor) if cursor.is_file() else {"schema":SCHEMA,"next_index":0}
        require(old.get("schema")==SCHEMA and type(old.get("next_index")) is int
                and old["next_index"]>=0,"QC_DEPTH_CURSOR_INVALID")
        start=old["next_index"]%len(names) if names else 0
        chosen=[names[(start+i)%len(names)] for i in range(min(batch,len(names)))]
        counts=Counter()
        findings=Counter()
        for name in chosen:
            try:
                manifest=stage34.read(manifests/name)
                stored=stage34.read(qcdir/name)
                actual=v003qc.check_one(area,name,stage34,None)
                require(stored==actual,"QC_DEPTH_FRESH_RECHECK_MISMATCH")
                path=v003qc.safe_archive(area,manifest.get("archive_relative_path"))
                prefix="agri-"+name[:-5]+"-v003/"
                with zipfile.ZipFile(path) as arc:
                    manuscripts={loc:arc.read(prefix+loc+".md").decode("utf8")
                                 for loc in ("fa-IR","en-US")}
                    sources=json.loads(arc.read(prefix+"sources.json"))
                verdict=analyse(name,manifest,actual,manuscripts,sources)
                target=inbox/name
                if target.is_file():
                    require(stage34.read(target)==verdict,
                            "QC_DEPTH_IMMUTABLE_VERDICT_STALE")
                    counts["verified_existing_rework_packets"]+=1
                else:
                    require(stage34.once(target,verdict),
                            "QC_DEPTH_PACKET_WRITE_FAILED")
                    counts["new_rework_packets"]+=1
                findings.update(verdict["critical_findings"])
            except (OSError,RuntimeError,ValueError,KeyError,TypeError,
                    UnicodeError,zipfile.BadZipFile) as exc:
                counts["blocked"]+=1
                stage34.atomic(blocked/name,{
                    "schema":SCHEMA,"order_file":name,
                    "reason":type(exc).__name__+":"+str(exc)[:150],
                    "quality1000_approved":False,"commercial_release":False})
        stage34.atomic(cursor,{"schema":SCHEMA,
              "next_index":(start+len(chosen))%len(names) if names else 0})
        total=sum(p.is_file() and not p.is_symlink() and ORDER.fullmatch(p.name) is not None
                  for p in inbox.iterdir())
        report={
            "schema":SCHEMA,"updated_utc":datetime.now(timezone.utc).isoformat(),
            "private_v003_products":len(names),"rechecked_this_tick":len(chosen),
            "real_content_rework_verdicts_total":total,
            "findings_this_tick":dict(findings),
            **dict(counts),
            "real_independent_human_scientific_approvals":0,
            "quality1000_approvals_created":0,"commercial_releases":0,
            "sites_modified":False,
            "next_action":"REAUTHOR_SCIENTIFIC_CONTENT_AND_OBTAIN_AUTHENTIC_INDEPENDENT_EVIDENCE",
        }
        stage34.atomic(area/"stage-06/doctoral-depth-health.json",report)
        return report

def selftest():
    name="WO-00000001--r001.json"
    manifest={"order_file":name,"zip_sha256":"a"*64,
              "quality1000_approved":False,"commercial_release":False,
              "independent_scientific_review":False}
    qc={"artifact_sha256":"a"*64,"mechanical_integrity_pass":True,
        "independent_quality1000_approved":False}
    sources=[{"id":"SRC-"+str(i),"title":"Item"} for i in range(4)]
    en=("Read the full primary studies. actual field testing. "
         +"SRC-0 SRC-1 SRC-2 SRC-3\n"+"## Chapter 1\n"+
         "### Reusable source-to-observation worksheet\n"+
         "| Claim | To verify | To record | Unknown | Unknown | Needs primary-text check |\n")*6
    fa=("متن کامل مقاله و شرایط محلی باید مستقل بررسی شوند. آزمون میدانی "
         +"SRC-0 SRC-1 SRC-2 SRC-3\n"+"## فصل ۱\n"+
         "### برگهٔ کار آماده برای استفاده\n"+
         "| ادعا | تکمیل شود | تکمیل شود | نامعلوم | نامعلوم | در انتظار بررسی |\n")*6
    row=analyse(name,manifest,qc,{"fa-IR":fa,"en-US":en},sources)
    assert SEVERE.issubset(row["critical_findings"])
    assert row["quality1000_approved"] is False
    try:
        bad=dict(manifest,zip_sha256="b"*64)
        analyse(name,bad,qc,{"fa-IR":fa,"en-US":en},sources)
        raise AssertionError("tampered hash accepted")
    except ValueError: pass
    print("QC_DOCTORAL_DEPTH_NEGATIVE_SCREEN_SELFTEST=PASS",flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--selftest",action="store_true")
    p.add_argument("--factory-private")
    p.add_argument("--stage34-worker")
    p.add_argument("--v003-qc-worker")
    p.add_argument("--batch",type=int,default=25)
    a=p.parse_args()
    if a.selftest:return selftest()
    require(a.factory_private and a.stage34_worker and a.v003_qc_worker,
            "QC_DEPTH_ARGUMENTS_MISSING")
    require(1<=a.batch<=250,"QC_DEPTH_BATCH_INVALID")
    result=execute(a.factory_private,
                   dependency(a.stage34_worker,"doctoral_stage34"),
                   dependency(a.v003_qc_worker,"doctoral_mechanical"),a.batch)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("QC_DOCTORAL_DEPTH_ERROR:"+type(exc).__name__+":"+str(exc)[:150],
              file=sys.stderr)
        raise SystemExit(1)
