#!/usr/bin/env python3
"""Scope-limited repeatable PICM login installer; preserves non-PICM routes."""
import ast
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import tempfile

HOME = Path("/home/zomorod2")
ROOT = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
BACKUPS = HOME / ".mojplaywin-backups"
FILES = (Path("config/urls.py"), Path("core/picm_auth.py"),
         Path("templates/picm/login.html"), Path("templates/picm/index.html"))
MARK = "# SAEIT_PICM_PRIVATE_LOGIN_V1"
ROUTES = '''
# SAEIT_PICM_PRIVATE_LOGIN_V1
from core.picm_auth import picm_login, picm_logout
urlpatterns += [
    path("picm/login/", picm_login, name="picm_login"),
    path("picm/logout/", picm_logout, name="picm_logout"),
]
'''


def verify_environment(run):
    if not re.fullmatch(r"[0-9]{1,20}", run):
        raise RuntimeError("INVALID_RUN_ID")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("WRONG_CPANEL_USER")
    if ROOT.is_symlink() or DOCROOT.is_symlink():
        raise RuntimeError("SYMLINK_ROOT_REFUSED")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(errors="replace"):
        raise RuntimeError("UNRECOGNIZED_PASSENGER_APPLICATION")


def atomic_write(path, content, mode):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("UNSAFE_FILE")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".picm-login-")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as fp:
            fp.write(content)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def restart():
    for folder in (ROOT / "tmp", DOCROOT / "tmp"):
        if folder.is_symlink():
            raise RuntimeError("UNSAFE_PASSENGER_RESTART")
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / "restart.txt").touch()


def deploy(run):
    verify_environment(run)
    stage = HOME / (".mojplaywin-picm-login-" + run)
    root_urls = (ROOT / "config/urls.py").read_text(encoding="utf-8")
    if "# SAEIT_PICM_V1_OWNER_SCOPED_ROUTES" not in root_urls:
        raise RuntimeError("PICM_PRIMARY_ROUTES_NOT_INSTALLED")
    if MARK in root_urls:
        # Safe update of the *already installed* PICM login; never append routes twice.
        if (root_urls.count(MARK) != 1
                or root_urls.count('path("picm/login/"') != 1
                or root_urls.count('path("picm/logout/"') != 1):
            raise RuntimeError("PICM_LOGIN_ROUTE_INTEGRITY_FAILED")
        urls = root_urls
    else:
        if ('path("picm/login/"' in root_urls
                or 'path("picm/logout/"' in root_urls):
            raise RuntimeError("PICM_LOGIN_ROUTE_COLLISION")
        urls = root_urls.rstrip() + "\n" + ROUTES
    ast.parse(urls)
    src_auth = (stage / "core/picm_auth.py").read_bytes()
    ast.parse(src_auth.decode("utf-8"))
    src_login = (stage / "templates/picm/login.html").read_bytes()
    src_index = (stage / "templates/picm/index.html").read_bytes()
    if b'<title>PICM' not in src_index or b'/picm/login/' not in src_index or b'csrf_token' not in src_login:
        raise RuntimeError("PICM_LOGIN_TEMPLATES_INVALID")
    backup = BACKUPS / ("picm-login-" + run)
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {}
    for relative in FILES:
        target = ROOT / relative
        if target.is_symlink() or target.parent.is_symlink():
            raise RuntimeError("UNSAFE_TARGET")
        existed = target.is_file()
        mode = (target.stat().st_mode & 0o777) if existed else 0o644
        manifest[str(relative)] = {"existed": existed, "mode": mode}
        if existed:
            save = backup / relative
            save.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, save)
    (backup / "manifest.json").write_text(json.dumps(manifest))
    try:
        payload = {FILES[0]: urls.encode(), FILES[1]: src_auth,
                   FILES[2]: src_login, FILES[3]: src_index}
        for relative, content in payload.items():
            atomic_write(ROOT / relative, content, manifest[str(relative)]["mode"])
        restart()
    except Exception:
        rollback(run)
        raise
    print("PICM_LOGIN_SAFE_DEPLOY_COMPLETE")


def rollback(run):
    verify_environment(run)
    backup = BACKUPS / ("picm-login-" + run)
    manifest = json.loads((backup / "manifest.json").read_text())
    for relative in FILES:
        target = ROOT / relative
        if target.is_symlink():
            raise RuntimeError("UNSAFE_ROLLBACK_TARGET")
        info = manifest[str(relative)]
        if info["existed"]:
            atomic_write(target, (backup / relative).read_bytes(), info["mode"])
        elif target.exists():
            target.unlink()
    restart()
    print("PICM_LOGIN_ROLLBACK_COMPLETE")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "deploy":
        deploy(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("deploy_picm_login.py deploy|rollback RUN_ID")
