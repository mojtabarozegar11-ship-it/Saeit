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
         Path("templates/picm/login.html"), Path("templates/picm/index.html"),
         Path("templates/picm/free_motion.js"),
         Path("core/picm_views.py"), Path("core/picm_access.py"),
         Path("core/picm_storyboard.py"), Path("templates/picm/story_preview.js"))
MARK = "# SAEIT_PICM_PRIVATE_LOGIN_V1"
WORKSPACE_MARK = "# SAEIT_PICM_WORKSPACE_V1"
ROUTES = '''
# SAEIT_PICM_PRIVATE_LOGIN_V1
from core.picm_auth import picm_login, picm_logout
urlpatterns += [
    path("picm/login/", picm_login, name="picm_login"),
    path("picm/logout/", picm_logout, name="picm_logout"),
]
'''

WORKSPACE_ROUTES = '''
# SAEIT_PICM_WORKSPACE_V1
from core.picm_views import picm_workbench
urlpatterns += [
    path("picm/workspace/", picm_workbench, name="picm_workbench"),
]
'''

PHOTO_MARK = "# SAEIT_PICM_REFERENCE_UPLOAD_V1"
PHOTO_ROUTES = '''
# SAEIT_PICM_REFERENCE_UPLOAD_V1
from core.picm_views import picm_reference_stage, picm_reference_status
urlpatterns += [
    path("picm/api/reference/", picm_reference_stage, name="picm_reference_stage"),
    path("picm/api/reference/<str:ident>/", picm_reference_status, name="picm_reference_status"),
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
    if WORKSPACE_MARK in urls:
        if (urls.count(WORKSPACE_MARK) != 1
                or urls.count('path("picm/workspace/"') != 1):
            raise RuntimeError("PICM_WORKSPACE_ROUTE_INTEGRITY_FAILED")
    else:
        if 'path("picm/workspace/"' in urls:
            raise RuntimeError("PICM_WORKSPACE_ROUTE_COLLISION")
        urls = urls.rstrip() + "\n" + WORKSPACE_ROUTES
    if PHOTO_MARK in urls:
        if (urls.count(PHOTO_MARK) != 1
                or urls.count('path("picm/api/reference/"') != 1
                or urls.count('path("picm/api/reference/<str:ident>/"') != 1):
            raise RuntimeError("PICM_REFERENCE_ROUTES_INTEGRITY_FAILED")
    else:
        if 'path("picm/api/reference/"' in urls:
            raise RuntimeError("PICM_REFERENCE_ROUTE_COLLISION")
        urls = urls.rstrip() + "\n" + PHOTO_ROUTES
    ast.parse(urls)
    src_auth = (stage / "core/picm_auth.py").read_bytes()
    ast.parse(src_auth.decode("utf-8"))
    src_login = (stage / "templates/picm/login.html").read_bytes()
    src_index = (stage / "templates/picm/index.html").read_bytes()
    src_motion = (stage / "templates/picm/free_motion.js").read_bytes()
    src_views = (stage / "core/picm_views.py").read_bytes()
    ast.parse(src_views.decode("utf-8"))
    src_story = (stage / "core/picm_storyboard.py").read_bytes()
    ast.parse(src_story.decode("utf-8"))
    src_story_ui = (stage / "templates/picm/story_preview.js").read_bytes()
    src_access = (stage / "core/picm_access.py").read_bytes()
    ast.parse(src_access.decode("utf-8"))
    if b"def owner_allowed(user):" not in src_access:
        raise RuntimeError("PICM_OWNER_AUTHORIZATION_GATE_MISSING")
    if (b"def picm_workbench(request):" not in src_views
            or b"def picm_page(request):" not in src_views
            or b"def picm_reference_stage(request):" not in src_views):
        raise RuntimeError("PICM_PHOTO_UPLOAD_VIEWS_NOT_FOUND")
    if (b'<title>PICM' not in src_index or b'id="renderform"' not in src_index
            or b"include 'picm/free_motion.js'" not in src_index
            or b"include 'picm/story_preview.js'" not in src_index
            or b"plan_story(" not in src_story
            or b"story_video" not in src_views
            or b"story_video" not in src_story_ui
            or b"captureStream(20)" not in src_motion
            or b"MediaRecorder(" not in src_motion
            or b'/picm/logout/' not in src_index or b'csrf_token' not in src_login):
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
                   FILES[2]: src_login, FILES[3]: src_index,
                   FILES[4]: src_motion, FILES[5]: src_views,
                   FILES[6]: src_access, FILES[7]: src_story,
                   FILES[8]: src_story_ui}
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
