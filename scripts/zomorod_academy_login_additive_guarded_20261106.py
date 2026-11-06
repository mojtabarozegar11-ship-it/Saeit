#!/usr/bin/env python3
"""Restore live academy auth routes without overwriting any other URL changes.

Current production URL SHA and the production login template were measured via
read-only pinned cPanel inspection. This operation never touches databases,
customer data, other routes, payments, mail or other websites.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit"
URLS = APP / "config/urls.py"
LOGIN_TEMPLATE = APP / "templates/registration/login.html"
VENV = HOME / "virtualenv/Saeit/3.10/bin/python"
BACKUP_ROOT = HOME / ".backups/zomorod-academy-login-additive-20261106"
EXPECTED_URL = "d5d2167f2331086f254a1a8f7351187b17e8ddd83cebd8e7a76fab41b3b01f42"
EXPECTED_LOGIN_TEMPLATE = "3b8c2aca25c19cb8c99ac9b3f94e8174e1a92b783b16e71d9cc2af59c114b2a4"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rid(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6,20}", value):
        raise RuntimeError("ACADEMY_LOGIN_RUN_ID_INVALID")
    return value


def patch_urls(raw: bytes, *, enforce_hash: bool = True) -> bytes:
    if enforce_hash and sha(raw) != EXPECTED_URL:
        raise RuntimeError("ACADEMY_LOGIN_URL_LIVE_BASELINE_CHANGED_ABORT")
    text = raw.decode("utf-8")
    if (text.count("urlpatterns = [") != 1 or
        text.count("from django.contrib import admin") != 1 or
        "from django.urls import" not in text or
        "accounts/login/" in text or "accounts/logout/" in text or
        not ("amozeshgah/" in text and "education_dashboard" in text)):
        raise RuntimeError("ACADEMY_LOGIN_URL_CONTEXT_CHANGED_ABORT")
    # Add only missing auth imports and paths; leave every other URL untouched.
    if "from django.contrib.auth.views import LoginView, LogoutView" not in text:
        text = text.replace(
            "from django.contrib import admin",
            "from django.contrib import admin\nfrom django.contrib.auth.views import LoginView, LogoutView",
            1,
        )
    injection = '''urlpatterns = [
    # Restored with an exact-live-SHA guarded additive academy patch.
    path("accounts/login/", LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True,
    ), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="education"), name="logout"),'''
    text = text.replace("urlpatterns = [", injection, 1)
    compile(text, "config/urls.py", "exec")
    if text.count('path("accounts/login/"') != 1 or text.count('path("accounts/logout/"') != 1:
        raise RuntimeError("ACADEMY_LOGIN_URL_PATCH_INVALID")
    return text.encode("utf-8")


def host_guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError("ACADEMY_LOGIN_CPANEL_USER_INVALID")
    htaccess = HOME / "public_html/.htaccess"
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise RuntimeError("ACADEMY_LOGIN_APP_ROOT_UNSAFE")
    if htaccess.is_symlink() or not htaccess.is_file() or not any(
        "PassengerAppRoot" in line and str(APP) in line
        for line in htaccess.read_text(errors="replace").splitlines()
    ):
        raise RuntimeError("ACADEMY_LOGIN_PASSENGER_ROOT_CHANGED")
    for p in (URLS, LOGIN_TEMPLATE):
        if p.is_symlink() or p.parent.is_symlink() or not p.is_file():
            raise RuntimeError("ACADEMY_LOGIN_TARGET_UNSAFE")
    if sha(LOGIN_TEMPLATE.read_bytes()) != EXPECTED_LOGIN_TEMPLATE:
        raise RuntimeError("ACADEMY_LOGIN_TEMPLATE_CHANGED_ABORT")
    if not VENV.is_file():
        raise RuntimeError("ACADEMY_LOGIN_PYTHON_MISSING")
    if BACKUP_ROOT.is_symlink() or (BACKUP_ROOT.exists() and not BACKUP_ROOT.is_dir()):
        raise RuntimeError("ACADEMY_LOGIN_BACKUP_ROOT_UNSAFE")


def atomic(path: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-auth-", delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def restart() -> None:
    marker = APP / "tmp/restart.txt"
    if marker.parent.is_symlink() or not marker.parent.is_dir() or marker.is_symlink():
        raise RuntimeError("ACADEMY_LOGIN_RESTART_MARKER_UNSAFE")
    marker.touch()
    # This account exposes the CloudLinux Python Selector, and the documented
    # restart applies only to the named Saeit app.
    p = subprocess.run(
        ["cloudlinux-selector", "restart", "--json", "--interpreter", "python",
         "--app-root", "Saeit"],
        capture_output=True, text=True, timeout=50, check=False,
    )
    if p.returncode:
        raise RuntimeError("ACADEMY_LOGIN_SELECTOR_RESTART_FAILED")
    try:
        result = json.loads(p.stdout)
    except Exception as e:
        raise RuntimeError("ACADEMY_LOGIN_SELECTOR_RESTART_UNPARSABLE") from e
    if isinstance(result, dict) and result.get("result") not in (None, "success", True):
        raise RuntimeError("ACADEMY_LOGIN_SELECTOR_RESTART_REJECTED")
    print("ACADEMY_LOGIN_CLOUDLINUX_RESTART=yes")


def django_check() -> None:
    source = """
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.checks import run_checks
from django.template.loader import get_template
from django.urls import resolve
if run_checks(): raise RuntimeError("DJANGO_CHECK_FAILED")
if resolve("/accounts/login/").url_name != "login": raise RuntimeError("LOGIN_ROUTE_ABSENT")
if resolve("/accounts/logout/").url_name != "logout": raise RuntimeError("LOGOUT_ROUTE_ABSENT")
get_template("registration/login.html")
print("ACADEMY_LOGIN_DJANGO_PASS=yes")
"""
    p = subprocess.run(
        [str(VENV), "-B", "-c", source], cwd=APP,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=45, check=False,
    )
    if p.returncode or "ACADEMY_LOGIN_DJANGO_PASS=yes" not in p.stdout:
        raise RuntimeError("ACADEMY_LOGIN_DJANGO_CHECK_FAILED")


def public_login() -> bool:
    req = Request(
        "https://zomorodmelal.ir/accounts/login/?zm_auth_repair=" + str(time.time_ns()),
        headers={"Cache-Control": "no-cache", "User-Agent": "ZM-Login-Guarded-Repair/1.0"},
    )
    with urlopen(req, timeout=18) as r:
        page = r.read(100_000)
        return r.status == 200 and b"id_username" in page


def main(mode: str, run_id: str) -> None:
    backup = BACKUP_ROOT / rid(run_id)
    if mode == "selftest":
        snippet = b'from django.contrib import admin\nfrom django.urls import include, path\nurlpatterns = [\n    path("amozeshgah/", education_dashboard),\n]'
        if not patch_urls(snippet, enforce_hash=False):
            raise RuntimeError("ACADEMY_LOGIN_SELFTEST_FAILED")
        print("ACADEMY_LOGIN_PATCH_SELFTEST=yes")
        return
    host_guard()
    if mode in ("preview", "publish"):
        old = URLS.read_bytes()
        patched = patch_urls(old)
        if backup.exists():
            raise RuntimeError("ACADEMY_LOGIN_RELEASE_ID_REUSED")
        if mode == "preview":
            print("ACADEMY_LOGIN_PREFLIGHT_READY=yes")
            return
        backup.mkdir(mode=0o700, parents=True, exist_ok=False)
        p = backup / "urls.original.py"
        with p.open("xb") as f:
            f.write(old)
            f.flush()
            os.fsync(f.fileno())
        p.chmod(0o600)
        atomic(URLS, patched)
        django_check()
        restart()
        print("ACADEMY_LOGIN_PATCHED=yes")
        return
    if mode == "verify":
        if not backup.is_dir():
            raise RuntimeError("ACADEMY_LOGIN_BACKUP_MISSING")
        old = (backup / "urls.original.py").read_bytes()
        expected = patch_urls(old)
        if sha(URLS.read_bytes()) != sha(expected):
            raise RuntimeError("ACADEMY_LOGIN_URL_CHANGED_AFTER_PUBLISH")
        django_check()
        for attempt in range(8):
            try:
                if public_login():
                    print("ACADEMY_LOGIN_PUBLIC_VERIFIED=yes")
                    return
            except Exception:
                pass
            if attempt < 7:
                time.sleep(5)
        raise RuntimeError("ACADEMY_LOGIN_PUBLIC_NOT_READY")
    if mode == "rollback":
        if not backup.is_dir():
            print("ACADEMY_LOGIN_NOTHING_TO_ROLLBACK=yes")
            return
        old = (backup / "urls.original.py").read_bytes()
        expected = patch_urls(old)
        if URLS.is_symlink() or sha(URLS.read_bytes()) not in (EXPECTED_URL, sha(expected)):
            raise RuntimeError("ACADEMY_LOGIN_CONCURRENT_CHANGE_REFUSE_ROLLBACK")
        atomic(URLS, old)
        restart()
        print("ACADEMY_LOGIN_ROLLED_BACK=yes")
        return
    raise RuntimeError("ACADEMY_LOGIN_RELEASE_MODE_INVALID")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("USAGE: script MODE RUN_ID")
    main(sys.argv[1], sys.argv[2])
