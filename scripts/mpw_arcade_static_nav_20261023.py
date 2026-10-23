#!/usr/bin/env python3
"""Guarded Arcade Lab discovery cards on TWO owned static indexes only.

Never modifies Django, Passenger, /games/, /products/, other tenants or .htaccess.
Fails closed on mismatched site, version, markers or concurrent edits.
"""
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import sys
from pathlib import Path

HOME = Path("/home/zomorod2")
SITE = HOME / "mojplaywin.com"
PRIVATE = HOME / ".private_mpw_arcade_nav_20261023"
VERSION = "04ba43522db4af1762c99a5e60eb280cba1dd8b5"
REL = "/mpw-editorial/arcade-lab/20261022/"
MARKER = "mpw-arcade-discovery-20261023"
FILES = {
    "editorial": SITE / "mpw-editorial" / "index.html",
    "games_catalog": SITE / "game-releases" / "20261021" / "index.html",
}
ASSETS = (
    ("Game Economy Simulator", "economy-simulator", "Game economy planning and balancing dashboard"),
    ("Game QA Matrix", "qa-matrix", "Quality assurance checklist for browser game development"),
    ("Circuit Courier", "circuit-courier", "Circuit Courier playable logic puzzle on an electric grid"),
)

def digest(b):
    return hashlib.sha256(b).hexdigest()

def card(title, slug, alt):
    href = REL + slug + "/index.html"
    image = REL + "assets/" + slug + ".webp"
    return ('<a href="'+href+'" style="display:block;max-width:290px;text-decoration:none;color:inherit;'
            'border:1px solid #557591;border-radius:14px;padding:12px;background:#132238">'
            '<img src="'+image+'" alt="'+alt+'" loading="lazy" decoding="async" '
            'width="290" height="160" style="width:100%;height:auto;aspect-ratio:29/16;object-fit:cover;border-radius:9px">'
            '<strong style="display:block;margin:9px 0 3px;color:#ffe5af">'+title+'</strong>'
            '<small style="color:#b5c9dc">Open free browser experience →</small></a>')

def section():
    return ('\n<section id="'+MARKER+'" data-arcade-sha="'+VERSION+'" aria-label="MojPlayWin Arcade Lab" '
            'style="margin:22px 0;padding:17px;border:1px solid #526d81;border-radius:16px;background:#0b1728;color:#f2f5fa">'
            '<h2 style="margin:0 0 9px;color:#ffdc98">Arcade Lab — games and design tools</h2>'
            '<p style="color:#b7c8da">Play the free 60-level Circuit Courier puzzle, test game economy scenarios, '
            'and run a QA checklist. Explore 50 original field guides.</p>'
            '<div style="display:flex;flex-wrap:wrap;gap:12px">'+''.join(card(*v) for v in ASSETS)+'</div>'
            '<p><a style="color:#ffe5af" href="'+REL+'guides/index.html">Explore 50 independent guides →</a></p>'
            '</section>\n')

def patch(name, old):
    if not old.startswith("<!doctype html>") and not old.lstrip().lower().startswith("<!doctype html"):
        raise RuntimeError("Unexpected HTML doctype: " + name)
    if MARKER in old:
        if old.count('id="'+MARKER+'"') != 1 or VERSION not in old:
            raise RuntimeError("Unexpected existing marker: " + name)
        return old, False
    if name == "editorial":
        if "Knowledge &amp; Insights" not in old and "Knowledge & Insights" not in old:
            raise RuntimeError("Unknown managed editorial index")
    else:
        if "Five Original Browser Games" not in old or "pulse-forge/index.html" not in old:
            raise RuntimeError("Unknown game catalog index")
    closing = "</main>" if "</main>" in old else "</body>"
    if old.count(closing) != 1:
        raise RuntimeError("Ambiguous HTML insertion: " + name)
    updated = old.replace(closing, section()+closing, 1)
    assert updated.count('id="'+MARKER+'"') == 1
    assert all(REL + slug + "/index.html" in updated for _,slug,_ in ASSETS)
    return updated, True

def confirm_site():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Wrong cPanel account")
    if SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Unexpected main site")
    if not (SITE/".htaccess").is_file() or not (SITE/"passenger_wsgi.py").is_file():
        raise RuntimeError("Shared site identity missing")
    arc = SITE / REL.lstrip("/")
    manifest = arc / "release.json"
    if manifest.is_symlink() or not manifest.is_file() or json.loads(manifest.read_text()).get("git_sha") != VERSION:
        raise RuntimeError("Arcade Lab production version mismatch")
    for _,slug,_ in ASSETS:
        for p in (arc / slug / "index.html", arc / "assets" / (slug+".webp")):
            if p.is_symlink() or not p.is_file() or p.stat().st_size > 500000:
                raise RuntimeError("Missing or unsafe public asset")
    owner = SITE/"game-releases"/"20261021"/".mojplaywin-five-games-owner.json"
    if owner.is_symlink() or not owner.is_file() or json.loads(owner.read_text()).get("owner") != "mojplaywin-five-games-v2":
        raise RuntimeError("Existing game catalog not owned by safe publisher")
    for p in FILES.values():
        if p.is_symlink() or not p.is_file() or not (1000 < p.stat().st_size < 700000):
            raise RuntimeError("Untrusted existing static index")
        if p.stat().st_uid != os.getuid():
            raise RuntimeError("Unexpected owner for "+p.name)

