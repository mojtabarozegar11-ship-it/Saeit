#!/usr/bin/env python3
"""Publish only reviewed academy resource-card content to the real Passenger app.

Requires exact live SHA, uses private recoverable backups, and refuses to
overwrite a concurrent edit. No database writes, mail, orders, or test users.
The release runner replaces PACKED_FILES with reviewed GitHub source bytes.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

PACKED_FILES = None  # Replaced with the exact reviewed academy resource source on runner.
HOME = Path("/home/zomorod2")
APP = HOME / "Saeit"
BACKUP_ROOT = HOME / ".backups/zomorod-academy-resources-20261106"
FILES = {
    # Current host SHA independently re-measured by read-only run 42258608158:
    # a concurrent publisher restored the previous views file after the first
    # guarded academy login release. Only this exact baseline may be replaced.
    "core/academy_views.py": "8e53348804828cb72a255efd517f206a12d8d1ded08a3f74a4a6c14174c5b3b0",
    "core/templates/core/academy.html": "358e34742f7b3177467c0c20b3e8dc9de17ef6dcef8aca10a5c1dd9fc8813d54",
}
VENV = HOME / "virtualenv/Saeit/3.10/bin/python"
REQUIRED_LIVE_DESTINATIONS = (
    "/agriculture/free-tools/20261025/farm-break-even/",
    "/agriculture/free-tools/20261025/import-landed-cost/",
    "/resources/20261025/farm-risk/",
    "/ask-master/index.php?service=1",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rid(value: str) -> str:
    if not re.fullmatch(r"[0-9]{6,20}", value):
        raise RuntimeError("INVALID_RELEASE_ID")
    return value


def package() -> dict[str, bytes]:
    if not isinstance(PACKED_FILES, dict) or set(PACKED_FILES) != set(FILES):
        raise RuntimeError("RESOURCE_PACKAGE_INCOMPLETE")
    content = {name: base64.b64decode(PACKED_FILES[name], validate=True) for name in FILES}
    for name, data in content.items():
        if not data or len(data) > 100_000 or b"\x00" in data or sha(data) == FILES[name]:
            raise RuntimeError("INVALID_OR_UNCHANGED_RESOURCE_PAYLOAD:" + name)
    view = content["core/academy_views.py"]
    page = content["core/templates/core/academy.html"]
    if any(u.encode() not in view for u in REQUIRED_LIVE_DESTINATIONS):
        raise RuntimeError("RESOURCE_DESTINATION_MISSING")
    if (b"if not courses" not in page or b"has_paid_courses" not in page or
            b"{{ resource.url }}" not in page or b"{{ resource.action }}" not in page or
            b"status__in=(\"active\", \"completed\")" not in view):
        raise RuntimeError("RESOURCE_TEMPLATE_OR_AUTH_CONTRACT_FAILED")
    compile(view.decode("utf-8"), "core/academy_views.py", "exec")
    return content


def host_guard() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError("CPANEL_USER_INVALID")
    if APP.is_symlink() or not APP.is_dir() or not (APP / "manage.py").is_file():
        raise RuntimeError("APP_ROOT_INVALID")
    htaccess = HOME / "public_html/.htaccess"
    if htaccess.is_symlink() or not htaccess.is_file() or not any(
        "PassengerAppRoot" in line and str(APP) in line
        for line in htaccess.read_text(errors="replace").splitlines()
    ):
        raise RuntimeError("PASSENGER_ROOT_CHANGED")
    for name in FILES:
        path = APP / name
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise RuntimeError("RESOURCE_TARGET_UNSAFE:" + name)
    if not VENV.is_file():
        raise RuntimeError("DJANGO_VENV_MISSING")
    if BACKUP_ROOT.is_symlink() or (BACKUP_ROOT.exists() and not BACKUP_ROOT.is_dir()):
        raise RuntimeError("RESOURCE_BACKUP_ROOT_UNSAFE")


def original() -> dict[str, bytes]:
    return {name: (APP / name).read_bytes() for name in FILES}


def preview(old: dict[str, bytes]) -> None:
    for name, expected in FILES.items():
        if sha(old[name]) != expected:
            raise RuntimeError("ACADEMY_RESOURCE_LIVE_CHANGED_ABORT:" + name)


def atomic(path: Path, payload: bytes) -> None:
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".zm-academy-res-", delete=False) as f:
            temp = f.name
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
        temp = None
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def restart() -> None:
    marker = APP / "tmp/restart.txt"
    if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.is_dir():
        raise RuntimeError("PASSENGER_RESTART_UNSAFE")
    marker.touch()


def check_django() -> None:
    code = """
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.checks import run_checks
from django.template.loader import get_template
from django.urls import resolve
if run_checks(): raise RuntimeError("DJANGO_CHECK_FAILED")
get_template("core/academy.html")
if resolve("/academy/").url_name != "academy":
    raise RuntimeError("ACADEMY_ROUTE_MISSING")
