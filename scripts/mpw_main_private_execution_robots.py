"""Five concrete, main-tenant-only MojPlayWin execution robots.

Robots execute independent tasks and write *private* audit/review artefacts:
1. Site route availability;
2. main-site editorial page and internal-link integrity;
3. fingerprint/deduplication of private editorial drafts;
4. preparation of a bounded pending-review work queue;
5. integrity of Gen64, Gen65, V11 and 77-module schedules and evidence.

They NEVER publish, transfer money, alter Django, use login credentials,
change Apache or touch any child site. A minute-Cron is unnecessary; run one
isolated batch hourly with a file lock. Evidence timestamps and warnings are
recorded. A successful run does not mean a live sale or AI fact-check.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import tempfile
from urllib import request, error
from urllib.parse import urlsplit

TENANT="mojplaywin-main"
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO=PRIVATE/"evolution_runtime_20261018"
STAGE=PRIVATE/"v91_verified_main_port_20261018"
DOCROOT=Path("/home/zomorod2/mojplaywin.com")
EDITORIAL=DOCROOT/"mpw-editorial"
REPORT=EVO/"robots_execution_20261018.json"
QUEUE=EVO/"robots_editorial_review_queue_20261018.json"
MARKER="MPW_MAIN_PRIVATE_EXECUTION_ROBOTS_20261018"
SOURCE_SCRIPT=STAGE/"scripts/mpw_main_private_execution_robots.py"
MAIN_ROUTES=("/", "/agents/", "/knowledge/", "/research/", "/studio/", "/store/")
MAX_DRAFTS=8
MAX_BYTES=20000
ROBOTS=("main_route_observer","editorial_integrity","draft_fingerprint",
        "editorial_review_queue","agent_runtime_watch")

def require(check,why):
    if not check:raise RuntimeError(why)

def private(path):
    return path.is_dir() and not path.is_symlink() and not(path.stat().st_mode&0o077)

def read_json(path,limit=MAX_BYTES):
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size<=limit,"UNSAFE_ROBOT_READ:"+path.name)
    obj=json.loads(path.read_text(encoding="utf8"))
    require(isinstance(obj,dict) and obj.get("tenant")==TENANT,
            "WRONG_ROBOT_TENANT:"+path.name)
    return obj

def atomic(path,data):
    require(path.parent==EVO and private(EVO),"ROBOT_OUTPUT_NOT_PRIVATE")
    require(not path.is_symlink(),"ROBOT_OUTPUT_SYMLINK")
    raw=json.dumps(data,ensure_ascii=False,sort_keys=True).encode("utf8")
    require(len(raw)<=MAX_BYTES,"ROBOT_OUTPUT_TOO_LARGE")
    fd,temp=tempfile.mkstemp(prefix=".mpw-robot-",dir=EVO)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def public_probe(path,method="HEAD"):
    require(path in MAIN_ROUTES or path=="/mpw-editorial/index.html",
            "ROBOT_REQUEST_UNAPPROVED_PATH")
    url="https://mojplaywin.com"+path
    opener=request.build_opener(NoRedirect(),request.HTTPSHandler(context=ssl.create_default_context()))
    req=request.Request(url,headers={"User-Agent":"MojPlayWin-PrivateRobots/1.0"},method=method)
    try:
        with opener.open(req,timeout=9) as response:
            code=response.status
            body=response.read(120000) if method=="GET" else b""
            return code,body
    except error.HTTPError as exc:
        return exc.code,b""

class InternalLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            v=dict(attrs).get("href")
            if isinstance(v,str):self.links.append(v)

def route_robot(probe=public_probe):
    findings=[]
    for path in MAIN_ROUTES:
        try:code,_=probe(path,"HEAD")
        except (error.URLError,OSError,TimeoutError) as ex:
            code=0
        findings.append({"path":path,"http":code,"healthy":code==200})
    return {"name":"main_route_observer","status":"ok" if all(x["healthy"] for x in findings) else "warning",
            "checks":len(findings),"healthy":sum(x["healthy"] for x in findings),
            "routes":findings,"mutations":0}

def editorial_robot(public=EDITORIAL,probe=public_probe):
    owner=read_json(public/".mpw-editorial-owner.json",10000)
    release=read_json(EVO/"editorial_publication_state.json",10000)
    require(owner.get("scope")=="mojplaywin-main-static-mpw-editorial-only",
            "EDITORIAL_NOT_MAIN_OWNED")
    require(release.get("status")=="published_verified_by_external_smoke",
            "EDITORIAL_RELEASE_UNVERIFIED")
    require(public.is_dir() and not public.is_symlink(),"EDITORIAL_DIR_UNSAFE")
    paths=[public/"index.html",public/"agents/index.html"]
    discovered=list(public.rglob("index.html"))
    # Site growth must not disable its own observer. Bound the scan by an
    # explicit resource budget while retaining per-file and symlink guards.
    require(2<=len(discovered)<=2048,
            "EDITORIAL_DOCUMENT_COUNT_UNSAFE:"+str(len(discovered)))
    require(not any(p.is_symlink() for p in discovered),
            "EDITORIAL_SYMLINK_UNSAFE")
    require(all(p.is_file() and p.stat().st_size<45000 for p in discovered),
            "EDITORIAL_DOCUMENT_NOT_FILE")
    urls=[]
    malformed=[]
    for doc in discovered:
        contents=doc.read_text("utf8")
        parser=InternalLinkParser();parser.feed(contents)
        for link in parser.links:
            if link.startswith("/mpw-editorial/"):
                # Passenger serves physical /index.html files, not folder URLs.
                if not link.endswith("/index.html"):
                    malformed.append(link);continue
                name=link.removeprefix("/mpw-editorial/")
                target=public/name
                if target.is_symlink() or not target.is_file():
                    malformed.append(link)
                urls.append(link)
    code,page=probe("/mpw-editorial/index.html","GET")
    reachable=code==200 and b"MojPlayWin" in page
    return {"name":"editorial_integrity","status":"ok" if reachable and not malformed else "warning",
            "published_documents":len(discovered),"published_articles":owner.get("published_articles"),
            "linked_static_pages":len(urls),"broken_internal_links":len(malformed),
            "homepage_external_http":code,"homepage_public_verified":reachable,
            "mutations":0}

def draft_robot():
    folder=EVO/"page_content_20261018/drafts"
    require(private(folder),"MAIN_PRIVATE_DRAFTS_UNAVAILABLE")
    files=sorted(folder.iterdir())
    require(0<len(files)<=MAX_DRAFTS,"PRIVATE_EDITORIAL_UNEXPECTED_DRAFT_COUNT")
    authorized={"/agents/","/knowledge/","/studio/","/research/"}
    seen=set(); rows=[]
    for file in files:
        require(file.suffix==".json" and not file.is_symlink(),"UNKNOWN_PRIVATE_DRAFT_FILE")
        doc=read_json(file)
        page=doc.get("page_path");slug=doc.get("slug")
        require(page in authorized and isinstance(slug,str) and
                re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",slug) and
                file.name==slug+".json","DRAFT_SCOPE_INVALID")
        calculated=hashlib.sha256((page+"\x1f"+doc["body_markdown"]).encode("utf8")).hexdigest()
        require(calculated==doc.get("content_sha256") and calculated not in seen,
                "DRAFT_DUPLICATE_OR_CONTENT_TAMPER")
        require(doc.get("published") is False
                and doc.get("approved_for_publication") is False
                and doc.get("language")=="en"
                and isinstance(doc.get("source_urls"),list)
                and len(doc["source_urls"])==2,"DRAFT_REVIEW_CONTRACT_VIOLATION")
        seen.add(calculated)
        rows.append({"slug":slug,"page":page,"fingerprint":calculated,
                     "review":"needs_independent_factual_review"})
    return {"name":"draft_fingerprint","status":"ok","examined":len(rows),
            "unique":len(seen),"duplicates":0,"draft_rows":rows,"mutations":0}

def review_queue_robot(draft_evidence):
    rows=draft_evidence["draft_rows"]
    require(len(rows)<=MAX_DRAFTS,"REVIEW_QUEUE_UNBOUNDED")
    return {"name":"editorial_review_queue","status":"ok",
            "review_tasks_created_or_refreshed":len(rows),
            "work_items":[{"slug":x["slug"],"section":x["page"],
                           "required_checks":["source_fact_check","copyright",
                                              "duplicate_live_content","editorial_clarity"],
                           "can_auto_approve":False} for x in rows],
            "publications":0,"private_manifest_only":True}

def agent_robot(crontab):
    required={
        "MPW_V91_MAIN_ONLY_20261018": "17",
        "MPW_V11_MAIN_ONLY_SITE_HEALTH_20261018":"37",
        "MPW_ZOMOROD_QUALITY_REVIEW_MAIN_ONLY_20261018":"49",
        "MPW_ZOMOROD_MANAGEMENT_INTELLIGENCE_MAIN_ONLY_20261018":"58",
        "MPW_PRIVATE_EVOLUTION_MAIN_ONLY_20261018":"*",
        "MPW_77_MODULES_MAIN_ONLY_20261018":"43",
    }
    issues=[]
    for mark,minute in required.items():
        found=[row for row in crontab.splitlines() if mark in row and not row.lstrip().startswith("#")]
        if len(found)!=1 or not found[0].startswith(minute+" "):
            issues.append(mark)
    report=read_json(EVO/"gen65_operational_report.json",10000)
    modules=read_json(EVO/"all_77_modules_last_run.json",35000)
    site=read_json(PRIVATE/"site_health_v11_port_20261018/last_scan.json")
    require(report.get("active_private_generation")==65 and
            report.get("status")=="gen65_operational_private",
            "GEN65_RUNTIME_OFFLINE")
    require(modules.get("modules_import_executed")==77
            and modules.get("capability_namespaces_active")==77
            and modules.get("functional_probes_executed",0)>=14
            and isinstance(modules.get("per_module_capability_registry"),list)
            and len(modules["per_module_capability_registry"])==77
            and all(row.get("loaded") is True
                    and row.get("safe_scope")=="read_only_private"
                    for row in modules["per_module_capability_registry"]),
            "ORIGINAL_77_MODULES_NOT_FUNCTIONALLY_AVAILABLE")
    require(site.get("total_agents")==11 and len(site.get("runs",[]))==11,
            "ELEVEN_AUDIT_ROLES_NOT_PRESENT")
    now=datetime.now(timezone.utc)
    age=(now-datetime.fromisoformat(report["observed_utc"].replace("Z","+00:00"))).total_seconds()
    if not 0<=age<=900: issues.append("gen65_stale")
    return {"name":"agent_runtime_watch","status":"ok" if not issues else "warning",
            "expected_schedules":len(required),"schedule_mismatches":issues,
            "gen65_age_seconds":int(age),"v11_roles":11,
            "legacy_modules_loaded":77,
            "legacy_modules_active_capabilities":77,
            "legacy_module_functional_contracts":modules["functional_probes_executed"],
            "mutations":0}

def cycle():
    require(private(PRIVATE) and private(EVO) and private(STAGE),"ROBOT_PRIVATE_CYCLE_SCOPE")
    require(os.geteuid()==STAGE.stat().st_uid,"ROBOT_USER_MISMATCH")
    scheduled=subprocess.run(["crontab","-l"],capture_output=True,text=True,timeout=12,check=True).stdout
    route=route_robot()
    editorial=editorial_robot()
    drafts=draft_robot()
    queue=review_queue_robot(drafts)
    control=agent_robot(scheduled)
    stamp=datetime.now(timezone.utc).isoformat()
    queue_doc={"tenant":TENANT,"observed_utc":stamp,
               "status":"private_nonpublishing_review_queue",
               "items":queue["work_items"],
               "automated_approval":False,"published":False}
    atomic(QUEUE,queue_doc)
    entries=[route,editorial,
             {k:v for k,v in drafts.items() if k!="draft_rows"},
             {k:v for k,v in queue.items() if k!="work_items"},control]
    report={"tenant":TENANT,"status":"five_main_robots_executed",
            "observed_utc":stamp,
            "robot_count":len(entries),"roles":entries,
            "successful":sum(row["status"]=="ok" for row in entries),
            "warnings":sum(row["status"]=="warning" for row in entries),
            "private_actions":["updated_review_queue","wrote_robot_evidence"],
            "site_writes":0,"subsite_writes":0,"financial_actions":0,
            "publisher_authority":False}
    atomic(REPORT,report)
    return report

def main():
    p=argparse.ArgumentParser(description="MojPlayWin private execution robots")
    p.add_argument("--once",action="store_true",required=True)
    p.parse_args()
    result=cycle()
    print(json.dumps({"status":result["status"],"robots_executed":result["robot_count"],
                      "robots_healthy":result["successful"],"warnings":result["warnings"],
                      "site_writes":0},sort_keys=True))

if __name__=="__main__":main()