def atomic_write(path, data):
    tmp = path.with_name("." + path.name + ".arcade-pending-" + str(os.getpid()))
    if tmp.exists() or tmp.is_symlink():
        raise RuntimeError("Pending file collision")
    try:
        with open(tmp,"xb") as fp:
            fp.write(data)
            fp.flush()
            os.fsync(fp.fileno())
        os.chmod(tmp, stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp,path)
    finally:
        if tmp.exists():
            tmp.unlink()

def operate(mode, run_id, commit):
    if not re.fullmatch(r"[0-9]{8,20}",run_id) or not re.fullmatch(r"[0-9a-f]{40}",commit):
        raise RuntimeError("Invalid run/commit identity")
    confirm_site()
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if PRIVATE.is_symlink() or PRIVATE.stat().st_uid != os.getuid():
        raise RuntimeError("Unsafe backup folder")
    os.chmod(PRIVATE,0o700)
    with open(PRIVATE/"lock","a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        receipt = PRIVATE/("receipt-"+run_id+".json")
        if mode == "install":
            if receipt.exists():
                raise RuntimeError("Existing run receipt")
            snapshots,changes={},{}
            for name,path in FILES.items():
                raw=path.read_bytes()
                old=raw.decode("utf-8")
                new,changed=patch(name,old)
                snapshots[name]={"pre_sha256":digest(raw),"post_sha256":digest(new.encode()),"changed":changed}
                changes[name]=(raw,new.encode(),changed)
            if not any(c for _,_,c in changes.values()):
                print("ALREADY_INSTALLED_CORRECT_VERSION", VERSION)
                return
            for name,(raw,_,changed) in changes.items():
                if changed:
                    backup=PRIVATE/("backup-"+run_id+"-"+name+".html")
                    with open(backup,"xb") as fp:
                        fp.write(raw);fp.flush();os.fsync(fp.fileno())
                    os.chmod(backup,0o600)
            info={"run_id":run_id,"commit":commit,"version":VERSION,"files":snapshots}
            with open(receipt,"x") as fp:
                json.dump(info,fp);fp.flush();os.fsync(fp.fileno())
            os.chmod(receipt,0o600)
            updated=[]
            try:
                for name,(raw,out,changed) in changes.items():
                    if changed:
                        if digest(FILES[name].read_bytes())!=digest(raw):
                            raise RuntimeError("Concurrent change: "+name)
                        atomic_write(FILES[name],out)
                        updated.append(name)
                print("GUARDED_ARCADE_NAV_INSTALLED",json.dumps(info,sort_keys=True))
            except Exception:
                for name in reversed(updated):
                    if digest(FILES[name].read_bytes())==snapshots[name]["post_sha256"]:
                        atomic_write(FILES[name],changes[name][0])
                raise
        elif mode == "rollback":
            if not receipt.is_file() or receipt.is_symlink():
                raise RuntimeError("No exact receipt to roll back")
            info=json.loads(receipt.read_text())
            if any(info[k]!=v for k,v in (("run_id",run_id),("commit",commit),("version",VERSION))):
                raise RuntimeError("Wrong rollback identity")
            for name,record in info["files"].items():
                if not record["changed"]:
                    continue
                path=FILES[name]
                backup=PRIVATE/("backup-"+run_id+"-"+name+".html")
                if not backup.is_file() or backup.is_symlink():
                    raise RuntimeError("Backup unavailable")
                raw=backup.read_bytes()
                if digest(raw)!=record["pre_sha256"] or digest(path.read_bytes())!=record["post_sha256"]:
                    raise RuntimeError("Concurrent edit - refuse destructive rollback: "+name)
                atomic_write(path,raw)
                print("ARCADE_NAV_RESTORED",name)
        else:
            raise RuntimeError("Unknown command")

def selftest():
    a='<!doctype html><html><title>Knowledge &amp; Insights</title><body><main>MojPlayWin</main></body></html>'
    b='<!doctype html><html><title>Five Original Browser Games</title><body><main>pulse-forge/index.html</main></body></html>'
    for n,source in (("editorial",a),("games_catalog",b)):
        out,changed=patch(n,source)
        assert changed and source in out.replace(section(),"")
        again,changed=patch(n,out)
        assert not changed and again==out
    for broken in ("", "<html><body></body></html>", a.replace("Knowledge","KnowledgeX")):
        try:patch("editorial",broken)
        except RuntimeError:pass
        else:raise AssertionError("Unexpected accepted HTML")
    print("ARCADE_NAV_UNIT_PATCH_IDEMPOTENCY_FAIL_CLOSED_PASS")

if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:
        selftest()
    elif len(sys.argv)==4:
        operate(sys.argv[1],sys.argv[2],sys.argv[3])
    else:
        raise SystemExit("selftest | install RUN_ID SHA | rollback RUN_ID SHA")
