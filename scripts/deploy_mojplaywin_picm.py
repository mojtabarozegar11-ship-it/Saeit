#!/usr/bin/env python3
"""Minimal, reversible PICM deployment to verified MojPlayWin Passenger app.

Only adds independent PICM Django routes and two new files. Never replaces
core/views.py, existing store/checkout paths, factory files, or global routing.
"""
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
FILES = [Path("config/urls.py"), Path("core/picm_views.py"),
         Path("templates/picm/index.html")]
MARK = "# SAEIT_PICM_V1_OWNER_SCOPED_ROUTES"
ROUTES = '''
# SAEIT_PICM_V1_OWNER_SCOPED_ROUTES
from core.picm_views import (
    picm_page, picm_submit, picm_status, picm_image,
    picm_worker_next, picm_worker_finish,
)
urlpatterns += [
    path("picm/", picm_page, name="picm_page"),
    path("picm/api/submit/", picm_submit, name="picm_submit"),
    path("picm/api/status/<str:ident>/", picm_status, name="picm_status"),
    path("picm/image/<str:ident>/", picm_image, name="picm_image"),
    path("picm/worker/next/", picm_worker_next, name="picm_worker_next"),
    path("picm/worker/finish/<str:ident>/", picm_worker_finish, name="picm_worker_finish"),
]
'''


def atomic_write(path, data, mode=0o644):
    if path.is_symlink():
        raise RuntimeError("PICM_REFUSE_SYMLINK")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".picm-")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sanity(run):
    if not re.fullmatch(r"[0-9]{1,20}", run):
        raise RuntimeError("PICM_INVALID_RUN")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("PICM_UNEXPECTED_ACCOUNT")
    if ROOT.is_symlink() or not ROOT.is_dir() or DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("PICM_INVALID_APP_ROOT")
    for item in ("passenger_wsgi.py", ".htaccess"):
        if not (DOCROOT / item).is_file():
            raise RuntimeError("PICM_DOCROOT_NOT_CONFIRMED")
    if "Saeit-staging" not in (DOCROOT / "passenger_wsgi.py").read_text(errors="replace"):
        raise RuntimeError("PICM_UNEXPECTED_PASSENGER_APPLICATION")


def restart():
    for root in (ROOT, DOCROOT):
        directory = root / "tmp"
        if directory.is_symlink():
            raise RuntimeError("PICM_UNSAFE_RESTART_PATH")
        directory.mkdir(exist_ok=True)
        (directory / "restart.txt").touch()


def deploy(run, sha):
    sanity(run)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("PICM_BAD_SOURCE_COMMIT")
    stage = HOME / (".mojplaywin-picm-" + run)
    urls = ROOT / "config/urls.py"
    original = urls.read_text(encoding="utf-8")
    if MARK in original or re.search(r'path\(["\']picm/', original):
        raise RuntimeError("PICM_ROUTE_ALREADY_EXISTS_REFUSE_OVERWRITE")
    assert "urlpatterns" in original and "from django.urls import" in original
    new_urls = original.rstrip() + "\n\n" + ROUTES + "\n"
    ast.parse(new_urls)
    for path in FILES[1:]:
        data = (stage / path).read_bytes()
        if not data:
            raise RuntimeError("PICM_STAGE_MISSING")
        if path.suffix == ".py":
            ast.parse(data.decode("utf-8"))
        else:
            if b'<title>PICM' not in data or b'id="renderform"' not in data:
                raise RuntimeError("PICM_TEMPLATE_INVALID")
    backup = BACKUPS / ("picm-" + run)
    backup.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {}
    for path in FILES:
        target = ROOT / path
        if target.is_symlink() or target.parent.is_symlink():
            raise RuntimeError("PICM_UNSAFE_TARGET")
        existed = target.is_file()
        manifest[str(path)] = {"exists": existed, "mode": (target.stat().st_mode & 0o777) if existed else 0o644}
        if existed:
            saved = backup / path
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / "manifest.json").write_text(json.dumps(manifest))
    try:
        atomic_write(urls, new_urls.encode(), manifest["config/urls.py"]["mode"])
        for path in FILES[1:]:
            atomic_write(ROOT / path, (stage / path).read_bytes(), manifest[str(path)]["mode"])
        restart()
    except Exception:
        rollback(run)
        raise
    (backup / "source.json").write_text(json.dumps({"commit": sha, "run": run}))
    print("PICM_SAFE_DEPLOY_COMPLETE")


def rollback(run):
    sanity(run)
    backup = BACKUPS / ("picm-" + run)
    if not (backup / "manifest.json").is_file():
        raise RuntimeError("PICM_BACKUP_MISSING")
    manifest = json.loads((backup / "manifest.json").read_text())
    for path in FILES:
        target = ROOT / path
        rec = manifest[str(path)]
        if target.is_symlink():
            raise RuntimeError("PICM_UNSAFE_TARGET")
        if rec["exists"]:
            atomic_write(target, (backup / path).read_bytes(), rec["mode"])
        elif target.exists():
            target.unlink()
    restart()
    print("PICM_ROLLBACK_COMPLETE")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy_picm.py deploy RUN_ID COMMIT | rollback RUN_ID")
