#!/usr/bin/env python3
"""Fail-closed, reversible, *capture-only* cPanel update for new MPW orders.

No order rows are migrated or backfilled. No recovery routes or outbound email
are enabled. Usage: preflight STAGE | publish STAGE RUN_ID | verify STAGE.
Designed to run only as the existing cPanel account through a pinned SSH relay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile


APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
SAFE_BACKUPS = Path("/home/zomorod2/.local/share/mpw-claim-capture-release")
ACCOUNT = "zomorod2"
PATHS = {
    "recovery": "services/mpw_trx_email_recovery.py",
    "guest": "services/mpw_trx_guest_commerce.py",
    "settings": "config/settings.py",
}
BEFORE = {
    "recovery": "8f5f4716ff4f2bb7b357a1dc634a01b3ac58349683d733d4ee3dca42fabd868a",
    "guest": "a9ea2dfc98809dc8991a5d8faf9a431d95b1c10cf4b33f174e69f9456a723d12",
}
AFTER = {
    "recovery": "164db1b46bf454dc311502f993e6f9d06e2f20b020e9f8986fb81fcda81a23bf",
    "guest": "fd4b9a0b045d911cf72bbfa933dbad8e468349f708bf420cdf62d2c462ca1c7e",
}
SETTING_MARKER = "# MPW_RECOVERY01_FLAGS_20261105"
CAPTURE_MARKER = "# MPW_CAPTURE_ONLY_20261105"
SETTING_ADDITION = ("\n" + CAPTURE_MARKER + "\n"
                    "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED = True\n")


def abort(reason):
    raise RuntimeError("MPW_CAPTURE_ONLY_ABORT:" + reason)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def safe_file(path):
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or path.stat().st_uid != os.geteuid() or path.stat().st_nlink != 1):
        abort("UNSAFE_FILE:" + path.name)
    return path.read_bytes()


def guard_host():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        abort("WRONG_ACCOUNT")
    for path in (APP, PUBLIC):
        if path.is_symlink() or not path.is_dir() or path.resolve() != path:
            abort("WRONG_HOST_ROOT")
    wsgi = safe_file(PUBLIC / "passenger_wsgi.py").decode("utf-8", "replace")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi:
        abort("WRONG_PASSENGER_APP")
    marker = PUBLIC / "tmp/restart.txt"
    if (marker.is_symlink() or marker.parent.is_symlink()
            or not marker.parent.is_dir()):
        abort("UNSAFE_PASSENGER_RESTART")


def source_state(stage):
    if stage.is_symlink() or not stage.is_dir():
        abort("UNSAFE_STAGE")
    staged = {}
    for key in ("recovery", "guest"):
        path = stage / PATHS[key]
        if not path.resolve().is_relative_to(stage.resolve()):
            abort("ESCAPED_STAGE:" + key)
        staged[key] = safe_file(path)
        if len(staged[key]) > 75000 or checksum(staged[key]) != AFTER[key]:
            abort("UNREVIEWED_STAGED_SOURCE:" + key)
        compile(staged[key], PATHS[key], "exec")
        current = safe_file(APP / PATHS[key])
        if checksum(current) != BEFORE[key]:
            abort("LIVE_SOURCE_DRIFT:" + key)
    return staged


def settings_state():
    current = safe_file(APP / PATHS["settings"])
    source = current.decode("utf-8")
    if (source.count(SETTING_MARKER) != 1 or CAPTURE_MARKER in source
            or "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED" in source):
        abort("LIVE_SETTINGS_DRIFT")
    for flag in ("MPW_GUEST_RECOVERY_ENABLED", "MPW_GUEST_RECOVERY_EMAIL_APPROVED"):
        if len(re.findall(r"(?m)^" + flag + r"\s*=\s*False\s*$", source)) != 1:
            abort("PUBLIC_RECOVERY_OR_EMAIL_NOT_OFF:" + flag)
    new = (source.rstrip() + SETTING_ADDITION).encode("utf-8")
    compile(new, PATHS["settings"], "exec")
    return current, new


DB_INSPECT = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, "/home/zomorod2/Saeit-staging")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from core.models import GuestOrderEmail
applied = MigrationRecorder(connection).applied_migrations()
tables = set(connection.introspection.table_names())
print(json.dumps({
  "vendor": connection.vendor,
  "m49": ("core", "0049_mpw_guest_email_recovery") in applied,
  "tables_present": all(t in tables for t in (
    "core_guestorderemail", "core_guestrecoverytoken", "core_guestrecoveryrate")),
  "claim_model": GuestOrderEmail._meta.db_table == "core_guestorderemail",
  "capture": getattr(settings, "MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED", False) is True,
  "public_recovery": getattr(settings, "MPW_GUEST_RECOVERY_ENABLED", False) is True,
  "outbound_mail": getattr(settings, "MPW_GUEST_RECOVERY_EMAIL_APPROVED", False) is True,
}, sort_keys=True))
'''


def db_state():
    result = subprocess.run([sys.executable, "-B", "-c", DB_INSPECT], cwd=APP,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                            capture_output=True, text=True, timeout=75)
    if result.returncode != 0:
        abort("DJANGO_DB_PREFLIGHT_FAILED")
    try:
        report = json.loads(result.stdout.strip())
    except ValueError:
        abort("DJANGO_DB_UNEXPECTED_OUTPUT")
    if not (report.get("vendor") == "mysql" and report.get("m49") is True
            and report.get("tables_present") is True
            and report.get("claim_model") is True and
            report.get("public_recovery") is False and
            report.get("outbound_mail") is False):
        abort("DB_OR_RUNTIME_FLAGS_DRIFT")
    return report


def preflight(stage):
    guard_host()
    staged = source_state(stage)
    old_settings, new_settings = settings_state()
    current = db_state()
    if current["capture"]:
        abort("CAPTURE_ALREADY_ENABLED")
    print("MPW_CAPTURE_ONLY_PREFLIGHT=PASS;PUBLIC_RECOVERY=OFF;EMAIL=OFF;"
          "ORDERS_CHANGED=0;PAYMENTS_CHANGED=0", flush=True)
    return staged, old_settings, new_settings


def atomic_replace(path, data, expected):
    if checksum(safe_file(path)) != expected:
        abort("CONCURRENT_EDIT:" + path.name)
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".mpw-claim-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def backup(run, old):
    if not re.fullmatch(r"[0-9]{8,20}", run):
        abort("BAD_RUN_ID")
    account_root = Path("/home") / ACCOUNT
    for path in (SAFE_BACKUPS, *SAFE_BACKUPS.parents):
        if path == account_root:
            break
        if path.is_symlink():
            abort("UNSAFE_BACKUP_ANCESTOR")
    SAFE_BACKUPS.mkdir(parents=True, mode=0o700, exist_ok=True)
    if stat.S_IMODE(SAFE_BACKUPS.stat().st_mode) & 0o077:
        abort("BACKUP_DIR_NOT_PRIVATE")
    target = SAFE_BACKUPS / run
    target.mkdir(mode=0o700)
    for key, content in old.items():
        with (target / (key + ".before")).open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    return target


def restart():
    target = PUBLIC / "tmp/restart.txt"
    if target.is_symlink() or target.parent.is_symlink():
        abort("UNSAFE_PASSENGER_RESTART")
    target.touch()


def publish(stage, run):
    staged, old_settings, new_settings = preflight(stage)
    old = {key: safe_file(APP / PATHS[key]) for key in ("recovery", "guest")}
    old["settings"] = old_settings
    backup(run, old)
    deployed = []
    try:
        for key in ("recovery", "guest", "settings"):
            payload = new_settings if key == "settings" else staged[key]
            atomic_replace(APP / PATHS[key], payload, checksum(old[key]))
            deployed.append(key)
        runtime = db_state()
        if not runtime["capture"]:
            abort("CAPTURE_NOT_ACTIVE_IN_DJANGO")
        restart()
        verify(stage)
        print("MPW_CAPTURE_ONLY_LIVE=PASS;NEW_ORDER_EMAIL_CLAIMS=ON;"
              "PUBLIC_RECOVERY=OFF;OUTBOUND_EMAIL=OFF;BACKFILL=0", flush=True)
    except BaseException:
        for key in reversed(deployed):
            new_bytes = new_settings if key == "settings" else staged[key]
            atomic_replace(APP / PATHS[key], old[key], checksum(new_bytes))
        if deployed:
            restart()
        raise


def verify(stage):
    guard_host()
    for key, expected in AFTER.items():
        source = safe_file(stage / PATHS[key])
        if checksum(source) != expected or checksum(safe_file(APP / PATHS[key])) != expected:
            abort("POST_RELEASE_CODE_DRIFT:" + key)
    settings_text = safe_file(APP / PATHS["settings"]).decode("utf-8")
    if (settings_text.count(CAPTURE_MARKER) != 1 or
            settings_text.count("MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED = True") != 1):
        abort("POST_RELEASE_SETTINGS_DRIFT")
    runtime = db_state()
    if not runtime["capture"]:
        abort("POST_RELEASE_CAPTURE_NOT_ENABLED")
    print("MPW_CAPTURE_ONLY_VERIFIED=PASS;PUBLIC_RECOVERY=OFF;OUTBOUND_EMAIL=OFF")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "preflight":
        preflight(Path(sys.argv[2]))
    elif len(sys.argv) == 4 and sys.argv[1] == "publish":
        publish(Path(sys.argv[2]), sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "verify":
        verify(Path(sys.argv[2]))
    else:
        raise SystemExit("Usage: preflight STAGE | publish STAGE RUN_ID | verify STAGE")
