# Moj Prop catalog trigger compatibility marker.
#!/usr/bin/env python3
"""Install or roll back only the static Moj Prop route."""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import sys
import tempfile
from pathlib import Path

HOME = Path("/home/zomorod2")
DOCROOT = HOME / "mojplaywin.com"
ROUTE = DOCROOT / "moj-prop"
BACKUPS = HOME / ".mojplaywin-backups"
PUBLIC_HTACCESS = "PassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n"
FILES = (
    Path("index.html"),
    Path("rules/index.html"),
    Path("signals/index.html"),
    Path("payment/index.html"),
    Path("contact/index.html"),
)


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[0-9]{1,20}", value):
        raise ValueError("Invalid deployment run ID")
    return value


def atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.moj-prop-", delete=False
    ) as stream:
        temp_path = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temp_path, mode)
    os.replace(temp_path, path)


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def staged_root(run_id: str) -> Path:
    root = HOME / f".mojplaywin-moj-prop-{run_id}" / "templates" / "moj-prop"
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Moj Prop staged directory is missing or unsafe")
    for relative in FILES:
        source = root / relative
        if source.is_symlink() or not source.is_file():
            raise RuntimeError(f"Missing or unsafe staged file: {relative}")
    index = (root / "index.html").read_text(encoding="utf-8")
    for required in ("<title>Moj Prop", "Discipline before ", "capital.", "mojtaba.bot.ai"):
        if required not in index:
            raise RuntimeError(f"Moj Prop page validation failed: {required}")
    return root


def route_files() -> list[Path]:
    result: list[Path] = []
    for path in ROUTE.rglob("*"):
        if path.is_file():
            result.append(path.relative_to(ROUTE))
    return sorted(result)


def rollback(run_id: str) -> None:
    run_id = safe_id(run_id)
    manifest_path = BACKUPS / f"moj-prop-{run_id}" / "manifest.json"
    if not manifest_path.is_file():
        print("NO_MOJ_PROP_DEPLOYMENT_BACKUP")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("route_created") is not True:
        print("MOJ_PROP_ROUTE_NOT_CREATED_BY_THIS_RUN")
        return
    if ROUTE.is_symlink() or not ROUTE.is_dir():
        raise RuntimeError("Refusing to remove an unexpected Moj Prop route")
    expected = {Path(item) for item in manifest.get("files", {})}
    actual = set(route_files())
    if actual != expected | {Path(".htaccess")}:
        raise RuntimeError("Moj Prop route contains unexpected files; refusing rollback")
    for relative, expected_sha in manifest["files"].items():
        path = ROUTE / relative
        if digest(path.read_bytes()) != expected_sha:
            raise RuntimeError("Live Moj Prop content changed; refusing rollback")
    htaccess = ROUTE / ".htaccess"
    if htaccess.read_text(encoding="utf-8") != PUBLIC_HTACCESS:
        raise RuntimeError("Moj Prop access file changed; refusing rollback")
    for relative in sorted(expected, key=lambda item: len(item.parts), reverse=True):
        (ROUTE / relative).unlink()
    htaccess.unlink()
    for directory in sorted(
        {path.parent for path in expected}, key=lambda item: len(item.parts), reverse=True
    ):
        if directory != Path("."):
            (ROUTE / directory).rmdir()
    ROUTE.rmdir()
    manifest["rolled_back"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("MOJ_PROP_ROUTE_ROLLBACK_COMPLETE")


def deploy(run_id: str, commit_sha: str) -> None:
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
        raise RuntimeError("Refusing to replace an existing /moj-prop/ path")

    source_root = staged_root(run_id)
    backup = BACKUPS / f"moj-prop-{run_id}"
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("Moj Prop backup already exists")
    backup.mkdir(mode=0o700, parents=True)
    installed: list[Path] = []
    try:
        ROUTE.mkdir(mode=0o755)
        for relative in FILES:
            content = (source_root / relative).read_bytes()
            target = ROUTE / relative
            atomic_write(target, content)
            installed.append(relative)
        atomic_write(ROUTE / ".htaccess", PUBLIC_HTACCESS.encode("utf-8"))
        manifest = {
            "run_id": run_id,
            "commit_sha": commit_sha,
            "route": "/moj-prop/",
            "route_created": True,
            "files": {
                str(relative): digest((source_root / relative).read_bytes())
                for relative in FILES
            },
            "root_files_modified": False,
        }
        (backup / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        for relative in reversed(installed):
            target = ROUTE / relative
            if target.is_file() and not target.is_symlink():
                target.unlink()
        htaccess = ROUTE / ".htaccess"
        if htaccess.is_file() and not htaccess.is_symlink():
            htaccess.unlink()
        for directory in sorted(
            {relative.parent for relative in installed}, key=lambda item: len(item.parts), reverse=True
        ):
            if directory != Path("."):
                candidate = ROUTE / directory
                if candidate.is_dir() and not candidate.is_symlink():
                    candidate.rmdir()
        if ROUTE.is_dir() and not ROUTE.is_symlink():
            ROUTE.rmdir()
        raise
    print(f"MOJ_PROP_FILES_INSTALLED commit={commit_sha}")
    print("MOJ_PROP_ROUTE=https://mojplaywin.com/moj-prop/")
    print(f"MOJ_PROP_BACKUP={backup}")


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "deploy":
        deploy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit(
            "Usage: deploy_mojplaywin_moj_prop.py deploy RUN_ID COMMIT_SHA | rollback RUN_ID"
        )


if __name__ == "__main__":
    main()
