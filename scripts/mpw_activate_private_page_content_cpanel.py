"""Activate source-grounded English MojPlayWin MAIN-only page-draft production.

No publishing, no webroot or Django modification, no payment or other tenant
changes. Uses existing Gen65 private once-per-minute Cron, SHA-pinned source,
exclusive flock lock, rollback, and independent on-server readback.
"""
from __future__ import annotations
import fcntl
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

TENANT="mojplaywin-main"
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=ROOT/"v91_verified_main_port_20261018"
STATE=STAGE/"operator_state"
EVO=ROOT/"evolution_runtime_20261018"
MODULE=STAGE/"mpw_v91_port"
ENTRY=MODULE/"evolution.py"
FACTORY=MODULE/"page_content_factory.py"
CONTENT=EVO/"page_content_20261018"
MARK="MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018"
SOURCES={"evolution.py":ENTRY,"page_content_factory.py":FACTORY}


def need(ok,code):
    if not ok: raise RuntimeError(code)

def private(directory):
    return directory.is_dir() and not directory.is_symlink() and not directory.stat().st_mode & 0o077

def read_package():
    raw=sys.stdin.buffer.read(150001)
    need(0<len(raw)<=150000,"CONTENT_PACKAGE_LIMIT")
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as f:
        names=f.getnames()
        need(len(names)==3 and set(names)==set(SOURCES)|{"manifest.json"},"PACKAGE_EXACT_PATHS_ONLY")
        data={}
        for name in names:
            member=f.getmember(name)
            need(member.isfile() and 0<member.size<30000,"CONTENT_PACKAGE_MEMBER")
            data[name]=f.extractfile(member).read()
    manifest=json.loads(data.pop("manifest.json"))
    need(manifest.get("tenant")==TENANT
         and manifest.get("scope")=="main_only_private_content_drafts"
         and set(manifest.get("sha256",{}))==set(SOURCES),"CONTENT_MANIFEST_INVALID")
    for name,value in data.items():
        need(hashlib.sha256(value).hexdigest()==manifest["sha256"][name],
             "CONTENT_MANIFEST_SHA_INVALID")
        compile(value,name,"exec")
    return data

def atom(path,raw):
    need(not path.is_symlink(),"UNSAFE_CONTENT_DEST_SYMLINK")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-main-content-",dir=str(path.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)

def read_cron():
    p=subprocess.run(["crontab","-l"],text=True,capture_output=True,timeout=12)
    need(p.returncode==0,"CRONTAB_UNAVAILABLE")
    entries=[v for v in p.stdout.splitlines() if MARK in v]
    need(len(entries)==1 and entries[0].startswith("* * * * * ")
         and str(ENTRY) in entries[0] and "--once" in entries[0]
         and str(EVO/"cron.lock") in entries[0],"GEN65_MINUTE_CRON_NOT_VERIFIED")
    return p.stdout

def load_report(path, maxsize=20000):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size<=maxsize,
         "CONTENT_REPORT_NOT_FOUND_OR_UNSAFE")
    value=json.loads(path.read_text("utf-8"))
    need(isinstance(value,dict) and value.get("tenant")==TENANT,"CONTENT_REPORT_TENANT_INVALID")
    return value

