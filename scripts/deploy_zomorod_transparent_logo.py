"""Atomic, asset-only Zomorod approved logo deployment.

Only the root homepage, six already-created Nova company pages and the
site-local Django Admin branding are modified. Everything else is
treated as immutable. Caller has already staged source files privately.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE=Path.home()
WEB=BASE/"public_html"
APP=BASE/"Saeit"
STAGE=Path(sys.argv[1]).resolve()
BACKUP=STAGE.parent
ORIGINAL=BACKUP/"original"
NEW_PATH=b"/static/site/company/company-logo-transparent.png"
OLD_PATH=b"/static/site/company/company-logo.png"
ASSET=WEB/"static/site/company/company-logo-transparent.png"
OLD_ASSET=WEB/"static/site/company/company-logo.png"
PAGES={
 "root":WEB/"index.html",
 "company":WEB/"company/index.html",
 "about":WEB/"about/index.html",
 "services":WEB/"services/index.html",
 "industry":WEB/"industry/index.html",
 "research":WEB/"research/index.html",
 "knowledge":WEB/"knowledge/index.html",
 "admin":APP/"templates/admin/base_site.html",
}
PROTECTED=[
 WEB/".htaccess", OLD_ASSET,
 WEB/"agriculture/index.html",
 WEB/"site-heritage/home-before-redesign/index.html",
 WEB/"mohammad/index.html", WEB/"ghanadi/index.html",
 WEB/"amozeshgah/index.html",
]
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def atomic_copy(src,dest):
    temp=dest.with_name(dest.name+".zm-logo-stage")
    if temp.exists():raise RuntimeError("Temporary file exists; refusing overwrite")
    shutil.copy2(src,temp)
    try:
        os.chmod(temp,dest.stat().st_mode & 0o777)
        os.replace(temp,dest)
    finally:
        if temp.exists():temp.unlink()

def request(path,required=None):
    url="https://zomorodmelal.ir"+path
    q="?logo_release="+STAGE.parent.name
    p=subprocess.run(["curl","-sS","-L","--max-time","23","-o","-","-w","\\n%{http_code}",url+q],capture_output=True,timeout=30)
    data,sep,status=p.stdout.rpartition(b"\\n")
    code=status.decode("ascii","replace").strip() if sep else "missing"
    print("ZM_LOGO_HTTP="+path+" code="+code,flush=True)
    if p.returncode or code!="200":
        raise RuntimeError("Public HTTP verification failed: "+path)
    if required is not None and required not in data:
        raise RuntimeError("Expected logo missing from page: "+path)
    return data

def main():
    if not STAGE.is_dir() or not STAGE.parent.name:
        raise RuntimeError("No approved private staging")
    if any(p.is_symlink() or not p.is_file() for p in PROTECTED):
        raise RuntimeError("Original protected source missing or symlinked")
    if ASSET.exists() or ASSET.is_symlink():
        raise RuntimeError("Target transparent asset already exists; no overwrite permitted")
    logo=STAGE/"logo.png"
    png=logo.read_bytes()
    if not png.startswith(b"\\x89PNG\\r\\n\\x1a\\n") or b"tRNS" not in png or len(png)<4000:
        raise RuntimeError("Logo is not a verified indexed alpha PNG")
    checks={str(p):sha256(p) for p in PROTECTED}
    prepared={}
    for name,target in PAGES.items():
        if target.is_symlink() or not target.is_file():
            raise RuntimeError("Missing expected original page: "+name)
        approved=(STAGE/(name+".html")).read_bytes()
        old=target.read_bytes()
        if NEW_PATH not in approved or NEW_PATH in old:
            raise RuntimeError("Expected old/new logo ref not found: "+name)
        if approved.replace(NEW_PATH,OLD_PATH)!=old:
            raise RuntimeError("Non-logo content difference / concurrent edit: "+name)
        prepared[name]=approved
        previous=ORIGINAL/(name+".html")
        if previous.exists():raise RuntimeError("Backup file already exists: "+name)
        shutil.copy2(target,previous)
        if previous.read_bytes()!=old:
            raise RuntimeError("Backup validation failed: "+name)
        print("ZM_LOGO_VERIFIED_ORIGINAL="+name,flush=True)
    changed=[]
    uploaded=False
    try:
        tmp=ASSET.with_name(ASSET.name+".zm-logo-stage")
        if tmp.exists():raise RuntimeError("Stale logo asset stage present")
        shutil.copy2(logo,tmp)
        os.chmod(tmp,0o644)
        os.replace(tmp,ASSET)
        uploaded=True
        if ASSET.read_bytes()!=png:raise RuntimeError("Uploaded PNG mismatch")
        for name,target in PAGES.items():
            if target.read_bytes()!=(ORIGINAL/(name+".html")).read_bytes():
                raise RuntimeError("Concurrent content edit: "+name)
            atomic_copy(STAGE/(name+".html"),target)
            changed.append(name)
            print("ZM_LOGO_BRANDING_UPDATED="+name,flush=True)
        image=request("/static/site/company/company-logo-transparent.png")
        if image!=png:raise RuntimeError("Public image is different from approved image")
        for path in ("/","/company/","/about/","/services/",
                     "/industry/","/research/","/knowledge/"):
            request(path,NEW_PATH)
        for path in ("/agriculture/","/agriculture/genetics/",
                     "/mohammad/","/ghanadi/","/amozeshgah/"):
            request(path)
        for item,digest in checks.items():
            if sha256(Path(item))!=digest:
                raise RuntimeError("Protected content changed: "+Path(item).name)
        print("ZM_LOGO_PRESERVED_ORIGINAL_ASSET_AND_SUBSITES=yes",flush=True)
        print("ZM_LOGO_RELEASE=success",flush=True)
    except BaseException:
        for name in reversed(changed):
            target=PAGES[name]
            try:
                if target.read_bytes()==prepared[name]:
                    atomic_copy(ORIGINAL/(name+".html"),target)
            except Exception as exc:
                print("ZM_LOGO_ROLLBACK_MANUAL_CHECK="+name+" "+type(exc).__name__,flush=True)
        if uploaded and ASSET.is_file() and not ASSET.is_symlink() and ASSET.read_bytes()==png:
            ASSET.unlink()
        print("ZM_LOGO_RELEASE=rolled_back_after_failed_verification",flush=True)
        raise

if __name__=="__main__":
    main()
