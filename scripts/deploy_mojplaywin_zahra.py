#!/usr/bin/env python3
"""Install or roll back only the static MojPlayWin Zahra route."""
import hashlib
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
ROUTE = DOCROOT / "zahra$$"
BACKUPS = HOME / ".mojplaywin-backups"
PUBLIC_HTACCESS = "PassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n"


def safe_id(value):
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Invalid deployment run ID")
    return value


def atomic_write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.zahra-", delete=False
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp_path, mode)
    os.replace(temp_path, path)


def remove_deployed_route(run_id):
    run_id = safe_id(run_id)
    backup = BACKUPS / f"zahra-{run_id}"
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        print("NO_ZAHRA_DEPLOYMENT_BACKUP")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("route_created") is not True:
        print("ZAHRA_ROUTE_NOT_CREATED_BY_THIS_RUN")
        return
    if ROUTE.is_symlink() or not ROUTE.is_dir():
        raise RuntimeError("Refusing to remove an unexpected Zahra route")
    index = ROUTE / "index.html"
    htaccess = ROUTE / ".htaccess"
    if index.is_symlink() or htaccess.is_symlink():
        raise RuntimeError("Refusing to remove symlinked Zahra files")
    if not index.is_file() or hashlib.sha256(index.read_bytes()).hexdigest() != manifest["index_sha256"]:
        raise RuntimeError("Live Zahra file changed; refusing automatic rollback")
    if htaccess.exists() and (not htaccess.is_file() or htaccess.read_text(encoding="utf-8") != PUBLIC_HTACCESS):
        raise RuntimeError("Zahra access file changed; refusing automatic rollback")
    index.unlink()
    if htaccess.exists():
        htaccess.unlink()
    try:
        ROUTE.rmdir()
    except OSError:
        raise RuntimeError("Zahra route contains unexpected files; refusing to remove them")
    manifest["rolled_back"] = True
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("ZAHRA_ROUTE_ROLLBACK_COMPLETE")


def deploy(run_id, commit_sha):
    run_id = safe_id(run_id)
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("Invalid source commit SHA")
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("Unexpected cPanel account")
    if DOCROOT.is_symlink() or not DOCROOT.is_dir():
        raise RuntimeError("MojPlayWin document root is missing or redirected")
    for name in ("passenger_wsgi.py", ".htaccess"):
        target = DOCROOT / name
        if target.is_symlink() or not target.is_file():
            raise RuntimeError(f"MojPlayWin root file is missing or unsafe: {name}")
    if ROUTE.exists() or ROUTE.is_symlink():
        raise RuntimeError("Refusing to replace an existing /zahra$$/ path")

    stage = HOME / f".mojplaywin-zahra-{run_id}"
    source = stage / "templates/zahra/index.html"
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("Staged Zahra page is missing or unsafe")
    html = source.read_bytes()
    decoded = html.decode("utf-8")
    for required in ("<title>Zahra", "Good finds, made useful.", "Market notes that show their work.", "Launch preview"):
        if required not in decoded:
            raise RuntimeError(f"Zahra page validation failed: {required}")
    if 'href="/styles.css"' in decoded or 'src="/app.js"' in decoded:
        raise RuntimeError("Zahra page has unresolved root-relative assets")

    backup = BACKUPS / f"zahra-{run_id}"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Zahra backup already exists")
    backup.mkdir(mode=0o700, parents=True)
    try:
        ROUTE.mkdir(mode=0o755)
        atomic_write(ROUTE / "index.html", html)
        atomic_write(ROUTE / ".htaccess", PUBLIC_HTACCESS.encode("utf-8"))
        manifest = {
            "run_id": run_id,
            "commit_sha": commit_sha,
            "route": "/zahra$$/",
            "route_created": True,
            "index_sha256": hashlib.sha256(html).hexdigest(),
            "root_files_modified": False,
        }
        (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except Exception:
        if ROUTE.is_dir() and not ROUTE.is_symlink():
            for child in ROUTE.iterdir():
                if child.is_file() and not child.is_symlink():
                    child.unlink()
            try:
                ROUTE.rmdir()
            except OSError:
                pass
        raise
    print(f"ZAHRA_FILES_INSTALLED commit={commit_sha}")
    print(f"ZAHRA_ROUTE=https://mojplaywin.com/zahra$$/")
    print(f"ZAHRA_BACKUP={backup}")


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        remove_deployed_route(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy_mojplaywin_zahra.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID")


if __name__ == "__main__":
    main()
