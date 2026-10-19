#!/usr/bin/env python3
"""Lighthouse-evidence-driven low-risk contrast and touch-target hotfix.
Changes only personal-site base template; preserves all existing site markup.
"""
from __future__ import annotations
import argparse,hashlib,json,os,stat,sys,tempfile
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
REL="templates/personal_site/base.html"
MARK="mpw-lighthouse-longform-20261019"
CSS=r"""
<style id="mpw-lighthouse-longform-20261019">
/* Final mobile longform index anchors: prevent virtual overlap. */
body main#main > section#mpw-journal-longform-index-20261016{
 content-visibility:visible!important;contain-intrinsic-size:none!important;
 position:relative!important;isolation:isolate;z-index:2!important;
}
body main#main > section#mpw-journal-longform-index-20261016 nav.link-grid{
 display:grid!important;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr))!important;
 gap:14px!important;position:relative!important;z-index:3!important;
}
body main#main > section#mpw-journal-longform-index-20261016 nav.link-grid>a{
 display:flex!important;position:relative!important;z-index:4!important;isolation:isolate;
 align-items:center!important;min-height:52px!important;box-sizing:border-box;
 padding:14px 16px!important;margin:0!important;line-height:1.6!important;
}
</style>"""
def digest(b):return hashlib.sha256(b).hexdigest()
def target(app):
    if app!=APP or app.is_symlink() or not (app/"manage.py").is_file():
        raise RuntimeError("Application allowlist mismatch")
    p=app/REL
    if not p.is_file() or p.is_symlink() or p.resolve()!=p:
        raise RuntimeError("Protected template missing")
    return p
def plan(app):
    orig=target(app).read_text("utf8")
    if MARK in orig:raise RuntimeError("Already installed")
    if orig.count("</head>")!=1:raise RuntimeError("HTML head drifted")
    for old in ("mpw-standard-20261019","mpw-complete-standard-20261019","mpw-lighthouse-a11y-20261019","mpw-lighthouse-targets-20261019"):
        if old not in orig:raise RuntimeError("Earlier protected release missing "+old)
    edited=orig.replace("</head>",CSS+"\n</head>",1)
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django;django.setup()
    from django.template import engines
    engines["django"].engine.from_string(edited)
    print("LIGHTHOUSE_LONGFORM_TEMPLATE_PREFLIGHT=PASS",flush=True)
    return orig.encode(),edited.encode()
def atomic(p,b):
    fd,name=tempfile.mkstemp(prefix=".a11y-",dir=p.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(p.stat().st_mode))
            f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(name,p)
    finally:
        if os.path.lexists(name):os.unlink(name)
def manifest(app,backup):
    if backup.is_symlink() or not backup.is_dir():raise RuntimeError("Unsafe backup")
    m=backup/"manifest.json"
    if not m.is_file() or m.is_symlink():raise RuntimeError("Missing manifest")
    x=json.loads(m.read_text("utf8"))
    if x.get("app")!=str(app) or x.get("file")!=REL:raise RuntimeError("Manifest mismatch")
    return x
def install(app,backup):
    original,edited=plan(app)
    p=target(app)
    if backup.exists() or backup.is_symlink():raise RuntimeError("Backup collision")
    backup.mkdir(mode=0o700,parents=True)
    b=backup/"base.original"
    with b.open("xb") as f:
        os.fchmod(f.fileno(),0o600);f.write(original);f.flush();os.fsync(f.fileno())
    m={"app":str(app),"file":REL,"before":digest(original),"after":digest(edited)}
    with (backup/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(m,f);f.flush();os.fsync(f.fileno())
    if p.read_bytes()!=original:raise RuntimeError("Concurrent modification")
    try:
        atomic(p,edited)
        verify(app,backup)
    except BaseException:
        rollback(app,backup)
        raise
    print("LIGHTHOUSE_LONGFORM_ONE_STAGE_INSTALLED=YES",flush=True)
    print("LIGHTHOUSE_LONGFORM_BACKUP="+str(backup),flush=True)
def verify(app,backup):
    m=manifest(app,backup)
    if digest(target(app).read_bytes())!=m["after"]:raise RuntimeError("Live template not matching approved patch")
    if digest((backup/"base.original").read_bytes())!=m["before"]:raise RuntimeError("Corrupt backup")
    print("LIGHTHOUSE_LONGFORM_HASH_VERIFIED=YES",flush=True)
def rollback(app,backup):
    m=manifest(app,backup);p=target(app);now=digest(p.read_bytes())
    if now not in (m["before"],m["after"]):raise RuntimeError("Concurrent modification; refusing rollback")
    orig=(backup/"base.original").read_bytes()
    if digest(orig)!=m["before"]:raise RuntimeError("Invalid backup")
    if now==m["after"]:atomic(p,orig)
    print("LIGHTHOUSE_LONGFORM_ROLLBACK=YES",flush=True)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("check","install","verify","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--backup",type=Path)
    a=p.parse_args()
    if a.action=="check":plan(a.app)
    else:
        if not a.backup:p.error("backup required")
        {"install":install,"verify":verify,"rollback":rollback}[a.action](a.app,a.backup)
if __name__=="__main__":main()
