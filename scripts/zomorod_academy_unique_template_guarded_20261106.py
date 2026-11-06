#!/usr/bin/env python3
"""Guarded release of a non-shadowed academy template and one-line view route.

Preserves the existing higher-priority production-only academy template intact.
Only two precise targets: add a uniquely named Django template and change
the academy() render string in the previously fingerprinted Python module.
No database writes, emails, payments or cross-site changes.
"""
from __future__ import annotations

import base64
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

PACKED_TEMPLATE = None  # Replaced with reviewed unique academy template bytes on runner.
HOME = Path("/home/zomorod2")
APP = HOME / "Saeit"
VENV = HOME / "virtualenv/Saeit/3.10/bin/python"
BACKUP_ROOT = HOME / ".backups/zomorod-academy-unique-template-20261106"
VIEW = APP / "core/academy_views.py"
NEW_TEMPLATE = APP / "core/templates/core/academy_live_resources_20261106.html"
SHADOW = APP / "templates/core/academy.html"
SHADOW_COLLISION = APP / "templates/core/academy_live_resources_20261106.html"
EXPECTED_VIEW = "8e53348804828cb72a255efd517f206a12d8d1ded08a3f74a4a6c14174c5b3b0"
EXPECTED_SHADOW = "1d069aa993ba4a473da832dbd5eb1466aca1e0696d04eb7051a2f9c0d128fcfb"
OLD_RENDER = b'return render(request, "core/academy.html", {'
NEW_RENDER = b'return render(request, "core/academy_live_resources_20261106.html", {'
DESTINATIONS = (
    "/agriculture/free-tools/20261025/farm-break-even/",
    "/agriculture/free-tools/20261025/import-landed-cost/",
    "/resources/20261025/farm-risk/",
    "/ask-master/index.php?service=1",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6,20}", value):
        raise RuntimeError("INVALID_UNIQUE_TEMPLATE_RELEASE_ID")
    return value


def template_bytes() -> bytes:
    if not isinstance(PACKED_TEMPLATE, str):
        raise RuntimeError("UNIQUE_ACADEMY_TEMPLATE_NOT_PACKAGED")
    data = base64.b64decode(PACKED_TEMPLATE, validate=True)
    if not 1000 <= len(data) < 100_000 or b"\x00" in data:
        raise RuntimeError("UNIQUE_ACADEMY_TEMPLATE_INVALID")
    if any(path.encode() not in data for path in DESTINATIONS):
        raise RuntimeError("ACADEMY_LIVE_DESTINATION_MISSING")
    if any(marker not in data for marker in (
        "محاسبه نقطه سربه‌سر مزرعه".encode(),
        "وضعیت دوره‌های آموزشگاه".encode(),
        b"{% if not courses %}",
    )):
        raise RuntimeError("UNIQUE_ACADEMY_TEMPLATE_CONTRACT_FAILED")
    if b"{{ resource.url }}" in data:
        raise RuntimeError("UNIQUE_TEMPLATE_DEPENDS_ON_NEWER_VIEW")
    return data


def patched_view(old: bytes) -> bytes:
    if digest(old) != EXPECTED_VIEW:
        raise RuntimeError("UNIQUE_ACADEMY_VIEW_BASELINE_CHANGED_ABORT")
    if old.count(OLD_RENDER) != 1 or NEW_RENDER in old:
        raise RuntimeError("UNIQUE_ACADEMY_RENDER_CONTEXT_CHANGED")
    result = old.replace(OLD_RENDER, NEW_RENDER, 1)
    compile(result.decode("utf-8"), "core/academy_views.py", "exec")
    return result


