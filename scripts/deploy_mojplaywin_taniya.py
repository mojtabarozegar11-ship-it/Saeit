#!/usr/bin/env python3
"""Install the Taniya page into the verified MojPlayWin Passenger application."""

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
APP_ROOT = HOME / "mojplaywin.com"
BACKUP_ROOT = HOME / ".mojplaywin-backups"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from taniya_patch import patch_urls, patch_views  # noqa: E402

FILES = (
    Path("config/urls.py"),
    Path("core/views.py"),
    Path("templates/taniya_studio/index.html"),
)

def safe_id(run_id):
    if not re.fullmatch(r"[0-9]{1,20}", run_id):
        raise ValueError("Invalid deployment run ID")
    return run_id

def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.taniya-", delete=False
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp_path, mode)
    os.replace(temp_path, path)

def restart_passenger():
    restart = APP_ROOT / "tmp" / "restart.txt"
    restart.parent.mkdir(parents=True, exist_ok=True)
    restart.touch()

def rollback(run_id):
    run_id = safe_id(run_id)
    backup = BACKUP_ROOT / f"taniya-{run_id}"
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        print("NO_TANIYA_BACKUP_TO_RESTORE")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in FILES:
        target = APP_ROOT / relative
        item = manifest[str(relative)]
        saved = backup / relative
        if item["existed"]:
            if not saved.is_file():
                raise RuntimeError(f"Missing backup for {relative}")
            mode = item["mode"]
            atomic_write(target, saved.read_text(encoding="utf-8"), mode)
        elif target.exists():
            if target.is_symlink():
                raise RuntimeError(f"Refusing to remove symlink: {target}")
            target.unlink()
    restart_passenger()
    (backup / "ROLLED_BACK").write_text("yes\n", encoding="utf-8")
    print("TANIYA_ROLLBACK_COMPLETE")

def deploy(run_id, commit_sha):
    run_id = safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("Invalid source commit")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if APP_ROOT.is_symlink() or not APP_ROOT.is_dir():
        raise RuntimeError("MojPlayWin Passenger root is missing or redirected")
    for required in ("passenger_wsgi.py", ".htaccess", "config/urls.py", "core/views.py"):
        if not (APP_ROOT / required).is_file():
            raise RuntimeError(f"Missing MojPlayWin application file: {required}")

    stage = HOME / f".mojplaywin-taniya-{run_id}"
    template_source = stage / FILES[2]
    if not template_source.is_file():
        raise RuntimeError("Staged Taniya page is missing")
    html = template_source.read_text(encoding="utf-8")
    if "<title>Taniya Studio" not in html or html.count('<article class="game"') != 20:
        raise RuntimeError("Staged page failed title or 20-game validation")

    url_target = APP_ROOT / FILES[0]
    view_target = APP_ROOT / FILES[1]
    template_target = APP_ROOT / FILES[2]
    for target in (url_target, view_target, template_target):
        if target.is_symlink():
            raise RuntimeError(f"Refusing to replace symlink: {target}")

    url_text = url_target.read_text(encoding="utf-8")
    view_text = view_target.read_text(encoding="utf-8")
    patched = {
        FILES[0]: patch_urls(url_text),
        FILES[1]: patch_views(view_text),
        FILES[2]: html,
    }
    ast.parse(patched[FILES[0]], filename=str(FILES[0]))
    ast.parse(patched[FILES[1]], filename=str(FILES[1]))

    backup = BACKUP_ROOT / f"taniya-{run_id}"
    if backup.exists():
        raise RuntimeError("Backup already exists; refusing to overwrite it")
    backup.mkdir(mode=0o700, parents=True)
    manifest = {}
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
            target = APP_ROOT / relative
            mode = manifest[str(relative)]["mode"]
            atomic_write(target, content, mode)
        restart_passenger()
    except Exception:
        rollback(run_id)
        raise

    (backup / "DEPLOYED.json").write_text(
        json.dumps({"commit": commit_sha, "run_id": run_id}), encoding="utf-8"
    )
    print(f"TANIYA_FILES_INSTALLED commit={commit_sha}")
    print(f"TANIYA_BACKUP={backup}")

def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: deploy_mojplaywin_taniya.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID")
    action, run_id = sys.argv[1:3]
    if action == "rollback" and len(sys.argv) == 3:
        rollback(run_id)
    elif action == "deploy" and len(sys.argv) == 4:
        deploy(run_id, sys.argv[3])
    else:
        raise SystemExit("Invalid deployment action")

if __name__ == "__main__":
    main()
