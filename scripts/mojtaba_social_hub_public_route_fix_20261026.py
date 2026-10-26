#!/usr/bin/env python3
"""Expose private Mojtaba Django social routes under the ACTUAL public prefix.

Only edits the exact standalone personal Django URLconf after hash verification;
NEVER edits root cPanel Apache/.htaccess, shared Saeit Django, other domains,
secrets, factory, credentials, accounts, or the social hub private ledger.
Creates a reversible, private checksum-bound record for future safe upgrades.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from mojtaba_social_hub_install_personal_20261026 import (
    LIVE_APP, LIVE_BACKUP, MARK_BEGIN, MARK_END, ROUTE,
    InstallationBlocked, _atomic, _manifest_dir, _resolve_urls, _sources, read, sha,
)
from mojtaba_social_hub_upgrade_personal_20261026 import _snapshot_match

PUBLIC_PREFIX = "mojtaba.roozegar/social-command/"
MARKER_BEGIN = "# MPW_SOCIAL_EXTERNAL_PUBLIC_ROUTE_BEGIN_20261026"
MARKER_END = "# MPW_SOCIAL_EXTERNAL_PUBLIC_ROUTE_END_20261026"
# Django's urlpatterns.insert(0, ...) guarantees the exact personal-only
# prefix takes priority even if old patterns include broad slug catchalls.
PUBLIC_ROUTE = (
    "\n" + MARKER_BEGIN + "\n"
    "urlpatterns.insert(0, _mpw_social_path('mojtaba.roozegar/social-command/',"
    " _mpw_social_include('social_hub.urls')))\n"
    + MARKER_END + "\n"
)

def check(app: Path, backup: Path):
    if app != LIVE_APP and os.environ.get("MPW_SOCIAL_INSTALL_TEST") != "1":
        raise InstallationBlocked("Only the authorized personal Django root can be changed")
    config=_snapshot_match(app,backup)
    urlconf=config["urls"]
    current=read(urlconf)
    if sha(current)!=config["url_sha"]:
        raise InstallationBlocked("URLconf changed since verified deployment snapshot")
    txt=current.decode("utf-8")
    if MARKER_BEGIN in txt or MARKER_END in txt or PUBLIC_PREFIX in txt:
        raise InstallationBlocked("Public route is already installed or conflicts")
    if txt.count(ROUTE)!=1 or txt.count(MARK_BEGIN)!=1 or txt.count(MARK_END)!=1:
        raise InstallationBlocked("Preexisting standalone social mount differs")
    if urlconf.is_symlink() or not urlconf.is_file():
        raise InstallationBlocked("Unsafe route config")
    return config

def install(app: Path, backup: Path, run_id: str):
    cfg=check(app,backup)
    old=read(cfg["urls"])
    target=old+PUBLIC_ROUTE.encode("utf-8")
    root=_manifest_dir(backup,run_id)
    if root.exists() or root.is_symlink():
        raise InstallationBlocked("Private backup ID collision")
    if backup.is_symlink() or backup.stat().st_mode & 0o077:
        raise InstallationBlocked("Private backup root is not restricted")
    root.mkdir(mode=0o700)
    (root/"original_urls.py").write_bytes(old)
    os.chmod(root/"original_urls.py",0o600)
    manifest={
        "kind":"personal_only_route_fix_v1",
        "package_path":str(cfg["package"]),
        "package_files":cfg["files"],
        "urlconf":str(cfg["urls"]),
        "urlconf_sha":sha(target),
        "original_urlconf_sha":sha(old),
        "after_sha":sha(target),
        "previous_verified_backup":str(cfg["matched"]),
        "external_public_prefix":"/"+PUBLIC_PREFIX,
        "database_preserved":True,
    }
    (root/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding="utf-8")
    os.chmod(root/"manifest.json",0o600)
    if read(cfg["urls"])!=old:
        raise InstallationBlocked("Concurrent URLconf change before installation")
    _atomic(cfg["urls"],target)
    if sha(read(cfg["urls"]))!=sha(target):
        raise InstallationBlocked("Installed URLconf integrity check failed")
    return {"status":"personal_route_installed","public_prefix":"/"+PUBLIC_PREFIX,
            "backup":str(root),"shared_root_untouched":True,
            "private_account_database_preserved":True}

def rollback(app: Path, backup: Path, run_id: str):
    root=_manifest_dir(backup,run_id)
    path=root/"manifest.json"
    orig=root/"original_urls.py"
    if not path.is_file() or path.is_symlink() or not orig.is_file() or orig.is_symlink():
        raise InstallationBlocked("Verified route restoration manifest unavailable")
    manifest=json.loads(path.read_text(encoding="utf-8"))
    urlconf,_=_resolve_urls(app)
    pkg=app/"social_hub"
    if (manifest.get("kind")!="personal_only_route_fix_v1"
        or manifest.get("urlconf")!=str(urlconf)
        or manifest.get("package_path")!=str(pkg)):
        raise InstallationBlocked("Rollback target mismatch")
    if sha(read(urlconf))!=manifest["urlconf_sha"]:
        raise InstallationBlocked("URLconf changed after route install; refuse blind rollback")
    if _sources(pkg)!=manifest["package_files"]:
        raise InstallationBlocked("Personal code changed after route install")
    old=read(orig)
    if sha(old)!=manifest["original_urlconf_sha"]:
        raise InstallationBlocked("Original backup checksum invalid")
    _atomic(urlconf,old)
    return {"status":"personal_route_restored",
            "account_database_preserved":True,"other_sites_untouched":True}

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","rollback"))
    parser.add_argument("--run-id",default="")
    parser.add_argument("--test-app-root",default="")
    parser.add_argument("--test-backup-root",default="")
    args=parser.parse_args(argv)
    test_mode=os.environ.get("MPW_SOCIAL_INSTALL_TEST")=="1"
    if (args.test_app_root or args.test_backup_root) and not test_mode:
        print('{"status":"blocked","reason":"Non-production targets require explicit test mode"}')
        return 2
    app=Path(args.test_app_root) if args.test_app_root else LIVE_APP
    backup=Path(args.test_backup_root) if args.test_backup_root else LIVE_BACKUP
    try:
        if args.action=="check":
            cfg=check(app,backup)
            result={"status":"ready","urlconf_sha":cfg["url_sha"],
                    "target":"personal_only","public_prefix":"/"+PUBLIC_PREFIX}
        elif args.action=="install":
            result=install(app,backup,args.run_id)
        else:
            result=rollback(app,backup,args.run_id)
    except (InstallationBlocked,ValueError,OSError,RuntimeError,KeyError,UnicodeError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