def host_guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError("ACADEMY_HOST_USER_INVALID")
    if APP.is_symlink() or not APP.is_dir() or not (APP / "manage.py").is_file():
        raise RuntimeError("ACADEMY_PASSENGER_ROOT_INVALID")
    htaccess = HOME / "public_html/.htaccess"
    if htaccess.is_symlink() or not htaccess.is_file() or not any(
        "PassengerAppRoot" in line and str(APP) in line
        for line in htaccess.read_text(errors="replace").splitlines()
    ):
        raise RuntimeError("ACADEMY_PASSENGER_ROUTE_INVALID")
    for path in (VIEW, SHADOW):
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise RuntimeError("ACADEMY_EXISTING_FILE_UNSAFE")
    if digest(SHADOW.read_bytes()) != EXPECTED_SHADOW:
        raise RuntimeError("ACADEMY_SHADOW_CONTENT_CHANGED_ABORT")
    if NEW_TEMPLATE.exists() or NEW_TEMPLATE.is_symlink():
        raise RuntimeError("ACADEMY_UNIQUE_TEMPLATE_ALREADY_EXISTS")
    if SHADOW_COLLISION.exists() or SHADOW_COLLISION.is_symlink():
        raise RuntimeError("ACADEMY_UNIQUE_TEMPLATE_SHADOW_COLLISION")
    if NEW_TEMPLATE.parent.is_symlink() or not NEW_TEMPLATE.parent.is_dir() or not VENV.is_file():
        raise RuntimeError("ACADEMY_TEMPLATE_DIRECTORY_OR_VENV_UNSAFE")
    if BACKUP_ROOT.is_symlink() or (BACKUP_ROOT.exists() and not BACKUP_ROOT.is_dir()):
        raise RuntimeError("ACADEMY_BACKUP_ROOT_UNSAFE")


def atomic_write(path: Path, data: bytes, *, add: bool = False) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-unique-", delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        if add:
            os.link(temporary, path)  # Refuses collision or concurrent template.
        else:
            os.replace(temporary, path)
            temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def restart() -> None:
    marker = APP / "tmp/restart.txt"
    if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
        raise RuntimeError("ACADEMY_PASSENGER_RESTART_UNSAFE")
    marker.touch()
    # A plain marker did not reload the public worker during the previous
    # guarded release. Use CloudLinux's documented user-scoped restart for
    # exactly this registered application; never stop or restart other apps.
    try:
        r = subprocess.run(
            ["cloudlinux-selector", "restart", "--json", "--interpreter", "python",
             "--app-root", "Saeit"],
            capture_output=True, text=True, timeout=50, check=False,
        )
    except Exception as exc:
        raise RuntimeError("ACADEMY_SELECTOR_RESTART_UNAVAILABLE") from exc
    if r.returncode:
        raise RuntimeError("ACADEMY_SELECTOR_RESTART_COMMAND_FAILED")
    try:
        response = json.loads(r.stdout)
    except Exception as exc:
        raise RuntimeError("ACADEMY_SELECTOR_RESTART_UNPARSABLE") from exc
    if isinstance(response, dict) and response.get("result") not in (None, "success", True):
        raise RuntimeError("ACADEMY_SELECTOR_RESTART_REJECTED")
    print("ACADEMY_CLOUDLINUX_TARGETED_RESTART=yes")


def check_django() -> None:
    code = """
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from pathlib import Path
from django.template.loader import get_template
from django.urls import resolve
from django.core.checks import run_checks
if run_checks(): raise RuntimeError("DJANGO_CHECK_FAILED")
expected=Path("/home/zomorod2/Saeit/core/templates/core/academy_live_resources_20261106.html")
actual=Path(get_template("core/academy_live_resources_20261106.html").origin.name).resolve()
if actual!=expected: raise RuntimeError("UNIQUE_ACADEMY_TEMPLATE_ORIGIN_CHANGED")
if resolve("/academy/").func.__module__!="core.academy_views":
    raise RuntimeError("ACADEMY_RESOLVER_CHANGED")
print("ACADEMY_UNIQUE_DJANGO_PASS=yes")
"""
    r = subprocess.run(
        [str(VENV), "-B", "-c", code], cwd=APP,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=40, check=False,
    )
    if r.returncode or "ACADEMY_UNIQUE_DJANGO_PASS=yes" not in r.stdout:
        raise RuntimeError("ACADEMY_UNIQUE_DJANGO_NOT_READY")


def check_public() -> bool:
    url = "https://zomorodmelal.ir/academy/?zm_unique_release=" + str(time.time_ns())
    req = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "ZM-Academy-Unique-Release/1.0"})
    with urlopen(req, timeout=18) as f:
        html = f.read(150_000)
        return (f.status == 200
                and "محاسبه نقطه سربه‌سر مزرعه".encode() in html
                and "وضعیت دوره‌های آموزشگاه".encode() in html
                and all(p.encode() in html for p in DESTINATIONS))


