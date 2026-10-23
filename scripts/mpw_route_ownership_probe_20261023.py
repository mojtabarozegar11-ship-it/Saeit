#!/usr/bin/env python3
"""Read-only route ownership diagnosis. No file mutation, import, shell calls or credentials."""
from pathlib import Path
import hashlib, os, re, json
HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
CANDIDATES=[ROOT,HOME/"Saeit-staging",HOME/"Saeit"]
KEYS=("password","token","secret","api_key","private_key","authorization","credential","passwd","database_url","dsn")
def safe_line(line):
    if any(word in line.lower() for word in KEYS):
        return "[REDACTED]"
    return line[:280]
def identity(path):
    p=Path(path)
    x={"path":str(p),"exists":p.exists(),"symlink":p.is_symlink()}
    if p.exists() and not p.is_symlink():
        s=p.stat();x.update(uid=s.st_uid,mode=oct(s.st_mode & 0o777),bytes=s.st_size,kind=("dir" if p.is_dir() else "file" if p.is_file() else "other"))
        if p.is_file() and s.st_size < 400000:
            x["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest()
    print("ROUTE_IDENTITY",json.dumps(x,sort_keys=True))
for root in CANDIDATES:
    identity(root)
    for rel in (".htaccess","passenger_wsgi.py","config/urls.py","core/urls.py","core/brand_views.py","core/mojplaywin_views.py","core/templates/mojplaywin/section.html"):
        p=root/rel
        if p.exists() and not p.is_symlink():identity(p)
        if p.is_file() and not p.is_symlink() and p.stat().st_size<200000 and rel in (".htaccess","passenger_wsgi.py"):
            for i,line in enumerate(p.read_text(errors="replace").splitlines(),1):
                if i>140: break
                print("ROUTER_LINE",json.dumps({"file":str(p),"line":i,"value":safe_line(line)}))
    for rel in ("config/urls.py","core/urls.py"):
        p=root/rel
        if not p.is_file() or p.is_symlink():continue
        for i,line in enumerate(p.read_text(errors="replace").splitlines(),1):
            if re.search(r"games|products|first.realm|digital.products|include\(|urlpatterns",line,re.I):
                print("ROUTE_SOURCE_LINE",json.dumps({"file":str(p),"line":i,"value":safe_line(line)}))
    if root == ROOT:
        continue
    count=0;matches=0;errors=0
    for directory, subdirs, files in os.walk(root):
        here=Path(directory)
        try:depth=len(here.relative_to(root).parts)
        except ValueError:continue
        subdirs[:]=[d for d in subdirs if not d.startswith(".") and d not in ("node_modules","venv",".venv","staticfiles","media","__pycache__","migrations","site-packages","backups") and depth<7]
        if count>8500 or matches>45:break
        for name in files:
            if not name.endswith((".py",".html",".jinja",".jinja2")):continue
            p=here/name
            try:
                if p.is_symlink() or p.stat().st_size>220000:continue
                count+=1
                b=p.read_bytes()
                if any(v in b.lower() for v in (b"first realm",b"reserved for the next independently",b"downloadable and software products",b"games -- mojplaywin",b"games - mojplaywin",b'def games(',b'def products(',b'path("games/"',b'path("products/"')):
                    matches+=1
                    print("CONTENT_OWNER_CANDIDATE",json.dumps({"file":str(p),"sha256":hashlib.sha256(b).hexdigest(),"bytes":len(b),"matched_markers":[term.decode() for term in (b"first realm",b"reserved for the next independently",b"downloadable and software products",b'def games(',b'def products(',b'path("games/"',b'path("products/"') if term in b.lower()]}))
            except (OSError,UnicodeError):errors+=1
    print("SOURCE_SCAN_SUMMARY",json.dumps({"root":str(root),"files_examined":count,"matches":matches,"errors":errors}))
