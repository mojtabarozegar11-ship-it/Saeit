#!/usr/bin/env python3
"""Install or roll back the SAMAN page in the verified MojPlayWin Django app."""

import ast
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
APP_ROOT = HOME / "Saeit-staging"
BACKUP_ROOT = HOME / ".mojplaywin-backups"
FILES = (
    Path("config/urls.py"),
    Path("core/views.py"),
    Path("templates/saman/index.html"),
)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from saman_patch import patch_urls, patch_views  # noqa: E402


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


def restart_passenger():
    restart = DOCROOT / "tmp" / "restart.txt"
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()


def rollback(run_id):
    run_id = safe_id(run_id)
    backup = BACKUP_ROOT / f"saman-{run_id}"
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        print("NO_SAMAN_BACKUP_TO_RESTORE")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in FILES:
        target = APP_ROOT / relative
        if target.is_symlink():
            raise RuntimeError(f"Refusing to replace symlink: {target}")
        item = manifest[str(relative)]
        saved = backup / relative
        if item["existed"]:
            if not saved.is_file():
                raise RuntimeError(f"Missing backup for {relative}")
            atomic_write(target, saved.read_text(encoding="utf-8"), item["mode"])
        elif target.exists():
            target.unlink()
    saman_dir = APP_ROOT / "templates" / "saman"
    if not manifest["saman_template_directory_existed"] and saman_dir.is_dir() and not any(saman_dir.iterdir()):
        saman_dir.rmdir()
    restart_passenger()
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
    if APP_ROOT.is_symlink() or not APP_ROOT.is_dir():
        raise RuntimeError("Active Saeit application root is missing or redirected")
    for required in ("passenger_wsgi.py", ".htaccess"):
        if not (DOCROOT / required).is_file():
            raise RuntimeError(f"Missing MojPlayWin document-root file: {required}")
    wrapper = (DOCROOT / "passenger_wsgi.py").read_text(encoding="utf-8", errors="replace")
    if "Saeit-staging" not in wrapper:
        raise RuntimeError("Passenger wrapper no longer points at the verified Saeit application")
    for required in ("config/urls.py", "core/views.py"):
        if not (APP_ROOT / required).is_file():
            raise RuntimeError(f"Missing active Saeit application file: {required}")

    stage = HOME / f".mojplaywin-saman-{run_id}"
    template_source = stage / "templates" / "saman" / "index.html"
    if not template_source.is_file() or template_source.is_symlink():
        raise RuntimeError("Staged SAMAN page is missing or unsafe")
    html = template_source.read_text(encoding="utf-8")
    required_markers = ("<html lang=\"en\">", "<title>SAMAN", "SAMAN collection", "Explore MojPlayWin")
    if any(marker not in html for marker in required_markers):
        raise RuntimeError("Staged page failed English content validation")

    template_dir = APP_ROOT / "templates" / "saman"
    if (APP_ROOT / "templates").is_symlink() or template_dir.is_symlink():
        raise RuntimeError("Refusing to write through a template symlink")
    template_directory_existed = template_dir.is_dir()
    for relative in FILES:
        target = APP_ROOT / relative
        if target.is_symlink():
            raise RuntimeError(f"Refusing to replace symlink: {target}")

    url_target = APP_ROOT / FILES[0]
    view_target = APP_ROOT / FILES[1]
    patched = {
        FILES[0]: patch_urls(url_target.read_text(encoding="utf-8")),
        FILES[1]: patch_views(view_target.read_text(encoding="utf-8")),
        FILES[2]: html,
    }
    ast.parse(patched[FILES[0]], filename=str(FILES[0]))
    ast.parse(patched[FILES[1]], filename=str(FILES[1]))

    backup = BACKUP_ROOT / f"saman-{run_id}"
    if backup.exists():
        raise RuntimeError("SAMAN backup already exists; refusing to overwrite it")
    backup.mkdir(mode=0o700, parents=True)
    manifest = {"saman_template_directory_existed": template_directory_existed}
    for relative in FILES:
        target = APP_ROOT / relative
        existed = target.is_file()
        mode = (target.stat().st_mode & 0o777) if existed else 0o644
        manifest[str(relative)] = {"existed": existed, "mode": mode}
        if existed:
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    try:
        for relative, content in patched.items():
            atomic_write(APP_ROOT / relative, content, manifest[str(relative)]["mode"])
        restart_passenger()
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
