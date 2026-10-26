#!/usr/bin/env python3
"""Transactional, exact-path-only installer for Mojtaba's independent Django app.

A new route + a new isolated package + a new PRIVATE db are the only targets.
Never edits shared MojPlayWin/Zomorod projects, factory, main cPanel settings or secrets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile

LIVE_APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
LIVE_BACKUP = Path("/home/zomorod2/.backups/mojtaba-social-control")
LIVE_PRIVATE = Path("/home/zomorod2/.mpw-social-hub-private")
MARK_BEGIN = "# MPW_SOCIAL_COMMAND_ISOLATED_BEGIN_20261026"
MARK_END = "# MPW_SOCIAL_COMMAND_ISOLATED_END_20261026"
ROUTE = (
    "\n" + MARK_BEGIN + "\n"
    "from django.urls import include as _mpw_social_include, path as _mpw_social_path\n"
    "urlpatterns.append(_mpw_social_path('social-command/', _mpw_social_include('social_hub.urls')))\n"
    + MARK_END + "\n"
)

class InstallationBlocked(RuntimeError):
    pass

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(p):
    return p.read_bytes()

def _resolve_urls(app):
    manage = app / "manage.py"
    if not manage.is_file() or manage.is_symlink():
        raise InstallationBlocked("Expected personal manage.py missing")
    match = re.search(r"DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([A-Za-z_][A-Za-z_0-9.]*)['\"]", 
                      manage.read_text(encoding="utf-8"))
    if not match:
        raise InstallationBlocked("Unknown Django settings module; refuse guessing")
    settings = app / (match.group(1).replace(".", "/") + ".py")
    if not settings.is_file() or settings.is_symlink():
        raise InstallationBlocked("Django settings path not safely resolved")
    smatch = re.search(r"\bROOT_URLCONF\s*=\s*['\"]([A-Za-z_][A-Za-z_0-9.]*)['\"]",
                       settings.read_text(encoding="utf-8"))
    if not smatch:
        raise InstallationBlocked("ROOT_URLCONF not an audited literal; refuse guessing")
    urls = app / (smatch.group(1).replace(".", "/") + ".py")
    if (not urls.is_file() or urls.is_symlink()
        or not urls.resolve(strict=True).is_relative_to(app.resolve(strict=True))):
        raise InstallationBlocked("Personal URLconf missing or outside app")
    before = urls.read_text(encoding="utf-8")
    if "urlpatterns" not in before:
        raise InstallationBlocked("Personal URLconf incompatible")
    return urls,before

def _sources(package):
    if not package.is_dir() or package.is_symlink() or package.name != "social_hub":
        raise InstallationBlocked("Expected isolated source package missing")
    result = {}
    for p in package.rglob("*"):
        if "__pycache__" in p.parts or p.suffix == ".pyc" or p.name == "site_config.py":
            continue
        if p.is_symlink():
            raise InstallationBlocked("Symlink in deployment source")
        if p.is_file():
            rel = str(p.relative_to(package))
            if (not rel.endswith(".py") or "__pycache__" in rel or
                not re.fullmatch(r"[A-Za-z0-9_./-]{1,180}",rel)):
                raise InstallationBlocked("Unexpected source file")
            result[rel] = sha(read(p))
        elif not p.is_dir():
            raise InstallationBlocked("Unexpected source entry")
    for mandatory in ("__init__.py","catalog.py","store.py","service.py","portal.py","urls.py"):
        if mandatory not in result:
            raise InstallationBlocked("Missing source file " + mandatory)
    return result

def plan(app, source):
    if not app.is_dir() or app.is_symlink() or not app.resolve().is_dir():
        raise InstallationBlocked("Personal Django root missing or symlinked")
    files = _sources(source)
    urls, before = _resolve_urls(app)
    if MARK_BEGIN in before or MARK_END in before or (app/"social_hub").exists():
        raise InstallationBlocked("Already installed or path collides; never overwrite")
    if "social-command/" in before:
        raise InstallationBlocked("Conflicting personal URL already exists")
    return {"urlconf":urls,"before":before,"package_files":files}

def _atomic(path, content):
    fd,tmp = tempfile.mkstemp(prefix=".mpw-social-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp,stat.S_IMODE(path.stat().st_mode))
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def _manifest_dir(root, run_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{6,80}", run_id):
        raise InstallationBlocked("Invalid deployment run ID")
    return root/run_id

def install(app,source,backup,private,run_id):
    cfg = plan(app,source)
    bdir = _manifest_dir(backup,run_id)
    if bdir.exists():
        raise InstallationBlocked("Backup run-id collision")
    if backup.is_symlink() or private.is_symlink():
        raise InstallationBlocked("Private destination symlink forbidden")
    backup.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(backup,0o700)
    bdir.mkdir(mode=0o700)
    pkg = app/"social_hub"
    temp_pkg = app/(".mpw-social-stage-"+run_id)
    before_bytes = cfg["before"].encode("utf-8")
    after_bytes = (cfg["before"]+ROUTE).encode("utf-8")
    manifest = {"urlconf":str(cfg["urlconf"]),"before_sha":sha(before_bytes),
                "after_sha":sha(after_bytes),"package_files":cfg["package_files"],
                "private_db":str(private/"social.sqlite"),"package_path":str(pkg)}
    (bdir/"original_urls.py").write_bytes(before_bytes)
    (bdir/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    os.chmod(bdir/"original_urls.py",0o600)
    os.chmod(bdir/"manifest.json",0o600)
    patched = False
    installed = False
    try:
        if temp_pkg.exists():
            raise InstallationBlocked("Temporary installation name collision")
        shutil.copytree(source,temp_pkg,symlinks=False)
        for path in temp_pkg.rglob("*"):
            if path.is_dir(): os.chmod(path,0o700)
            else: os.chmod(path,0o600)
        site_cfg = temp_pkg/"site_config.py"
        site_cfg.write_text("PRIVATE_DB = "+repr(str(private/"social.sqlite"))+"\n",encoding="utf-8")
        os.chmod(site_cfg,0o600)
        for rel,digest in cfg["package_files"].items():
            if sha(read(temp_pkg/rel)) != digest:
                raise InstallationBlocked("Staged package checksum mismatch")
        os.rename(temp_pkg,pkg)
        installed = True
        _atomic(cfg["urlconf"],after_bytes)
        patched = True
        private.mkdir(mode=0o700,parents=True,exist_ok=True)
        os.chmod(private,0o700)
        # local pure-Python Store uses only the new private db, no shared database migration.
        sys.path.insert(0,str(app))
        from social_hub.store import Store
        db = Store(private/"social.sqlite")
        try: db.summary()
        finally: db.close()
    except BaseException:
        if patched and sha(read(cfg["urlconf"])) == sha(after_bytes):
            _atomic(cfg["urlconf"],before_bytes)
        if installed and pkg.is_dir() and not pkg.is_symlink():
            shutil.rmtree(pkg)
        if temp_pkg.is_dir() and not temp_pkg.is_symlink():
            shutil.rmtree(temp_pkg)
        raise
    return {"status":"installed", "target":"personal-only", "backup":str(bdir),
            "private_db_created":True,"urlconf_sha":sha(after_bytes)}

def rollback(app,backup,run_id):
    bdir = _manifest_dir(backup,run_id)
    manpath = bdir/"manifest.json"
    if not manpath.is_file() or manpath.is_symlink():
        raise InstallationBlocked("Rollback manifest missing")
    m = json.loads(manpath.read_text(encoding="utf-8"))
    urls,_ = _resolve_urls(app)
    pkg = app/"social_hub"
    if str(urls) != m["urlconf"] or str(pkg) != m["package_path"]:
        raise InstallationBlocked("Rollback target mismatch")
    if sha(read(urls)) != m["after_sha"]:
        raise InstallationBlocked("URLconf changed since install; manual recovery required")
    if not pkg.is_dir() or pkg.is_symlink():
        raise InstallationBlocked("Installed package missing or unsafe")
    actual = _sources(pkg)
    if actual != m["package_files"]:
        raise InstallationBlocked("Package has changed; manual recovery required")
    cfg = pkg/"site_config.py"
    if not cfg.is_file() or cfg.is_symlink():
        raise InstallationBlocked("Site configuration missing")
    orig=read(bdir/"original_urls.py")
    if sha(orig) != m["before_sha"]:
        raise InstallationBlocked("Backup checksum mismatch")
    _atomic(urls,orig)
    shutil.rmtree(pkg)
    # Deliberately preserve private database so no drafts/accounts are lost.
    return {"status":"rolled_back", "database_preserved":True}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("check","install","rollback"))
    parser.add_argument("--source",default=str(Path(__file__).resolve().parents[1]/"social_hub"))
    parser.add_argument("--run-id",default="")
    parser.add_argument("--test-app-root",default="")
    parser.add_argument("--test-backup-root",default="")
    parser.add_argument("--test-private-root",default="")
    args=parser.parse_args(argv)
    test=os.getenv("MPW_SOCIAL_INSTALL_TEST")=="1"
    if (args.test_app_root or args.test_backup_root or args.test_private_root) and not test:
        print("Test roots not permitted in production",file=sys.stderr)
        return 2
    app=Path(args.test_app_root) if test and args.test_app_root else LIVE_APP
    backup=Path(args.test_backup_root) if test and args.test_backup_root else LIVE_BACKUP
    private=Path(args.test_private_root) if test and args.test_private_root else LIVE_PRIVATE
    try:
        if args.command=="check":
            cfg=plan(app,Path(args.source))
            result={"status":"ready","target":"personal-only","source_count":len(cfg["package_files"]),
                    "urlconf":str(cfg["urlconf"])}
        elif args.command=="install":
            result=install(app,Path(args.source),backup,private,args.run_id)
        else:
            result=rollback(app,backup,args.run_id)
    except (InstallationBlocked,OSError,ValueError,RuntimeError) as exc:
        result={"status":"blocked","reason":str(exc)}
        print(json.dumps(result))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
