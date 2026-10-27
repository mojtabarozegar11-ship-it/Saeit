#!/usr/bin/env python3
"""Scope: main MojPlayWin dynamic page template + static /studio/ only."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ACCOUNT = Path("/home/zomorod2")
APP = ACCOUNT / "Saeit-staging"
SITE = ACCOUNT / "mojplaywin.com"
DYNAMIC = APP / "core/templates/brands/mojplaywin/page.html"
STUDIO = SITE / "design-preview-20261017/mpw-ten-editorials-20261018/pages/studio.html"
WSGI = SITE / "passenger_wsgi.py"
FIXES = {
    b'href="/#mpw-insight-title"': b'href="/mpw-editorial/field-guides/original-ten/"',
    b'href="/#field-library-round2"': b'href="/mpw-editorial/field-guides/20261023/index.html"',
    b'href="/#field-library-business"': b'href="/mpw-editorial/field-guides/20261023/index.html"',
    b'href="/#field-library-advanced"': b'href="/mpw-editorial/field-guides/20261023/index.html"',
}
REQUIRED = {
    "dynamic": tuple(FIXES),
    "studio": tuple(k for k in FIXES if b"business" not in k),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def targets():
    return {"dynamic": DYNAMIC, "studio": STUDIO}


def verify():
    for root in (APP,SITE):
        if not root.is_dir() or root.is_symlink():
            raise RuntimeError("UNSAFE_APP_ROOT:" + str(root))
    for path in (*targets().values(), WSGI, SITE / ".htaccess"):
        if not path.is_file() or path.is_symlink() or path.parent.is_symlink():
            raise RuntimeError("UNSAFE_SOURCE_FILE:" + str(path))
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
        raise RuntimeError("WSGI_SOURCE_BINDING_DRIFT")


def repair(name,raw):
    active={old:raw.count(old) for old in FIXES}
    if all(count==0 for count in active.values()):
        if (b'/mpw-editorial/field-guides/original-ten/' not in raw
            or b'/mpw-editorial/field-guides/20261023/index.html' not in raw):
            raise RuntimeError("UNEXPECTED_ALREADY_PATCHED_SOURCE:"+name)
        return raw
    for needle in REQUIRED[name]:
        if not active[needle]:
            raise RuntimeError("PARTIAL_LEGACY_LINK_DRIFT:"+name+":"+needle.decode())
    fixed=raw
    for old,new in FIXES.items():
        fixed=fixed.replace(old,new)
    if any(x in fixed for x in FIXES) or len(fixed)<len(raw):
        raise RuntimeError("GUIDE_LINK_REPAIR_VALIDATION_FAILED:"+name)
    # This release only expands URLs; every existing paragraph, product and game stays.
    assert sum(raw.count(x) for x in FIXES)>0
    return fixed


def atomic(path,raw):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-guide-link-release-",dir=str(path.parent))
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def backup(run):
    if not re.fullmatch(r"[0-9]{6,20}",run):
        raise RuntimeError("INVALID_RUN_ID")
    return ACCOUNT / (".mpw-main-guide-links-20261027-" + run)


def audit():
    verify()
    for name,path in targets().items():
        raw=path.read_bytes()
        print("MPW_GUIDE_SOURCE_AUDIT="+json.dumps({"file":name,"sha256":sha(raw),
            "bytes":len(raw),"legacy_counts":{key.decode():raw.count(key) for key in FIXES}},sort_keys=True))


def publish(run):
    verify()
    paths=targets()
    before={name:path.read_bytes() for name,path in paths.items()}
    after={name:repair(name,raw) for name,raw in before.items()}
    changes=[name for name in paths if after[name]!=before[name]]
    if not changes:
        print("MPW_GUIDES_ALREADY_APPLIED");return
    state=backup(run)
    if state.exists() or state.is_symlink():raise RuntimeError("BACKUP_COLLISION")
    state.mkdir(mode=0o700)
    manifest={"run":run,"files":{}}
    for name in changes:
        (state/(name+".before")).write_bytes(before[name])
        manifest["files"][name]={"before":sha(before[name]),"after":sha(after[name])}
    (state/"manifest.json").write_text(json.dumps(manifest,sort_keys=True))
    done=[]
    try:
        for name in changes:
            path=paths[name]
            if sha(path.read_bytes())!=sha(before[name]):
                raise RuntimeError("SOURCE_CONCURRENT_EDIT:"+name)
            atomic(path,after[name]);done.append(name)
            if sha(path.read_bytes())!=sha(after[name]):
                raise RuntimeError("SOURCE_POSTWRITE_MISMATCH:"+name)
    except BaseException:
        for name in reversed(done):
            if sha(paths[name].read_bytes())==sha(after[name]):
                atomic(paths[name],before[name])
        raise
    print("MPW_GUIDE_LINKS_RELEASED="+json.dumps({"changed":changes,
          "fixed_counts":{name:sum(before[name].count(old) for old in FIXES) for name in changes}},sort_keys=True))


def rollback(run):
    verify()
    state=backup(run)
    if not state.is_dir() or state.is_symlink():
        print("MPW_GUIDE_LINKS_NO_BACKUP");return
    manifest=json.loads((state/"manifest.json").read_text())
    if manifest.get("run")!=run:raise RuntimeError("WRONG_BACKUP_RUN")
    restore={}
    for name,checks in manifest["files"].items():
        raw=(state/(name+".before")).read_bytes()
        if sha(raw)!=checks["before"] or sha(targets()[name].read_bytes())!=checks["after"]:
            raise RuntimeError("ROLLBACK_HASH_DRIFT:"+name)
        restore[name]=raw
    for name,raw in restore.items():
        atomic(targets()[name],raw)
    print("MPW_GUIDE_LINKS_ROLLBACK_OK")


def refresh():
    verify()
    for root in (APP,SITE):
        folder=root/"tmp"
        if folder.is_symlink():raise RuntimeError("UNSAFE_RESTART_DIRECTORY")
        folder.mkdir(exist_ok=True)
        marker=folder/"restart.txt"
        if marker.is_symlink() or (marker.exists() and not marker.is_file()):
            raise RuntimeError("UNSAFE_RESTART_MARKER")
        marker.touch()
    print("MPW_MAIN_GUIDE_TEMPLATE_REFRESH_REQUESTED")


def selftest():
    fixture=(b'<main><a href="/#mpw-insight-title">One</a>'
             b'<a href="/#field-library-round2">Two</a>'
             b'<a href="/#field-library-business">Three</a>'
             b'<a href="/#field-library-advanced">Four</a></main>')
    fixed=repair("dynamic",fixture)
    assert b'href="/#field-library' not in fixed
    assert repair("dynamic",fixed)==fixed
    studio=fixture.replace(b'<a href="/#field-library-business">Three</a>',b'')
    assert repair("studio",studio).count(b'/mpw-editorial/field-guides/')==3
    print("MPW_GUIDE_LINKS_SELFTEST=PASS")


if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1] in ("audit","refresh","selftest"):
        {"audit":audit,"refresh":refresh,"selftest":selftest}[sys.argv[1]]()
    elif len(sys.argv)==3 and sys.argv[1] in ("publish","rollback"):
        (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("usage: audit | refresh | selftest | publish RUN_ID | rollback RUN_ID")