def main():
    os.umask(0o077)
    need(getpass.getuser()=="zomorod2","INVALID_CPANEL_OWNER")
    parts=read_package()
    need(all(private(p) for p in (ROOT,STAGE,STATE,EVO,MODULE)),"CONTENT_PRIVATE_STAGE_INVALID")
    enable=STATE/"enabled"
    need(enable.is_file() and not enable.is_symlink()
         and enable.read_text().strip()=="MPW_V91_MAIN_ONLY_PRIVATE_20261018",
         "EXISTING_MAIN_AGENT_NOT_ENABLED")
    existing=load_report(EVO/"gen65_operational_report.json",9000)
    need(existing.get("status")=="gen65_operational_private"
         and existing.get("active_private_generation")==65
         and existing.get("existing_public_master_generation")==64
         and existing.get("auto_published") is False,
         "GEN65_NOT_OPERATIONAL")
    original_cron=read_cron()
    need(ENTRY.is_file() and not ENTRY.is_symlink() and not FACTORY.is_symlink(),
         "EXISTING_CONTENT_ENTRY_INVALID")
    backups={ENTRY:ENTRY.read_bytes(), FACTORY:FACTORY.read_bytes() if FACTORY.exists() else None}
    lock=EVO/"cron.lock"
    need(not lock.is_symlink(),"UNSAFE_EXISTING_CRON_LOCK")
    fd=os.open(str(lock),os.O_CREAT|os.O_RDWR|getattr(os,"O_NOFOLLOW",0),0o600)
    try:
        acquired=False
        for _ in range(24):
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;break
            except BlockingIOError: time.sleep(.35)
        need(acquired,"GEN65_CRON_BUSY_NOT_INTERRUPTED")
        need(read_cron()==original_cron,"CRON_CHANGED_DURING_CONTENT_PREFLIGHT")
        try:
            atom(FACTORY,parts["page_content_factory.py"])
            atom(ENTRY,parts["evolution.py"])
            for name,path in SOURCES.items():
                need(hashlib.sha256(path.read_bytes()).hexdigest()
                     ==hashlib.sha256(parts[name]).hexdigest(),"CONTENT_SOURCE_INSTALL_SHA")
            p=subprocess.run([shutil.which("python3") or "/usr/bin/python3",
                              "-B",str(ENTRY),"--once"],
                             capture_output=True,text=True,timeout=45)
            need(p.returncode==0,"CONTENT_FIRST_PRIVATE_CYCLE_FAILED:"+p.stderr[-350:])
            output=json.loads(p.stdout)
            need(output.get("status")=="active_private_learning"
                 and output.get("gen65_runtime_status")=="gen65_operational_private"
                 and output.get("page_content_pipeline_status")=="active_private_page_content_pipeline"
                 and output.get("page_content_total_drafts",0)>=2
                 and output.get("page_content_auto_published") is False,
                 "CONTENT_NOT_GENERATED_OR_GEN65_OFF")
            report=load_report(CONTENT/"last_report.json")
            need(report.get("status")=="active_private_page_content_pipeline"
                 and report.get("total_drafts",0)>=2
                 and report.get("language")=="en"
                 and report.get("auto_publish") is False
                 and report.get("public_site_modified") is False
                 and report.get("other_subsites_modified") is False,
                 "CONTENT_REPORT_ASSERTION_FAILED")
            folder=CONTENT/"drafts"
            need(private(CONTENT) and private(folder),"CONTENT_DRAFT_PRIVACY_FAILED")
            saved=list(folder.glob("*.json"))
            need(len(saved)>=2 and len(saved)<=32,"CONTENT_DRAFT_COUNT_UNSAFE")
            for file in saved:
                draft=load_report(file)
                need(draft["site"]=="mojplaywin.com"
                     and draft["page_path"] in ("/agents/","/knowledge/","/studio/","/research/")
                     and draft["published"] is False
                     and draft["approved_for_publication"] is False
                     and draft["language"]=="en"
                     and len(draft["source_urls"])==2
                     and draft["gen65_private_review_recommendation"]=="candidate_ready_for_human_review",
                     "CONTENT_DRAFT_OR_REVIEW_PROOF_FAILED")
            need(read_cron()==original_cron,"OTHER_CRON_ENTRY_CHANGED")
            print(json.dumps({
               "status":"MPW_MAIN_PRIVATE_ENGLISH_CONTENT_FACTORY_ACTIVE",
               "tenant":TENANT,
               "draft_count":len(saved),
               "new_drafts_this_cycle":report["new_drafts"],
               "remaining_curated_briefs":report["remaining_curated_briefs"],
               "language":"en","gen65_running":True,
               "content_moderation":"private_gen65_editorial_review_required",
               "schedule":"one_minute_private_evolution_cron",
               "auto_publish":False,
               "existing_cron_preserved":True,
               "public_site_changed":False,
               "other_subsites_changed":False,
               "payment_changed":False,
               "passenger_restarted":False
            },ensure_ascii=False,sort_keys=True))
        except BaseException:
            for path,previous in backups.items():
                if previous is not None:atom(path,previous)
                elif path.exists() and not path.is_symlink():path.unlink()
            raise
    finally:
        os.close(fd)

if __name__=="__main__":main()
