#!/usr/bin/env python3
"""Append-only MojPlayWin ACTIVE homepage deployment. No other template may change."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import tempfile

OWNER = "zomorod2"
HOME = Path("/home/zomorod2")
APP = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
RELATIVE = Path("core/templates/mojplaywin/home.html")
BACKUPS = HOME / ".mojplaywin-backups"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise RuntimeError("Unsafe run ID")
    return value


def check_path(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("Refusing symbolic link: " + str(path))
    p = path.parent
    while p not in (HOME, Path("/")):
        if p.is_symlink():
            raise RuntimeError("Refusing symbolic link parent")
        p = p.parent


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    check_path(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".mpw-active-", delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def validate_only_append(old: str, proposed: str) -> None:
    if not old.rstrip().endswith("{% endblock %}"):
        raise RuntimeError("Existing active home has a different ending")
    if "mw-home-title" not in old or "WHAT WE DO" not in old or "CONNECTED VENTURES" not in old:
        raise RuntimeError("Existing active MojPlayWin template is unrecognized")
    end = old.rfind("{% endblock %}")
    if not proposed.startswith(old[:end]) or not proposed.rstrip().endswith("{% endblock %}"):
        raise RuntimeError("Existing homepage content would be changed or removed")
    if proposed.count('id="mpw-home-ten-guides"') != 1:
        raise RuntimeError("Expected only one original ten-guide section")
    found = re.findall(r'id="home-guide-([a-z-]+)"', proposed)
    expected = {
        "vertical-slice", "accessible-play", "ai-workflow-risk", "ai-privacy",
        "demo-proof", "product-readiness", "web-discovery", "support-library",
        "vancouver-pilot-plan", "agro-scenario-dashboard",
    }
    if len(found) != 10 or set(found) != expected:
        raise RuntimeError("Expected exactly ten verified unique guide IDs")
    if len(proposed.encode("utf-8")) - len(old.encode("utf-8")) not in range(15000, 23001):
        raise RuntimeError("Unexpected change size to active homepage")
    for marker in ("class=\"mw-grid\"", "class=\"mw-card\"", "site/heroes/",
                   "Implementation method", "Quality checklist", "Example"):
        if marker not in proposed:
            raise RuntimeError("Required content marker is absent: " + marker)
    if "{% extends \"base.html\" %}" not in proposed:
        raise RuntimeError("Must preserve existing site base template")
    if "https://" in proposed[end:]:
        raise RuntimeError("New content cannot add unverified external destinations")


def verify_host() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != OWNER:
        raise RuntimeError("Unexpected deployment account")
    for d in (APP, DOCROOT):
        if not d.is_dir() or d.is_symlink():
            raise RuntimeError("Application or document root is unavailable")
    passenger = DOCROOT / "passenger_wsgi.py"
    if passenger.is_symlink() or not passenger.is_file():
        raise RuntimeError("Passenger entrypoint is unavailable")
    if "Saeit-staging" not in passenger.read_text(errors="replace"):
        raise RuntimeError("Document root points to a different app")


def deploy(run_id: str) -> None:
    verify_host()
    stage = HOME / (".mpw-active-home-" + run_id)
    backup = BACKUPS / ("mpw-active-home-" + run_id)
    target = APP / RELATIVE
    check_path(target)
    if not target.is_file() or target.is_symlink() or not stage.is_dir() or stage.is_symlink():
        raise RuntimeError("Unsafe or missing source/staging path")
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Refusing to reuse backup")
    old_bytes = target.read_bytes()
    new_bytes = (stage / "home.html").read_bytes()
    validate_only_append(old_bytes.decode("utf-8"), new_bytes.decode("utf-8"))
    mode = target.stat().st_mode & 0o777
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(target, backup / "home.html")
    if digest((backup / "home.html").read_bytes()) != digest(old_bytes):
        raise RuntimeError("Backup was not verified")
    manifest = {"before": digest(old_bytes), "after": digest(new_bytes), "mode": mode}
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    try:
        atomic_write(target, new_bytes, mode)
        if digest(target.read_bytes()) != manifest["after"]:
            raise RuntimeError("Atomic write verification failed")
        (DOCROOT / "tmp").mkdir(exist_ok=True)
        (DOCROOT / "tmp" / "restart.txt").touch()
    except Exception:
        rollback(run_id)
        raise
    print("MOJPLAYWIN_ACTIVE_HOME_TEN_INSTALLED=yes", flush=True)
    print("MOJPLAYWIN_ACTIVE_HOME_BACKUP_VERIFIED=yes", flush=True)


def rollback(run_id: str) -> None:
    backup = BACKUPS / ("mpw-active-home-" + run_id)
    source = backup / "home.html"
    meta = backup / "manifest.json"
    target = APP / RELATIVE
    check_path(target)
    if any(p.is_symlink() for p in (backup, source, meta, target)):
        raise RuntimeError("Unsafe rollback path")
    if not source.is_file() or not meta.is_file() or not target.is_file():
        raise RuntimeError("Required original backup not present")
    record = json.loads(meta.read_text(encoding="utf-8"))
    previous = source.read_bytes()
    current = target.read_bytes()
    if digest(previous) != record["before"]:
        raise RuntimeError("Backup content checksum does not match")
    if digest(current) not in (record["after"], record["before"]):
        raise RuntimeError("Source modified by other process; refusing to overwrite")
    atomic_write(target, previous, record["mode"])
    (DOCROOT / "tmp" / "restart.txt").touch()
    print("MOJPLAYWIN_ACTIVE_HOME_ROLLBACK_VERIFIED=yes", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("deploy", "rollback"):
        raise SystemExit("Usage: deploy|rollback RUN_ID")
    run = safe_run_id(sys.argv[2])
    if sys.argv[1] == "deploy":
        deploy(run)
    else:
        rollback(run)
