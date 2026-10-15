#!/usr/bin/env python3
"""Narrow, reversible Astra preview route installation on one verified app."""
import argparse
import hashlib
import os
from pathlib import Path
import tempfile

IMPORT_ANCHOR = "from core.brand import brand_for_request"
IMPORT_NEW = "from core.astra_preview_views import astra_preview_page"
URL_ANCHOR = 'urlpatterns = [\n    path("", branded_home, name="home"),'
ROUTES = (
    '    path("factory-previews/", astra_preview_page, name="astra_preview_index"),\n',
    '    path("factory-previews/<slug:slug>/", astra_preview_page, name="astra_preview_detail"),\n',
)


def plan(app, module, backupdir):
    root=Path(app)
    source=Path(module)
    backups=Path(backupdir)
    if (root.is_symlink() or root.name!="Saeit-staging" or
            not (root/"manage.py").is_file() or
            source.is_symlink() or not source.is_file() or source.stat().st_size>20_000 or
            backups.is_symlink() or not backups.is_dir()):
        raise ValueError("unknown application, source, or private backup directory")
    urls=root/"config/urls.py"
    target=root/"core/astra_preview_views.py"
    if urls.is_symlink() or not urls.is_file() or target.is_symlink():
        raise ValueError("unsafe Django module")
    payload=source.read_bytes()
    compile(payload, str(target), "exec")
    prior_guard = (
        b'    hostname = request.get_host().split(":", 1)[0].lower().rstrip(".")\\n'
        b'    if hostname not in {"mojplaywin.com", "www.mojplaywin.com"}:\\n'
        b'        raise Http404("Not found")\\n'
    )
    old_allowed = payload.replace(prior_guard, b"", 1)
    if target.exists() and target.read_bytes() not in (payload, old_allowed):
        raise ValueError("existing Astra preview module conflicts")
    old=urls.read_text(encoding="utf-8")
    if ((IMPORT_NEW in old) != (ROUTES[0] in old and ROUTES[1] in old)):
        raise ValueError("partial Astra URL integration")
    if IMPORT_NEW in old:
        if old.count(IMPORT_NEW)!=1 or old.count(ROUTES[0])!=1 or old.count(ROUTES[1])!=1:
            raise ValueError("duplicate Astra URL integration")
        updated=old
    else:
        if old.count(IMPORT_ANCHOR)!=1 or old.count(URL_ANCHOR)!=1:
            raise ValueError("active URL route anchors missing; no overwrite")
        updated=old.replace(IMPORT_ANCHOR,IMPORT_ANCHOR+"\n"+IMPORT_NEW)
        updated=updated.replace(URL_ANCHOR,'urlpatterns = [\n'+ROUTES[0]+ROUTES[1]+'    path("", branded_home, name="home"),')
    compile(updated,str(urls),"exec")
    return {"urls":urls,"target":target,"old":old,"new":updated,
            "payload":payload,"backups":backups}


def write_new(path,data,mode):
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,"wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def apply(plan, *, commit=False):
    if not commit:
        return {"status":"DRY_RUN","modified_url":plan["old"]!=plan["new"],
                "new_module":not plan["target"].exists()}
    if not plan["target"].exists():
        write_new(plan["target"],plan["payload"],0o644)
    elif plan["target"].read_bytes()!=plan["payload"]:
        old_module=plan["target"].read_bytes()
        sha=hashlib.sha256(old_module).hexdigest()[:20]
        backup=plan["backups"]/("before-astra-preview-module-"+sha+".py")
        if not backup.exists():
            write_new(backup,old_module,0o600)
        elif backup.read_bytes()!=old_module:
            raise ValueError("existing module backup differs")
        fd,tmp=tempfile.mkstemp(prefix=".astra-preview-",dir=str(plan["target"].parent))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(plan["payload"])
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp,plan["target"].stat().st_mode & 0o777)
            os.replace(tmp,plan["target"])
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    if plan["old"]!=plan["new"]:
        checksum=hashlib.sha256(plan["old"].encode()).hexdigest()[:20]
        backup=plan["backups"]/("before-astra-preview-urls-"+checksum+".py")
        if not backup.exists():
            write_new(backup,plan["old"].encode(),0o600)
        elif backup.read_text(encoding="utf-8")!=plan["old"]:
            raise ValueError("existing URL backup differs")
        fd,tmp=tempfile.mkstemp(prefix=".astra-urls-",dir=str(plan["urls"].parent))
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as f:
                f.write(plan["new"])
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp,plan["urls"].stat().st_mode & 0o777)
            os.replace(tmp,plan["urls"])
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    return {"status":"ROUTES_REGISTERED","modified_url":plan["old"]!=plan["new"],
            "new_module":True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app",required=True)
    parser.add_argument("--module-source",required=True)
    parser.add_argument("--backups",required=True)
    parser.add_argument("--apply",action="store_true")
    a=parser.parse_args()
    result=apply(plan(a.app,a.module_source,a.backups),commit=a.apply)
    for k,v in sorted(result.items()):
        print("ASTRA_ROUTE_"+k.upper()+"="+str(v))


if __name__=="__main__":
    main()
