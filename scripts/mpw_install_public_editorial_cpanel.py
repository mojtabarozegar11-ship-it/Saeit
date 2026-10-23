"""Install isolated, SHA-checked MojPlayWin public editorial publisher.

Main docroot gets ONLY the new owned /mpw-standalone-guides/ subtree. We do NOT edit
Apache .htaccess, Django, Passenger, shared app, payments, personal or sibling
subsites. External public HTTP canary must pass before finalizing the release.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

TENANT="mojplaywin-main"
ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=ROOT/"v91_verified_main_port_20261018"
EVO=ROOT/"evolution_runtime_20261018"
ENGINE=STAGE/"mpw_v91_port"
SCRIPTS=STAGE/"scripts"
DOCROOT=Path("/home/zomorod2/mojplaywin.com")
ALLOWED={"page_content_factory.py":ENGINE/"page_content_factory.py",
         "public_editorial_publisher.py":ENGINE/"public_editorial_publisher.py",
         "mpw_static_editorial_release_control.py":SCRIPTS/"mpw_static_editorial_release_control.py"}
NEW=("public_editorial_publisher.py","mpw_static_editorial_release_control.py")

def need(ok,why):
    if not ok:raise RuntimeError(why)

def private(path):
    return path.is_dir() and not path.is_symlink() and not (path.stat().st_mode & 0o077)

def read_input():
    data=sys.stdin.buffer.read(160001)
    need(0<len(data)<=160000,"INVALID_PUBLIC_EDITORIAL_PACKAGE_SIZE")
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as bundle:
        names=bundle.getnames()
        need(len(names)==4 and set(names)==set(ALLOWED)|{"manifest.json"},"PUBLIC_PACKAGE_PATH_VIOLATION")
        files={}
        for name in names:
            row=bundle.getmember(name)
            need(row.isfile() and 0<row.size<31000,"INVALID_PUBLIC_SOURCE_MEMBER")
            files[name]=bundle.extractfile(row).read()
    manifest=json.loads(files.pop("manifest.json"))
    need(manifest.get("tenant")==TENANT
         and manifest.get("scope")=="main_mpw_editorial_only"
         and set(manifest.get("sha256",{}))==set(ALLOWED),"PUBLIC_PUBLISH_MANIFEST_INVALID")
    for name,code in files.items():
        need(hashlib.sha256(code).hexdigest()==manifest["sha256"][name],
             "UNEXPECTED_PUBLIC_PUBLISH_SOURCE_HASH")
        compile(code,name,"exec")
    return files

def atom(path,raw):
    need(not path.is_symlink(),"PUBLIC_PUBLISH_SOURCE_SYMLINK")
    fd,temp=tempfile.mkstemp(prefix=".mpw-standalone-guides-source-",dir=str(path.parent))
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"wb") as w:
            w.write(raw);w.flush();os.fsync(w.fileno())
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def main():
    os.umask(0o077)
    need(os.geteuid()==DOCROOT.stat().st_uid,"CPANEL_MAIN_DOCROOT_OWNER_MISMATCH")
    sources=read_input()
    need(all(private(p) for p in (ROOT,STAGE,EVO,ENGINE,STAGE/"operator_state")),
         "PRIVATE_PUBLISH_SOURCE_STAGE_INVALID")
    need(DOCROOT.is_dir() and not DOCROOT.is_symlink()
         and (DOCROOT/"passenger_wsgi.py").is_file()
         and not (DOCROOT/"passenger_wsgi.py").is_symlink()
         and (DOCROOT/".htaccess").is_file()
         and not (DOCROOT/".htaccess").is_symlink(),"WRONG_OR_SHARED_PUBLIC_DOCUMENTROOT")
    need((STAGE/"operator_state/enabled").read_text().strip()
         =="MPW_V91_MAIN_ONLY_PRIVATE_20261018","PRIVATE_MPW_MAIN_OWNER_FLAG")
    current=ALLOWED["page_content_factory.py"]
    need(current.is_file() and not current.is_symlink()
         and hashlib.sha256(current.read_bytes()).hexdigest()
            ==hashlib.sha256(sources["page_content_factory.py"]).hexdigest(),
         "ACTIVE_PRIVATE_PAGE_FACTORY_SOURCE_DIFFERS")
    gen65=json.loads((EVO/"gen65_operational_report.json").read_text())
    need(gen65.get("tenant")==TENANT
         and gen65.get("status")=="gen65_operational_private","GEN65_NOT_CURRENTLY_OPERATIONAL")
    if SCRIPTS.exists():
        need(private(SCRIPTS),"UNRELATED_PRIVATE_SCRIPT_DIR_NOT_OWNED")
    else:SCRIPTS.mkdir(mode=0o700)
    previous={}
    for name in NEW:
        path=ALLOWED[name]
        need(not path.is_symlink(),"EXISTING_PUBLICATION_SOURCE_SYMLINK")
        previous[path]=path.read_bytes() if path.exists() else None
    try:
        for name in NEW: atom(ALLOWED[name],sources[name])
        for name in NEW:
            need(hashlib.sha256(ALLOWED[name].read_bytes()).hexdigest()
                 ==hashlib.sha256(sources[name]).hexdigest(),
                 "PUBLICATION_INSTALLED_SOURCE_HASH_MISMATCH")
        p=subprocess.run(["/usr/bin/python3","-B",str(ALLOWED["mpw_static_editorial_release_control.py"]),
                          "--publish"],text=True,capture_output=True,timeout=35)
        need(p.returncode==0,"STATIC_PUBLICATION_PRECHECK_OR_DEPLOY_FAILED:"+p.stderr[-450:])
        result=json.loads(p.stdout)
        need(result["status"] in ("already_published_no_change","published_standalone_awaiting_external_smoke")
             and (DOCROOT/"mpw-standalone-guides/index.html").is_file(),
             "STATIC_PUBLICATION_DOCUMENT_NOT_WRITTEN")
        print(json.dumps({"status":"MPW_EDITORIAL_STANDALONE_FIRST_RELEASE_STAGED",
            "server_status":result["status"],"source_sha256":hashlib.sha256(sources["public_editorial_publisher.py"]).hexdigest(),
            "public_prefix":"/mpw-standalone-guides/","articles":result["articles"],
            "original_htaccess_modified":False,"shared_django_modified":False,
            "passenger_restart":False,"other_sites_modified":False,
            "external_http_smoke_pending":True},sort_keys=True))
    except BaseException:
        for path,old in previous.items():
            if old is None:
                if path.exists() and not path.is_symlink():path.unlink()
            else:atom(path,old)
        raise

if __name__=="__main__":main()
