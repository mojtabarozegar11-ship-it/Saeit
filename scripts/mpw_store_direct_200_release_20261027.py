#!/usr/bin/env python3
"""Remove only the legacy GET /store/ 307 canonical-bridge hop.

Never alters Django, commerce, invoice, other rewrite rules or sibling websites.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

ROOT = Path("/home/zomorod2")
SITE = ROOT / "mojplaywin.com"
RULES = SITE / ".htaccess"
WSGI = SITE / "passenger_wsgi.py"
EXPECTED_ORIGINAL_SHA256 = "4fb3130655b2aec1c35400c9b7fa7472fc36f5bcc99eab273a1a33d5ea197a45"
LEGACY = (
    b"RewriteCond %{REQUEST_METHOD} ^GET$\n"
    b"RewriteCond %{REQUEST_URI} ^/store/$\n"
    b"RewriteCond %{QUERY_STRING} !(^|&)__mpw_canon_passthru=1(&|$)\n"
    b"RewriteRule ^.*$ /design-preview-20261017/_mpw_main_canonical_bridge_20261017.php?__mpw_canon_route=store [END,QSA]\n"
)
MARKER = b"# MPW_STORE_DIRECT_DJANGO_200_20261027: isolated store canonical-hop removal\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_identity():
    if not SITE.is_dir() or SITE.is_symlink():
        raise RuntimeError("SITE_ROOT_NOT_REGULAR")
    for path in (RULES, WSGI):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("PROTECTED_SOURCE_NOT_REGULAR:"+str(path))
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8","replace"):
        raise RuntimeError("SHARED_DJANGO_BINDING_CHANGED")


def transform(raw, require_sha=True):
    if MARKER in raw:
        if raw.count(MARKER)!=1 or LEGACY in raw:
            raise RuntimeError("PARTIALLY_APPLIED_STORE_ROUTE_MARKER")
        return raw
    if raw.count(LEGACY)!=1:
        raise RuntimeError("LEGACY_STORE_BRIDGE_NOT_EXACTLY_UNIQUE")
    if require_sha and digest(raw)!=EXPECTED_ORIGINAL_SHA256:
        raise RuntimeError("HTACCESS_UNEXPECTED_CONCURRENT_BASELINE:"+digest(raw))
    newer=raw.replace(LEGACY,MARKER,1)
    if (LEGACY in newer or newer.count(MARKER)!=1
            or newer.count(b"RewriteCond %{REQUEST_URI} ^/store/$")!=0):
        raise RuntimeError("STORE_ROUTE_REWRITE_INCOMPLETE")
    if b"RewriteCond %{REQUEST_URI} ^/games/crown-defender/?$" not in newer:
        raise RuntimeError("PROTECTED_GAME_RULE_DISAPPEARED")
    return newer


def state_dir(run):
    if not re.fullmatch(r"[0-9]{6,20}",run):
        raise RuntimeError("INVALID_RUN_IDENTIFIER")
    return ROOT / (".mpw-store-200-20261027-" + run)


def atomic(path,raw):
    fd,temp=tempfile.mkstemp(prefix=".mpw-store-200-",dir=str(path.parent))
    try:
        os.fchmod(fd,stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd,"wb") as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def audit():
    verify_identity()
    raw=RULES.read_bytes()
    print("MPW_STORE_BRIDGE_SOURCE="+json.dumps({
        "sha256":digest(raw),"bytes":len(raw),
        "original_block_count":raw.count(LEGACY),
        "installed_marker_count":raw.count(MARKER),
        "django_host_binding":True
    },sort_keys=True))


def publish(run):
    verify_identity()
    before=RULES.read_bytes()
    after=transform(before)
    if before==after:
        print("MPW_STORE_CANONICAL_ALREADY_DIRECT");return
    state=state_dir(run)
    if state.exists() or state.is_symlink():
        raise RuntimeError("BACKUP_NAME_COLLISION")
    state.mkdir(mode=0o700)
    (state/"htaccess.before").write_bytes(before)
    (state/"manifest.json").write_text(json.dumps({
        "run":run,"original":digest(before),"updated":digest(after)
    },sort_keys=True))
    if digest(RULES.read_bytes())!=digest(before):
        raise RuntimeError("CONCURRENT_APACHE_EDIT")
    try:
        atomic(RULES,after)
        if digest(RULES.read_bytes())!=digest(after):
            raise RuntimeError("ATOMIC_APACHE_POSTWRITE_MISMATCH")
    except BaseException:
        if digest(RULES.read_bytes())==digest(after):
            atomic(RULES,before)
        raise
    print("MPW_STORE_DIRECT_200_PUBLISHED="+json.dumps({
        "from":digest(before),"to":digest(after),"path":"/store/"}))


def rollback(run):
    verify_identity()
    state=state_dir(run)
    if not state.is_dir() or state.is_symlink():
        print("MPW_STORE_DIRECT_200_NO_BACKUP");return
    meta=json.loads((state/"manifest.json").read_text())
    old=(state/"htaccess.before").read_bytes()
    if meta.get("run")!=run or digest(old)!=meta.get("original"):
        raise RuntimeError("INCOMPLETE_BACKUP")
    if digest(RULES.read_bytes())!=meta.get("updated"):
        raise RuntimeError("APACHE_CHANGED_SINCE_RELEASE_REFUSE_ROLLBACK")
    atomic(RULES,old)
    print("MPW_STORE_CANONICAL_ROLLBACK_VERIFIED")


def selftest():
    assert MARKER not in LEGACY
    original=(b"RewriteEngine On\n"+LEGACY+
              b"RewriteCond %{REQUEST_URI} ^/games/crown-defender/?$\n")
    updated=transform(original,require_sha=False)
    assert updated.count(MARKER)==1 and b"games/crown-defender" in updated
    assert transform(updated,require_sha=False)==updated
    print("MPW_STORE_DIRECT_200_SELFTEST=PASS")


if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1] in ("audit","selftest"):
        (audit if sys.argv[1]=="audit" else selftest)()
    elif len(sys.argv)==3 and sys.argv[1] in ("publish","rollback"):
        (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("usage: audit | selftest | publish RUN_ID | rollback RUN_ID")
