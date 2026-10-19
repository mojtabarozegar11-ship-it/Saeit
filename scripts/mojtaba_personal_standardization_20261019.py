#!/usr/bin/env python3
"""Guarded one-release standards upgrade for independent Mojtaba personal Django site.

Only the allowlisted templates are changed. Nothing outside this app, no DB writes,
no .htaccess, no uploads, no images, and no parent MojPlayWin pages are touched.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
MARK = "mpw-standard-20261019"
FILES = {
    "base": "templates/personal_site/base.html",
    "home": "templates/personal_site/core/home.html",
    "about": "templates/personal_site/core/about.html",
    "posts": "templates/personal_site/core/posts.html",
}
CSS = """
<style id="mpw-standard-20261019" media="all">
.mpw-standard-nav{max-width:1200px;margin:22px auto 38px;padding:clamp(18px,3vw,32px);border-radius:20px;border:1px solid #90734b;background:linear-gradient(135deg,#20211e,#151613);box-shadow:0 14px 44px rgba(0,0,0,.23);color:#f3e9d7}
.mpw-standard-nav h2{font:600 clamp(22px,3vw,32px)/1.3 Georgia,serif;color:#efd3a2;margin:0 0 9px}
.mpw-standard-nav p{color:#e1d6c2;line-height:1.75;margin:0 0 17px}
.mpw-standard-nav-links{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.mpw-standard-nav-links a{display:flex;align-items:center;justify-content:space-between;min-height:54px;padding:12px 16px;border-radius:12px;text-decoration:none!important;color:#f4e3c5!important;background:#2a2924;border:1px solid #796244;font:600 15px/1.45 system-ui,sans-serif;overflow-wrap:anywhere}
.mpw-standard-nav-links a:hover{background:#383327;border-color:#d6b477}
.mpw-standard-nav-links a:focus-visible{outline:3px solid #ffda84;outline-offset:3px}
@media(max-width:720px){.mpw-standard-nav{margin:14px 12px 25px;padding:19px}.mpw-standard-nav-links{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:390px){.mpw-standard-nav-links{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.mpw-standard-nav-links a{transition:none!important}}
</style>"""
NAV = """
<nav class="mpw-standard-nav" id="mpw-standard-20261019-navigation" aria-label="Explore the personal website">
<h2>Explore the professional profile</h2>
<p>Start with a concise biography, verified experience, selected work or the research journal. The full articles and photo collection remain available in their own sections.</p>
<div class="mpw-standard-nav-links">
<a href="/mojtaba.roozegar/about/">Biography <span aria-hidden="true">↗</span></a>
<a href="/mojtaba.roozegar/resume/">Professional résumé <span aria-hidden="true">↗</span></a>
<a href="/mojtaba.roozegar/projects/">Projects <span aria-hidden="true">↗</span></a>
<a href="/mojtaba.roozegar/blog/">Research journal <span aria-hidden="true">↗</span></a>
<a href="/mojtaba.roozegar/gallery/">Photo portfolio <span aria-hidden="true">↗</span></a>
<a href="/mojtaba.roozegar/contact/">Professional contact <span aria-hidden="true">↗</span></a>
</div>
</nav>
"""

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def paths(app: Path) -> dict:
    if app != APP or app.is_symlink() or not (app / "manage.py").is_file():
        raise RuntimeError("Independent personal Django application identity mismatch")
    result = {}
    for key, rel in FILES.items():
        p = app / rel
        if not p.is_file() or p.is_symlink() or p.resolve() != p:
            raise RuntimeError("Protected template absent or unsafe: " + rel)
        result[key] = p
    return result

def lazy_images(source: str, preserve_first: int) -> tuple[str,int]:
    count = 0
    changed = 0
    def modify(match):
        nonlocal count, changed
        tag = match.group(0)
        count += 1
        if count <= preserve_first:
            return tag
        if "loading=" not in tag.lower():
            tag = tag[:-1] + ' loading="lazy">'
            changed += 1
        if "decoding=" not in tag.lower():
            tag = tag[:-1] + ' decoding="async">'
        return tag
    return re.sub(r"<img\b[^>]*>",modify,source,flags=re.I),changed

def patch(name: str, source: str) -> str:
    if MARK in source:
        raise RuntimeError("Already installed: refusing duplicate standards markup")
    if name == "base":
        if source.count("</head>") != 1:
            raise RuntimeError("Unexpected base template head")
        return source.replace("</head>",CSS+"\n</head>",1)
    if name == "home":
        tag = "{% block content %}"
        if source.count(tag) != 1 or source.count("mpw-enterprise-v18-20261016-home") != 1:
            raise RuntimeError("Home structure/last known release mismatch")
        source = source.replace(tag,tag+"\n"+NAV,1)
        source,_=lazy_images(source,2)
        return source
    if name == "about":
        expected = "My previous experience includes serving as CEO of Zomorod Melal Agro-Industry Company"
        replacement = "I currently serve as CEO of Zomorod Melal Agro-Industry Company"
        if source.count(expected)>1:
            raise RuntimeError("Unexpected duplicate CEO reference")
        source = source.replace(expected,replacement,1)
        source,_=lazy_images(source,1)
        return source
    if name == "posts":
        if source.count("mpw-enterprise-v18-20261016-posts") != 1:
            raise RuntimeError("Journal release marker missing")
        # The site's ?page=2 query produces the same journal content as /blog/.
        # Preserve its correct canonical instead of misleading crawlers with a fake page 2.
        source,_=lazy_images(source,1)
        return source
    raise RuntimeError("Not on change allowlist")

def candidates(app):
    originals={name:path.read_text("utf-8") for name,path in paths(app).items()}
    planned={name:patch(name,body) for name,body in originals.items()}
    if planned["base"].count(MARK)!=1 or planned["home"].count(MARK)!=1:
        raise RuntimeError("Upgrade markers incomplete")
    if NAV not in planned["home"]:
        raise RuntimeError("Navigation missing")
    if planned["base"].count("{%") != originals["base"].count("{%"):
        raise RuntimeError("Base template Django blocks changed unexpectedly")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    sys.path.insert(0,str(app))
    import django
    django.setup()
    from django.template import engines
    engine=engines["django"].engine
    for key,html in planned.items():
        engine.from_string(html)
        print("PERSONAL_STANDARDS_TEMPLATE_PARSE_OK="+key,flush=True)
    return originals,planned

def replace_atomic(target: Path, data: bytes):
    if target.is_symlink() or target.resolve()!=target:
        raise RuntimeError("Refuse symlink mutation")
    import stat
    mode=stat.S_IMODE(target.stat().st_mode)
    fd,temp=tempfile.mkstemp(prefix=".mpw-standard-",dir=target.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),mode)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.lexists(temp):
            os.unlink(temp)

def install(app: Path, backup: Path):
    originals,planned=candidates(app)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Fresh backup directory required")
    backup.mkdir(parents=True,mode=0o700)
    meta={"app":str(app),"files":{}}
    try:
        for name,p in paths(app).items():
            old=originals[name].encode("utf-8")
            new=planned[name].encode("utf-8")
            b=backup/(name+".html")
            with b.open("xb") as f:
                os.fchmod(f.fileno(),0o600)
                f.write(old)
                f.flush()
                os.fsync(f.fileno())
            if b.read_bytes()!=old:
                raise RuntimeError("Backup verification failure")
            meta["files"][name]={"before":sha(old),"after":sha(new)}
        m=backup/"manifest.json"
        with m.open("x") as f:
            os.fchmod(f.fileno(),0o600)
            json.dump(meta,f,indent=2)
            f.flush()
            os.fsync(f.fileno())
        for name,p in paths(app).items():
            if sha(p.read_bytes())!=meta["files"][name]["before"]:
                raise RuntimeError("Concurrent template mutation; abort")
            replace_atomic(p,planned[name].encode())
        verify(app,backup)
    except BaseException:
        if (backup/"manifest.json").is_file():
            rollback(app,backup)
        raise
    print("PERSONAL_STANDARD_ONE_STAGE_INSTALLED=YES",flush=True)
    print("PERSONAL_STANDARD_BACKUP="+str(backup),flush=True)

def manifest(app: Path, backup: Path):
    if not backup.is_dir() or backup.is_symlink() or not (backup/"manifest.json").is_file():
        raise RuntimeError("Verified backup manifest absent")
    meta=json.loads((backup/"manifest.json").read_text("utf-8"))
    if meta.get("app")!=str(app) or set(meta.get("files",{}))!=set(FILES):
        raise RuntimeError("Manifest identity mismatch")
    return meta

def verify(app: Path,backup: Path):
    meta=manifest(app,backup)
    for name,p in paths(app).items():
        if sha(p.read_bytes())!=meta["files"][name]["after"]:
            raise RuntimeError("Post-install checksum failed: "+name)
        if sha((backup/(name+".html")).read_bytes())!=meta["files"][name]["before"]:
            raise RuntimeError("Backup checksum failed: "+name)
        print("PERSONAL_STANDARD_HASH_VERIFIED="+name,flush=True)
    print("PERSONAL_STANDARD_CONTENT_UNDELETED=YES",flush=True)

def rollback(app: Path, backup: Path):
    meta=manifest(app,backup)
    for name,p in paths(app).items():
        saved=(backup/(name+".html")).read_bytes()
        if sha(saved)!=meta["files"][name]["before"]:
            raise RuntimeError("Corrupted backup: "+name)
        if sha(p.read_bytes()) not in (meta["files"][name]["before"],meta["files"][name]["after"]):
            raise RuntimeError("Concurrent modification; refuse unsafe rollback: "+name)
    for name,p in paths(app).items():
        saved=(backup/(name+".html")).read_bytes()
        if sha(p.read_bytes())==meta["files"][name]["after"]:
            replace_atomic(p,saved)
    print("PERSONAL_STANDARD_ROLLBACK_VERIFIED=YES",flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","verify","rollback"))
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--backup",type=Path)
    args=parser.parse_args()
    if args.action=="check":
        candidates(args.app)
        print("PERSONAL_STANDARD_PREFLIGHT=YES",flush=True)
    else:
        if not args.backup:
            parser.error("--backup is required")
        {"install":install,"verify":verify,"rollback":rollback}[args.action](args.app,args.backup)

if __name__=="__main__":
    main()
