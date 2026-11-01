#!/usr/bin/env python3
"""Guarded Zomorod private office additive release; no PHP accounting DB access.

Run as the authenticated cPanel user. Never invokes factory, marketing workers,
outbound messages, cPanel billing or destructive schema migration.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import sqlite3
import subprocess
import tempfile
import sys
import time
import urllib.error
import urllib.request

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit"
PRIVATE = HOME / ".private"
MODULES = ("enterprise_portal", "ecosystem_hub", "company_messaging", "company_marketing")
MAIN_BLOBS = {
    "config/settings.py": "76d37568f3477ac514d6aac14237e49ce5fd4971",
    "config/urls.py": "32a9b60c4ae5152c490b4d281069ba137d287cb1",
    "passenger_wsgi.py": "a2c6ff97d3d8684e02de4ea2f76331f946867d93",
}
ALLOWED_HEAD = set("0123456789abcdef")


def fail(message: str) -> None:
    raise RuntimeError(message)


def blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def http(path: str, redirects: bool = False) -> tuple[int, str, bytes]:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener() if redirects else urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(urllib.request.Request(
            "https://zomorodmelal.ir" + path,
            headers={"User-Agent": "ZM-Office-Guarded-Release/1.0"}), timeout=14) as r:
            return r.status, r.headers.get("Location", ""), r.read(4096)
    except urllib.error.HTTPError as error:
        return error.code, error.headers.get("Location", ""), error.read(256)


def status(path: str, expected: int, location_contains: str | None = None, body_contains: bytes | None = None) -> None:
    last = None
    for attempt in range(15):
        try:
            code, location, body = http(path)
            last = (code, location)
            if code == expected and (location_contains is None or location_contains in location) and (
                body_contains is None or body_contains in body
            ):
                print("RELEASE_LIVE_SMOKE=" + path + " HTTP=" + str(code), flush=True)
                return
        except (OSError, TimeoutError) as err:
            last = type(err).__name__
        time.sleep(3)
    fail("LIVE_SMOKE_FAILED " + path + " LAST=" + str(last))


def atomic_copy(src: Path, dst: Path, mode: int = 0o644) -> None:
    # Unique same-filesystem temporary file, always removed on exceptions.
    fd, name = tempfile.mkstemp(prefix=".zm-office-incoming-", dir=str(dst.parent))
    temp = Path(name)
    try:
        with src.open("rb") as input_stream, os.fdopen(fd, "wb") as output:
            shutil.copyfileobj(input_stream, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, dst)
    finally:
        if temp.exists():
            temp.unlink()


def restart_passenger(passenger: Path) -> None:
    """Signal Passenger's documented restart marker after atomic file swaps.

    Merely touching the WSGI module was insufficient in the October 30 live
    release: stale workers kept the old INSTALLED_APPS while loading new URLs.
    """
    if not regular(passenger):
        fail("PASSENGER_WSGI_INVALID")
    app_tmp = APP / "tmp"
    if app_tmp.is_symlink() or (app_tmp.exists() and not app_tmp.is_dir()):
        fail("PASSENGER_RESTART_DIRECTORY_UNSAFE")
    app_tmp.mkdir(mode=0o700, exist_ok=True)
    marker = app_tmp / "restart.txt"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        fail("PASSENGER_RESTART_MARKER_UNSAFE")
    # Rollback may signal another restart within the same clock tick.
    # Guarantee the marker's timestamp advances even on coarse filesystems.
    prior = marker.stat().st_mtime_ns if marker.exists() else -1
    marker.touch()
    observed = time.time_ns()
    newer_than_prior = max(observed, prior + 1_000_000_000)
    os.utime(marker, ns=(newer_than_prior, newer_than_prior))
    passenger.touch()
    print("PASSENGER_RESTART_MARKER=signalled", flush=True)
    # Passenger notices restarts on incoming requests, subject to throttling.
    time.sleep(3)



def require_mfa_provisioned(conn: sqlite3.Connection) -> None:
    """Fail closed until the isolated office DB contains a named, confirmed MFA administrator.

    This verifies metadata only: no password, OTP secret or private record is read.
    It is not a substitute for an owner-verified live login acceptance test.
    """
    try:
        active_admins = conn.execute(
            "SELECT COUNT(*) FROM auth_user WHERE is_active=1 AND is_staff=1 AND is_superuser=1"
        ).fetchone()[0]
        confirmed_admin_devices = conn.execute(
            "SELECT COUNT(*) FROM otp_totp_totpdevice AS d "
            "JOIN auth_user AS u ON u.id=d.user_id "
            "WHERE d.confirmed=1 AND u.is_active=1 AND u.is_staff=1 AND u.is_superuser=1"
        ).fetchone()[0]
    except sqlite3.DatabaseError:
        fail("OFFICE_MFA_SCHEMA_NOT_READY")
    if active_admins < 1:
        fail("OFFICE_NAMED_ADMIN_MISSING")
    if confirmed_admin_devices < 1:
        fail("OFFICE_ADMIN_MFA_DEVICE_MISSING")



def production_python() -> Path:
    """Resolve the configured Passenger interpreter, never a guessed venv."""
    # cPanel serves Passenger directives from the document root, not APP.
    htaccess = HOME / "public_html" / ".htaccess"
    if not regular(htaccess):
        fail("PASSENGER_PYTHON_UNATTESTED")
    try:
        configured = []
        app_roots = []
        for line in htaccess.read_text(encoding="utf-8").splitlines():
            if re.match(r"^\s*PassengerPython(?:\s|$)", line, re.IGNORECASE):
                fields = shlex.split(line, comments=True)
                if len(fields) != 2 or fields[0].lower() != "passengerpython":
                    fail("PASSENGER_PYTHON_UNATTESTED")
                configured.append(fields[1])
            elif re.match(r"^\s*PassengerAppRoot(?:\s|$)", line, re.IGNORECASE):
                fields = shlex.split(line, comments=True)
                if len(fields) != 2 or fields[0].lower() != "passengerapproot":
                    fail("PASSENGER_APP_ROOT_UNATTESTED")
                app_roots.append(fields[1])
    except (OSError, UnicodeError, ValueError):
        fail("PASSENGER_PYTHON_UNATTESTED")
    if len(configured) != 1:
        fail("PASSENGER_PYTHON_UNATTESTED")
    if app_roots != [str(APP)]:
        fail("PASSENGER_APP_ROOT_UNATTESTED")
    candidate = Path(configured[0])
    if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
        fail("PASSENGER_PYTHON_UNATTESTED")
    return candidate


def require_production_dependencies(py: Path) -> None:
    """Fail closed *before mutation* when the live venv lacks pinned MFA support.

    Isolated Python ignores PYTHONPATH and user packages, so a dependency
    installed under the private staging directory cannot give a false pass.
    Never print interpreter output: it may contain environment details.
    """
    expression = (
        "import importlib.metadata as metadata; "
        "import django, django_otp; "
        "assert metadata.version('django-otp') == '1.7.5'"
    )
    try:
        completed = subprocess.run(
            [str(py), "-I", "-B", "-c", expression],
            cwd=APP,
            check=False,
            timeout=25,
            capture_output=True,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
    except (OSError, subprocess.TimeoutExpired):
        fail("PRODUCTION_DEPENDENCY_PREFLIGHT_FAILED")
    if completed.returncode != 0:
        fail("PRODUCTION_DEPENDENCY_PREFLIGHT_FAILED")


def verify():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 40 or any(x not in ALLOWED_HEAD for x in sys.argv[1]):
        fail("HEAD_SHA_INVALID")
    if pwd.getpwuid(os.geteuid()).pw_name != "zomorod2":
        fail("CPANEL_ACCOUNT_UNEXPECTED")
    sha = sys.argv[1]
    stage = PRIVATE / "zomorod-messaging-release-stages" / sha
    code = stage / "code"
    # Security checks must still run under python -O; never use assert here.
    if not APP.is_dir() or APP.is_symlink():
        fail("MAIN_APPLICATION_DIRECTORY_UNSAFE")
    if (
        any(path.is_symlink() for path in (PRIVATE, stage.parent, stage, code))
        or not stage.is_dir()
        or not code.is_dir()
    ):
        fail("STAGE_DIRECTORY_UNSAFE")
    if not regular(stage / "manifest.txt") or not regular(stage / "package.tar"):
        fail("STAGE_MANIFEST_OR_ARCHIVE_MISSING")
    manifest = dict(line.split("=", 1) for line in (stage / "manifest.txt").read_text().splitlines() if "=" in line)
    if manifest.get("release") != sha or manifest.get("mode") != "PRIVATE_STAGE_NO_DEPLOY":
        fail("STAGE_IDENTITY_UNVERIFIED")
    digest = hashlib.sha256((stage / "package.tar").read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        fail("STAGE_PACKAGE_TAMPERED")
    for module in MODULES:
        if not (code / module / "models.py").is_file() or (APP / module).exists():
            fail("MODULE_MISSING_OR_ALREADY_DEPLOYED " + module)
        if (code / module).is_symlink():
            fail("MODULE_SYMLINK " + module)
    for relative, expected in MAIN_BLOBS.items():
        p = APP / relative
        if not regular(p) or blob(p) != expected:
            fail("LIVE_BASELINE_MISMATCH " + relative)
    if not regular(APP / "manage.py"):
        fail("MAIN_APPLICATION_MISSING")
    db = APP / "db.sqlite3"
    if not regular(db) or db.stat().st_size != 0:
        fail("PRODUCTION_SQLITE_IS_NOT_KNOWN_EMPTY")
    if any((APP / ("db.sqlite3" + suffix)).exists() for suffix in ("-wal", "-shm", "-journal")):
        fail("SQLITE_ACTIVE_SIDE_FILES")
    staged_db = code / "isolation.sqlite3"
    if not regular(staged_db) or staged_db.stat().st_size < 80000:
        fail("STAGED_DATABASE_NOT_READY")
    with sqlite3.connect("file:" + str(staged_db) + "?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            fail("STAGE_SQLITE_INTEGRITY_FAIL")
        require_mfa_provisioned(conn)
        n = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        if n < 55:
            fail("STAGING_SCHEMA_INCOMPLETE")
    if not regular(PRIVATE / "zomorod-business" / "management.sqlite3"):
        fail("LEGACY_BUSINESS_DB_MISSING")
    if not regular(APP / "passenger_wsgi.py"):
        fail("PASSENGER_MISSING")
    if shutil.disk_usage(APP).free < 512 * 1024**2:
        fail("INSUFFICIENT_ROLLBACK_SPACE")
    # New office stylesheet is self-contained; no production static manifest change.
    shell = code / "enterprise_portal" / "templates" / "enterprise_portal" / "shell.html"
    if not regular(shell) or b"enterprise_portal:office_css" not in shell.read_bytes():
        fail("OFFICE_STYLESHEET_ROUTE_REQUIRED")
    # Inspect Passenger's configured interpreter before creating backups or
    # replacing even a single live file. Staging-only dependencies do not count.
    py = production_python()
    require_production_dependencies(py)
    return sha, stage, code, py


def main():
    sha, stage, code, py = verify()
    preflight = (("/", 200), ("/api/health/", 200), ("/business/", 200),
                 ("/amozeshgah/", 200), ("/company/office/login/", 302))
    for path, expected in preflight:
        status(path, expected)
    root = PRIVATE / "zomorod-office-live-releases"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = root / sha
    if backup.exists() or backup.is_symlink():
        fail("RELEASE_ID_ALREADY_USED")
    backup.mkdir(mode=0o700)
    for relative in ("config/settings.py", "config/urls.py", "db.sqlite3"):
        source = APP / relative
        target = backup / relative.replace("/", "__")
        shutil.copy2(source, target)
        os.chmod(target, 0o600)
    meta = {"source_sha": sha, "status": "prepared",
            "original_blobs": MAIN_BLOBS, "db_original_bytes": 0,
            "legacy_business_database_touched": False,
            "marketing_send_enabled": False, "factory_started": False}
    (backup / "manifest.json").write_text(json.dumps(meta, sort_keys=True))
    os.chmod(backup / "manifest.json", 0o600)

    created_modules = []
    modified = False
    passenger = APP / "passenger_wsgi.py"
    try:
        for module in MODULES:
            source = code / module
            target = APP / module
            if target.exists() or target.is_symlink():
                fail("CONCURRENT_MODULE_CHANGED " + module)
            created_modules.append(target)
            shutil.copytree(source, target, symlinks=False)
        # Mark the live DB as potentially changed BEFORE atomic replacement so
        # even a partially failed copy follows the verified rollback path.
        modified = True
        atomic_copy(code / "isolation.sqlite3", APP / "db.sqlite3", 0o600)
        for relative in ("config/settings.py", "config/urls.py"):
            if blob(APP / relative) != MAIN_BLOBS[relative]:
                fail("CONCURRENT_MAIN_CHANGE " + relative)
            atomic_copy(code / relative, APP / relative)
        restart_passenger(passenger)
        subprocess.run([str(py), "manage.py", "check", "--deploy"],
                       cwd=APP, check=True, timeout=55, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        status("/", 200)
        status("/api/health/", 200)
        status("/business/", 200)
        status("/amozeshgah/", 200)
        status("/company/office/login/", 302)
        status("/company/office/secure-login/", 200, body_contains="ورود".encode())
        status("/company/office/assets/app.css", 200, body_contains=b".site-shell")
        status("/company/office/messages/", 302, location_contains="secure-login")
        status("/company/office/marketing/", 302, location_contains="secure-login")
        status("/company/office/", 302, location_contains="secure-login")
        # Release has no users and outbound services are disabled by default.
        with sqlite3.connect("file:" + str(APP / "db.sqlite3") + "?mode=ro", uri=True) as conn:
            require_mfa_provisioned(conn)
        meta["status"] = "verified_limited_web_release"
        (backup / "manifest.json").write_text(json.dumps(meta, sort_keys=True))
        print("ZOMOROD_OFFICE_LIVE_RELEASE=verified", flush=True)
        print("DYNAMIC_OFFICE_LOGIN=provisioned_authenticity_not_live_tested", flush=True)
        print("PRODUCTION_AUTH_WITH_MFA=device_registered_live_login_not_tested", flush=True)
        print("LEGACY_BUSINESS_DB_UNMODIFIED_BY_RELEASE=true", flush=True)
        print("FACTORY_STATE_UNMODIFIED=true", flush=True)
        print("OUTBOUND_MESSAGING=disabled", flush=True)
    except Exception:
        print("ZOMOROD_OFFICE_ROLLBACK=starting", flush=True)
        # Preserve every new file and DB in private quarantine for examination.
        failed = backup / "failed_new_release"
        failed.mkdir(exist_ok=True)
        for module in reversed(created_modules):
            if module.exists():
                shutil.move(str(module), str(failed / module.name))
        if modified:
            db = APP / "db.sqlite3"
            if db.exists():
                shutil.move(str(db), str(failed / "db.sqlite3"))
        for relative in ("config/settings.py", "config/urls.py", "db.sqlite3"):
            target = APP / relative
            saved = backup / relative.replace("/", "__")
            if saved.is_file():
                atomic_copy(saved, target, 0o600 if relative == "db.sqlite3" else 0o644)
        restart_passenger(passenger)
        meta["status"] = "rolled_back_after_error"
        (backup / "manifest.json").write_text(json.dumps(meta, sort_keys=True))
        print("ZOMOROD_OFFICE_ROLLBACK=completed", flush=True)
        raise


if __name__ == "__main__":
    main()