print("ACADEMY_RESOURCE_DJANGO_PASS")
"""
    r = subprocess.run(
        [str(VENV), "-B", "-c", code], cwd=APP,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=35, check=False,
    )
    if r.returncode or "ACADEMY_RESOURCE_DJANGO_PASS" not in r.stdout:
        raise RuntimeError("ACADEMY_RESOURCE_DJANGO_CHECK_FAILED")


def check_public() -> bool:
    req = Request(
        "https://zomorodmelal.ir/academy/?zm_resource_release=" + str(time.time_ns()),
        headers={"Cache-Control": "no-cache", "User-Agent": "ZM-Academy-Resources/1.0"},
    )
    with urlopen(req, timeout=18) as response:
        page = response.read(150_000)
        return (
            response.status == 200
            and "محاسبه نقطه سربه‌سر مزرعه".encode() in page
            and "برآورد هزینه واردات".encode() in page
            and "وضعیت دوره‌های آموزشگاه".encode() in page
            and all(p.encode() in page for p in REQUIRED_LIVE_DESTINATIONS)
        )


def main(mode: str, run_id: str) -> None:
    pack = package()
    rid(run_id)
    if mode == "selftest":
        print("ACADEMY_RESOURCE_PACKAGE_VALID=yes")
        return
    host_guard()
    backup = BACKUP_ROOT / run_id
    if mode == "preview":
        preview(original())
        if backup.exists():
            raise RuntimeError("RESOURCE_RELEASE_ID_REUSED")
        print("ACADEMY_RESOURCE_PREFLIGHT_READY=yes")
        return
    if mode == "publish":
        old = original()
        preview(old)
        if backup.exists():
            raise RuntimeError("RESOURCE_RELEASE_ID_REUSED")
        backup.mkdir(parents=True, mode=0o700, exist_ok=False)
        for name, data in old.items():
            dest = backup / name
            dest.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            with dest.open("xb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            dest.chmod(0o600)
        for name in FILES:
            atomic(APP / name, pack[name])
        check_django()
        restart()
        print("ACADEMY_RESOURCE_PUBLISHED=yes")
        return
    if mode == "verify":
        if not backup.is_dir():
            raise RuntimeError("RESOURCE_BACKUP_MISSING")
        for name, data in pack.items():
            if sha((APP / name).read_bytes()) != sha(data):
                raise RuntimeError("RESOURCE_DEPLOYED_SHA_MISMATCH:" + name)
        check_django()
        for attempt in range(6):
            try:
                if check_public():
                    print("ACADEMY_RESOURCE_PUBLIC_VERIFIED=yes")
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(4)
        raise RuntimeError("ACADEMY_RESOURCE_PUBLIC_NOT_READY")
    if mode == "rollback":
        if not backup.is_dir():
            print("ACADEMY_RESOURCE_NOTHING_TO_ROLLBACK=yes")
            return
        old = {name: (backup / name).read_bytes() for name in FILES}
        if any(sha(old[name]) != expected for name, expected in FILES.items()):
            raise RuntimeError("RESOURCE_BACKUP_CORRUPTED")
        for name in FILES:
            target = APP / name
            if target.is_symlink() or sha(target.read_bytes()) not in {FILES[name], sha(pack[name])}:
                raise RuntimeError("RESOURCE_CONCURRENT_EDIT_ABORT_ROLLBACK:" + name)
        for name in FILES:
            atomic(APP / name, old[name])
        restart()
        print("ACADEMY_RESOURCE_ROLLBACK=yes")
        return
    raise RuntimeError("UNKNOWN_RESOURCE_RELEASE_MODE")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("USAGE: script MODE RUN_ID")
    main(sys.argv[1], sys.argv[2])
