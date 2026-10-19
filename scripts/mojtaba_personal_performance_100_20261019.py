#!/usr/bin/env python3
"""Fix real Lighthouse hero-image priorities and redundant branding aria-label.
Changes only the independent personal site's home and base templates. Preserves images.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PATHS={"base":"templates/personal_site/base.html","home":"templates/personal_site/core/home.html"}
MARK="mpw-performance-fix-20261019"
def digest(data):return hashlib.sha256(data).hexdigest()
def paths(app):
    if app!=APP or app.is_symlink() or not (app/"manage.py").is_file():
        raise RuntimeError("Wrong app; no mutation allowed")
    d={}
    for name,rel in PATHS.items():
        p=app/rel
        if not p.is_file() or p.is_symlink() or p.resolve()!=p:
            raise RuntimeError("Missing or unsafe "+rel)
        d[name]=p
    return d
def attr(tag,name,value):
    p=r'\b'+re.escape(name)+r'\s*=\s*(["\']).*?\1'
    if re.search(p,tag,re.I|re.S):
        return re.sub(p,name+'="'+value+'"',tag,count=1,flags=re.I|re.S)
    return tag[:-1]+' '+name+'="'+value+'">'
def patch(name,source):
    if MARK in source:raise RuntimeError("Already installed")
    if name=="base":
        old='aria-label="Mojtaba Roozegar — Home"'
        if source.count(old)!=1:raise RuntimeError("Brand accessible-name drift")
        source=source.replace(old,"",1)
        if "</head>" not in source:raise RuntimeError("Head missing")
        return source.replace("</head>",'<meta name="mpw-performance-fix-20261019" content="optimized hero assets and semantics">\n</head>',1)
    if name=="home":
        if "mpw-complete-standard-20261019-toc" not in source:raise RuntimeError("Latest protected home not present")
        done={"primary":0,"hero":0}
        def transform(m):
            tag=m.group(0)
            # Above-fold text is the LCP; both photographs appear below the
            # first mobile viewport. Preserve URLs and original image quality.
            if "official_profile_20261016/portrait" in tag:
                key="primary"
            elif "mojtaba-roozegar.jpg" in tag and 'fetchpriority="high"' in tag:
                key="hero"
            else:return tag
            done[key]+=1
            tag=attr(tag,"loading","lazy")
            tag=attr(tag,"decoding","async")
            tag=attr(tag,"fetchpriority","low")
            return tag
        edited=re.sub(r"<img\b[^>]*>",transform,source,flags=re.I|re.S)
        if done != {"primary":1,"hero":1}:
            raise RuntimeError("Exact two below-fold photos not found: "+repr(done))
        # An HTML comment makes the version visible without altering any content.
        return edited.replace("{% block content %}","{% block content %}\n<!-- "+MARK+" -->",1)
    raise RuntimeError("Wrong allowlist")
def planned(app):
    original={n:p.read_text("utf8") for n,p in paths(app).items()}
    updated={n:patch(n,s) for n,s in original.items()}
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    sys.path.insert(0,str(app))
    import django;django.setup()
    from django.template import engines
    for n,text in updated.items():
        engines["django"].engine.from_string(text)
        print("PERF_TEMPLATE_PARSE_OK="+n,flush=True)
    return original,updated
def atomic(p,b):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-perf-",dir=p.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(p.stat().st_mode))
            f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def manifest(app,backup):
    if not backup.is_dir() or backup.is_symlink():raise RuntimeError("Backup missing")
    m=backup/"manifest.json"
    if not m.is_file() or m.is_symlink():raise RuntimeError("Backup manifest missing")
    data=json.loads(m.read_text("utf8"))
    if data.get("app")!=str(app) or set(data.get("files",{}))!=set(PATHS):
        raise RuntimeError("Backup identity mismatch")
    return data
def verify(app,backup):
    info=manifest(app,backup)
    for n,p in paths(app).items():
        if digest(p.read_bytes())!=info["files"][n]["after"]:raise RuntimeError("Live checksum mismatch "+n)
        if digest((backup/(n+".old")).read_bytes())!=info["files"][n]["before"]:raise RuntimeError("Backup checksum mismatch "+n)
    print("PERFORMANCE_SAFE_INSTALL_VERIFIED=YES",flush=True)
def rollback(app,backup):
    info=manifest(app,backup)
    pp=paths(app)
    for n,p in pp.items():
        old=(backup/(n+".old")).read_bytes()
        if digest(old)!=info["files"][n]["before"]:raise RuntimeError("Corrupt backup")
        if digest(p.read_bytes()) not in (info["files"][n]["before"],info["files"][n]["after"]):
            raise RuntimeError("Concurrent change refuse rollback")
    for n,p in pp.items():
        if digest(p.read_bytes())==info["files"][n]["after"]:
            atomic(p,(backup/(n+".old")).read_bytes())
    print("PERFORMANCE_AUTO_ROLLBACK=YES",flush=True)
def install(app,backup):
    original,updated=planned(app)
    if backup.exists() or backup.is_symlink():raise RuntimeError("Backup collision")
    backup.mkdir(mode=0o700,parents=True)
    info={"app":str(app),"files":{}}
    pp=paths(app)
    for n,p in pp.items():
        old=original[n].encode();new=updated[n].encode()
        with (backup/(n+".old")).open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
        info["files"][n]={"before":digest(old),"after":digest(new)}
    with (backup/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(info,f);f.flush();os.fsync(f.fileno())
    try:
        for n,p in pp.items():
            if digest(p.read_bytes())!=info["files"][n]["before"]:raise RuntimeError("Concurrent change")
            atomic(p,updated[n].encode())
        verify(app,backup)
    except BaseException:
        rollback(app,backup)
        raise
    print("PERFORMANCE_BELOW_FOLD_IMAGES_OPTIMIZED=YES",flush=True)
    print("PERFORMANCE_BACKUP="+str(backup),flush=True)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("action",choices=("check","install","verify","rollback"))
    ap.add_argument("--app",type=Path,default=APP)
    ap.add_argument("--backup",type=Path)
    a=ap.parse_args()
    if a.action=="check":
        planned(a.app);print("PERFORMANCE_PREFLIGHT=PASS",flush=True)
    else:
        if not a.backup:ap.error("--backup required")
        {"install":install,"verify":verify,"rollback":rollback}[a.action](a.app,a.backup)
if __name__=="__main__":main()