def backup_dir(value: str) -> Path:
    return BACKUP_ROOT / release_id(value)


def main(mode: str, run_id: str) -> None:
    payload = template_bytes()
    backup = backup_dir(run_id)
    if mode == "selftest":
        print("ACADEMY_UNIQUE_PACKAGE_VALID=yes")
        return
    if mode in ("preview", "publish"):
        host_guard()
        old = VIEW.read_bytes()
        patched = patched_view(old)
        if backup.exists():
            raise RuntimeError("ACADEMY_UNIQUE_RELEASE_ID_REUSED")
        if mode == "preview":
            print("ACADEMY_UNIQUE_PREFLIGHT_READY=yes")
            return
        backup.mkdir(parents=True, mode=0o700, exist_ok=False)
        for label, data in (("academy_views.original", old), ("academy_shadow.preserved", SHADOW.read_bytes())):
            path = backup / label
            with path.open("xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            path.chmod(0o600)
        atomic_write(NEW_TEMPLATE, payload, add=True)
        atomic_write(VIEW, patched)
        check_django()
        restart()
        print("ACADEMY_UNIQUE_PUBLISHED=yes")
        return
    if mode == "verify":
        if not backup.is_dir():
            raise RuntimeError("ACADEMY_UNIQUE_BACKUP_MISSING")
        old = (backup / "academy_views.original").read_bytes()
        if digest(old) != EXPECTED_VIEW or digest((backup / "academy_shadow.preserved").read_bytes()) != EXPECTED_SHADOW:
            raise RuntimeError("ACADEMY_UNIQUE_BACKUP_INVALID")
        if digest(VIEW.read_bytes()) != digest(patched_view(old)):
            raise RuntimeError("ACADEMY_UNIQUE_VIEW_HASH_MISMATCH")
        if digest(NEW_TEMPLATE.read_bytes()) != digest(payload):
            raise RuntimeError("ACADEMY_UNIQUE_TEMPLATE_HASH_MISMATCH")
        if digest(SHADOW.read_bytes()) != EXPECTED_SHADOW:
            raise RuntimeError("ACADEMY_SHADOW_CHANGED_DURING_RELEASE")
        check_django()
        for attempt in range(8):
            try:
                if check_public():
                    print("ACADEMY_UNIQUE_PUBLIC_VERIFIED=yes")
                    return
            except Exception:
                pass
            if attempt < 7:
                time.sleep(5)
        raise RuntimeError("ACADEMY_UNIQUE_PUBLIC_NOT_READY")
    if mode == "rollback":
        if not backup.is_dir():
            print("ACADEMY_UNIQUE_NOTHING_TO_ROLLBACK=yes")
            return
        old = (backup / "academy_views.original").read_bytes()
        if digest(old) != EXPECTED_VIEW:
            raise RuntimeError("ACADEMY_UNIQUE_BACKUP_CORRUPTED")
        if VIEW.is_symlink() or NEW_TEMPLATE.is_symlink():
            raise RuntimeError("ACADEMY_UNIQUE_ROLLBACK_SYMLINK_REFUSED")
        if digest(VIEW.read_bytes()) not in {EXPECTED_VIEW, digest(patched_view(old))}:
            raise RuntimeError("ACADEMY_UNIQUE_CONCURRENT_VIEW_CHANGE_REFUSED")
        if NEW_TEMPLATE.exists() and digest(NEW_TEMPLATE.read_bytes()) != digest(payload):
            raise RuntimeError("ACADEMY_UNIQUE_CONCURRENT_TEMPLATE_CHANGE_REFUSED")
        atomic_write(VIEW, old)
        if NEW_TEMPLATE.exists():
            NEW_TEMPLATE.unlink()
        restart()
        print("ACADEMY_UNIQUE_ROLLBACK=yes")
        return
    raise RuntimeError("ACADEMY_UNIQUE_UNKNOWN_MODE")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("USAGE: script MODE RUN_ID")
    main(sys.argv[1], sys.argv[2])
