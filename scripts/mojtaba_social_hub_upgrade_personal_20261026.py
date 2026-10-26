#!/usr/bin/env python3
"""Strictly verified repeat upgrades for the *independent* Mojtaba Django social panel.

Does not change URL routes, production databases, other websites, or any credentials.
Replaces only the isolated /social_hub Python package after making a private, hash-
verified snapshot. Supports rollback of exactly the version installed by this run.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

from mojtaba_social_hub_install_personal_20261026 import (
    LIVE_APP, LIVE_BACKUP, MARK_BEGIN, MARK_END, ROUTE,
    InstallationBlocked, _manifest_dir, _resolve_urls, _sources, read, sha,
)

def _private_dir(path: Path):
    if path.is_symlink() or not path.is_dir():
        raise InstallationBlocked("Backup root missing or symlinked")
    if path.stat().st_mode & 0o077:
        raise InstallationBlocked("Backups must not be readable by group/world")

def _snapshot_match(app: Path, backups: Path):
    """Find a previously verified release snapshot matching *all* current code."""
    urls, body = _resolve_urls(app)
    if body.count(MARK_BEGIN) != 1 or body.count(MARK_END) != 1 or body.count(ROUTE) != 1:
        raise InstallationBlocked("Installed social route changed; refuse upgrade")
    pkg = app/"social_hub"
    if pkg.is_symlink() or not pkg.is_dir():
        raise InstallationBlocked("No original isolated social package")
    files = _sources(pkg)
    if not backups.is_dir() or backups.is_symlink():
        raise InstallationBlocked("Original release backup unavailable")
    _private_dir(backups)
    for candidate in sorted(backups.iterdir(),key=lambda p:p.name,reverse=True):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        manifest = candidate/"manifest.json"
        if not manifest.is_file() or manifest.is_symlink():
            continue
        try:
            data=json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError,OSError):
            continue
        latest = data.get("new_files", data.get("package_files"))
        h = data.get("urlconf_sha", data.get("after_sha"))
        if (latest == files and h == sha(read(urls))
            and data.get("package_path") == str(pkg)
            and data.get("urlconf") == str(urls)):
            config=pkg/"site_config.py"
            if not config.is_file() or config.is_symlink():
                raise InstallationBlocked("Existing private config is missing or symlinked")
            return {"urls":urls,"url_sha":sha(read(urls)),"package":pkg,
                    "files":files,"config":config,"matched":candidate}
    raise InstallationBlocked("Installed files do not match a verified backup; manual audit required")

def check(app,source,backups):
    cfg = _snapshot_match(app,backups)
    new_files = _sources(source)
    if cfg["files"] == new_files:
        return {"status":"already_current","matched":str(cfg["matched"])}
    return {"status":"ready_upgrade","existing_code_files":len(cfg["files"]),
            "new_code_files":len(new_files),"matched":str(cfg["matched"])}

def _hashes_any_dir(folder: Path):
    """Audit copied snapshots whose backup directory is not named social_hub."""
    if folder.is_symlink() or not folder.is_dir():
        raise InstallationBlocked("Snapshot directory missing or unsafe")
    hashes={}
    for item in folder.rglob("*"):
        if item.is_symlink():
            raise InstallationBlocked("Snapshot contains a symlink")
        if "__pycache__" in item.parts or item.suffix==".pyc" or item.name=="site_config.py":
            continue
        if item.is_file():
            rel=item.relative_to(folder).as_posix()
            if not rel.endswith(".py") or not re.fullmatch(r"[A-Za-z0-9_./-]{1,180}",rel):
                raise InstallationBlocked("Unexpected snapshot file")
            hashes[rel]=sha(read(item))
        elif not item.is_dir():
            raise InstallationBlocked("Unexpected snapshot entry")
    for name in ("__init__.py","catalog.py","store.py","service.py","portal.py","urls.py"):
        if name not in hashes:
            raise InstallationBlocked("Missing mandatory snapshot code")
    return hashes

def _copy_private(src,dst):
    shutil.copytree(src,dst,symlinks=False,
        ignore=lambda dir,names: [n for n in names if n=="__pycache__" or n.endswith(".pyc")])
    for node in dst.rglob("*"):
        if node.is_dir(): os.chmod(node,0o700)
        elif node.is_file(): os.chmod(node,0o600)
    os.chmod(dst,0o700)

def upgrade(app,source,backups,run_id):
    cfg=_snapshot_match(app,backups)
    new_files=_sources(source)
    if new_files == cfg["files"]:
        return {"status":"already_current","database_preserved":True}
    bdir=_manifest_dir(backups,run_id)
    if bdir.exists() or bdir.is_symlink():
        raise InstallationBlocked("Upgrade ID collision")
    bdir.mkdir(mode=0o700)
    old_copy=bdir/"prior_package"
    _copy_private(cfg["package"],old_copy)
    if _hashes_any_dir(old_copy)!=cfg["files"]:
        raise InstallationBlocked("Original package backup checksum mismatch")
    stage=app/(".mpw-social-upgrade-stage-"+run_id)
    prior=app/(".mpw-social-upgrade-prior-"+run_id)
    if stage.exists() or prior.exists() or stage.is_symlink() or prior.is_symlink():
        raise InstallationBlocked("Stage collision")
    swapped_old=False
    swapped_new=False
    try:
        _copy_private(source,stage)
        shutil.copy2(cfg["config"],stage/"site_config.py")
        os.chmod(stage/"site_config.py",0o600)
        if _hashes_any_dir(stage)!=new_files or sha(read(stage/"site_config.py"))!=sha(read(cfg["config"])):
            raise InstallationBlocked("Staged checksum or private DB config mismatch")
        # Prevent any change to the independent Django URLconf.
        if sha(read(cfg["urls"]))!=cfg["url_sha"]:
            raise InstallationBlocked("URLconf changed during staging")
        manifest={"kind":"isolated_upgrade_v1","urlconf":str(cfg["urls"]),
                  "urlconf_sha":cfg["url_sha"],"package_path":str(cfg["package"]),
                  "old_files":cfg["files"],"new_files":new_files,
                  "old_config_sha":sha(read(cfg["config"])),
                  "previous_verified_backup":str(cfg["matched"])}
        (bdir/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding="utf-8")
        os.chmod(bdir/"manifest.json",0o600)
        cfg["package"].rename(prior)
        swapped_old=True
        stage.rename(cfg["package"])
        swapped_new=True
        if _sources(cfg["package"])!=new_files:
            raise InstallationBlocked("Installed source verification failed")
        # All private account data remain in the existing directory; no DB reset.
    except BaseException:
        if swapped_new and cfg["package"].is_dir() and not cfg["package"].is_symlink():
            shutil.rmtree(cfg["package"])
        if swapped_old and prior.exists():
            prior.rename(cfg["package"])
        if stage.is_dir() and not stage.is_symlink():
            shutil.rmtree(stage)
        raise
    if prior.is_dir() and not prior.is_symlink():
        shutil.rmtree(prior)
    return {"status":"upgraded","target":"personal_only",
            "backup":str(bdir),"database_preserved":True,
            "new_files":len(new_files)}

def rollback(app,backups,run_id):
    bdir=_manifest_dir(backups,run_id)
    mpath=bdir/"manifest.json"
    if not mpath.is_file() or mpath.is_symlink():
        raise InstallationBlocked("Upgrade manifest missing")
    m=json.loads(mpath.read_text(encoding="utf-8"))
    urls,_=_resolve_urls(app)
    pkg=app/"social_hub"
    if (m.get("kind")!="isolated_upgrade_v1" or m.get("package_path")!=str(pkg)
        or m.get("urlconf")!=str(urls) or m.get("urlconf_sha")!=sha(read(urls))):
        raise InstallationBlocked("Rollback does not match audited route")
    if not pkg.is_dir() or pkg.is_symlink() or _sources(pkg)!=m["new_files"]:
        raise InstallationBlocked("Current installed package modified; refuse rollback")
    old=bdir/"prior_package"
    if not old.is_dir() or old.is_symlink() or _hashes_any_dir(old)!=m["old_files"]:
        raise InstallationBlocked("Rollback backup files unavailable or altered")
    if sha(read(old/"site_config.py"))!=m["old_config_sha"]:
        raise InstallationBlocked("Private config backup changed")
    stage=app/(".mpw-social-rollback-current-"+run_id)
    if stage.exists() or stage.is_symlink():
        raise InstallationBlocked("Rollback stage already exists")
    pkg.rename(stage)
    try:
        _copy_private(old,pkg)
        if _sources(pkg)!=m["old_files"]:
            raise InstallationBlocked("Rollback restore checksum failed")
    except BaseException:
        if pkg.exists() and not pkg.is_symlink(): shutil.rmtree(pkg)
        stage.rename(pkg)
        raise
    shutil.rmtree(stage)
    return {"status":"rolled_back","database_preserved":True,
            "other_websites_preserved":True}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=("check","upgrade","rollback"))
    parser.add_argument("--source",default=str(Path(__file__).resolve().parents[1]/"social_hub"))
    parser.add_argument("--run-id",default="")
    parser.add_argument("--test-app-root",default="")
    parser.add_argument("--test-backup-root",default="")
    args=parser.parse_args(argv)
    is_test=os.getenv("MPW_SOCIAL_INSTALL_TEST")=="1"
    if (args.test_app_root or args.test_backup_root) and not is_test:
        print('{"status":"blocked","reason":"Test roots forbidden"}')
        return 2
    app=Path(args.test_app_root) if is_test and args.test_app_root else LIVE_APP
    backups=Path(args.test_backup_root) if is_test and args.test_backup_root else LIVE_BACKUP
    try:
        if args.command=="check": result=check(app,Path(args.source),backups)
        elif args.command=="upgrade": result=upgrade(app,Path(args.source),backups,args.run_id)
        else: result=rollback(app,backups,args.run_id)
    except (InstallationBlocked,ValueError,OSError,RuntimeError,KeyError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},sort_keys=True))
        return 2
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
