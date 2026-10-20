#!/usr/bin/env python3
"""Single-purpose, reversible PICM text-image UI update on existing cPanel.

Allows exactly two relative template files. NEVER touches views, shared routing,
factory, databases, authentication code, other subsite files or worker tokens.
Verifies the old production template Git blob SHA before overwriting to prevent
clobbering unrelated concurrent changes. Passenger reload is limited to the
existing shared app's two standard restart markers, with rollback on failures.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import tempfile

HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
BACKUPS = HOME / ".mojplaywin-backups"
RELATIVE = (Path("templates/picm/index.html"), Path("templates/picm/text_image.js"))
BASE_INDEX_BLOB = "92e4fe396fa04a94e56265d3db7db56d7824b1dc"
REQUIRED = ("id=\"mode-text_image\"", "id=\"text-image-options\"",
            "id=\"picm-text-resume\"", "{% include 'picm/text_image.js' %}")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw):
    return hashlib.sha1(("blob " + str(len(raw)) + "\0").encode("ascii") + raw).hexdigest()


def atomically_write(path, data, mode=0o644):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("PICM_UNSAFE_FILE")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".picm-ui-")
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


def sanity(run_id):
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise RuntimeError("PICM_INVALID_RUN_ID")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("PICM_UNEXPECTED_CPANEL_USER")
    if any(p.is_symlink() or not p.is_dir() for p in (APP, DOCROOT)):
        raise RuntimeError("PICM_WRONG_APPLICATION_ROOT")
    wsgi = DOCROOT / "passenger_wsgi.py"
    if wsgi.is_symlink() or not wsgi.is_file() or "Saeit-staging" not in wsgi.read_text(errors="replace"):
        raise RuntimeError("PICM_UNEXPECTED_PASSENGER_APP")
    if not (APP / "templates/picm/login.html").is_file():
        raise RuntimeError("PICM_LOGIN_MISSING")
    if not (HOME / ".picm-queue/.owner-user-id").is_file():
        raise RuntimeError("PICM_OWNER_BINDING_MISSING")
    for relative in RELATIVE:
        parent = APP / relative.parent
        if parent.is_symlink() or not parent.is_dir():
            raise RuntimeError("PICM_UNSAFE_TEMPLATE_FOLDER")


def restart():
    for root in (APP, DOCROOT):
        tmp = root / "tmp"
        if tmp.is_symlink():
            raise RuntimeError("PICM_UNSAFE_PASSENGER_MARKER")
        tmp.mkdir(exist_ok=True)
        marker = tmp / "restart.txt"
        if marker.is_symlink():
            raise RuntimeError("PICM_UNSAFE_PASSENGER_MARKER")
        marker.touch()


def stage_path(run_id):
    return HOME / (".picm-text-image-stage-" + run_id)


def backup_path(run_id):
    return BACKUPS / ("picm-text-image-" + run_id)


def deploy(run_id, expected_index, expected_js):
    sanity(run_id)
    if not all(re.fullmatch(r"[a-f0-9]{64}", d) for d in (expected_index, expected_js)):
        raise RuntimeError("PICM_INVALID_CANDIDATE_HASH")
    stage = stage_path(run_id)
    if stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("PICM_STAGE_MISSING")
    content = {}
    for relative, expected in zip(RELATIVE, (expected_index, expected_js)):
        file = stage / relative
        if file.is_symlink() or not file.is_file():
            raise RuntimeError("PICM_CANDIDATE_MISSING")
        raw = file.read_bytes()
        if sha256(raw) != expected or len(raw) < 1500:
            raise RuntimeError("PICM_BAD_CANDIDATE_DIGEST")
        content[str(relative)] = raw
    html = content[str(RELATIVE[0])].decode("utf-8")
    javascript = content[str(RELATIVE[1])].decode("utf-8")
    if any(item not in html for item in REQUIRED):
        raise RuntimeError("PICM_NEW_UI_MISSING_REQUIRED_CONTROLS")
    if ("fetch(\"/picm/api/submit/\"" not in javascript or
            "event.stopImmediatePropagation()" not in javascript or
            'credentials:"same-origin"' not in javascript):
        raise RuntimeError("PICM_UNSAFE_NEW_UI")
    old = APP / RELATIVE[0]
    new = APP / RELATIVE[1]
    if not old.is_file() or old.is_symlink() or new.is_symlink():
        raise RuntimeError("PICM_UNEXPECTED_TEMPLATE_STATE")
    if blob_sha(old.read_bytes()) != BASE_INDEX_BLOB:
        raise RuntimeError("PICM_LIVE_TEMPLATE_CHANGED_REFUSE_OVERWRITE")
    if new.exists():
        raise RuntimeError("PICM_NEW_FILE_ALREADY_EXISTS_REFUSE")
    backup = backup_path(run_id)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("PICM_BACKUP_ALREADY_EXISTS")
    backup.mkdir(parents=True, mode=0o700)
    (backup / RELATIVE[0]).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old, backup / RELATIVE[0])
    record = {
        "run_id": run_id,
        "original_index_sha": sha256(old.read_bytes()),
        "installed_index_sha": expected_index,
        "installed_js_sha": expected_js,
        "files": [str(item) for item in RELATIVE],
    }
    atomically_write(backup / "manifest.json", (json.dumps(record) + "\n").encode(), 0o600)
    changed = False
    try:
        atomically_write(old, content[str(RELATIVE[0])], old.stat().st_mode & 0o777)
        changed = True
        atomically_write(new, content[str(RELATIVE[1])], 0o644)
        restart()
    except Exception:
        if changed:
            rollback(run_id)
        raise
    print("PICM_SCOPED_TEXT_IMAGE_UI_DEPLOYED")
    print("PICM_UI_BACKUP_RUN_ID=" + run_id)


def rollback(run_id):
    sanity(run_id)
    backup = backup_path(run_id)
    manifest = backup / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("PICM_ROLLBACK_MANIFEST_MISSING")
    rec = json.loads(manifest.read_text(encoding="utf-8"))
    if rec.get("run_id") != run_id:
        raise RuntimeError("PICM_ROLLBACK_ID_MISMATCH")
    old = APP / RELATIVE[0]
    new = APP / RELATIVE[1]
    if old.is_symlink() or new.is_symlink():
        raise RuntimeError("PICM_UNSAFE_ROLLBACK_FILE")
    backup_original = backup / RELATIVE[0]
    if backup_original.is_symlink() or sha256(backup_original.read_bytes()) != rec["original_index_sha"]:
        raise RuntimeError("PICM_BACKUP_INTEGRITY_FAILURE")
    if old.exists() and sha256(old.read_bytes()) != rec["installed_index_sha"]:
        raise RuntimeError("PICM_ROLLBACK_REFUSES_CHANGED_TEMPLATE")
    if new.exists() and sha256(new.read_bytes()) != rec["installed_js_sha"]:
        raise RuntimeError("PICM_ROLLBACK_REFUSES_CHANGED_SCRIPT")
    atomically_write(old, backup_original.read_bytes(),
                     backup_original.stat().st_mode & 0o777)
    if new.is_file():
        new.unlink()
    restart()
    print("PICM_SCOPED_TEXT_IMAGE_UI_ROLLED_BACK")


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy RUN_ID INDEX_SHA256 JS_SHA256 | rollback RUN_ID")
