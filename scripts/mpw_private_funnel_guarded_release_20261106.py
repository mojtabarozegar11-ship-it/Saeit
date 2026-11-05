#!/usr/bin/env python3
"""Guarded, rollback-capable anonymous metrics release for MojPlayWin only.

No traffic replay, email, payment, order, invoice, customer row or remote URL
actions.  The only live changes are a reviewed checkout adapter, a new private
counter module, an explicit setting, and a Passenger refresh marker.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import stat
import sys
import tempfile


ACCOUNT = "zomorod2"
APP = Path("/home/zomorod2/Saeit-staging")
PUBLIC = Path("/home/zomorod2/mojplaywin.com")
BACKUPS = Path("/home/zomorod2/.local/share/mpw-private-funnel-releases")
GUEST = APP / "services/mpw_trx_guest_commerce.py"
METRICS = APP / "services/mpw_checkout_funnel.py"
SETTINGS = APP / "config/settings.py"
RESTART = PUBLIC / "tmp/restart.txt"
GUEST_BEFORE = "797b69c28c228a1892b11057584c58c6123d2b3d9080fcbb469aa865a615a090"
GUEST_AFTER = "fd4b9a0b045d911cf72bbfa933dbad8e468349f708bf420cdf62d2c462ca1c7e"
METRICS_AFTER = "177992882f08f03f3f78b721ce073ff341e988b4343544886b4fccb4860d4c2d"
MARKER = "# MPW_PRIVATE_FUNNEL_20261106"
APPEND = "\n" + MARKER + "\nMPW_PRIVATE_FUNNEL_COUNTERS_ENABLED = True\n"


def fail(reason):
    raise RuntimeError("MPW_FUNNEL_ABORT:" + reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def owned_file(path):
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file() or
            path.stat().st_uid != os.geteuid() or path.stat().st_nlink != 1):
        fail("UNSAFE_FILE:" + path.name)
    return path.read_bytes()


def guard_host():
    if pwd.getpwuid(os.geteuid()).pw_name != ACCOUNT:
        fail("WRONG_ACCOUNT")
    for root in (APP, PUBLIC):
        if root.is_symlink() or not root.is_dir() or root.resolve() != root:
            fail("WRONG_APP_ROOT")
    wsgi = owned_file(PUBLIC / "passenger_wsgi.py").decode("utf8", "replace")
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi:
        fail("WRONG_PASSENGER_APP")
    if RESTART.is_symlink() or not RESTART.parent.is_dir() or RESTART.parent.is_symlink():
        fail("UNSAFE_RESTART")


def staged(stage):
    if stage.is_symlink() or not stage.is_dir() or stage.resolve() != stage:
        fail("UNSAFE_STAGE")
    data = {}
    for name, expected in (("mpw_trx_guest_commerce.py", GUEST_AFTER),
                           ("mpw_checkout_funnel.py", METRICS_AFTER)):
        path = stage / "services" / name
        content = owned_file(path)
        if not 0 < len(content) < 32_000 or sha(content) != expected:
            fail("UNREVIEWED_CODE:" + name)
        compile(content, name, "exec")
        data[name] = content
    return data


def state(stage):
    guard_host()
    code = staged(stage)
    guest = owned_file(GUEST)
    settings = owned_file(SETTINGS)
    if sha(guest) != GUEST_BEFORE:
        fail("GUEST_VERSION_DRIFT")
    if METRICS.exists() or METRICS.is_symlink():
        fail("METRICS_ALREADY_EXISTS")
    source = settings.decode("utf-8")
    if MARKER in source or "MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED" in source:
        fail("METRICS_ALREADY_CONFIGURED")
    if source.count("# MPW_CAPTURE_ONLY_20261105") != 1 or not re.search(
            r"(?m)^MPW_GUEST_EMAIL_CLAIM_CAPTURE_ENABLED\s*=\s*True\s*$", source):
        fail("CLAIM_CAPTURE_DRIFT")
    for name in ("MPW_GUEST_RECOVERY_ENABLED", "MPW_GUEST_RECOVERY_EMAIL_APPROVED"):
        if len(re.findall(r"(?m)^" + name + r"\s*=\s*False\s*$", source)) != 1:
            fail("EMAIL_OR_PUBLIC_RECOVERY_CHANGED:" + name)
    new_settings = (source.rstrip() + APPEND).encode("utf-8")
    compile(new_settings, str(SETTINGS), "exec")
    return code, guest, settings, new_settings


def atomic_replace(path, new, expected_sha):
    if sha(owned_file(path)) != expected_sha:
        fail("CONCURRENT_EDIT:" + path.name)
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".mpw-funnel-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_new(path, data):
    if path.exists() or path.is_symlink():
        fail("MODULE_COLLISION")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def backup_originals(run_id, guest, settings):
    if not re.fullmatch(r"[0-9]{7,20}", run_id):
        fail("BAD_RUN_ID")
    if BACKUPS.is_symlink():
        fail("UNSAFE_BACKUP_ROOT")
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if stat.S_IMODE(BACKUPS.stat().st_mode) != 0o700:
        fail("UNSAFE_BACKUP_MODE")
    folder = BACKUPS / run_id
    folder.mkdir(mode=0o700)
    for filename, content in (("guest.before.py", guest), ("settings.before.py", settings)):
        atomic_new(folder / filename, content)
    return folder


def restart():
    if RESTART.is_symlink():
        fail("UNSAFE_RESTART")
    RESTART.touch()


def ready_storage():
    """Create only a private empty aggregate table; never fabricate an event."""
    spec = importlib.util.spec_from_file_location("mpw_private_funnel_runtime", METRICS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db_file = module._private_path()
    if db_file.is_relative_to(PUBLIC):
        fail("METRICS_IN_PUBLIC_ROOT")
    with sqlite3.connect(db_file, timeout=1.0) as db:
        db.execute(module.SCHEMA)
        columns = [row[1] for row in db.execute("PRAGMA table_info(daily)")]
        if columns != ["day_utc", "stage", "product_id", "count"]:
            fail("BAD_AGGREGATE_SCHEMA")


def publish(stage, run_id):
    code, guest, settings, new_settings = state(stage)
    folder = backup_originals(run_id, guest, settings)
    changed_guest = changed_settings = created_module = False
    try:
        atomic_replace(GUEST, code["mpw_trx_guest_commerce.py"], sha(guest))
        changed_guest = True
        atomic_new(METRICS, code["mpw_checkout_funnel.py"])
        created_module = True
        atomic_replace(SETTINGS, new_settings, sha(settings))
        changed_settings = True
        if sha(owned_file(GUEST)) != GUEST_AFTER or sha(owned_file(METRICS)) != METRICS_AFTER:
            fail("POST_PUBLISH_CODE_DRIFT")
        if MARKER.encode() not in owned_file(SETTINGS):
            fail("POST_PUBLISH_SETTINGS_DRIFT")
        ready_storage()
        restart()
    except BaseException:
        if changed_settings and sha(owned_file(SETTINGS)) == sha(new_settings):
            atomic_replace(SETTINGS, settings, sha(new_settings))
        if created_module and sha(owned_file(METRICS)) == METRICS_AFTER:
            METRICS.unlink()
        if changed_guest and sha(owned_file(GUEST)) == GUEST_AFTER:
            atomic_replace(GUEST, guest, GUEST_AFTER)
        restart()
        raise
    print(json.dumps({"status": "published", "backup_reference": folder.name,
                      "private_aggregates": True, "email_changed": False,
                      "payments_changed": False, "checkout_behavior_changed": False},
                     sort_keys=True), flush=True)


def verify():
    guard_host()
    guest = owned_file(GUEST)
    module = owned_file(METRICS)
    settings = owned_file(SETTINGS).decode("utf8")
    if sha(guest) != GUEST_AFTER or sha(module) != METRICS_AFTER or \
            settings.count(MARKER) != 1 or \
            not re.search(r"(?m)^MPW_PRIVATE_FUNNEL_COUNTERS_ENABLED\s*=\s*True$", settings):
        fail("VERIFY_DRIFT")
    if "MPW_GUEST_RECOVERY_EMAIL_APPROVED = True" in settings:
        fail("OUTBOUND_EMAIL_NOT_OFF")
    print("MPW_FUNNEL_VERIFY=PASS;NO_EMAIL=TRUE;NO_PAYMENT=TRUE;NO_PII=TRUE", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        fail("OPERATION_REQUIRED")
    cmd = sys.argv[1]
    if cmd == "preflight" and len(sys.argv) == 3:
        state(Path(sys.argv[2]))
        print("MPW_FUNNEL_PREFLIGHT=PASS;NO_CHANGES=TRUE", flush=True)
    elif cmd == "publish" and len(sys.argv) == 4:
        publish(Path(sys.argv[2]), sys.argv[3])
    elif cmd == "verify" and len(sys.argv) == 2:
        verify()
    else:
        fail("UNKNOWN_OPERATION")
