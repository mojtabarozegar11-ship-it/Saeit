#!/usr/bin/env python3
"""Deploy only MojPlayWin legacy content templates with a recoverable snapshot."""
import json
import os
import pwd
import re
import shutil
import sys
import time
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

HOME = Path("/home/zomorod2")
APP_ROOT = HOME / "Saeit-staging"
DOCROOT = HOME / "mojplaywin.com"
BACKUP_ROOT = HOME / ".mojplaywin-backups"
FILES = (
    Path("core/templates/brands/mojplaywin/base.html"),
    Path("core/templates/brands/mojplaywin/home.html"),
    Path("core/templates/brands/mojplaywin/page.html"),
    Path("core/static/site/mojplaywin.css"),
)

def safe_id(value):
    if not re.fullmatch(r"[0-9]{1,20}", str(value)):
        raise ValueError("Invalid deployment run ID")
    return str(value)

def safe_path(path):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink: {path}")
    current = path.parent
    while current not in (APP_ROOT, HOME, Path("/")):
        if current.is_symlink():
            raise RuntimeError(f"Refusing symlink parent: {current}")
        current = current.parent

def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.mpw-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, mode)
    os.replace(temporary, path)

def rollback(run_id):
    run_id = safe_id(run_id)
    backup = BACKUP_ROOT / f"mojplaywin-legacy-content-{run_id}"
    manifest_file = backup / "manifest.json"
    if not manifest_file.is_file() or manifest_file.is_symlink():
        raise RuntimeError("MojPlayWin content backup is missing")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    for relative in FILES:
        target = APP_ROOT / relative
        safe_path(target)
        entry = manifest[str(relative)]
        saved = backup / relative
        if not saved.is_file() or saved.is_symlink():
            raise RuntimeError(f"Missing backup for {relative}")
        atomic_write(target, saved.read_text(encoding="utf-8"), entry["mode"])
    restart_passenger()
    (backup / "ROLLED_BACK").write_text("yes\n", encoding="utf-8")
    print("MOJPLAYWIN_CONTENT_ROLLBACK_COMPLETE")

def restart_passenger():
    restart = DOCROOT / "tmp" / "restart.txt"
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()

def read_payload(stage):
    archive_path = stage / "content.tar.gz"
    if archive_path.is_symlink() or not archive_path.is_file():
        raise RuntimeError("Missing or unsafe content archive")
    payload = {}
    expected = {str(p) for p in FILES}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        names = {PurePosixPath(m.name).as_posix() for m in members}
        if names != expected or any(not m.isfile() for m in members):
            raise RuntimeError("Archive must contain exactly the three MojPlayWin content files")
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError("Unsafe archive path")
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Unreadable archive member: {member.name}")
            payload[Path(member.name)] = stream.read().decode("utf-8")
    return payload

def validate_payload(payload):
    home = payload[FILES[1]]
    page = payload[FILES[2]]
    css = payload[FILES[3]]
    required_base = ("MojPlayWin", "site/mojplaywin.css", "?v=20261016")
    required_home = ("mpw-hero", "PORTFOLIO MIX", "80% digital momentum", "20% real-world ventures")
    required_page = ("mpw-page-hero", "Seven practical fields", "page_key == 'agro-industry'")
    required_css = ("--bg:#050505", "--mpw-gold:#d4af37", "border:3px solid var(--mpw-gold)")
    for label, text, required in (
        ("base", payload[FILES[0]], required_base),
        ("home", home, required_home), ("page", page, required_page), ("css", css, required_css)
    ):
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise RuntimeError(f"{label} content validation failed: {missing}")
    if "/ventures/" in home:
        raise RuntimeError("Home page contains a link to an unavailable venture route")

def deploy(run_id, stage_arg):
    run_id = safe_id(run_id)
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    if APP_ROOT.is_symlink() or not APP_ROOT.is_dir():
        raise RuntimeError("MojPlayWin application root is missing or redirected")
    passenger = DOCROOT / "passenger_wsgi.py"
    if passenger.is_symlink() or not passenger.is_file():
        raise RuntimeError("MojPlayWin Passenger entrypoint is missing or unsafe")
    if "Saeit-staging" not in passenger.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("MojPlayWin no longer points to the verified application root")

    stage = Path(stage_arg)
    expected_stage = HOME / f".mojplaywin-content-{run_id}"
    if stage != expected_stage or stage.is_symlink() or not stage.is_dir():
        raise RuntimeError("Unexpected or unsafe MojPlayWin staging directory")
    payload = read_payload(stage)
    validate_payload(payload)

    outputs = {}
    for relative in FILES:
        target = APP_ROOT / relative
        safe_path(target)
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"Active MojPlayWin file is missing or unsafe: {relative}")
        existing = target.read_text(encoding="utf-8", errors="replace")
        marker = "mpw-hero" if relative.name == "home.html" else (
            "mpw-page-hero" if relative.name == "page.html" else (
                "site/mojplaywin.css" if relative.name == "base.html" else ".mpw-header"
            )
        )
        if marker not in existing:
            raise RuntimeError(f"Refusing to replace an unexpected live template: {relative}")
        outputs[relative] = payload[relative]

    backup = BACKUP_ROOT / f"mojplaywin-legacy-content-{run_id}"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("MojPlayWin content backup already exists")
    backup.mkdir(mode=0o700, parents=True)
    manifest = {}
    for relative in FILES:
        target = APP_ROOT / relative
        mode = target.stat().st_mode & 0o777
        saved = backup / relative
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, saved)
        manifest[str(relative)] = {"mode": mode}
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    try:
        for relative in FILES:
            target = APP_ROOT / relative
            atomic_write(target, outputs[relative], manifest[str(relative)]["mode"])
        restart_passenger()
        time.sleep(3)  # Give Passenger time to replace pre-release worker processes.
    except Exception:
        rollback(run_id)
        raise

    (backup / "DEPLOYED.json").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
    print("MOJPLAYWIN_LEGACY_CONTENT_DEPLOYED")
    print(f"MOJPLAYWIN_CONTENT_BACKUP={backup}")

def main():
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy RUN_ID STAGE_DIR | rollback RUN_ID")

if __name__ == "__main__":
    main()
