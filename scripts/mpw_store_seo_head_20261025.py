#!/usr/bin/env python3
"""Narrow, reversible MojPlayWin storefront search/snippet metadata fix.

Only the store-specific fallback head metadata in the verified Django shell
is changed. Does not touch orders, products, payment, emails, or site routing.
"""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
SITE = HOME / "mojplaywin.com"
BASE = APP / "core/templates/mojplaywin/site_base.html"
WSGI = SITE / "passenger_wsgi.py"
BACKUP_ROOT = HOME / ".private_mojplaywin_main_agents"
OLD_SHA = "70d1ff928d0660c7ba612d80796027dfc66a371918d8b779544c9d80a6a15771"
NEW_TITLE = "Digital Books & Website Kits | MojPlayWin"
NEW_DESC = ("Explore two original English digital books and an editable website kit. "
            "Compare listed prices and review account-based TRX checkout and private delivery terms.")
TITLE_OLD = '<title>{% block title %}MojPlayWin | Research, Games &amp; Learning{% endblock %}</title>'
TITLE_NEW = ('<title>{% block title %}{% if request.path == "/store/" %}'
             + NEW_TITLE + '{% else %}MojPlayWin | Research, Games &amp; Learning'
             '{% endif %}{% endblock %}</title>')
DESC_OLD = ('<meta name="description" content="{% block meta_description %}'
            'Explore MojPlayWin research, games, AI, digital products and learning resources.'
            '{% endblock %}">')
DESC_NEW = ('<meta name="description" content="{% block meta_description %}'
            '{% if request.path == "/store/" %}' + NEW_DESC +
            '{% else %}Explore MojPlayWin research, games, AI, digital products and learning resources.'
            '{% endif %}{% endblock %}">')
OG_TITLE_OLD = ('{% else %}MojPlayWin | Research, Games &amp; Learning{% endif %}">')
OG_TITLE_NEW = ('{% elif request.path == "/store/" %}' + NEW_TITLE +
                '{% else %}MojPlayWin | Research, Games &amp; Learning{% endif %}">')
OG_DESC_OLD = ('{% else %}Original games, practical research, learning and digital products.{% endif %}">')
OG_DESC_NEW = ('{% elif request.path == "/store/" %}' + NEW_DESC +
               '{% else %}Original games, practical research, learning and digital products.{% endif %}">')

def sha(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()

def run_id(s):
    if not re.fullmatch(r"[0-9]{9,20}", s):
        raise RuntimeError("Invalid workflow run ID")
    return s

def patch(source):
    text = source.decode("utf8")
    for old, new, label in (
        (TITLE_OLD, TITLE_NEW, "title"),
        (DESC_OLD, DESC_NEW, "description"),
        (OG_TITLE_OLD, OG_TITLE_NEW, "og:title"),
        (OG_DESC_OLD, OG_DESC_NEW, "og:description"),
    ):
        if text.count(old) != 1:
            raise RuntimeError("Unexpected " + label + " source count: " + str(text.count(old)))
        text = text.replace(old, new, 1)
    return text.encode("utf8")

def guard():
    if APP.is_symlink() or not APP.is_dir() or SITE.is_symlink() or not SITE.is_dir():
        raise RuntimeError("Pinned roots invalid")
    if BASE.is_symlink() or not BASE.is_file() or BASE.parent.is_symlink():
        raise RuntimeError("Pinned shell file invalid")
    if WSGI.is_symlink() or not WSGI.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text("utf8", "replace"):
        raise RuntimeError("Passenger root changed")
    if BACKUP_ROOT.is_symlink() or not BACKUP_ROOT.is_dir() or BACKUP_ROOT.stat().st_mode & 0o077:
        raise RuntimeError("Private backup root unavailable")
    if BASE.stat().st_size > 100000:
        raise RuntimeError("Unexpected shell size")

def atomic_write(path, data):
    fd, temp = tempfile.mkstemp(prefix=".mpw-seo-head-", dir=path.parent)
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def restart():
    for root in (APP, SITE):
        d = root / "tmp"
        if d.is_symlink():
            raise RuntimeError("Unsafe restart directory")
        d.mkdir(exist_ok=True)
        p = d / "restart.txt"
        if p.is_symlink() or (p.exists() and not p.is_file()):
            raise RuntimeError("Unsafe restart marker")
        p.touch()

def state(run):
    return BACKUP_ROOT / ("mpw-store-seo-head-" + run)

def install(run):
    run = run_id(run)
    guard()
    old = BASE.read_bytes()
    if sha(old) != OLD_SHA:
        raise RuntimeError("Live shell drift; no write")
    new = patch(old)
    import django.template
    django.template.Template(new.decode("utf8"))
    d = state(run)
    if d.exists() or d.is_symlink():
        raise RuntimeError("Backup collision")
    d.mkdir(mode=0o700)
    backup = d / "site_base.bak"
    with backup.open("xb") as f:
        os.fchmod(f.fileno(), 0o600)
        f.write(old)
        f.flush()
        os.fsync(f.fileno())
    manifest = {"run": run, "old": sha(old), "new": sha(new), "path": str(BASE)}
    mf = d / "manifest.json"
    with mf.open("x") as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(manifest, f)
        f.flush()
        os.fsync(f.fileno())
    if sha(BASE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Concurrent edit before install")
    try:
        atomic_write(BASE, new)
        if sha(BASE.read_bytes()) != manifest["new"]:
            raise RuntimeError("Write verification failed")
        restart()
    except BaseException:
        if sha(BASE.read_bytes()) == manifest["new"]:
            atomic_write(BASE, old)
            restart()
        raise
    print(json.dumps({"status": "INSTALLED", "run": run, "old_sha": manifest["old"],
                      "new_sha": manifest["new"], "scope": "store fallback head only",
                      "orders_or_payments_changed": False}))

def rollback(run):
    run = run_id(run)
    guard()
    d = state(run)
    if d.is_symlink() or not d.is_dir():
        raise RuntimeError("Backup unavailable")
    m = json.loads((d / "manifest.json").read_text("utf8"))
    old = (d / "site_base.bak").read_bytes()
    if m.get("run") != run or m.get("old") != OLD_SHA or sha(old) != OLD_SHA or m.get("path") != str(BASE):
        raise RuntimeError("Backup mismatch")
    if sha(BASE.read_bytes()) != m.get("new"):
        raise RuntimeError("Concurrent edit; rollback denied")
    atomic_write(BASE, old)
    if sha(BASE.read_bytes()) != OLD_SHA:
        raise RuntimeError("Rollback verification failed")
    restart()
    print(json.dumps({"status": "ROLLED_BACK", "run": run, "sha": OLD_SHA}))

def selftest():
    source = Path("core/templates/mojplaywin/site_base.html").read_bytes()
    if sha(source) != OLD_SHA:
        raise RuntimeError("Repository base shell changed; update review required")
    result = patch(source).decode("utf8")
    assert result.count(NEW_TITLE) == 2 and result.count(NEW_DESC) == 2
    assert result.count('request.path == "/store/"') == 4
    print("MPW_STORE_META_PATCH_SELFTEST=PASS")

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ("install", "rollback"):
        {"install": install, "rollback": rollback}[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit("Usage: script selftest | install RUN_ID | rollback RUN_ID")
