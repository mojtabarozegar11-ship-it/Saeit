#!/usr/bin/env python3
"""Safely install or roll back the standalone SAMAN page under MojPlayWin."""

import json
import os
import pwd
import re
import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
BACKUP_ROOT = HOME / ".mojplaywin-backups"

def safe_id(run_id):
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("Invalid deployment run ID")
    return run_id

def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.saman-", delete=False
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp_path, mode)
    os.replace(temp_path, path)

def rollback(run_id):
    run_id = safe_id(run_id)
    backup = BACKUP_ROOT / f"saman-{run_id}"
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        print("NO_SAMAN_BACKUP_TO_RESTORE")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target_dir = DOCROOT / "saman"
    target = target_dir / "index.html"
    if target_dir.is_symlink() or target.is_symlink():
        raise RuntimeError("Refusing to roll back through a symlink")
    item = manifest["index.html"]
    saved = backup / "index.html"
    if item["existed"]:
        if not saved.is_file():
            raise RuntimeError("Missing SAMAN backup")
        atomic_write(target, saved.read_text(encoding="utf-8"), item["mode"])
    elif target.exists():
        target.unlink()
    if not manifest["directory_existed"] and target_dir.is_dir() and not any(target_dir.iterdir()):
        target_dir.rmdir()
    (backup / "ROLLED_BACK").write_text("yes\n", encoding="utf-8")
    print("SAMAN_ROLLBACK_COMPLETE")

def deploy(run_id, commit_sha):
    run_id = safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("Invalid source commit")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    for required in ("passenger_wsgi.py", ".htaccess"):
        if not (DOCROOT / required).is_file():
            raise RuntimeError(f"Missing MojPlayWin document-root file: {required}")
    wrapper = (DOCROOT / "passenger_wsgi.py").read_text(encoding="utf-8", errors="replace")
    if "Saeit-staging" not in wrapper:
        raise RuntimeError("Passenger wrapper no longer points at the verified Saeit application")

    stage = HOME / f".mojplaywin-saman-{run_id}"
    source = stage / "templates" / "saman" / "index.html"
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("Staged SAMAN page is missing or unsafe")
    html = source.read_text(encoding="utf-8")
    required_markers = ("<html lang=\"en\">", "<title>SAMAN", "SAMAN collection", "Explore MojPlayWin")
    if any(marker not in html for marker in required_markers):
        raise RuntimeError("Staged SAMAN page failed content validation")

    target_dir = DOCROOT / "saman"
    target = target_dir / "index.html"
    if target_dir.is_symlink() or target.is_symlink():
        raise RuntimeError("Refusing to write through a symlink")
    if target_dir.exists() and not target_dir.is_dir():
        raise RuntimeError("The SAMAN target path exists and is not a directory")
    directory_existed = target_dir.is_dir()
    existed = target.is_file()
    mode = (target.stat().st_mode & 0o777) if existed else 0o644

    backup = BACKUP_ROOT / f"saman-{run_id}"
    if backup.exists():
        raise RuntimeError("SAMAN backup already exists; refusing to overwrite it")
    backup.mkdir(mode=0o700, parents=True)
    if existed:
        shutil.copy2(target, backup / "index.html")
    (backup / "manifest.json").write_text(
        json.dumps({"directory_existed": directory_existed,
                    "index.html": {"existed": existed, "mode": mode}}),
        encoding="utf-8"
    )

    try:
        atomic_write(target, html, mode)
    except Exception:
        rollback(run_id)
        raise

    (backup / "DEPLOYED.json").write_text(
        json.dumps({"commit": commit_sha, "run_id": run_id}), encoding="utf-8"
    )
    print(f"SAMAN_FILES_INSTALLED commit={commit_sha}")
    print(f"SAMAN_BACKUP={backup}")

def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: deploy_mojplaywin_saman.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID")
    action, run_id = sys.argv[1:3]
    if action == "rollback" and len(sys.argv) == 3:
        rollback(run_id)
    elif action == "deploy" and len(sys.argv) == 4:
        deploy(run_id, sys.argv[3])
    else:
        raise SystemExit("Invalid deployment action")

if __name__ == "__main__":
    main()
