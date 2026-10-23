"""Six additional MojPlayWin MAIN execution robots; private, nonfinancial.

Works alongside five existing hourly MojPlayWin robots, never touching shared
Django, Passenger, other sites, store/database, external payment, or VPS factory.
Each worker does a bounded practical job and reports actual successes/warnings.
All writes are private audit data; existing web documents are strictly read-only.

Missions:
  SEO metadata verifier, source-origin verifier, publishing reconciliation,
  public content security verifier, disk-capacity watchdog and publication worklist.
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
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

TENANT="mojplaywin-main"
BASE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STATE=BASE/"evolution_runtime_20261018"
STAGE=BASE/"v91_verified_main_port_20261018"
PAGES=Path("/home/zomorod2/mojplaywin.com/mpw-editorial")
DRAFTS=STATE/"page_content_20261018/drafts"
REPORT=STATE/"extended_robots_status_20261018.json"
WORKLIST=STATE/"extended_robots_pending_release_20261018.json"
MAX_PAGES=2048
MAX_DRAFTS=8
MAX_REPORT_BYTES=17500
SECTIONS={"agents":"/agents/","knowledge":"/knowledge/","studio":"/studio/","research":"/research/"}
SOURCE_HOSTS={"www.nist.gov","www.w3.org","developers.google.com","owasp.org"}
NAMES=("seo_metadata","reference_origin","release_reconciliation",
       "public_content_security","disk_capacity","publication_worklist")

def ensure(ok,msg):
    if not ok:raise RuntimeError(msg)

def private(directory):
    return directory.is_dir() and not directory.is_symlink() and (directory.stat().st_mode&0o077)==0

def json_read(path,maximum=20000):
    ensure(path.is_file() and not path.is_symlink() and path.stat().st_size<=maximum,
           "UNSAFE_EXTENDED_ROBOT_INPUT:"+path.name)
    data=json.loads(path.read_text(encoding="utf8"))
    ensure(isinstance(data,dict) and data.get("tenant")==TENANT,
           "CROSS_TENANT_EXTENDED_ROBOT_INPUT:"+path.name)
    return data

def private_write(path,document):
    ensure(path.parent==STATE and private(STATE),"UNAUTHORIZED_ROBOT_WRITE")
    ensure(not path.is_symlink(),"ROBOT_REPORT_SYMLINK")
    raw=json.dumps(document,sort_keys=True,ensure_ascii=False).encode("utf8")
    ensure(len(raw)<MAX_REPORT_BYTES,"ROBOT_REPORT_EXCEEDS_BOUND")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-extended-bots-",dir=STATE)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)

class HTMLFacts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title=[];self.capture=False;self.canonicals=[];self.descriptions=[]
        self.noindex=False;self.scripts=0;self.forms=0;self.csp=False
        self.external_assets=0;self.target_blank_unsafe=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=="title":self.capture=True
        if tag=="script":self.scripts+=1
        if tag=="form":self.forms+=1
        if tag=="meta":
            if d.get("name","").lower()=="description":self.descriptions.append(d.get("content",""))
            if d.get("name","").lower()=="robots" and "noindex" in d.get("content","").lower():self.noindex=True
            if d.get("http-equiv","").lower()=="content-security-policy":self.csp=True
        if tag=="link" and d.get("rel")=="canonical":self.canonicals.append(d.get("href"))
        if tag in ("script","img","link"):
            url=d.get("src",d.get("href",""))
            if url.startswith(("http://","https://","//")) and d.get("rel")!="canonical":
                self.external_assets+=1
        if tag=="a" and d.get("target")=="_blank":
            if not {"noopener","noreferrer"} & set(d.get("rel","").split()):
                self.target_blank_unsafe+=1
    def handle_endtag(self,tag):
        if tag=="title":self.capture=False
    def handle_data(self,data):
        if self.capture:self.title.append(data)

def approved_pages(public=PAGES):
    ensure(public.is_dir() and not public.is_symlink(),"STATIC_ROOT_MISSING")
    owned=json_read(public/".mpw-editorial-owner.json",9000)
    ensure(owned.get("scope")=="mojplaywin-main-static-mpw-editorial-only",
           "STATIC_DOCUMENT_ROOT_NOT_OWNED")
    files=sorted(public.rglob("index.html"))
    # Editorial pages grow independently of the bot deployment cadence.
    # Keep a finite scan bound while preserving all per-file safety checks.
    ensure(2<=len(files)<=MAX_PAGES,
           "PUBLIC_HTML_COUNT_OUT_OF_POLICY:"+str(len(files)))
    ensure(all(f.is_file() and not f.is_symlink()
           and f.stat().st_size<49000 and public in f.parents for f in files),
           "PUBLIC_HTML_LIST_OUT_OF_POLICY")
    return owned,files

def seo_robot(files,public=PAGES):
    titles=set()
    malformed=[]
    for p in files:
        doc=HTMLFacts()
        doc.feed(p.read_text("utf8"))
        rel=p.relative_to(public).as_posix()
        canonical="https://mojplaywin.com/mpw-editorial/"+rel
        title=" ".join(doc.title).strip()
        if (not title or title in titles or doc.canonicals!=[canonical]
            or len(doc.descriptions)!=1 or len(doc.descriptions[0])<30
            or doc.noindex):
            malformed.append(rel)
        titles.add(title)
    return {"name":"seo_metadata","status":"ok" if not malformed else "warning",
            "pages_checked":len(files),"unique_titles":len(titles),
            "invalid_seo_documents":malformed}

def references_robot(rows):
    invalid=[];links=0
    for draft in rows:
        refs=draft.get("source_urls",[])
        if not isinstance(refs,list) or len(refs)!=2 or len(set(refs))!=2:
            invalid.append(draft.get("slug","unknown"));continue
        for raw in refs:
            try:
                parsed=urlsplit(raw)
                if parsed.scheme!="https" or parsed.hostname not in SOURCE_HOSTS or parsed.username or parsed.password:
                    invalid.append(draft["slug"])
                else:links+=1
            except (ValueError,TypeError,KeyError):
                invalid.append(draft.get("slug","unknown"))
    return {"name":"reference_origin","status":"ok" if not invalid else "warning",
            "source_annotations_checked":links,
            "invalid_or_unknown_source_drafts":sorted(set(invalid)),
            "external_content_fact_verified":False}

def reconcile_robot(rows,owned,public=PAGES):
    fingerprints=owned.get("content_fingerprints",{})
    ensure(isinstance(fingerprints,dict) and len(fingerprints)<=MAX_DRAFTS,
           "PUBLIC_MANIFEST_NOT_BOUNDED")
    byslug={r["slug"]:r for r in rows}
    mismatched=[]
    for slug,digest in fingerprints.items():
        draft=byslug.get(slug)
        if not draft or draft.get("content_sha256")!=digest:
            mismatched.append(slug);continue
        section=draft["page_path"].strip("/")
        if section not in SECTIONS or not (public/section/slug/"index.html").is_file():
            mismatched.append(slug)
    pending=sorted(r["slug"] for r in rows if r["slug"] not in fingerprints)
    return {"name":"release_reconciliation",
            "status":"ok" if not mismatched else "warning",
            "manifest_articles":len(fingerprints),
            "published_record_mismatches":mismatched,
            "unpublished_private_drafts":pending,
            "public_writes":0}

def content_security_robot(files):
    issues=[]
    for p in files:
        doc=HTMLFacts();doc.feed(p.read_text("utf8"))
        if doc.scripts or doc.forms or doc.external_assets or doc.target_blank_unsafe or not doc.csp:
            issues.append(p.name)
    return {"name":"public_content_security","status":"ok" if not issues else "warning",
            "pages_checked":len(files),"risky_pages":len(issues),
            "site_write_attempts":0,
            "scope":"owned_standalone_educational_html_only"}

def capacity_robot(directory=PAGES):
    usage=shutil.disk_usage(directory)
    pct=round(100*usage.free/usage.total,2) if usage.total else 0.0
    return {"name":"disk_capacity","status":"ok" if pct>=10 else "warning",
            "disk_free_percent":pct,"disk_free_gb":round(usage.free/1024**3,2),
            "cleanup_performed":False}

def worklist_robot(rows,manifest):
    fingerprints=manifest.get("content_fingerprints",{})
    require_keys=("slug","page_path","title")
    pending=[r for r in rows if r["slug"] not in fingerprints]
    items=[{"slug":r["slug"],"page":r["page_path"],"title":r["title"],
            "gates":["verify_source_claims","rights","duplicate_check","publication_gate"],
            "approved":False} for r in pending]
    return {"name":"publication_worklist","status":"ok",
            "pending_count":len(items),"items":items,
            "auto_published":False,"authoritative_queue_only":False}

def cycle():
    ensure(private(BASE) and private(STAGE) and private(STATE) and private(DRAFTS),
           "PRIVATE_SCOPE_MISSING")
    ensure(os.geteuid()==STAGE.stat().st_uid,"WRONG_CPANEL_USER")
    owned,files=approved_pages()
    paths=sorted(DRAFTS.iterdir())
    ensure(0<len(paths)<=MAX_DRAFTS and all(p.suffix==".json" and p.is_file()
           and not p.is_symlink() for p in paths),"INVALID_CONTENT_STAGE")
    rows=[json_read(p) for p in paths]
    ensure(len({r.get("slug") for r in rows})==len(rows),"DUPLICATE_DRAFT_SLUG")
    all_reports=[seo_robot(files),references_robot(rows),reconcile_robot(rows,owned),
                 content_security_robot(files),capacity_robot(),worklist_robot(rows,owned)]
    jobs=all_reports[-1]
    stamp=datetime.now(timezone.utc).isoformat()
    private_write(WORKLIST,{"tenant":TENANT,"status":"private_publication_worklist",
             "observed_utc":stamp,"items":jobs["items"],"automatic_publication":False})
    all_reports[-1]={k:v for k,v in jobs.items() if k!="items"}
    report={"tenant":TENANT,"status":"six_extended_main_robots_executed",
            "observed_utc":stamp,"robot_count":len(all_reports),"roles":all_reports,
            "healthy":sum(r["status"]=="ok" for r in all_reports),
            "warnings":sum(r["status"]=="warning" for r in all_reports),
            "public_site_modified":False,"sibling_sites_modified":False,
            "finance_executed":False,"review_worklist_size":len(jobs["items"])}
    private_write(REPORT,report)
    return report

def main():
    parser=argparse.ArgumentParser(description="6 private MojPlayWin robot missions")
    parser.add_argument("--once",required=True,action="store_true")
    parser.parse_args()
    result=cycle()
    print(json.dumps({"tenant":TENANT,"status":result["status"],
                      "robots_executed":result["robot_count"],
                      "healthy":result["healthy"],"warnings":result["warnings"],
                      "private_worklist":result["review_worklist_size"],
                      "public_site_modified":False},sort_keys=True))

if __name__=="__main__":main()
